//! Chain-of-thought reasoning with contradiction-driven backtracking.
//!
//! Builds a reasoning chain step-by-step from query nodes. At each depth
//! level the method gathers context, selects the best reasoning strategy,
//! checks consistency, and backtracks on contradiction.

use crate::reasoning::{ReasoningEngine, ReasoningResult, ReasoningStep};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

/// Extended result for reason_chain with backtrack metadata.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReasonChainResult {
    pub result: ReasoningResult,
    pub backtrack_count: usize,
    pub abandoned_paths: Vec<AbandonedPath>,
}

/// An abandoned reasoning path due to contradiction.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AbandonedPath {
    pub depth: usize,
    pub operation: String,
    pub abandoned_conclusion: Option<i64>,
    pub chain_length_at_abandon: usize,
    pub contradiction_reason: String,
}

/// A snapshot of the chain state for backtracking.
#[derive(Clone)]
struct Checkpoint {
    chain: Vec<ReasoningStep>,
    frontier: Vec<i64>,
    visited: HashSet<i64>,
}

impl ReasoningEngine {
    /// Chain-of-thought reasoning with contradiction-driven backtracking.
    ///
    /// Builds a reasoning chain step-by-step. On contradiction: saves the
    /// abandoned path, restores checkpoint, marks contradicting conclusion
    /// as visited, and retries.
    ///
    /// `strategy_weights` allows self-improvement engine to bias operation
    /// selection (e.g., {"inductive": 1.5, "deductive": 0.8, "abductive": 1.0}).
    pub fn reason_chain(
        &self,
        query_node_ids: &[i64],
        max_depth: usize,
        max_backtrack: usize,
        strategy_weights: Option<&HashMap<String, f64>>,
    ) -> ReasonChainResult {
        let mut chain: Vec<ReasoningStep> = Vec::new();
        let mut visited: HashSet<i64> = HashSet::new();
        let mut backtrack_count: usize = 0;
        let mut abandoned_paths: Vec<AbandonedPath> = Vec::new();

        // Initialize chain with query nodes
        let mut frontier: Vec<i64> = Vec::new();
        for &nid in query_node_ids {
            if let Some(node) = self.knowledge_graph().get_node(nid) {
                chain.push(ReasoningStep::premise(nid, node.content.clone(), node.confidence));
                visited.insert(nid);
                frontier.push(nid);
            }
        }

        if chain.is_empty() {
            return ReasonChainResult {
                result: ReasoningResult::failure("reason_chain", query_node_ids.to_vec(), "No valid starting nodes found"),
                backtrack_count: 0,
                abandoned_paths: Vec::new(),
            };
        }

        // Save initial checkpoint
        let mut checkpoints = vec![Checkpoint {
            chain: chain.clone(),
            frontier: frontier.clone(),
            visited: visited.clone(),
        }];

        let mut conclusion_id: Option<i64> = None;
        let mut overall_confidence: f64 = 1.0;

        for depth in 0..max_depth {
            // 1. Gather context from frontier
            let context = self.gather_context(&frontier, &visited);
            if context.is_empty() {
                break;
            }

            // Categorize context nodes by type
            let mut obs_count = 0_usize;
            let mut inf_count = 0_usize;
            for &cid in &context {
                if let Some(cnode) = self.knowledge_graph().get_node(cid) {
                    match cnode.node_type.as_str() {
                        "observation" | "meta_observation" => obs_count += 1,
                        "inference" | "assertion" | "axiom" => inf_count += 1,
                        _ => {}
                    }
                }
            }

            // 2. Determine operation priority order
            let mut op_order: Vec<&str> = if obs_count >= 2 {
                vec!["inductive", "deductive", "abductive"]
            } else if inf_count >= 2 {
                vec!["deductive", "inductive", "abductive"]
            } else {
                vec!["abductive", "inductive", "deductive"]
            };

            // Re-sort by strategy_weights if provided
            if let Some(weights) = strategy_weights {
                let context_bonus = |op: &str| -> f64 {
                    match op {
                        "inductive" => if obs_count >= 2 { 1.5 } else { 0.8 },
                        "deductive" => if inf_count >= 2 { 1.5 } else { 0.8 },
                        "abductive" => if obs_count < 2 && inf_count < 2 { 1.2 } else { 0.8 },
                        _ => 1.0,
                    }
                };
                let mut scored: Vec<(&str, f64)> = op_order.iter()
                    .map(|&op| {
                        let w = weights.get(op).copied().unwrap_or(1.0);
                        (op, w * context_bonus(op))
                    })
                    .collect();
                scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
                op_order = scored.into_iter().map(|(op, _)| op).collect();
            }

            // 3. Try operations in priority order
            let mut op_result: Option<ReasoningResult> = None;
            for &op_type in &op_order {
                let r = self.try_operation(op_type, &context);
                if let Some(ref res) = r {
                    if res.success {
                        op_result = r;
                        break;
                    }
                }
            }

            let result = match op_result {
                Some(r) if r.success => r,
                _ => break,
            };

            // 4. Check for contradictions
            let contradiction = if let Some(cid) = result.conclusion_node_id {
                self.check_chain_consistency(&chain, cid)
            } else {
                None
            };

            if let Some(reason) = contradiction {
                backtrack_count += 1;
                abandoned_paths.push(AbandonedPath {
                    depth,
                    operation: result.operation_type.clone(),
                    abandoned_conclusion: result.conclusion_node_id,
                    chain_length_at_abandon: chain.len(),
                    contradiction_reason: reason,
                });

                if backtrack_count >= max_backtrack || checkpoints.is_empty() {
                    break;
                }

                // Restore last checkpoint
                let cp = checkpoints.pop().unwrap();
                chain = cp.chain;
                frontier = cp.frontier;
                visited = cp.visited;
                if let Some(cid) = result.conclusion_node_id {
                    visited.insert(cid);
                }
                continue;
            }

            // 5. Success — save checkpoint and extend chain
            checkpoints.push(Checkpoint {
                chain: chain.clone(),
                frontier: frontier.clone(),
                visited: visited.clone(),
            });

            if let Some(cid) = result.conclusion_node_id {
                let mut content = HashMap::new();
                content.insert("type".into(), format!("{}_step", result.operation_type));
                content.insert("depth".into(), depth.to_string());
                chain.push(ReasoningStep::conclusion(cid, content, result.confidence));
                overall_confidence = overall_confidence.min(result.confidence);
                conclusion_id = Some(cid);
                frontier = vec![cid];

                // Expand frontier with neighbors
                if let Some(node) = self.knowledge_graph().get_node(cid) {
                    for &nid in node.edges_out.iter().take(10) {
                        if !visited.contains(&nid) {
                            frontier.push(nid);
                        }
                    }
                }
            }
        }

        let success = chain.len() > query_node_ids.len();

        ReasonChainResult {
            result: ReasoningResult {
                operation_type: "reason_chain".into(),
                premise_ids: query_node_ids.to_vec(),
                conclusion_node_id: conclusion_id,
                confidence: overall_confidence.clamp(0.0, 1.0),
                chain,
                success,
                explanation: format!(
                    "Reason chain: backtracks={}, abandoned_paths={}",
                    backtrack_count, abandoned_paths.len()
                ),
                domain: String::new(),
                block_height: self.block_height(),
                hypotheses: Vec::new(),
            },
            backtrack_count,
            abandoned_paths,
        }
    }

    /// Gather neighbor node IDs reachable from frontier not yet visited.
    pub(crate) fn gather_context(&self, frontier: &[i64], visited: &HashSet<i64>) -> Vec<i64> {
        let mut context_ids = Vec::new();
        let mut seen = HashSet::new();

        for &nid in frontier {
            if let Some(node) = self.knowledge_graph().get_node(nid) {
                for &neighbor_id in &node.edges_out {
                    if !visited.contains(&neighbor_id) && seen.insert(neighbor_id) {
                        context_ids.push(neighbor_id);
                    }
                }
                for &neighbor_id in &node.edges_in {
                    if !visited.contains(&neighbor_id) && seen.insert(neighbor_id) {
                        context_ids.push(neighbor_id);
                    }
                }
            }
        }
        context_ids
    }

    /// Attempt a single reasoning operation of the given type.
    pub(crate) fn try_operation(&self, op_type: &str, context: &[i64]) -> Option<ReasoningResult> {
        if context.is_empty() {
            return None;
        }

        match op_type {
            "inductive" => {
                let obs_ids: Vec<i64> = context.iter().copied()
                    .filter(|&nid| {
                        self.knowledge_graph().get_node(nid)
                            .map(|n| matches!(n.node_type.as_str(), "observation" | "assertion" | "meta_observation"))
                            .unwrap_or(false)
                    })
                    .take(5)
                    .collect();
                if obs_ids.len() >= 2 {
                    Some(self.induce(&obs_ids))
                } else {
                    None
                }
            }
            "deductive" => {
                let inf_ids: Vec<i64> = context.iter().copied()
                    .filter(|&nid| {
                        self.knowledge_graph().get_node(nid)
                            .map(|n| matches!(n.node_type.as_str(), "inference" | "assertion" | "axiom"))
                            .unwrap_or(false)
                    })
                    .take(5)
                    .collect();
                if inf_ids.len() >= 2 {
                    Some(self.deduce(&inf_ids, None))
                } else {
                    None
                }
            }
            "abductive" => {
                let obs_ids: Vec<i64> = context.iter().copied()
                    .filter(|&nid| {
                        self.knowledge_graph().get_node(nid)
                            .map(|n| matches!(n.node_type.as_str(), "observation" | "meta_observation"))
                            .unwrap_or(false)
                    })
                    .collect();
                if let Some(&first) = obs_ids.first() {
                    Some(self.abduce(first))
                } else {
                    Some(self.abduce(context[0]))
                }
            }
            _ => None,
        }
    }

    /// Check whether a newly concluded node contradicts anything in the chain.
    ///
    /// Returns a reason string if contradiction found, None if consistent.
    pub(crate) fn check_chain_consistency(&self, chain: &[ReasoningStep], new_node_id: i64) -> Option<String> {
        let _new_node = self.knowledge_graph().get_node(new_node_id)?;

        // Collect all node IDs in the chain
        let chain_node_ids: HashSet<i64> = chain.iter()
            .filter_map(|s| s.node_id)
            .collect();

        if chain_node_ids.is_empty() {
            return None;
        }

        // Check 1: Explicit 'contradicts' edges from new_node -> chain nodes
        for edge in self.knowledge_graph().get_edges_from(new_node_id) {
            if edge.edge_type == "contradicts" && chain_node_ids.contains(&edge.to_node_id) {
                return Some(format!(
                    "Node {} explicitly contradicts chain node {}",
                    new_node_id, edge.to_node_id
                ));
            }
        }

        // Check 2: Explicit 'contradicts' edges from chain nodes -> new_node
        for edge in self.knowledge_graph().get_edges_to(new_node_id) {
            if edge.edge_type == "contradicts" && chain_node_ids.contains(&edge.from_node_id) {
                return Some(format!(
                    "Chain node {} explicitly contradicts new node {}",
                    edge.from_node_id, new_node_id
                ));
            }
        }

        // Check 3: Content-level conflict (same domain, opposing numeric values)
        let new_node = self.knowledge_graph().get_node(new_node_id)?;
        let new_text = new_node.content.get("text").cloned().unwrap_or_default().to_lowercase();
        if !new_text.is_empty() {
            let new_numbers = extract_numbers(&new_text);
            let new_words: HashSet<&str> = new_text.split_whitespace().collect();

            for step in chain {
                let step_nid = match step.node_id {
                    Some(id) if id != new_node_id => id,
                    _ => continue,
                };
                let chain_node = match self.knowledge_graph().get_node(step_nid) {
                    Some(n) => n,
                    None => continue,
                };
                // Only compare same-domain nodes
                if !chain_node.domain.is_empty() && !new_node.domain.is_empty()
                    && chain_node.domain != new_node.domain
                {
                    continue;
                }
                let chain_text = chain_node.content.get("text").cloned().unwrap_or_default().to_lowercase();
                if chain_text.is_empty() {
                    continue;
                }
                let chain_words: HashSet<&str> = chain_text.split_whitespace().collect();
                let overlap = new_words.intersection(&chain_words).count();
                let total = new_words.union(&chain_words).count();
                let word_sim = if total > 0 { overlap as f64 / total as f64 } else { 0.0 };

                if word_sim > 0.4 {
                    let chain_numbers = extract_numbers(&chain_text);
                    if !new_numbers.is_empty() && !chain_numbers.is_empty()
                        && new_numbers != chain_numbers
                        && new_numbers.intersection(&chain_numbers).count() == 0
                    {
                        return Some(format!(
                            "Content conflict: node {} and chain node {} share {}/{} words but have different numeric values",
                            new_node_id, step_nid, overlap, total
                        ));
                    }
                }
            }
        }

        None
    }
}

/// Extract numbers from text for contradiction detection.
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
    fn test_extract_numbers() {
        let nums = extract_numbers("the value is 42.5 and count is 100");
        assert!(nums.contains("42.5"));
        assert!(nums.contains("100"));
    }

    #[test]
    fn test_extract_numbers_no_trailing_dot() {
        let nums = extract_numbers("block 1234.");
        assert!(nums.contains("1234"));
        assert!(!nums.contains("1234."));
    }

    #[test]
    fn test_reason_chain_basic() {
        let (kg, engine) = make_engine();
        let n1 = kg.add_node("assertion".into(), make_content("fact A"), 0.9, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("fact B"), 0.8, 2, String::new());
        kg.add_edge(n1.node_id, n2.node_id, "supports".into(), 1.0);

        let result = engine.reason_chain(&[n1.node_id], 3, 2, None);
        assert_eq!(result.result.operation_type, "reason_chain");
        assert_eq!(result.backtrack_count, 0);
    }

    #[test]
    fn test_reason_chain_no_nodes() {
        let (_kg, engine) = make_engine();
        let result = engine.reason_chain(&[999], 3, 2, None);
        assert!(!result.result.success);
    }

    #[test]
    fn test_reason_chain_with_strategy_weights() {
        let (kg, engine) = make_engine();
        kg.add_node("observation".into(), make_content("obs 1"), 0.9, 1, String::new());
        kg.add_node("observation".into(), make_content("obs 2"), 0.8, 2, String::new());
        kg.add_edge(1, 2, "supports".into(), 1.0);

        let mut weights = HashMap::new();
        weights.insert("inductive".into(), 2.0);
        weights.insert("deductive".into(), 0.5);
        weights.insert("abductive".into(), 1.0);

        let result = engine.reason_chain(&[1], 3, 2, Some(&weights));
        assert_eq!(result.result.operation_type, "reason_chain");
    }

    #[test]
    fn test_check_chain_consistency_no_conflict() {
        let (kg, engine) = make_engine();
        let n1 = kg.add_node("assertion".into(), make_content("safe claim"), 0.9, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("compatible claim"), 0.8, 2, String::new());

        let chain = vec![ReasoningStep::premise(n1.node_id, n1.content.clone(), n1.confidence)];
        assert!(engine.check_chain_consistency(&chain, n2.node_id).is_none());
    }

    #[test]
    fn test_check_chain_consistency_explicit_contradiction() {
        let (kg, engine) = make_engine();
        let n1 = kg.add_node("inference".into(), make_content("claim A"), 0.9, 1, String::new());
        let n2 = kg.add_node("inference".into(), make_content("claim B"), 0.8, 2, String::new());
        kg.add_edge(n2.node_id, n1.node_id, "contradicts".into(), 1.0);

        let chain = vec![ReasoningStep::premise(n1.node_id, n1.content.clone(), n1.confidence)];
        let contradiction = engine.check_chain_consistency(&chain, n2.node_id);
        assert!(contradiction.is_some());
    }

    #[test]
    fn test_gather_context() {
        let (kg, engine) = make_engine();
        let n1 = kg.add_node("assertion".into(), make_content("root"), 0.9, 1, String::new());
        let n2 = kg.add_node("assertion".into(), make_content("child"), 0.8, 2, String::new());
        kg.add_edge(n1.node_id, n2.node_id, "supports".into(), 1.0);

        let visited = HashSet::new();
        let context = engine.gather_context(&[n1.node_id], &visited);
        assert!(context.contains(&n2.node_id));
    }

    #[test]
    fn test_try_operation_inductive() {
        let (kg, engine) = make_engine();
        kg.add_node("observation".into(), make_content("obs A"), 0.9, 1, String::new());
        kg.add_node("observation".into(), make_content("obs B"), 0.8, 2, String::new());

        let result = engine.try_operation("inductive", &[1, 2]);
        assert!(result.is_some());
        assert!(result.unwrap().success);
    }

    #[test]
    fn test_try_operation_deductive() {
        let (kg, engine) = make_engine();
        kg.add_node("assertion".into(), make_content("premise A"), 0.9, 1, String::new());
        kg.add_node("assertion".into(), make_content("premise B"), 0.8, 2, String::new());

        let result = engine.try_operation("deductive", &[1, 2]);
        assert!(result.is_some());
        assert!(result.unwrap().success);
    }

    #[test]
    fn test_try_operation_abductive() {
        let (kg, engine) = make_engine();
        kg.add_node("observation".into(), make_content("mystery"), 0.9, 1, String::new());

        let result = engine.try_operation("abductive", &[1]);
        assert!(result.is_some());
        assert!(result.unwrap().success);
    }
}
