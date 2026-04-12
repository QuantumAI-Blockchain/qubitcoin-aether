//! Aether NLP — Lightweight NLP pipeline for the Aether Tree.
//!
//! Provides tokenization, POS tagging, NER, dependency parsing, coreference resolution,
//! sentiment analysis, query translation, and extractive summarization.

pub mod coreference;
pub mod nlp_pipeline;
pub mod query_translator;
pub mod sentiment_analyzer;
pub mod summarizer;

// Re-export key types for convenience.
pub use coreference::{CoreferenceResolver, Mention, RegisteredEntity};
pub use nlp_pipeline::{
    Dependency, EntityLabel, NLPEntity, NLPPipeline, NLPResult, PipelineStats, PosTag,
};
pub use query_translator::{
    FilterOp, QueryFilter, QueryIntent, QueryIntentType, QueryTranslator, SortOrder,
    StructuredQuery,
};
pub use sentiment_analyzer::{SentimentAnalyzer, SentimentLabel, SentimentResult};
pub use summarizer::{Summary, SummarizerConfig, TextSummarizer};
