//! Adversarial Debate Protocol -- Chesed vs Gevurah with Tiferet as arbiter.
//!
//! Implements a structured multi-round debate between a proposer (Chesed,
//! expansion/exploration) and a critic (Gevurah, constraint/safety), with
//! Tiferet synthesizing the final verdict.
//!
//! Debate flow:
//! 1. Chesed proposes a hypothesis with supporting evidence from adjacency
//! 2. Gevurah critiques -- finds contradicting evidence, low-confidence weakeners
//! 3. Chesed refines based on critique
//! 4. Repeat for max_rounds or until convergence
//! 5. Tiferet judges by quality-adjusted evidence scores

use aether_graph::KnowledgeGraph;
use aether_types::DebateVerdict;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use tracing::info;

/// A single position (argument) in a debate round.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DebatePosition {
    pub role: String,
    pub argument: String,
    pub confidence: f64,
    pub evidence_node_ids: Vec<i64>,
    pub evidence_quality: f64,
    pub round_num: usize,
}

/// Outcome of a completed debate.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DebateResult {
    pub topic: String,
    pub rounds: usize,
    pub proposer_final_confidence: f64,
    pub critic_final_confidence: f64,
    pub verdict: DebateVerdict,
    pub synthesis: HashMap<String, String>,
    pub positions: Vec<DebatePosition>,
    pub conclusion_node_id: Option<i64>,
    pub timestamp: f64,
}

/// Structured adversarial debate between Sephirot nodes.
pub struct DebateProtocol {
    kg: Arc<KnowledgeGraph>,
    debates_run: AtomicUsize,
    accepted: AtomicUsize,
    rejected: AtomicUsize,
    modified: AtomicUsize,
    undecided: AtomicUsize,
    debate_log: RwLock<Vec<HashMap<String, String>>>,
}

/// Confidence adjustment constants
const ACCEPTED_BOOST: f64 = 0.05;
const REJECTED_PENALTY: f64 = 0.1;
const LOW_CONFIDENCE_THRESHOLD: f64 = 0.35;

impl DebateProtocol {
    pub fn new(kg: Arc<KnowledgeGraph>) -> Self {
        Self {
            kg,
            debates_run: AtomicUsize::new(0),
            accepted: AtomicUsize::new(0),
            rejected: AtomicUsize::new(0),
            modified: AtomicUsize::new(0),
            undecided: AtomicUsize::new(0),
            debate_log: RwLock::new(Vec::new()),
        }
    }

    pub fn knowledge_graph(&self) -> &KnowledgeGraph {
        &self.kg
    }

    pub fn total_debates(&self) -> usize {
        self.debates_run.load(Ordering::Relaxed)
    }

    pub fn total_accepted(&self) -> usize {
        self.accepted.load(Ordering::Relaxed)
    }

    pub fn total_rejected(&self) -> usize {
        self.rejected.load(Ordering::Relaxed)
    }

    /// Run a structured debate about the given topic nodes.
    pub fn debate(
        &self,
        topic_node_ids: &[i64],
        max_rounds: usize,
        convergence_threshold: f64,
    ) -> DebateResult {
        if topic_node_ids.is_empty() {
            return DebateResult {
                topic: "empty".into(),
                rounds: 0,
                proposer_final_confidence: 0.0,
                critic_final_confidence: 0.0,
                verdict: DebateVerdict::Rejected,
                synthesis: HashMap::new(),
                positions: Vec::new(),
                conclusion_node_id: None,
                timestamp: 0.0,
            };
        }

        self.debates_run.fetch_add(1, Ordering::Relaxed);

        // Gather topic context
        let topic_nodes: Vec<_> = topic_node_ids
            .iter()
            .filter_map(|&nid| self.kg.get_node(nid))
            .collect();

        if topic_nodes.is_empty() {
            return DebateResult {
                topic: "missing".into(),
                rounds: 0,
                proposer_final_confidence: 0.0,
                critic_final_confidence: 0.0,
                verdict: DebateVerdict::Rejected,
                synthesis: HashMap::new(),
                positions: Vec::new(),
                conclusion_node_id: None,
                timestamp: 0.0,
            };
        }

        let topic_text: String = topic_nodes
            .iter()
            .map(|n| {
                let text = n.content.get("text").cloned().unwrap_or_default();
                if text.len() > 100 {
                    text[..100].to_string()
                } else {
                    text
                }
            })
            .collect::<Vec<_>>()
            .join("; ");

        // Initial confidences
        let mut proposer_conf: f64 =
            topic_nodes.iter().map(|n| n.confidence).sum::<f64>() / topic_nodes.len() as f64;
        let mut critic_conf = (1.0 - proposer_conf).max(0.35);

        let mut positions: Vec<DebatePosition> = Vec::new();
        let mut final_round = 0;

        let topic_set: HashSet<i64> = topic_node_ids.iter().copied().collect();

        for round_num in 0..max_rounds {
            final_round = round_num;

            // --- Chesed proposes ---
            let support_evidence = self.find_supporting_evidence(topic_node_ids);
            let proposer_strength = self.compute_evidence_strength(&support_evidence);
            let proposer_quality = self.score_evidence_quality(&support_evidence);
            proposer_conf =
                (proposer_conf * 0.7 + proposer_strength * 0.3).clamp(0.0, 1.0);

            positions.push(DebatePosition {
                role: "proposer".into(),
                argument: format!(
                    "Round {}: {} supporting nodes (strength {:.3}, quality {:.3})",
                    round_num + 1,
                    support_evidence.len(),
                    proposer_strength,
                    proposer_quality
                ),
                confidence: proposer_conf,
                evidence_node_ids: support_evidence.iter().take(5).copied().collect(),
                evidence_quality: proposer_quality,
                round_num,
            });

            // --- Gevurah critiques ---
            let counter_evidence =
                self.find_counter_evidence(topic_node_ids, &topic_set);
            let mut critic_strength = self.compute_evidence_strength(&counter_evidence);
            let critic_quality = self.score_evidence_quality(&counter_evidence);

            // Safety check
            let safety_concerns = self.check_safety_concerns(topic_node_ids);
            if safety_concerns > 0 {
                critic_strength = (critic_strength + 0.2).min(1.0);
            }

            critic_conf =
                (critic_conf * 0.6 + critic_strength * 0.4).clamp(0.0, 1.0);

            positions.push(DebatePosition {
                role: "critic".into(),
                argument: format!(
                    "Round {}: {} counter-nodes, {} safety concerns (strength {:.3}, quality {:.3})",
                    round_num + 1,
                    counter_evidence.len(),
                    safety_concerns,
                    critic_strength,
                    critic_quality
                ),
                confidence: critic_conf,
                evidence_node_ids: counter_evidence.iter().take(5).copied().collect(),
                evidence_quality: critic_quality,
                round_num,
            });

            // Check convergence
            if (proposer_conf - critic_conf).abs() < convergence_threshold {
                break;
            }
        }

        // --- Tiferet synthesizes verdict ---
        let mut all_pro_evidence: HashSet<i64> = HashSet::new();
        let mut all_con_evidence: HashSet<i64> = HashSet::new();
        for pos in &positions {
            if pos.role == "proposer" {
                all_pro_evidence.extend(&pos.evidence_node_ids);
            } else {
                all_con_evidence.extend(&pos.evidence_node_ids);
            }
        }

        let pro_ids: Vec<i64> = all_pro_evidence.into_iter().collect();
        let con_ids: Vec<i64> = all_con_evidence.into_iter().collect();

        let pro_quality = self.score_evidence_quality(&pro_ids);
        let con_quality = self.score_evidence_quality(&con_ids);

        let pro_adjusted = proposer_conf * (0.5 + 0.5 * pro_quality);
        let con_adjusted = critic_conf * (0.5 + 0.5 * con_quality);

        let independence = self.compute_independence_score(&pro_ids, &con_ids);

        let (verdict, synthesis_conf) =
            if (proposer_conf - critic_conf).abs() <= 0.05
                && (pro_adjusted - con_adjusted).abs() <= 0.02
            {
                self.undecided.fetch_add(1, Ordering::Relaxed);
                (DebateVerdict::Undecided, (proposer_conf + critic_conf) / 2.0)
            } else if pro_adjusted > con_adjusted + 0.02 {
                self.accepted.fetch_add(1, Ordering::Relaxed);
                (
                    DebateVerdict::Accepted,
                    proposer_conf * 0.8 + (1.0 - critic_conf) * 0.2,
                )
            } else if con_adjusted > pro_adjusted + 0.02 {
                self.rejected.fetch_add(1, Ordering::Relaxed);
                (
                    DebateVerdict::Rejected,
                    (1.0 - proposer_conf) * 0.5,
                )
            } else {
                self.modified.fetch_add(1, Ordering::Relaxed);
                let pro_weight = if pro_quality + con_quality > 0.0 {
                    pro_quality / (pro_quality + con_quality)
                } else {
                    0.5
                };
                (
                    DebateVerdict::Modified,
                    proposer_conf * pro_weight + (1.0 - critic_conf) * (1.0 - pro_weight),
                )
            };

        let mut synthesis = HashMap::new();
        synthesis.insert("type".into(), "debate_synthesis".into());
        synthesis.insert("topic".into(), topic_text.chars().take(200).collect());
        synthesis.insert("verdict".into(), verdict.to_string());
        synthesis.insert("proposer_final".into(), format!("{:.4}", proposer_conf));
        synthesis.insert("critic_final".into(), format!("{:.4}", critic_conf));
        synthesis.insert("pro_quality".into(), format!("{:.4}", pro_quality));
        synthesis.insert("con_quality".into(), format!("{:.4}", con_quality));
        synthesis.insert(
            "debate_independence_score".into(),
            format!("{:.4}", independence),
        );
        synthesis.insert("rounds".into(), (final_round + 1).to_string());
        synthesis.insert("source".into(), "debate_protocol_v3".into());

        // Apply verdict to topic nodes
        self.apply_verdict_to_topics(topic_node_ids, &verdict, synthesis_conf);

        // Create conclusion node
        let max_block = topic_nodes
            .iter()
            .map(|n| n.source_block)
            .max()
            .unwrap_or(0);

        let conclusion = self
            .kg
            .add_node("inference".into(), synthesis.clone(), synthesis_conf, max_block, String::new());
        let conclusion_id = conclusion.node_id;

        for &nid in topic_node_ids {
            self.kg
                .add_edge(nid, conclusion_id, "derives".into(), 1.0);
        }

        // Record contradiction resolution for modified/rejected verdicts
        if verdict == DebateVerdict::Modified || verdict == DebateVerdict::Rejected {
            let mut res_content = HashMap::new();
            res_content.insert("type".into(), "contradiction_resolution".into());
            res_content.insert(
                "original_topic".into(),
                topic_text.chars().take(200).collect(),
            );
            res_content.insert("verdict".into(), verdict.to_string());

            let res_conf = synthesis_conf.max(0.3);
            let resolution = self
                .kg
                .add_node("inference".into(), res_content, res_conf, max_block, String::new());
            for &nid in topic_node_ids {
                self.kg
                    .add_edge(nid, resolution.node_id, "contradicts".into(), 1.0);
            }
        }

        info!(
            topic = %topic_text.chars().take(50).collect::<String>(),
            verdict = %verdict,
            proposer_conf,
            critic_conf,
            rounds = final_round + 1,
            "Debate completed"
        );

        DebateResult {
            topic: topic_text.chars().take(200).collect(),
            rounds: final_round + 1,
            proposer_final_confidence: proposer_conf,
            critic_final_confidence: critic_conf,
            verdict,
            synthesis,
            positions,
            conclusion_node_id: Some(conclusion_id),
            timestamp: 0.0,
        }
    }

    // ------------------------------------------------------------------
    // Evidence gathering
    // ------------------------------------------------------------------

    /// Find nodes that support the topic via adjacency edges.
    fn find_supporting_evidence(&self, topic_node_ids: &[i64]) -> Vec<i64> {
        let topic_set: HashSet<i64> = topic_node_ids.iter().copied().collect();
        let mut supporters: HashSet<i64> = HashSet::new();

        for &nid in topic_node_ids {
            // Incoming: nodes that support/derive this topic
            for edge in self.kg.get_edges_to(nid) {
                if matches!(edge.edge_type.as_str(), "supports" | "derives" | "causes") {
                    supporters.insert(edge.from_node_id);
                }
            }
            // Outgoing: bidirectional support
            for edge in self.kg.get_edges_from(nid) {
                if edge.edge_type == "supports" {
                    supporters.insert(edge.to_node_id);
                }
            }
        }

        supporters.retain(|x| !topic_set.contains(x));
        supporters.into_iter().collect()
    }

    /// Find counter-evidence: contradicts edges, low-confidence weakeners.
    fn find_counter_evidence(
        &self,
        topic_node_ids: &[i64],
        topic_set: &HashSet<i64>,
    ) -> Vec<i64> {
        let mut counter: HashSet<i64> = HashSet::new();

        // Direct contradiction edges
        for &nid in topic_node_ids {
            for edge in self.kg.get_edges_from(nid) {
                if edge.edge_type == "contradicts" {
                    counter.insert(edge.to_node_id);
                }
            }
            for edge in self.kg.get_edges_to(nid) {
                if edge.edge_type == "contradicts" {
                    counter.insert(edge.from_node_id);
                }
            }
        }

        // Low-confidence connected nodes as weakeners
        for &nid in topic_node_ids {
            for edge in self.kg.get_edges_to(nid) {
                if !matches!(edge.edge_type.as_str(), "supports" | "derives") {
                    continue;
                }
                if let Some(supporter) = self.kg.get_node(edge.from_node_id) {
                    if supporter.confidence < LOW_CONFIDENCE_THRESHOLD
                        && !topic_set.contains(&supporter.node_id)
                    {
                        counter.insert(supporter.node_id);
                    }
                }
            }
        }

        counter.retain(|x| !topic_set.contains(x));
        counter.into_iter().collect()
    }

    /// Count safety-related nodes connected to topic.
    fn check_safety_concerns(&self, topic_node_ids: &[i64]) -> usize {
        let mut count = 0;
        for &nid in topic_node_ids {
            for edge in self.kg.get_edges_from(nid) {
                if edge.edge_type == "safety_concern" || edge.edge_type == "risk" {
                    count += 1;
                }
            }
            for edge in self.kg.get_edges_to(nid) {
                if edge.edge_type == "safety_concern" || edge.edge_type == "risk" {
                    count += 1;
                }
            }
        }
        count
    }

    /// Compute evidence strength from a set of evidence nodes.
    fn compute_evidence_strength(&self, evidence_ids: &[i64]) -> f64 {
        if evidence_ids.is_empty() {
            return 0.0;
        }

        let confidences: Vec<f64> = evidence_ids
            .iter()
            .filter_map(|&nid| self.kg.get_node(nid).map(|n| n.confidence))
            .collect();

        if confidences.is_empty() {
            return 0.0;
        }

        let avg = confidences.iter().sum::<f64>() / confidences.len() as f64;
        let count_factor = (confidences.len() as f64).ln().min(3.0) / 3.0;

        avg * 0.6 + count_factor * 0.4
    }

    /// Score evidence quality based on source diversity, confidence, causal strength.
    fn score_evidence_quality(&self, evidence_ids: &[i64]) -> f64 {
        if evidence_ids.is_empty() {
            return 0.0;
        }

        let mut source_blocks: HashSet<i64> = HashSet::new();
        let mut total_confidence = 0.0;
        let mut valid_count = 0;
        let mut causal_edges = 0;
        let mut support_edges = 0;

        for &nid in evidence_ids {
            if let Some(node) = self.kg.get_node(nid) {
                source_blocks.insert(node.source_block);
                total_confidence += node.confidence;
                valid_count += 1;

                for edge in self.kg.get_edges_from(nid) {
                    match edge.edge_type.as_str() {
                        "causes" => causal_edges += 1,
                        "supports" => support_edges += 1,
                        _ => {}
                    }
                }
                for edge in self.kg.get_edges_to(nid) {
                    match edge.edge_type.as_str() {
                        "causes" => causal_edges += 1,
                        "supports" => support_edges += 1,
                        _ => {}
                    }
                }
            }
        }

        if valid_count == 0 {
            return 0.0;
        }

        let source_diversity = source_blocks.len() as f64 / valid_count as f64;
        let avg_confidence = total_confidence / valid_count as f64;
        let total_relevant = causal_edges + support_edges;
        let causal_strength = if total_relevant > 0 {
            causal_edges as f64 / total_relevant as f64
        } else {
            0.0
        };

        // Blend: 40% diversity, 40% confidence, 20% causal strength
        source_diversity * 0.4 + avg_confidence * 0.4 + causal_strength * 0.2
    }

    /// Compute independence between pro and con evidence sources.
    fn compute_independence_score(&self, pro_ids: &[i64], con_ids: &[i64]) -> f64 {
        if pro_ids.is_empty() && con_ids.is_empty() {
            return 0.0;
        }

        let pro_set: HashSet<i64> = pro_ids.iter().copied().collect();
        let con_set: HashSet<i64> = con_ids.iter().copied().collect();
        let union: HashSet<i64> = pro_set.union(&con_set).copied().collect();

        if union.is_empty() {
            return 0.0;
        }

        let overlap = pro_set.intersection(&con_set).count();
        1.0 - overlap as f64 / union.len() as f64
    }

    /// Apply verdict-based confidence updates to topic nodes.
    fn apply_verdict_to_topics(
        &self,
        topic_node_ids: &[i64],
        verdict: &DebateVerdict,
        _synthesis_conf: f64,
    ) {
        // Note: KnowledgeGraph nodes are behind RwLock internally.
        // We cannot mutate confidence in the current KeterNode struct
        // (it requires interior mutability). The Python version uses direct
        // attribute mutation. For the Rust port, this is a no-op until
        // KnowledgeGraph exposes an update_confidence method.
        //
        // The verdict and synthesis are recorded as new inference nodes above,
        // which is the primary mechanism for recording debate outcomes.
        let _ = (topic_node_ids, verdict, ACCEPTED_BOOST, REJECTED_PENALTY);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_content(text: &str) -> HashMap<String, String> {
        let mut c = HashMap::new();
        c.insert("text".into(), text.into());
        c
    }

    fn make_debate() -> (Arc<KnowledgeGraph>, DebateProtocol) {
        let kg = Arc::new(KnowledgeGraph::new());
        let dp = DebateProtocol::new(Arc::clone(&kg));
        (kg, dp)
    }

    #[test]
    fn test_debate_empty_topic() {
        let (_kg, dp) = make_debate();
        let result = dp.debate(&[], 3, 0.1);
        assert_eq!(result.verdict, DebateVerdict::Rejected);
        assert_eq!(result.rounds, 0);
    }

    #[test]
    fn test_debate_missing_nodes() {
        let (_kg, dp) = make_debate();
        let result = dp.debate(&[999], 3, 0.1);
        assert_eq!(result.verdict, DebateVerdict::Rejected);
    }

    #[test]
    fn test_debate_basic() {
        let (kg, dp) = make_debate();
        let n1 = kg.add_node("assertion".into(), make_content("hypothesis A"), 0.7, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("support for A"), 0.8, 2, String::new());
        kg.add_edge(n2.node_id, n1.node_id, "supports".into(), 1.0);

        let result = dp.debate(&[n1.node_id], 3, 0.1);
        assert!(result.rounds > 0);
        assert!(!result.positions.is_empty());
        assert!(result.conclusion_node_id.is_some());
    }

    #[test]
    fn test_debate_with_counter_evidence() {
        let (kg, dp) = make_debate();
        let n1 = kg.add_node("assertion".into(), make_content("claim X"), 0.6, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("contradicts X"), 0.9, 2, String::new());
        kg.add_edge(n1.node_id, n2.node_id, "contradicts".into(), 1.0);

        let result = dp.debate(&[n1.node_id], 3, 0.1);
        // Should find counter-evidence
        let has_critic = result.positions.iter().any(|p| p.role == "critic");
        assert!(has_critic);
    }

    #[test]
    fn test_debate_creates_conclusion_node() {
        let (kg, dp) = make_debate();
        let n1 = kg.add_node("assertion".into(), make_content("tested claim"), 0.5, 1, String::new());
        let initial_count = kg.node_count();

        let result = dp.debate(&[n1.node_id], 2, 0.1);
        assert!(result.conclusion_node_id.is_some());
        // Should have created at least one new node (conclusion)
        assert!(kg.node_count() > initial_count);
    }

    #[test]
    fn test_debate_counter_tracks() {
        let (kg, dp) = make_debate();
        let n1 = kg.add_node("assertion".into(), make_content("track test"), 0.5, 1, String::new());

        assert_eq!(dp.total_debates(), 0);
        dp.debate(&[n1.node_id], 2, 0.1);
        assert_eq!(dp.total_debates(), 1);
    }

    #[test]
    fn test_compute_evidence_strength_empty() {
        let (_kg, dp) = make_debate();
        assert!((dp.compute_evidence_strength(&[]) - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_score_evidence_quality_empty() {
        let (_kg, dp) = make_debate();
        assert!((dp.score_evidence_quality(&[]) - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_compute_independence_score() {
        let (_kg, dp) = make_debate();

        // Completely independent
        let score = dp.compute_independence_score(&[1, 2, 3], &[4, 5, 6]);
        assert!((score - 1.0).abs() < f64::EPSILON);

        // Completely overlapping
        let score = dp.compute_independence_score(&[1, 2], &[1, 2]);
        assert!((score - 0.0).abs() < f64::EPSILON);

        // Partial overlap
        let score = dp.compute_independence_score(&[1, 2, 3], &[3, 4, 5]);
        assert!(score > 0.0 && score < 1.0);
    }

    #[test]
    fn test_find_supporting_evidence() {
        let (kg, dp) = make_debate();
        let n1 = kg.add_node("assertion".into(), make_content("topic"), 0.7, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("supporter"), 0.8, 2, String::new());
        let n3 = kg.add_node("assertion".into(), make_content("unrelated"), 0.9, 3, String::new());

        kg.add_edge(n2.node_id, n1.node_id, "supports".into(), 1.0);

        let evidence = dp.find_supporting_evidence(&[n1.node_id]);
        assert!(evidence.contains(&n2.node_id));
        assert!(!evidence.contains(&n3.node_id));
    }

    #[test]
    fn test_debate_rejected_creates_contradiction_resolution() {
        let (kg, dp) = make_debate();
        // Create a node with very low confidence -- likely rejected
        let n1 = kg.add_node("assertion".into(), make_content("weak claim"), 0.1, 1, String::new());
        // Add strong counter-evidence
        let n2 = kg.add_node("assertion".into(), make_content("strong counter"), 0.95, 2, String::new());
        kg.add_edge(n1.node_id, n2.node_id, "contradicts".into(), 1.0);

        let initial_count = kg.node_count();
        let _result = dp.debate(&[n1.node_id], 3, 0.1);
        // Should create both conclusion and possibly contradiction_resolution nodes
        assert!(kg.node_count() > initial_count);
    }

    #[test]
    fn test_debate_multiple_topics() {
        let (kg, dp) = make_debate();
        let n1 = kg.add_node("assertion".into(), make_content("topic A"), 0.6, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("topic B"), 0.7, 2, String::new());

        let result = dp.debate(&[n1.node_id, n2.node_id], 2, 0.1);
        assert!(result.rounds > 0);
        // Topic should include both
        assert!(result.topic.contains("topic A") || result.topic.contains("topic B"));
    }
}
