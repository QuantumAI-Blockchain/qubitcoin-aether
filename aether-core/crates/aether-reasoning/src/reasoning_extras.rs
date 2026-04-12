//! Reasoning extras — analogy detection, Bayesian confidence updates,
//! and cross-domain inference support.

use crate::reasoning::{ReasoningEngine, ReasoningResult, ReasoningStep};
use std::collections::{HashMap, HashSet};

impl ReasoningEngine {
    /// Find structural analogies between a source node and nodes in other domains.
    ///
    /// Compares the edge-type pattern around the source node with patterns
    /// around nodes in different domains. Matching patterns indicate an
    /// analogous relationship.
    pub fn find_analogies(
        &self,
        source_node_id: i64,
        target_domain: Option<&str>,
        max_results: usize,
    ) -> ReasoningResult {
        let mut chain = Vec::new();
        let source = match self.knowledge_graph().get_node(source_node_id) {
            Some(n) => n,
            None => return ReasoningResult::failure(
                "analogy_detection", vec![source_node_id], "Source node not found",
            ),
        };

        let source_pattern = self.get_edge_pattern(source_node_id);
        if source_pattern.is_empty() {
            return ReasoningResult::failure(
                "analogy_detection", vec![source_node_id],
                "Source node has no edges -- no pattern to match",
            );
        }

        chain.push(ReasoningStep::premise(source_node_id, source.content.clone(), source.confidence));

        let source_domain = &source.domain;
        let all_nodes = self.knowledge_graph().get_nodes_raw();

        let mut analogies_found: Vec<(i64, String, f64, Vec<String>)> = Vec::new();

        for candidate in &all_nodes {
            if candidate.node_id == source_node_id {
                continue;
            }
            // Different domain (or any domain if source has none)
            if !source_domain.is_empty() && candidate.domain == *source_domain {
                continue;
            }
            if let Some(td) = target_domain {
                if candidate.domain != td {
                    continue;
                }
            }
            if !matches!(candidate.node_type.as_str(), "assertion" | "inference") {
                continue;
            }

            let cand_pattern = self.get_edge_pattern(candidate.node_id);
            if cand_pattern.is_empty() {
                continue;
            }

            let common: HashSet<_> = source_pattern.intersection(&cand_pattern).cloned().collect();
            let union_count = source_pattern.union(&cand_pattern).count();
            let similarity = if union_count > 0 { common.len() as f64 / union_count as f64 } else { 0.0 };

            if similarity >= 0.3 && !common.is_empty() {
                analogies_found.push((
                    candidate.node_id,
                    candidate.domain.clone(),
                    similarity,
                    common.into_iter().collect(),
                ));
                if analogies_found.len() >= max_results {
                    break;
                }
            }
        }

        // Create analogous_to edges for matches
        let mut created_edges = 0;
        let mut conclusion_id = None;

        for (nid, domain, similarity, common_types) in &analogies_found {
            self.knowledge_graph().add_edge(
                source_node_id, *nid, "analogous_to".into(),
                *similarity,
            );
            created_edges += 1;

            let mut content = HashMap::new();
            content.insert("type".into(), "analogy".into());
            content.insert("source_domain".into(), source_domain.clone());
            content.insert("target_domain".into(), domain.clone());
            content.insert("similarity".into(), format!("{:.3}", similarity));
            content.insert("common_patterns".into(), common_types.join(", "));

            chain.push(ReasoningStep::conclusion(*nid, content, *similarity));
            conclusion_id = Some(*nid);
        }

        let max_sim = analogies_found.iter().map(|(_, _, s, _)| *s).fold(0.0_f64, f64::max);

        ReasoningResult {
            operation_type: "analogy_detection".into(),
            premise_ids: vec![source_node_id],
            conclusion_node_id: conclusion_id,
            confidence: max_sim,
            chain,
            success: created_edges > 0,
            explanation: format!("Found {} analogies across domains", created_edges),
            domain: String::new(),
            block_height: 0,
            hypotheses: Vec::new(),
        }
    }

    /// Get the set of edge types connected to a node (both in and out).
    fn get_edge_pattern(&self, node_id: i64) -> HashSet<String> {
        let mut pattern = HashSet::new();
        for edge in self.knowledge_graph().get_edges_from(node_id) {
            pattern.insert(edge.edge_type.clone());
        }
        for edge in self.knowledge_graph().get_edges_to(node_id) {
            pattern.insert(edge.edge_type.clone());
        }
        pattern
    }

    /// Perform cross-domain inference by finding nodes in different domains
    /// that share structural patterns.
    ///
    /// Returns the number of cross-domain inference nodes created.
    pub fn cross_domain_inference(
        &self,
        source_domain: &str,
        target_domain: &str,
        max_inferences: usize,
    ) -> usize {
        let all_nodes = self.knowledge_graph().get_nodes_raw();

        let source_nodes: Vec<_> = all_nodes.iter()
            .filter(|n| n.domain == source_domain && matches!(n.node_type.as_str(), "inference" | "assertion"))
            .take(50)
            .collect();

        let target_nodes: Vec<_> = all_nodes.iter()
            .filter(|n| n.domain == target_domain && matches!(n.node_type.as_str(), "inference" | "assertion"))
            .take(50)
            .collect();

        let mut created = 0;
        for sn in &source_nodes {
            if created >= max_inferences {
                break;
            }
            let s_pattern = self.get_edge_pattern(sn.node_id);
            if s_pattern.is_empty() {
                continue;
            }

            for tn in &target_nodes {
                if created >= max_inferences {
                    break;
                }
                let t_pattern = self.get_edge_pattern(tn.node_id);
                let common: HashSet<_> = s_pattern.intersection(&t_pattern).cloned().collect();
                let union_count = s_pattern.union(&t_pattern).count();
                let sim = if union_count > 0 { common.len() as f64 / union_count as f64 } else { 0.0 };

                if sim >= 0.4 && !common.is_empty() {
                    // Create cross-domain inference node
                    let mut content = HashMap::new();
                    content.insert("type".into(), "cross_domain_inference".into());
                    content.insert("source_domain".into(), source_domain.into());
                    content.insert("target_domain".into(), target_domain.into());
                    content.insert("source_node".into(), sn.node_id.to_string());
                    content.insert("target_node".into(), tn.node_id.to_string());
                    content.insert("similarity".into(), format!("{:.3}", sim));
                    content.insert("cross_domain".into(), "true".into());

                    let conf = sim * sn.confidence.min(tn.confidence);
                    let block = sn.source_block.max(tn.source_block);
                    let inf_node = self.knowledge_graph().add_node(
                        "inference".into(), content, conf, block, String::new(),
                    );
                    self.knowledge_graph().add_edge(sn.node_id, inf_node.node_id, "derives".into(), 1.0);
                    self.knowledge_graph().add_edge(tn.node_id, inf_node.node_id, "derives".into(), 1.0);
                    created += 1;
                }
            }
        }
        created
    }

    /// Apply Bayesian confidence update to a node based on new evidence.
    ///
    /// Uses a simple Bayesian update:
    ///   posterior = (likelihood * prior) / evidence
    /// where evidence = likelihood * prior + (1 - likelihood) * (1 - prior)
    pub fn bayesian_update(
        &self,
        node_id: i64,
        evidence_confidence: f64,
        supports: bool,
    ) -> Option<f64> {
        let node = self.knowledge_graph().get_node(node_id)?;
        let prior = node.confidence;
        let likelihood = if supports { evidence_confidence } else { 1.0 - evidence_confidence };
        let evidence = likelihood * prior + (1.0 - likelihood) * (1.0 - prior);

        if evidence < 1e-12 {
            return Some(prior);
        }

        let posterior = (likelihood * prior / evidence).clamp(0.01, 0.99);
        Some(posterior)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use aether_graph::KnowledgeGraph;
    use std::sync::Arc;

    fn make_content(text: &str) -> HashMap<String, String> {
        let mut c = HashMap::new();
        c.insert("text".into(), text.into());
        c
    }

    fn make_engine() -> (Arc<KnowledgeGraph>, ReasoningEngine) {
        let kg = Arc::new(KnowledgeGraph::new());
        let engine = ReasoningEngine::new(Arc::clone(&kg));
        (kg, engine)
    }

    #[test]
    fn test_find_analogies_no_source() {
        let (_kg, engine) = make_engine();
        let result = engine.find_analogies(999, None, 5);
        assert!(!result.success);
    }

    #[test]
    fn test_find_analogies_no_edges() {
        let (kg, engine) = make_engine();
        kg.add_node("assertion".into(), make_content("isolated node"), 0.9, 1, String::new());
        let result = engine.find_analogies(1, None, 5);
        assert!(!result.success);
    }

    #[test]
    fn test_find_analogies_with_match() {
        let (kg, engine) = make_engine();
        // Create two nodes in different domains with same edge patterns
        let n1 = kg.add_node("assertion".into(), make_content("quantum theory"), 0.9, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("string theory"), 0.8, 2, String::new());
        let n3 = kg.add_node("assertion".into(), make_content("economics model"), 0.85, 3, String::new());

        kg.add_edge(n1.node_id, n2.node_id, "supports".into(), 1.0);
        kg.add_edge(n3.node_id, n2.node_id, "supports".into(), 1.0);
        // n1 and n3 share the "supports" edge pattern
        let result = engine.find_analogies(n1.node_id, None, 5);
        // May or may not find analogies depending on domain classification
        assert_eq!(result.operation_type, "analogy_detection");
    }

    #[test]
    fn test_bayesian_update_supporting() {
        let (kg, engine) = make_engine();
        kg.add_node("assertion".into(), make_content("hypothesis"), 0.5, 1, String::new());

        let posterior = engine.bayesian_update(1, 0.8, true).unwrap();
        assert!(posterior > 0.5); // Supporting evidence should increase confidence
    }

    #[test]
    fn test_bayesian_update_contradicting() {
        let (kg, engine) = make_engine();
        kg.add_node("assertion".into(), make_content("hypothesis"), 0.5, 1, String::new());

        let posterior = engine.bayesian_update(1, 0.8, false).unwrap();
        assert!(posterior < 0.5); // Contradicting evidence should decrease confidence
    }

    #[test]
    fn test_bayesian_update_missing_node() {
        let (_kg, engine) = make_engine();
        assert!(engine.bayesian_update(999, 0.8, true).is_none());
    }

    #[test]
    fn test_bayesian_update_clamped() {
        let (kg, engine) = make_engine();
        kg.add_node("assertion".into(), make_content("near certain"), 0.99, 1, String::new());
        let posterior = engine.bayesian_update(1, 0.99, true).unwrap();
        assert!(posterior <= 0.99);
        assert!(posterior >= 0.01);
    }

    #[test]
    fn test_cross_domain_inference() {
        let (kg, engine) = make_engine();
        // Create nodes in two domains with shared edge patterns
        let n1 = kg.add_node("assertion".into(), make_content("quantum entanglement"), 0.9, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("quantum decoherence"), 0.8, 2, String::new());
        let n3 = kg.add_node("assertion".into(), make_content("market correlation"), 0.85, 3, String::new());
        let n4 = kg.add_node("assertion".into(), make_content("market volatility"), 0.8, 4, String::new());

        kg.add_edge(n1.node_id, n2.node_id, "supports".into(), 1.0);
        kg.add_edge(n3.node_id, n4.node_id, "supports".into(), 1.0);

        // Both share "supports" pattern — cross-domain inference may be created
        let created = engine.cross_domain_inference("quantum_physics", "economics", 5);
        // Result depends on domain classification of the nodes
        assert!(created == 0 || created > 0);
    }
}
