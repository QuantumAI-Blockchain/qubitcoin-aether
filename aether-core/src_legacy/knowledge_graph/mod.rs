//! KnowledgeGraph — in-memory knowledge graph with Merkle root, TF-IDF search,
//! adjacency index, domain classification, and confidence propagation.
//!
//! This is the Rust-accelerated pure computation layer. Database persistence
//! remains in the Python wrapper — this module handles the hot-path operations:
//! - O(1) node/edge lookup via HashMap + adjacency lists
//! - Cached Merkle root (SHA-256, invalidated on mutation)
//! - Built-in TF-IDF search (no external dependency)
//! - Thread-safe via parking_lot::RwLock

pub mod keter_edge;
pub mod keter_node;

pub use keter_edge::KeterEdge;
pub use keter_node::KeterNode;

use parking_lot::RwLock;
use pyo3::prelude::*;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

// ── Domain keyword mapping ──────────────────────────────────────────────────

/// Domain keyword sets for auto-classification of knowledge nodes.
fn domain_keywords() -> HashMap<&'static str, HashSet<&'static str>> {
    let mut m: HashMap<&str, HashSet<&str>> = HashMap::new();

    m.insert(
        "quantum_physics",
        [
            "qubit",
            "quantum",
            "superposition",
            "entanglement",
            "decoherence",
            "hamiltonian",
            "vqe",
            "qiskit",
            "photon",
            "wave",
            "particle",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "mathematics",
        [
            "theorem",
            "proof",
            "algebra",
            "topology",
            "geometry",
            "calculus",
            "prime",
            "fibonacci",
            "equation",
            "integral",
            "matrix",
            "vector",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "computer_science",
        [
            "algorithm",
            "compiler",
            "database",
            "hash",
            "binary",
            "complexity",
            "turing",
            "sorting",
            "graph_theory",
            "recursion",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "blockchain",
        [
            "block",
            "transaction",
            "consensus",
            "mining",
            "utxo",
            "merkle",
            "ledger",
            "token",
            "smart_contract",
            "defi",
            "bridge",
            "staking",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "cryptography",
        [
            "encryption",
            "signature",
            "dilithium",
            "lattice",
            "zero_knowledge",
            "zkp",
            "aes",
            "rsa",
            "cipher",
            "post_quantum",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "philosophy",
        [
            "consciousness",
            "qualia",
            "epistemology",
            "ethics",
            "ontology",
            "kabbalah",
            "sephirot",
            "phenomenology",
            "mind",
            "metaphysics",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "biology",
        [
            "neuron", "dna", "gene", "evolution", "cell", "protein", "ecology", "organism",
            "neural", "brain", "synapse",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "physics",
        [
            "relativity",
            "gravity",
            "thermodynamics",
            "entropy",
            "energy",
            "electromagnetism",
            "nuclear",
            "optics",
            "cosmology",
            "dark_matter",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "economics",
        [
            "market",
            "inflation",
            "monetary",
            "gdp",
            "trade",
            "supply_demand",
            "fiscal",
            "currency",
            "game_theory",
        ]
        .into_iter()
        .collect(),
    );
    m.insert(
        "ai_ml",
        [
            "transformer",
            "neural_network",
            "reinforcement",
            "gradient",
            "backpropagation",
            "llm",
            "attention",
            "embedding",
            "training",
            "inference",
        ]
        .into_iter()
        .collect(),
    );

    m
}

/// Classify a knowledge node's domain from its content.
///
/// Scans all text values in the content dict against keyword sets.
/// Returns the best-matching domain or "general" if no strong match.
fn classify_domain(content: &HashMap<String, String>) -> String {
    let text: String = content
        .values()
        .map(|v| v.to_lowercase())
        .collect::<Vec<_>>()
        .join(" ");
    let text = text.replace('-', "_").replace('.', " ");
    let words: HashSet<&str> = text.split_whitespace().collect();

    let keywords = domain_keywords();
    let mut best_domain = "general";
    let mut best_score: usize = 0;

    for (domain, kw_set) in &keywords {
        let score = words.iter().filter(|w| kw_set.contains(*w)).count();
        if score > best_score {
            best_score = score;
            best_domain = domain;
        }
    }

    best_domain.to_string()
}

// ── TF-IDF search index ─────────────────────────────────────────────────────

/// Stop words filtered from search queries and indexed text.
const STOP_WORDS: &[&str] = &[
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
fn tokenize(text: &str) -> Vec<String> {
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
fn extract_text(content: &HashMap<String, String>) -> String {
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
struct TFIDFIndex {
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
    fn new() -> Self {
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
    fn add_node(&mut self, node_id: i64, content: &HashMap<String, String>) {
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
    fn remove_node(&mut self, node_id: i64) {
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
    fn query(&mut self, query_text: &str, top_k: usize) -> Vec<(i64, f64)> {
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
    fn refresh_idf(&mut self) {
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
    fn get_stats(&self) -> HashMap<String, f64> {
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

// ── Internal graph state ────────────────────────────────────────────────────

/// Interior state protected by RwLock.
struct GraphInner {
    nodes: HashMap<i64, KeterNode>,
    edges: Vec<KeterEdge>,
    /// node_id -> outgoing edges
    adj_out: HashMap<i64, Vec<KeterEdge>>,
    /// node_id -> incoming edges
    adj_in: HashMap<i64, Vec<KeterEdge>>,
    next_id: i64,
    /// Merkle root cache
    merkle_dirty: bool,
    merkle_cache: String,
    /// TF-IDF search index
    search_index: TFIDFIndex,
}

impl GraphInner {
    fn new() -> Self {
        GraphInner {
            nodes: HashMap::new(),
            edges: Vec::new(),
            adj_out: HashMap::new(),
            adj_in: HashMap::new(),
            next_id: 1,
            merkle_dirty: true,
            merkle_cache: String::new(),
            search_index: TFIDFIndex::new(),
        }
    }
}

// ── KnowledgeGraph (PyO3 class) ─────────────────────────────────────────────

/// In-memory knowledge graph — Rust-accelerated pure computation layer.
///
/// Supports CRUD operations, BFS subgraph traversal, DFS path finding,
/// Merkle root computation, TF-IDF search, domain classification,
/// confidence propagation, and contradiction detection.
///
/// Thread-safe via parking_lot::RwLock — multiple readers, exclusive writers.
#[pyclass]
pub struct KnowledgeGraph {
    inner: Arc<RwLock<GraphInner>>,
}

/// Return current UNIX timestamp as f64.
fn now_f64() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

#[pymethods]
impl KnowledgeGraph {
    /// Create a new empty KnowledgeGraph (in-memory, no DB).
    #[new]
    pub fn new() -> Self {
        KnowledgeGraph {
            inner: Arc::new(RwLock::new(GraphInner::new())),
        }
    }

    /// Add a new knowledge node.
    ///
    /// Returns the newly created KeterNode with auto-assigned ID, content hash,
    /// timestamp, and domain classification.
    #[pyo3(signature = (node_type, content, confidence, source_block, domain = String::new()))]
    pub fn add_node(
        &self,
        node_type: String,
        content: HashMap<String, String>,
        confidence: f64,
        source_block: i64,
        domain: String,
    ) -> KeterNode {
        let clamped_confidence = confidence.clamp(0.0, 1.0);
        let resolved_domain = if domain.is_empty() {
            classify_domain(&content)
        } else {
            domain
        };
        let ts = now_f64();

        let mut node = KeterNode {
            node_id: 0, // set below under lock
            node_type,
            content_hash: String::new(),
            content: content.clone(),
            confidence: clamped_confidence,
            source_block,
            timestamp: ts,
            domain: resolved_domain,
            last_referenced_block: source_block,
            reference_count: 0,
            grounding_source: String::new(),
            edges_out: vec![],
            edges_in: vec![],
        };
        node.content_hash = node.calculate_hash();

        let mut g = self.inner.write();
        node.node_id = g.next_id;
        g.next_id += 1;
        g.nodes.insert(node.node_id, node.clone());
        g.merkle_dirty = true;
        g.search_index.add_node(node.node_id, &content);

        node
    }

    /// Add a directed edge between two nodes.
    ///
    /// Returns the KeterEdge if both nodes exist, or None if either is missing.
    #[pyo3(signature = (from_id, to_id, edge_type = "supports".to_string(), weight = 1.0))]
    pub fn add_edge(
        &self,
        from_id: i64,
        to_id: i64,
        edge_type: String,
        weight: f64,
    ) -> Option<KeterEdge> {
        let mut g = self.inner.write();

        if !g.nodes.contains_key(&from_id) || !g.nodes.contains_key(&to_id) {
            return None;
        }

        let edge = KeterEdge {
            from_node_id: from_id,
            to_node_id: to_id,
            edge_type,
            weight,
            timestamp: now_f64(),
        };

        g.edges.push(edge.clone());
        g.adj_out
            .entry(from_id)
            .or_insert_with(Vec::new)
            .push(edge.clone());
        g.adj_in
            .entry(to_id)
            .or_insert_with(Vec::new)
            .push(edge.clone());
        g.merkle_dirty = true;

        if let Some(from_node) = g.nodes.get_mut(&from_id) {
            from_node.edges_out.push(to_id);
        }
        if let Some(to_node) = g.nodes.get_mut(&to_id) {
            to_node.edges_in.push(from_id);
        }

        Some(edge)
    }

    /// Get a node by ID, or None if not found.
    pub fn get_node(&self, node_id: i64) -> Option<KeterNode> {
        let g = self.inner.read();
        g.nodes.get(&node_id).cloned()
    }

    /// Get neighboring nodes in the given direction ('out' or 'in').
    #[pyo3(signature = (node_id, direction = "out".to_string()))]
    pub fn get_neighbors(&self, node_id: i64, direction: String) -> Vec<KeterNode> {
        let g = self.inner.read();
        let node = match g.nodes.get(&node_id) {
            Some(n) => n,
            None => return vec![],
        };

        let ids = if direction == "out" {
            &node.edges_out
        } else {
            &node.edges_in
        };

        ids.iter()
            .filter_map(|nid| g.nodes.get(nid).cloned())
            .collect()
    }

    /// BFS to get subgraph up to given depth. Returns dict of {node_id: KeterNode}.
    #[pyo3(signature = (root_id, depth = 3))]
    pub fn get_subgraph(&self, root_id: i64, depth: i64) -> HashMap<i64, KeterNode> {
        let g = self.inner.read();
        let mut visited: HashMap<i64, KeterNode> = HashMap::new();
        let mut queue: VecDeque<(i64, i64)> = VecDeque::new();
        queue.push_back((root_id, 0));

        while let Some((nid, d)) = queue.pop_front() {
            if visited.contains_key(&nid) || d > depth {
                continue;
            }
            let node = match g.nodes.get(&nid) {
                Some(n) => n.clone(),
                None => continue,
            };

            // Collect neighbor IDs before inserting
            let neighbor_ids: Vec<i64> = node
                .edges_out
                .iter()
                .chain(node.edges_in.iter())
                .copied()
                .collect();

            visited.insert(nid, node);

            for neighbor_id in neighbor_ids {
                if !visited.contains_key(&neighbor_id) {
                    queue.push_back((neighbor_id, d + 1));
                }
            }
        }

        visited
    }

    /// Find all paths between two nodes up to max_depth using DFS.
    #[pyo3(signature = (from_id, to_id, max_depth = 5))]
    pub fn find_paths(&self, from_id: i64, to_id: i64, max_depth: i64) -> Vec<Vec<i64>> {
        let g = self.inner.read();
        let mut paths: Vec<Vec<i64>> = Vec::new();
        let mut path = vec![from_id];
        let mut visited: HashSet<i64> = HashSet::new();
        visited.insert(from_id);

        Self::dfs_paths(
            &g.nodes,
            from_id,
            to_id,
            max_depth as usize,
            &mut path,
            &mut visited,
            &mut paths,
        );

        paths
    }

    /// Propagate confidence scores through the graph.
    ///
    /// Nodes supported by high-confidence parents gain confidence;
    /// nodes contradicted by high-confidence parents lose it.
    #[pyo3(signature = (iterations = 3))]
    pub fn propagate_confidence(&self, iterations: i64) {
        let mut g = self.inner.write();

        for _ in 0..iterations {
            let mut updates: HashMap<i64, f64> = HashMap::new();

            for (&nid, node) in &g.nodes {
                if node.edges_in.is_empty() {
                    continue;
                }

                let mut support_sum: f64 = 0.0;
                let mut contradict_sum: f64 = 0.0;
                let mut count: usize = 0;

                if let Some(in_edges) = g.adj_in.get(&nid) {
                    for edge in in_edges {
                        if let Some(parent) = g.nodes.get(&edge.from_node_id) {
                            match edge.edge_type.as_str() {
                                "supports" | "derives" => {
                                    support_sum += parent.confidence * edge.weight;
                                }
                                "contradicts" => {
                                    contradict_sum += parent.confidence * edge.weight;
                                }
                                _ => {}
                            }
                            count += 1;
                        }
                    }
                }

                if count > 0 {
                    let delta = (support_sum - contradict_sum) / count as f64 * 0.1;
                    let new_conf = (node.confidence + delta).clamp(0.0, 1.0);
                    updates.insert(nid, new_conf);
                }
            }

            for (nid, conf) in updates {
                if let Some(node) = g.nodes.get_mut(&nid) {
                    node.confidence = conf;
                }
            }
        }
    }

    /// Compute Merkle root hash of the entire knowledge graph.
    ///
    /// Used in Proof-of-Thought for chain binding.
    /// Cached: only recomputes when graph is mutated.
    pub fn compute_knowledge_root(&self) -> String {
        let mut g = self.inner.write();

        if g.nodes.is_empty() {
            let mut hasher = Sha256::new();
            hasher.update(b"empty_knowledge");
            return format!("{:x}", hasher.finalize());
        }

        if !g.merkle_dirty && !g.merkle_cache.is_empty() {
            return g.merkle_cache.clone();
        }

        // Sorted by node_id for determinism
        let sorted_ids: BTreeMap<i64, &KeterNode> = g.nodes.iter().map(|(&k, v)| (k, v)).collect();

        let mut leaves: Vec<String> = sorted_ids
            .into_iter()
            .map(|(nid, node)| {
                let data = format!("{}:{}:{:.6}", nid, node.content_hash, node.confidence);
                let mut hasher = Sha256::new();
                hasher.update(data.as_bytes());
                format!("{:x}", hasher.finalize())
            })
            .collect();

        // Build Merkle tree
        while leaves.len() > 1 {
            if leaves.len() % 2 == 1 {
                let last = leaves.last().unwrap().clone();
                leaves.push(last);
            }
            let mut new_leaves = Vec::with_capacity(leaves.len() / 2);
            for i in (0..leaves.len()).step_by(2) {
                let combined = format!("{}{}", leaves[i], leaves[i + 1]);
                let mut hasher = Sha256::new();
                hasher.update(combined.as_bytes());
                new_leaves.push(format!("{:x}", hasher.finalize()));
            }
            leaves = new_leaves;
        }

        g.merkle_cache = leaves[0].clone();
        g.merkle_dirty = false;
        g.merkle_cache.clone()
    }

    /// TF-IDF search over the knowledge graph.
    ///
    /// Returns list of (KeterNode, similarity_score) tuples, best match first.
    #[pyo3(signature = (query, top_k = 10))]
    pub fn search(&self, query: String, top_k: usize) -> Vec<(KeterNode, f64)> {
        let mut g = self.inner.write();
        let results = g.search_index.query(&query, top_k);
        results
            .into_iter()
            .filter_map(|(nid, score)| g.nodes.get(&nid).cloned().map(|node| (node, score)))
            .collect()
    }

    /// Find nodes by type, sorted by confidence descending.
    #[pyo3(signature = (node_type, limit = 100))]
    pub fn find_by_type(&self, node_type: String, limit: usize) -> Vec<KeterNode> {
        let g = self.inner.read();
        let mut matching: Vec<KeterNode> = g
            .nodes
            .values()
            .filter(|n| n.node_type == node_type)
            .cloned()
            .collect();
        matching.sort_by(|a, b| {
            b.confidence
                .partial_cmp(&a.confidence)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        matching.truncate(limit);
        matching
    }

    /// Find nodes whose content dict contains a matching key-value pair.
    #[pyo3(signature = (key, value, limit = 50))]
    pub fn find_by_content(&self, key: String, value: String, limit: usize) -> Vec<KeterNode> {
        let g = self.inner.read();
        let mut matching: Vec<KeterNode> = g
            .nodes
            .values()
            .filter(|n| n.content.get(&key).map(|v| v.as_str()) == Some(value.as_str()))
            .cloned()
            .collect();
        matching.sort_by(|a, b| b.source_block.cmp(&a.source_block));
        matching.truncate(limit);
        matching
    }

    /// Get the most recently added nodes by source block.
    #[pyo3(signature = (count = 20))]
    pub fn find_recent(&self, count: usize) -> Vec<KeterNode> {
        let g = self.inner.read();
        let mut nodes: Vec<KeterNode> = g.nodes.values().cloned().collect();
        nodes.sort_by(|a, b| b.source_block.cmp(&a.source_block));
        nodes.truncate(count);
        nodes
    }

    /// Get all edges grouped by type for a specific node.
    ///
    /// Returns dict like {"out_supports": [2, 3], "in_derives": [1]}.
    pub fn get_edge_types_for_node(&self, node_id: i64) -> HashMap<String, Vec<i64>> {
        let g = self.inner.read();
        let mut result: HashMap<String, Vec<i64>> = HashMap::new();

        if let Some(out_edges) = g.adj_out.get(&node_id) {
            for edge in out_edges {
                result
                    .entry(format!("out_{}", edge.edge_type))
                    .or_insert_with(Vec::new)
                    .push(edge.to_node_id);
            }
        }

        if let Some(in_edges) = g.adj_in.get(&node_id) {
            for edge in in_edges {
                result
                    .entry(format!("in_{}", edge.edge_type))
                    .or_insert_with(Vec::new)
                    .push(edge.from_node_id);
            }
        }

        result
    }

    /// Get all outgoing edges from a node.
    pub fn get_edges_from(&self, node_id: i64) -> Vec<KeterEdge> {
        let g = self.inner.read();
        g.adj_out.get(&node_id).cloned().unwrap_or_default()
    }

    /// Get all incoming edges to a node.
    pub fn get_edges_to(&self, node_id: i64) -> Vec<KeterEdge> {
        let g = self.inner.read();
        g.adj_in.get(&node_id).cloned().unwrap_or_default()
    }

    /// Prune nodes with confidence below threshold.
    ///
    /// Nodes of protected types (default: {"axiom"}) are never pruned.
    /// Returns the number of nodes removed.
    #[pyo3(signature = (threshold = 0.1, protect_types = None))]
    pub fn prune_low_confidence(
        &self,
        threshold: f64,
        protect_types: Option<HashSet<String>>,
    ) -> usize {
        let protect = protect_types.unwrap_or_else(|| {
            let mut s = HashSet::new();
            s.insert("axiom".into());
            s
        });

        let mut g = self.inner.write();

        let to_remove: Vec<i64> = g
            .nodes
            .iter()
            .filter(|(_, node)| node.confidence < threshold && !protect.contains(&node.node_type))
            .map(|(&nid, _)| nid)
            .collect();

        if to_remove.is_empty() {
            return 0;
        }

        let remove_set: HashSet<i64> = to_remove.iter().copied().collect();

        // Remove edges referencing pruned nodes
        g.edges
            .retain(|e| !remove_set.contains(&e.from_node_id) && !remove_set.contains(&e.to_node_id));

        for &nid in &to_remove {
            // Clean up adjacency index: remove outgoing edge references
            if let Some(out_edges) = g.adj_out.remove(&nid) {
                for edge in &out_edges {
                    if let Some(in_list) = g.adj_in.get_mut(&edge.to_node_id) {
                        in_list.retain(|e| e.from_node_id != nid);
                    }
                }
            }
            // Clean up adjacency index: remove incoming edge references
            if let Some(in_edges) = g.adj_in.remove(&nid) {
                for edge in &in_edges {
                    if let Some(out_list) = g.adj_out.get_mut(&edge.from_node_id) {
                        out_list.retain(|e| e.to_node_id != nid);
                    }
                }
            }
            // Clean up edges_out/edges_in lists on remaining nodes
            for (_, other_node) in g.nodes.iter_mut() {
                other_node.edges_out.retain(|&id| id != nid);
                other_node.edges_in.retain(|&id| id != nid);
            }
            // Remove from search index
            g.search_index.remove_node(nid);
            // Remove node
            g.nodes.remove(&nid);
        }

        g.merkle_dirty = true;
        to_remove.len()
    }

    /// Update a node's last_referenced_block and increment reference count.
    pub fn touch_node(&self, node_id: i64, current_block: i64) {
        let mut g = self.inner.write();
        if let Some(node) = g.nodes.get_mut(&node_id) {
            node.last_referenced_block = current_block;
            node.reference_count += 1;
        }
    }

    /// Boost confidence of frequently-referenced nodes.
    ///
    /// Nodes with reference_count >= min_references get a small confidence
    /// increase proportional to log(reference_count).
    /// Returns the number of nodes boosted.
    #[pyo3(signature = (min_references = 5, boost_per_ref = 0.01, max_boost = 0.15))]
    pub fn boost_referenced_nodes(
        &self,
        min_references: i64,
        boost_per_ref: f64,
        max_boost: f64,
    ) -> usize {
        let mut g = self.inner.write();
        let mut boosted: usize = 0;

        for node in g.nodes.values_mut() {
            if node.reference_count >= min_references {
                let boost =
                    max_boost.min(boost_per_ref * (node.reference_count as f64).ln());
                let new_conf = 1.0_f64.min(node.confidence + boost);
                if new_conf > node.confidence {
                    node.confidence = new_conf;
                    boosted += 1;
                }
            }
        }

        boosted
    }

    /// Detect contradictions between a new node and existing nodes in the same domain.
    ///
    /// Checks for numeric value conflicts and creates 'contradicts' edges.
    /// Returns the number of contradiction edges created.
    #[pyo3(signature = (new_node_id, max_checks = 20))]
    pub fn detect_contradictions(&self, new_node_id: i64, max_checks: usize) -> usize {
        // We need to read the new node first, then potentially write edges.
        // To avoid holding the lock across add_edge, we gather candidates first.
        let candidates: Vec<(i64, String)>;
        let new_text: String;
        let new_domain: String;

        {
            let g = self.inner.read();
            let new_node = match g.nodes.get(&new_node_id) {
                Some(n) => n,
                None => return 0,
            };

            if new_node.node_type != "assertion" && new_node.node_type != "inference" {
                return 0;
            }

            new_text = new_node
                .content
                .get("text")
                .cloned()
                .unwrap_or_default()
                .to_lowercase();
            if new_text.is_empty() {
                return 0;
            }
            new_domain = new_node.domain.clone();

            let mut cands: Vec<(i64, i64, String)> = g
                .nodes
                .values()
                .filter(|n| {
                    n.node_id != new_node_id
                        && (n.node_type == "assertion" || n.node_type == "inference")
                        && (n.domain == new_domain || new_domain.is_empty())
                        && n.content.contains_key("text")
                })
                .map(|n| {
                    (
                        n.node_id,
                        n.source_block,
                        n.content
                            .get("text")
                            .cloned()
                            .unwrap_or_default()
                            .to_lowercase(),
                    )
                })
                .collect();

            // Sort by most recent first
            cands.sort_by(|a, b| b.1.cmp(&a.1));
            cands.truncate(max_checks);

            candidates = cands.into_iter().map(|(id, _, text)| (id, text)).collect();
        }

        let new_words: HashSet<&str> = new_text.split_whitespace().collect();
        let new_numbers: HashSet<String> = extract_numbers(&new_text);

        let mut created: usize = 0;

        for (existing_id, existing_text) in &candidates {
            if existing_text.is_empty() {
                continue;
            }

            let existing_words: HashSet<&str> = existing_text.split_whitespace().collect();
            let existing_numbers: HashSet<String> = extract_numbers(existing_text);

            let overlap = new_words.intersection(&existing_words).count();
            let total = new_words.union(&existing_words).count();
            let word_similarity = if total > 0 {
                overlap as f64 / total as f64
            } else {
                0.0
            };

            if word_similarity > 0.4
                && !new_numbers.is_empty()
                && !existing_numbers.is_empty()
                && new_numbers != existing_numbers
                && new_numbers.intersection(&existing_numbers).count() == 0
            {
                // Likely contradiction: same subject, different numeric values
                if self
                    .add_edge(new_node_id, *existing_id, "contradicts".into(), 0.7)
                    .is_some()
                {
                    created += 1;
                }
                if created >= 3 {
                    break;
                }
            }
        }

        created
    }

    /// Get knowledge graph statistics.
    pub fn get_stats(&self) -> HashMap<String, PyObject> {
        Python::with_gil(|py| {
            let g = self.inner.read();

            let mut type_counts: HashMap<String, usize> = HashMap::new();
            for node in g.nodes.values() {
                *type_counts.entry(node.node_type.clone()).or_insert(0) += 1;
            }

            let mut edge_type_counts: HashMap<String, usize> = HashMap::new();
            for edge in &g.edges {
                *edge_type_counts.entry(edge.edge_type.clone()).or_insert(0) += 1;
            }

            let avg_confidence = if g.nodes.is_empty() {
                0.0
            } else {
                let sum: f64 = g.nodes.values().map(|n| n.confidence).sum();
                (sum / g.nodes.len() as f64 * 10000.0).round() / 10000.0
            };

            let mut domain_counts: HashMap<String, usize> = HashMap::new();
            for node in g.nodes.values() {
                let d = if node.domain.is_empty() {
                    "general"
                } else {
                    &node.domain
                };
                *domain_counts.entry(d.to_string()).or_insert(0) += 1;
            }

            // Compute merkle root (need to drop read guard and use write path)
            drop(g);
            let root = self.compute_knowledge_root();
            let truncated_root = if root.len() > 16 {
                format!("{}...", &root[..16])
            } else {
                root
            };

            let mut stats: HashMap<String, PyObject> = HashMap::new();
            let g = self.inner.read();
            stats.insert("total_nodes".into(), g.nodes.len().into_pyobject(py).unwrap().into());
            stats.insert("total_edges".into(), g.edges.len().into_pyobject(py).unwrap().into());
            stats.insert("node_types".into(), type_counts.into_pyobject(py).unwrap().into());
            stats.insert("edge_types".into(), edge_type_counts.into_pyobject(py).unwrap().into());
            stats.insert("avg_confidence".into(), avg_confidence.into_pyobject(py).unwrap().into());
            stats.insert("domains".into(), domain_counts.into_pyobject(py).unwrap().into());
            stats.insert("knowledge_root".into(), truncated_root.into_pyobject(py).unwrap().into());

            stats
        })
    }

    /// Get node counts and average confidence per domain.
    pub fn get_domain_stats(&self) -> HashMap<String, HashMap<String, f64>> {
        let g = self.inner.read();
        let mut domains: HashMap<String, (usize, f64)> = HashMap::new();

        for node in g.nodes.values() {
            let d = if node.domain.is_empty() {
                "general".to_string()
            } else {
                node.domain.clone()
            };
            let entry = domains.entry(d).or_insert((0, 0.0));
            entry.0 += 1;
            entry.1 += node.confidence;
        }

        let mut result: HashMap<String, HashMap<String, f64>> = HashMap::new();
        // Sort by count descending
        let mut sorted: Vec<(String, (usize, f64))> = domains.into_iter().collect();
        sorted.sort_by(|a, b| b.1 .0.cmp(&a.1 .0));

        for (domain, (count, total_conf)) in sorted {
            let mut entry = HashMap::new();
            entry.insert("count".into(), count as f64);
            let avg = if count > 0 {
                (total_conf / count as f64 * 10000.0).round() / 10000.0
            } else {
                0.0
            };
            entry.insert("avg_confidence".into(), avg);
            result.insert(domain, entry);
        }

        result
    }

    /// Get statistics on grounded vs ungrounded knowledge nodes.
    pub fn get_grounding_stats(&self) -> HashMap<String, PyObject> {
        Python::with_gil(|py| {
            let g = self.inner.read();
            let total = g.nodes.len();
            let mut grounded: usize = 0;
            let mut by_source: HashMap<String, usize> = HashMap::new();

            for node in g.nodes.values() {
                if !node.grounding_source.is_empty() {
                    grounded += 1;
                    *by_source.entry(node.grounding_source.clone()).or_insert(0) += 1;
                }
            }

            let ratio = if total > 0 {
                (grounded as f64 / total as f64 * 10000.0).round() / 10000.0
            } else {
                0.0
            };

            let mut result: HashMap<String, PyObject> = HashMap::new();
            result.insert("total_nodes".into(), total.into_pyobject(py).unwrap().into());
            result.insert("grounded_nodes".into(), grounded.into_pyobject(py).unwrap().into());
            result.insert("grounding_ratio".into(), ratio.into_pyobject(py).unwrap().into());
            result.insert("by_source".into(), by_source.into_pyobject(py).unwrap().into());
            result
        })
    }

    /// Reclassify domains for all nodes that have no domain set.
    /// Returns the number of nodes reclassified.
    pub fn reclassify_domains(&self) -> usize {
        let mut g = self.inner.write();
        let mut count: usize = 0;

        // Collect node_ids that need reclassification and their content
        let to_reclassify: Vec<(i64, HashMap<String, String>)> = g
            .nodes
            .iter()
            .filter(|(_, n)| n.domain.is_empty())
            .map(|(&id, n)| (id, n.content.clone()))
            .collect();

        for (nid, content) in to_reclassify {
            let domain = classify_domain(&content);
            if let Some(node) = g.nodes.get_mut(&nid) {
                node.domain = domain;
                count += 1;
            }
        }

        count
    }

    /// Get TF-IDF search index statistics.
    pub fn get_search_stats(&self) -> HashMap<String, f64> {
        let g = self.inner.read();
        g.search_index.get_stats()
    }

    /// Return the total number of nodes.
    pub fn node_count(&self) -> usize {
        let g = self.inner.read();
        g.nodes.len()
    }

    /// Return the total number of edges.
    pub fn edge_count(&self) -> usize {
        let g = self.inner.read();
        g.edges.len()
    }

    /// Bulk-load nodes from Python (list of KeterNode objects).
    ///
    /// Used during initial load to bypass per-node locking overhead.
    pub fn bulk_load_nodes(&self, nodes: Vec<KeterNode>) {
        let mut g = self.inner.write();
        for node in nodes {
            g.search_index.add_node(node.node_id, &node.content);
            g.next_id = g.next_id.max(node.node_id + 1);
            g.nodes.insert(node.node_id, node);
        }
        g.merkle_dirty = true;
    }

    /// Bulk-load edges from Python (list of KeterEdge objects).
    ///
    /// Used during initial load to bypass per-edge locking overhead.
    pub fn bulk_load_edges(&self, edges: Vec<KeterEdge>) {
        let mut g = self.inner.write();
        for edge in edges {
            let from_id = edge.from_node_id;
            let to_id = edge.to_node_id;

            g.adj_out
                .entry(from_id)
                .or_insert_with(Vec::new)
                .push(edge.clone());
            g.adj_in
                .entry(to_id)
                .or_insert_with(Vec::new)
                .push(edge.clone());

            if let Some(from_node) = g.nodes.get_mut(&from_id) {
                from_node.edges_out.push(to_id);
            }
            if let Some(to_node) = g.nodes.get_mut(&to_id) {
                to_node.edges_in.push(from_id);
            }

            g.edges.push(edge);
        }
        g.merkle_dirty = true;
    }
}

// ── Rust-internal accessors (not exposed to Python) ─────────────────────────

impl KnowledgeGraph {
    /// Return a snapshot of all nodes as a Vec, sorted by node_id for
    /// deterministic ordering. Used by PhiCalculator and other Rust modules.
    pub fn get_nodes_raw(&self) -> Vec<KeterNode> {
        let g = self.inner.read();
        let mut nodes: Vec<KeterNode> = g.nodes.values().cloned().collect();
        nodes.sort_by_key(|n| n.node_id);
        nodes
    }

    /// Return a clone of all edges. Used by PhiCalculator and other Rust modules.
    pub fn get_edges_raw(&self) -> Vec<KeterEdge> {
        let g = self.inner.read();
        g.edges.clone()
    }

    /// Add a raw KeterNode without auto-assignment of ID, hash, or domain.
    /// The node is inserted as-is. Used by tests and internal Rust callers.
    pub fn add_node_raw(&self, node: KeterNode) {
        let mut g = self.inner.write();
        g.next_id = g.next_id.max(node.node_id + 1);
        g.search_index.add_node(node.node_id, &node.content);
        g.nodes.insert(node.node_id, node);
        g.merkle_dirty = true;
    }

    /// Add a raw KeterEdge without validation. Used by tests and internal
    /// Rust callers.
    pub fn add_edge_raw(&self, edge: KeterEdge) {
        let mut g = self.inner.write();
        let from_id = edge.from_node_id;
        let to_id = edge.to_node_id;
        g.adj_out
            .entry(from_id)
            .or_insert_with(Vec::new)
            .push(edge.clone());
        g.adj_in
            .entry(to_id)
            .or_insert_with(Vec::new)
            .push(edge.clone());
        if let Some(from_node) = g.nodes.get_mut(&from_id) {
            from_node.edges_out.push(to_id);
        }
        if let Some(to_node) = g.nodes.get_mut(&to_id) {
            to_node.edges_in.push(from_id);
        }
        g.edges.push(edge);
        g.merkle_dirty = true;
    }
}

// ── Private helper methods (not exposed to Python) ──────────────────────────

impl KnowledgeGraph {
    /// DFS helper for find_paths.
    fn dfs_paths(
        nodes: &HashMap<i64, KeterNode>,
        current: i64,
        target: i64,
        max_depth: usize,
        path: &mut Vec<i64>,
        visited: &mut HashSet<i64>,
        paths: &mut Vec<Vec<i64>>,
    ) {
        if path.len() > max_depth {
            return;
        }
        if current == target {
            paths.push(path.clone());
            return;
        }
        let node = match nodes.get(&current) {
            Some(n) => n,
            None => return,
        };
        for &nid in &node.edges_out {
            if !visited.contains(&nid) {
                visited.insert(nid);
                path.push(nid);
                Self::dfs_paths(nodes, nid, target, max_depth, path, visited, paths);
                path.pop();
                visited.remove(&nid);
            }
        }
    }
}

/// Extract numbers (integers and decimals) from text for contradiction detection.
fn extract_numbers(text: &str) -> HashSet<String> {
    let mut numbers = HashSet::new();
    let mut current = String::new();
    let mut has_digit = false;

    for ch in text.chars() {
        if ch.is_ascii_digit() {
            current.push(ch);
            has_digit = true;
        } else if ch == '.' && has_digit && !current.contains('.') {
            current.push(ch);
        } else {
            if has_digit && !current.is_empty() {
                // Trim trailing dot
                let s = current.trim_end_matches('.').to_string();
                if !s.is_empty() {
                    numbers.insert(s);
                }
            }
            current.clear();
            has_digit = false;
        }
    }
    if has_digit && !current.is_empty() {
        let s = current.trim_end_matches('.').to_string();
        if !s.is_empty() {
            numbers.insert(s);
        }
    }

    numbers
}

// ── Unit tests ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn make_content(text: &str) -> HashMap<String, String> {
        let mut c = HashMap::new();
        c.insert("text".into(), text.into());
        c
    }

    fn make_graph_with_nodes() -> KnowledgeGraph {
        let kg = KnowledgeGraph::new();
        kg.add_node(
            "assertion".into(),
            make_content("quantum entanglement is real"),
            0.9,
            1,
            String::new(),
        );
        kg.add_node(
            "observation".into(),
            make_content("photon detected at 532nm wavelength"),
            0.8,
            2,
            String::new(),
        );
        kg.add_node(
            "inference".into(),
            make_content("quantum computing enables faster optimization"),
            0.7,
            3,
            String::new(),
        );
        kg
    }

    #[test]
    fn test_add_node_basic() {
        let kg = KnowledgeGraph::new();
        let node = kg.add_node(
            "assertion".into(),
            make_content("hello world"),
            0.8,
            1,
            String::new(),
        );
        assert_eq!(node.node_id, 1);
        assert_eq!(node.node_type, "assertion");
        assert!((node.confidence - 0.8).abs() < f64::EPSILON);
        assert_eq!(node.source_block, 1);
        assert!(!node.content_hash.is_empty());
        assert_eq!(node.last_referenced_block, 1);
    }

    #[test]
    fn test_add_node_clamps_confidence() {
        let kg = KnowledgeGraph::new();
        let low = kg.add_node("assertion".into(), make_content("test"), -0.5, 0, String::new());
        assert!((low.confidence - 0.0).abs() < f64::EPSILON);

        let high = kg.add_node("assertion".into(), make_content("test"), 1.5, 0, String::new());
        assert!((high.confidence - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_add_node_auto_domain() {
        let kg = KnowledgeGraph::new();
        let node = kg.add_node(
            "assertion".into(),
            make_content("qubit superposition entanglement quantum"),
            0.9,
            1,
            String::new(),
        );
        assert_eq!(node.domain, "quantum_physics");
    }

    #[test]
    fn test_add_node_explicit_domain() {
        let kg = KnowledgeGraph::new();
        let node = kg.add_node(
            "axiom".into(),
            make_content("some axiom"),
            1.0,
            0,
            "mathematics".into(),
        );
        assert_eq!(node.domain, "mathematics");
    }

    #[test]
    fn test_add_node_increments_ids() {
        let kg = KnowledgeGraph::new();
        let n1 = kg.add_node("assertion".into(), make_content("a"), 0.5, 0, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("b"), 0.5, 0, String::new());
        let n3 = kg.add_node("assertion".into(), make_content("c"), 0.5, 0, String::new());
        assert_eq!(n1.node_id, 1);
        assert_eq!(n2.node_id, 2);
        assert_eq!(n3.node_id, 3);
    }

    #[test]
    fn test_get_node() {
        let kg = make_graph_with_nodes();
        let node = kg.get_node(1);
        assert!(node.is_some());
        assert_eq!(node.unwrap().node_type, "assertion");

        let missing = kg.get_node(999);
        assert!(missing.is_none());
    }

    #[test]
    fn test_add_edge() {
        let kg = make_graph_with_nodes();
        let edge = kg.add_edge(1, 2, "supports".into(), 0.9);
        assert!(edge.is_some());
        let e = edge.unwrap();
        assert_eq!(e.from_node_id, 1);
        assert_eq!(e.to_node_id, 2);
        assert_eq!(e.edge_type, "supports");
    }

    #[test]
    fn test_add_edge_missing_node() {
        let kg = make_graph_with_nodes();
        let edge = kg.add_edge(1, 999, "supports".into(), 1.0);
        assert!(edge.is_none());

        let edge2 = kg.add_edge(999, 1, "supports".into(), 1.0);
        assert!(edge2.is_none());
    }

    #[test]
    fn test_get_neighbors() {
        let kg = make_graph_with_nodes();
        kg.add_edge(1, 2, "supports".into(), 1.0);
        kg.add_edge(1, 3, "derives".into(), 0.8);

        let out = kg.get_neighbors(1, "out".into());
        assert_eq!(out.len(), 2);

        let in_nodes = kg.get_neighbors(2, "in".into());
        assert_eq!(in_nodes.len(), 1);
        assert_eq!(in_nodes[0].node_id, 1);
    }

    #[test]
    fn test_get_subgraph() {
        let kg = make_graph_with_nodes();
        kg.add_edge(1, 2, "supports".into(), 1.0);
        kg.add_edge(2, 3, "derives".into(), 0.8);

        let subgraph = kg.get_subgraph(1, 1);
        // Depth 1: node 1 + its direct neighbors (2)
        assert!(subgraph.contains_key(&1));
        assert!(subgraph.contains_key(&2));
        // Node 3 is depth 2 from node 1
        assert!(!subgraph.contains_key(&3));

        let full = kg.get_subgraph(1, 3);
        assert_eq!(full.len(), 3);
    }

    #[test]
    fn test_find_paths() {
        let kg = make_graph_with_nodes();
        kg.add_edge(1, 2, "supports".into(), 1.0);
        kg.add_edge(2, 3, "derives".into(), 0.8);
        kg.add_edge(1, 3, "supports".into(), 0.5);

        let paths = kg.find_paths(1, 3, 5);
        // Two paths: 1->3 direct, and 1->2->3
        assert_eq!(paths.len(), 2);
    }

    #[test]
    fn test_find_paths_no_path() {
        let kg = make_graph_with_nodes();
        // No edges, so no paths
        let paths = kg.find_paths(1, 3, 5);
        assert!(paths.is_empty());
    }

    #[test]
    fn test_compute_knowledge_root_empty() {
        let kg = KnowledgeGraph::new();
        let root = kg.compute_knowledge_root();
        // SHA-256 of b"empty_knowledge"
        assert_eq!(root.len(), 64);
    }

    #[test]
    fn test_compute_knowledge_root_deterministic() {
        let kg = make_graph_with_nodes();
        let root1 = kg.compute_knowledge_root();
        let root2 = kg.compute_knowledge_root();
        assert_eq!(root1, root2);
        assert_eq!(root1.len(), 64);
    }

    #[test]
    fn test_compute_knowledge_root_changes_on_mutation() {
        let kg = KnowledgeGraph::new();
        kg.add_node("assertion".into(), make_content("a"), 0.5, 0, String::new());
        let root1 = kg.compute_knowledge_root();

        kg.add_node("assertion".into(), make_content("b"), 0.5, 0, String::new());
        let root2 = kg.compute_knowledge_root();

        assert_ne!(root1, root2);
    }

    #[test]
    fn test_compute_knowledge_root_cached() {
        let kg = make_graph_with_nodes();
        let root1 = kg.compute_knowledge_root();
        // Call again — should use cache (same result)
        let root2 = kg.compute_knowledge_root();
        assert_eq!(root1, root2);
    }

    #[test]
    fn test_search_tfidf() {
        let kg = KnowledgeGraph::new();
        kg.add_node(
            "assertion".into(),
            make_content("quantum entanglement experiment"),
            0.9,
            1,
            String::new(),
        );
        kg.add_node(
            "observation".into(),
            make_content("classical mechanics gravity"),
            0.8,
            2,
            String::new(),
        );
        kg.add_node(
            "inference".into(),
            make_content("quantum computing qubit superposition"),
            0.7,
            3,
            String::new(),
        );

        let results = kg.search("quantum entanglement".into(), 10);
        assert!(!results.is_empty());
        // The first result should be the node about quantum entanglement
        assert_eq!(results[0].0.node_id, 1);
    }

    #[test]
    fn test_search_no_results() {
        let kg = KnowledgeGraph::new();
        kg.add_node("assertion".into(), make_content("hello world"), 0.9, 1, String::new());
        let results = kg.search("zzzznonexistent".into(), 10);
        assert!(results.is_empty());
    }

    #[test]
    fn test_find_by_type() {
        let kg = make_graph_with_nodes();
        let assertions = kg.find_by_type("assertion".into(), 100);
        assert_eq!(assertions.len(), 1);
        assert_eq!(assertions[0].node_type, "assertion");
    }

    #[test]
    fn test_find_by_content() {
        let kg = KnowledgeGraph::new();
        let mut content = HashMap::new();
        content.insert("subject".into(), "physics".into());
        content.insert("text".into(), "something about physics".into());
        kg.add_node("assertion".into(), content, 0.9, 1, String::new());

        let results = kg.find_by_content("subject".into(), "physics".into(), 50);
        assert_eq!(results.len(), 1);

        let no_results = kg.find_by_content("subject".into(), "math".into(), 50);
        assert!(no_results.is_empty());
    }

    #[test]
    fn test_find_recent() {
        let kg = KnowledgeGraph::new();
        kg.add_node("assertion".into(), make_content("a"), 0.5, 10, String::new());
        kg.add_node("assertion".into(), make_content("b"), 0.5, 20, String::new());
        kg.add_node("assertion".into(), make_content("c"), 0.5, 30, String::new());

        let recent = kg.find_recent(2);
        assert_eq!(recent.len(), 2);
        assert_eq!(recent[0].source_block, 30);
        assert_eq!(recent[1].source_block, 20);
    }

    #[test]
    fn test_get_edge_types_for_node() {
        let kg = make_graph_with_nodes();
        kg.add_edge(1, 2, "supports".into(), 1.0);
        kg.add_edge(1, 3, "derives".into(), 0.8);
        kg.add_edge(3, 1, "contradicts".into(), 0.5);

        let edge_types = kg.get_edge_types_for_node(1);
        assert!(edge_types.contains_key("out_supports"));
        assert!(edge_types.contains_key("out_derives"));
        assert!(edge_types.contains_key("in_contradicts"));
        assert_eq!(edge_types["out_supports"], vec![2]);
    }

    #[test]
    fn test_get_edges_from_to() {
        let kg = make_graph_with_nodes();
        kg.add_edge(1, 2, "supports".into(), 1.0);
        kg.add_edge(1, 3, "derives".into(), 0.8);

        let from_1 = kg.get_edges_from(1);
        assert_eq!(from_1.len(), 2);

        let to_2 = kg.get_edges_to(2);
        assert_eq!(to_2.len(), 1);
        assert_eq!(to_2[0].from_node_id, 1);

        let from_99 = kg.get_edges_from(99);
        assert!(from_99.is_empty());
    }

    #[test]
    fn test_propagate_confidence() {
        let kg = KnowledgeGraph::new();
        let n1 = kg.add_node("assertion".into(), make_content("a"), 0.9, 0, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("b"), 0.5, 0, String::new());
        kg.add_edge(n1.node_id, n2.node_id, "supports".into(), 1.0);

        kg.propagate_confidence(3);

        // n2 should have increased confidence due to support from high-confidence n1
        let updated = kg.get_node(n2.node_id).unwrap();
        assert!(updated.confidence > 0.5);
    }

    #[test]
    fn test_propagate_confidence_contradiction() {
        let kg = KnowledgeGraph::new();
        let n1 = kg.add_node("assertion".into(), make_content("a"), 0.9, 0, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("b"), 0.5, 0, String::new());
        kg.add_edge(n1.node_id, n2.node_id, "contradicts".into(), 1.0);

        kg.propagate_confidence(3);

        // n2 should have decreased confidence due to contradiction from high-confidence n1
        let updated = kg.get_node(n2.node_id).unwrap();
        assert!(updated.confidence < 0.5);
    }

    #[test]
    fn test_prune_low_confidence() {
        let kg = KnowledgeGraph::new();
        kg.add_node("assertion".into(), make_content("low"), 0.05, 0, String::new());
        kg.add_node("assertion".into(), make_content("mid"), 0.5, 0, String::new());
        kg.add_node("axiom".into(), make_content("axiom"), 0.01, 0, String::new());
        kg.add_edge(1, 2, "supports".into(), 1.0);

        assert_eq!(kg.node_count(), 3);

        let pruned = kg.prune_low_confidence(0.1, None);
        assert_eq!(pruned, 1); // Only the low-confidence non-axiom
        assert_eq!(kg.node_count(), 2);

        // Axiom was below threshold but protected
        assert!(kg.get_node(3).is_some());
        // Low-confidence node removed
        assert!(kg.get_node(1).is_none());
    }

    #[test]
    fn test_prune_removes_edges() {
        let kg = KnowledgeGraph::new();
        kg.add_node("assertion".into(), make_content("low"), 0.05, 0, String::new());
        kg.add_node("assertion".into(), make_content("mid"), 0.5, 0, String::new());
        kg.add_edge(1, 2, "supports".into(), 1.0);
        kg.add_edge(2, 1, "derives".into(), 0.8);

        kg.prune_low_confidence(0.1, None);

        // Edges involving pruned node should be removed
        assert!(kg.get_edges_from(1).is_empty());
        assert!(kg.get_edges_to(1).is_empty());
        assert!(kg.get_edges_from(2).is_empty()); // 2->1 removed
        assert!(kg.get_edges_to(2).is_empty()); // 1->2 removed
    }

    #[test]
    fn test_touch_node() {
        let kg = KnowledgeGraph::new();
        let node = kg.add_node("assertion".into(), make_content("test"), 0.8, 10, String::new());

        kg.touch_node(node.node_id, 100);
        let updated = kg.get_node(node.node_id).unwrap();
        assert_eq!(updated.last_referenced_block, 100);
        assert_eq!(updated.reference_count, 1);

        kg.touch_node(node.node_id, 200);
        let updated = kg.get_node(node.node_id).unwrap();
        assert_eq!(updated.last_referenced_block, 200);
        assert_eq!(updated.reference_count, 2);
    }

    #[test]
    fn test_boost_referenced_nodes() {
        let kg = KnowledgeGraph::new();
        let node = kg.add_node("assertion".into(), make_content("test"), 0.5, 0, String::new());

        // Touch it many times
        for _ in 0..10 {
            kg.touch_node(node.node_id, 100);
        }

        let boosted = kg.boost_referenced_nodes(5, 0.01, 0.15);
        assert_eq!(boosted, 1);

        let updated = kg.get_node(node.node_id).unwrap();
        assert!(updated.confidence > 0.5);
    }

    #[test]
    fn test_detect_contradictions() {
        let kg = KnowledgeGraph::new();
        kg.add_node(
            "assertion".into(),
            make_content("the speed of light is 300000 km/s in vacuum"),
            0.9,
            1,
            "physics".into(),
        );
        let n2 = kg.add_node(
            "assertion".into(),
            make_content("the speed of light is 250000 km/s in vacuum"),
            0.7,
            2,
            "physics".into(),
        );

        let created = kg.detect_contradictions(n2.node_id, 20);
        // Should detect a contradiction: same subject, different numbers
        assert!(created >= 1);
    }

    #[test]
    fn test_detect_contradictions_same_numbers() {
        let kg = KnowledgeGraph::new();
        kg.add_node(
            "assertion".into(),
            make_content("the speed of light is 300000 km/s"),
            0.9,
            1,
            "physics".into(),
        );
        let n2 = kg.add_node(
            "assertion".into(),
            make_content("the speed of light is 300000 km/s"),
            0.7,
            2,
            "physics".into(),
        );

        let created = kg.detect_contradictions(n2.node_id, 20);
        // No contradiction — same numbers
        assert_eq!(created, 0);
    }

    #[test]
    fn test_get_stats() {
        let kg = make_graph_with_nodes();
        kg.add_edge(1, 2, "supports".into(), 1.0);

        Python::with_gil(|py| {
            let stats = kg.get_stats();
            let total: usize = stats["total_nodes"].extract(py).unwrap();
            assert_eq!(total, 3);
            let edges: usize = stats["total_edges"].extract(py).unwrap();
            assert_eq!(edges, 1);
        });
    }

    #[test]
    fn test_get_domain_stats() {
        let kg = KnowledgeGraph::new();
        kg.add_node(
            "assertion".into(),
            make_content("quantum entanglement qubit"),
            0.9,
            1,
            String::new(),
        );
        kg.add_node(
            "assertion".into(),
            make_content("quantum superposition"),
            0.8,
            2,
            String::new(),
        );
        kg.add_node(
            "observation".into(),
            make_content("theorem proof algebra"),
            0.7,
            3,
            String::new(),
        );

        let stats = kg.get_domain_stats();
        assert!(stats.contains_key("quantum_physics"));
        assert_eq!(stats["quantum_physics"]["count"] as usize, 2);
    }

    #[test]
    fn test_get_grounding_stats() {
        let kg = KnowledgeGraph::new();
        let n1 = kg.add_node("assertion".into(), make_content("a"), 0.9, 1, String::new());
        // Set grounding source manually
        {
            let mut g = kg.inner.write();
            if let Some(node) = g.nodes.get_mut(&n1.node_id) {
                node.grounding_source = "block_oracle".into();
            }
        }
        kg.add_node("assertion".into(), make_content("b"), 0.8, 2, String::new());

        Python::with_gil(|py| {
            let stats = kg.get_grounding_stats();
            let grounded: usize = stats["grounded_nodes"].extract(py).unwrap();
            assert_eq!(grounded, 1);
            let total: usize = stats["total_nodes"].extract(py).unwrap();
            assert_eq!(total, 2);
        });
    }

    #[test]
    fn test_reclassify_domains() {
        let kg = KnowledgeGraph::new();
        // Add a node with no domain but quantum content
        {
            let mut g = kg.inner.write();
            let mut content = HashMap::new();
            content.insert("text".into(), "qubit superposition quantum".into());
            let node = KeterNode {
                node_id: 1,
                node_type: "assertion".into(),
                content_hash: String::new(),
                content,
                confidence: 0.5,
                source_block: 0,
                timestamp: 0.0,
                domain: String::new(), // empty — needs reclassification
                last_referenced_block: 0,
                reference_count: 0,
                grounding_source: String::new(),
                edges_out: vec![],
                edges_in: vec![],
            };
            g.nodes.insert(1, node);
            g.next_id = 2;
        }

        let reclassified = kg.reclassify_domains();
        assert_eq!(reclassified, 1);

        let node = kg.get_node(1).unwrap();
        assert_eq!(node.domain, "quantum_physics");
    }

    #[test]
    fn test_node_count_edge_count() {
        let kg = make_graph_with_nodes();
        assert_eq!(kg.node_count(), 3);
        assert_eq!(kg.edge_count(), 0);

        kg.add_edge(1, 2, "supports".into(), 1.0);
        assert_eq!(kg.edge_count(), 1);
    }

    #[test]
    fn test_bulk_load() {
        let kg = KnowledgeGraph::new();

        let nodes = vec![
            KeterNode {
                node_id: 10,
                node_type: "assertion".into(),
                content_hash: "abc".into(),
                content: make_content("bulk node 1"),
                confidence: 0.9,
                source_block: 100,
                timestamp: 1000.0,
                domain: "general".into(),
                last_referenced_block: 100,
                reference_count: 0,
                grounding_source: String::new(),
                edges_out: vec![],
                edges_in: vec![],
            },
            KeterNode {
                node_id: 20,
                node_type: "observation".into(),
                content_hash: "def".into(),
                content: make_content("bulk node 2"),
                confidence: 0.8,
                source_block: 200,
                timestamp: 2000.0,
                domain: "general".into(),
                last_referenced_block: 200,
                reference_count: 0,
                grounding_source: String::new(),
                edges_out: vec![],
                edges_in: vec![],
            },
        ];

        kg.bulk_load_nodes(nodes);
        assert_eq!(kg.node_count(), 2);
        assert!(kg.get_node(10).is_some());
        assert!(kg.get_node(20).is_some());

        // Next ID should be 21 (max(10,20) + 1)
        let new = kg.add_node("assertion".into(), make_content("new"), 0.5, 0, String::new());
        assert_eq!(new.node_id, 21);
    }

    #[test]
    fn test_bulk_load_edges() {
        let kg = KnowledgeGraph::new();
        kg.add_node("assertion".into(), make_content("a"), 0.5, 0, String::new());
        kg.add_node("assertion".into(), make_content("b"), 0.5, 0, String::new());
        kg.add_node("assertion".into(), make_content("c"), 0.5, 0, String::new());

        let edges = vec![
            KeterEdge {
                from_node_id: 1,
                to_node_id: 2,
                edge_type: "supports".into(),
                weight: 1.0,
                timestamp: 0.0,
            },
            KeterEdge {
                from_node_id: 2,
                to_node_id: 3,
                edge_type: "derives".into(),
                weight: 0.8,
                timestamp: 0.0,
            },
        ];

        kg.bulk_load_edges(edges);
        assert_eq!(kg.edge_count(), 2);
        assert_eq!(kg.get_edges_from(1).len(), 1);
        assert_eq!(kg.get_edges_to(3).len(), 1);
    }

    #[test]
    fn test_classify_domain_quantum() {
        let content = make_content("qubit superposition entanglement");
        assert_eq!(classify_domain(&content), "quantum_physics");
    }

    #[test]
    fn test_classify_domain_math() {
        let content = make_content("theorem proof algebra topology");
        assert_eq!(classify_domain(&content), "mathematics");
    }

    #[test]
    fn test_classify_domain_general() {
        let content = make_content("hello world random words");
        assert_eq!(classify_domain(&content), "general");
    }

    #[test]
    fn test_classify_domain_handles_separators() {
        let content = make_content("post-quantum zero-knowledge lattice");
        // Dashes become underscores: post_quantum, zero_knowledge
        assert_eq!(classify_domain(&content), "cryptography");
    }

    #[test]
    fn test_tokenize() {
        let tokens = tokenize("Hello World! This is a test of quantum computing.");
        assert!(tokens.contains(&"hello".to_string()));
        assert!(tokens.contains(&"world".to_string()));
        assert!(tokens.contains(&"quantum".to_string()));
        assert!(tokens.contains(&"computing".to_string()));
        assert!(tokens.contains(&"test".to_string()));
        // Stop words excluded
        assert!(!tokens.contains(&"this".to_string()));
        assert!(!tokens.contains(&"is".to_string()));
        assert!(!tokens.contains(&"a".to_string()));
        assert!(!tokens.contains(&"of".to_string()));
    }

    #[test]
    fn test_tokenize_short_tokens_removed() {
        let tokens = tokenize("I am ok");
        assert!(tokens.is_empty()); // All tokens are <= 2 chars or stop words
    }

    #[test]
    fn test_extract_numbers() {
        let nums = extract_numbers("the speed is 300000 km/s or 3.14 meters");
        assert!(nums.contains("300000"));
        assert!(nums.contains("3.14"));
    }

    #[test]
    fn test_extract_numbers_no_trailing_dot() {
        let nums = extract_numbers("value is 42.");
        assert!(nums.contains("42"));
        assert!(!nums.contains("42."));
    }

    #[test]
    fn test_tfidf_index_basic() {
        let mut idx = TFIDFIndex::new();
        idx.add_node(1, &make_content("quantum entanglement experiment"));
        idx.add_node(2, &make_content("classical mechanics gravity"));

        let results = idx.query("quantum entanglement", 10);
        assert!(!results.is_empty());
        assert_eq!(results[0].0, 1); // First result should be the quantum node
    }

    #[test]
    fn test_tfidf_remove_node() {
        let mut idx = TFIDFIndex::new();
        idx.add_node(1, &make_content("quantum entanglement experiment"));
        idx.add_node(2, &make_content("classical mechanics gravity"));

        idx.remove_node(1);
        let results = idx.query("quantum entanglement", 10);
        // Should no longer find node 1
        assert!(results.is_empty() || results[0].0 != 1);
    }

    #[test]
    fn test_tfidf_stats() {
        let mut idx = TFIDFIndex::new();
        idx.add_node(1, &make_content("quantum entanglement experiment"));
        let stats = idx.get_stats();
        assert_eq!(stats["total_docs"], 1.0);
        assert!(stats["unique_terms"] > 0.0);
    }

    #[test]
    fn test_merkle_root_single_node() {
        let kg = KnowledgeGraph::new();
        kg.add_node("assertion".into(), make_content("single"), 0.5, 0, String::new());
        let root = kg.compute_knowledge_root();
        assert_eq!(root.len(), 64);
    }

    #[test]
    fn test_merkle_root_odd_nodes() {
        // Odd number of nodes — Merkle tree duplicates last leaf
        let kg = KnowledgeGraph::new();
        kg.add_node("assertion".into(), make_content("a"), 0.5, 0, String::new());
        kg.add_node("assertion".into(), make_content("b"), 0.5, 0, String::new());
        kg.add_node("assertion".into(), make_content("c"), 0.5, 0, String::new());
        let root = kg.compute_knowledge_root();
        assert_eq!(root.len(), 64);
    }

    #[test]
    fn test_thread_safety() {
        use std::sync::Arc;
        use std::thread;

        let kg = Arc::new(KnowledgeGraph::new());
        let mut handles = vec![];

        // Spawn multiple writer threads
        for i in 0..10 {
            let kg_clone = Arc::clone(&kg);
            handles.push(thread::spawn(move || {
                kg_clone.add_node(
                    "assertion".into(),
                    make_content(&format!("node {}", i)),
                    0.5,
                    i as i64,
                    String::new(),
                );
            }));
        }

        for h in handles {
            h.join().unwrap();
        }

        assert_eq!(kg.node_count(), 10);
    }

    #[test]
    fn test_concurrent_read_write() {
        use std::sync::Arc;
        use std::thread;

        let kg = Arc::new(KnowledgeGraph::new());

        // Pre-populate
        for i in 0..5 {
            kg.add_node(
                "assertion".into(),
                make_content(&format!("base node {}", i)),
                0.5,
                i,
                String::new(),
            );
        }

        let mut handles = vec![];

        // Reader threads
        for _ in 0..5 {
            let kg_clone = Arc::clone(&kg);
            handles.push(thread::spawn(move || {
                for i in 1..=5 {
                    let _ = kg_clone.get_node(i);
                    let _ = kg_clone.find_recent(10);
                }
            }));
        }

        // Writer thread
        let kg_clone = Arc::clone(&kg);
        handles.push(thread::spawn(move || {
            for i in 100..110 {
                kg_clone.add_node(
                    "observation".into(),
                    make_content(&format!("concurrent node {}", i)),
                    0.8,
                    i,
                    String::new(),
                );
            }
        }));

        for h in handles {
            h.join().unwrap();
        }

        assert_eq!(kg.node_count(), 15);
    }
}
