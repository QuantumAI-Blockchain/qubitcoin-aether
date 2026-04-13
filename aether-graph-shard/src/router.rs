//! Shard router: maps domains to shards and routes operations.
//!
//! Domain-based sharding with sub-sharding by node_id hash:
//!   shard_id = domain_base_id * SUB_SHARDS + (node_id_hash % SUB_SHARDS)
//!
//! This gives 12 domains × 256 sub-shards = 3072 total shards.
//! Each shard holds ~325M nodes at 1T total scale.

use crate::merkle::GlobalMerkle;
use crate::storage::ShardStore;
use crate::types::{Domain, GlobalStats, ShardConfig, ShardEdge, ShardNode, ShardStats};
use anyhow::{Context, Result};
use dashmap::DashMap;
use parking_lot::RwLock;
use std::collections::BTreeMap;
use std::sync::Arc;
use tracing::{info, warn};

/// Number of sub-shards per domain. Start with 1 (simple), scale to 256.
const DEFAULT_SUB_SHARDS: u32 = 1;
/// Maximum sub-shards per domain (for horizontal scaling).
const MAX_SUB_SHARDS: u32 = 256;

/// The shard router manages all shards and routes operations to the correct one.
pub struct ShardRouter {
    /// All active shards: shard_id -> ShardStore
    shards: DashMap<u32, Arc<ShardStore>>,
    /// Global Merkle tree (composed from shard Merkle roots)
    global_merkle: RwLock<GlobalMerkle>,
    /// Sub-shards per domain
    sub_shards: u32,
    /// Base data directory
    data_dir: String,
    /// LRU cache capacity per shard
    cache_per_shard: usize,
}

impl ShardRouter {
    /// Create a new router with the given base directory.
    pub fn new(data_dir: &str, cache_per_shard: usize) -> Self {
        Self {
            shards: DashMap::new(),
            global_merkle: RwLock::new(GlobalMerkle::new()),
            sub_shards: DEFAULT_SUB_SHARDS,
            data_dir: data_dir.to_string(),
            cache_per_shard,
        }
    }

    /// Initialize all domain shards. Call at startup.
    pub fn init_shards(&self) -> Result<()> {
        for domain in Domain::all() {
            for sub in 0..self.sub_shards {
                let shard_id = self.compute_shard_id(*domain, sub);
                let config = ShardConfig {
                    shard_id,
                    domain: *domain,
                    sub_shard: sub,
                    data_dir: format!(
                        "{}/shard_{}_{}_{}",
                        self.data_dir,
                        domain.as_str(),
                        shard_id,
                        sub
                    ),
                    cache_capacity: self.cache_per_shard,
                    compaction_threshold: 0.1,
                };

                let store = ShardStore::open(config)?;
                self.shards.insert(shard_id, Arc::new(store));
            }
        }

        info!(
            total_shards = self.shards.len(),
            sub_shards = self.sub_shards,
            "All shards initialized"
        );

        Ok(())
    }

    /// Compute shard_id from domain and sub-shard index.
    fn compute_shard_id(&self, domain: Domain, sub_shard: u32) -> u32 {
        domain.shard_base_id() * MAX_SUB_SHARDS + sub_shard
    }

    /// Route a node to its shard based on domain and node_id.
    pub fn route(&self, domain: &str, node_id: i64) -> u32 {
        let d = Domain::from_str(domain);
        let sub = if self.sub_shards > 1 {
            (node_id.unsigned_abs() % self.sub_shards as u64) as u32
        } else {
            0
        };
        self.compute_shard_id(d, sub)
    }

    /// Get the shard for a domain.
    pub fn get_shard(&self, shard_id: u32) -> Option<Arc<ShardStore>> {
        self.shards.get(&shard_id).map(|s| s.value().clone())
    }

    /// Get the shard for a node (by domain + id).
    pub fn shard_for_node(&self, domain: &str, node_id: i64) -> Option<Arc<ShardStore>> {
        let id = self.route(domain, node_id);
        self.get_shard(id)
    }

    /// Route a node to its shard, trying all shards if domain unknown.
    pub fn find_node(&self, node_id: i64) -> Result<Option<(ShardNode, u32)>> {
        for entry in self.shards.iter() {
            let shard = entry.value();
            if let Some(node) = shard.get_node(node_id)? {
                return Ok(Some((node, shard.shard_id())));
            }
        }
        Ok(None)
    }

    // ── Node Operations ────────────────────────────────────────────

    /// Put a node into the correct shard.
    pub fn put_node(&self, node: &ShardNode) -> Result<u32> {
        let shard_id = self.route(&node.domain, node.node_id);
        let shard = self
            .get_shard(shard_id)
            .context(format!("shard {} not found", shard_id))?;
        shard.put_node(node)?;
        Ok(shard_id)
    }

    /// Get a node from the correct shard (domain must be known).
    pub fn get_node(&self, domain: &str, node_id: i64) -> Result<Option<ShardNode>> {
        let shard_id = self.route(domain, node_id);
        if let Some(shard) = self.get_shard(shard_id) {
            shard.get_node(node_id)
        } else {
            Ok(None)
        }
    }

    /// Get a node from any shard (domain unknown — scans all shards).
    pub fn get_node_any(&self, node_id: i64) -> Result<Option<ShardNode>> {
        self.find_node(node_id).map(|opt| opt.map(|(n, _)| n))
    }

    /// Delete a node.
    pub fn delete_node(&self, domain: &str, node_id: i64, cascade: bool) -> Result<(bool, i32)> {
        let shard_id = self.route(domain, node_id);
        if let Some(shard) = self.get_shard(shard_id) {
            shard.delete_node(node_id, cascade)
        } else {
            Ok((false, 0))
        }
    }

    // ── Edge Operations ────────────────────────────────────────────

    /// Put an edge. Routes to the source node's shard.
    pub fn put_edge(&self, edge: &ShardEdge, source_domain: &str) -> Result<bool> {
        let shard_id = self.route(source_domain, edge.from_node_id);
        let shard = self
            .get_shard(shard_id)
            .context(format!("shard {} not found", shard_id))?;
        shard.put_edge(edge)
    }

    // ── Search ─────────────────────────────────────────────────────

    /// Search within a single domain shard.
    pub fn search_domain(
        &self,
        domain: &str,
        query: &str,
        top_k: usize,
        min_confidence: f64,
    ) -> Result<Vec<(ShardNode, f64)>> {
        let d = Domain::from_str(domain);
        let mut all_results = Vec::new();

        for sub in 0..self.sub_shards {
            let shard_id = self.compute_shard_id(d, sub);
            if let Some(shard) = self.get_shard(shard_id) {
                let results = shard.search(query, top_k, min_confidence, None)?;
                all_results.extend(results);
            }
        }

        all_results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        all_results.truncate(top_k);
        Ok(all_results)
    }

    /// Cross-domain scatter-gather search.
    pub fn search_cross_domain(
        &self,
        domains: &[String],
        query: &str,
        top_k_per_domain: usize,
        min_confidence: f64,
    ) -> Result<BTreeMap<String, Vec<(ShardNode, f64)>>> {
        let mut results = BTreeMap::new();

        for domain in domains {
            let domain_results = self.search_domain(domain, query, top_k_per_domain, min_confidence)?;
            results.insert(domain.clone(), domain_results);
        }

        Ok(results)
    }

    /// Search all shards (expensive but complete).
    pub fn search_all(
        &self,
        query: &str,
        top_k: usize,
        min_confidence: f64,
    ) -> Result<Vec<(ShardNode, f64)>> {
        let mut all_results = Vec::new();

        for entry in self.shards.iter() {
            let shard = entry.value();
            let results = shard.search(query, top_k, min_confidence, None)?;
            all_results.extend(results);
        }

        all_results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        all_results.truncate(top_k);
        Ok(all_results)
    }

    // ── Vector Search ────────────────────────────────────────────────

    /// Semantic vector search across specified domains (or all).
    pub fn vector_search(
        &self,
        query_embedding: &[f32],
        top_k: usize,
        domain_filter: &str,
        min_confidence: f64,
    ) -> Result<Vec<(ShardNode, f32)>> {
        let mut all_results = Vec::new();

        if domain_filter.is_empty() {
            // Search all shards
            for entry in self.shards.iter() {
                let shard = entry.value();
                let results = shard.vector_search(query_embedding, top_k, min_confidence)?;
                all_results.extend(results);
            }
        } else {
            let d = Domain::from_str(domain_filter);
            for sub in 0..self.sub_shards {
                let shard_id = self.compute_shard_id(d, sub);
                if let Some(shard) = self.get_shard(shard_id) {
                    let results = shard.vector_search(query_embedding, top_k, min_confidence)?;
                    all_results.extend(results);
                }
            }
        }

        // Sort by distance (ascending — closest first)
        all_results.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
        all_results.truncate(top_k);
        Ok(all_results)
    }

    // ── Merkle ─────────────────────────────────────────────────────

    /// Compute the global Merkle root from all shard roots.
    pub fn global_merkle_root(&self) -> String {
        let mut global = self.global_merkle.write();

        for entry in self.shards.iter() {
            let shard = entry.value();
            let root_hex = shard.merkle_root();
            if let Ok(bytes) = hex::decode(&root_hex) {
                if bytes.len() == 32 {
                    let mut arr = [0u8; 32];
                    arr.copy_from_slice(&bytes);
                    global.update_shard(shard.shard_id(), arr);
                }
            }
        }

        global.global_root_hex()
    }

    /// Get per-shard Merkle roots.
    pub fn shard_merkle_roots(&self) -> BTreeMap<u32, String> {
        let mut roots = BTreeMap::new();
        for entry in self.shards.iter() {
            let shard = entry.value();
            roots.insert(shard.shard_id(), shard.merkle_root());
        }
        roots
    }

    // ── Statistics ─────────────────────────────────────────────────

    /// Aggregate global statistics from all shards.
    pub fn global_stats(&self) -> GlobalStats {
        let mut stats = GlobalStats::default();
        let mut total_confidence = 0.0;
        let mut total_nodes_for_avg = 0i64;

        for entry in self.shards.iter() {
            let shard = entry.value();
            let s = shard.stats();
            stats.total_nodes += s.node_count;
            stats.total_edges += s.edge_count;
            stats.total_cache_hits += s.cache_hits;
            stats.total_cache_misses += s.cache_misses;
            stats.active_shards += 1;

            *stats
                .nodes_per_domain
                .entry(s.domain.clone())
                .or_insert(0) += s.node_count;
        }

        if stats.total_cache_hits + stats.total_cache_misses > 0 {
            // cache_hit_rate computed on demand
        }

        stats.global_merkle_root = self.global_merkle_root();
        stats
    }

    /// Get stats for a single shard.
    pub fn shard_stats(&self, shard_id: u32) -> Option<ShardStats> {
        self.get_shard(shard_id).map(|s| s.stats())
    }

    // ── Management ─────────────────────────────────────────────────

    /// Compact all shards (prune low-value nodes).
    pub fn compact_all(&self, min_score: f64, current_block: i64) -> Result<(i64, u64)> {
        let mut total_pruned = 0i64;
        let mut total_reclaimed = 0u64;

        for entry in self.shards.iter() {
            let shard = entry.value();
            let (pruned, reclaimed) = shard.compact(min_score, current_block)?;
            total_pruned += pruned;
            total_reclaimed += reclaimed;
        }

        info!(total_pruned, total_reclaimed, "Global compaction complete");
        Ok((total_pruned, total_reclaimed))
    }

    /// Number of active shards.
    pub fn shard_count(&self) -> usize {
        self.shards.len()
    }

    /// Stream nodes from a domain shard.
    pub fn stream_nodes(
        &self,
        domain: &str,
        min_node_id: i64,
        batch_size: usize,
    ) -> Result<Vec<ShardNode>> {
        let d = Domain::from_str(domain);
        let shard_id = self.compute_shard_id(d, 0); // First sub-shard
        if let Some(shard) = self.get_shard(shard_id) {
            shard.iter_nodes(min_node_id, batch_size)
        } else {
            Ok(Vec::new())
        }
    }
}
