//! VectorIndex + HNSWIndex — Dense embedding search for the Aether Tree.
//!
//! Provides cosine-similarity search over pre-computed dense embeddings.
//! Two exported classes:
//!
//! - **HNSWIndex**: A pure-Rust HNSW (Hierarchical Navigable Small World) graph
//!   for O(log n) approximate nearest neighbor search.  Parameters match the
//!   Python implementation: M=16, M0=32, ef_construction=200, max_layers=4.
//!
//! - **VectorIndex**: Higher-level wrapper that stores node_id -> embedding
//!   mappings, auto-switches between brute-force (<=1000 vectors) and HNSW
//!   (>1000 vectors), and provides partition mutual information for Phi v3.
//!
//! Thread safety: All mutable state is behind `parking_lot::RwLock` so the
//! indices can be shared across Python threads without the GIL.

use std::collections::{BTreeMap, HashMap, HashSet};

use ordered_float::OrderedFloat;
use parking_lot::RwLock;
use pyo3::prelude::*;
use rand::Rng;

// ---------------------------------------------------------------------------
// Cosine helpers
// ---------------------------------------------------------------------------

/// Cosine similarity in [-1, 1].  Returns 0.0 if either vector has zero norm.
#[inline]
fn cosine_similarity(a: &[f64], b: &[f64]) -> f64 {
    let mut dot = 0.0_f64;
    let mut norm_a = 0.0_f64;
    let mut norm_b = 0.0_f64;
    for (x, y) in a.iter().zip(b.iter()) {
        dot += x * y;
        norm_a += x * x;
        norm_b += y * y;
    }
    if norm_a == 0.0 || norm_b == 0.0 {
        return 0.0;
    }
    dot / (norm_a.sqrt() * norm_b.sqrt())
}

/// Cosine distance: 1.0 - cosine_similarity.  In [0, 2].
#[inline]
fn cosine_distance(a: &[f64], b: &[f64]) -> f64 {
    1.0 - cosine_similarity(a, b)
}

// ---------------------------------------------------------------------------
// Internal HNSW graph (no PyO3 — used by both HNSWIndex and VectorIndex)
// ---------------------------------------------------------------------------

/// Internal HNSW state (not exposed to Python; wrapped by the `#[pyclass]`es).
struct HnswInner {
    m: usize,
    m0: usize,
    ef_construction: usize,
    max_layers: usize,
    ml: f64,

    /// node_id -> embedding vector
    vectors: HashMap<i64, Vec<f64>>,
    /// node_id -> highest layer the node appears in
    node_layers: HashMap<i64, usize>,
    /// layer -> (node_id -> set of connected node_ids)
    graph: Vec<HashMap<i64, HashSet<i64>>>,
    /// Current entry point (node at the highest layer)
    entry_point: Option<i64>,
    /// Highest occupied layer (-1 means empty; stored as Option for clarity)
    max_level: Option<usize>,
    /// Embedding dimension (set on first insert)
    dim: usize,
}

impl HnswInner {
    fn new(max_connections: usize, ef_construction: usize, max_layers: usize) -> Self {
        let m = max_connections.max(2);
        let ml = 1.0 / (m as f64).ln();
        let mut graph = Vec::with_capacity(max_layers);
        for _ in 0..max_layers {
            graph.push(HashMap::new());
        }
        HnswInner {
            m,
            m0: 2 * m,
            ef_construction,
            max_layers,
            ml,
            vectors: HashMap::new(),
            node_layers: HashMap::new(),
            graph,
            entry_point: None,
            max_level: None,
            dim: 0,
        }
    }

    /// Assign a random layer level using exponential decay: floor(-ln(U) * mL).
    fn random_level(&self) -> usize {
        let mut rng = rand::thread_rng();
        let r: f64 = rng.gen::<f64>().max(1e-12);
        let level = (-r.ln() * self.ml) as usize;
        level.min(self.max_layers - 1)
    }

    /// Greedy beam search on a single layer.
    /// Returns vec of (distance, node_id) sorted ascending by distance, up to `ef` items.
    fn search_layer(
        &self,
        query: &[f64],
        entry_point: i64,
        ef: usize,
        layer: usize,
    ) -> Vec<(OrderedFloat<f64>, i64)> {
        let ep_vec = match self.vectors.get(&entry_point) {
            Some(v) => v,
            None => return Vec::new(),
        };
        let dist = OrderedFloat(cosine_distance(query, ep_vec));
        let mut visited = HashSet::new();
        visited.insert(entry_point);

        // Min-heap of candidates (closest first — BTreeMap gives us sorted iteration)
        let mut candidates: BTreeMap<OrderedFloat<f64>, Vec<i64>> = BTreeMap::new();
        candidates.entry(dist).or_default().push(entry_point);

        // Results buffer
        let mut results: Vec<(OrderedFloat<f64>, i64)> = vec![(dist, entry_point)];

        let layer_graph = match self.graph.get(layer) {
            Some(g) => g,
            None => return results,
        };

        loop {
            // Pop closest candidate
            let (c_dist, c_id) = match pop_min(&mut candidates) {
                Some(v) => v,
                None => break,
            };

            // Early termination: closest candidate farther than farthest result
            if results.len() >= ef {
                results.sort_unstable();
                if c_dist > results[results.len() - 1].0 {
                    break;
                }
            }

            // Explore neighbors
            if let Some(neighbors) = layer_graph.get(&c_id) {
                for &neighbor in neighbors {
                    if visited.contains(&neighbor) {
                        continue;
                    }
                    visited.insert(neighbor);

                    let n_vec = match self.vectors.get(&neighbor) {
                        Some(v) => v,
                        None => continue,
                    };
                    let n_dist = OrderedFloat(cosine_distance(query, n_vec));

                    results.sort_unstable();
                    if results.len() < ef || n_dist < results[results.len() - 1].0 {
                        candidates.entry(n_dist).or_default().push(neighbor);
                        results.push((n_dist, neighbor));
                        if results.len() > ef {
                            results.sort_unstable();
                            results.truncate(ef);
                        }
                    }
                }
            }
        }

        results.sort_unstable();
        results.truncate(ef);
        results
    }

    /// Insert a vector into the HNSW graph.
    fn add_vector(&mut self, node_id: i64, embedding: Vec<f64>) {
        if embedding.is_empty() {
            return;
        }
        if self.dim == 0 {
            self.dim = embedding.len();
        }

        self.vectors.insert(node_id, embedding.clone());
        let level = self.random_level();
        self.node_layers.insert(node_id, level);

        // Ensure graph layers exist
        while self.graph.len() <= level {
            self.graph.push(HashMap::new());
        }

        // First node — make it the entry point
        if self.entry_point.is_none() {
            self.entry_point = Some(node_id);
            self.max_level = Some(level);
            for lc in 0..=level {
                self.graph[lc].insert(node_id, HashSet::new());
            }
            return;
        }

        let max_level = self.max_level.unwrap_or(0);

        // Traverse from top layer down to level+1, greedy with ef=1
        let mut current_entry = self.entry_point.unwrap();
        for lc in (level + 1..=max_level).rev() {
            if lc < self.graph.len() && self.graph[lc].contains_key(&current_entry) {
                let result = self.search_layer(&embedding, current_entry, 1, lc);
                if let Some((_d, nid)) = result.first() {
                    current_entry = *nid;
                }
            }
        }

        // For layers min(level, max_level) down to 0, find & connect neighbors
        let start_layer = level.min(max_level);
        for lc in (0..=start_layer).rev() {
            let max_conn = if lc == 0 { self.m0 } else { self.m };

            // Ensure node has adjacency list at this layer
            if !self.graph[lc].contains_key(&node_id) {
                self.graph[lc].insert(node_id, HashSet::new());
            }

            // Search for nearest neighbors
            let candidates = if self.vectors.contains_key(&current_entry) {
                self.search_layer(&embedding, current_entry, self.ef_construction, lc)
            } else {
                Vec::new()
            };

            // Select best neighbors (simple: take closest max_conn)
            let neighbors: Vec<(OrderedFloat<f64>, i64)> =
                candidates.iter().take(max_conn).cloned().collect();

            // Add bidirectional connections
            for &(_dist, neighbor_id) in &neighbors {
                if neighbor_id == node_id {
                    continue;
                }
                self.graph[lc]
                    .entry(node_id)
                    .or_default()
                    .insert(neighbor_id);
                self.graph[lc]
                    .entry(neighbor_id)
                    .or_default()
                    .insert(node_id);

                // Prune neighbor if over limit
                let neighbor_conns = self.graph[lc].entry(neighbor_id).or_default();
                if neighbor_conns.len() > max_conn {
                    let n_emb = self.vectors.get(&neighbor_id).cloned();
                    if let Some(ref n_emb) = n_emb {
                        let mut scored: Vec<(OrderedFloat<f64>, i64)> = neighbor_conns
                            .iter()
                            .filter_map(|&conn| {
                                self.vectors
                                    .get(&conn)
                                    .map(|v| (OrderedFloat(cosine_distance(n_emb, v)), conn))
                            })
                            .collect();
                        scored.sort_unstable();
                        scored.truncate(max_conn);
                        let keep: HashSet<i64> = scored.into_iter().map(|(_, id)| id).collect();
                        *self.graph[lc].get_mut(&neighbor_id).unwrap() = keep;
                    }
                }
            }

            if let Some(first) = candidates.first() {
                current_entry = first.1;
            }
        }

        // Update entry point if new node is at a higher level
        if level > max_level {
            self.entry_point = Some(node_id);
            self.max_level = Some(level);
        }
    }

    /// Search for k approximate nearest neighbors.
    /// Returns vec of (node_id, cosine_similarity), highest similarity first.
    fn search(&self, query: &[f64], k: usize, ef_search: usize) -> Vec<(i64, f64)> {
        if self.vectors.is_empty() || self.entry_point.is_none() {
            return Vec::new();
        }
        let ef = if ef_search == 0 { k.max(50) } else { ef_search };

        let max_level = self.max_level.unwrap_or(0);
        let mut current_entry = self.entry_point.unwrap();

        // Traverse from top layer to layer 1 with ef=1
        for lc in (1..=max_level).rev() {
            if lc < self.graph.len() && self.graph[lc].contains_key(&current_entry) {
                let result = self.search_layer(query, current_entry, 1, lc);
                if let Some((_d, nid)) = result.first() {
                    current_entry = *nid;
                }
            }
        }

        // Search layer 0 with full ef
        let candidates = self.search_layer(query, current_entry, ef, 0);

        // Convert distance to similarity, take top k
        candidates
            .iter()
            .take(k)
            .map(|(dist, nid)| (*nid, 1.0 - dist.0))
            .collect()
    }

    /// Remove a vector and all its connections from the graph.
    fn remove(&mut self, node_id: i64) {
        if !self.vectors.contains_key(&node_id) {
            return;
        }

        let level = self.node_layers.get(&node_id).copied().unwrap_or(0);

        // Remove from all layers
        for lc in 0..=level {
            if lc < self.graph.len() {
                // Remove from neighbors' adjacency lists
                if let Some(neighbors) = self.graph[lc].get(&node_id).cloned() {
                    for neighbor in &neighbors {
                        if let Some(adj) = self.graph[lc].get_mut(neighbor) {
                            adj.remove(&node_id);
                        }
                    }
                }
                self.graph[lc].remove(&node_id);
            }
        }

        self.vectors.remove(&node_id);
        self.node_layers.remove(&node_id);

        // Update entry point if needed
        if self.entry_point == Some(node_id) {
            if self.vectors.is_empty() {
                self.entry_point = None;
                self.max_level = None;
            } else {
                let mut best_id: Option<i64> = None;
                let mut best_level: usize = 0;
                for (&nid, &nlevel) in &self.node_layers {
                    if best_id.is_none() || nlevel > best_level {
                        best_level = nlevel;
                        best_id = Some(nid);
                    }
                }
                self.entry_point = best_id;
                self.max_level = Some(best_level);
            }
        }
    }

    fn len(&self) -> usize {
        self.vectors.len()
    }

    fn contains(&self, node_id: i64) -> bool {
        self.vectors.contains_key(&node_id)
    }

    fn get_stats(&self, py: Python<'_>) -> HashMap<String, PyObject> {
        let total_edges: usize = self
            .graph
            .iter()
            .map(|layer| layer.values().map(|adj| adj.len()).sum::<usize>())
            .sum();

        let mut d: HashMap<String, PyObject> = HashMap::new();
        d.insert(
            "total_vectors".into(),
            self.vectors.len().into_pyobject(py).unwrap().into(),
        );
        d.insert(
            "max_level".into(),
            self.max_level
                .map(|l| l as i64)
                .unwrap_or(-1)
                .into_pyobject(py)
                .unwrap()
                .into(),
        );
        d.insert(
            "entry_point".into(),
            match self.entry_point {
                Some(ep) => ep.into_pyobject(py).unwrap().into(),
                None => py.None(),
            },
        );
        d.insert(
            "total_edges".into(),
            total_edges.into_pyobject(py).unwrap().into(),
        );
        d.insert("dim".into(), self.dim.into_pyobject(py).unwrap().into());
        d.insert(
            "M".into(),
            self.m.into_pyobject(py).unwrap().into(),
        );
        d.insert(
            "ef_construction".into(),
            self.ef_construction.into_pyobject(py).unwrap().into(),
        );
        d
    }
}

/// Pop the smallest entry from a BTreeMap<OrderedFloat<f64>, Vec<i64>>.
fn pop_min(map: &mut BTreeMap<OrderedFloat<f64>, Vec<i64>>) -> Option<(OrderedFloat<f64>, i64)> {
    let key = *map.keys().next()?;
    let list = map.get_mut(&key)?;
    let val = list.pop()?;
    if list.is_empty() {
        map.remove(&key);
    }
    Some((key, val))
}

// ---------------------------------------------------------------------------
// HNSWIndex — PyO3 class
// ---------------------------------------------------------------------------

/// Pure-Rust HNSW graph for O(log n) approximate nearest neighbor search.
///
/// Implements the core HNSW algorithm from Malkov & Yashunin (2016/2018):
/// - Multi-layer navigable small world graph
/// - Greedy search with beam width (ef)
/// - Layer assignment via exponential decay: floor(-ln(uniform) * mL)
/// - Cosine similarity as distance metric
///
/// Parameters:
///     max_connections: Max connections per node per layer (M). Default 16.
///     ef_construction: Beam width during construction. Default 200.
///     max_layers: Maximum hierarchy depth. Default 4.
#[pyclass]
pub struct HNSWIndex {
    inner: RwLock<HnswInner>,
}

#[pymethods]
impl HNSWIndex {
    /// Create a new HNSWIndex.
    #[new]
    #[pyo3(signature = (max_connections = 16, ef_construction = 200, max_layers = 4))]
    pub fn new(max_connections: usize, ef_construction: usize, max_layers: usize) -> Self {
        HNSWIndex {
            inner: RwLock::new(HnswInner::new(max_connections, ef_construction, max_layers)),
        }
    }

    /// Insert a vector into the HNSW graph.
    ///
    /// Args:
    ///     node_id: Unique identifier for the vector.
    ///     embedding: Dense embedding vector (list of floats).
    pub fn add_vector(&self, node_id: i64, embedding: Vec<f64>) {
        self.inner.write().add_vector(node_id, embedding);
    }

    /// Find k approximate nearest neighbors.
    ///
    /// Args:
    ///     query_embedding: Query vector.
    ///     k: Number of neighbors to return. Default 5.
    ///     ef_search: Search beam width. Default max(k, 50).
    ///
    /// Returns:
    ///     List of (node_id, cosine_similarity) tuples, highest similarity first.
    #[pyo3(signature = (query_embedding, k = 5, ef_search = 0))]
    pub fn search(
        &self,
        query_embedding: Vec<f64>,
        k: usize,
        ef_search: usize,
    ) -> Vec<(i64, f64)> {
        self.inner.read().search(&query_embedding, k, ef_search)
    }

    /// Remove a vector from the HNSW graph.
    pub fn remove(&self, node_id: i64) {
        self.inner.write().remove(node_id);
    }

    /// Check if a node_id is in the index.
    pub fn __contains__(&self, node_id: i64) -> bool {
        self.inner.read().contains(node_id)
    }

    /// Number of vectors in the index.
    pub fn __len__(&self) -> usize {
        self.inner.read().len()
    }

    /// Return HNSW index statistics as a dict.
    pub fn get_stats(&self, py: Python<'_>) -> HashMap<String, PyObject> {
        self.inner.read().get_stats(py)
    }
}

// ---------------------------------------------------------------------------
// VectorIndex — PyO3 class
// ---------------------------------------------------------------------------

/// Internal state for VectorIndex, behind RwLock.
struct VectorIndexInner {
    /// node_id -> embedding vector
    embeddings: HashMap<i64, Vec<f64>>,
    /// Embedding dimension (set on first add)
    dim: usize,
    /// Pure-Rust HNSW index (lazy-built when dirty and enough embeddings)
    hnsw: Option<HnswInner>,
    /// Whether the HNSW index needs a rebuild
    hnsw_dirty: bool,
    /// User override: None = auto, true = always HNSW, false = never HNSW
    use_hnsw: Option<bool>,
}

/// Auto-switch threshold: use HNSW when vector count exceeds this.
const HNSW_AUTO_THRESHOLD: usize = 1000;

impl VectorIndexInner {
    fn new(use_hnsw: Option<bool>) -> Self {
        VectorIndexInner {
            embeddings: HashMap::new(),
            dim: 0,
            hnsw: None,
            hnsw_dirty: true,
            use_hnsw,
        }
    }

    fn should_use_hnsw(&self) -> bool {
        match self.use_hnsw {
            Some(true) => true,
            Some(false) => false,
            None => self.embeddings.len() > HNSW_AUTO_THRESHOLD,
        }
    }

    /// Ensure the HNSW index is built and current.  Returns reference if available.
    fn ensure_hnsw(&mut self) -> bool {
        if !self.should_use_hnsw() || self.embeddings.is_empty() {
            return false;
        }
        if !self.hnsw_dirty && self.hnsw.is_some() {
            return true;
        }
        // Rebuild from scratch
        let mut hnsw = HnswInner::new(16, 200, 4);
        for (&nid, emb) in &self.embeddings {
            hnsw.add_vector(nid, emb.clone());
        }
        self.hnsw = Some(hnsw);
        self.hnsw_dirty = false;
        true
    }

    fn add_embedding(&mut self, node_id: i64, embedding: Vec<f64>) {
        if embedding.is_empty() {
            return;
        }
        if self.dim == 0 {
            self.dim = embedding.len();
        }
        self.embeddings.insert(node_id, embedding);
        self.hnsw_dirty = true;
    }

    fn get_embedding(&self, node_id: i64) -> Option<Vec<f64>> {
        self.embeddings.get(&node_id).cloned()
    }

    fn remove_embedding(&mut self, node_id: i64) {
        self.embeddings.remove(&node_id);
        self.hnsw_dirty = true;
    }

    fn query_by_embedding(&mut self, query_emb: &[f64], top_k: usize) -> Vec<(i64, f64)> {
        if self.embeddings.is_empty() {
            return Vec::new();
        }

        // Try HNSW
        if self.ensure_hnsw() {
            if let Some(ref hnsw) = self.hnsw {
                return hnsw.search(query_emb, top_k, 0);
            }
        }

        // Brute-force fallback
        let mut scores: Vec<(i64, f64)> = self
            .embeddings
            .iter()
            .map(|(&nid, emb)| (nid, cosine_similarity(query_emb, emb)))
            .collect();
        scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        scores.truncate(top_k);
        scores
    }

    fn find_near_duplicates(&mut self, threshold: f64) -> Vec<(i64, i64, f64)> {
        let ids: Vec<i64> = self.embeddings.keys().copied().collect();
        let mut duplicates: Vec<(i64, i64, f64)> = Vec::new();

        // HNSW-accelerated duplicate detection for large indices
        if self.ensure_hnsw() && ids.len() > 100 {
            if let Some(ref hnsw) = self.hnsw {
                let mut seen_pairs: HashSet<(i64, i64)> = HashSet::new();
                let k = ids.len().min(10);
                for &nid in &ids {
                    if let Some(emb) = self.embeddings.get(&nid) {
                        let results = hnsw.search(emb, k, 0);
                        for (other_nid, sim) in results {
                            if other_nid == nid {
                                continue;
                            }
                            if sim >= threshold {
                                let pair = (nid.min(other_nid), nid.max(other_nid));
                                if seen_pairs.insert(pair) {
                                    duplicates.push((pair.0, pair.1, sim));
                                }
                            }
                        }
                    }
                }
                return duplicates;
            }
        }

        // Brute-force O(n^2) fallback
        for i in 0..ids.len() {
            let emb_i = match self.embeddings.get(&ids[i]) {
                Some(e) => e,
                None => continue,
            };
            for j in (i + 1)..ids.len() {
                let emb_j = match self.embeddings.get(&ids[j]) {
                    Some(e) => e,
                    None => continue,
                };
                let sim = cosine_similarity(emb_i, emb_j);
                if sim >= threshold {
                    duplicates.push((ids[i], ids[j], sim));
                }
            }
        }
        duplicates
    }

    fn compute_partition_mutual_info(
        &self,
        partition_a: &[i64],
        partition_b: &[i64],
    ) -> f64 {
        let embs_a: Vec<&Vec<f64>> = partition_a
            .iter()
            .filter_map(|nid| self.embeddings.get(nid))
            .collect();
        let embs_b: Vec<&Vec<f64>> = partition_b
            .iter()
            .filter_map(|nid| self.embeddings.get(nid))
            .collect();

        if embs_a.is_empty() || embs_b.is_empty() {
            return 0.0;
        }

        let h_a = embedding_entropy(&embs_a);
        let h_b = embedding_entropy(&embs_b);

        let combined: Vec<&Vec<f64>> = embs_a.iter().chain(embs_b.iter()).copied().collect();
        let h_ab = embedding_entropy(&combined);

        // Mutual information (clamp non-negative due to estimation noise)
        (h_a + h_b - h_ab).max(0.0)
    }

    fn size(&self) -> usize {
        self.embeddings.len()
    }
}

/// Estimate entropy of an embedding distribution.
///
/// Uses per-dimension variance as a Gaussian proxy:
///   H approx = 0.5 * sum_d(log(2 pi e * var_d))
///
/// Returns max(0, entropy).
fn embedding_entropy(embeddings: &[&Vec<f64>]) -> f64 {
    if embeddings.is_empty() {
        return 0.0;
    }
    let dim = embeddings[0].len();
    if dim == 0 {
        return 0.0;
    }
    let n = embeddings.len();
    if n < 2 {
        return 0.0;
    }

    let two_pi_e = 2.0 * std::f64::consts::PI * std::f64::consts::E;
    let n_f = n as f64;
    let mut entropy = 0.0_f64;

    for d in 0..dim {
        let mut sum = 0.0_f64;
        for emb in embeddings {
            sum += emb[d];
        }
        let mean = sum / n_f;
        let mut var = 0.0_f64;
        for emb in embeddings {
            let diff = emb[d] - mean;
            var += diff * diff;
        }
        var /= n_f;
        if var > 1e-12 {
            entropy += 0.5 * (two_pi_e * var).ln();
        }
    }

    entropy.max(0.0)
}

/// Dense embedding index over knowledge graph nodes.
///
/// Stores node_id -> embedding mappings and supports:
/// - Incremental add/remove of pre-computed embeddings
/// - Cosine similarity search (HNSW for >1000 vectors, brute-force otherwise)
/// - Near-duplicate detection
/// - Partition mutual information for Phi v3 integration score
///
/// Thread-safe: internal state is behind a RwLock.
///
/// Args:
///     use_hnsw: None = auto (switch at >1000 vectors), True = always, False = never.
#[pyclass]
pub struct VectorIndex {
    inner: RwLock<VectorIndexInner>,
}

#[pymethods]
impl VectorIndex {
    #[new]
    #[pyo3(signature = (use_hnsw = None))]
    pub fn new(use_hnsw: Option<bool>) -> Self {
        VectorIndex {
            inner: RwLock::new(VectorIndexInner::new(use_hnsw)),
        }
    }

    /// Store a pre-computed embedding for a node.
    ///
    /// Args:
    ///     node_id: Knowledge graph node ID.
    ///     embedding: Dense float vector.
    pub fn add_embedding(&self, node_id: i64, embedding: Vec<f64>) {
        self.inner.write().add_embedding(node_id, embedding);
    }

    /// Get the stored embedding for a node, or None if not present.
    pub fn get_embedding(&self, node_id: i64) -> Option<Vec<f64>> {
        self.inner.read().get_embedding(node_id)
    }

    /// Remove a node's embedding from the index.
    pub fn remove_embedding(&self, node_id: i64) {
        self.inner.write().remove_embedding(node_id);
    }

    /// Search by pre-computed embedding vector.
    ///
    /// Returns list of (node_id, cosine_similarity), highest similarity first.
    ///
    /// Args:
    ///     query_emb: Query embedding vector.
    ///     top_k: Number of results. Default 10.
    #[pyo3(signature = (query_emb, top_k = 10))]
    pub fn query_by_embedding(&self, query_emb: Vec<f64>, top_k: usize) -> Vec<(i64, f64)> {
        self.inner.write().query_by_embedding(&query_emb, top_k)
    }

    /// Find pairs of nodes with cosine similarity above threshold.
    ///
    /// Returns list of (node_a, node_b, similarity) tuples.
    ///
    /// Args:
    ///     threshold: Minimum cosine similarity. Default 0.95.
    #[pyo3(signature = (threshold = 0.95))]
    pub fn find_near_duplicates(&self, threshold: f64) -> Vec<(i64, i64, f64)> {
        self.inner.write().find_near_duplicates(threshold)
    }

    /// Compute approximate mutual information between two graph partitions.
    ///
    /// Uses embedding distributions to estimate I(A;B) = H(A) + H(B) - H(A,B).
    /// Used by Phi v3 for information-theoretic integration.
    ///
    /// Args:
    ///     partition_a: List of node IDs in partition A.
    ///     partition_b: List of node IDs in partition B.
    pub fn compute_partition_mutual_info(
        &self,
        partition_a: Vec<i64>,
        partition_b: Vec<i64>,
    ) -> f64 {
        self.inner
            .read()
            .compute_partition_mutual_info(&partition_a, &partition_b)
    }

    /// Return index statistics as a dict.
    pub fn get_stats(&self) -> HashMap<String, PyObject> {
        let inner = self.inner.read();
        Python::with_gil(|py| {
            let mut d: HashMap<String, PyObject> = HashMap::new();
            d.insert(
                "total_embeddings".into(),
                inner.embeddings.len().into_pyobject(py).unwrap().into(),
            );
            d.insert(
                "embedding_dim".into(),
                inner.dim.into_pyobject(py).unwrap().into(),
            );
            let uses_hnsw = inner.hnsw.is_some() && !inner.hnsw_dirty;
            d.insert(
                "uses_hnsw".into(),
                uses_hnsw.into_pyobject(py).unwrap().to_owned().into(),
            );
            let mode_str = match inner.use_hnsw {
                None => "auto",
                Some(true) => "true",
                Some(false) => "false",
            };
            d.insert(
                "hnsw_mode".into(),
                mode_str.into_pyobject(py).unwrap().into(),
            );
            d.insert(
                "hnsw_auto_threshold".into(),
                HNSW_AUTO_THRESHOLD.into_pyobject(py).unwrap().into(),
            );
            if let Some(ref hnsw) = inner.hnsw {
                if !inner.hnsw_dirty {
                    d.insert("hnsw_stats".into(), hnsw.get_stats(py).into_pyobject(py).unwrap().into());
                }
            }
            d
        })
    }

    /// Number of stored embeddings.
    #[getter]
    pub fn size(&self) -> usize {
        self.inner.read().size()
    }

    /// Number of stored embeddings (len protocol).
    pub fn __len__(&self) -> usize {
        self.inner.read().size()
    }

    /// Check if a node_id has a stored embedding.
    pub fn __contains__(&self, node_id: i64) -> bool {
        self.inner.read().embeddings.contains_key(&node_id)
    }
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Helper: create a normalized vector in a given direction.
    fn make_vec(dim: usize, seed: u64) -> Vec<f64> {
        let mut v = vec![0.0; dim];
        // Deterministic pseudo-random fill using a simple LCG
        let mut state = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
        for x in v.iter_mut() {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            *x = ((state >> 33) as f64) / (u32::MAX as f64) - 0.5;
        }
        // L2 normalize
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm > 0.0 {
            for x in v.iter_mut() {
                *x /= norm;
            }
        }
        v
    }

    /// Helper: create a vector close to another (high cosine similarity).
    fn make_similar(base: &[f64], noise: f64) -> Vec<f64> {
        let mut v: Vec<f64> = base
            .iter()
            .enumerate()
            .map(|(i, &x)| x + noise * ((i as f64 * 0.7).sin()) * 0.01)
            .collect();
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm > 0.0 {
            for x in v.iter_mut() {
                *x /= norm;
            }
        }
        v
    }

    // -----------------------------------------------------------------------
    // Cosine function tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_cosine_similarity_identical() {
        let v = vec![1.0, 2.0, 3.0];
        let sim = cosine_similarity(&v, &v);
        assert!((sim - 1.0).abs() < 1e-10, "identical vectors should have sim=1.0");
    }

    #[test]
    fn test_cosine_similarity_orthogonal() {
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![0.0, 1.0, 0.0];
        let sim = cosine_similarity(&a, &b);
        assert!(sim.abs() < 1e-10, "orthogonal vectors should have sim=0.0");
    }

    #[test]
    fn test_cosine_similarity_opposite() {
        let a = vec![1.0, 2.0, 3.0];
        let b: Vec<f64> = a.iter().map(|x| -x).collect();
        let sim = cosine_similarity(&a, &b);
        assert!((sim - (-1.0)).abs() < 1e-10, "opposite vectors should have sim=-1.0");
    }

    #[test]
    fn test_cosine_distance_identical() {
        let v = vec![1.0, 0.5, 0.3];
        let dist = cosine_distance(&v, &v);
        assert!(dist.abs() < 1e-10, "distance to self should be 0");
    }

    #[test]
    fn test_cosine_zero_vector() {
        let a = vec![0.0, 0.0, 0.0];
        let b = vec![1.0, 2.0, 3.0];
        assert_eq!(cosine_similarity(&a, &b), 0.0);
        assert_eq!(cosine_distance(&a, &b), 1.0);
    }

    // -----------------------------------------------------------------------
    // HNSWIndex tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_hnsw_insert_and_len() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        assert_eq!(hnsw.len(), 0);

        hnsw.add_vector(1, vec![1.0, 0.0, 0.0]);
        assert_eq!(hnsw.len(), 1);

        hnsw.add_vector(2, vec![0.0, 1.0, 0.0]);
        assert_eq!(hnsw.len(), 2);

        assert!(hnsw.contains(1));
        assert!(hnsw.contains(2));
        assert!(!hnsw.contains(3));
    }

    #[test]
    fn test_hnsw_insert_empty_embedding_ignored() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        hnsw.add_vector(1, vec![]);
        assert_eq!(hnsw.len(), 0);
    }

    #[test]
    fn test_hnsw_search_exact_match() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        let dim = 32;

        // Insert 50 random vectors
        for i in 0..50 {
            hnsw.add_vector(i, make_vec(dim, i as u64));
        }

        // Search for vector 7 — it should be the top result
        let query = make_vec(dim, 7);
        let results = hnsw.search(&query, 5, 0);
        assert!(!results.is_empty(), "search should return results");
        assert_eq!(results[0].0, 7, "top result should be the exact vector");
        assert!(
            (results[0].1 - 1.0).abs() < 1e-6,
            "similarity to self should be ~1.0, got {}",
            results[0].1
        );
    }

    #[test]
    fn test_hnsw_search_returns_k_results() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        let dim = 16;

        for i in 0..100 {
            hnsw.add_vector(i, make_vec(dim, i as u64));
        }

        let query = make_vec(dim, 42);
        let results = hnsw.search(&query, 10, 0);
        assert_eq!(results.len(), 10, "should return exactly k=10 results");

        // Results should be sorted by similarity descending
        for i in 1..results.len() {
            assert!(
                results[i - 1].1 >= results[i].1 - 1e-10,
                "results should be sorted descending by similarity"
            );
        }
    }

    #[test]
    fn test_hnsw_search_empty_index() {
        let hnsw = HnswInner::new(16, 200, 4);
        let results = hnsw.search(&[1.0, 0.0], 5, 0);
        assert!(results.is_empty());
    }

    #[test]
    fn test_hnsw_search_single_element() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        hnsw.add_vector(42, vec![1.0, 0.0, 0.0]);

        let results = hnsw.search(&[1.0, 0.0, 0.0], 5, 0);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].0, 42);
        assert!((results[0].1 - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_hnsw_remove() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        let dim = 16;

        for i in 0..20 {
            hnsw.add_vector(i, make_vec(dim, i as u64));
        }
        assert_eq!(hnsw.len(), 20);

        hnsw.remove(5);
        assert_eq!(hnsw.len(), 19);
        assert!(!hnsw.contains(5));

        // Search should not return removed node
        let query = make_vec(dim, 5);
        let results = hnsw.search(&query, 20, 0);
        for (nid, _sim) in &results {
            assert_ne!(*nid, 5, "removed node should not appear in results");
        }
    }

    #[test]
    fn test_hnsw_remove_entry_point() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        hnsw.add_vector(1, vec![1.0, 0.0]);
        hnsw.add_vector(2, vec![0.0, 1.0]);

        let ep = hnsw.entry_point.unwrap();
        hnsw.remove(ep);
        assert_eq!(hnsw.len(), 1);
        assert!(hnsw.entry_point.is_some(), "should have a new entry point");
        assert_ne!(hnsw.entry_point.unwrap(), ep);
    }

    #[test]
    fn test_hnsw_remove_all() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        hnsw.add_vector(1, vec![1.0, 0.0]);
        hnsw.add_vector(2, vec![0.0, 1.0]);

        hnsw.remove(1);
        hnsw.remove(2);
        assert_eq!(hnsw.len(), 0);
        assert!(hnsw.entry_point.is_none());
        assert!(hnsw.max_level.is_none());
    }

    #[test]
    fn test_hnsw_remove_nonexistent() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        hnsw.add_vector(1, vec![1.0, 0.0]);
        hnsw.remove(999); // should not panic
        assert_eq!(hnsw.len(), 1);
    }

    #[test]
    fn test_hnsw_get_stats() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        for i in 0..10 {
            hnsw.add_vector(i, make_vec(8, i as u64));
        }
        Python::with_gil(|py| {
            let stats = hnsw.get_stats(py);
            assert!(stats.contains_key("total_vectors"));
            let total: usize = stats["total_vectors"].extract(py).unwrap();
            assert_eq!(total, 10);
            let m_val: usize = stats["M"].extract(py).unwrap();
            assert_eq!(m_val, 16);
        });
    }

    #[test]
    fn test_hnsw_duplicate_insert_overwrites() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        hnsw.add_vector(1, vec![1.0, 0.0, 0.0]);
        hnsw.add_vector(1, vec![0.0, 1.0, 0.0]); // overwrite vector

        assert_eq!(hnsw.len(), 1); // still just 1 node (vector replaced in HashMap)

        // The stored vector should be the second one
        let results = hnsw.search(&[0.0, 1.0, 0.0], 1, 0);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].0, 1);
        assert!((results[0].1 - 1.0).abs() < 1e-6);
    }

    // -----------------------------------------------------------------------
    // VectorIndex tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_vector_index_add_and_get() {
        let mut vi = VectorIndexInner::new(Some(false)); // brute-force only
        vi.add_embedding(1, vec![1.0, 0.0, 0.0]);
        vi.add_embedding(2, vec![0.0, 1.0, 0.0]);
        vi.add_embedding(3, vec![0.0, 0.0, 1.0]);

        assert_eq!(vi.size(), 3);
        assert_eq!(vi.dim, 3);

        let e = vi.get_embedding(1).unwrap();
        assert_eq!(e, vec![1.0, 0.0, 0.0]);

        assert!(vi.get_embedding(999).is_none());
    }

    #[test]
    fn test_vector_index_add_empty_ignored() {
        let mut vi = VectorIndexInner::new(None);
        vi.add_embedding(1, vec![]);
        assert_eq!(vi.size(), 0);
    }

    #[test]
    fn test_vector_index_remove() {
        let mut vi = VectorIndexInner::new(Some(false));
        vi.add_embedding(1, vec![1.0, 0.0]);
        vi.add_embedding(2, vec![0.0, 1.0]);
        assert_eq!(vi.size(), 2);

        vi.remove_embedding(1);
        assert_eq!(vi.size(), 1);
        assert!(vi.get_embedding(1).is_none());
        assert!(vi.get_embedding(2).is_some());
    }

    #[test]
    fn test_vector_index_bruteforce_search() {
        let mut vi = VectorIndexInner::new(Some(false)); // force brute-force
        let dim = 16;

        for i in 0..50 {
            vi.add_embedding(i, make_vec(dim, i as u64));
        }

        let query = make_vec(dim, 7);
        let results = vi.query_by_embedding(&query, 5);

        assert!(!results.is_empty());
        assert_eq!(results[0].0, 7, "top result should be exact match");
        assert!(
            (results[0].1 - 1.0).abs() < 1e-6,
            "similarity to self should be ~1.0"
        );

        // Sorted descending by similarity
        for i in 1..results.len() {
            assert!(results[i - 1].1 >= results[i].1 - 1e-10);
        }
    }

    #[test]
    fn test_vector_index_hnsw_search() {
        let mut vi = VectorIndexInner::new(Some(true)); // force HNSW
        let dim = 16;

        for i in 0..50 {
            vi.add_embedding(i, make_vec(dim, i as u64));
        }

        let query = make_vec(dim, 25);
        let results = vi.query_by_embedding(&query, 5);

        assert!(!results.is_empty());
        assert_eq!(results[0].0, 25, "HNSW should find exact match");
        assert!((results[0].1 - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_vector_index_search_empty() {
        let mut vi = VectorIndexInner::new(None);
        let results = vi.query_by_embedding(&[1.0, 0.0], 5);
        assert!(results.is_empty());
    }

    #[test]
    fn test_vector_index_search_more_than_available() {
        let mut vi = VectorIndexInner::new(Some(false));
        vi.add_embedding(1, vec![1.0, 0.0]);
        vi.add_embedding(2, vec![0.0, 1.0]);

        let results = vi.query_by_embedding(&[1.0, 0.0], 100);
        assert_eq!(results.len(), 2, "should return all available when k > n");
    }

    // -----------------------------------------------------------------------
    // Near-duplicate detection tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_find_near_duplicates_exact() {
        let mut vi = VectorIndexInner::new(Some(false));
        let base = vec![1.0, 2.0, 3.0, 4.0];
        // Normalize
        let norm: f64 = base.iter().map(|x| x * x).sum::<f64>().sqrt();
        let base_norm: Vec<f64> = base.iter().map(|x| x / norm).collect();

        vi.add_embedding(1, base_norm.clone());
        vi.add_embedding(2, base_norm.clone()); // exact duplicate
        vi.add_embedding(3, vec![0.0, 0.0, 0.0, 1.0]); // very different

        let dups = vi.find_near_duplicates(0.99);
        assert_eq!(dups.len(), 1, "should find exactly 1 duplicate pair");
        let (a, b, sim) = &dups[0];
        assert!((*a == 1 && *b == 2) || (*a == 2 && *b == 1));
        assert!(
            (*sim - 1.0).abs() < 1e-10,
            "exact duplicates should have sim=1.0"
        );
    }

    #[test]
    fn test_find_near_duplicates_similar() {
        let mut vi = VectorIndexInner::new(Some(false));
        let dim = 32;
        let base = make_vec(dim, 100);
        let similar = make_similar(&base, 1.0);
        let different = make_vec(dim, 999);

        vi.add_embedding(1, base.clone());
        vi.add_embedding(2, similar);
        vi.add_embedding(3, different);

        let sim_12 = cosine_similarity(
            vi.get_embedding(1).unwrap().as_slice(),
            vi.get_embedding(2).unwrap().as_slice(),
        );
        // The similar vector should have high similarity
        assert!(
            sim_12 > 0.95,
            "similar vectors should have cosine sim > 0.95, got {}",
            sim_12
        );

        let dups = vi.find_near_duplicates(0.95);
        assert!(
            !dups.is_empty(),
            "should find near-duplicate pair with threshold 0.95"
        );

        // Node 3 should NOT be a near-duplicate of 1 or 2
        for (a, b, _sim) in &dups {
            assert!(*a != 3 || *b != 1);
            assert!(*a != 3 || *b != 2);
            assert!(*a != 1 || *b != 3);
            assert!(*a != 2 || *b != 3);
        }
    }

    #[test]
    fn test_find_near_duplicates_none() {
        let mut vi = VectorIndexInner::new(Some(false));
        vi.add_embedding(1, vec![1.0, 0.0, 0.0]);
        vi.add_embedding(2, vec![0.0, 1.0, 0.0]);
        vi.add_embedding(3, vec![0.0, 0.0, 1.0]);

        let dups = vi.find_near_duplicates(0.95);
        assert!(dups.is_empty(), "orthogonal vectors should have no near-duplicates");
    }

    #[test]
    fn test_find_near_duplicates_empty() {
        let mut vi = VectorIndexInner::new(None);
        let dups = vi.find_near_duplicates(0.95);
        assert!(dups.is_empty());
    }

    // -----------------------------------------------------------------------
    // Partition mutual information tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_mutual_info_identical_partitions() {
        let vi = {
            let mut vi = VectorIndexInner::new(None);
            let dim = 8;
            for i in 0..20 {
                vi.add_embedding(i, make_vec(dim, i as u64));
            }
            vi
        };

        let ids: Vec<i64> = (0..20).collect();
        // MI of a partition with itself should be positive and equal to entropy
        let mi = vi.compute_partition_mutual_info(&ids, &ids);
        // I(A; A) = H(A) + H(A) - H(A) = H(A) >= 0
        assert!(mi >= 0.0, "MI should be non-negative, got {}", mi);
    }

    #[test]
    fn test_mutual_info_disjoint_different() {
        let vi = {
            let mut vi = VectorIndexInner::new(None);
            // Partition A: all vectors along x-axis direction
            for i in 0..10 {
                let mut v = vec![0.0; 8];
                v[0] = 1.0 + (i as f64) * 0.01;
                vi.add_embedding(i, v);
            }
            // Partition B: all vectors along y-axis direction
            for i in 10..20 {
                let mut v = vec![0.0; 8];
                v[1] = 1.0 + ((i - 10) as f64) * 0.01;
                vi.add_embedding(i, v);
            }
            vi
        };

        let part_a: Vec<i64> = (0..10).collect();
        let part_b: Vec<i64> = (10..20).collect();

        let mi = vi.compute_partition_mutual_info(&part_a, &part_b);
        assert!(mi >= 0.0, "MI should be non-negative, got {}", mi);
        // MI should be relatively small for independent partitions
        // (not necessarily zero due to Gaussian approximation, but bounded)
    }

    #[test]
    fn test_mutual_info_empty_partition() {
        let vi = {
            let mut vi = VectorIndexInner::new(None);
            vi.add_embedding(1, vec![1.0, 0.0]);
            vi
        };

        // One partition empty
        let mi = vi.compute_partition_mutual_info(&[1], &[999]);
        assert_eq!(mi, 0.0, "MI with missing nodes should be 0.0");

        let mi = vi.compute_partition_mutual_info(&[], &[1]);
        assert_eq!(mi, 0.0, "MI with empty partition should be 0.0");
    }

    #[test]
    fn test_mutual_info_single_element_partitions() {
        let vi = {
            let mut vi = VectorIndexInner::new(None);
            vi.add_embedding(1, vec![1.0, 0.0, 0.0]);
            vi.add_embedding(2, vec![0.0, 1.0, 0.0]);
            vi
        };

        // Single-element partitions have zero entropy (n < 2), so MI = 0
        let mi = vi.compute_partition_mutual_info(&[1], &[2]);
        assert_eq!(mi, 0.0, "single-element partitions should yield MI=0");
    }

    // -----------------------------------------------------------------------
    // Embedding entropy tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_embedding_entropy_empty() {
        let embs: Vec<&Vec<f64>> = vec![];
        assert_eq!(embedding_entropy(&embs), 0.0);
    }

    #[test]
    fn test_embedding_entropy_single() {
        let v = vec![1.0, 2.0, 3.0];
        let embs = vec![&v];
        assert_eq!(embedding_entropy(&embs), 0.0, "single embedding has zero entropy");
    }

    #[test]
    fn test_embedding_entropy_identical() {
        let v = vec![1.0, 2.0, 3.0];
        let embs = vec![&v, &v, &v];
        assert_eq!(
            embedding_entropy(&embs),
            0.0,
            "identical embeddings have zero variance = zero entropy"
        );
    }

    #[test]
    fn test_embedding_entropy_positive_for_diverse() {
        let v1 = vec![1.0, 0.0, 0.0];
        let v2 = vec![0.0, 1.0, 0.0];
        let v3 = vec![0.0, 0.0, 1.0];
        let embs = vec![&v1, &v2, &v3];
        let h = embedding_entropy(&embs);
        assert!(
            h > 0.0,
            "diverse embeddings should have positive entropy, got {}",
            h
        );
    }

    #[test]
    fn test_embedding_entropy_increases_with_diversity() {
        // Low diversity: very similar vectors
        let v1 = vec![1.0, 0.0];
        let v2 = vec![1.01, 0.0];
        let v3 = vec![0.99, 0.0];
        let low = vec![&v1, &v2, &v3];
        let h_low = embedding_entropy(&low);

        // High diversity: spread out
        let w1 = vec![1.0, 0.0];
        let w2 = vec![0.0, 1.0];
        let w3 = vec![-1.0, 0.0];
        let high = vec![&w1, &w2, &w3];
        let h_high = embedding_entropy(&high);

        assert!(
            h_high > h_low,
            "more diverse embeddings should have higher entropy: {} vs {}",
            h_high,
            h_low
        );
    }

    // -----------------------------------------------------------------------
    // Auto-switch threshold tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_auto_hnsw_threshold() {
        let vi = VectorIndexInner::new(None); // auto mode
        assert!(
            !vi.should_use_hnsw(),
            "empty index should not use HNSW in auto mode"
        );
    }

    #[test]
    fn test_force_hnsw() {
        let vi = VectorIndexInner::new(Some(true));
        assert!(vi.should_use_hnsw(), "forced HNSW should always return true");
    }

    #[test]
    fn test_force_no_hnsw() {
        let mut vi = VectorIndexInner::new(Some(false));
        // Add many vectors
        for i in 0..2000 {
            vi.add_embedding(i, make_vec(8, i as u64));
        }
        assert!(
            !vi.should_use_hnsw(),
            "forced no-HNSW should always return false"
        );
    }

    #[test]
    fn test_auto_switches_above_threshold() {
        let mut vi = VectorIndexInner::new(None);
        for i in 0..=HNSW_AUTO_THRESHOLD as i64 {
            vi.add_embedding(i, make_vec(8, i as u64));
        }
        assert!(
            vi.should_use_hnsw(),
            "auto mode should use HNSW when > {} vectors",
            HNSW_AUTO_THRESHOLD
        );
    }

    // -----------------------------------------------------------------------
    // Integration: HNSW rebuild on dirty
    // -----------------------------------------------------------------------

    #[test]
    fn test_hnsw_rebuild_on_query() {
        let mut vi = VectorIndexInner::new(Some(true));
        let dim = 8;
        for i in 0..50 {
            vi.add_embedding(i, make_vec(dim, i as u64));
        }
        assert!(vi.hnsw_dirty, "should be dirty after adds");

        // Query triggers rebuild
        let results = vi.query_by_embedding(&make_vec(dim, 10), 3);
        assert!(!vi.hnsw_dirty, "should not be dirty after query");
        assert!(!results.is_empty());
        assert_eq!(results[0].0, 10);
    }

    #[test]
    fn test_add_after_query_marks_dirty() {
        let mut vi = VectorIndexInner::new(Some(true));
        let dim = 8;
        for i in 0..10 {
            vi.add_embedding(i, make_vec(dim, i as u64));
        }

        // Trigger rebuild
        let _ = vi.query_by_embedding(&make_vec(dim, 0), 1);
        assert!(!vi.hnsw_dirty);

        // Add new vector — should mark dirty
        vi.add_embedding(100, make_vec(dim, 100));
        assert!(vi.hnsw_dirty);
    }

    // -----------------------------------------------------------------------
    // Large-scale smoke test
    // -----------------------------------------------------------------------

    #[test]
    fn test_hnsw_large_index() {
        let mut hnsw = HnswInner::new(16, 200, 4);
        let dim = 32;
        let n = 500;

        for i in 0..n {
            hnsw.add_vector(i, make_vec(dim, i as u64));
        }
        assert_eq!(hnsw.len(), n as usize);

        // Search should return correct results
        let query = make_vec(dim, 250);
        let results = hnsw.search(&query, 10, 100);
        assert!(!results.is_empty());
        assert_eq!(results[0].0, 250);
        assert!((results[0].1 - 1.0).abs() < 1e-6);

        // Remove some nodes
        for i in 0..50 {
            hnsw.remove(i);
        }
        assert_eq!(hnsw.len(), 450);

        // Search still works
        let results = hnsw.search(&make_vec(dim, 300), 5, 0);
        assert!(!results.is_empty());
        assert_eq!(results[0].0, 300);
    }

    #[test]
    fn test_vector_index_near_duplicates_with_hnsw() {
        let mut vi = VectorIndexInner::new(Some(true));
        let dim = 16;

        // Insert base vectors
        for i in 0..200 {
            vi.add_embedding(i, make_vec(dim, i as u64));
        }

        // Insert a near-duplicate of vector 50
        let base = make_vec(dim, 50);
        let dup = make_similar(&base, 0.5);
        vi.add_embedding(1000, dup);

        // The duplicate should be found
        let dups = vi.find_near_duplicates(0.95);
        let found = dups
            .iter()
            .any(|(a, b, _s)| (*a == 50 && *b == 1000) || (*a == 1000 && *b == 50));
        assert!(
            found,
            "HNSW near-duplicate search should find the duplicate pair (50, 1000). Found: {:?}",
            dups
        );
    }
}
