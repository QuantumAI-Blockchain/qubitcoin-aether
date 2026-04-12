//! In-memory KnowledgeGraph with Merkle root, TF-IDF search, adjacency index,
//! domain classification, and confidence propagation.

use crate::domain::classify_domain;
use crate::tfidf::TFIDFIndex;

pub use aether_types::{KeterEdge, KeterNode, VALID_EDGE_TYPES, VALID_NODE_TYPES};

use parking_lot::RwLock;
use pyo3::prelude::*;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

// ── Internal graph state ────────────────────────────────────────────────────

/// Interior state protected by RwLock.
pub(crate) struct GraphInner {
    pub(crate) nodes: HashMap<i64, KeterNode>,
    pub(crate) edges: Vec<KeterEdge>,
    /// node_id -> outgoing edges
    pub(crate) adj_out: HashMap<i64, Vec<KeterEdge>>,
    /// node_id -> incoming edges
    pub(crate) adj_in: HashMap<i64, Vec<KeterEdge>>,
    pub(crate) next_id: i64,
    /// Merkle root cache
    pub(crate) merkle_dirty: bool,
    pub(crate) merkle_cache: String,
    /// TF-IDF search index
    pub(crate) search_index: TFIDFIndex,
}

impl GraphInner {
    pub(crate) fn new() -> Self {
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

/// In-memory knowledge graph -- Rust-accelerated pure computation layer.
///
/// Supports CRUD operations, BFS subgraph traversal, DFS path finding,
/// Merkle root computation, TF-IDF search, domain classification,
/// confidence propagation, and contradiction detection.
///
/// Thread-safe via parking_lot::RwLock -- multiple readers, exclusive writers.
#[pyclass]
pub struct KnowledgeGraph {
    pub(crate) inner: Arc<RwLock<GraphInner>>,
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
pub fn extract_numbers(text: &str) -> HashSet<String> {
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
