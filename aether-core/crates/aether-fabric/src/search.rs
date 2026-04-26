//! Multi-shard search across the entire Knowledge Fabric.

use std::path::Path;

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

        // Deduplicate by content (keep highest-scoring copy)
        let mut seen = std::collections::HashSet::new();
        all_results.retain(|r| seen.insert(r.2.clone()));

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

    /// Save all shards to a directory (one file per shard).
    pub fn save_to_dir(&self, dir: &Path) -> Result<usize, String> {
        std::fs::create_dir_all(dir).map_err(|e| format!("mkdir error: {e}"))?;
        let mut total = 0;
        for shard in &self.shards {
            let data = shard.save_to_bytes()?;
            let path = dir.join(format!("shard_{}.bin", shard.domain()));
            std::fs::write(&path, &data).map_err(|e| format!("write error: {e}"))?;
            total += shard.len();
        }
        Ok(total)
    }

    /// Load all shards from a directory.
    pub fn load_from_dir(&self, dir: &Path) -> Result<usize, String> {
        if !dir.exists() {
            return Ok(0);
        }
        let mut total = 0;
        for shard in &self.shards {
            let path = dir.join(format!("shard_{}.bin", shard.domain()));
            if path.exists() {
                let data = std::fs::read(&path).map_err(|e| format!("read error: {e}"))?;
                let count = shard.load_from_bytes(&data)?;
                total += count;
            }
        }
        Ok(total)
    }
}

impl Default for KnowledgeFabric {
    fn default() -> Self {
        Self::new()
    }
}
