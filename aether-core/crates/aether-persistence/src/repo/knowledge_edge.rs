//! CRUD + graph queries for the `knowledge_edges` table.

use sqlx::PgPool;
use tracing::instrument;

use crate::error::Result;
use crate::models::KnowledgeEdgeRow;

/// Repository for `knowledge_edges`.
pub struct KnowledgeEdgeRepo;

impl KnowledgeEdgeRepo {
    /// Insert an edge and return the auto-generated ID.
    #[instrument(skip(pool, row), fields(
        from = row.from_node_id, to = row.to_node_id, edge_type = %row.edge_type
    ))]
    pub async fn insert(pool: &PgPool, row: &KnowledgeEdgeRow) -> Result<i64> {
        let id = sqlx::query_scalar::<_, i64>(
            r#"
            INSERT INTO knowledge_edges (from_node_id, to_node_id, edge_type, weight)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            "#,
        )
        .bind(row.from_node_id)
        .bind(row.to_node_id)
        .bind(&row.edge_type)
        .bind(row.weight)
        .fetch_one(pool)
        .await?;
        Ok(id)
    }

    /// Fetch a single edge by primary key.
    #[instrument(skip(pool))]
    pub async fn get_by_id(pool: &PgPool, id: i64) -> Result<Option<KnowledgeEdgeRow>> {
        let row = sqlx::query_as::<_, KnowledgeEdgeRow>(
            "SELECT * FROM knowledge_edges WHERE id = $1",
        )
        .bind(id)
        .fetch_optional(pool)
        .await?;
        Ok(row)
    }

    /// Paginated listing ordered by creation time descending.
    #[instrument(skip(pool))]
    pub async fn list(pool: &PgPool, limit: i64, offset: i64) -> Result<Vec<KnowledgeEdgeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeEdgeRow>(
            "SELECT * FROM knowledge_edges ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        )
        .bind(limit)
        .bind(offset)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch all outgoing edges from a given node.
    #[instrument(skip(pool))]
    pub async fn get_edges_from_node(
        pool: &PgPool,
        node_id: i64,
    ) -> Result<Vec<KnowledgeEdgeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeEdgeRow>(
            "SELECT * FROM knowledge_edges WHERE from_node_id = $1 ORDER BY created_at DESC",
        )
        .bind(node_id)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch all incoming edges to a given node.
    #[instrument(skip(pool))]
    pub async fn get_edges_to_node(
        pool: &PgPool,
        node_id: i64,
    ) -> Result<Vec<KnowledgeEdgeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeEdgeRow>(
            "SELECT * FROM knowledge_edges WHERE to_node_id = $1 ORDER BY created_at DESC",
        )
        .bind(node_id)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch all edges (in either direction) for a node.
    #[instrument(skip(pool))]
    pub async fn get_edges_for_node(
        pool: &PgPool,
        node_id: i64,
    ) -> Result<Vec<KnowledgeEdgeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeEdgeRow>(
            r#"
            SELECT * FROM knowledge_edges
            WHERE from_node_id = $1 OR to_node_id = $1
            ORDER BY created_at DESC
            "#,
        )
        .bind(node_id)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Count total edges.
    #[instrument(skip(pool))]
    pub async fn count(pool: &PgPool) -> Result<i64> {
        let count = sqlx::query_scalar::<_, i64>(
            "SELECT COUNT(*) FROM knowledge_edges",
        )
        .fetch_one(pool)
        .await?;
        Ok(count)
    }

    /// Fetch edges between two specific nodes.
    #[instrument(skip(pool))]
    pub async fn get_edges_between(
        pool: &PgPool,
        from_id: i64,
        to_id: i64,
    ) -> Result<Vec<KnowledgeEdgeRow>> {
        let rows = sqlx::query_as::<_, KnowledgeEdgeRow>(
            "SELECT * FROM knowledge_edges WHERE from_node_id = $1 AND to_node_id = $2",
        )
        .bind(from_id)
        .bind(to_id)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Count edges grouped by type, returned as `(edge_type, count)` pairs.
    #[instrument(skip(pool))]
    pub async fn count_by_type(pool: &PgPool) -> Result<Vec<(String, i64)>> {
        let rows: Vec<(String, i64)> = sqlx::query_as(
            "SELECT edge_type, COUNT(*) as cnt FROM knowledge_edges GROUP BY edge_type ORDER BY cnt DESC",
        )
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }
}
