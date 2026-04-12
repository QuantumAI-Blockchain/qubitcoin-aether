//! Connection pool creation for CockroachDB (PostgreSQL wire protocol).

use sqlx::postgres::{PgPool, PgPoolOptions};
use tracing::info;

use crate::error::{PersistenceError, Result};

/// Create and verify a PostgreSQL connection pool.
///
/// The pool is tested with a `SELECT 1` probe before being returned.
/// CockroachDB speaks the PostgreSQL wire protocol, so `PgPool` works
/// out of the box.
pub async fn create_pool(db_url: &str, max_connections: u32) -> Result<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(max_connections)
        .connect(db_url)
        .await
        .map_err(|e| PersistenceError::Connection(format!("failed to connect: {e}")))?;

    // Verify the connection is live.
    sqlx::query("SELECT 1")
        .execute(&pool)
        .await
        .map_err(|e| PersistenceError::Connection(format!("health check failed: {e}")))?;

    info!(
        db_url = %db_url,
        max_connections = max_connections,
        "aether-persistence pool created"
    );

    Ok(pool)
}
