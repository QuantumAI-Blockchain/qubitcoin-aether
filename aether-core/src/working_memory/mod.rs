//! WorkingMemory — Fixed-capacity attention buffer with relevance decay.
//!
//! A simplified standalone working memory module inspired by Miller's number (7 +/- 2).
//! Items are stored with a relevance score that decays over time. When capacity is
//! reached, the least-relevant item is evicted. This module provides the core buffer
//! mechanism; the full three-tier memory system lives in [`MemoryManager`].
//!
//! Exposed to Python via PyO3 as `aether_core.WorkingMemoryItem` and
//! `aether_core.WorkingMemory`.

use pyo3::prelude::*;
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

/// Get current unix timestamp as f64 seconds.
fn now_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

// ---------------------------------------------------------------------------
// WorkingMemoryItem
// ---------------------------------------------------------------------------

/// A single item in working memory, tracking a knowledge graph node's relevance.
///
/// Fields:
/// - `node_id`: Knowledge graph node ID being attended to.
/// - `relevance`: Attention weight in [0.0, 1.0], decays over time.
/// - `last_access`: Unix timestamp of last access.
/// - `access_count`: Number of times this item has been attended to.
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct WorkingMemoryItem {
    pub node_id: i64,
    pub relevance: f64,
    pub last_access: f64,
    pub access_count: i64,
}

#[pymethods]
impl WorkingMemoryItem {
    #[new]
    #[pyo3(signature = (node_id, relevance = 0.3, last_access = 0.0, access_count = 1))]
    pub fn new(node_id: i64, relevance: f64, last_access: f64, access_count: i64) -> Self {
        let ts = if last_access <= 0.0 {
            now_timestamp()
        } else {
            last_access
        };
        WorkingMemoryItem {
            node_id,
            relevance: relevance.clamp(0.0, 1.0),
            last_access: ts,
            access_count,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "WorkingMemoryItem(node_id={}, relevance={:.4}, access_count={})",
            self.node_id, self.relevance, self.access_count
        )
    }
}

// ---------------------------------------------------------------------------
// WorkingMemory
// ---------------------------------------------------------------------------

/// Fixed-capacity attention buffer with relevance-based eviction and decay.
///
/// This is a simplified standalone working memory suitable for direct use.
/// The full three-tier system (working + episodic + semantic) is in
/// [`MemoryManager`](crate::memory_manager::MemoryManager).
///
/// # Behaviour
///
/// - `push` (Python: `push`): Insert or boost an item. If at capacity, evict
///   the item with the lowest relevance before inserting.
/// - `decay_all`: Multiply all relevance scores by a factor. Remove items
///   whose relevance drops below a threshold (default 0.01).
/// - `get_active`: Return the top-k items sorted by relevance (highest first).
/// - `refresh`: Boost an existing item's relevance and update its timestamp.
#[pyclass]
pub struct WorkingMemory {
    /// Node ID -> WorkingMemoryItem
    items: HashMap<i64, WorkingMemoryItem>,
    /// Maximum number of items in the buffer.
    capacity: usize,
    /// Default multiplicative decay rate (applied per decay_all call).
    decay_rate: f64,
}

#[pymethods]
impl WorkingMemory {
    /// Create a new working memory buffer.
    ///
    /// # Arguments
    /// - `capacity`: Maximum number of items (default 50).
    /// - `decay_rate`: Default decay factor per decay_all call (default 0.95).
    #[new]
    #[pyo3(signature = (capacity = 50, decay_rate = 0.95))]
    pub fn new(capacity: usize, decay_rate: f64) -> Self {
        WorkingMemory {
            items: HashMap::with_capacity(capacity),
            capacity,
            decay_rate,
        }
    }

    /// Add or boost a node in working memory.
    ///
    /// If the node is already present, its relevance is boosted and access count
    /// incremented. If at capacity, the lowest-relevance item is evicted first.
    ///
    /// # Arguments
    /// - `node_id`: Knowledge graph node ID.
    /// - `relevance`: Relevance score for new items, or boost amount for existing.
    #[pyo3(signature = (node_id, relevance = 0.3))]
    pub fn push(&mut self, node_id: i64, relevance: f64) {
        let now = now_timestamp();

        if let Some(item) = self.items.get_mut(&node_id) {
            // Existing item: boost relevance, update access
            item.relevance = (item.relevance + relevance).min(1.0);
            item.last_access = now;
            item.access_count += 1;
            return;
        }

        // Evict lowest if at capacity
        if self.items.len() >= self.capacity {
            self.evict_lowest();
        }

        self.items.insert(
            node_id,
            WorkingMemoryItem {
                node_id,
                relevance: relevance.clamp(0.0, 1.0),
                last_access: now,
                access_count: 1,
            },
        );
    }

    /// Boost an existing item's relevance. No-op if the node is not present.
    ///
    /// # Arguments
    /// - `node_id`: Knowledge graph node ID.
    /// - `boost`: Amount to add to relevance (clamped to 1.0).
    #[pyo3(signature = (node_id, boost = 0.1))]
    pub fn refresh(&mut self, node_id: i64, boost: f64) {
        if let Some(item) = self.items.get_mut(&node_id) {
            item.relevance = (item.relevance + boost).min(1.0);
            item.last_access = now_timestamp();
            item.access_count += 1;
        }
    }

    /// Multiply all relevance scores by `factor`. Remove items below `threshold`.
    ///
    /// # Arguments
    /// - `factor`: Multiplicative decay (defaults to the instance's `decay_rate`).
    /// - `threshold`: Items below this relevance are removed (default 0.01).
    #[pyo3(signature = (factor = None, threshold = 0.01))]
    pub fn decay_all(&mut self, factor: Option<f64>, threshold: f64) {
        let f = factor.unwrap_or(self.decay_rate);
        let mut to_remove = Vec::new();

        for (node_id, item) in self.items.iter_mut() {
            item.relevance *= f;
            if item.relevance < threshold {
                to_remove.push(*node_id);
            }
        }

        for node_id in to_remove {
            self.items.remove(&node_id);
        }
    }

    /// Return the top-k items sorted by relevance (highest first).
    ///
    /// # Arguments
    /// - `top_k`: Number of items to return (default 10, 0 = all).
    #[pyo3(signature = (top_k = 10))]
    pub fn get_active(&self, top_k: usize) -> Vec<WorkingMemoryItem> {
        let mut sorted: Vec<&WorkingMemoryItem> = self.items.values().collect();
        sorted.sort_by(|a, b| {
            b.relevance
                .partial_cmp(&a.relevance)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let limit = if top_k == 0 { sorted.len() } else { top_k.min(sorted.len()) };
        sorted[..limit].iter().map(|item| (*item).clone()).collect()
    }

    /// Check if a node is currently in working memory.
    pub fn contains(&self, node_id: i64) -> bool {
        self.items.contains_key(&node_id)
    }

    /// Current number of items in the buffer.
    pub fn size(&self) -> usize {
        self.items.len()
    }

    /// Maximum capacity of the buffer.
    #[getter]
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Current decay rate.
    #[getter]
    pub fn decay_rate(&self) -> f64 {
        self.decay_rate
    }

    /// Remove all items from working memory.
    pub fn clear(&mut self) {
        self.items.clear();
    }

    /// Remove a specific node from working memory. Returns True if it was present.
    pub fn remove(&mut self, node_id: i64) -> bool {
        self.items.remove(&node_id).is_some()
    }

    /// Get a specific item by node_id, or None if not present.
    pub fn get(&self, node_id: i64) -> Option<WorkingMemoryItem> {
        self.items.get(&node_id).cloned()
    }

    /// Return all node IDs currently in working memory.
    pub fn node_ids(&self) -> Vec<i64> {
        self.items.keys().copied().collect()
    }

    fn __repr__(&self) -> String {
        format!(
            "WorkingMemory(size={}, capacity={}, decay_rate={:.4})",
            self.items.len(),
            self.capacity,
            self.decay_rate
        )
    }

    fn __len__(&self) -> usize {
        self.items.len()
    }

    fn __contains__(&self, node_id: i64) -> bool {
        self.items.contains_key(&node_id)
    }
}

// Internal (not exposed to Python)
impl WorkingMemory {
    /// Evict the item with the lowest relevance score.
    fn evict_lowest(&mut self) {
        if self.items.is_empty() {
            return;
        }
        let lowest_id = self
            .items
            .iter()
            .min_by(|a, b| {
                a.1.relevance
                    .partial_cmp(&b.1.relevance)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .map(|(id, _)| *id);

        if let Some(id) = lowest_id {
            self.items.remove(&id);
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- WorkingMemoryItem tests --

    #[test]
    fn test_item_creation() {
        let item = WorkingMemoryItem::new(42, 0.7, 1000.0, 1);
        assert_eq!(item.node_id, 42);
        assert!((item.relevance - 0.7).abs() < f64::EPSILON);
        assert!((item.last_access - 1000.0).abs() < f64::EPSILON);
        assert_eq!(item.access_count, 1);
    }

    #[test]
    fn test_item_relevance_clamped() {
        let item = WorkingMemoryItem::new(1, 1.5, 100.0, 1);
        assert!((item.relevance - 1.0).abs() < f64::EPSILON);

        let item2 = WorkingMemoryItem::new(2, -0.5, 100.0, 1);
        assert!((item2.relevance - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_item_auto_timestamp() {
        // When last_access is 0.0, it should be set to now
        let item = WorkingMemoryItem::new(1, 0.5, 0.0, 1);
        assert!(item.last_access > 1_000_000_000.0); // Some reasonable unix timestamp
    }

    #[test]
    fn test_item_clone() {
        let item = WorkingMemoryItem::new(10, 0.8, 500.0, 3);
        let cloned = item.clone();
        assert_eq!(cloned.node_id, item.node_id);
        assert!((cloned.relevance - item.relevance).abs() < f64::EPSILON);
        assert_eq!(cloned.access_count, item.access_count);
    }

    #[test]
    fn test_item_repr() {
        let item = WorkingMemoryItem::new(42, 0.75, 100.0, 3);
        let repr = item.__repr__();
        assert!(repr.contains("42"));
        assert!(repr.contains("0.75"));
        assert!(repr.contains("3"));
    }

    // -- WorkingMemory tests --

    #[test]
    fn test_new_empty() {
        let wm = WorkingMemory::new(10, 0.95);
        assert_eq!(wm.size(), 0);
        assert_eq!(wm.capacity(), 10);
        assert!((wm.decay_rate() - 0.95).abs() < f64::EPSILON);
    }

    #[test]
    fn test_push_and_contains() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.5);
        assert!(wm.contains(1));
        assert!(!wm.contains(2));
        assert_eq!(wm.size(), 1);
    }

    #[test]
    fn test_push_boost_existing() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.3);

        let item_before = wm.get(1).unwrap();
        let relevance_before = item_before.relevance;
        let count_before = item_before.access_count;

        wm.push(1, 0.2);

        let item_after = wm.get(1).unwrap();
        assert!((item_after.relevance - (relevance_before + 0.2)).abs() < f64::EPSILON);
        assert_eq!(item_after.access_count, count_before + 1);
    }

    #[test]
    fn test_push_boost_clamped_at_one() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.8);
        wm.push(1, 0.5); // 0.8 + 0.5 = 1.3 -> clamped to 1.0
        let item = wm.get(1).unwrap();
        assert!((item.relevance - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_eviction_at_capacity() {
        let mut wm = WorkingMemory::new(3, 0.95);
        wm.push(1, 0.3);
        wm.push(2, 0.5);
        wm.push(3, 0.8);
        assert_eq!(wm.size(), 3);

        // Push a 4th item — should evict node 1 (lowest relevance 0.3)
        wm.push(4, 0.6);
        assert_eq!(wm.size(), 3);
        assert!(!wm.contains(1)); // evicted
        assert!(wm.contains(2));
        assert!(wm.contains(3));
        assert!(wm.contains(4));
    }

    #[test]
    fn test_decay_all_default() {
        let mut wm = WorkingMemory::new(10, 0.5);
        wm.push(1, 1.0);
        wm.push(2, 0.5);

        wm.decay_all(None, 0.01);

        let item1 = wm.get(1).unwrap();
        assert!((item1.relevance - 0.5).abs() < f64::EPSILON);
        let item2 = wm.get(2).unwrap();
        assert!((item2.relevance - 0.25).abs() < f64::EPSILON);
    }

    #[test]
    fn test_decay_all_custom_factor() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.8);

        wm.decay_all(Some(0.5), 0.01);

        let item = wm.get(1).unwrap();
        assert!((item.relevance - 0.4).abs() < f64::EPSILON);
    }

    #[test]
    fn test_decay_removes_below_threshold() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.02);
        wm.push(2, 0.8);

        // After decay with factor 0.4: node 1 = 0.008 (< 0.01), node 2 = 0.32
        wm.decay_all(Some(0.4), 0.01);

        assert!(!wm.contains(1));
        assert!(wm.contains(2));
        assert_eq!(wm.size(), 1);
    }

    #[test]
    fn test_get_active_sorted_by_relevance() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.3);
        wm.push(2, 0.9);
        wm.push(3, 0.6);

        let active = wm.get_active(10);
        assert_eq!(active.len(), 3);
        assert_eq!(active[0].node_id, 2); // highest
        assert_eq!(active[1].node_id, 3);
        assert_eq!(active[2].node_id, 1); // lowest
    }

    #[test]
    fn test_get_active_top_k() {
        let mut wm = WorkingMemory::new(10, 0.95);
        for i in 0..5 {
            wm.push(i, (i as f64) * 0.2);
        }
        let active = wm.get_active(2);
        assert_eq!(active.len(), 2);
        // Should be the top 2 by relevance
        assert!(active[0].relevance >= active[1].relevance);
    }

    #[test]
    fn test_get_active_zero_returns_all() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.3);
        wm.push(2, 0.5);
        wm.push(3, 0.7);
        let active = wm.get_active(0);
        assert_eq!(active.len(), 3);
    }

    #[test]
    fn test_get_active_empty() {
        let wm = WorkingMemory::new(10, 0.95);
        let active = wm.get_active(5);
        assert!(active.is_empty());
    }

    #[test]
    fn test_refresh_existing() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.5);
        wm.refresh(1, 0.2);
        let item = wm.get(1).unwrap();
        assert!((item.relevance - 0.7).abs() < f64::EPSILON);
        assert_eq!(item.access_count, 2);
    }

    #[test]
    fn test_refresh_nonexistent_noop() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.refresh(999, 0.5); // Should do nothing
        assert!(!wm.contains(999));
        assert_eq!(wm.size(), 0);
    }

    #[test]
    fn test_remove() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.5);
        assert!(wm.remove(1));
        assert!(!wm.contains(1));
        assert_eq!(wm.size(), 0);
    }

    #[test]
    fn test_remove_nonexistent() {
        let mut wm = WorkingMemory::new(10, 0.95);
        assert!(!wm.remove(999));
    }

    #[test]
    fn test_clear() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 0.5);
        wm.push(2, 0.6);
        wm.push(3, 0.7);
        wm.clear();
        assert_eq!(wm.size(), 0);
        assert!(!wm.contains(1));
    }

    #[test]
    fn test_node_ids() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(10, 0.5);
        wm.push(20, 0.5);
        wm.push(30, 0.5);
        let mut ids = wm.node_ids();
        ids.sort();
        assert_eq!(ids, vec![10, 20, 30]);
    }

    #[test]
    fn test_len_and_contains_dunder() {
        let mut wm = WorkingMemory::new(10, 0.95);
        assert_eq!(wm.__len__(), 0);
        wm.push(1, 0.5);
        assert_eq!(wm.__len__(), 1);
        assert!(wm.__contains__(1));
        assert!(!wm.__contains__(2));
    }

    #[test]
    fn test_evict_lowest_empty() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.evict_lowest(); // Should not panic
        assert_eq!(wm.size(), 0);
    }

    #[test]
    fn test_capacity_one() {
        let mut wm = WorkingMemory::new(1, 0.95);
        wm.push(1, 0.5);
        wm.push(2, 0.8);
        assert_eq!(wm.size(), 1);
        assert!(wm.contains(2));
        assert!(!wm.contains(1));
    }

    #[test]
    fn test_repeated_decay_convergence() {
        let mut wm = WorkingMemory::new(10, 0.95);
        wm.push(1, 1.0);

        // After many decays, relevance should drop below threshold
        for _ in 0..500 {
            wm.decay_all(Some(0.95), 0.01);
        }
        assert!(!wm.contains(1));
    }

    #[test]
    fn test_repr() {
        let wm = WorkingMemory::new(50, 0.95);
        let repr = wm.__repr__();
        assert!(repr.contains("size=0"));
        assert!(repr.contains("capacity=50"));
    }
}
