//! aether-persistence: Async CockroachDB persistence for the Aether Tree.
//!
//! Provides typed CRUD access to the five core AI tables via sqlx and
//! the PostgreSQL wire protocol.  All queries use runtime string SQL
//! (not compile-time macros) because a live database is not guaranteed
//! at build time.
//!
//! # Quick start
//!
//! ```rust,no_run
//! use aether_persistence::{create_pool, repo::KnowledgeNodeRepo};
//!
//! # async fn example() -> aether_persistence::error::Result<()> {
//! let pool = create_pool("postgresql://root@localhost:26257/qbc?sslmode=disable", 10).await?;
//! let nodes = KnowledgeNodeRepo::list(&pool, 100, 0).await?;
//! # Ok(())
//! # }
//! ```

pub mod error;
pub mod models;
pub mod pool;
pub mod repo;

pub use error::{PersistenceError, Result};
pub use models::{
    ConsciousnessEventRow, ConversationInsightRow, ConversationMessageRow,
    ConversationSessionRow, KnowledgeEdgeRow, KnowledgeNodeRow,
    PhiMeasurementRow, ReasoningOperationRow, UserMemoryRow,
};
pub use pool::create_pool;
pub use repo::{
    ConsciousnessRepo, ConversationInsightRepo, ConversationMessageRepo,
    ConversationSessionRepo, KnowledgeEdgeRepo, KnowledgeNodeRepo,
    PhiRepo, ReasoningRepo, UserMemoryRepo,
    ensure_conversation_tables,
};

// Re-export PgPool so downstream crates don't need a direct sqlx dependency.
pub use sqlx::postgres::PgPool;
