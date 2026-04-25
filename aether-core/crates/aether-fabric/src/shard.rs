//! Fabric shard — a single partition of the knowledge fabric.
//!
//! Phase 0: In-memory Vec<KnowledgeVector> with brute-force search.
//! Phase 1: RocksDB + HNSW.

use parking_lot::RwLock;
use std::sync::atomic::{AtomicU64, Ordering};

use crate::types::{KnowledgeVector, Provenance};

/// A single shard of the knowledge fabric.
pub struct FabricShard {
    domain: u8,
    vectors: RwLock<Vec<KnowledgeVector>>,
    next_id: AtomicU64,
}

impl FabricShard {
    pub fn new(domain: u8) -> Self {
        Self {
            domain,
            vectors: RwLock::new(Vec::new()),
            next_id: AtomicU64::new(0),
        }
    }

    /// Insert a knowledge vector into this shard.
    pub fn insert(&self, embedding: Vec<f32>, content: String, provenance: Provenance, block_height: u64) -> u64 {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let vector = KnowledgeVector {
            id,
            embedding,
            domain: self.domain,
            content,
            provenance,
            block_height,
            confidence: 1.0,
        };
        self.vectors.write().push(vector);
        id
    }

    /// Search for the top-k most similar vectors by cosine similarity.
    pub fn search(&self, query: &[f32], top_k: usize) -> Vec<(u64, f32, String)> {
        let vectors = self.vectors.read();
        let mut scored: Vec<(u64, f32, String)> = vectors
            .iter()
            .map(|v| {
                let sim = cosine_similarity(query, &v.embedding);
                (v.id, sim, v.content.clone())
            })
            .collect();

        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        scored.truncate(top_k);
        scored
    }

    /// Number of vectors in this shard.
    pub fn len(&self) -> usize {
        self.vectors.read().len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    pub fn domain(&self) -> u8 {
        self.domain
    }
}

/// Cosine similarity between two vectors.
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() {
        return 0.0;
    }
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm_a == 0.0 || norm_b == 0.0 {
        return 0.0;
    }
    dot / (norm_a * norm_b)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_insert_and_search() {
        let shard = FabricShard::new(0);

        // Insert some vectors
        shard.insert(vec![1.0, 0.0, 0.0], "vec_a".into(), Provenance::Genesis, 0);
        shard.insert(vec![0.0, 1.0, 0.0], "vec_b".into(), Provenance::Genesis, 0);
        shard.insert(vec![0.9, 0.1, 0.0], "vec_c".into(), Provenance::Genesis, 0);

        assert_eq!(shard.len(), 3);

        // Search: query closest to vec_a
        let results = shard.search(&[1.0, 0.0, 0.0], 2);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].2, "vec_a"); // exact match first
        assert_eq!(results[1].2, "vec_c"); // close second
    }

    #[test]
    fn test_cosine_similarity() {
        assert!((cosine_similarity(&[1.0, 0.0], &[1.0, 0.0]) - 1.0).abs() < 1e-6);
        assert!((cosine_similarity(&[1.0, 0.0], &[0.0, 1.0]) - 0.0).abs() < 1e-6);
        assert!((cosine_similarity(&[1.0, 0.0], &[-1.0, 0.0]) - (-1.0)).abs() < 1e-6);
    }
}
