//! aether-knowledge: Knowledge processing pipeline for the Aether Tree AI.
//!
//! Provides extraction, scoring, seeding, indexing, and question-answering over
//! the knowledge graph. This is the sensory and retrieval layer of the AI.
//!
//! Modules:
//! - `knowledge_extractor`: Extract knowledge nodes from blocks and transactions
//! - `knowledge_scorer`: Score knowledge quality, novelty, and detect gaming
//! - `knowledge_seeder`: Seed genesis knowledge at startup
//! - `genesis_knowledge`: Static seed data across 11 domains (~180 facts)
//! - `external_knowledge`: Manage external knowledge sources
//! - `external_ingestion`: Ingest raw text into knowledge nodes
//! - `kg_index`: TF-IDF inverted index for fast text search
//! - `kgqa`: Knowledge Graph Question Answering
//! - `blockchain_entity_extractor`: Extract blockchain-specific entities from data

pub mod knowledge_extractor;
pub mod knowledge_scorer;
pub mod knowledge_seeder;
pub mod genesis_knowledge;
pub mod external_knowledge;
pub mod external_ingestion;
pub mod kg_index;
pub mod kgqa;
pub mod blockchain_entity_extractor;

// Re-export key types
pub use knowledge_extractor::{KnowledgeExtractor, ExtractedKnowledge};
pub use knowledge_scorer::{KnowledgeScorer, ContributionScore, QualityTier};
pub use knowledge_seeder::{KnowledgeSeeder, SeedNode};
pub use genesis_knowledge::GENESIS_KNOWLEDGE;
pub use external_knowledge::{ExternalKnowledgeManager, KnowledgeSource};
pub use external_ingestion::{IngestionPipeline, IngestedNode};
pub use kg_index::KGIndex;
pub use kgqa::{KGQA, QAResult, QuestionType};
pub use blockchain_entity_extractor::{BlockchainEntityExtractor, BlockchainEntity, EntityType};
