//! HNSW (Hierarchical Navigable Small World) index for Knowledge Fabric.
//!
//! Pure-Rust f32 HNSW implementation optimized for the Knowledge Fabric's
//! 896-dimensional embedding vectors. Parameters: M=16, M0=32, ef_construction=200.
//!
//! Auto-switches between brute-force (<=1000 vectors) and HNSW (>1000) for
//! optimal performance at all scales.

use std::collections::{BTreeMap, HashMap, HashSet};

use ordered_float::OrderedFloat;
use rand::Rng;

// ---------------------------------------------------------------------------
// Cosine helpers (f32)
// ---------------------------------------------------------------------------

/// Cosine similarity in [-1, 1]. Returns 0.0 if either vector has zero norm.
#[inline]
pub fn cosine_similarity_f32(a: &[f32], b: &[f32]) -> f32 {
    const EPSILON: f32 = 1e-10;
    let mut dot = 0.0f32;
    let mut norm_a = 0.0f32;
    let mut norm_b = 0.0f32;
    for (x, y) in a.iter().zip(b.iter()) {
        dot += x * y;
        norm_a += x * x;
        norm_b += y * y;
    }
    if norm_a < EPSILON || norm_b < EPSILON {
        return 0.0;
    }
    (dot / (norm_a.sqrt() * norm_b.sqrt())).clamp(-1.0, 1.0)
}

/// Cosine distance: 1.0 - cosine_similarity. In [0, 2].
#[inline]
fn cosine_distance_f32(a: &[f32], b: &[f32]) -> f32 {
    1.0 - cosine_similarity_f32(a, b)
}

/// Pop the minimum (key, value) from a BTreeMap<OrderedFloat, Vec<u64>>.
fn pop_min(map: &mut BTreeMap<OrderedFloat<f32>, Vec<u64>>) -> Option<(OrderedFloat<f32>, u64)> {
    let first_key = *map.keys().next()?;
    let ids = map.get_mut(&first_key)?;
    let id = ids.pop()?;
    if ids.is_empty() {
        map.remove(&first_key);
    }
    Some((first_key, id))
}

// ---------------------------------------------------------------------------
// HNSW Graph
// ---------------------------------------------------------------------------

/// HNSW index for f32 embeddings with u64 vector IDs.
pub struct HnswGraph {
    m: usize,
    m0: usize,
    ef_construction: usize,
    max_layers: usize,
    ml: f64,

    /// id -> embedding vector
    vectors: HashMap<u64, Vec<f32>>,
    /// id -> highest layer the node appears in
    node_layers: HashMap<u64, usize>,
    /// layer -> (id -> set of connected ids)
    graph: Vec<HashMap<u64, HashSet<u64>>>,
    /// Current entry point
    entry_point: Option<u64>,
    /// Highest occupied layer
    max_level: Option<usize>,
    /// Embedding dimension
    dim: usize,
}

impl HnswGraph {
    /// Create a new HNSW graph with given parameters.
    /// - `max_connections`: M parameter (edges per node per layer, default 16)
    /// - `ef_construction`: beam width during construction (default 200)
    /// - `max_layers`: maximum number of layers (default 6)
    pub fn new(max_connections: usize, ef_construction: usize, max_layers: usize) -> Self {
        let m = max_connections.max(2);
        let ml = 1.0 / (m as f64).ln();
        let mut graph = Vec::with_capacity(max_layers);
        for _ in 0..max_layers {
            graph.push(HashMap::new());
        }
        HnswGraph {
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

    /// Default construction parameters for the Knowledge Fabric.
    pub fn default_fabric() -> Self {
        Self::new(16, 200, 6)
    }

    /// Random level using exponential decay.
    fn random_level(&self) -> usize {
        let mut rng = rand::thread_rng();
        let r: f64 = rng.gen::<f64>().max(1e-12);
        let level = (-r.ln() * self.ml) as usize;
        level.min(self.max_layers - 1)
    }

    /// Greedy beam search on a single layer.
    fn search_layer(
        &self,
        query: &[f32],
        entry_point: u64,
        ef: usize,
        layer: usize,
    ) -> Vec<(OrderedFloat<f32>, u64)> {
        let ep_vec = match self.vectors.get(&entry_point) {
            Some(v) => v,
            None => return Vec::new(),
        };
        let dist = OrderedFloat(cosine_distance_f32(query, ep_vec));
        let mut visited = HashSet::new();
        visited.insert(entry_point);

        let mut candidates: BTreeMap<OrderedFloat<f32>, Vec<u64>> = BTreeMap::new();
        candidates.entry(dist).or_default().push(entry_point);

        let mut results: Vec<(OrderedFloat<f32>, u64)> = vec![(dist, entry_point)];

        let layer_graph = match self.graph.get(layer) {
            Some(g) => g,
            None => return results,
        };

        loop {
            let (c_dist, c_id) = match pop_min(&mut candidates) {
                Some(v) => v,
                None => break,
            };

            if results.len() >= ef {
                results.sort_unstable();
                if c_dist > results[results.len() - 1].0 {
                    break;
                }
            }

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
                    let n_dist = OrderedFloat(cosine_distance_f32(query, n_vec));

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
    pub fn insert(&mut self, id: u64, embedding: Vec<f32>) {
        if embedding.is_empty() {
            return;
        }
        if self.dim == 0 {
            self.dim = embedding.len();
        }

        self.vectors.insert(id, embedding.clone());
        let level = self.random_level();
        self.node_layers.insert(id, level);

        // Ensure graph layers exist
        while self.graph.len() <= level {
            self.graph.push(HashMap::new());
        }

        // First node — entry point
        if self.entry_point.is_none() {
            self.entry_point = Some(id);
            self.max_level = Some(level);
            for lc in 0..=level {
                self.graph[lc].insert(id, HashSet::new());
            }
            return;
        }

        let max_level = self.max_level.unwrap_or(0);

        // Traverse from top layer down to level+1
        let mut current_entry = match self.entry_point {
            Some(ep) => ep,
            None => return,
        };
        for lc in (level + 1..=max_level).rev() {
            if lc < self.graph.len() && self.graph[lc].contains_key(&current_entry) {
                let result = self.search_layer(&embedding, current_entry, 1, lc);
                if let Some((_d, nid)) = result.first() {
                    current_entry = *nid;
                }
            }
        }

        // For layers min(level, max_level) down to 0
        let start_layer = level.min(max_level);
        for lc in (0..=start_layer).rev() {
            let max_conn = if lc == 0 { self.m0 } else { self.m };

            if !self.graph[lc].contains_key(&id) {
                self.graph[lc].insert(id, HashSet::new());
            }

            let candidates = if self.vectors.contains_key(&current_entry) {
                self.search_layer(&embedding, current_entry, self.ef_construction, lc)
            } else {
                Vec::new()
            };

            let neighbors: Vec<(OrderedFloat<f32>, u64)> =
                candidates.iter().take(max_conn).cloned().collect();

            for &(_dist, neighbor_id) in &neighbors {
                if neighbor_id == id {
                    continue;
                }
                self.graph[lc].entry(id).or_default().insert(neighbor_id);
                self.graph[lc]
                    .entry(neighbor_id)
                    .or_default()
                    .insert(id);

                // Prune neighbor if over limit
                let neighbor_conns = self.graph[lc].entry(neighbor_id).or_default();
                if neighbor_conns.len() > max_conn {
                    let n_emb = self.vectors.get(&neighbor_id).cloned();
                    if let Some(ref n_emb) = n_emb {
                        let mut scored: Vec<(OrderedFloat<f32>, u64)> = neighbor_conns
                            .iter()
                            .filter_map(|&conn| {
                                self.vectors
                                    .get(&conn)
                                    .map(|v| (OrderedFloat(cosine_distance_f32(n_emb, v)), conn))
                            })
                            .collect();
                        scored.sort_unstable();
                        scored.truncate(max_conn);
                        let keep: HashSet<u64> = scored.into_iter().map(|(_, nid)| nid).collect();
                        *self.graph[lc].get_mut(&neighbor_id).unwrap() = keep;
                    }
                }
            }

            if let Some(first) = candidates.first() {
                current_entry = first.1;
            }
        }

        if level > max_level {
            self.entry_point = Some(id);
            self.max_level = Some(level);
        }
    }

    /// Search for k approximate nearest neighbors.
    /// Returns vec of (id, cosine_similarity), highest similarity first.
    pub fn search(&self, query: &[f32], k: usize) -> Vec<(u64, f32)> {
        self.search_with_ef(query, k, 0)
    }

    /// Search with explicit ef_search parameter.
    pub fn search_with_ef(&self, query: &[f32], k: usize, ef_search: usize) -> Vec<(u64, f32)> {
        if self.vectors.is_empty() || self.entry_point.is_none() {
            return Vec::new();
        }
        let ef = if ef_search == 0 { k.max(50) } else { ef_search };

        let max_level = self.max_level.unwrap_or(0);
        let mut current_entry = match self.entry_point {
            Some(ep) => ep,
            None => return Vec::new(),
        };

        // Traverse from top to layer 1
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

        candidates
            .iter()
            .take(k)
            .map(|(dist, nid)| (*nid, 1.0 - dist.0))
            .collect()
    }

    /// Remove a vector.
    pub fn remove(&mut self, id: u64) {
        if !self.vectors.contains_key(&id) {
            return;
        }

        let level = self.node_layers.get(&id).copied().unwrap_or(0);

        for lc in 0..=level {
            if lc < self.graph.len() {
                if let Some(neighbors) = self.graph[lc].get(&id).cloned() {
                    for neighbor in &neighbors {
                        if let Some(adj) = self.graph[lc].get_mut(neighbor) {
                            adj.remove(&id);
                        }
                    }
                }
                self.graph[lc].remove(&id);
            }
        }

        self.vectors.remove(&id);
        self.node_layers.remove(&id);

        if self.entry_point == Some(id) {
            if self.vectors.is_empty() {
                self.entry_point = None;
                self.max_level = None;
            } else {
                let mut best_id: Option<u64> = None;
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

    pub fn len(&self) -> usize {
        self.vectors.len()
    }

    pub fn is_empty(&self) -> bool {
        self.vectors.is_empty()
    }

    pub fn contains(&self, id: u64) -> bool {
        self.vectors.contains_key(&id)
    }

    pub fn dim(&self) -> usize {
        self.dim
    }

    /// Get a reference to a stored embedding.
    pub fn get_embedding(&self, id: u64) -> Option<&[f32]> {
        self.vectors.get(&id).map(|v| v.as_slice())
    }
}

// ---------------------------------------------------------------------------
// Hybrid Index: brute-force for small, HNSW for large
// ---------------------------------------------------------------------------

/// Auto-switching index: brute-force below threshold, HNSW above.
pub struct HybridIndex {
    /// Brute-force storage (used when count <= threshold)
    brute_vectors: HashMap<u64, Vec<f32>>,
    /// HNSW graph (activated when count > threshold)
    hnsw: Option<HnswGraph>,
    /// Threshold for switching to HNSW
    threshold: usize,
    /// Next auto-generated ID
    next_id: u64,
}

impl HybridIndex {
    pub fn new(threshold: usize) -> Self {
        Self {
            brute_vectors: HashMap::new(),
            hnsw: None,
            threshold,
            next_id: 0,
        }
    }

    /// Default: switch at 1000 vectors
    pub fn default_fabric() -> Self {
        Self::new(1000)
    }

    /// Insert an embedding with a given ID.
    pub fn insert_with_id(&mut self, id: u64, embedding: Vec<f32>) {
        if self.next_id <= id {
            self.next_id = id + 1;
        }

        if let Some(ref mut hnsw) = self.hnsw {
            hnsw.insert(id, embedding);
        } else {
            self.brute_vectors.insert(id, embedding);
            // Check if we should switch to HNSW
            if self.brute_vectors.len() > self.threshold {
                self.upgrade_to_hnsw();
            }
        }
    }

    /// Insert and auto-assign an ID.
    pub fn insert(&mut self, embedding: Vec<f32>) -> u64 {
        let id = self.next_id;
        self.next_id += 1;
        self.insert_with_id(id, embedding);
        id
    }

    /// Upgrade from brute-force to HNSW.
    fn upgrade_to_hnsw(&mut self) {
        log::info!(
            "HybridIndex: upgrading to HNSW ({} vectors)",
            self.brute_vectors.len()
        );
        let mut hnsw = HnswGraph::default_fabric();
        for (id, emb) in self.brute_vectors.drain() {
            hnsw.insert(id, emb);
        }
        self.hnsw = Some(hnsw);
    }

    /// Search for k nearest neighbors.
    /// Returns (id, similarity) pairs sorted by descending similarity.
    pub fn search(&self, query: &[f32], k: usize) -> Vec<(u64, f32)> {
        if let Some(ref hnsw) = self.hnsw {
            hnsw.search(query, k)
        } else {
            // Brute-force search
            let mut scored: Vec<(u64, f32)> = self
                .brute_vectors
                .iter()
                .map(|(&id, emb)| (id, cosine_similarity_f32(query, emb)))
                .collect();
            scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            scored.truncate(k);
            scored
        }
    }

    pub fn remove(&mut self, id: u64) {
        if let Some(ref mut hnsw) = self.hnsw {
            hnsw.remove(id);
        } else {
            self.brute_vectors.remove(&id);
        }
    }

    pub fn len(&self) -> usize {
        if let Some(ref hnsw) = self.hnsw {
            hnsw.len()
        } else {
            self.brute_vectors.len()
        }
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    pub fn is_hnsw_active(&self) -> bool {
        self.hnsw.is_some()
    }

    pub fn get_embedding(&self, id: u64) -> Option<&[f32]> {
        if let Some(ref hnsw) = self.hnsw {
            hnsw.get_embedding(id)
        } else {
            self.brute_vectors.get(&id).map(|v| v.as_slice())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hnsw_insert_search() {
        let mut hnsw = HnswGraph::new(4, 50, 4);

        // Insert orthogonal vectors
        hnsw.insert(0, vec![1.0, 0.0, 0.0]);
        hnsw.insert(1, vec![0.0, 1.0, 0.0]);
        hnsw.insert(2, vec![0.0, 0.0, 1.0]);
        hnsw.insert(3, vec![0.9, 0.1, 0.0]);
        hnsw.insert(4, vec![0.1, 0.9, 0.0]);

        assert_eq!(hnsw.len(), 5);

        // Search for vec closest to [1,0,0]
        let results = hnsw.search(&[1.0, 0.0, 0.0], 3);
        assert!(!results.is_empty());
        assert_eq!(results[0].0, 0); // exact match
        assert!((results[0].1 - 1.0).abs() < 1e-5);
        // Second should be id=3 (0.9, 0.1, 0)
        assert_eq!(results[1].0, 3);
    }

    #[test]
    fn test_hnsw_remove() {
        let mut hnsw = HnswGraph::new(4, 50, 4);
        hnsw.insert(0, vec![1.0, 0.0]);
        hnsw.insert(1, vec![0.0, 1.0]);
        assert_eq!(hnsw.len(), 2);
        hnsw.remove(0);
        assert_eq!(hnsw.len(), 1);
        assert!(!hnsw.contains(0));
        assert!(hnsw.contains(1));
    }

    #[test]
    fn test_hybrid_brute_force() {
        let mut idx = HybridIndex::new(100);
        let id = idx.insert(vec![1.0, 0.0, 0.0]);
        assert_eq!(id, 0);
        idx.insert(vec![0.0, 1.0, 0.0]);
        idx.insert(vec![0.9, 0.1, 0.0]);
        assert!(!idx.is_hnsw_active());

        let results = idx.search(&[1.0, 0.0, 0.0], 2);
        assert_eq!(results[0].0, 0);
    }

    #[test]
    fn test_hybrid_upgrade() {
        let mut idx = HybridIndex::new(5);
        for i in 0..10 {
            idx.insert(vec![i as f32, (10 - i) as f32]);
        }
        assert!(idx.is_hnsw_active());
        assert_eq!(idx.len(), 10);

        let results = idx.search(&[9.0, 1.0], 1);
        assert_eq!(results[0].0, 9); // Should find the closest vector
    }

    #[test]
    fn test_cosine_similarity() {
        assert!((cosine_similarity_f32(&[1.0, 0.0], &[1.0, 0.0]) - 1.0).abs() < 1e-5);
        assert!((cosine_similarity_f32(&[1.0, 0.0], &[0.0, 1.0]) - 0.0).abs() < 1e-5);
        assert!((cosine_similarity_f32(&[1.0, 0.0], &[-1.0, 0.0]) + 1.0).abs() < 1e-5);
    }
}
