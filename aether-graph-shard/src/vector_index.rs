//! HNSW-inspired vector index for semantic similarity search.
//!
//! Each shard maintains its own vector index for embeddings.
//! Architecture: flat brute-force for <100K vectors, HNSW layers for >100K.
//!
//! Memory layout: all vectors are stored in a contiguous f32 buffer
//! for cache-friendly SIMD-accelerated distance computation.

use ordered_float::OrderedFloat;
use parking_lot::RwLock;
use rand::Rng;
use std::collections::{BinaryHeap, HashMap};

/// Configuration for the vector index.
#[derive(Debug, Clone)]
pub struct VectorIndexConfig {
    /// Embedding dimensionality (e.g. 384 for MiniLM, 768 for BERT)
    pub dim: usize,
    /// Max connections per node in HNSW graph (M parameter)
    pub max_connections: usize,
    /// Size of dynamic candidate list during construction (ef_construction)
    pub ef_construction: usize,
    /// Size of dynamic candidate list during search (ef_search)
    pub ef_search: usize,
    /// Threshold to switch from flat to HNSW (node count)
    pub hnsw_threshold: usize,
}

impl Default for VectorIndexConfig {
    fn default() -> Self {
        Self {
            dim: 384, // MiniLM default
            max_connections: 16,
            ef_construction: 200,
            ef_search: 64,
            hnsw_threshold: 10_000,
        }
    }
}

/// A scored search result.
#[derive(Debug, Clone)]
pub struct VectorResult {
    pub node_id: i64,
    pub distance: f32,
}

/// HNSW-inspired vector index with flat fallback.
pub struct ShardVectorIndex {
    config: VectorIndexConfig,
    /// node_id -> position in the vector buffer
    id_to_pos: RwLock<HashMap<i64, usize>>,
    /// position -> node_id
    pos_to_id: RwLock<Vec<i64>>,
    /// Flat contiguous buffer: [dim * num_vectors] f32 values
    vectors: RwLock<Vec<f32>>,
    /// HNSW graph layers: layer -> (node_pos -> neighbors at that layer)
    /// Layer 0 is the base (most connections), higher layers are sparser
    hnsw_layers: RwLock<Vec<Vec<Vec<usize>>>>,
    /// Entry point for HNSW search (highest layer node)
    entry_point: RwLock<Option<usize>>,
    /// Max level in the HNSW graph
    max_level: RwLock<usize>,
}

impl ShardVectorIndex {
    pub fn new(config: VectorIndexConfig) -> Self {
        Self {
            config,
            id_to_pos: RwLock::new(HashMap::new()),
            pos_to_id: RwLock::new(Vec::new()),
            vectors: RwLock::new(Vec::new()),
            hnsw_layers: RwLock::new(Vec::new()),
            entry_point: RwLock::new(None),
            max_level: RwLock::new(0),
        }
    }

    /// Number of indexed vectors.
    pub fn len(&self) -> usize {
        self.pos_to_id.read().len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Insert or update a vector for a node_id.
    pub fn upsert(&self, node_id: i64, embedding: &[f32]) {
        if embedding.len() != self.config.dim {
            return; // Dimension mismatch — skip silently
        }

        let mut id_map = self.id_to_pos.write();
        let mut pos_map = self.pos_to_id.write();
        let mut vecs = self.vectors.write();

        if let Some(&pos) = id_map.get(&node_id) {
            // Update existing vector in-place
            let start = pos * self.config.dim;
            vecs[start..start + self.config.dim].copy_from_slice(embedding);
        } else {
            // Append new vector
            let pos = pos_map.len();
            id_map.insert(node_id, pos);
            pos_map.push(node_id);
            vecs.extend_from_slice(embedding);

            // Add to HNSW if above threshold
            drop(vecs);
            drop(pos_map);
            drop(id_map);
            if self.pos_to_id.read().len() >= self.config.hnsw_threshold {
                self.hnsw_insert(pos, embedding);
            }
        }
    }

    /// Remove a vector by node_id.
    pub fn remove(&self, node_id: i64) {
        let mut id_map = self.id_to_pos.write();
        if let Some(pos) = id_map.remove(&node_id) {
            // Mark as removed by zeroing the vector (lazy deletion)
            let mut vecs = self.vectors.write();
            let start = pos * self.config.dim;
            if start + self.config.dim <= vecs.len() {
                for v in &mut vecs[start..start + self.config.dim] {
                    *v = f32::NAN;
                }
            }
            // Don't compact — positions are stable references in HNSW graph
        }
    }

    /// Search for the top-k nearest neighbors to a query vector.
    pub fn search(&self, query: &[f32], top_k: usize) -> Vec<VectorResult> {
        if query.len() != self.config.dim || self.is_empty() {
            return Vec::new();
        }

        let count = self.len();

        if count < self.config.hnsw_threshold {
            // Flat brute-force search (fast for <10K vectors)
            self.flat_search(query, top_k)
        } else {
            // HNSW search
            let hnsw_results = self.hnsw_search(query, top_k);
            if hnsw_results.is_empty() {
                // Fallback to flat if HNSW not built yet
                self.flat_search(query, top_k)
            } else {
                hnsw_results
            }
        }
    }

    /// Brute-force search across all vectors.
    fn flat_search(&self, query: &[f32], top_k: usize) -> Vec<VectorResult> {
        let vecs = self.vectors.read();
        let pos_map = self.pos_to_id.read();
        let dim = self.config.dim;

        // Min-heap of (negative_distance, pos) — we keep top_k largest (closest)
        let mut heap: BinaryHeap<(OrderedFloat<f32>, usize)> = BinaryHeap::new();

        for pos in 0..pos_map.len() {
            let start = pos * dim;
            if start + dim > vecs.len() {
                break;
            }
            let vec_slice = &vecs[start..start + dim];

            // Skip removed vectors (NaN marker)
            if vec_slice[0].is_nan() {
                continue;
            }

            let dist = cosine_distance(query, vec_slice);

            if heap.len() < top_k {
                heap.push((OrderedFloat(dist), pos));
            } else if let Some(&(OrderedFloat(worst), _)) = heap.peek() {
                if dist < worst {
                    heap.pop();
                    heap.push((OrderedFloat(dist), pos));
                }
            }
        }

        // Convert to results (sorted by distance ascending)
        let mut results: Vec<VectorResult> = heap
            .into_iter()
            .map(|(OrderedFloat(dist), pos)| VectorResult {
                node_id: pos_map[pos],
                distance: dist,
            })
            .collect();
        results.sort_by(|a, b| a.distance.partial_cmp(&b.distance).unwrap_or(std::cmp::Ordering::Equal));
        results
    }

    // ── HNSW Implementation ─────────────────────────────────────────

    /// Determine the random level for a new node (exponential distribution).
    fn random_level(&self) -> usize {
        let mut rng = rand::rng();
        let ml = 1.0 / (self.config.max_connections as f64).ln();
        let mut level = (-rng.random::<f64>().ln() * ml) as usize;
        // Cap at reasonable max
        level = level.min(16);
        level
    }

    /// Insert a node into the HNSW graph.
    fn hnsw_insert(&self, pos: usize, embedding: &[f32]) {
        let level = self.random_level();

        let mut layers = self.hnsw_layers.write();
        let mut entry = self.entry_point.write();
        let mut max_lvl = self.max_level.write();

        // Ensure layers exist
        while layers.len() <= level {
            layers.push(Vec::new());
        }
        // Ensure node slots exist in each layer up to this level
        for l in 0..=level {
            while layers[l].len() <= pos {
                layers[l].push(Vec::new());
            }
        }

        if entry.is_none() {
            // First node
            *entry = Some(pos);
            *max_lvl = level;
            return;
        }

        let ep = entry.unwrap();
        let vecs = self.vectors.read();
        let dim = self.config.dim;

        // Greedy descent from top layer to level+1
        let mut current = ep;
        for l in (level + 1..=*max_lvl).rev() {
            if l >= layers.len() {
                continue;
            }
            loop {
                let mut changed = false;
                if current < layers[l].len() {
                    for &neighbor in &layers[l][current] {
                        let n_start = neighbor * dim;
                        let c_start = current * dim;
                        if n_start + dim <= vecs.len() && c_start + dim <= vecs.len() {
                            let d_neighbor = cosine_distance(embedding, &vecs[n_start..n_start + dim]);
                            let d_current = cosine_distance(embedding, &vecs[c_start..c_start + dim]);
                            if d_neighbor < d_current {
                                current = neighbor;
                                changed = true;
                            }
                        }
                    }
                }
                if !changed {
                    break;
                }
            }
        }

        // Insert at each layer from min(level, max_level) down to 0
        let max_conn = self.config.max_connections;
        for l in (0..=level.min(*max_lvl)).rev() {
            if l >= layers.len() {
                continue;
            }

            // Find ef_construction nearest neighbors at this layer
            let neighbors = self.search_layer(&vecs, embedding, current, self.config.ef_construction, l, &layers);

            // Select top max_connections
            let selected: Vec<usize> = neighbors
                .iter()
                .take(max_conn)
                .map(|&(_, p)| p)
                .collect();

            // Ensure slot exists
            while layers[l].len() <= pos {
                layers[l].push(Vec::new());
            }

            // Connect new node to selected neighbors
            layers[l][pos] = selected.clone();

            // Add reverse connections (bidirectional)
            for &n in &selected {
                if n < layers[l].len() {
                    if layers[l][n].len() < max_conn * 2 {
                        layers[l][n].push(pos);
                    } else {
                        // Prune: keep only the closest max_conn neighbors
                        let n_start = n * dim;
                        if n_start + dim <= vecs.len() {
                            let n_vec = &vecs[n_start..n_start + dim];
                            layers[l][n].push(pos);
                            layers[l][n].sort_by(|&a, &b| {
                                let a_start = a * dim;
                                let b_start = b * dim;
                                let da = if a_start + dim <= vecs.len() {
                                    cosine_distance(n_vec, &vecs[a_start..a_start + dim])
                                } else {
                                    f32::MAX
                                };
                                let db = if b_start + dim <= vecs.len() {
                                    cosine_distance(n_vec, &vecs[b_start..b_start + dim])
                                } else {
                                    f32::MAX
                                };
                                da.partial_cmp(&db).unwrap_or(std::cmp::Ordering::Equal)
                            });
                            layers[l][n].truncate(max_conn * 2);
                        }
                    }
                }
            }

            // Update entry point to first neighbor for next layer
            if !selected.is_empty() {
                current = selected[0];
            }
        }

        // Update global entry point if new node is at higher level
        if level > *max_lvl {
            *entry = Some(pos);
            *max_lvl = level;
        }
    }

    /// Search a single HNSW layer for nearest neighbors.
    fn search_layer(
        &self,
        vecs: &[f32],
        query: &[f32],
        entry: usize,
        ef: usize,
        layer: usize,
        layers: &[Vec<Vec<usize>>],
    ) -> Vec<(OrderedFloat<f32>, usize)> {
        let dim = self.config.dim;

        let entry_start = entry * dim;
        let entry_dist = if entry_start + dim <= vecs.len() {
            cosine_distance(query, &vecs[entry_start..entry_start + dim])
        } else {
            return Vec::new();
        };

        // candidates: min-heap (closest first)
        let mut candidates: BinaryHeap<std::cmp::Reverse<(OrderedFloat<f32>, usize)>> = BinaryHeap::new();
        // results: max-heap (farthest first for pruning)
        let mut results: BinaryHeap<(OrderedFloat<f32>, usize)> = BinaryHeap::new();
        let mut visited = std::collections::HashSet::new();

        candidates.push(std::cmp::Reverse((OrderedFloat(entry_dist), entry)));
        results.push((OrderedFloat(entry_dist), entry));
        visited.insert(entry);

        while let Some(std::cmp::Reverse((OrderedFloat(c_dist), c_pos))) = candidates.pop() {
            // If closest candidate is farther than farthest result, stop
            if let Some(&(OrderedFloat(f_dist), _)) = results.peek() {
                if c_dist > f_dist && results.len() >= ef {
                    break;
                }
            }

            // Explore neighbors
            if layer < layers.len() && c_pos < layers[layer].len() {
                for &neighbor in &layers[layer][c_pos] {
                    if visited.contains(&neighbor) {
                        continue;
                    }
                    visited.insert(neighbor);

                    let n_start = neighbor * dim;
                    if n_start + dim > vecs.len() {
                        continue;
                    }
                    let n_vec = &vecs[n_start..n_start + dim];
                    if n_vec[0].is_nan() {
                        continue; // Deleted vector
                    }

                    let n_dist = cosine_distance(query, n_vec);

                    if results.len() < ef {
                        candidates.push(std::cmp::Reverse((OrderedFloat(n_dist), neighbor)));
                        results.push((OrderedFloat(n_dist), neighbor));
                    } else if let Some(&(OrderedFloat(f_dist), _)) = results.peek() {
                        if n_dist < f_dist {
                            candidates.push(std::cmp::Reverse((OrderedFloat(n_dist), neighbor)));
                            results.push((OrderedFloat(n_dist), neighbor));
                            results.pop(); // Remove farthest
                        }
                    }
                }
            }
        }

        // Return sorted by distance
        let mut res: Vec<_> = results.into_iter().collect();
        res.sort_by(|a, b| a.0.cmp(&b.0));
        res
    }

    /// HNSW search from the entry point.
    fn hnsw_search(&self, query: &[f32], top_k: usize) -> Vec<VectorResult> {
        let layers = self.hnsw_layers.read();
        let entry = self.entry_point.read();
        let max_lvl = *self.max_level.read();
        let vecs = self.vectors.read();
        let pos_map = self.pos_to_id.read();
        let dim = self.config.dim;

        let ep = match *entry {
            Some(ep) => ep,
            None => return Vec::new(),
        };

        // Greedy descent from top layer to layer 1
        let mut current = ep;
        for l in (1..=max_lvl).rev() {
            if l >= layers.len() {
                continue;
            }
            loop {
                let mut changed = false;
                if current < layers[l].len() {
                    for &neighbor in &layers[l][current] {
                        let n_start = neighbor * dim;
                        let c_start = current * dim;
                        if n_start + dim <= vecs.len() && c_start + dim <= vecs.len() {
                            if !vecs[n_start].is_nan() {
                                let d_n = cosine_distance(query, &vecs[n_start..n_start + dim]);
                                let d_c = cosine_distance(query, &vecs[c_start..c_start + dim]);
                                if d_n < d_c {
                                    current = neighbor;
                                    changed = true;
                                }
                            }
                        }
                    }
                }
                if !changed {
                    break;
                }
            }
        }

        // Search layer 0 with ef_search
        let results = self.search_layer(&vecs, query, current, self.config.ef_search, 0, &layers);

        results
            .into_iter()
            .take(top_k)
            .map(|(OrderedFloat(dist), pos)| VectorResult {
                node_id: if pos < pos_map.len() { pos_map[pos] } else { -1 },
                distance: dist,
            })
            .filter(|r| r.node_id >= 0)
            .collect()
    }

    /// Rebuild the HNSW index from all stored vectors.
    /// Call this after bulk loading.
    pub fn rebuild_hnsw(&self) {
        let count = self.len();
        if count < self.config.hnsw_threshold {
            return;
        }

        // Clear existing HNSW
        {
            let mut layers = self.hnsw_layers.write();
            layers.clear();
            *self.entry_point.write() = None;
            *self.max_level.write() = 0;
        }

        let dim = self.config.dim;

        // Copy vectors out to avoid borrow conflicts with hnsw_insert
        let embeddings: Vec<Vec<f32>> = {
            let vecs = self.vectors.read();
            (0..count)
                .filter_map(|pos| {
                    let start = pos * dim;
                    if start + dim <= vecs.len() && !vecs[start].is_nan() {
                        Some(vecs[start..start + dim].to_vec())
                    } else {
                        None
                    }
                })
                .collect()
        };

        for (pos, emb) in embeddings.iter().enumerate() {
            self.hnsw_insert(pos, emb);
        }
    }
}

/// Cosine distance: 1 - cosine_similarity.
/// Returns 0.0 for identical vectors, 2.0 for opposite.
#[inline]
fn cosine_distance(a: &[f32], b: &[f32]) -> f32 {
    debug_assert_eq!(a.len(), b.len());
    let mut dot = 0.0f32;
    let mut norm_a = 0.0f32;
    let mut norm_b = 0.0f32;

    // Process 4 elements at a time for better auto-vectorization
    let chunks = a.len() / 4;
    let remainder = a.len() % 4;

    for i in 0..chunks {
        let base = i * 4;
        dot += a[base] * b[base]
            + a[base + 1] * b[base + 1]
            + a[base + 2] * b[base + 2]
            + a[base + 3] * b[base + 3];
        norm_a += a[base] * a[base]
            + a[base + 1] * a[base + 1]
            + a[base + 2] * a[base + 2]
            + a[base + 3] * a[base + 3];
        norm_b += b[base] * b[base]
            + b[base + 1] * b[base + 1]
            + b[base + 2] * b[base + 2]
            + b[base + 3] * b[base + 3];
    }

    let base = chunks * 4;
    for i in 0..remainder {
        dot += a[base + i] * b[base + i];
        norm_a += a[base + i] * a[base + i];
        norm_b += b[base + i] * b[base + i];
    }

    let denom = (norm_a * norm_b).sqrt();
    if denom < 1e-10 {
        return 1.0; // Zero vectors → max distance
    }

    1.0 - (dot / denom)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cosine_distance_identical() {
        let a = vec![1.0, 2.0, 3.0];
        let b = vec![1.0, 2.0, 3.0];
        assert!((cosine_distance(&a, &b)).abs() < 1e-5);
    }

    #[test]
    fn test_cosine_distance_orthogonal() {
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![0.0, 1.0, 0.0];
        assert!((cosine_distance(&a, &b) - 1.0).abs() < 1e-5);
    }

    #[test]
    fn test_cosine_distance_opposite() {
        let a = vec![1.0, 0.0];
        let b = vec![-1.0, 0.0];
        assert!((cosine_distance(&a, &b) - 2.0).abs() < 1e-5);
    }

    #[test]
    fn test_flat_search() {
        let config = VectorIndexConfig {
            dim: 3,
            hnsw_threshold: 1_000_000, // Force flat search
            ..Default::default()
        };
        let idx = ShardVectorIndex::new(config);

        idx.upsert(1, &[1.0, 0.0, 0.0]);
        idx.upsert(2, &[0.0, 1.0, 0.0]);
        idx.upsert(3, &[0.9, 0.1, 0.0]); // Close to node 1
        idx.upsert(4, &[0.0, 0.0, 1.0]);

        let results = idx.search(&[1.0, 0.0, 0.0], 2);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].node_id, 1); // Exact match
        assert_eq!(results[1].node_id, 3); // Closest
    }

    #[test]
    fn test_remove_and_search() {
        let config = VectorIndexConfig {
            dim: 3,
            hnsw_threshold: 1_000_000,
            ..Default::default()
        };
        let idx = ShardVectorIndex::new(config);

        idx.upsert(1, &[1.0, 0.0, 0.0]);
        idx.upsert(2, &[0.9, 0.1, 0.0]);
        idx.remove(1);

        let results = idx.search(&[1.0, 0.0, 0.0], 2);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].node_id, 2);
    }

    #[test]
    fn test_update_vector() {
        let config = VectorIndexConfig {
            dim: 3,
            hnsw_threshold: 1_000_000,
            ..Default::default()
        };
        let idx = ShardVectorIndex::new(config);

        idx.upsert(1, &[1.0, 0.0, 0.0]);
        idx.upsert(1, &[0.0, 1.0, 0.0]); // Update

        let results = idx.search(&[0.0, 1.0, 0.0], 1);
        assert_eq!(results[0].node_id, 1);
        assert!(results[0].distance < 0.01);
    }
}
