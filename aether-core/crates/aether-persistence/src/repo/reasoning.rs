//! CRUD for the `reasoning_operations` table.

use sqlx::PgPool;
use tracing::instrument;

use crate::error::Result;
use crate::models::ReasoningOperationRow;

/// Repository for `reasoning_operations`.
pub struct ReasoningRepo;

impl ReasoningRepo {
    /// Insert a reasoning operation and return the auto-generated ID.
    #[instrument(skip(pool, row), fields(op_type = %row.operation_type, block = row.block_height))]
    pub async fn insert(pool: &PgPool, row: &ReasoningOperationRow) -> Result<i64> {
        let id = sqlx::query_scalar::<_, i64>(
            r#"
            INSERT INTO reasoning_operations
                (operation_type, premise_nodes, conclusion_node_id,
                 confidence, reasoning_chain, block_height)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            "#,
        )
        .bind(&row.operation_type)
        .bind(&row.premise_nodes)
        .bind(row.conclusion_node_id)
        .bind(row.confidence)
        .bind(&row.reasoning_chain)
        .bind(row.block_height)
        .fetch_one(pool)
        .await?;
        Ok(id)
    }

    /// Fetch a single reasoning operation by primary key.
    #[instrument(skip(pool))]
    pub async fn get_by_id(pool: &PgPool, id: i64) -> Result<Option<ReasoningOperationRow>> {
        let row = sqlx::query_as::<_, ReasoningOperationRow>(
            "SELECT * FROM reasoning_operations WHERE id = $1",
        )
        .bind(id)
        .fetch_optional(pool)
        .await?;
        Ok(row)
    }

    /// Paginated listing ordered by block height descending.
    #[instrument(skip(pool))]
    pub async fn list(
        pool: &PgPool,
        limit: i64,
        offset: i64,
    ) -> Result<Vec<ReasoningOperationRow>> {
        let rows = sqlx::query_as::<_, ReasoningOperationRow>(
            "SELECT * FROM reasoning_operations ORDER BY block_height DESC LIMIT $1 OFFSET $2",
        )
        .bind(limit)
        .bind(offset)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch reasoning operations by type (deduction, induction, etc.).
    #[instrument(skip(pool))]
    pub async fn get_by_type(
        pool: &PgPool,
        operation_type: &str,
        limit: i64,
    ) -> Result<Vec<ReasoningOperationRow>> {
        let rows = sqlx::query_as::<_, ReasoningOperationRow>(
            r#"
            SELECT * FROM reasoning_operations
            WHERE operation_type = $1
            ORDER BY block_height DESC LIMIT $2
            "#,
        )
        .bind(operation_type)
        .bind(limit)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Count total reasoning operations.
    #[instrument(skip(pool))]
    pub async fn count(pool: &PgPool) -> Result<i64> {
        let count = sqlx::query_scalar::<_, i64>(
            "SELECT COUNT(*) FROM reasoning_operations",
        )
        .fetch_one(pool)
        .await?;
        Ok(count)
    }
}
