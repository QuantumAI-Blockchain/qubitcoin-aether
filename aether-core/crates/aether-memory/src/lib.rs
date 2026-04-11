//! aether-memory: Memory systems for the Aether Tree.
//!
//! Provides working memory, episodic memory, vector index (HNSW),
//! and the 3-tier memory manager.

pub mod vector_index;
pub mod working_memory;
pub mod memory_manager;

pub use vector_index::{VectorIndex, HNSWIndex};
pub use working_memory::{WorkingMemoryItem, WorkingMemory};
pub use memory_manager::{Episode, MemoryManager};
