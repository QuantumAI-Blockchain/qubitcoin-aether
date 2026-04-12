//! Knowledge Seeder -- Seeds the knowledge graph with genesis knowledge.
//!
//! Called once at node startup or genesis to bootstrap the tree with verified
//! facts across all domains. Idempotent: checks for existing seeds.

use crate::genesis_knowledge::{CROSS_DOMAIN_LINKS, domains, facts_for_domain};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A seed node ready to be inserted into the knowledge graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeedNode {
    pub node_type: String,
    pub content: HashMap<String, serde_json::Value>,
    pub confidence: f64,
    pub domain: String,
    pub grounding_source: String,
}

/// A seed edge connecting two nodes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeedEdge {
    /// Index of source node in the seeds vector
    pub source_idx: usize,
    /// Index of target node in the seeds vector
    pub target_idx: usize,
    pub edge_type: String,
}

/// Result of a seeding operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeedResult {
    pub nodes_created: usize,
    pub edges_created: usize,
    pub domains_seeded: usize,
}

/// Knowledge Seeder: generates seed nodes and edges for the knowledge graph.
pub struct KnowledgeSeeder;

impl KnowledgeSeeder {
    /// Generate all genesis knowledge seed nodes.
    ///
    /// Returns a vector of seed nodes ready for insertion into the graph.
    /// Does NOT insert them -- the caller is responsible for graph interaction.
    pub fn seed_genesis_knowledge() -> (Vec<SeedNode>, Vec<SeedEdge>) {
        let mut nodes = Vec::new();
        let mut edges = Vec::new();
        let mut domain_ranges: HashMap<&str, (usize, usize)> = HashMap::new();

        for domain in domains() {
            let start_idx = nodes.len();
            let facts = facts_for_domain(domain);

            for fact in facts {
                let mut content = HashMap::new();
                content.insert("type".into(), serde_json::Value::String("genesis_knowledge".into()));
                content.insert("text".into(), serde_json::Value::String(fact.text.to_string()));
                content.insert("domain".into(), serde_json::Value::String(domain.to_string()));
                content.insert("source".into(), serde_json::Value::String("genesis_seed".into()));

                nodes.push(SeedNode {
                    node_type: "axiom".into(),
                    content,
                    confidence: fact.confidence,
                    domain: domain.to_string(),
                    grounding_source: "genesis_seed".into(),
                });
            }

            let end_idx = nodes.len();
            domain_ranges.insert(domain, (start_idx, end_idx));

            // Intra-domain sequential edges
            for i in (start_idx + 1)..end_idx {
                edges.push(SeedEdge {
                    source_idx: i - 1,
                    target_idx: i,
                    edge_type: "supports".into(),
                });
            }
        }

        // Cross-domain edges
        for (src_domain, dst_domain, edge_type) in CROSS_DOMAIN_LINKS {
            if let (Some(&(s_start, s_end)), Some(&(d_start, _d_end))) =
                (domain_ranges.get(src_domain), domain_ranges.get(dst_domain))
            {
                if s_start < s_end && d_start < nodes.len() {
                    // First of src -> first of dst
                    edges.push(SeedEdge {
                        source_idx: s_start,
                        target_idx: d_start,
                        edge_type: edge_type.to_string(),
                    });
                    // Last of src -> first of dst
                    if s_end > s_start + 1 {
                        edges.push(SeedEdge {
                            source_idx: s_end - 1,
                            target_idx: d_start,
                            edge_type: edge_type.to_string(),
                        });
                    }
                }
            }
        }

        // Add seed marker node
        let mut marker_content = HashMap::new();
        marker_content.insert("type".into(), serde_json::Value::String("genesis_seed_marker".into()));
        marker_content.insert("text".into(), serde_json::Value::String("Aether Tree genesis knowledge seeded".into()));
        marker_content.insert("nodes_created".into(), serde_json::json!(nodes.len()));
        nodes.push(SeedNode {
            node_type: "axiom".into(),
            content: marker_content,
            confidence: 1.0,
            domain: "ai_ml".into(),
            grounding_source: "genesis_seed".into(),
        });

        (nodes, edges)
    }

    /// Generate seed nodes for a specific domain only.
    pub fn seed_domain_knowledge(domain: &str) -> Vec<SeedNode> {
        let facts = facts_for_domain(domain);
        facts.into_iter().map(|fact| {
            let mut content = HashMap::new();
            content.insert("type".into(), serde_json::Value::String("genesis_knowledge".into()));
            content.insert("text".into(), serde_json::Value::String(fact.text.to_string()));
            content.insert("domain".into(), serde_json::Value::String(domain.to_string()));
            content.insert("source".into(), serde_json::Value::String("genesis_seed".into()));

            SeedNode {
                node_type: "axiom".into(),
                content,
                confidence: fact.confidence,
                domain: domain.to_string(),
                grounding_source: "genesis_seed".into(),
            }
        }).collect()
    }

    /// Get statistics about the genesis knowledge.
    pub fn stats() -> SeedResult {
        let (nodes, edges) = Self::seed_genesis_knowledge();
        SeedResult {
            nodes_created: nodes.len(),
            edges_created: edges.len(),
            domains_seeded: domains().len(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_seed_genesis_knowledge() {
        let (nodes, edges) = KnowledgeSeeder::seed_genesis_knowledge();
        assert!(nodes.len() >= 90, "expected >= 90 seed nodes, got {}", nodes.len());
        assert!(edges.len() > 50);
        // Check marker node exists
        let marker = nodes.last().unwrap();
        assert_eq!(
            marker.content.get("type").and_then(|v| v.as_str()),
            Some("genesis_seed_marker")
        );
    }

    #[test]
    fn test_seed_domain_knowledge() {
        let qp = KnowledgeSeeder::seed_domain_knowledge("quantum_physics");
        assert!(qp.len() >= 15);
        for node in &qp {
            assert_eq!(node.domain, "quantum_physics");
            assert_eq!(node.node_type, "axiom");
            assert!(node.confidence > 0.8);
        }
    }

    #[test]
    fn test_seed_unknown_domain() {
        let unknown = KnowledgeSeeder::seed_domain_knowledge("nonexistent");
        assert!(unknown.is_empty());
    }

    #[test]
    fn test_stats() {
        let stats = KnowledgeSeeder::stats();
        assert!(stats.nodes_created >= 90, "expected >= 90 nodes created, got {}", stats.nodes_created);
        assert!(stats.edges_created > 30);
        assert!(stats.domains_seeded >= 10);
    }
}
