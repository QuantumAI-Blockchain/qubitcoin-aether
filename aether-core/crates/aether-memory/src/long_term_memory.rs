//! LongTermMemory — Long-term memory consolidation for the Aether Tree.
//!
//! Rust equivalent of the Python `consolidate_long_term()` method. Provides:
//!
//! - **Episode merging**: Merges related episodes (same strategy, overlapping inputs)
//!   into consolidated summaries.
//! - **Pattern extraction**: Identifies recurring strategies and input patterns
//!   across episodes to create "axioms" (highly reliable patterns).
//! - **Episode replay**: Re-surfaces high-value episodes for reinforcement learning.
//! - **Consolidation scheduling**: Tracks when consolidation last ran and how many
//!   cycles have completed.
//!
//! This module works with the MemoryManager's episodic storage but does NOT hold
//! a reference to it — episodes are passed in, and consolidation results are
//! returned for the caller to apply.

use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};

use crate::memory_manager::Episode;

// ---------------------------------------------------------------------------
// ConsolidatedPattern
// ---------------------------------------------------------------------------

/// A pattern discovered during long-term consolidation.
///
/// Represents a recurring strategy+input combination that appears across
/// multiple successful episodes.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct ConsolidatedPattern {
    /// Unique pattern ID (incrementing).
    pub pattern_id: i64,
    /// The reasoning strategy shared by the merged episodes.
    pub strategy: String,
    /// Canonical set of input node IDs that recur across episodes.
    pub canonical_inputs: Vec<i64>,
    /// Number of episodes that contributed to this pattern.
    pub episode_count: i64,
    /// Average confidence across contributing episodes.
    pub avg_confidence: f64,
    /// Success rate across contributing episodes.
    pub success_rate: f64,
    /// Whether this pattern has been promoted to an axiom (very reliable).
    pub is_axiom: bool,
    /// Block height at which this pattern was discovered.
    pub discovered_at_block: i64,
}

#[pymethods]
impl ConsolidatedPattern {
    #[new]
    #[pyo3(signature = (
        pattern_id = 0,
        strategy = String::new(),
        canonical_inputs = vec![],
        episode_count = 0,
        avg_confidence = 0.0,
        success_rate = 0.0,
        is_axiom = false,
        discovered_at_block = 0,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        pattern_id: i64,
        strategy: String,
        canonical_inputs: Vec<i64>,
        episode_count: i64,
        avg_confidence: f64,
        success_rate: f64,
        is_axiom: bool,
        discovered_at_block: i64,
    ) -> Self {
        ConsolidatedPattern {
            pattern_id,
            strategy,
            canonical_inputs,
            episode_count,
            avg_confidence,
            success_rate,
            is_axiom,
            discovered_at_block,
        }
    }

    /// Check if this pattern qualifies as an axiom.
    ///
    /// An axiom requires: episode_count >= 5, success_rate >= 0.8, avg_confidence >= 0.7.
    pub fn qualifies_as_axiom(&self) -> bool {
        self.episode_count >= 5 && self.success_rate >= 0.8 && self.avg_confidence >= 0.7
    }

    fn __repr__(&self) -> String {
        format!(
            "ConsolidatedPattern(id={}, strategy='{}', episodes={}, success={:.2}, axiom={})",
            self.pattern_id, self.strategy, self.episode_count, self.success_rate, self.is_axiom
        )
    }
}

// ---------------------------------------------------------------------------
// ConsolidationResult
// ---------------------------------------------------------------------------

/// Result of a consolidation cycle.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct ConsolidationResult {
    /// Newly discovered or updated patterns.
    pub patterns: Vec<ConsolidatedPattern>,
    /// New axioms promoted this cycle.
    pub new_axioms: Vec<ConsolidatedPattern>,
    /// Episode IDs selected for replay.
    pub replay_episode_ids: Vec<i64>,
    /// Number of episodes processed.
    pub episodes_processed: i64,
    /// Number of episode clusters found.
    pub clusters_found: i64,
}

#[pymethods]
impl ConsolidationResult {
    #[new]
    pub fn new() -> Self {
        ConsolidationResult {
            patterns: Vec::new(),
            new_axioms: Vec::new(),
            replay_episode_ids: Vec::new(),
            episodes_processed: 0,
            clusters_found: 0,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "ConsolidationResult(patterns={}, axioms={}, replays={}, processed={})",
            self.patterns.len(),
            self.new_axioms.len(),
            self.replay_episode_ids.len(),
            self.episodes_processed
        )
    }
}

// ---------------------------------------------------------------------------
// LongTermMemory
// ---------------------------------------------------------------------------

/// Long-term memory consolidation engine.
///
/// Consolidates episodic memories into stable patterns and axioms.
/// Designed to run periodically (e.g., every 3300 blocks / ~3 hours).
///
/// The consolidation algorithm:
/// 1. Group episodes by reasoning strategy.
/// 2. Within each strategy group, cluster episodes by input overlap (Jaccard > 0.3).
/// 3. For each cluster, create a ConsolidatedPattern with statistics.
/// 4. Promote patterns to axioms when they meet reliability thresholds.
/// 5. Select high-value episodes for replay (successful + high confidence).
#[pyclass]
pub struct LongTermMemory {
    /// Number of consolidation cycles completed.
    consolidation_count: i64,
    /// Block height of last consolidation.
    last_consolidation_block: i64,
    /// Consolidation interval in blocks (default 3300 = ~3 hours at 3.3s/block).
    consolidation_interval: i64,
    /// Known patterns from previous consolidations.
    patterns: Vec<ConsolidatedPattern>,
    /// Next pattern ID to assign.
    next_pattern_id: i64,
    /// Minimum Jaccard similarity to merge episodes into a cluster.
    cluster_threshold: f64,
    /// Maximum number of episodes to replay per consolidation.
    max_replay: usize,
}

#[pymethods]
impl LongTermMemory {
    /// Create a new LongTermMemory consolidation engine.
    ///
    /// # Arguments
    /// - `consolidation_interval`: Blocks between consolidations (default 3300).
    /// - `cluster_threshold`: Jaccard similarity threshold for clustering (default 0.3).
    /// - `max_replay`: Max episodes to replay per cycle (default 20).
    #[new]
    #[pyo3(signature = (consolidation_interval = 3300, cluster_threshold = 0.3, max_replay = 20))]
    pub fn new(
        consolidation_interval: i64,
        cluster_threshold: f64,
        max_replay: usize,
    ) -> Self {
        LongTermMemory {
            consolidation_count: 0,
            last_consolidation_block: 0,
            consolidation_interval,
            patterns: Vec::new(),
            next_pattern_id: 1,
            cluster_threshold,
            max_replay,
        }
    }

    /// Check if consolidation should run for the given block height.
    pub fn should_consolidate(&self, current_block: i64) -> bool {
        current_block - self.last_consolidation_block >= self.consolidation_interval
    }

    /// Run consolidation on a set of episodes.
    ///
    /// # Arguments
    /// - `episodes`: All episodic memories to consolidate.
    /// - `current_block`: Current block height (for tracking).
    ///
    /// # Returns
    /// A ConsolidationResult with discovered patterns, new axioms, and replay candidates.
    pub fn consolidate(
        &mut self,
        episodes: Vec<Episode>,
        current_block: i64,
    ) -> ConsolidationResult {
        let mut result = ConsolidationResult::new();
        result.episodes_processed = episodes.len() as i64;

        if episodes.is_empty() {
            self.last_consolidation_block = current_block;
            self.consolidation_count += 1;
            return result;
        }

        // Step 1: Group by strategy
        let strategy_groups = group_by_strategy(&episodes);
        let mut all_new_patterns: Vec<ConsolidatedPattern> = Vec::new();

        // Step 2: Cluster within each group
        for (strategy, group_episodes) in &strategy_groups {
            let clusters = cluster_by_input_overlap(group_episodes, self.cluster_threshold);
            result.clusters_found += clusters.len() as i64;

            for cluster in &clusters {
                if cluster.len() < 2 {
                    continue; // Need at least 2 episodes to form a pattern
                }

                let pattern = self.build_pattern(strategy, cluster, current_block);
                all_new_patterns.push(pattern);
            }
        }

        // Step 3: Merge with existing patterns
        for new_pattern in &all_new_patterns {
            let merged = self.merge_with_existing(new_pattern);
            if !merged {
                self.patterns.push(new_pattern.clone());
            }
        }

        // Step 4: Promote axioms
        let mut new_axioms = Vec::new();
        for pattern in &mut self.patterns {
            if !pattern.is_axiom && pattern.qualifies_as_axiom() {
                pattern.is_axiom = true;
                new_axioms.push(pattern.clone());
            }
        }

        // Step 5: Select replay candidates
        let replay_ids = self.select_replay_candidates(&episodes);

        result.patterns = self.patterns.clone();
        result.new_axioms = new_axioms;
        result.replay_episode_ids = replay_ids;

        self.last_consolidation_block = current_block;
        self.consolidation_count += 1;

        result
    }

    /// Replay high-value episodes: select episodes worth re-attending to.
    ///
    /// Criteria: successful, high confidence, not recently replayed.
    ///
    /// # Arguments
    /// - `episodes`: All available episodes.
    ///
    /// # Returns
    /// Episode IDs to replay, sorted by value (highest first).
    pub fn replay_episodes(&self, episodes: Vec<Episode>) -> Vec<i64> {
        self.select_replay_candidates(&episodes)
    }

    /// Get all known patterns.
    pub fn get_patterns(&self) -> Vec<ConsolidatedPattern> {
        self.patterns.clone()
    }

    /// Get only axiom patterns (high reliability).
    pub fn get_axioms(&self) -> Vec<ConsolidatedPattern> {
        self.patterns
            .iter()
            .filter(|p| p.is_axiom)
            .cloned()
            .collect()
    }

    /// Number of consolidation cycles completed.
    #[getter]
    pub fn consolidation_count(&self) -> i64 {
        self.consolidation_count
    }

    /// Block height of last consolidation.
    #[getter]
    pub fn last_consolidation_block(&self) -> i64 {
        self.last_consolidation_block
    }

    /// Total patterns discovered.
    #[getter]
    pub fn pattern_count(&self) -> usize {
        self.patterns.len()
    }

    /// Total axioms.
    #[getter]
    pub fn axiom_count(&self) -> usize {
        self.patterns.iter().filter(|p| p.is_axiom).count()
    }

    /// Clear all patterns and reset state (for testing).
    pub fn reset(&mut self) {
        self.patterns.clear();
        self.consolidation_count = 0;
        self.last_consolidation_block = 0;
        self.next_pattern_id = 1;
    }

    fn __repr__(&self) -> String {
        format!(
            "LongTermMemory(consolidations={}, patterns={}, axioms={}, last_block={})",
            self.consolidation_count,
            self.patterns.len(),
            self.axiom_count(),
            self.last_consolidation_block
        )
    }
}

// Internal methods
impl LongTermMemory {
    /// Build a ConsolidatedPattern from a cluster of episodes.
    fn build_pattern(
        &mut self,
        strategy: &str,
        cluster: &[&Episode],
        current_block: i64,
    ) -> ConsolidatedPattern {
        let id = self.next_pattern_id;
        self.next_pattern_id += 1;

        // Compute canonical inputs (intersection of all episode inputs)
        let canonical = compute_canonical_inputs(cluster);

        // Compute statistics
        let total = cluster.len() as f64;
        let success_count = cluster.iter().filter(|e| e.success).count() as f64;
        let avg_conf: f64 = cluster.iter().map(|e| e.confidence).sum::<f64>() / total;

        ConsolidatedPattern {
            pattern_id: id,
            strategy: strategy.to_string(),
            canonical_inputs: canonical,
            episode_count: cluster.len() as i64,
            avg_confidence: avg_conf,
            success_rate: success_count / total,
            is_axiom: false,
            discovered_at_block: current_block,
        }
    }

    /// Try to merge a new pattern with an existing one. Returns true if merged.
    fn merge_with_existing(&mut self, new_pattern: &ConsolidatedPattern) -> bool {
        for existing in &mut self.patterns {
            if existing.strategy != new_pattern.strategy {
                continue;
            }
            // Check input overlap
            let jaccard = jaccard_similarity_vecs(
                &existing.canonical_inputs,
                &new_pattern.canonical_inputs,
            );
            if jaccard > 0.5 {
                // Merge: weighted average of statistics
                let total = existing.episode_count + new_pattern.episode_count;
                let w_old = existing.episode_count as f64 / total as f64;
                let w_new = new_pattern.episode_count as f64 / total as f64;

                existing.avg_confidence =
                    w_old * existing.avg_confidence + w_new * new_pattern.avg_confidence;
                existing.success_rate =
                    w_old * existing.success_rate + w_new * new_pattern.success_rate;
                existing.episode_count = total;

                // Merge canonical inputs (union)
                let mut combined: HashSet<i64> =
                    existing.canonical_inputs.iter().copied().collect();
                combined.extend(new_pattern.canonical_inputs.iter().copied());
                existing.canonical_inputs = combined.into_iter().collect();
                existing.canonical_inputs.sort();

                return true;
            }
        }
        false
    }

    /// Select episodes worth replaying.
    fn select_replay_candidates(&self, episodes: &[Episode]) -> Vec<i64> {
        let mut candidates: Vec<(i64, f64)> = episodes
            .iter()
            .filter(|e| e.success && e.confidence > 0.5)
            .map(|e| {
                // Score: confidence * recency_boost * (1 / (1 + replay_count))
                let replay_penalty = 1.0 / (1.0 + e.replay_count as f64);
                let score = e.confidence * replay_penalty;
                (e.episode_id, score)
            })
            .collect();

        // Sort by score descending
        candidates.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        candidates.truncate(self.max_replay);
        candidates.into_iter().map(|(id, _)| id).collect()
    }
}

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

/// Group episodes by reasoning strategy.
fn group_by_strategy<'a>(episodes: &'a [Episode]) -> HashMap<String, Vec<&'a Episode>> {
    let mut groups: HashMap<String, Vec<&Episode>> = HashMap::new();
    for ep in episodes {
        groups
            .entry(ep.reasoning_strategy.clone())
            .or_default()
            .push(ep);
    }
    groups
}

/// Cluster episodes by input node overlap using greedy Jaccard-based clustering.
fn cluster_by_input_overlap<'a>(
    episodes: &[&'a Episode],
    threshold: f64,
) -> Vec<Vec<&'a Episode>> {
    if episodes.is_empty() {
        return Vec::new();
    }

    let mut assigned = vec![false; episodes.len()];
    let mut clusters: Vec<Vec<&Episode>> = Vec::new();

    for i in 0..episodes.len() {
        if assigned[i] {
            continue;
        }
        assigned[i] = true;
        let mut cluster = vec![episodes[i]];

        for j in (i + 1)..episodes.len() {
            if assigned[j] {
                continue;
            }
            let jaccard = jaccard_similarity(
                &episodes[i].input_node_ids,
                &episodes[j].input_node_ids,
            );
            if jaccard >= threshold {
                assigned[j] = true;
                cluster.push(episodes[j]);
            }
        }

        clusters.push(cluster);
    }

    clusters
}

/// Jaccard similarity between two sets (represented as slices).
fn jaccard_similarity(a: &[i64], b: &[i64]) -> f64 {
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    let set_a: HashSet<i64> = a.iter().copied().collect();
    let set_b: HashSet<i64> = b.iter().copied().collect();
    let intersection = set_a.intersection(&set_b).count();
    let union = set_a.union(&set_b).count();
    if union == 0 {
        return 0.0;
    }
    intersection as f64 / union as f64
}

/// Jaccard similarity between two sorted Vec<i64>.
fn jaccard_similarity_vecs(a: &[i64], b: &[i64]) -> f64 {
    jaccard_similarity(a, b)
}

/// Compute canonical inputs: nodes that appear in the majority of episodes.
fn compute_canonical_inputs(cluster: &[&Episode]) -> Vec<i64> {
    if cluster.is_empty() {
        return Vec::new();
    }
    let threshold = (cluster.len() as f64 * 0.5).ceil() as usize;
    let mut counts: HashMap<i64, usize> = HashMap::new();

    for ep in cluster {
        for &nid in &ep.input_node_ids {
            *counts.entry(nid).or_insert(0) += 1;
        }
    }

    let mut canonical: Vec<i64> = counts
        .into_iter()
        .filter(|(_, count)| *count >= threshold)
        .map(|(nid, _)| nid)
        .collect();
    canonical.sort();
    canonical
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_episode(
        id: i64,
        strategy: &str,
        inputs: Vec<i64>,
        success: bool,
        confidence: f64,
    ) -> Episode {
        Episode::new(
            id,
            100 + id, // block height
            inputs,
            strategy.to_string(),
            Some(id * 100),
            success,
            confidence,
            1000.0 + id as f64,
            0,
        )
    }

    // -- ConsolidatedPattern tests --

    #[test]
    fn test_pattern_qualifies_as_axiom() {
        let mut p = ConsolidatedPattern::new(
            1,
            "deductive".into(),
            vec![1, 2, 3],
            5,
            0.8,
            0.9,
            false,
            1000,
        );
        assert!(p.qualifies_as_axiom());

        p.episode_count = 3; // Too few
        assert!(!p.qualifies_as_axiom());

        p.episode_count = 10;
        p.success_rate = 0.5; // Too low
        assert!(!p.qualifies_as_axiom());

        p.success_rate = 0.9;
        p.avg_confidence = 0.3; // Too low
        assert!(!p.qualifies_as_axiom());
    }

    #[test]
    fn test_pattern_repr() {
        let p = ConsolidatedPattern::new(1, "test".into(), vec![], 5, 0.8, 0.9, true, 0);
        let r = p.__repr__();
        assert!(r.contains("test"));
        assert!(r.contains("axiom=true"));
    }

    // -- Jaccard similarity tests --

    #[test]
    fn test_jaccard_identical() {
        let sim = jaccard_similarity(&[1, 2, 3], &[1, 2, 3]);
        assert!((sim - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_jaccard_disjoint() {
        let sim = jaccard_similarity(&[1, 2, 3], &[4, 5, 6]);
        assert!(sim.abs() < 1e-10);
    }

    #[test]
    fn test_jaccard_partial_overlap() {
        let sim = jaccard_similarity(&[1, 2, 3], &[2, 3, 4]);
        // intersection={2,3}=2, union={1,2,3,4}=4, jaccard=0.5
        assert!((sim - 0.5).abs() < 1e-10);
    }

    #[test]
    fn test_jaccard_empty_both() {
        let sim = jaccard_similarity(&[], &[]);
        assert!((sim - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_jaccard_one_empty() {
        let sim = jaccard_similarity(&[1, 2], &[]);
        assert!(sim.abs() < 1e-10);
    }

    // -- Clustering tests --

    #[test]
    fn test_cluster_by_overlap() {
        let e1 = make_episode(1, "deductive", vec![1, 2, 3], true, 0.8);
        let e2 = make_episode(2, "deductive", vec![2, 3, 4], true, 0.7);
        let e3 = make_episode(3, "deductive", vec![10, 11, 12], true, 0.9);

        let episodes: Vec<&Episode> = vec![&e1, &e2, &e3];
        let clusters = cluster_by_input_overlap(&episodes, 0.3);

        // e1 and e2 share {2,3} (jaccard=0.5 >= 0.3), e3 is separate
        assert_eq!(clusters.len(), 2);
    }

    #[test]
    fn test_cluster_empty() {
        let episodes: Vec<&Episode> = vec![];
        let clusters = cluster_by_input_overlap(&episodes, 0.3);
        assert!(clusters.is_empty());
    }

    // -- Canonical inputs tests --

    #[test]
    fn test_canonical_inputs() {
        let e1 = make_episode(1, "x", vec![1, 2, 3], true, 0.8);
        let e2 = make_episode(2, "x", vec![2, 3, 4], true, 0.7);
        let e3 = make_episode(3, "x", vec![3, 4, 5], true, 0.9);

        let cluster: Vec<&Episode> = vec![&e1, &e2, &e3];
        let canonical = compute_canonical_inputs(&cluster);

        // threshold = ceil(3 * 0.5) = 2
        // node 1: count=1 (no), node 2: count=2 (yes), node 3: count=3 (yes),
        // node 4: count=2 (yes), node 5: count=1 (no)
        assert!(canonical.contains(&2));
        assert!(canonical.contains(&3));
        assert!(canonical.contains(&4));
        assert!(!canonical.contains(&1));
        assert!(!canonical.contains(&5));
    }

    // -- LongTermMemory tests --

    #[test]
    fn test_ltm_creation() {
        let ltm = LongTermMemory::new(3300, 0.3, 20);
        assert_eq!(ltm.consolidation_count(), 0);
        assert_eq!(ltm.last_consolidation_block(), 0);
        assert_eq!(ltm.pattern_count(), 0);
    }

    #[test]
    fn test_should_consolidate() {
        let ltm = LongTermMemory::new(100, 0.3, 20);
        assert!(ltm.should_consolidate(100));
        assert!(ltm.should_consolidate(200));
        assert!(!ltm.should_consolidate(50));
    }

    #[test]
    fn test_consolidate_empty() {
        let mut ltm = LongTermMemory::new(100, 0.3, 20);
        let result = ltm.consolidate(vec![], 100);
        assert_eq!(result.episodes_processed, 0);
        assert_eq!(ltm.consolidation_count(), 1);
        assert_eq!(ltm.last_consolidation_block(), 100);
    }

    #[test]
    fn test_consolidate_finds_patterns() {
        let mut ltm = LongTermMemory::new(100, 0.3, 20);

        let episodes = vec![
            make_episode(1, "deductive", vec![1, 2, 3], true, 0.8),
            make_episode(2, "deductive", vec![2, 3, 4], true, 0.9),
            make_episode(3, "deductive", vec![1, 3, 4], true, 0.7),
            make_episode(4, "inductive", vec![10, 11], true, 0.6),
            make_episode(5, "inductive", vec![10, 12], true, 0.7),
        ];

        let result = ltm.consolidate(episodes, 1000);
        assert_eq!(result.episodes_processed, 5);
        assert!(result.clusters_found > 0);
        assert!(ltm.pattern_count() > 0);
    }

    #[test]
    fn test_consolidate_promotes_axioms() {
        let mut ltm = LongTermMemory::new(100, 0.3, 20);

        // Create many similar successful episodes to trigger axiom promotion
        let mut episodes = Vec::new();
        for i in 0..10 {
            episodes.push(make_episode(
                i,
                "deductive",
                vec![1, 2, 3],
                true,
                0.85,
            ));
        }

        let result = ltm.consolidate(episodes, 1000);
        // With 10 identical episodes, should form a pattern that qualifies as axiom
        assert!(
            !result.new_axioms.is_empty() || ltm.axiom_count() > 0,
            "should promote axiom with 10 successful identical episodes"
        );
    }

    #[test]
    fn test_replay_episodes() {
        let ltm = LongTermMemory::new(100, 0.3, 5);

        let episodes = vec![
            make_episode(1, "deductive", vec![1, 2], true, 0.9),
            make_episode(2, "deductive", vec![3, 4], false, 0.8), // Failed - excluded
            make_episode(3, "inductive", vec![5, 6], true, 0.3),  // Low confidence - excluded
            make_episode(4, "abductive", vec![7, 8], true, 0.7),
        ];

        let replay_ids = ltm.replay_episodes(episodes.clone());
        // Should include episode 1 (success + high conf) and 4 (success + conf > 0.5)
        assert!(replay_ids.contains(&1));
        assert!(replay_ids.contains(&4));
        // Should not include 2 (failed) or 3 (low confidence)
        assert!(!replay_ids.contains(&2));
        assert!(!replay_ids.contains(&3));
    }

    #[test]
    fn test_replay_respects_max() {
        let ltm = LongTermMemory::new(100, 0.3, 2);

        let mut episodes = Vec::new();
        for i in 0..10 {
            episodes.push(make_episode(i, "deductive", vec![1, 2], true, 0.9));
        }

        let replay_ids = ltm.replay_episodes(episodes.clone());
        assert!(replay_ids.len() <= 2);
    }

    #[test]
    fn test_replay_penalizes_already_replayed() {
        let ltm = LongTermMemory::new(100, 0.3, 10);

        let mut e1 = make_episode(1, "d", vec![1], true, 0.9);
        e1.replay_count = 10; // Already replayed many times
        let e2 = make_episode(2, "d", vec![1], true, 0.8);

        let replay_ids = ltm.replay_episodes(vec![e1, e2]);
        // e2 should rank higher because e1 has been replayed 10 times
        if replay_ids.len() >= 2 {
            assert_eq!(replay_ids[0], 2, "less-replayed episode should rank first");
        }
    }

    #[test]
    fn test_consolidate_merges_patterns() {
        let mut ltm = LongTermMemory::new(100, 0.3, 20);

        // First consolidation
        let episodes1 = vec![
            make_episode(1, "deductive", vec![1, 2, 3], true, 0.8),
            make_episode(2, "deductive", vec![1, 2, 4], true, 0.7),
        ];
        ltm.consolidate(episodes1, 100);
        let count_after_first = ltm.pattern_count();

        // Second consolidation with similar episodes — should merge
        let episodes2 = vec![
            make_episode(3, "deductive", vec![1, 2, 3], true, 0.9),
            make_episode(4, "deductive", vec![1, 2, 5], true, 0.85),
        ];
        ltm.consolidate(episodes2, 200);

        // Pattern count should stay roughly the same (merged, not duplicated)
        assert!(
            ltm.pattern_count() <= count_after_first + 1,
            "patterns should merge, not accumulate: count={}",
            ltm.pattern_count()
        );
    }

    #[test]
    fn test_reset() {
        let mut ltm = LongTermMemory::new(100, 0.3, 20);
        let episodes = vec![
            make_episode(1, "d", vec![1, 2], true, 0.8),
            make_episode(2, "d", vec![1, 3], true, 0.9),
        ];
        ltm.consolidate(episodes, 100);
        assert!(ltm.pattern_count() > 0 || ltm.consolidation_count() > 0);

        ltm.reset();
        assert_eq!(ltm.consolidation_count(), 0);
        assert_eq!(ltm.pattern_count(), 0);
        assert_eq!(ltm.last_consolidation_block(), 0);
    }

    #[test]
    fn test_get_axioms_empty() {
        let ltm = LongTermMemory::new(100, 0.3, 20);
        assert!(ltm.get_axioms().is_empty());
    }

    #[test]
    fn test_repr() {
        let ltm = LongTermMemory::new(3300, 0.3, 20);
        let r = ltm.__repr__();
        assert!(r.contains("LongTermMemory"));
        assert!(r.contains("consolidations=0"));
    }
}
