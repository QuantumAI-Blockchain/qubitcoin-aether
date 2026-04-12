//! aether-memory: Memory systems for the Aether Tree.
//!
//! Provides working memory, episodic memory, vector index (HNSW),
//! the 3-tier memory manager, text embedding, and long-term consolidation.

pub mod embedder;
pub mod long_term_memory;
pub mod memory_manager;
pub mod vector_index;
pub mod working_memory;

pub use embedder::{cosine_sim, Embedder, IDFEmbedder, SimpleEmbedder};
pub use long_term_memory::{ConsolidatedPattern, ConsolidationResult, LongTermMemory};
pub use memory_manager::{Episode, MemoryManager};
pub use vector_index::{HNSWIndex, VectorIndex};
pub use working_memory::{WorkingMemory, WorkingMemoryItem};
