//! KnowledgeGraph -- in-memory knowledge graph with Merkle root, TF-IDF search,
//! adjacency index, domain classification, and confidence propagation.
//!
//! This is the Rust-accelerated pure computation layer. Database persistence
//! remains in the Python wrapper -- this module handles the hot-path operations:
//! - O(1) node/edge lookup via HashMap + adjacency lists
//! - Cached Merkle root (SHA-256, invalidated on mutation)
//! - Built-in TF-IDF search (no external dependency)
//! - Thread-safe via parking_lot::RwLock
//!
//! Additionally provides `DbKnowledgeGraph` for write-through DB-backed operation
//! with an in-memory LRU hot cache.

pub mod domain;
pub mod tfidf;
pub mod graph;
pub mod db_graph;

// Re-export primary types for backwards compatibility
pub use aether_types::{KeterNode, KeterEdge, VALID_NODE_TYPES, VALID_EDGE_TYPES};
pub use graph::KnowledgeGraph;
pub use db_graph::{DbKnowledgeGraph, GraphStats};
pub use domain::{domain_keywords, classify_domain};
pub use tfidf::{TFIDFIndex, tokenize, extract_text, STOP_WORDS};

// Re-export extract_numbers from graph module
pub use graph::extract_numbers;

// ── Unit tests ──────────────────────────────────────────────────────────────
// All tests are kept here to preserve the original test module structure.

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

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
        // Call again -- should use cache (same result)
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
        // No contradiction -- same numbers
        assert_eq!(created, 0);
    }

    #[test]
    fn test_get_stats() {
        let kg = make_graph_with_nodes();
        kg.add_edge(1, 2, "supports".into(), 1.0);

        pyo3::Python::with_gil(|py| {
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

        pyo3::Python::with_gil(|py| {
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
                domain: String::new(), // empty -- needs reclassification
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
        // Odd number of nodes -- Merkle tree duplicates last leaf
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
