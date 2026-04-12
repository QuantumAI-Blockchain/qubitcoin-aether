//! Repository modules — one per AGI table.
//!
//! Each repo exposes async functions that accept `&PgPool` and operate on a
//! single table.  All queries use runtime string SQL (not compile-time macros)
//! because CockroachDB is not available during `cargo build`.

pub mod knowledge_node;
pub mod knowledge_edge;
pub mod reasoning;
pub mod phi;
pub mod consciousness;

pub use knowledge_node::KnowledgeNodeRepo;
pub use knowledge_edge::KnowledgeEdgeRepo;
pub use reasoning::ReasoningRepo;
pub use phi::PhiRepo;
pub use consciousness::ConsciousnessRepo;
