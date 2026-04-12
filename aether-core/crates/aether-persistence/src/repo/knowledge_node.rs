//! CRUD + domain queries for the `knowledge_nodes` table.

use sqlx::PgPool;
use tracing::instrument;

use crate::error::Result;
use crate::models::KnowledgeNodeRow;

/// Repository for `knowledge_nodes`.
pub struct KnowledgeNodeRepo;

impl KnowledgeNodeRepo {
    /// Insert a knowledge node and return the auto-generated ID.
    #[instrument(skip(pool, row), fields(node_type = %row.node_type, domain = %row.domain))]
    pub async fn insert(pool: &PgPool, row: &KnowledgeNodeRow) -> Result<i64> {
        let rec = sqlx::query_scalar::<_, i64>(
            r#"
            INSERT INTO knowledge_nodes
                (node_type, content_hash, content, confidence, source_block,
                 domain, grounding_source, reference_count, last_referenced_block, search_text)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
            "#,
        )
        .bind(&row.node_type)
        .bind(&row.content_hash)
        .bind(&row.content)
        .bind(row.confidence)
        .bind(row.source_block)
        .bind(&row.domain)
        .bind(&row.grounding_source)
        .bind(row.reference_count)
        .bind(row.last_referenced_block)
        .bind(&row.search_text)
        .fetch_one(pool)
        .await?;
        Ok(rec)
    }

    /// Fetch a single node by primary key.
    #[instrument(skip(pool))]
    pub async fn get_by_id(pool: &PgPool, id: i64) -> Result<Option<KnowledgeNodeRow>> {
        let row = sqlx::query_as::<_, KnowledgeNodeRow>(
            "SELECT * FROM knowledge_nodes WHERE id = $1",
        )
        .bind(id)
        .fetch_optional(pool)
        .await?;
        Ok(row)
    }

    /// Paginated listing ordered by creation time descending.
    #[instrument(skip(pool))]
    pub async fn list(pool: &PgPool, limit: i64, offset: i64) -> Result<Vec<KnowledgeNodeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeNodeRow>(
            "SELECT * FROM knowledge_nodes ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        )
        .bind(limit)
        .bind(offset)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch all nodes within a given Sephirot domain.
    #[instrument(skip(pool))]
    pub async fn get_nodes_by_domain(
        pool: &PgPool,
        domain: &str,
        limit: i64,
    ) -> Result<Vec<KnowledgeNodeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeNodeRow>(
            "SELECT * FROM knowledge_nodes WHERE domain = $1 ORDER BY created_at DESC LIMIT $2",
        )
        .bind(domain)
        .bind(limit)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch all nodes of a given type (assertion, inference, etc.).
    #[instrument(skip(pool))]
    pub async fn get_nodes_by_type(
        pool: &PgPool,
        node_type: &str,
        limit: i64,
    ) -> Result<Vec<KnowledgeNodeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeNodeRow>(
            "SELECT * FROM knowledge_nodes WHERE node_type = $1 ORDER BY created_at DESC LIMIT $2",
        )
        .bind(node_type)
        .bind(limit)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Count total knowledge nodes.
    #[instrument(skip(pool))]
    pub async fn count(pool: &PgPool) -> Result<i64> {
        let count = sqlx::query_scalar::<_, i64>(
            "SELECT COUNT(*) FROM knowledge_nodes",
        )
        .fetch_one(pool)
        .await?;
        Ok(count)
    }

    /// Count nodes per domain, returned as `(domain, count)` pairs.
    #[instrument(skip(pool))]
    pub async fn count_by_domain(pool: &PgPool) -> Result<Vec<(String, i64)>> {
        let rows: Vec<(String, i64)> = sqlx::query_as(
            "SELECT domain, COUNT(*) as cnt FROM knowledge_nodes GROUP BY domain ORDER BY cnt DESC",
        )
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Update last_referenced_block and reference_count for a node.
    #[instrument(skip(pool))]
    pub async fn update_reference(pool: &PgPool, id: i64, block: i64, ref_count: i32) -> Result<()> {
        sqlx::query(
            "UPDATE knowledge_nodes SET last_referenced_block = $2, reference_count = $3 WHERE id = $1",
        )
        .bind(id)
        .bind(block)
        .bind(ref_count)
        .execute(pool)
        .await?;
        Ok(())
    }

    /// Get top N nodes by confidence (for cache warming).
    #[instrument(skip(pool))]
    pub async fn get_top_by_confidence(pool: &PgPool, limit: i64) -> Result<Vec<KnowledgeNodeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeNodeRow>(
            "SELECT * FROM knowledge_nodes ORDER BY confidence DESC LIMIT $1",
        )
        .bind(limit)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Simple ILIKE text search on search_text column.
    #[instrument(skip(pool))]
    pub async fn search_text(pool: &PgPool, query: &str, limit: i64) -> Result<Vec<KnowledgeNodeRow>> {
        let pattern = format!("%{}%", query);
        let rows = sqlx::query_as::<_, KnowledgeNodeRow>(
            "SELECT * FROM knowledge_nodes WHERE search_text ILIKE $1 ORDER BY confidence DESC LIMIT $2",
        )
        .bind(pattern)
        .bind(limit)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Count nodes per type, returned as `(node_type, count)` pairs.
    #[instrument(skip(pool))]
    pub async fn count_by_type(pool: &PgPool) -> Result<Vec<(String, i64)>> {
        let rows: Vec<(String, i64)> = sqlx::query_as(
            "SELECT node_type, COUNT(*) as cnt FROM knowledge_nodes GROUP BY node_type ORDER BY cnt DESC",
        )
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Average confidence across all knowledge nodes.
    #[instrument(skip(pool))]
    pub async fn avg_confidence(pool: &PgPool) -> Result<f64> {
        let avg: Option<f64> = sqlx::query_scalar(
            "SELECT AVG(confidence) FROM knowledge_nodes",
        )
        .fetch_one(pool)
        .await?;
        Ok(avg.unwrap_or(0.0))
    }

    /// Get nodes from a specific source block.
    #[instrument(skip(pool))]
    pub async fn get_by_source_block(pool: &PgPool, block: i64) -> Result<Vec<KnowledgeNodeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeNodeRow>(
            "SELECT * FROM knowledge_nodes WHERE source_block = $1 ORDER BY id",
        )
        .bind(block)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }
}
