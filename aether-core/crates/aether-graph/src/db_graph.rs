//! DbKnowledgeGraph: Write-through DB-backed knowledge graph with LRU hot cache.
//!
//! Architecture: every mutation writes to PostgreSQL/CockroachDB AND updates
//! the in-memory `KnowledgeGraph`. Reads hit the in-memory cache first and
//! fall back to DB on miss, promoting to cache.
//!
//! NOT a PyO3 class -- pure Rust API for use by other crates.

use std::collections::HashMap;
use std::sync::Arc;

use aether_persistence::error::PersistenceError;
use aether_persistence::{
    KnowledgeEdgeRepo, KnowledgeEdgeRow, KnowledgeNodeRepo, KnowledgeNodeRow, PgPool,
};
use aether_types::{KeterEdge, KeterNode};

use crate::domain::classify_domain;
use crate::graph::KnowledgeGraph;
use crate::tfidf::extract_text;

/// Aggregate statistics from the DB-backed graph.
#[derive(Debug, Clone, Default)]
pub struct GraphStats {
    pub total_nodes: i64,
    pub total_edges: i64,
    pub node_type_counts: HashMap<String, i64>,
    pub edge_type_counts: HashMap<String, i64>,
    pub domain_counts: HashMap<String, i64>,
    pub avg_confidence: f64,
}

/// A DB-backed knowledge graph with an in-memory LRU hot cache.
///
/// Write-through: every add_node / add_edge writes to DB first,
/// then updates the in-memory `KnowledgeGraph` cache.
///
/// Read path: cache first, DB fallback, promote on miss.
pub struct DbKnowledgeGraph {
    pool: PgPool,
    cache: KnowledgeGraph,
    cache_capacity: usize,
    rt: Arc<tokio::runtime::Runtime>,
}

impl DbKnowledgeGraph {
    /// Create a new DB-backed graph.
    ///
    /// `pool`: sqlx PgPool for database access.
    /// `cache_capacity`: maximum nodes to hold in the in-memory cache.
    ///     When exceeded, the cache still grows (the underlying KnowledgeGraph
    ///     is a HashMap) but warm_cache limits the initial load.
    pub fn new(pool: PgPool, cache_capacity: usize) -> Result<Self, PersistenceError> {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| PersistenceError::Runtime(e.to_string()))?;

        Ok(Self {
            pool,
            cache: KnowledgeGraph::new(),
            cache_capacity,
            rt: Arc::new(rt),
        })
    }

    /// Create from an existing tokio runtime (for use inside async contexts).
    pub fn with_runtime(pool: PgPool, cache_capacity: usize, rt: Arc<tokio::runtime::Runtime>) -> Self {
        Self {
            pool,
            cache: KnowledgeGraph::new(),
            cache_capacity,
            rt,
        }
    }

    /// Load top N nodes by confidence from DB into the in-memory cache at startup.
    /// Returns the number of nodes loaded.
    pub async fn warm_cache(&self, limit: i64) -> Result<usize, PersistenceError> {
        let actual_limit = (limit as usize).min(self.cache_capacity) as i64;
        let rows = KnowledgeNodeRepo::get_top_by_confidence(&self.pool, actual_limit).await?;
        let count = rows.len();

        for row in rows {
            let node = row.into_keter_node();
            self.cache.add_node_raw(node);
        }

        Ok(count)
    }

    /// Add a knowledge node. Writes to DB, then caches in memory and indexes in TF-IDF.
    pub async fn add_node(
        &self,
        node_type: &str,
        content: HashMap<String, String>,
        confidence: f64,
        source_block: i64,
        domain: &str,
    ) -> Result<KeterNode, PersistenceError> {
        let clamped = confidence.clamp(0.0, 1.0);
        let resolved_domain = if domain.is_empty() {
            classify_domain(&content)
        } else {
            domain.to_string()
        };

        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);

        // Build content hash
        let mut tmp_node = KeterNode {
            node_id: 0,
            node_type: node_type.to_string(),
            content_hash: String::new(),
            content: content.clone(),
            confidence: clamped,
            source_block,
            timestamp: ts,
            domain: resolved_domain.clone(),
            last_referenced_block: source_block,
            reference_count: 0,
            grounding_source: String::new(),
            edges_out: vec![],
            edges_in: vec![],
        };
        tmp_node.content_hash = tmp_node.calculate_hash();

        let search = extract_text(&content);

        // Build row for DB insert
        let mut row = KnowledgeNodeRow::from_keter_node(&tmp_node);
        row.search_text = Some(search);

        // Write to DB
        let db_id = KnowledgeNodeRepo::insert(&self.pool, &row).await?;
        tmp_node.node_id = db_id;

        // Write-through to in-memory cache
        self.cache.add_node_raw(tmp_node.clone());

        Ok(tmp_node)
    }

    /// Add a directed edge. Writes to DB, then caches in memory.
    pub async fn add_edge(
        &self,
        from_id: i64,
        to_id: i64,
        edge_type: &str,
        weight: f64,
    ) -> Result<Option<KeterEdge>, PersistenceError> {
        let edge = KeterEdge {
            from_node_id: from_id,
            to_node_id: to_id,
            edge_type: edge_type.to_string(),
            weight,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs_f64())
                .unwrap_or(0.0),
        };

        // Build row for DB insert
        let row = KnowledgeEdgeRow::from_keter_edge(&edge);

        // Write to DB first
        let _db_id = KnowledgeEdgeRepo::insert(&self.pool, &row).await?;

        // Ensure both nodes are in cache (fetch from DB if needed)
        self.ensure_cached(from_id).await?;
        self.ensure_cached(to_id).await?;

        // Add to in-memory graph
        let result = self.cache.add_edge(
            from_id,
            to_id,
            edge_type.to_string(),
            weight,
        );

        if result.is_some() {
            Ok(Some(edge))
        } else {
            // Nodes might not be in cache even after ensure_cached
            // (if they don't exist in DB either). Return the edge anyway
            // since the DB write succeeded.
            self.cache.add_edge_raw(edge.clone());
            Ok(Some(edge))
        }
    }

    /// Get a node. Cache first, DB fallback with promotion to cache.
    pub async fn get_node(&self, node_id: i64) -> Result<Option<KeterNode>, PersistenceError> {
        // Check cache first
        if let Some(node) = self.cache.get_node(node_id) {
            return Ok(Some(node));
        }

        // DB fallback
        if let Some(row) = KnowledgeNodeRepo::get_by_id(&self.pool, node_id).await? {
            let node = row.into_keter_node();
            // Promote to cache
            self.cache.add_node_raw(node.clone());
            Ok(Some(node))
        } else {
            Ok(None)
        }
    }

    /// Search: delegates to in-memory TF-IDF for cached nodes,
    /// falls back to DB text search for broader results.
    pub async fn search(
        &self,
        query: &str,
        top_k: usize,
    ) -> Result<Vec<(KeterNode, f64)>, PersistenceError> {
        // First try in-memory TF-IDF
        let cached_results = self.cache.search(query.to_string(), top_k);
        if cached_results.len() >= top_k {
            return Ok(cached_results);
        }

        // Supplement with DB text search
        let remaining = top_k - cached_results.len();
        let db_rows = KnowledgeNodeRepo::search_text(&self.pool, query, remaining as i64).await?;

        let mut results = cached_results;
        for row in db_rows {
            let node_id = row.id;
            // Skip nodes already in results
            if results.iter().any(|(n, _)| n.node_id == node_id) {
                continue;
            }
            let node = row.into_keter_node();
            // DB search results get a default similarity score of 0.5
            results.push((node, 0.5));
        }

        results.truncate(top_k);
        Ok(results)
    }

    /// Get stats from DB (count, domain distribution, etc.)
    pub async fn get_stats(&self) -> Result<GraphStats, PersistenceError> {
        let total_nodes = KnowledgeNodeRepo::count(&self.pool).await?;
        let total_edges = KnowledgeEdgeRepo::count(&self.pool).await?;
        let avg_confidence = KnowledgeNodeRepo::avg_confidence(&self.pool).await?;

        let type_counts_vec = KnowledgeNodeRepo::count_by_type(&self.pool).await?;
        let domain_counts_vec = KnowledgeNodeRepo::count_by_domain(&self.pool).await?;
        let edge_type_counts_vec = KnowledgeEdgeRepo::count_by_type(&self.pool).await?;

        let node_type_counts: HashMap<String, i64> = type_counts_vec.into_iter().collect();
        let domain_counts: HashMap<String, i64> = domain_counts_vec.into_iter().collect();
        let edge_type_counts: HashMap<String, i64> = edge_type_counts_vec.into_iter().collect();

        Ok(GraphStats {
            total_nodes,
            total_edges,
            node_type_counts,
            edge_type_counts,
            domain_counts,
            avg_confidence,
        })
    }

    /// Count nodes (from DB -- authoritative).
    pub async fn node_count(&self) -> Result<i64, PersistenceError> {
        KnowledgeNodeRepo::count(&self.pool).await
    }

    /// Count edges (from DB -- authoritative).
    pub async fn edge_count(&self) -> Result<i64, PersistenceError> {
        KnowledgeEdgeRepo::count(&self.pool).await
    }

    /// Get nodes by domain from DB.
    pub async fn get_nodes_by_domain(
        &self,
        domain: &str,
        limit: i64,
    ) -> Result<Vec<KeterNode>, PersistenceError> {
        let rows = KnowledgeNodeRepo::get_nodes_by_domain(&self.pool, domain, limit).await?;
        Ok(rows.into_iter().map(|r| r.into_keter_node()).collect())
    }

    /// Get edges from a node (cache first, DB fallback).
    pub async fn get_edges_from(&self, node_id: i64) -> Result<Vec<KeterEdge>, PersistenceError> {
        let cached = self.cache.get_edges_from(node_id);
        if !cached.is_empty() {
            return Ok(cached);
        }

        let rows = KnowledgeEdgeRepo::get_edges_from_node(&self.pool, node_id).await?;
        Ok(rows.into_iter().map(|r| r.into_keter_edge()).collect())
    }

    /// Get edges to a node (cache first, DB fallback).
    pub async fn get_edges_to(&self, node_id: i64) -> Result<Vec<KeterEdge>, PersistenceError> {
        let cached = self.cache.get_edges_to(node_id);
        if !cached.is_empty() {
            return Ok(cached);
        }

        let rows = KnowledgeEdgeRepo::get_edges_to_node(&self.pool, node_id).await?;
        Ok(rows.into_iter().map(|r| r.into_keter_edge()).collect())
    }

    /// Merkle root (computed from cached nodes -- same as in-memory graph).
    pub fn compute_knowledge_root(&self) -> String {
        self.cache.compute_knowledge_root()
    }

    /// Confidence propagation (operates on cached nodes).
    pub fn propagate_confidence(&self, iterations: i64) {
        self.cache.propagate_confidence(iterations);
    }

    /// Touch node -- update reference tracking in both cache and DB.
    pub async fn touch_node(&self, node_id: i64, current_block: i64) -> Result<(), PersistenceError> {
        // Update cache
        self.cache.touch_node(node_id, current_block);

        // Get updated ref count from cache
        let ref_count = self
            .cache
            .get_node(node_id)
            .map(|n| n.reference_count as i32)
            .unwrap_or(1);

        // Update DB
        KnowledgeNodeRepo::update_reference(&self.pool, node_id, current_block, ref_count).await?;

        Ok(())
    }

    /// Access the underlying in-memory graph for Phi computation.
    pub fn cached_graph(&self) -> &KnowledgeGraph {
        &self.cache
    }

    /// Synchronous wrapper for add_node using the internal runtime.
    pub fn add_node_sync(
        &self,
        node_type: &str,
        content: HashMap<String, String>,
        confidence: f64,
        source_block: i64,
        domain: &str,
    ) -> Result<KeterNode, PersistenceError> {
        self.rt.block_on(self.add_node(node_type, content, confidence, source_block, domain))
    }

    /// Synchronous wrapper for get_node using the internal runtime.
    pub fn get_node_sync(&self, node_id: i64) -> Result<Option<KeterNode>, PersistenceError> {
        self.rt.block_on(self.get_node(node_id))
    }

    // -- Internal helpers --

    /// Ensure a node is in the cache. If not, fetch from DB.
    async fn ensure_cached(&self, node_id: i64) -> Result<(), PersistenceError> {
        if self.cache.get_node(node_id).is_some() {
            return Ok(());
        }
        // Try DB
        if let Some(row) = KnowledgeNodeRepo::get_by_id(&self.pool, node_id).await? {
            let node = row.into_keter_node();
            self.cache.add_node_raw(node);
        }
        Ok(())
    }
}

// ── Unit tests (no DB required) ─────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_graph_stats_default() {
        let stats = GraphStats::default();
        assert_eq!(stats.total_nodes, 0);
        assert_eq!(stats.total_edges, 0);
        assert!(stats.node_type_counts.is_empty());
        assert!(stats.edge_type_counts.is_empty());
        assert!(stats.domain_counts.is_empty());
        assert!((stats.avg_confidence - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_graph_stats_with_data() {
        let mut stats = GraphStats::default();
        stats.total_nodes = 100;
        stats.total_edges = 50;
        stats.node_type_counts.insert("assertion".into(), 60);
        stats.node_type_counts.insert("inference".into(), 40);
        stats.domain_counts.insert("quantum_physics".into(), 30);
        stats.avg_confidence = 0.75;

        assert_eq!(stats.total_nodes, 100);
        assert_eq!(stats.node_type_counts["assertion"], 60);
        assert_eq!(stats.domain_counts["quantum_physics"], 30);
    }

    #[test]
    fn test_row_to_node_conversion() {
        let content = serde_json::json!({"text": "hello"});
        let row = KnowledgeNodeRow {
            id: 42,
            node_type: "assertion".into(),
            content_hash: "abc123".into(),
            content,
            confidence: 0.9,
            source_block: 100,
            domain: "general".into(),
            last_referenced_block: 100,
            reference_count: 5,
            grounding_source: "block_oracle".into(),
            search_text: Some("hello".into()),
            created_at: chrono::NaiveDateTime::default(),
        };

        let node = row.into_keter_node();
        assert_eq!(node.node_id, 42);
        assert_eq!(node.node_type, "assertion");
        assert_eq!(node.content_hash, "abc123");
        assert_eq!(node.content.get("text").unwrap(), "hello");
        assert!((node.confidence - 0.9).abs() < f64::EPSILON);
        assert_eq!(node.source_block, 100);
        assert_eq!(node.reference_count, 5);
        assert_eq!(node.grounding_source, "block_oracle");
    }

    #[test]
    fn test_row_to_edge_conversion() {
        let row = KnowledgeEdgeRow {
            id: 1,
            from_node_id: 10,
            to_node_id: 20,
            edge_type: "supports".into(),
            weight: 0.8,
            created_at: chrono::NaiveDateTime::default(),
        };

        let edge = row.into_keter_edge();
        assert_eq!(edge.from_node_id, 10);
        assert_eq!(edge.to_node_id, 20);
        assert_eq!(edge.edge_type, "supports");
        assert!((edge.weight - 0.8).abs() < f64::EPSILON);
    }

    #[test]
    fn test_row_content_empty_json() {
        let row = KnowledgeNodeRow {
            id: 1,
            node_type: "assertion".into(),
            content_hash: String::new(),
            content: serde_json::json!({}),
            confidence: 0.5,
            source_block: 0,
            domain: "general".into(),
            last_referenced_block: 0,
            reference_count: 0,
            grounding_source: String::new(),
            search_text: None,
            created_at: chrono::NaiveDateTime::default(),
        };

        let node = row.into_keter_node();
        assert!(node.content.is_empty());
    }

    #[test]
    fn test_graph_stats_clone() {
        let mut stats = GraphStats::default();
        stats.total_nodes = 50;
        stats.avg_confidence = 0.8;

        let cloned = stats.clone();
        assert_eq!(cloned.total_nodes, 50);
        assert!((cloned.avg_confidence - 0.8).abs() < f64::EPSILON);
    }
}
