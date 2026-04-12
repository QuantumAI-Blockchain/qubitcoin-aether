//! External Knowledge Source Manager
//!
//! Manages external knowledge sources (APIs, feeds, documents) that can be
//! ingested into the Aether Tree knowledge graph.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Type of external knowledge source.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum SourceType {
    /// REST API endpoint
    Api,
    /// RSS/Atom feed
    Feed,
    /// Static document or file
    Document,
    /// Blockchain data feed
    Blockchain,
    /// Custom source
    Custom(String),
}

/// An external knowledge source configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KnowledgeSource {
    /// Unique identifier for this source
    pub id: String,
    /// Human-readable name
    pub name: String,
    /// Source type
    pub source_type: SourceType,
    /// URL or path to the source
    pub endpoint: String,
    /// Whether this source is currently enabled
    pub enabled: bool,
    /// Priority (higher = more important)
    pub priority: u32,
    /// Additional configuration parameters
    pub config: HashMap<String, String>,
}

/// Manages registration and retrieval of external knowledge sources.
pub struct ExternalKnowledgeManager {
    sources: HashMap<String, KnowledgeSource>,
}

impl ExternalKnowledgeManager {
    /// Create a new empty manager.
    pub fn new() -> Self {
        Self {
            sources: HashMap::new(),
        }
    }

    /// Register a knowledge source.
    pub fn register(&mut self, source: KnowledgeSource) {
        log::info!("Registering external knowledge source: {} ({})", source.name, source.id);
        self.sources.insert(source.id.clone(), source);
    }

    /// Remove a knowledge source by ID.
    pub fn remove(&mut self, id: &str) -> Option<KnowledgeSource> {
        self.sources.remove(id)
    }

    /// Get a source by ID.
    pub fn get(&self, id: &str) -> Option<&KnowledgeSource> {
        self.sources.get(id)
    }

    /// List all registered sources.
    pub fn list(&self) -> Vec<&KnowledgeSource> {
        self.sources.values().collect()
    }

    /// List only enabled sources, sorted by priority (descending).
    pub fn list_enabled(&self) -> Vec<&KnowledgeSource> {
        let mut sources: Vec<_> = self.sources.values().filter(|s| s.enabled).collect();
        sources.sort_by(|a, b| b.priority.cmp(&a.priority));
        sources
    }

    /// Number of registered sources.
    pub fn count(&self) -> usize {
        self.sources.len()
    }
}

impl Default for ExternalKnowledgeManager {
    fn default() -> Self {
        Self::new()
    }
}
