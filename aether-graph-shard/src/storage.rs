//! RocksDB-backed shard storage with LRU hot cache.
//!
//! Each shard owns a RocksDB instance with column families:
//! - "nodes"  : node_id (i64 BE) -> ShardNode (bincode)
//! - "edges"  : "from:to:type" -> ShardEdge (bincode)
//! - "adj_out": node_id (i64 BE) -> Vec<(to_id, edge_type, weight)> (bincode)
//! - "adj_in" : node_id (i64 BE) -> Vec<(from_id, edge_type, weight)> (bincode)
//! - "meta"   : key -> value (counters, config)

use crate::merkle::IncrementalMerkle;
use crate::types::{Domain, ShardConfig, ShardEdge, ShardNode, ShardStats};
use anyhow::{Context, Result};
use lru::LruCache;
use parking_lot::RwLock;
use rocksdb::{
    AsColumnFamilyRef, ColumnFamilyDescriptor, DBWithThreadMode, MultiThreaded, Options,
    WriteBatch,
};
use std::num::NonZeroUsize;
use std::path::Path;
use std::sync::atomic::{AtomicI64, AtomicU64, Ordering};
use std::sync::Arc;
use tracing::{debug, info, warn};

const CF_NODES: &str = "nodes";
const CF_EDGES: &str = "edges";
const CF_ADJ_OUT: &str = "adj_out";
const CF_ADJ_IN: &str = "adj_in";
const CF_META: &str = "meta";

type RocksDB = DBWithThreadMode<MultiThreaded>;

/// A single shard backed by RocksDB with an LRU hot cache.
pub struct ShardStore {
    db: Arc<RocksDB>,
    config: ShardConfig,
    cache: RwLock<LruCache<i64, ShardNode>>,
    merkle: RwLock<IncrementalMerkle>,
    node_count: AtomicI64,
    edge_count: AtomicI64,
    cache_hits: AtomicU64,
    cache_misses: AtomicU64,
}

impl ShardStore {
    /// Open or create a shard at the given path.
    pub fn open(config: ShardConfig) -> Result<Self> {
        let path = Path::new(&config.data_dir);
        std::fs::create_dir_all(path).context("create shard directory")?;

        let mut db_opts = Options::default();
        db_opts.create_if_missing(true);
        db_opts.create_missing_column_families(true);
        db_opts.set_max_open_files(256);
        db_opts.set_keep_log_file_num(3);
        db_opts.set_max_total_wal_size(64 * 1024 * 1024); // 64MB WAL
        db_opts.increase_parallelism(num_cpus::get() as i32);
        db_opts.set_max_background_jobs(4);

        // Block-based table with bloom filters for fast key lookups
        let mut block_opts = rocksdb::BlockBasedOptions::default();
        block_opts.set_bloom_filter(10.0, false);
        block_opts.set_cache_index_and_filter_blocks(true);
        block_opts.set_block_size(16 * 1024); // 16KB blocks
        db_opts.set_block_based_table_factory(&block_opts);

        // Compression: LZ4 for speed
        db_opts.set_compression_type(rocksdb::DBCompressionType::Lz4);

        let cf_descriptors = vec![
            ColumnFamilyDescriptor::new(CF_NODES, Options::default()),
            ColumnFamilyDescriptor::new(CF_EDGES, Options::default()),
            ColumnFamilyDescriptor::new(CF_ADJ_OUT, Options::default()),
            ColumnFamilyDescriptor::new(CF_ADJ_IN, Options::default()),
            ColumnFamilyDescriptor::new(CF_META, Options::default()),
        ];

        let db = RocksDB::open_cf_descriptors(&db_opts, path, cf_descriptors)
            .context("open RocksDB")?;

        let cache_cap =
            NonZeroUsize::new(config.cache_capacity).unwrap_or(NonZeroUsize::new(100_000).unwrap());

        let store = Self {
            db: Arc::new(db),
            config,
            cache: RwLock::new(LruCache::new(cache_cap)),
            merkle: RwLock::new(IncrementalMerkle::new()),
            node_count: AtomicI64::new(0),
            edge_count: AtomicI64::new(0),
            cache_hits: AtomicU64::new(0),
            cache_misses: AtomicU64::new(0),
        };

        // Count existing items
        store.recount()?;

        info!(
            shard_id = store.config.shard_id,
            domain = store.config.domain.as_str(),
            nodes = store.node_count.load(Ordering::Relaxed),
            edges = store.edge_count.load(Ordering::Relaxed),
            "Shard opened"
        );

        Ok(store)
    }

    /// Recount nodes and edges from disk.
    fn recount(&self) -> Result<()> {
        let cf_nodes = self.db.cf_handle(CF_NODES).context("nodes CF")?;
        let mut count: i64 = 0;
        let iter = self.db.iterator_cf(&cf_nodes, rocksdb::IteratorMode::Start);
        for item in iter {
            if item.is_ok() {
                count += 1;
            }
        }
        self.node_count.store(count, Ordering::Relaxed);

        let cf_edges = self.db.cf_handle(CF_EDGES).context("edges CF")?;
        let mut ecount: i64 = 0;
        let iter = self.db.iterator_cf(&cf_edges, rocksdb::IteratorMode::Start);
        for item in iter {
            if item.is_ok() {
                ecount += 1;
            }
        }
        self.edge_count.store(ecount, Ordering::Relaxed);

        Ok(())
    }

    // ── Node Operations ────────────────────────────────────────────

    /// Put a node into the shard. Updates both RocksDB and LRU cache.
    pub fn put_node(&self, node: &ShardNode) -> Result<()> {
        let cf = self.db.cf_handle(CF_NODES).context("nodes CF")?;
        let key = node.node_id.to_be_bytes();
        let value = node.to_bytes();

        self.db.put_cf(&cf, key, &value)?;

        // Update cache
        {
            let mut cache = self.cache.write();
            cache.put(node.node_id, node.clone());
        }

        // Update Merkle tree
        {
            let mut merkle = self.merkle.write();
            merkle.insert(node.node_id, node.merkle_leaf());
        }

        self.node_count.fetch_add(1, Ordering::Relaxed);

        debug!(
            shard = self.config.shard_id,
            node_id = node.node_id,
            "Node stored"
        );
        Ok(())
    }

    /// Get a node by ID. Checks cache first, then RocksDB.
    pub fn get_node(&self, node_id: i64) -> Result<Option<ShardNode>> {
        // Check cache first
        {
            let mut cache = self.cache.write();
            if let Some(node) = cache.get(&node_id) {
                self.cache_hits.fetch_add(1, Ordering::Relaxed);
                return Ok(Some(node.clone()));
            }
        }

        self.cache_misses.fetch_add(1, Ordering::Relaxed);

        // Fetch from RocksDB
        let cf = self.db.cf_handle(CF_NODES).context("nodes CF")?;
        let key = node_id.to_be_bytes();

        match self.db.get_cf(&cf, key)? {
            Some(data) => {
                let node = ShardNode::from_bytes(&data)?;
                // Promote to cache
                {
                    let mut cache = self.cache.write();
                    cache.put(node_id, node.clone());
                }
                Ok(Some(node))
            }
            None => Ok(None),
        }
    }

    /// Get multiple nodes by ID. Batch read.
    pub fn get_nodes(&self, node_ids: &[i64]) -> Result<Vec<ShardNode>> {
        let mut result = Vec::with_capacity(node_ids.len());
        let mut missing_from_cache = Vec::new();

        // Check cache first for all
        {
            let mut cache = self.cache.write();
            for &id in node_ids {
                if let Some(node) = cache.get(&id) {
                    result.push(node.clone());
                    self.cache_hits.fetch_add(1, Ordering::Relaxed);
                } else {
                    missing_from_cache.push(id);
                    self.cache_misses.fetch_add(1, Ordering::Relaxed);
                }
            }
        }

        // Fetch remaining from RocksDB one by one (multi_get_cf API is tricky)
        if !missing_from_cache.is_empty() {
            let cf = self.db.cf_handle(CF_NODES).context("nodes CF")?;
            let mut cache = self.cache.write();
            for id in missing_from_cache {
                if let Some(data) = self.db.get_cf(&cf, id.to_be_bytes())? {
                    if let Ok(node) = ShardNode::from_bytes(&data) {
                        cache.put(id, node.clone());
                        result.push(node);
                    }
                }
            }
        }

        Ok(result)
    }

    /// Delete a node and its associated edges.
    pub fn delete_node(&self, node_id: i64, cascade_edges: bool) -> Result<(bool, i32)> {
        let cf_nodes = self.db.cf_handle(CF_NODES).context("nodes CF")?;
        let key = node_id.to_be_bytes();

        // Check if exists
        let existed = self.db.get_cf(&cf_nodes, key)?.is_some();
        if !existed {
            return Ok((false, 0));
        }

        let mut edges_removed = 0i32;
        let mut batch = WriteBatch::default();

        // Remove node
        batch.delete_cf(&cf_nodes, key);

        // Remove from cache
        {
            let mut cache = self.cache.write();
            cache.pop(&node_id);
        }

        // Remove from Merkle
        {
            let mut merkle = self.merkle.write();
            merkle.remove(node_id);
        }

        // Cascade edges if requested
        if cascade_edges {
            let cf_edges = self.db.cf_handle(CF_EDGES).context("edges CF")?;
            let cf_adj_out = self.db.cf_handle(CF_ADJ_OUT).context("adj_out CF")?;
            let cf_adj_in = self.db.cf_handle(CF_ADJ_IN).context("adj_in CF")?;

            // Remove adjacency lists
            batch.delete_cf(&cf_adj_out, key);
            batch.delete_cf(&cf_adj_in, key);

            // Scan edges involving this node
            let prefix = format!("{}:", node_id);
            let iter = self
                .db
                .iterator_cf(&cf_edges, rocksdb::IteratorMode::Start);
            for item in iter {
                if let Ok((k, _)) = item {
                    let key_str = String::from_utf8_lossy(&k);
                    if key_str.starts_with(&prefix)
                        || key_str.contains(&format!(":{}:", node_id))
                    {
                        batch.delete_cf(&cf_edges, &*k);
                        edges_removed += 1;
                    }
                }
            }
        }

        self.db.write(batch)?;
        self.node_count.fetch_sub(1, Ordering::Relaxed);
        if cascade_edges {
            self.edge_count
                .fetch_sub(edges_removed as i64, Ordering::Relaxed);
        }

        Ok((true, edges_removed))
    }

    /// Update a node's confidence.
    pub fn update_confidence(
        &self,
        node_id: i64,
        confidence: f64,
        block: i64,
    ) -> Result<Option<f64>> {
        if let Some(mut node) = self.get_node(node_id)? {
            let old = node.confidence;
            node.confidence = confidence.clamp(0.0, 1.0);
            node.last_referenced_block = block;
            node.reference_count += 1;
            self.put_node(&node)?;
            Ok(Some(old))
        } else {
            Ok(None)
        }
    }

    // ── Edge Operations ────────────────────────────────────────────

    /// Put an edge. Updates adjacency lists atomically.
    pub fn put_edge(&self, edge: &ShardEdge) -> Result<bool> {
        let cf_edges = self.db.cf_handle(CF_EDGES).context("edges CF")?;
        let cf_adj_out = self.db.cf_handle(CF_ADJ_OUT).context("adj_out CF")?;
        let cf_adj_in = self.db.cf_handle(CF_ADJ_IN).context("adj_in CF")?;

        let edge_key = edge.storage_key();
        let existed = self.db.get_cf(&cf_edges, &edge_key)?.is_some();

        let mut batch = WriteBatch::default();

        // Store edge
        batch.put_cf(&cf_edges, &edge_key, &edge.to_bytes());

        // Update outgoing adjacency list
        let from_key = edge.from_node_id.to_be_bytes();
        let mut adj_out = self.get_adjacency_list(&cf_adj_out, &from_key)?;
        if !adj_out
            .iter()
            .any(|(to, et, _)| *to == edge.to_node_id && *et == edge.edge_type)
        {
            adj_out.push((edge.to_node_id, edge.edge_type.clone(), edge.weight));
            batch.put_cf(&cf_adj_out, from_key, bincode::serialize(&adj_out)?);
        }

        // Update incoming adjacency list
        let to_key = edge.to_node_id.to_be_bytes();
        let mut adj_in = self.get_adjacency_list(&cf_adj_in, &to_key)?;
        if !adj_in
            .iter()
            .any(|(from, et, _)| *from == edge.from_node_id && *et == edge.edge_type)
        {
            adj_in.push((
                edge.from_node_id,
                edge.edge_type.clone(),
                edge.weight,
            ));
            batch.put_cf(&cf_adj_in, to_key, bincode::serialize(&adj_in)?);
        }

        self.db.write(batch)?;

        if !existed {
            self.edge_count.fetch_add(1, Ordering::Relaxed);
        }

        Ok(!existed)
    }

    /// Get adjacency list from a column family.
    fn get_adjacency_list(
        &self,
        cf: &impl AsColumnFamilyRef,
        key: &[u8],
    ) -> Result<Vec<(i64, String, f64)>> {
        match self.db.get_cf(cf, key)? {
            Some(data) => Ok(bincode::deserialize(&data)?),
            None => Ok(Vec::new()),
        }
    }

    /// Get edges for a node by direction.
    pub fn get_edges(
        &self,
        node_id: i64,
        direction: EdgeDirection,
        edge_type_filter: Option<&str>,
    ) -> Result<Vec<ShardEdge>> {
        let cf_edges = self.db.cf_handle(CF_EDGES).context("edges CF")?;
        let mut edges = Vec::new();

        match direction {
            EdgeDirection::Outgoing | EdgeDirection::Both => {
                let cf_adj = self.db.cf_handle(CF_ADJ_OUT).context("adj_out CF")?;
                let adj = self.get_adjacency_list(&cf_adj, &node_id.to_be_bytes())?;
                for (to_id, etype, weight) in &adj {
                    if edge_type_filter.is_none()
                        || edge_type_filter == Some(etype.as_str())
                    {
                        let key = format!("{}:{}:{}", node_id, to_id, etype);
                        if let Some(data) = self.db.get_cf(&cf_edges, key.as_bytes())? {
                            edges.push(ShardEdge::from_bytes(&data)?);
                        } else {
                            edges.push(ShardEdge {
                                from_node_id: node_id,
                                to_node_id: *to_id,
                                edge_type: etype.clone(),
                                weight: *weight,
                                timestamp: 0.0,
                            });
                        }
                    }
                }
            }
            _ => {}
        }

        match direction {
            EdgeDirection::Incoming | EdgeDirection::Both => {
                let cf_adj = self.db.cf_handle(CF_ADJ_IN).context("adj_in CF")?;
                let adj = self.get_adjacency_list(&cf_adj, &node_id.to_be_bytes())?;
                for (from_id, etype, weight) in &adj {
                    if edge_type_filter.is_none()
                        || edge_type_filter == Some(etype.as_str())
                    {
                        let key = format!("{}:{}:{}", from_id, node_id, etype);
                        if let Some(data) = self.db.get_cf(&cf_edges, key.as_bytes())? {
                            edges.push(ShardEdge::from_bytes(&data)?);
                        } else {
                            edges.push(ShardEdge {
                                from_node_id: *from_id,
                                to_node_id: node_id,
                                edge_type: etype.clone(),
                                weight: *weight,
                                timestamp: 0.0,
                            });
                        }
                    }
                }
            }
            _ => {}
        }

        Ok(edges)
    }

    // ── Search ─────────────────────────────────────────────────────

    /// Keyword search within this shard.
    pub fn search(
        &self,
        query: &str,
        top_k: usize,
        min_confidence: f64,
        node_type_filter: Option<&str>,
    ) -> Result<Vec<(ShardNode, f64)>> {
        let terms: Vec<String> = query
            .to_lowercase()
            .split_whitespace()
            .filter(|t| t.len() >= 2)
            .map(String::from)
            .collect();

        if terms.is_empty() {
            return Ok(Vec::new());
        }

        let cf = self.db.cf_handle(CF_NODES).context("nodes CF")?;
        let mut scored: Vec<(ShardNode, f64)> = Vec::new();

        let iter = self.db.iterator_cf(&cf, rocksdb::IteratorMode::Start);
        for item in iter {
            let (_, value) = item?;
            let node = ShardNode::from_bytes(&value)?;

            if node.confidence < min_confidence {
                continue;
            }
            if let Some(filter) = node_type_filter {
                if node.node_type != filter {
                    continue;
                }
            }

            let content_text: String = node
                .content
                .values()
                .map(|v| v.to_lowercase())
                .collect::<Vec<_>>()
                .join(" ");

            let mut score = 0.0;
            for term in &terms {
                if content_text.contains(term.as_str()) {
                    score += 1.0;
                }
            }

            if score > 0.0 {
                score *= node.confidence;
                scored.push((node, score));
            }

            if scored.len() > top_k * 10 {
                scored.sort_by(|a, b| {
                    b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal)
                });
                scored.truncate(top_k * 2);
            }
        }

        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        scored.truncate(top_k);

        Ok(scored)
    }

    // ── Merkle ─────────────────────────────────────────────────────

    pub fn merkle_root(&self) -> String {
        let mut merkle = self.merkle.write();
        merkle.root_hex()
    }

    pub fn rebuild_merkle(&self) -> Result<String> {
        let cf = self.db.cf_handle(CF_NODES).context("nodes CF")?;
        let mut merkle = self.merkle.write();

        let iter = self.db.iterator_cf(&cf, rocksdb::IteratorMode::Start);
        for item in iter {
            let (_key_bytes, value) = item?;
            let node = ShardNode::from_bytes(&value)?;
            merkle.insert(node.node_id, node.merkle_leaf());
        }

        Ok(merkle.root_hex())
    }

    // ── Statistics ─────────────────────────────────────────────────

    pub fn stats(&self) -> ShardStats {
        let hits = self.cache_hits.load(Ordering::Relaxed);
        let misses = self.cache_misses.load(Ordering::Relaxed);

        ShardStats {
            shard_id: self.config.shard_id,
            domain: self.config.domain.as_str().to_string(),
            node_count: self.node_count.load(Ordering::Relaxed),
            edge_count: self.edge_count.load(Ordering::Relaxed),
            disk_bytes: self.disk_usage(),
            avg_confidence: 0.0,
            merkle_root: self.merkle_root(),
            cache_hits: hits,
            cache_misses: misses,
        }
    }

    fn disk_usage(&self) -> u64 {
        self.db
            .property_int_value("rocksdb.estimate-live-data-size")
            .unwrap_or(None)
            .unwrap_or(0)
    }

    pub fn compact(&self, min_value_score: f64, current_block: i64) -> Result<(i64, u64)> {
        let cf = self.db.cf_handle(CF_NODES).context("nodes CF")?;
        let mut to_delete = Vec::new();

        let iter = self.db.iterator_cf(&cf, rocksdb::IteratorMode::Start);
        for item in iter {
            let (key, value) = item?;
            let node = ShardNode::from_bytes(&value)?;
            if node.value_score(current_block) < min_value_score {
                to_delete.push((key.to_vec(), node.node_id));
            }
        }

        let pruned = to_delete.len() as i64;
        let mut batch = WriteBatch::default();
        for (key, node_id) in &to_delete {
            batch.delete_cf(&cf, key);
            let mut cache = self.cache.write();
            cache.pop(node_id);
            let mut merkle = self.merkle.write();
            merkle.remove(*node_id);
        }

        let bytes_before = self.disk_usage();
        self.db.write(batch)?;

        self.db
            .compact_range_cf(&cf, None::<&[u8]>, None::<&[u8]>);

        let bytes_after = self.disk_usage();
        let reclaimed = bytes_before.saturating_sub(bytes_after);

        self.node_count.fetch_sub(pruned, Ordering::Relaxed);

        info!(
            shard = self.config.shard_id,
            pruned,
            reclaimed_bytes = reclaimed,
            "Shard compacted"
        );

        Ok((pruned, reclaimed))
    }

    pub fn iter_nodes(&self, min_node_id: i64, batch_size: usize) -> Result<Vec<ShardNode>> {
        let cf = self.db.cf_handle(CF_NODES).context("nodes CF")?;
        let start_key = min_node_id.to_be_bytes();
        let iter = self.db.iterator_cf(
            &cf,
            rocksdb::IteratorMode::From(&start_key, rocksdb::Direction::Forward),
        );

        let mut nodes = Vec::with_capacity(batch_size);
        for item in iter.take(batch_size) {
            let (_, value) = item?;
            nodes.push(ShardNode::from_bytes(&value)?);
        }

        Ok(nodes)
    }

    pub fn shard_id(&self) -> u32 {
        self.config.shard_id
    }

    pub fn domain(&self) -> Domain {
        self.config.domain
    }
}

#[derive(Debug, Clone, Copy)]
pub enum EdgeDirection {
    Outgoing,
    Incoming,
    Both,
}
