//! KeterNode — a knowledge node in the Aether Tree.
//!
//! Named after Keter (Crown) in the Kabbalistic Tree of Life — the highest sephira.
//! Each node represents a piece of verified knowledge with content, confidence,
//! source block provenance, domain classification, and graph connectivity.

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;

/// Valid node types for KeterNode.
pub const VALID_NODE_TYPES: &[&str] = &[
    "assertion",
    "observation",
    "inference",
    "axiom",
    "prediction",
    "meta_observation",
];

/// A knowledge node in the Aether Tree.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KeterNode {
    pub node_id: i64,
    pub node_type: String,
    pub content_hash: String,
    pub content: HashMap<String, String>,
    pub confidence: f64,
    pub source_block: i64,
    pub timestamp: f64,
    pub domain: String,
    pub last_referenced_block: i64,
    pub reference_count: i64,
    pub grounding_source: String,
    pub edges_out: Vec<i64>,
    pub edges_in: Vec<i64>,
}

#[pymethods]
impl KeterNode {
    /// Create a new KeterNode with all fields configurable.
    #[new]
    #[pyo3(signature = (
        node_id = 0,
        node_type = "assertion".to_string(),
        content_hash = String::new(),
        content = HashMap::new(),
        confidence = 0.5,
        source_block = 0,
        timestamp = 0.0,
        domain = String::new(),
        last_referenced_block = 0,
        reference_count = 0,
        grounding_source = String::new(),
        edges_out = vec![],
        edges_in = vec![],
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        node_id: i64,
        node_type: String,
        content_hash: String,
        content: HashMap<String, String>,
        confidence: f64,
        source_block: i64,
        timestamp: f64,
        domain: String,
        last_referenced_block: i64,
        reference_count: i64,
        grounding_source: String,
        edges_out: Vec<i64>,
        edges_in: Vec<i64>,
    ) -> Self {
        KeterNode {
            node_id,
            node_type,
            content_hash,
            content,
            confidence,
            source_block,
            timestamp,
            domain,
            last_referenced_block,
            reference_count,
            grounding_source,
            edges_out,
            edges_in,
        }
    }

    /// Return confidence adjusted for time-decay.
    ///
    /// Decay is based on blocks since last reference (or creation if never
    /// referenced). Axioms never decay. Floor defaults to 0.3.
    #[pyo3(signature = (current_block = 0, halflife = 10000.0, floor = 0.3))]
    pub fn effective_confidence(&self, current_block: i64, halflife: f64, floor: f64) -> f64 {
        if self.node_type == "axiom" || current_block <= 0 {
            return self.confidence;
        }
        let ref_block = if self.last_referenced_block > 0 {
            self.last_referenced_block
        } else {
            self.source_block
        };
        let age = (current_block - ref_block).max(0) as f64;
        let decay = (1.0 - age / halflife).max(floor);
        self.confidence * decay
    }

    /// Compute SHA-256 hash of the node's content for deduplication and Merkle tree.
    pub fn calculate_hash(&self) -> String {
        // Deterministic JSON: sort keys
        let mut content_pairs: Vec<(&String, &String)> = self.content.iter().collect();
        content_pairs.sort_by_key(|(k, _)| *k);
        let content_json = content_pairs
            .iter()
            .map(|(k, v)| format!("\"{}\": \"{}\"", escape_json(k), escape_json(v)))
            .collect::<Vec<_>>()
            .join(", ");

        // Match Python: json.dumps({'type': ..., 'content': ..., 'source_block': ...}, sort_keys=True)
        let data = format!(
            "{{\"content\": {{{}}}, \"source_block\": {}, \"type\": \"{}\"}}",
            content_json, self.source_block, self.node_type
        );

        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Convert to a dict, excluding graph links (edges_out, edges_in).
    pub fn to_dict(&self) -> HashMap<String, PyObject> {
        Python::with_gil(|py| {
            let mut d: HashMap<String, PyObject> = HashMap::new();
            d.insert("node_id".into(), self.node_id.into_pyobject(py).unwrap().into());
            d.insert("node_type".into(), self.node_type.clone().into_pyobject(py).unwrap().into());
            d.insert(
                "content_hash".into(),
                self.content_hash.clone().into_pyobject(py).unwrap().into(),
            );
            d.insert("content".into(), self.content.clone().into_pyobject(py).unwrap().into());
            d.insert("confidence".into(), self.confidence.into_pyobject(py).unwrap().into());
            d.insert("source_block".into(), self.source_block.into_pyobject(py).unwrap().into());
            d.insert("timestamp".into(), self.timestamp.into_pyobject(py).unwrap().into());
            d.insert("domain".into(), self.domain.clone().into_pyobject(py).unwrap().into());
            d.insert(
                "last_referenced_block".into(),
                self.last_referenced_block.into_pyobject(py).unwrap().into(),
            );
            d.insert(
                "reference_count".into(),
                self.reference_count.into_pyobject(py).unwrap().into(),
            );
            d.insert(
                "grounding_source".into(),
                self.grounding_source.clone().into_pyobject(py).unwrap().into(),
            );
            d
        })
    }

    fn __repr__(&self) -> String {
        format!(
            "KeterNode(id={}, type='{}', confidence={:.4}, domain='{}', block={})",
            self.node_id, self.node_type, self.confidence, self.domain, self.source_block
        )
    }
}

/// Escape special JSON characters in a string.
fn escape_json(s: &str) -> String {
    s.replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_node() {
        let node = KeterNode::new(
            0,
            "assertion".into(),
            String::new(),
            HashMap::new(),
            0.5,
            0,
            0.0,
            String::new(),
            0,
            0,
            String::new(),
            vec![],
            vec![],
        );
        assert_eq!(node.node_id, 0);
        assert_eq!(node.node_type, "assertion");
        assert!((node.confidence - 0.5).abs() < f64::EPSILON);
        assert!(node.edges_out.is_empty());
        assert!(node.edges_in.is_empty());
    }

    #[test]
    fn test_calculate_hash_deterministic() {
        let mut content = HashMap::new();
        content.insert("text".into(), "quantum entanglement".into());
        content.insert("subject".into(), "physics".into());

        let node = KeterNode::new(
            1,
            "observation".into(),
            String::new(),
            content.clone(),
            0.8,
            100,
            1000.0,
            "quantum_physics".into(),
            100,
            0,
            String::new(),
            vec![],
            vec![],
        );

        let h1 = node.calculate_hash();
        let h2 = node.calculate_hash();
        assert_eq!(h1, h2);
        assert_eq!(h1.len(), 64); // SHA-256 hex
    }

    #[test]
    fn test_effective_confidence_axiom_no_decay() {
        let node = KeterNode::new(
            1,
            "axiom".into(),
            String::new(),
            HashMap::new(),
            0.95,
            0,
            0.0,
            String::new(),
            0,
            0,
            String::new(),
            vec![],
            vec![],
        );
        // Axioms never decay
        let eff = node.effective_confidence(100_000, 10_000.0, 0.3);
        assert!((eff - 0.95).abs() < f64::EPSILON);
    }

    #[test]
    fn test_effective_confidence_decays() {
        let node = KeterNode::new(
            1,
            "assertion".into(),
            String::new(),
            HashMap::new(),
            1.0,
            0,
            0.0,
            String::new(),
            0,
            0,
            String::new(),
            vec![],
            vec![],
        );
        // After halflife blocks, decay = max(floor, 1.0 - age/halflife) = max(0.3, 0.0) = 0.3
        let eff = node.effective_confidence(10_000, 10_000.0, 0.3);
        assert!((eff - 0.3).abs() < f64::EPSILON);
    }

    #[test]
    fn test_effective_confidence_floor() {
        let node = KeterNode::new(
            1,
            "assertion".into(),
            String::new(),
            HashMap::new(),
            1.0,
            0,
            0.0,
            String::new(),
            0,
            0,
            String::new(),
            vec![],
            vec![],
        );
        // Way past halflife — floor should apply
        let eff = node.effective_confidence(999_999, 10_000.0, 0.3);
        assert!((eff - 0.3).abs() < f64::EPSILON);
    }

    #[test]
    fn test_effective_confidence_zero_current_block() {
        let node = KeterNode::new(
            1,
            "assertion".into(),
            String::new(),
            HashMap::new(),
            0.8,
            0,
            0.0,
            String::new(),
            0,
            0,
            String::new(),
            vec![],
            vec![],
        );
        // current_block <= 0 means no decay
        let eff = node.effective_confidence(0, 10_000.0, 0.3);
        assert!((eff - 0.8).abs() < f64::EPSILON);
    }
}
