//! KeterEdge — a directed edge between two KeterNodes in the knowledge graph.
//!
//! Edge types encode semantic relationships:
//! - supports: evidence for a claim
//! - contradicts: evidence against a claim
//! - derives: logical derivation
//! - requires: dependency
//! - refines: specialization
//! - causes: causal relationship
//! - abstracts: generalization
//! - analogous_to: structural similarity

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

/// Valid edge types.
pub const VALID_EDGE_TYPES: &[&str] = &[
    "supports",
    "contradicts",
    "derives",
    "requires",
    "refines",
    "causes",
    "correlates",
    "abstracts",
    "analogous_to",
];

/// A directed edge between two KeterNodes.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KeterEdge {
    pub from_node_id: i64,
    pub to_node_id: i64,
    pub edge_type: String,
    pub weight: f64,
    pub timestamp: f64,
}

#[pymethods]
impl KeterEdge {
    #[new]
    #[pyo3(signature = (from_node_id, to_node_id, edge_type = "supports".to_string(), weight = 1.0, timestamp = 0.0))]
    pub fn new(
        from_node_id: i64,
        to_node_id: i64,
        edge_type: String,
        weight: f64,
        timestamp: f64,
    ) -> Self {
        KeterEdge {
            from_node_id,
            to_node_id,
            edge_type,
            weight,
            timestamp,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "KeterEdge(from={}, to={}, type='{}', weight={:.4})",
            self.from_node_id, self.to_node_id, self.edge_type, self.weight
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_edge() {
        let edge = KeterEdge::new(1, 2, "supports".into(), 1.0, 0.0);
        assert_eq!(edge.from_node_id, 1);
        assert_eq!(edge.to_node_id, 2);
        assert_eq!(edge.edge_type, "supports");
        assert!((edge.weight - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_contradicts_edge() {
        let edge = KeterEdge::new(3, 4, "contradicts".into(), 0.7, 12345.0);
        assert_eq!(edge.edge_type, "contradicts");
        assert!((edge.weight - 0.7).abs() < f64::EPSILON);
        assert!((edge.timestamp - 12345.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_clone() {
        let edge = KeterEdge::new(1, 2, "derives".into(), 0.9, 100.0);
        let cloned = edge.clone();
        assert_eq!(cloned.from_node_id, edge.from_node_id);
        assert_eq!(cloned.to_node_id, edge.to_node_id);
        assert_eq!(cloned.edge_type, edge.edge_type);
    }
}
