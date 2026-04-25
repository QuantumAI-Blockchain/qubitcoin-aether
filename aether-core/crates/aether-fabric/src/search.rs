//! Multi-shard search across the entire Knowledge Fabric.

use crate::shard::FabricShard;

/// The full Knowledge Fabric: 10 shards (one per Sephirot domain).
pub struct KnowledgeFabric {
    shards: Vec<FabricShard>,
}

impl KnowledgeFabric {
    /// Create a new fabric with 10 Sephirot shards.
    pub fn new() -> Self {
        let shards = (0..10).map(|i| FabricShard::new(i as u8)).collect();
        Self { shards }
    }

    /// Search across all shards, merging and ranking results.
    pub fn search_all(&self, query: &[f32], top_k: usize) -> Vec<(u64, f32, String, u8)> {
        let mut all_results: Vec<(u64, f32, String, u8)> = self
            .shards
            .iter()
            .flat_map(|shard| {
                shard
                    .search(query, top_k)
                    .into_iter()
                    .map(|(id, sim, content)| (id, sim, content, shard.domain()))
            })
            .collect();

        all_results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        all_results.truncate(top_k);
        all_results
    }

    /// Search a specific domain shard.
    pub fn search_domain(&self, domain: u8, query: &[f32], top_k: usize) -> Vec<(u64, f32, String)> {
        if let Some(shard) = self.shards.get(domain as usize) {
            shard.search(query, top_k)
        } else {
            Vec::new()
        }
    }

    /// Get a shard by domain index.
    pub fn shard(&self, domain: u8) -> Option<&FabricShard> {
        self.shards.get(domain as usize)
    }

    /// Total vectors across all shards.
    pub fn total_vectors(&self) -> usize {
        self.shards.iter().map(|s| s.len()).sum()
    }
}

impl Default for KnowledgeFabric {
    fn default() -> Self {
        Self::new()
    }
}
