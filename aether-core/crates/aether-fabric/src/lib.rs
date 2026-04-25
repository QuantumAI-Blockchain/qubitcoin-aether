//! # Aether Knowledge Fabric — V5
//!
//! Replaces the Python Knowledge Graph (dict of string nodes) with a continuous
//! embedding manifold stored in sharded RocksDB with HNSW vector indices.
//!
//! Phase 0: In-memory vector store with cosine similarity search.
//! Phase 1: RocksDB persistence + HNSW ANN index.
//! Phase 2: Multi-shard with Sephirot domain routing.

pub mod shard;
pub mod types;
pub mod search;

pub use shard::FabricShard;
pub use types::{KnowledgeVector, Provenance};
