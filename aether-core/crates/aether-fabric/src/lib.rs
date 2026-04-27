//! # Aether Knowledge Fabric — V5
//!
//! Replaces the Python Knowledge Graph (dict of string nodes) with a continuous
//! embedding manifold stored in sharded vector indices.
//!
//! Uses HybridIndex: brute-force for <=1000 vectors, HNSW for >1000.
//! O(log n) approximate nearest neighbor search at scale.

pub mod hnsw;
pub mod search;
pub mod shard;
pub mod types;

pub use hnsw::{cosine_similarity_f32, HnswGraph, HybridIndex};
pub use search::KnowledgeFabric;
pub use shard::FabricShard;
pub use types::{KnowledgeVector, Provenance};
