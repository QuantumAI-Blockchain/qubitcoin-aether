//! TF-IDF search index for knowledge graph nodes.

use std::collections::{HashMap, HashSet};

/// Stop words filtered from search queries and indexed text.
pub const STOP_WORDS: &[&str] = &[
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "shall", "to",
    "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "just", "because", "but", "and", "or", "if",
    "while", "about", "up", "it", "its", "this", "that", "these", "those", "i", "me", "my", "we",
    "our", "you", "your", "he", "him", "his", "she", "her", "they", "them", "their", "what",
    "which", "who", "whom", "also", "well", "like", "even", "still", "much",
];

/// Tokenize text: lowercase, extract alphanumeric tokens, filter stop words and short tokens.
pub fn tokenize(text: &str) -> Vec<String> {
    let stop: HashSet<&str> = STOP_WORDS.iter().copied().collect();
    let lower = text.to_lowercase();
    let mut tokens = Vec::new();
    let mut current = String::new();

    for ch in lower.chars() {
        if ch.is_alphanumeric() {
            current.push(ch);
        } else {
            if current.len() > 2 && !stop.contains(current.as_str()) {
                tokens.push(std::mem::take(&mut current));
            } else {
                current.clear();
            }
        }
    }
    if current.len() > 2 && !stop.contains(current.as_str()) {
        tokens.push(current);
    }

    tokens
}

/// Extract searchable text from a KeterNode's content dict.
pub fn extract_text(content: &HashMap<String, String>) -> String {
    let keys = [
        "text",
        "description",
        "subject",
        "query",
        "content",
        "block_hash",
        "miner_address",
        "node_type",
    ];
    let mut parts = Vec::new();
    for key in &keys {
        if let Some(val) = content.get(*key) {
            parts.push(val.as_str());
        }
    }
    parts.join(" ")
}

/// Incremental TF-IDF index over knowledge graph nodes.
pub struct TFIDFIndex {
    /// term -> {node_id: augmented_tf}
    inverted_index: HashMap<String, HashMap<i64, f64>>,
    /// term -> count of docs containing term
    doc_freq: HashMap<String, usize>,
    /// node_id -> set of terms
    node_terms: HashMap<i64, HashSet<String>>,
    /// total documents indexed
    n_docs: usize,
    /// cached IDF values
    idf_cache: HashMap<String, f64>,
    /// whether IDF cache needs refresh
    idf_dirty: bool,
}

impl TFIDFIndex {
    pub fn new() -> Self {
        TFIDFIndex {
            inverted_index: HashMap::new(),
            doc_freq: HashMap::new(),
            node_terms: HashMap::new(),
            n_docs: 0,
            idf_cache: HashMap::new(),
            idf_dirty: true,
        }
    }

    /// Index a single node's content.
    pub fn add_node(&mut self, node_id: i64, content: &HashMap<String, String>) {
        let text = extract_text(content);
        let tokens = tokenize(&text);
        if tokens.is_empty() {
            return;
        }

        // Compute term frequencies
        let mut tf: HashMap<String, f64> = HashMap::new();
        for token in &tokens {
            *tf.entry(token.clone()).or_insert(0.0) += 1.0;
        }

        // Normalize by max frequency (augmented TF)
        let max_tf = tf.values().cloned().fold(1.0_f64, f64::max);
        for val in tf.values_mut() {
            *val = 0.5 + 0.5 * (*val / max_tf);
        }

        // Update inverted index
        let mut new_terms = HashSet::new();
        for (term, score) in &tf {
            let entry = self
                .inverted_index
                .entry(term.clone())
                .or_insert_with(HashMap::new);
            if !entry.contains_key(&node_id) {
                *self.doc_freq.entry(term.clone()).or_insert(0) += 1;
            }
            entry.insert(node_id, *score);
            new_terms.insert(term.clone());
        }

        self.node_terms.insert(node_id, new_terms);
        self.n_docs += 1;
        self.idf_dirty = true;
    }

    /// Remove a node from the index.
    pub fn remove_node(&mut self, node_id: i64) {
        if let Some(terms) = self.node_terms.remove(&node_id) {
            for term in &terms {
                if let Some(postings) = self.inverted_index.get_mut(term) {
                    postings.remove(&node_id);
                    if let Some(df) = self.doc_freq.get_mut(term) {
                        *df = df.saturating_sub(1);
                    }
                    if postings.is_empty() {
                        self.inverted_index.remove(term);
                        self.doc_freq.remove(term);
                    }
                }
            }
            self.n_docs = self.n_docs.saturating_sub(1);
            self.idf_dirty = true;
        }
    }

    /// Search the index with a natural language query.
    /// Returns (node_id, cosine_similarity) pairs, highest first.
    pub fn query(&mut self, query_text: &str, top_k: usize) -> Vec<(i64, f64)> {
        if self.n_docs == 0 {
            return vec![];
        }

        let tokens = tokenize(query_text);
        if tokens.is_empty() {
            return vec![];
        }

        self.refresh_idf();

        // Build query TF-IDF vector
        let mut q_tf: HashMap<String, f64> = HashMap::new();
        for t in &tokens {
            *q_tf.entry(t.clone()).or_insert(0.0) += 1.0;
        }
        let max_q = q_tf.values().cloned().fold(1.0_f64, f64::max);

        let mut q_tfidf: HashMap<String, f64> = HashMap::new();
        for (term, count) in &q_tf {
            if let Some(&idf) = self.idf_cache.get(term) {
                q_tfidf.insert(term.clone(), (0.5 + 0.5 * count / max_q) * idf);
            }
        }

        if q_tfidf.is_empty() {
            return vec![];
        }

        let q_norm: f64 = q_tfidf.values().map(|v| v * v).sum::<f64>().sqrt();
        if q_norm == 0.0 {
            return vec![];
        }

        // Score each candidate document
        let mut scores: HashMap<i64, f64> = HashMap::new();
        for (term, q_weight) in &q_tfidf {
            let idf = self.idf_cache.get(term).copied().unwrap_or(0.0);
            if let Some(postings) = self.inverted_index.get(term) {
                for (&node_id, &tf_score) in postings {
                    *scores.entry(node_id).or_insert(0.0) += q_weight * (tf_score * idf);
                }
            }
        }

        // Normalize by document norms for cosine similarity
        let mut results: Vec<(i64, f64)> = scores
            .into_iter()
            .map(|(node_id, dot_product)| {
                let doc_terms = self.node_terms.get(&node_id);
                let doc_norm_sq: f64 = match doc_terms {
                    Some(terms) => terms
                        .iter()
                        .map(|t| {
                            let tf = self
                                .inverted_index
                                .get(t)
                                .and_then(|m| m.get(&node_id))
                                .copied()
                                .unwrap_or(0.0);
                            let idf = self.idf_cache.get(t).copied().unwrap_or(0.0);
                            (tf * idf).powi(2)
                        })
                        .sum(),
                    None => 0.0,
                };
                let doc_norm = if doc_norm_sq > 0.0 {
                    doc_norm_sq.sqrt()
                } else {
                    1.0
                };
                let cosine = dot_product / (q_norm * doc_norm);
                (node_id, cosine)
            })
            .collect();

        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(top_k);
        results
    }

    /// Recompute IDF cache if dirty.
    pub fn refresh_idf(&mut self) {
        if !self.idf_dirty {
            return;
        }
        let n = self.n_docs.max(1) as f64;
        self.idf_cache.clear();
        for (term, &df) in &self.doc_freq {
            // Smoothed IDF: log((1 + n) / (1 + df)) + 1 (sklearn default)
            let idf = ((1.0 + n) / (1.0 + df as f64)).ln() + 1.0;
            self.idf_cache.insert(term.clone(), idf);
        }
        self.idf_dirty = false;
    }

    /// Return index statistics.
    pub fn get_stats(&self) -> HashMap<String, f64> {
        let mut stats = HashMap::new();
        stats.insert("total_docs".into(), self.n_docs as f64);
        stats.insert("unique_terms".into(), self.doc_freq.len() as f64);
        let avg = if self.n_docs > 0 {
            self.node_terms.values().map(|t| t.len()).sum::<usize>() as f64 / self.n_docs as f64
        } else {
            0.0
        };
        stats.insert("avg_terms_per_doc".into(), avg);
        stats
    }
}
