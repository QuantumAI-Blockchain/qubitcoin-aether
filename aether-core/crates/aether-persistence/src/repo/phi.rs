//! CRUD for the `phi_measurements` table.

use sqlx::PgPool;
use tracing::instrument;

use crate::error::Result;
use crate::models::PhiMeasurementRow;

/// Repository for `phi_measurements`.
pub struct PhiRepo;

impl PhiRepo {
    /// Insert a phi measurement and return the auto-generated ID.
    #[instrument(skip(pool, row), fields(phi = row.phi_value, block = row.block_height))]
    pub async fn insert(pool: &PgPool, row: &PhiMeasurementRow) -> Result<i64> {
        let id = sqlx::query_scalar::<_, i64>(
            r#"
            INSERT INTO phi_measurements
                (phi_value, phi_threshold, integration_score, differentiation_score,
                 num_nodes, num_edges, block_height, measured_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            "#,
        )
        .bind(row.phi_value)
        .bind(row.phi_threshold)
        .bind(row.integration_score)
        .bind(row.differentiation_score)
        .bind(row.num_nodes)
        .bind(row.num_edges)
        .bind(row.block_height)
        .bind(row.measured_at)
        .fetch_one(pool)
        .await?;
        Ok(id)
    }

    /// Fetch a single phi measurement by primary key.
    #[instrument(skip(pool))]
    pub async fn get_by_id(pool: &PgPool, id: i64) -> Result<Option<PhiMeasurementRow>> {
        let row = sqlx::query_as::<_, PhiMeasurementRow>(
            "SELECT * FROM phi_measurements WHERE id = $1",
        )
        .bind(id)
        .fetch_optional(pool)
        .await?;
        Ok(row)
    }

    /// Paginated listing ordered by block height descending.
    #[instrument(skip(pool))]
    pub async fn list(pool: &PgPool, limit: i64, offset: i64) -> Result<Vec<PhiMeasurementRow>> {
        let rows = sqlx::query_as::<_, PhiMeasurementRow>(
            "SELECT * FROM phi_measurements ORDER BY block_height DESC LIMIT $1 OFFSET $2",
        )
        .bind(limit)
        .bind(offset)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch the most recent phi measurement.
    #[instrument(skip(pool))]
    pub async fn get_latest(pool: &PgPool) -> Result<Option<PhiMeasurementRow>> {
        let row = sqlx::query_as::<_, PhiMeasurementRow>(
            "SELECT * FROM phi_measurements ORDER BY block_height DESC LIMIT 1",
        )
        .fetch_optional(pool)
        .await?;
        Ok(row)
    }

    /// Fetch phi measurements above a given threshold.
    #[instrument(skip(pool))]
    pub async fn get_above_threshold(
        pool: &PgPool,
        threshold: f64,
        limit: i64,
    ) -> Result<Vec<PhiMeasurementRow>> {
        let rows = sqlx::query_as::<_, PhiMeasurementRow>(
            r#"
            SELECT * FROM phi_measurements
            WHERE phi_value >= $1
            ORDER BY block_height DESC LIMIT $2
            "#,
        )
        .bind(threshold)
        .bind(limit)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Count total phi measurements.
    #[instrument(skip(pool))]
    pub async fn count(pool: &PgPool) -> Result<i64> {
        let count = sqlx::query_scalar::<_, i64>(
            "SELECT COUNT(*) FROM phi_measurements",
        )
        .fetch_one(pool)
        .await?;
        Ok(count)
    }
}
