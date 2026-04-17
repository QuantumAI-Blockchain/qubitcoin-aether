//! MemoryManager — Three-tier biologically-inspired memory system.
//!
//! A Rust/PyO3 port of the Python `aether/memory_manager.py`. Provides:
//!
//! - **Working Memory (Tier 1):** Fixed-capacity buffer of recently-accessed
//!   knowledge graph node IDs with relevance scores that decay over time.
//! - **Episodic Memory (Tier 2):** Chronological record of reasoning episodes
//!   (strategy, inputs, success/failure, confidence).
//! - **Semantic Memory (Tier 3):** The existing KnowledgeGraph (external —
//!   consolidation with KG happens on the Python side).
//!
//! Unlike the Python version, this Rust `MemoryManager` is standalone and does
//! **not** hold a reference to the KnowledgeGraph. KG-dependent operations
//! (confidence boosting during consolidation, axiom promotion during replay)
//! are performed by the Python wrapper that calls into this Rust accelerator
//! for the hot-path operations (attend/decay/retrieve/scoring/episode storage).

use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::working_memory::WorkingMemoryItem;

/// Get current unix timestamp as f64 seconds.
fn now_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

// ---------------------------------------------------------------------------
// Episode
// ---------------------------------------------------------------------------

/// A recorded reasoning episode with its context and outcome.
///
/// Fields map 1:1 to the Python `Episode` dataclass in `memory_manager.py`.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct Episode {
    pub episode_id: i64,
    pub block_height: i64,
    pub input_node_ids: Vec<i64>,
    pub reasoning_strategy: String,
    pub conclusion_node_id: Option<i64>,
    pub success: bool,
    pub confidence: f64,
    pub timestamp: f64,
    pub replay_count: i64,
}

#[pymethods]
impl Episode {
    #[new]
    #[pyo3(signature = (
        episode_id = 0,
        block_height = 0,
        input_node_ids = vec![],
        reasoning_strategy = String::new(),
        conclusion_node_id = None,
        success = false,
        confidence = 0.0,
        timestamp = 0.0,
        replay_count = 0,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        episode_id: i64,
        block_height: i64,
        input_node_ids: Vec<i64>,
        reasoning_strategy: String,
        conclusion_node_id: Option<i64>,
        success: bool,
        confidence: f64,
        timestamp: f64,
        replay_count: i64,
    ) -> Self {
        Episode {
            episode_id,
            block_height,
            input_node_ids,
            reasoning_strategy,
            conclusion_node_id,
            success,
            confidence,
            timestamp,
            replay_count,
        }
    }

    /// Convert episode to a Python dict.
    pub fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("episode_id", self.episode_id)?;
        dict.set_item("block_height", self.block_height)?;
        dict.set_item("input_node_ids", self.input_node_ids.clone())?;
        dict.set_item("reasoning_strategy", &self.reasoning_strategy)?;
        dict.set_item("conclusion_node_id", self.conclusion_node_id)?;
        dict.set_item("success", self.success)?;
        dict.set_item("confidence", self.confidence)?;
        dict.set_item("timestamp", self.timestamp)?;
        dict.set_item("replay_count", self.replay_count)?;
        Ok(dict)
    }

    fn __repr__(&self) -> String {
        format!(
            "Episode(id={}, block={}, strategy='{}', success={}, confidence={:.4}, replays={})",
            self.episode_id,
            self.block_height,
            self.reasoning_strategy,
            self.success,
            self.confidence,
            self.replay_count,
        )
    }
}

// ---------------------------------------------------------------------------
// ReplayStats — returned from replay_episodes
// ---------------------------------------------------------------------------

/// Statistics returned by `MemoryManager.replay_episodes()`.
///
/// Mirrors the Python dict with keys: episodes_replayed, reinforced,
/// suppressed, promoted_to_axiom.
#[derive(Clone, Debug, Default)]
struct ReplayStats {
    episodes_replayed: i64,
    reinforced: i64,
    suppressed: i64,
    promoted_to_axiom: i64,
}

// ---------------------------------------------------------------------------
// MemoryManager
// ---------------------------------------------------------------------------

/// Three-tier memory system for the Aether Tree AI engine.
///
/// Provides Rust-accelerated working memory and episodic memory operations.
/// KG-dependent consolidation (confidence boosting, axiom promotion) is done
/// on the Python side — this struct is standalone with no KG reference.
///
/// # Python API
///
/// ## Working Memory (Tier 1)
/// - `attend(node_id, boost=0.3)` — add or boost a node
/// - `retrieve(top_k=10)` — return top-k node IDs by relevance
/// - `decay(factor=0.95)` — decay all relevance scores
/// - `contains(node_id)` — check membership
/// - `get_hit_rate()` — cache hit ratio
///
/// ## Episodic Memory (Tier 2)
/// - `record_episode(...)` — store a reasoning episode
/// - `recall_similar(strategy, success_only, limit)` — find matching episodes
/// - `get_success_rate(strategy)` — success rate for a strategy
///
/// ## Consolidation helpers
/// - `get_frequently_accessed(threshold=5)` — items with access_count > threshold
/// - `prune_old_episodes(cutoff_block)` — remove episodes before cutoff
/// - `score_episodes_for_replay(block_height, top_k)` — importance-scored episodes
/// - `increment_replay_count(episode_id)` — bump replay count
/// - `track_strategy_success(strategy)` — track successful replays
/// - `get_promotable_strategies(threshold=5)` — strategies ready for axiom promotion
/// - `reset_strategy_count(strategy)` — reset after promotion
///
/// ## Stats
/// - `get_stats()` — full statistics dict
#[pyclass]
pub struct MemoryManager {
    // -- Working Memory (Tier 1) --
    working_memory: HashMap<i64, WorkingMemoryItem>,
    capacity: usize,
    attend_calls: i64,
    attend_hits: i64,

    // -- Episodic Memory (Tier 2) --
    episodes: Vec<Episode>,
    max_episodes: usize,
    next_episode_id: i64,

    // -- Replay tracking --
    /// strategy name -> successful replay count
    strategy_replay_success: HashMap<String, i64>,

    // -- Stats --
    consolidations_total: i64,
    replay_total: i64,
}

#[pymethods]
impl MemoryManager {
    /// Create a new MemoryManager.
    ///
    /// # Arguments
    /// - `capacity`: Maximum working memory size (default 50).
    /// - `max_episodes`: Maximum episodic memory size (default 1000).
    #[new]
    #[pyo3(signature = (capacity = 50, max_episodes = 1000))]
    pub fn new(capacity: usize, max_episodes: usize) -> Self {
        MemoryManager {
            working_memory: HashMap::with_capacity(capacity),
            capacity,
            attend_calls: 0,
            attend_hits: 0,
            episodes: Vec::with_capacity(max_episodes.min(1024)),
            max_episodes,
            next_episode_id: 1,
            strategy_replay_success: HashMap::new(),
            consolidations_total: 0,
            replay_total: 0,
        }
    }

    // -----------------------------------------------------------------------
    // Working Memory (Tier 1)
    // -----------------------------------------------------------------------

    /// Add or boost a node in working memory.
    ///
    /// If the node is already present, its relevance is boosted and access
    /// count incremented (cache hit). If at capacity, the lowest-relevance
    /// item is evicted to make room.
    ///
    /// # Arguments
    /// - `node_id`: Knowledge graph node ID.
    /// - `boost`: Relevance boost for new items or existing items (default 0.3).
    #[pyo3(signature = (node_id, boost = 0.3))]
    pub fn attend(&mut self, node_id: i64, boost: f64) {
        self.attend_calls += 1;
        let now = now_timestamp();

        if let Some(item) = self.working_memory.get_mut(&node_id) {
            // Cache hit
            self.attend_hits += 1;
            item.relevance = (item.relevance + boost).min(1.0);
            item.last_access = now;
            item.access_count += 1;
            return;
        }

        // New item — evict if at capacity
        if self.working_memory.len() >= self.capacity {
            self.evict_lowest();
        }

        self.working_memory.insert(
            node_id,
            WorkingMemoryItem {
                node_id,
                relevance: boost.clamp(0.0, 1.0),
                last_access: now,
                access_count: 1,
            },
        );
    }

    /// Return the top-k node IDs sorted by relevance (highest first).
    ///
    /// # Arguments
    /// - `top_k`: Number of node IDs to return (default 10).
    #[pyo3(signature = (top_k = 10))]
    pub fn retrieve(&self, top_k: usize) -> Vec<i64> {
        if self.working_memory.is_empty() {
            return Vec::new();
        }

        let mut items: Vec<&WorkingMemoryItem> = self.working_memory.values().collect();
        items.sort_by(|a, b| {
            b.relevance
                .partial_cmp(&a.relevance)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let limit = top_k.min(items.len());
        items[..limit].iter().map(|item| item.node_id).collect()
    }

    /// Multiply all relevance scores by a decay factor. Remove items below 0.01.
    ///
    /// # Arguments
    /// - `factor`: Multiplicative decay factor (default 0.95).
    #[pyo3(signature = (factor = 0.95))]
    pub fn decay(&mut self, factor: f64) {
        let mut to_remove = Vec::new();
        for (node_id, item) in self.working_memory.iter_mut() {
            item.relevance *= factor;
            if item.relevance < 0.01 {
                to_remove.push(*node_id);
            }
        }
        for node_id in to_remove {
            self.working_memory.remove(&node_id);
        }
    }

    /// Check if a node is currently in working memory.
    pub fn contains(&self, node_id: i64) -> bool {
        self.working_memory.contains_key(&node_id)
    }

    /// Fraction of attend() calls that found an existing item (cache hit rate).
    pub fn get_hit_rate(&self) -> f64 {
        if self.attend_calls == 0 {
            return 0.0;
        }
        self.attend_hits as f64 / self.attend_calls as f64
    }

    /// Current number of items in working memory.
    pub fn working_memory_size(&self) -> usize {
        self.working_memory.len()
    }

    /// Get all working memory items (for Python-side consolidation).
    pub fn get_working_memory_items(&self) -> Vec<WorkingMemoryItem> {
        self.working_memory.values().cloned().collect()
    }

    /// Get a specific working memory item by node_id, or None.
    pub fn get_working_memory_item(&self, node_id: i64) -> Option<WorkingMemoryItem> {
        self.working_memory.get(&node_id).cloned()
    }

    /// Return node IDs in working memory with access_count above a threshold.
    ///
    /// Used by Python-side consolidation to find nodes whose confidence
    /// should be boosted in the KnowledgeGraph.
    ///
    /// # Arguments
    /// - `threshold`: Minimum access count (default 5).
    #[pyo3(signature = (threshold = 5))]
    pub fn get_frequently_accessed(&self, threshold: i64) -> Vec<WorkingMemoryItem> {
        self.working_memory
            .values()
            .filter(|item| item.access_count > threshold)
            .cloned()
            .collect()
    }

    // -----------------------------------------------------------------------
    // Episodic Memory (Tier 2)
    // -----------------------------------------------------------------------

    /// Record a reasoning episode.
    ///
    /// # Arguments
    /// - `block_height`: Block height when the episode occurred.
    /// - `input_ids`: Node IDs used as input.
    /// - `strategy`: Reasoning strategy name.
    /// - `conclusion_id`: Conclusion node ID (None if no conclusion).
    /// - `success`: Whether the reasoning succeeded.
    /// - `confidence`: Confidence of the outcome.
    ///
    /// # Returns
    /// The recorded `Episode`.
    #[pyo3(signature = (block_height, input_ids, strategy, conclusion_id = None, success = false, confidence = 0.0))]
    pub fn record_episode(
        &mut self,
        block_height: i64,
        input_ids: Vec<i64>,
        strategy: String,
        conclusion_id: Option<i64>,
        success: bool,
        confidence: f64,
    ) -> Episode {
        let episode = Episode {
            episode_id: self.next_episode_id,
            block_height,
            input_node_ids: input_ids,
            reasoning_strategy: strategy,
            conclusion_node_id: conclusion_id,
            success,
            confidence,
            timestamp: now_timestamp(),
            replay_count: 0,
        };
        self.next_episode_id += 1;
        self.episodes.push(episode.clone());

        // FIFO eviction — keep only the last max_episodes
        if self.episodes.len() > self.max_episodes {
            let drain_count = self.episodes.len() - self.max_episodes;
            self.episodes.drain(..drain_count);
        }

        episode
    }

    /// Find similar past episodes by strategy and success.
    ///
    /// Returns matching episodes in reverse chronological order (most recent first).
    ///
    /// # Arguments
    /// - `strategy`: Filter by strategy name (empty = all).
    /// - `success_only`: If true, only return successful episodes (default true).
    /// - `limit`: Maximum results (default 10).
    #[pyo3(signature = (strategy = String::new(), success_only = true, limit = 10))]
    pub fn recall_similar(
        &self,
        strategy: String,
        success_only: bool,
        limit: usize,
    ) -> Vec<Episode> {
        let mut results = Vec::with_capacity(limit);

        for episode in self.episodes.iter().rev() {
            if !strategy.is_empty() && episode.reasoning_strategy != strategy {
                continue;
            }
            if success_only && !episode.success {
                continue;
            }
            results.push(episode.clone());
            if results.len() >= limit {
                break;
            }
        }

        results
    }

    /// Get the success rate for a strategy (or overall if strategy is empty).
    ///
    /// # Returns
    /// Float between 0.0 and 1.0.
    #[pyo3(signature = (strategy = String::new()))]
    pub fn get_success_rate(&self, strategy: String) -> f64 {
        let mut total: i64 = 0;
        let mut successes: i64 = 0;

        for episode in &self.episodes {
            if !strategy.is_empty() && episode.reasoning_strategy != strategy {
                continue;
            }
            total += 1;
            if episode.success {
                successes += 1;
            }
        }

        if total == 0 {
            return 0.0;
        }
        successes as f64 / total as f64
    }

    /// Total number of recorded episodes.
    pub fn episodes_total(&self) -> usize {
        self.episodes.len()
    }

    /// Get an episode by its ID, or None.
    pub fn get_episode(&self, episode_id: i64) -> Option<Episode> {
        self.episodes
            .iter()
            .find(|ep| ep.episode_id == episode_id)
            .cloned()
    }

    /// Get the N most recent episodes.
    #[pyo3(signature = (limit = 10))]
    pub fn get_recent_episodes(&self, limit: usize) -> Vec<Episode> {
        let start = if self.episodes.len() > limit {
            self.episodes.len() - limit
        } else {
            0
        };
        self.episodes[start..].iter().rev().cloned().collect()
    }

    // -----------------------------------------------------------------------
    // Consolidation helpers (KG interaction happens on Python side)
    // -----------------------------------------------------------------------

    /// Remove episodes older than `cutoff_block`.
    ///
    /// # Returns
    /// Number of episodes pruned.
    pub fn prune_old_episodes(&mut self, cutoff_block: i64) -> usize {
        let original = self.episodes.len();
        self.episodes
            .retain(|ep| ep.block_height >= cutoff_block);
        let pruned = original - self.episodes.len();
        if pruned > 0 {
            self.consolidations_total += 1;
        }
        pruned
    }

    /// Score episodes by importance for replay and return the top-k.
    ///
    /// Importance = success_weight * recency_weight
    /// - success_weight: 1.5 for successful, 0.5 for failed
    /// - recency_weight: 1.0 / (1 + (block_height - ep.block_height) / 1000)
    ///
    /// Returns episodes sorted by importance (highest first).
    ///
    /// # Arguments
    /// - `block_height`: Current block height for recency weighting.
    /// - `top_k`: Number of episodes to select (default 10).
    #[pyo3(signature = (block_height, top_k = 10))]
    pub fn score_episodes_for_replay(&self, block_height: i64, top_k: usize) -> Vec<Episode> {
        if self.episodes.is_empty() {
            return Vec::new();
        }

        let mut scored: Vec<(f64, &Episode)> = self
            .episodes
            .iter()
            .map(|ep| {
                let success_weight = if ep.success { 1.5 } else { 0.5 };
                let age = (block_height - ep.block_height).max(0) as f64;
                let recency_weight = 1.0 / (1.0 + age / 1000.0);
                let importance = success_weight * recency_weight;
                (importance, ep)
            })
            .collect();

        scored.sort_by(|a, b| {
            b.0.partial_cmp(&a.0)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let limit = top_k.min(scored.len());
        scored[..limit]
            .iter()
            .map(|(_, ep)| (*ep).clone())
            .collect()
    }

    /// Increment an episode's replay count by 1.
    ///
    /// # Returns
    /// True if the episode was found and incremented.
    pub fn increment_replay_count(&mut self, episode_id: i64) -> bool {
        if let Some(ep) = self
            .episodes
            .iter_mut()
            .find(|ep| ep.episode_id == episode_id)
        {
            ep.replay_count += 1;
            true
        } else {
            false
        }
    }

    /// Track a successful replay for a strategy.
    pub fn track_strategy_success(&mut self, strategy: String) {
        *self.strategy_replay_success.entry(strategy).or_insert(0) += 1;
    }

    /// Return strategies whose successful replay count meets or exceeds a threshold.
    ///
    /// These are candidates for promotion to axiom nodes in the KG.
    ///
    /// # Arguments
    /// - `threshold`: Minimum replay count for promotion (default 5).
    ///
    /// # Returns
    /// Vec of (strategy_name, replay_count) tuples.
    #[pyo3(signature = (threshold = 5))]
    pub fn get_promotable_strategies(&self, threshold: i64) -> Vec<(String, i64)> {
        self.strategy_replay_success
            .iter()
            .filter(|(_, count)| **count >= threshold)
            .map(|(strategy, count)| (strategy.clone(), *count))
            .collect()
    }

    /// Reset a strategy's replay success count (call after promoting to axiom).
    pub fn reset_strategy_count(&mut self, strategy: String) {
        self.strategy_replay_success.insert(strategy, 0);
    }

    /// Increment the global consolidation counter.
    pub fn increment_consolidations(&mut self) {
        self.consolidations_total += 1;
    }

    /// Increment the global replay counter.
    pub fn increment_replay_total(&mut self) {
        self.replay_total += 1;
    }

    // -----------------------------------------------------------------------
    // Stats
    // -----------------------------------------------------------------------

    /// Get comprehensive memory manager statistics.
    ///
    /// Returns a dict matching the Python `MemoryManager.get_stats()` shape:
    /// - working_memory_size, working_memory_capacity, working_memory_hit_rate
    /// - episodes_total, episodes_successful
    /// - consolidations_total, replay_total
    /// - strategy_replay_success (dict)
    pub fn get_stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(py);

        // Working memory stats
        dict.set_item("working_memory_size", self.working_memory.len())?;
        dict.set_item("working_memory_capacity", self.capacity)?;

        let hit_rate = self.get_hit_rate();
        let hit_rate_rounded = (hit_rate * 10000.0).round() / 10000.0;
        dict.set_item("working_memory_hit_rate", hit_rate_rounded)?;

        // Episodic memory stats
        dict.set_item("episodes_total", self.episodes.len())?;
        let successful = self.episodes.iter().filter(|ep| ep.success).count();
        dict.set_item("episodes_successful", successful)?;

        // Consolidation stats
        dict.set_item("consolidations_total", self.consolidations_total)?;
        dict.set_item("replay_total", self.replay_total)?;

        // Strategy replay success (as Python dict)
        let strategy_dict = PyDict::new(py);
        for (strategy, count) in &self.strategy_replay_success {
            strategy_dict.set_item(strategy, count)?;
        }
        dict.set_item("strategy_replay_success", strategy_dict)?;

        Ok(dict)
    }

    /// Working memory capacity getter.
    #[getter]
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Maximum episodes limit getter.
    #[getter]
    pub fn max_episodes(&self) -> usize {
        self.max_episodes
    }

    fn __repr__(&self) -> String {
        format!(
            "MemoryManager(wm_size={}/{}, episodes={}/{}, hit_rate={:.4}, consolidations={}, replays={})",
            self.working_memory.len(),
            self.capacity,
            self.episodes.len(),
            self.max_episodes,
            self.get_hit_rate(),
            self.consolidations_total,
            self.replay_total,
        )
    }
}

// Internal methods (not exposed to Python)
impl MemoryManager {
    /// Evict the item with the lowest relevance from working memory.
    fn evict_lowest(&mut self) {
        if self.working_memory.is_empty() {
            return;
        }
        let lowest_id = self
            .working_memory
            .iter()
            .min_by(|a, b| {
                a.1.relevance
                    .partial_cmp(&b.1.relevance)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .map(|(id, _)| *id);

        if let Some(id) = lowest_id {
            self.working_memory.remove(&id);
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- Episode tests --

    #[test]
    fn test_episode_creation() {
        let ep = Episode::new(
            1,
            100,
            vec![10, 20, 30],
            "deductive".into(),
            Some(40),
            true,
            0.85,
            1000.0,
            0,
        );
        assert_eq!(ep.episode_id, 1);
        assert_eq!(ep.block_height, 100);
        assert_eq!(ep.input_node_ids, vec![10, 20, 30]);
        assert_eq!(ep.reasoning_strategy, "deductive");
        assert_eq!(ep.conclusion_node_id, Some(40));
        assert!(ep.success);
        assert!((ep.confidence - 0.85).abs() < f64::EPSILON);
        assert_eq!(ep.replay_count, 0);
    }

    #[test]
    fn test_episode_defaults() {
        let ep = Episode::new(
            0,
            0,
            vec![],
            String::new(),
            None,
            false,
            0.0,
            0.0,
            0,
        );
        assert_eq!(ep.episode_id, 0);
        assert!(ep.input_node_ids.is_empty());
        assert_eq!(ep.conclusion_node_id, None);
        assert!(!ep.success);
    }

    #[test]
    fn test_episode_clone() {
        let ep = Episode::new(5, 200, vec![1, 2], "inductive".into(), Some(3), true, 0.9, 500.0, 2);
        let cloned = ep.clone();
        assert_eq!(cloned.episode_id, ep.episode_id);
        assert_eq!(cloned.block_height, ep.block_height);
        assert_eq!(cloned.input_node_ids, ep.input_node_ids);
        assert_eq!(cloned.reasoning_strategy, ep.reasoning_strategy);
        assert_eq!(cloned.replay_count, ep.replay_count);
    }

    #[test]
    fn test_episode_repr() {
        let ep = Episode::new(1, 100, vec![], "deductive".into(), None, true, 0.85, 0.0, 3);
        let repr = ep.__repr__();
        assert!(repr.contains("id=1"));
        assert!(repr.contains("deductive"));
        assert!(repr.contains("success=true"));
        assert!(repr.contains("replays=3"));
    }

    // -- MemoryManager: Working Memory tests --

    #[test]
    fn test_mm_new() {
        let mm = MemoryManager::new(50, 1000);
        assert_eq!(mm.capacity(), 50);
        assert_eq!(mm.max_episodes(), 1000);
        assert_eq!(mm.working_memory_size(), 0);
        assert_eq!(mm.episodes_total(), 0);
    }

    #[test]
    fn test_attend_new_item() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(42, 0.5);
        assert!(mm.contains(42));
        assert_eq!(mm.working_memory_size(), 1);
    }

    #[test]
    fn test_attend_boost_existing() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 0.3);

        let item_before = mm.get_working_memory_item(1).unwrap();
        assert!((item_before.relevance - 0.3).abs() < f64::EPSILON);
        assert_eq!(item_before.access_count, 1);

        mm.attend(1, 0.2);

        let item_after = mm.get_working_memory_item(1).unwrap();
        assert!((item_after.relevance - 0.5).abs() < f64::EPSILON);
        assert_eq!(item_after.access_count, 2);
    }

    #[test]
    fn test_attend_clamp_at_one() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 0.8);
        mm.attend(1, 0.5); // 0.8 + 0.5 = 1.3 -> clamped to 1.0
        let item = mm.get_working_memory_item(1).unwrap();
        assert!((item.relevance - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_attend_new_item_clamp() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 1.5); // Should be clamped to 1.0
        let item = mm.get_working_memory_item(1).unwrap();
        assert!((item.relevance - 1.0).abs() < f64::EPSILON);

        let mut mm2 = MemoryManager::new(10, 100);
        mm2.attend(2, -0.5); // Should be clamped to 0.0
        let item2 = mm2.get_working_memory_item(2).unwrap();
        assert!((item2.relevance - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_attend_eviction_at_capacity() {
        let mut mm = MemoryManager::new(3, 100);
        mm.attend(1, 0.3);
        mm.attend(2, 0.5);
        mm.attend(3, 0.8);
        assert_eq!(mm.working_memory_size(), 3);

        // Node 1 has lowest relevance (0.3), should be evicted
        mm.attend(4, 0.6);
        assert_eq!(mm.working_memory_size(), 3);
        assert!(!mm.contains(1));
        assert!(mm.contains(2));
        assert!(mm.contains(3));
        assert!(mm.contains(4));
    }

    #[test]
    fn test_hit_rate() {
        let mut mm = MemoryManager::new(10, 100);
        assert!((mm.get_hit_rate() - 0.0).abs() < f64::EPSILON);

        mm.attend(1, 0.5); // miss
        mm.attend(2, 0.5); // miss
        mm.attend(1, 0.1); // hit
        mm.attend(2, 0.1); // hit

        // 2 hits out of 4 calls = 0.5
        assert!((mm.get_hit_rate() - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_retrieve_empty() {
        let mm = MemoryManager::new(10, 100);
        let result = mm.retrieve(10);
        assert!(result.is_empty());
    }

    #[test]
    fn test_retrieve_sorted_by_relevance() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 0.3);
        mm.attend(2, 0.9);
        mm.attend(3, 0.6);

        let result = mm.retrieve(10);
        assert_eq!(result, vec![2, 3, 1]);
    }

    #[test]
    fn test_retrieve_top_k() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 0.3);
        mm.attend(2, 0.9);
        mm.attend(3, 0.6);
        mm.attend(4, 0.1);

        let result = mm.retrieve(2);
        assert_eq!(result.len(), 2);
        assert_eq!(result[0], 2); // highest relevance
        assert_eq!(result[1], 3);
    }

    #[test]
    fn test_decay() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 1.0);
        mm.attend(2, 0.5);

        mm.decay(0.5);

        let item1 = mm.get_working_memory_item(1).unwrap();
        assert!((item1.relevance - 0.5).abs() < f64::EPSILON);
        let item2 = mm.get_working_memory_item(2).unwrap();
        assert!((item2.relevance - 0.25).abs() < f64::EPSILON);
    }

    #[test]
    fn test_decay_removes_below_threshold() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 0.02);
        mm.attend(2, 0.8);

        // After 0.4 decay: node 1 = 0.008 (< 0.01 removed), node 2 = 0.32
        mm.decay(0.4);

        assert!(!mm.contains(1));
        assert!(mm.contains(2));
    }

    #[test]
    fn test_decay_default_factor() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 1.0);
        mm.decay(0.95);
        let item = mm.get_working_memory_item(1).unwrap();
        assert!((item.relevance - 0.95).abs() < f64::EPSILON);
    }

    #[test]
    fn test_frequently_accessed() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 0.5);
        // Attend node 1 six times total (first attend + 5 more = access_count=6)
        for _ in 0..5 {
            mm.attend(1, 0.01);
        }
        mm.attend(2, 0.5); // Only 1 access

        let frequent = mm.get_frequently_accessed(5);
        assert_eq!(frequent.len(), 1);
        assert_eq!(frequent[0].node_id, 1);
        assert_eq!(frequent[0].access_count, 6);
    }

    #[test]
    fn test_get_all_working_memory_items() {
        let mut mm = MemoryManager::new(10, 100);
        mm.attend(1, 0.5);
        mm.attend(2, 0.6);
        mm.attend(3, 0.7);

        let items = mm.get_working_memory_items();
        assert_eq!(items.len(), 3);
        let mut ids: Vec<i64> = items.iter().map(|i| i.node_id).collect();
        ids.sort();
        assert_eq!(ids, vec![1, 2, 3]);
    }

    // -- MemoryManager: Episodic Memory tests --

    #[test]
    fn test_record_episode() {
        let mut mm = MemoryManager::new(10, 100);
        let ep = mm.record_episode(100, vec![1, 2, 3], "deductive".into(), Some(4), true, 0.85);

        assert_eq!(ep.episode_id, 1);
        assert_eq!(ep.block_height, 100);
        assert_eq!(ep.input_node_ids, vec![1, 2, 3]);
        assert_eq!(ep.reasoning_strategy, "deductive");
        assert_eq!(ep.conclusion_node_id, Some(4));
        assert!(ep.success);
        assert!((ep.confidence - 0.85).abs() < f64::EPSILON);
        assert_eq!(ep.replay_count, 0);
        assert!(ep.timestamp > 0.0);

        assert_eq!(mm.episodes_total(), 1);
    }

    #[test]
    fn test_record_episode_auto_increments_id() {
        let mut mm = MemoryManager::new(10, 100);
        let ep1 = mm.record_episode(100, vec![], "a".into(), None, false, 0.0);
        let ep2 = mm.record_episode(101, vec![], "b".into(), None, false, 0.0);
        let ep3 = mm.record_episode(102, vec![], "c".into(), None, false, 0.0);

        assert_eq!(ep1.episode_id, 1);
        assert_eq!(ep2.episode_id, 2);
        assert_eq!(ep3.episode_id, 3);
    }

    #[test]
    fn test_record_episode_fifo_eviction() {
        let mut mm = MemoryManager::new(10, 5); // max 5 episodes
        for i in 0..8 {
            mm.record_episode(i, vec![], "x".into(), None, false, 0.0);
        }

        assert_eq!(mm.episodes_total(), 5);
        // First 3 should have been evicted
        assert!(mm.get_episode(1).is_none());
        assert!(mm.get_episode(2).is_none());
        assert!(mm.get_episode(3).is_none());
        // Last 5 should remain
        assert!(mm.get_episode(4).is_some());
        assert!(mm.get_episode(8).is_some());
    }

    #[test]
    fn test_recall_similar_all() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![1], "deductive".into(), Some(2), true, 0.8);
        mm.record_episode(101, vec![3], "inductive".into(), Some(4), true, 0.7);
        mm.record_episode(102, vec![5], "deductive".into(), None, false, 0.3);

        // All successful (default success_only=true)
        let results = mm.recall_similar(String::new(), true, 10);
        assert_eq!(results.len(), 2);
        // Most recent first
        assert_eq!(results[0].episode_id, 2);
        assert_eq!(results[1].episode_id, 1);
    }

    #[test]
    fn test_recall_similar_by_strategy() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![1], "deductive".into(), Some(2), true, 0.8);
        mm.record_episode(101, vec![3], "inductive".into(), Some(4), true, 0.7);
        mm.record_episode(102, vec![5], "deductive".into(), Some(6), true, 0.9);

        let results = mm.recall_similar("deductive".into(), true, 10);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].reasoning_strategy, "deductive");
        assert_eq!(results[1].reasoning_strategy, "deductive");
    }

    #[test]
    fn test_recall_similar_include_failures() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![1], "x".into(), None, false, 0.1);
        mm.record_episode(101, vec![2], "x".into(), Some(3), true, 0.9);

        let results = mm.recall_similar(String::new(), false, 10);
        assert_eq!(results.len(), 2);
    }

    #[test]
    fn test_recall_similar_limit() {
        let mut mm = MemoryManager::new(10, 100);
        for i in 0..20 {
            mm.record_episode(i, vec![], "x".into(), None, true, 0.5);
        }

        let results = mm.recall_similar(String::new(), true, 5);
        assert_eq!(results.len(), 5);
    }

    #[test]
    fn test_get_success_rate_overall() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![], "a".into(), None, true, 0.8);
        mm.record_episode(101, vec![], "a".into(), None, false, 0.2);
        mm.record_episode(102, vec![], "b".into(), None, true, 0.9);
        mm.record_episode(103, vec![], "b".into(), None, true, 0.7);

        // Overall: 3/4 = 0.75
        let rate = mm.get_success_rate(String::new());
        assert!((rate - 0.75).abs() < f64::EPSILON);
    }

    #[test]
    fn test_get_success_rate_by_strategy() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![], "deductive".into(), None, true, 0.8);
        mm.record_episode(101, vec![], "deductive".into(), None, false, 0.2);
        mm.record_episode(102, vec![], "inductive".into(), None, true, 0.9);

        // deductive: 1/2 = 0.5
        assert!((mm.get_success_rate("deductive".into()) - 0.5).abs() < f64::EPSILON);
        // inductive: 1/1 = 1.0
        assert!((mm.get_success_rate("inductive".into()) - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_get_success_rate_empty() {
        let mm = MemoryManager::new(10, 100);
        assert!((mm.get_success_rate(String::new()) - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_get_success_rate_no_matching_strategy() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![], "deductive".into(), None, true, 0.8);
        assert!((mm.get_success_rate("nonexistent".into()) - 0.0).abs() < f64::EPSILON);
    }

    // -- Consolidation helper tests --

    #[test]
    fn test_prune_old_episodes() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![], "a".into(), None, true, 0.5);
        mm.record_episode(5000, vec![], "b".into(), None, true, 0.5);
        mm.record_episode(15000, vec![], "c".into(), None, true, 0.5);

        // Cutoff at block 5000: episodes at block 100 should be pruned
        let pruned = mm.prune_old_episodes(5000);
        assert_eq!(pruned, 1);
        assert_eq!(mm.episodes_total(), 2);
    }

    #[test]
    fn test_prune_old_episodes_none_pruned() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![], "a".into(), None, true, 0.5);
        mm.record_episode(200, vec![], "b".into(), None, true, 0.5);

        let pruned = mm.prune_old_episodes(50);
        assert_eq!(pruned, 0);
        assert_eq!(mm.episodes_total(), 2);
    }

    #[test]
    fn test_score_episodes_for_replay_empty() {
        let mm = MemoryManager::new(10, 100);
        let scored = mm.score_episodes_for_replay(1000, 10);
        assert!(scored.is_empty());
    }

    #[test]
    fn test_score_episodes_for_replay_success_preferred() {
        let mut mm = MemoryManager::new(10, 100);
        // Same recency, but different success
        mm.record_episode(100, vec![], "a".into(), None, false, 0.3);
        mm.record_episode(100, vec![], "b".into(), None, true, 0.8);

        let scored = mm.score_episodes_for_replay(100, 10);
        assert_eq!(scored.len(), 2);
        // Successful episode should be ranked first (1.5 > 0.5 when same recency)
        assert!(scored[0].success);
        assert!(!scored[1].success);
    }

    #[test]
    fn test_score_episodes_for_replay_recency() {
        let mut mm = MemoryManager::new(10, 100);
        // Both successful, different recency
        mm.record_episode(0, vec![], "old".into(), None, true, 0.8);
        mm.record_episode(990, vec![], "recent".into(), None, true, 0.8);

        let scored = mm.score_episodes_for_replay(1000, 10);
        assert_eq!(scored.len(), 2);
        // More recent episode should rank higher
        assert_eq!(scored[0].reasoning_strategy, "recent");
    }

    #[test]
    fn test_score_episodes_top_k_limit() {
        let mut mm = MemoryManager::new(10, 100);
        for i in 0..20 {
            mm.record_episode(i, vec![], "x".into(), None, true, 0.5);
        }
        let scored = mm.score_episodes_for_replay(1000, 5);
        assert_eq!(scored.len(), 5);
    }

    #[test]
    fn test_increment_replay_count() {
        let mut mm = MemoryManager::new(10, 100);
        let ep = mm.record_episode(100, vec![], "a".into(), None, true, 0.5);
        assert_eq!(ep.replay_count, 0);

        assert!(mm.increment_replay_count(1));
        assert!(mm.increment_replay_count(1));

        let ep_after = mm.get_episode(1).unwrap();
        assert_eq!(ep_after.replay_count, 2);
    }

    #[test]
    fn test_increment_replay_count_nonexistent() {
        let mut mm = MemoryManager::new(10, 100);
        assert!(!mm.increment_replay_count(999));
    }

    #[test]
    fn test_track_strategy_success() {
        let mut mm = MemoryManager::new(10, 100);
        mm.track_strategy_success("deductive".into());
        mm.track_strategy_success("deductive".into());
        mm.track_strategy_success("inductive".into());

        let promotable = mm.get_promotable_strategies(2);
        assert_eq!(promotable.len(), 1);
        assert_eq!(promotable[0].0, "deductive");
        assert_eq!(promotable[0].1, 2);
    }

    #[test]
    fn test_get_promotable_strategies() {
        let mut mm = MemoryManager::new(10, 100);
        for _ in 0..5 {
            mm.track_strategy_success("deductive".into());
        }
        for _ in 0..3 {
            mm.track_strategy_success("inductive".into());
        }

        let promotable = mm.get_promotable_strategies(5);
        assert_eq!(promotable.len(), 1);
        assert_eq!(promotable[0].0, "deductive");
        assert_eq!(promotable[0].1, 5);

        let promotable_lower = mm.get_promotable_strategies(3);
        assert_eq!(promotable_lower.len(), 2);
    }

    #[test]
    fn test_reset_strategy_count() {
        let mut mm = MemoryManager::new(10, 100);
        for _ in 0..10 {
            mm.track_strategy_success("deductive".into());
        }
        mm.reset_strategy_count("deductive".into());

        let promotable = mm.get_promotable_strategies(1);
        assert!(promotable.is_empty()); // Count was reset to 0
    }

    #[test]
    fn test_get_recent_episodes() {
        let mut mm = MemoryManager::new(10, 100);
        for i in 0..10 {
            mm.record_episode(i * 100, vec![], format!("s{}", i), None, true, 0.5);
        }

        let recent = mm.get_recent_episodes(3);
        assert_eq!(recent.len(), 3);
        // Most recent first
        assert_eq!(recent[0].episode_id, 10);
        assert_eq!(recent[1].episode_id, 9);
        assert_eq!(recent[2].episode_id, 8);
    }

    #[test]
    fn test_get_recent_episodes_fewer_than_limit() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![], "a".into(), None, true, 0.5);

        let recent = mm.get_recent_episodes(10);
        assert_eq!(recent.len(), 1);
    }

    // -- Stats test --

    #[test]
    fn test_get_episode_by_id() {
        let mut mm = MemoryManager::new(10, 100);
        mm.record_episode(100, vec![1, 2], "deductive".into(), Some(3), true, 0.9);
        mm.record_episode(200, vec![4, 5], "inductive".into(), None, false, 0.3);

        let ep = mm.get_episode(1).unwrap();
        assert_eq!(ep.block_height, 100);
        assert_eq!(ep.reasoning_strategy, "deductive");

        let ep2 = mm.get_episode(2).unwrap();
        assert_eq!(ep2.block_height, 200);

        assert!(mm.get_episode(999).is_none());
    }

    #[test]
    fn test_consolidation_and_replay_counters() {
        let mut mm = MemoryManager::new(10, 100);
        assert_eq!(mm.consolidations_total, 0);
        assert_eq!(mm.replay_total, 0);

        mm.increment_consolidations();
        mm.increment_consolidations();
        mm.increment_replay_total();

        assert_eq!(mm.consolidations_total, 2);
        assert_eq!(mm.replay_total, 1);
    }

    #[test]
    fn test_repr() {
        let mm = MemoryManager::new(50, 1000);
        let repr = mm.__repr__();
        assert!(repr.contains("wm_size=0/50"));
        assert!(repr.contains("episodes=0/1000"));
        assert!(repr.contains("hit_rate=0.0000"));
    }

    // -- Integration-style tests --

    #[test]
    fn test_full_working_memory_lifecycle() {
        let mut mm = MemoryManager::new(5, 100);

        // Phase 1: Fill working memory
        for i in 1..=5 {
            mm.attend(i, i as f64 * 0.1);
        }
        assert_eq!(mm.working_memory_size(), 5);

        // Phase 2: Boost a few items
        mm.attend(3, 0.2);
        mm.attend(3, 0.2);
        mm.attend(5, 0.1);

        // Phase 3: Retrieve top items
        let top = mm.retrieve(3);
        assert_eq!(top.len(), 3);
        // Node 3 was boosted most (0.3 + 0.2 + 0.2 = 0.7), node 5 was 0.5+0.1=0.6
        assert_eq!(top[0], 3);
        assert_eq!(top[1], 5);

        // Phase 4: Decay
        mm.decay(0.5);
        let item3 = mm.get_working_memory_item(3).unwrap();
        assert!((item3.relevance - 0.35).abs() < f64::EPSILON);

        // Phase 5: Check hit rate (5 misses + 3 hits = 3/8)
        assert!((mm.get_hit_rate() - 3.0 / 8.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_full_episodic_lifecycle() {
        let mut mm = MemoryManager::new(10, 100);

        // Record a series of episodes
        mm.record_episode(100, vec![1, 2], "deductive".into(), Some(3), true, 0.9);
        mm.record_episode(200, vec![4, 5], "inductive".into(), None, false, 0.2);
        mm.record_episode(300, vec![6], "deductive".into(), Some(7), true, 0.85);
        mm.record_episode(400, vec![8, 9], "abductive".into(), Some(10), true, 0.7);

        // Overall success rate: 3/4 = 0.75
        assert!((mm.get_success_rate(String::new()) - 0.75).abs() < f64::EPSILON);

        // Deductive success rate: 2/2 = 1.0
        assert!((mm.get_success_rate("deductive".into()) - 1.0).abs() < f64::EPSILON);

        // Inductive success rate: 0/1 = 0.0
        assert!((mm.get_success_rate("inductive".into()) - 0.0).abs() < f64::EPSILON);

        // Recall similar (deductive, success_only)
        let recalled = mm.recall_similar("deductive".into(), true, 10);
        assert_eq!(recalled.len(), 2);
        assert_eq!(recalled[0].block_height, 300); // Most recent first

        // Score for replay at block 500
        let scored = mm.score_episodes_for_replay(500, 2);
        assert_eq!(scored.len(), 2);
        // Most recent successful episodes should rank highest
        assert!(scored[0].success);

        // Prune old episodes (cutoff at block 250)
        let pruned = mm.prune_old_episodes(250);
        assert_eq!(pruned, 2); // Episodes at 100 and 200
        assert_eq!(mm.episodes_total(), 2);
    }

    #[test]
    fn test_strategy_promotion_flow() {
        let mut mm = MemoryManager::new(10, 100);

        // Simulate 5 successful replays of "deductive"
        for _ in 0..5 {
            mm.track_strategy_success("deductive".into());
        }

        // Should be promotable (>= 5 replays)
        let promotable = mm.get_promotable_strategies(5);
        assert_eq!(promotable.len(), 1);
        assert_eq!(promotable[0].0, "deductive");
        assert_eq!(promotable[0].1, 5);

        // After promotion, reset count
        mm.reset_strategy_count("deductive".into());
        let promotable_after = mm.get_promotable_strategies(5);
        assert!(promotable_after.is_empty());
    }

    #[test]
    fn test_eviction_preserves_highest_relevance() {
        let mut mm = MemoryManager::new(3, 100);
        mm.attend(1, 0.1);
        mm.attend(2, 0.5);
        mm.attend(3, 0.9);

        // Fill is at 3 items. Add node 4 with medium relevance.
        // Should evict node 1 (0.1, lowest).
        mm.attend(4, 0.4);
        assert!(!mm.contains(1));
        assert!(mm.contains(2));
        assert!(mm.contains(3));
        assert!(mm.contains(4));

        // Add node 5 with low relevance.
        // Should evict node 4 (0.4) since 2=0.5, 3=0.9, 4=0.4
        mm.attend(5, 0.3);
        assert!(!mm.contains(4));
        assert!(mm.contains(5));
    }
}
