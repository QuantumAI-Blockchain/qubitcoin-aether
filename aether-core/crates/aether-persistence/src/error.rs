//! Persistence error types.

use thiserror::Error;

/// Errors that can occur during database operations.
#[derive(Debug, Error)]
pub enum PersistenceError {
    /// SQL/connection failure from sqlx.
    #[error("database error: {0}")]
    Database(#[from] sqlx::Error),

    /// JSON serialization/deserialization failure.
    #[error("serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// Requested entity was not found.
    #[error("entity not found: {0}")]
    NotFound(String),

    /// Failed to establish or maintain a connection pool.
    #[error("connection error: {0}")]
    Connection(String),
}

/// Convenience alias used throughout the crate.
pub type Result<T> = std::result::Result<T, PersistenceError>;
