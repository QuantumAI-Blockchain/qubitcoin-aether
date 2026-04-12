//! KG Index -- TF-IDF Inverted Index for Knowledge Graph Text Search
//!
//! Provides fast text-based retrieval over knowledge node content using a
//! simple TF-IDF inverted index. This enables keyword and phrase search
//! without requiring a full database query.

use std::collections::{HashMap, HashSet};

/// A simple TF-IDF inverted index for knowledge graph nodes.
pub struct KGIndex {
    /// Mapping from term -> set of node IDs containing that term
    inverted: HashMap<String, HashSet<String>>,
    /// Total number of indexed documents (nodes)
    doc_count: usize,
}

impl KGIndex {
    /// Create a new empty index.
    pub fn new() -> Self {
        Self {
            inverted: HashMap::new(),
            doc_count: 0,
        }
    }

    /// Index a document (knowledge node) by its ID and content.
    pub fn add(&mut self, node_id: &str, content: &str) {
        let terms = Self::tokenize(content);
        for term in terms {
            self.inverted
                .entry(term)
                .or_default()
                .insert(node_id.to_string());
        }
        self.doc_count += 1;
    }

    /// Remove a document from the index.
    pub fn remove(&mut self, node_id: &str) {
        for postings in self.inverted.values_mut() {
            postings.remove(node_id);
        }
        if self.doc_count > 0 {
            self.doc_count -= 1;
        }
    }

    /// Search for nodes matching the given query string.
    /// Returns node IDs sorted by relevance (number of matching terms).
    pub fn search(&self, query: &str, limit: usize) -> Vec<String> {
        let terms = Self::tokenize(query);
        if terms.is_empty() {
            return Vec::new();
        }

        let mut scores: HashMap<&str, usize> = HashMap::new();
        for term in &terms {
            if let Some(postings) = self.inverted.get(term) {
                for node_id in postings {
                    *scores.entry(node_id.as_str()).or_insert(0) += 1;
                }
            }
        }

        let mut results: Vec<_> = scores.into_iter().collect();
        results.sort_by(|a, b| b.1.cmp(&a.1));
        results
            .into_iter()
            .take(limit)
            .map(|(id, _)| id.to_string())
            .collect()
    }

    /// Number of indexed documents.
    pub fn doc_count(&self) -> usize {
        self.doc_count
    }

    /// Number of unique terms in the index.
    pub fn term_count(&self) -> usize {
        self.inverted.len()
    }

    /// Tokenize text into lowercase terms.
    fn tokenize(text: &str) -> Vec<String> {
        text.to_lowercase()
            .split(|c: char| !c.is_alphanumeric())
            .filter(|w| w.len() >= 2)
            .map(|w| w.to_string())
            .collect()
    }
}

impl Default for KGIndex {
    fn default() -> Self {
        Self::new()
    }
}
