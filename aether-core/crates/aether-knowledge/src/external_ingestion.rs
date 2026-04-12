//! External Ingestion Pipeline
//!
//! Ingests raw text and structured data into knowledge nodes suitable for
//! insertion into the Aether Tree knowledge graph.

use serde::{Deserialize, Serialize};

/// A knowledge node produced by the ingestion pipeline.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IngestedNode {
    /// The domain this node belongs to (e.g. "blockchain", "physics")
    pub domain: String,
    /// Content text of the node
    pub content: String,
    /// Confidence score assigned during ingestion (0.0 - 1.0)
    pub confidence: f64,
    /// Source identifier (which external source produced this)
    pub source_id: String,
    /// Optional tags for categorisation
    pub tags: Vec<String>,
}

/// Pipeline that processes raw text into knowledge nodes.
pub struct IngestionPipeline {
    /// Minimum content length to accept
    min_content_length: usize,
    /// Default confidence for ingested nodes
    default_confidence: f64,
}

impl IngestionPipeline {
    /// Create a new ingestion pipeline with default settings.
    pub fn new() -> Self {
        Self {
            min_content_length: 10,
            default_confidence: 0.5,
        }
    }

    /// Create with custom parameters.
    pub fn with_params(min_content_length: usize, default_confidence: f64) -> Self {
        Self {
            min_content_length,
            default_confidence: default_confidence.clamp(0.0, 1.0),
        }
    }

    /// Ingest a single piece of raw text from a source.
    pub fn ingest(&self, text: &str, domain: &str, source_id: &str) -> Option<IngestedNode> {
        let content = text.trim().to_string();
        if content.len() < self.min_content_length {
            log::debug!("Rejected ingestion: content too short ({} < {})", content.len(), self.min_content_length);
            return None;
        }

        Some(IngestedNode {
            domain: domain.to_string(),
            content,
            confidence: self.default_confidence,
            source_id: source_id.to_string(),
            tags: Vec::new(),
        })
    }

    /// Ingest a batch of texts, filtering out those that are too short.
    pub fn ingest_batch(&self, items: &[(String, String)], source_id: &str) -> Vec<IngestedNode> {
        items
            .iter()
            .filter_map(|(text, domain)| self.ingest(text, domain, source_id))
            .collect()
    }
}

impl Default for IngestionPipeline {
    fn default() -> Self {
        Self::new()
    }
}
