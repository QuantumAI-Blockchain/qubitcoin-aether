//! aether-persistence: Async CockroachDB persistence for the Aether Tree.
//!
//! Provides typed CRUD access to the five core AGI tables via sqlx and
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
    ConsciousnessEventRow, KnowledgeEdgeRow, KnowledgeNodeRow,
    PhiMeasurementRow, ReasoningOperationRow,
};
pub use pool::create_pool;
pub use repo::{
    ConsciousnessRepo, KnowledgeEdgeRepo, KnowledgeNodeRepo,
    PhiRepo, ReasoningRepo,
};
