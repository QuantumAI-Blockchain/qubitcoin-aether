//! CRUD for the `consciousness_events` table.

use sqlx::PgPool;
use tracing::instrument;

use crate::error::Result;
use crate::models::ConsciousnessEventRow;

/// Repository for `consciousness_events`.
pub struct ConsciousnessRepo;

impl ConsciousnessRepo {
    /// Insert a consciousness event and return the auto-generated ID.
    #[instrument(skip(pool, row), fields(event_type = %row.event_type, block = row.block_height))]
    pub async fn insert(pool: &PgPool, row: &ConsciousnessEventRow) -> Result<i64> {
        let id = sqlx::query_scalar::<_, i64>(
            r#"
            INSERT INTO consciousness_events
                (event_type, phi_at_event, trigger_data, is_verified, block_height)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            "#,
        )
        .bind(&row.event_type)
        .bind(row.phi_at_event)
        .bind(&row.trigger_data)
        .bind(row.is_verified)
        .bind(row.block_height)
        .fetch_one(pool)
        .await?;
        Ok(id)
    }

    /// Fetch a single consciousness event by primary key.
    #[instrument(skip(pool))]
    pub async fn get_by_id(pool: &PgPool, id: i64) -> Result<Option<ConsciousnessEventRow>> {
        let row = sqlx::query_as::<_, ConsciousnessEventRow>(
            "SELECT * FROM consciousness_events WHERE id = $1",
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
    ) -> Result<Vec<ConsciousnessEventRow>> {
        let rows = sqlx::query_as::<_, ConsciousnessEventRow>(
            "SELECT * FROM consciousness_events ORDER BY block_height DESC LIMIT $1 OFFSET $2",
        )
        .bind(limit)
        .bind(offset)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch events of a specific type (phi_threshold_crossed, genesis, etc.).
    #[instrument(skip(pool))]
    pub async fn get_events_by_type(
        pool: &PgPool,
        event_type: &str,
        limit: i64,
    ) -> Result<Vec<ConsciousnessEventRow>> {
        let rows = sqlx::query_as::<_, ConsciousnessEventRow>(
            r#"
            SELECT * FROM consciousness_events
            WHERE event_type = $1
            ORDER BY block_height DESC LIMIT $2
            "#,
        )
        .bind(event_type)
        .bind(limit)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Fetch only verified events.
    #[instrument(skip(pool))]
    pub async fn get_verified(
        pool: &PgPool,
        limit: i64,
    ) -> Result<Vec<ConsciousnessEventRow>> {
        let rows = sqlx::query_as::<_, ConsciousnessEventRow>(
            r#"
            SELECT * FROM consciousness_events
            WHERE is_verified = true
            ORDER BY block_height DESC LIMIT $1
            "#,
        )
        .bind(limit)
        .fetch_all(pool)
        .await?;
        Ok(rows)
    }

    /// Count total consciousness events.
    #[instrument(skip(pool))]
    pub async fn count(pool: &PgPool) -> Result<i64> {
        let count = sqlx::query_scalar::<_, i64>(
            "SELECT COUNT(*) FROM consciousness_events",
        )
        .fetch_one(pool)
        .await?;
        Ok(count)
    }
}
