//! Fabric shard — a single partition of the knowledge fabric.
//!
//! Uses HybridIndex (brute-force for <=1000 vectors, HNSW for >1000)
//! for O(log n) approximate nearest neighbor search at scale.

use parking_lot::RwLock;
use std::sync::atomic::{AtomicU64, Ordering};

use crate::hnsw::HybridIndex;
use crate::types::{KnowledgeVector, Provenance};

/// A single shard of the knowledge fabric (one per Sephirot domain).
pub struct FabricShard {
    domain: u8,
    /// HNSW-backed vector index for fast ANN search
    index: RwLock<HybridIndex>,
    /// Metadata storage (content, provenance, etc.) keyed by vector ID
    metadata: RwLock<Vec<KnowledgeVector>>,
    next_id: AtomicU64,
}

impl FabricShard {
    pub fn new(domain: u8) -> Self {
        Self {
            domain,
            index: RwLock::new(HybridIndex::default_fabric()),
            metadata: RwLock::new(Vec::new()),
            next_id: AtomicU64::new(0),
        }
    }

    /// Insert a knowledge vector into this shard.
    pub fn insert(
        &self,
        embedding: Vec<f32>,
        content: String,
        provenance: Provenance,
        block_height: u64,
    ) -> u64 {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let vector = KnowledgeVector {
            id,
            embedding: embedding.clone(),
            domain: self.domain,
            content,
            provenance,
            block_height,
            confidence: 1.0,
        };

        // Insert into HNSW index
        self.index.write().insert_with_id(id, embedding);
        // Store metadata
        self.metadata.write().push(vector);

        id
    }

    /// Search for the top-k most similar vectors by cosine similarity.
    /// Uses HNSW for O(log n) search when >1000 vectors.
    pub fn search(&self, query: &[f32], top_k: usize) -> Vec<(u64, f32, String)> {
        let index = self.index.read();
        let results = index.search(query, top_k);

        let metadata = self.metadata.read();
        results
            .iter()
            .filter_map(|&(id, sim)| {
                // Find metadata by ID (binary search would be faster but metadata
                // is append-only and IDs are sequential within a shard)
                metadata
                    .iter()
                    .find(|v| v.id == id)
                    .map(|v| (id, sim, v.content.clone()))
            })
            .collect()
    }

    /// Search returning full KnowledgeVector results.
    pub fn search_vectors(&self, query: &[f32], top_k: usize) -> Vec<(f32, KnowledgeVector)> {
        let index = self.index.read();
        let results = index.search(query, top_k);

        let metadata = self.metadata.read();
        results
            .iter()
            .filter_map(|&(id, sim)| {
                metadata
                    .iter()
                    .find(|v| v.id == id)
                    .map(|v| (sim, v.clone()))
            })
            .collect()
    }

    /// Number of vectors in this shard.
    pub fn len(&self) -> usize {
        self.index.read().len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    pub fn domain(&self) -> u8 {
        self.domain
    }

    /// Whether HNSW is active (vs brute-force for small shards).
    pub fn is_hnsw_active(&self) -> bool {
        self.index.read().is_hnsw_active()
    }

    /// Serialize all vectors to bytes (bincode).
    pub fn save_to_bytes(&self) -> Result<Vec<u8>, String> {
        let metadata = self.metadata.read();
        bincode::serialize(&*metadata).map_err(|e| format!("Serialize error: {e}"))
    }

    /// Load vectors from bytes, replacing current contents.
    /// Rebuilds the HNSW index from the loaded vectors.
    pub fn load_from_bytes(&self, data: &[u8]) -> Result<usize, String> {
        let loaded: Vec<KnowledgeVector> =
            bincode::deserialize(data).map_err(|e| format!("Deserialize error: {e}"))?;
        let count = loaded.len();

        // Rebuild HNSW index
        let mut index = HybridIndex::default_fabric();
        let max_id = loaded.iter().map(|v| v.id).max().unwrap_or(0);
        for v in &loaded {
            index.insert_with_id(v.id, v.embedding.clone());
        }
        self.next_id.store(max_id + 1, Ordering::Relaxed);

        *self.index.write() = index;
        *self.metadata.write() = loaded;

        log::info!(
            "Shard {} loaded {} vectors (HNSW: {})",
            self.domain,
            count,
            self.is_hnsw_active()
        );

        Ok(count)
    }

    /// Remove a vector by ID.
    pub fn remove(&self, id: u64) -> bool {
        let mut index = self.index.write();
        let mut metadata = self.metadata.write();

        index.remove(id);
        let before = metadata.len();
        metadata.retain(|v| v.id != id);
        metadata.len() < before
    }

    /// Get all metadata (for bulk operations).
    pub fn all_vectors(&self) -> Vec<KnowledgeVector> {
        self.metadata.read().clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_insert_and_search() {
        let shard = FabricShard::new(0);

        shard.insert(vec![1.0, 0.0, 0.0], "vec_a".into(), Provenance::Genesis, 0);
        shard.insert(vec![0.0, 1.0, 0.0], "vec_b".into(), Provenance::Genesis, 0);
        shard.insert(
            vec![0.9, 0.1, 0.0],
            "vec_c".into(),
            Provenance::Genesis,
            0,
        );

        assert_eq!(shard.len(), 3);

        let results = shard.search(&[1.0, 0.0, 0.0], 2);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].2, "vec_a");
        assert_eq!(results[1].2, "vec_c");
    }

    #[test]
    fn test_save_load() {
        let shard = FabricShard::new(3);
        shard.insert(vec![1.0, 0.0], "alpha".into(), Provenance::Genesis, 0);
        shard.insert(vec![0.0, 1.0], "beta".into(), Provenance::Genesis, 1);

        let data = shard.save_to_bytes().unwrap();

        let shard2 = FabricShard::new(3);
        let count = shard2.load_from_bytes(&data).unwrap();
        assert_eq!(count, 2);
        assert_eq!(shard2.len(), 2);

        let results = shard2.search(&[1.0, 0.0], 1);
        assert_eq!(results[0].2, "alpha");
    }

    #[test]
    fn test_remove() {
        let shard = FabricShard::new(0);
        let id = shard.insert(vec![1.0, 0.0], "test".into(), Provenance::Genesis, 0);
        assert_eq!(shard.len(), 1);
        assert!(shard.remove(id));
        assert_eq!(shard.len(), 0);
    }
}
