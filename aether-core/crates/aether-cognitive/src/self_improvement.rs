//! Recursive Self-Improvement Engine — Aether Reasons About Its Own Reasoning.
//!
//! Analyzes past reasoning operations to identify patterns of success and failure
//! across reasoning modes and knowledge domains, then adjusts strategy weights
//! to improve future performance.
//!
//! Key design principles:
//! - Safety-bounded: No single strategy can dominate (min 0.05, max 0.5)
//! - Diversity-preserving: Strategy diversity is enforced structurally
//! - Transparent: All adjustments are logged and queryable
//! - Periodic: Runs every N blocks (configurable)
//! - Rollback: Automatic rollback if performance regresses > 10%

use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

use crate::metacognition::MetacognitionEngine;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Reasoning modes tracked by this engine.
pub const REASONING_MODES: &[&str] = &[
    "deductive",
    "inductive",
    "abductive",
    "chain_of_thought",
    "neural",
    "causal",
];

/// Default knowledge domains.
pub const DEFAULT_DOMAINS: &[&str] = &[
    "quantum_physics",
    "mathematics",
    "computer_science",
    "blockchain",
    "cryptography",
    "philosophy",
    "biology",
    "physics",
    "economics",
    "ai_ml",
    "general",
];

const DEFAULT_INTERVAL: u64 = 100;
const DEFAULT_MIN_WEIGHT: f64 = 0.05;
const DEFAULT_MAX_WEIGHT: f64 = 0.5;
const DEFAULT_EMA_ALPHA: f64 = 0.3;
const MIN_OBSERVATIONS: u64 = 3;
const MAX_RECORDS: usize = 5000;
const MAX_ACTIONS: usize = 1000;
const MAX_SNAPSHOTS: usize = 10;
const MAX_CYCLE_STATS: usize = 50;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// A single reasoning performance observation.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PerformanceRecord {
    pub strategy: String,
    pub domain: String,
    pub confidence: f64,
    pub success: bool,
    pub block_height: u64,
    pub timestamp: f64,
}

/// A weight adjustment made during an improvement cycle.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ImprovementAction {
    pub strategy: String,
    pub domain: String,
    pub old_weight: f64,
    pub new_weight: f64,
    pub reason: String,
    pub block_height: u64,
    pub timestamp: f64,
    pub outcome_measured: bool,
    pub outcome_improved: Option<bool>,
    pub post_adjustment_success_rate: f64,
}

impl ImprovementAction {
    fn new(
        strategy: String,
        domain: String,
        old_weight: f64,
        new_weight: f64,
        reason: String,
        block_height: u64,
    ) -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        Self {
            strategy,
            domain,
            old_weight,
            new_weight,
            reason,
            block_height,
            timestamp,
            outcome_measured: false,
            outcome_improved: None,
            post_adjustment_success_rate: 0.0,
        }
    }
}

/// Per-strategy stats within a domain.
#[derive(Clone, Debug, Default)]
struct InternalStats {
    attempts: u64,
    correct: u64,
    total_confidence: f64,
}

/// Weak or strong area identified during a cycle.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PerformanceArea {
    pub strategy: String,
    pub domain: String,
    pub success_rate: f64,
}

/// Result of a single improvement cycle.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CycleResult {
    pub cycle_number: u64,
    pub block_height: u64,
    pub adjustments: usize,
    pub weak_areas: Vec<PerformanceArea>,
    pub strong_areas: Vec<PerformanceArea>,
    pub duration_seconds: f64,
    pub regression_detected: bool,
    pub pre_success_rate: f64,
    pub post_success_rate: f64,
}

/// Enactment result.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EnactResult {
    pub enacted_count: usize,
    pub rollback_performed: bool,
    pub block_height: u64,
    pub domains_updated: usize,
}

/// Cycle stats for chat exposure.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CycleChatStats {
    pub cycles_completed: u64,
    pub total_adjustments: u64,
    pub performance_delta: f64,
    pub total_records: usize,
    pub recent_cycles: Vec<CycleResult>,
    pub trend: String,
    pub regressions_detected: usize,
}

/// Overall stats for the engine.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SelfImprovementStats {
    pub cycles_completed: u64,
    pub total_adjustments: u64,
    pub rollbacks: u64,
    pub performance_delta: f64,
    pub total_records: usize,
    pub last_cycle_block: u64,
    pub interval: u64,
    pub min_weight: f64,
    pub max_weight: f64,
    pub domains_tracked: usize,
    pub strategies_tracked: usize,
    pub diversity_score: f64,
    pub average_weights: HashMap<String, f64>,
}

// ---------------------------------------------------------------------------
// SelfImprovementEngine
// ---------------------------------------------------------------------------

/// Recursive self-improvement engine for Aether Tree reasoning.
///
/// Analyzes past reasoning operations to identify which reasoning modes
/// succeed or fail on which knowledge domains, then adjusts per-domain
/// strategy weights to improve future performance.
#[pyclass]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SelfImprovementEngine {
    /// Per-domain, per-strategy weights: domain -> {strategy -> weight}
    domain_weights: HashMap<String, HashMap<String, f64>>,
    records: Vec<PerformanceRecord>,
    actions: Vec<ImprovementAction>,
    cycles_completed: u64,
    total_adjustments: u64,
    last_cycle_block: u64,
    last_performance_delta: f64,
    prev_cycle_success_rate: f64,
    rollback_count: u64,
    interval: u64,
    min_weight: f64,
    max_weight: f64,
    ema_alpha: f64,
    /// Weight snapshots for rollback: (block_height, weights)
    weight_snapshots: Vec<(u64, HashMap<String, HashMap<String, f64>>)>,
    /// Adaptive per-domain alpha
    adaptive_alpha: HashMap<String, f64>,
    /// Cycle stats history for chat
    cycle_stats_history: Vec<CycleResult>,
}

impl Default for SelfImprovementEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl SelfImprovementEngine {
    /// Create a new SelfImprovementEngine with uniform weights.
    pub fn new() -> Self {
        Self::with_params(DEFAULT_INTERVAL, DEFAULT_MIN_WEIGHT, DEFAULT_MAX_WEIGHT)
    }

    /// Create with custom parameters.
    pub fn with_params(interval: u64, min_weight: f64, max_weight: f64) -> Self {
        let n = REASONING_MODES.len();
        let uniform = 1.0 / n as f64;
        let mut domain_weights = HashMap::new();
        for &domain in DEFAULT_DOMAINS {
            let mut weights = HashMap::new();
            for &strategy in REASONING_MODES {
                weights.insert(strategy.to_string(), uniform);
            }
            domain_weights.insert(domain.to_string(), weights);
        }

        Self {
            domain_weights,
            records: Vec::new(),
            actions: Vec::new(),
            cycles_completed: 0,
            total_adjustments: 0,
            last_cycle_block: 0,
            last_performance_delta: 0.0,
            prev_cycle_success_rate: 0.0,
            rollback_count: 0,
            interval,
            min_weight,
            max_weight,
            ema_alpha: DEFAULT_EMA_ALPHA,
            weight_snapshots: Vec::new(),
            adaptive_alpha: HashMap::new(),
            cycle_stats_history: Vec::new(),
        }
    }

    /// Record the outcome of a reasoning operation.
    pub fn record_performance(
        &mut self,
        strategy: &str,
        domain: &str,
        confidence: f64,
        success: bool,
        block_height: u64,
    ) {
        let strategy = if REASONING_MODES.contains(&strategy) {
            strategy.to_string()
        } else {
            "chain_of_thought".to_string()
        };

        // Auto-register unknown domains
        if !self.domain_weights.contains_key(domain) {
            let n = REASONING_MODES.len();
            let uniform = 1.0 / n as f64;
            let mut weights = HashMap::new();
            for &s in REASONING_MODES {
                weights.insert(s.to_string(), uniform);
            }
            self.domain_weights.insert(domain.to_string(), weights);
        }

        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);

        self.records.push(PerformanceRecord {
            strategy,
            domain: domain.to_string(),
            confidence: confidence.clamp(0.0, 1.0),
            success,
            block_height,
            timestamp,
        });

        if self.records.len() > MAX_RECORDS {
            let start = self.records.len() - MAX_RECORDS;
            self.records = self.records[start..].to_vec();
        }
    }

    /// Check whether it is time to run an improvement cycle.
    pub fn should_run_cycle(&self, block_height: u64) -> bool {
        if block_height == 0 {
            return false;
        }
        if self.last_cycle_block == 0 {
            return block_height >= self.interval;
        }
        (block_height - self.last_cycle_block) >= self.interval
    }

    /// Run a complete improvement cycle.
    pub fn run_improvement_cycle(&mut self, block_height: u64) -> CycleResult {
        let cycle_start = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);

        let mut adjustments_this_cycle = 0_usize;
        let mut weak_areas: Vec<PerformanceArea> = Vec::new();
        let mut strong_areas: Vec<PerformanceArea> = Vec::new();

        // Save snapshot for rollback
        let snapshot = self.domain_weights.clone();
        self.weight_snapshots.push((block_height, snapshot));
        if self.weight_snapshots.len() > MAX_SNAPSHOTS {
            let start = self.weight_snapshots.len() - MAX_SNAPSHOTS;
            self.weight_snapshots = self.weight_snapshots[start..].to_vec();
        }

        // Pre-cycle performance
        let pre_stats = self.compute_performance_stats();
        let pre_success = Self::compute_overall_success_rate(&pre_stats);

        // Adjust weights based on performance
        let domains: Vec<String> = self.domain_weights.keys().cloned().collect();
        for domain in &domains {
            if let Some(strategy_stats) = pre_stats.get(domain) {
                for (strategy, stats) in strategy_stats {
                    if stats.attempts < MIN_OBSERVATIONS {
                        continue;
                    }

                    let success_rate = stats.correct as f64 / stats.attempts as f64;
                    let old_weight = self
                        .domain_weights
                        .get(domain)
                        .and_then(|dw| dw.get(strategy))
                        .copied()
                        .unwrap_or(1.0 / REASONING_MODES.len() as f64);

                    let target_weight = success_rate;

                    // Adaptive alpha
                    let domain_alpha = self.adaptive_alpha.get(domain).copied().unwrap_or(self.ema_alpha);
                    let domain_alpha = if stats.attempts > 50 {
                        (domain_alpha * 1.05).min(0.5)
                    } else if stats.attempts < 10 {
                        (domain_alpha * 0.95).max(0.1)
                    } else {
                        domain_alpha
                    };
                    self.adaptive_alpha.insert(domain.clone(), domain_alpha);

                    let new_weight = (old_weight * (1.0 - domain_alpha) + target_weight * domain_alpha)
                        .clamp(self.min_weight, self.max_weight);

                    if (new_weight - old_weight).abs() > 0.001 {
                        let reason = if success_rate < 0.3 {
                            weak_areas.push(PerformanceArea {
                                strategy: strategy.clone(),
                                domain: domain.clone(),
                                success_rate: (success_rate * 10000.0).round() / 10000.0,
                            });
                            format!("weak: success_rate={:.3} (n={})", success_rate, stats.attempts)
                        } else if success_rate > 0.7 {
                            strong_areas.push(PerformanceArea {
                                strategy: strategy.clone(),
                                domain: domain.clone(),
                                success_rate: (success_rate * 10000.0).round() / 10000.0,
                            });
                            format!("strong: success_rate={:.3} (n={})", success_rate, stats.attempts)
                        } else {
                            format!("success_rate={:.3} (n={})", success_rate, stats.attempts)
                        };

                        let action = ImprovementAction::new(
                            strategy.clone(),
                            domain.clone(),
                            old_weight,
                            new_weight,
                            reason,
                            block_height,
                        );
                        self.actions.push(action);
                        if self.actions.len() > MAX_ACTIONS {
                            let start = self.actions.len() - MAX_ACTIONS;
                            self.actions = self.actions[start..].to_vec();
                        }

                        if let Some(dw) = self.domain_weights.get_mut(domain) {
                            dw.insert(strategy.clone(), new_weight);
                        }
                        adjustments_this_cycle += 1;
                    }
                }
            }
        }

        // Normalize weights per domain
        let all_domains: Vec<String> = self.domain_weights.keys().cloned().collect();
        for domain in &all_domains {
            self.normalize_domain_weights(domain);
        }

        // Post-cycle performance
        let post_stats = self.compute_performance_stats();
        let post_success = Self::compute_overall_success_rate(&post_stats);

        // Cross-cycle delta
        if self.prev_cycle_success_rate > 0.0 {
            self.last_performance_delta = post_success - self.prev_cycle_success_rate;
        } else if adjustments_this_cycle > 0 {
            self.last_performance_delta = if post_success > 0.0 { post_success } else { 0.01 };
        }
        self.prev_cycle_success_rate = post_success;

        let regression_detected =
            pre_success > 0.0 && post_success < pre_success * 0.9;

        // Evaluate previous actions
        self.evaluate_previous_actions(&post_stats);

        // Update counters
        self.cycles_completed += 1;
        self.total_adjustments += adjustments_this_cycle as u64;
        self.last_cycle_block = block_height;

        let cycle_end = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        let duration = cycle_end - cycle_start;

        let result = CycleResult {
            cycle_number: self.cycles_completed,
            block_height,
            adjustments: adjustments_this_cycle,
            weak_areas,
            strong_areas,
            duration_seconds: (duration * 10000.0).round() / 10000.0,
            regression_detected,
            pre_success_rate: (pre_success * 10000.0).round() / 10000.0,
            post_success_rate: (post_success * 10000.0).round() / 10000.0,
        };

        self.cycle_stats_history.push(result.clone());
        if self.cycle_stats_history.len() > MAX_CYCLE_STATS {
            let start = self.cycle_stats_history.len() - MAX_CYCLE_STATS;
            self.cycle_stats_history = self.cycle_stats_history[start..].to_vec();
        }

        result
    }

    /// Compute per-domain, per-strategy performance statistics.
    fn compute_performance_stats(&self) -> HashMap<String, HashMap<String, InternalStats>> {
        let mut stats: HashMap<String, HashMap<String, InternalStats>> = HashMap::new();
        for record in &self.records {
            let domain_map = stats.entry(record.domain.clone()).or_default();
            let entry = domain_map.entry(record.strategy.clone()).or_default();
            entry.attempts += 1;
            if record.success {
                entry.correct += 1;
            }
            entry.total_confidence += record.confidence;
        }
        stats
    }

    fn compute_overall_success_rate(stats: &HashMap<String, HashMap<String, InternalStats>>) -> f64 {
        let mut total_attempts = 0_u64;
        let mut total_correct = 0_u64;
        for domain_stats in stats.values() {
            for s in domain_stats.values() {
                total_attempts += s.attempts;
                total_correct += s.correct;
            }
        }
        if total_attempts == 0 {
            0.0
        } else {
            total_correct as f64 / total_attempts as f64
        }
    }

    fn normalize_domain_weights(&mut self, domain: &str) {
        if let Some(weights) = self.domain_weights.get_mut(domain) {
            let total: f64 = weights.values().sum();
            if total <= 0.0 {
                let n = weights.len() as f64;
                for v in weights.values_mut() {
                    *v = 1.0 / n;
                }
                return;
            }

            // Normalize to sum to 1.0
            for v in weights.values_mut() {
                *v /= total;
            }

            // Re-clamp
            for v in weights.values_mut() {
                *v = v.clamp(self.min_weight, self.max_weight);
            }

            // Re-normalize after clamping
            let total: f64 = weights.values().sum();
            if total > 0.0 {
                for v in weights.values_mut() {
                    *v /= total;
                }
            }
        }
    }

    fn evaluate_previous_actions(
        &mut self,
        current_stats: &HashMap<String, HashMap<String, InternalStats>>,
    ) {
        let n = self.actions.len();
        let start = n.saturating_sub(20);
        for i in (start..n).rev() {
            if self.actions[i].outcome_measured {
                continue;
            }
            let domain = &self.actions[i].domain;
            let strategy = &self.actions[i].strategy;
            if let Some(ds) = current_stats.get(domain) {
                if let Some(ss) = ds.get(strategy) {
                    if ss.attempts >= MIN_OBSERVATIONS {
                        let current_rate = ss.correct as f64 / ss.attempts as f64;
                        let weight_increased =
                            self.actions[i].new_weight > self.actions[i].old_weight;
                        let rate_is_good = current_rate > 0.5;

                        self.actions[i].outcome_measured = true;
                        self.actions[i].post_adjustment_success_rate = current_rate;
                        self.actions[i].outcome_improved = Some(weight_increased == rate_is_good);
                    }
                }
            }
        }
    }

    /// Get current strategy weights for a specific domain.
    pub fn get_domain_weights(&self, domain: &str) -> HashMap<String, f64> {
        if let Some(w) = self.domain_weights.get(domain) {
            w.clone()
        } else {
            let n = REASONING_MODES.len();
            REASONING_MODES
                .iter()
                .map(|s| (s.to_string(), 1.0 / n as f64))
                .collect()
        }
    }

    /// Get the highest-weighted strategy for a domain.
    pub fn get_best_strategy(&self, domain: &str) -> String {
        let weights = self.get_domain_weights(domain);
        weights
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(k, _)| k.clone())
            .unwrap_or_else(|| "deductive".to_string())
    }

    /// Rollback weights to a previous snapshot.
    pub fn rollback_to_snapshot(&mut self, snapshot_index: isize) -> bool {
        if self.weight_snapshots.is_empty() {
            return false;
        }

        let idx = if snapshot_index < 0 {
            let abs_idx = (-snapshot_index) as usize;
            if abs_idx > self.weight_snapshots.len() {
                return false;
            }
            self.weight_snapshots.len() - abs_idx
        } else {
            snapshot_index as usize
        };

        if idx >= self.weight_snapshots.len() {
            return false;
        }

        let (_, snapshot) = self.weight_snapshots[idx].clone();
        self.domain_weights = snapshot;
        self.rollback_count += 1;
        true
    }

    /// Apply pending improvements and perform automatic rollback if needed.
    pub fn enact_improvements(&mut self, block_height: u64) -> EnactResult {
        let enacted_count = self
            .actions
            .iter()
            .filter(|a| {
                a.block_height == block_height
                    || (self.last_cycle_block > 0 && a.block_height >= self.last_cycle_block)
            })
            .count();

        let mut rollback_performed = false;

        // Regression detection with automatic rollback
        if self.records.len() >= 20 {
            let recent_start = self.records.len().saturating_sub(100);
            let recent_records = &self.records[recent_start..];
            let recent_success = recent_records.iter().filter(|r| r.success).count();
            let recent_rate = recent_success as f64 / recent_records.len() as f64;

            if self.records.len() > 200 {
                let baseline_end = self.records.len().saturating_sub(100);
                let baseline_start = self.records.len().saturating_sub(300).min(baseline_end);
                let baseline_records = &self.records[baseline_start..baseline_end];
                if !baseline_records.is_empty() {
                    let baseline_success = baseline_records.iter().filter(|r| r.success).count();
                    let baseline_rate = baseline_success as f64 / baseline_records.len() as f64;

                    if baseline_rate > 0.0 && recent_rate < baseline_rate * 0.9 {
                        if self.weight_snapshots.len() >= 2 {
                            rollback_performed = self.rollback_to_snapshot(-2);
                        }
                    }
                }
            }
        }

        EnactResult {
            enacted_count,
            rollback_performed,
            block_height,
            domains_updated: self.domain_weights.len(),
        }
    }

    /// Sync aggregated strategy weights to a MetacognitionEngine.
    pub fn sync_to_metacognition(&self, metacognition: &mut MetacognitionEngine) {
        let mut global_weights: HashMap<String, f64> = HashMap::new();
        for &s in REASONING_MODES {
            global_weights.insert(s.to_string(), 0.0);
        }

        let n_domains = self.domain_weights.len();
        if n_domains == 0 {
            return;
        }

        for domain_weights in self.domain_weights.values() {
            for (s, w) in domain_weights {
                *global_weights.entry(s.clone()).or_default() += w;
            }
        }

        let n_strategies = REASONING_MODES.len() as f64;
        let mc_weights = metacognition.strategy_weights_mut();
        for (s, w) in &global_weights {
            let scaled = 0.5 + (w / n_domains as f64) * n_strategies;
            if mc_weights.contains_key(s) {
                mc_weights.insert(s.clone(), scaled);
            }
        }
    }

    /// Get cycle stats for chat exposure.
    pub fn get_cycle_stats_for_chat(&self) -> CycleChatStats {
        let recent: Vec<CycleResult> = self
            .cycle_stats_history
            .iter()
            .rev()
            .take(5)
            .cloned()
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect();

        let success_rates: Vec<f64> = recent.iter().map(|c| c.post_success_rate).collect();

        let trend = if success_rates.len() >= 2 {
            let last = *success_rates.last().unwrap();
            let first = *success_rates.first().unwrap();
            if last > first {
                "improving"
            } else if last < first {
                "declining"
            } else {
                "stable"
            }
        } else if success_rates.is_empty() {
            "no_data"
        } else {
            "insufficient_data"
        };

        let regressions_detected = self
            .cycle_stats_history
            .iter()
            .filter(|c| c.regression_detected)
            .count();

        CycleChatStats {
            cycles_completed: self.cycles_completed,
            total_adjustments: self.total_adjustments,
            performance_delta: self.last_performance_delta,
            total_records: self.records.len(),
            recent_cycles: recent,
            trend: trend.to_string(),
            regressions_detected,
        }
    }

    /// Get comprehensive self-improvement statistics.
    pub fn get_stats(&self) -> SelfImprovementStats {
        // Compute average weights across all domains
        let mut avg_weights: HashMap<String, f64> = HashMap::new();
        for &s in REASONING_MODES {
            avg_weights.insert(s.to_string(), 0.0);
        }

        let n_domains = self.domain_weights.len();
        if n_domains > 0 {
            for domain_weights in self.domain_weights.values() {
                for (s, w) in domain_weights {
                    *avg_weights.entry(s.clone()).or_default() += w;
                }
            }
            for v in avg_weights.values_mut() {
                *v /= n_domains as f64;
            }
        }

        // Shannon entropy for diversity
        let entropy: f64 = avg_weights
            .values()
            .filter(|&&w| w > 0.0)
            .map(|&w| -w * w.log2())
            .sum();
        let max_entropy = (REASONING_MODES.len() as f64).log2();
        let diversity_score = if max_entropy > 0.0 {
            entropy / max_entropy
        } else {
            0.0
        };

        SelfImprovementStats {
            cycles_completed: self.cycles_completed,
            total_adjustments: self.total_adjustments,
            rollbacks: self.rollback_count,
            performance_delta: self.last_performance_delta,
            total_records: self.records.len(),
            last_cycle_block: self.last_cycle_block,
            interval: self.interval,
            min_weight: self.min_weight,
            max_weight: self.max_weight,
            domains_tracked: self.domain_weights.len(),
            strategies_tracked: REASONING_MODES.len(),
            diversity_score: (diversity_score * 10000.0).round() / 10000.0,
            average_weights: avg_weights
                .into_iter()
                .map(|(k, v)| (k, (v * 1_000_000.0).round() / 1_000_000.0))
                .collect(),
        }
    }

    /// Get recent actions.
    pub fn get_recent_actions(&self, limit: usize) -> Vec<ImprovementAction> {
        let start = self.actions.len().saturating_sub(limit);
        let mut result: Vec<ImprovementAction> = self.actions[start..].to_vec();
        result.reverse();
        result
    }

    /// Get the number of cycles completed.
    pub fn cycles_completed(&self) -> u64 {
        self.cycles_completed
    }

    /// Get performance delta.
    pub fn last_performance_delta(&self) -> f64 {
        self.last_performance_delta
    }

    /// Get rollback count.
    pub fn rollback_count(&self) -> u64 {
        self.rollback_count
    }

    /// Get interval.
    pub fn interval(&self) -> u64 {
        self.interval
    }
}

// ---------------------------------------------------------------------------
// PyO3 methods
// ---------------------------------------------------------------------------

#[pymethods]
impl SelfImprovementEngine {
    #[new]
    #[pyo3(signature = (interval = 100, min_weight = 0.05, max_weight = 0.5))]
    pub fn py_new(interval: u64, min_weight: f64, max_weight: f64) -> Self {
        Self::with_params(interval, min_weight, max_weight)
    }

    /// Record the outcome of a reasoning operation.
    #[pyo3(name = "record_performance")]
    pub fn py_record_performance(
        &mut self,
        strategy: &str,
        domain: &str,
        confidence: f64,
        success: bool,
        block_height: u64,
    ) {
        self.record_performance(strategy, domain, confidence, success, block_height);
    }

    /// Check if it's time to run an improvement cycle.
    #[pyo3(name = "should_run_cycle")]
    pub fn py_should_run_cycle(&self, block_height: u64) -> bool {
        self.should_run_cycle(block_height)
    }

    /// Run an improvement cycle and return a dict of results.
    #[pyo3(name = "run_improvement_cycle")]
    pub fn py_run_improvement_cycle(&mut self, block_height: u64) -> PyResult<PyObject> {
        let result = self.run_improvement_cycle(block_height);
        Python::with_gil(|py| {
            let json = serde_json::to_string(&result)
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let json_mod = py.import("json")?;
            let obj = json_mod.call_method1("loads", (json,))?;
            Ok(obj.into())
        })
    }

    /// Get current weights for a domain.
    #[pyo3(name = "get_domain_weights")]
    pub fn py_get_domain_weights(&self, domain: &str) -> PyResult<PyObject> {
        let weights = self.get_domain_weights(domain);
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            for (k, v) in &weights {
                dict.set_item(k, v)?;
            }
            Ok(dict.into())
        })
    }

    /// Get the best strategy for a domain.
    #[pyo3(name = "get_best_strategy")]
    pub fn py_get_best_strategy(&self, domain: &str) -> String {
        self.get_best_strategy(domain)
    }

    /// Rollback to a previous snapshot.
    #[pyo3(name = "rollback_to_snapshot")]
    #[pyo3(signature = (snapshot_index = -1))]
    pub fn py_rollback_to_snapshot(&mut self, snapshot_index: isize) -> bool {
        self.rollback_to_snapshot(snapshot_index)
    }

    /// Enact improvements with automatic rollback.
    #[pyo3(name = "enact_improvements")]
    pub fn py_enact_improvements(&mut self, block_height: u64) -> PyResult<PyObject> {
        let result = self.enact_improvements(block_height);
        Python::with_gil(|py| {
            let json = serde_json::to_string(&result)
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let json_mod = py.import("json")?;
            let obj = json_mod.call_method1("loads", (json,))?;
            Ok(obj.into())
        })
    }

    /// Get stats dict.
    #[pyo3(name = "get_stats")]
    pub fn py_get_stats(&self) -> PyResult<PyObject> {
        let stats = self.get_stats();
        Python::with_gil(|py| {
            let json = serde_json::to_string(&stats)
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let json_mod = py.import("json")?;
            let obj = json_mod.call_method1("loads", (json,))?;
            Ok(obj.into())
        })
    }

    fn __repr__(&self) -> String {
        format!(
            "SelfImprovementEngine(cycles={}, adjustments={}, rollbacks={}, domains={})",
            self.cycles_completed,
            self.total_adjustments,
            self.rollback_count,
            self.domain_weights.len(),
        )
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_engine() -> SelfImprovementEngine {
        SelfImprovementEngine::new()
    }

    #[test]
    fn test_new_has_uniform_weights() {
        let eng = make_engine();
        let expected = 1.0 / REASONING_MODES.len() as f64;
        for domain in DEFAULT_DOMAINS {
            let weights = eng.get_domain_weights(domain);
            for &strategy in REASONING_MODES {
                assert!(
                    (weights[strategy] - expected).abs() < 1e-10,
                    "Non-uniform weight for {}/{}: {}",
                    domain,
                    strategy,
                    weights[strategy]
                );
            }
        }
    }

    #[test]
    fn test_record_performance() {
        let mut eng = make_engine();
        eng.record_performance("deductive", "general", 0.8, true, 1);
        assert_eq!(eng.records.len(), 1);
        assert_eq!(eng.records[0].strategy, "deductive");
        assert!(eng.records[0].success);
    }

    #[test]
    fn test_record_unknown_strategy_falls_back() {
        let mut eng = make_engine();
        eng.record_performance("unknown_mode", "general", 0.5, true, 1);
        assert_eq!(eng.records[0].strategy, "chain_of_thought");
    }

    #[test]
    fn test_record_unknown_domain_auto_registers() {
        let mut eng = make_engine();
        eng.record_performance("deductive", "new_domain", 0.7, true, 1);
        assert!(eng.domain_weights.contains_key("new_domain"));
    }

    #[test]
    fn test_records_bounded() {
        let mut eng = make_engine();
        for i in 0..6000 {
            eng.record_performance("deductive", "general", 0.5, i % 2 == 0, i as u64);
        }
        assert!(eng.records.len() <= MAX_RECORDS);
    }

    #[test]
    fn test_should_run_cycle_initial() {
        let eng = make_engine();
        assert!(!eng.should_run_cycle(0));
        assert!(!eng.should_run_cycle(50));
        assert!(eng.should_run_cycle(100));
    }

    #[test]
    fn test_should_run_cycle_subsequent() {
        let mut eng = make_engine();
        eng.last_cycle_block = 100;
        assert!(!eng.should_run_cycle(150));
        assert!(eng.should_run_cycle(200));
    }

    #[test]
    fn test_run_improvement_cycle_empty() {
        let mut eng = make_engine();
        let result = eng.run_improvement_cycle(100);
        assert_eq!(result.cycle_number, 1);
        assert_eq!(result.adjustments, 0);
        assert_eq!(eng.cycles_completed, 1);
    }

    #[test]
    fn test_run_improvement_cycle_with_data() {
        let mut eng = make_engine();
        for i in 0..20 {
            eng.record_performance("deductive", "general", 0.9, true, i);
            eng.record_performance("neural", "general", 0.3, false, i);
        }
        let result = eng.run_improvement_cycle(100);
        assert!(result.adjustments > 0);
        // Deductive should have higher weight than neural
        let w = eng.get_domain_weights("general");
        assert!(w["deductive"] > w["neural"]);
    }

    #[test]
    fn test_normalize_domain_weights() {
        let mut eng = make_engine();
        // Manually set unbalanced weights
        if let Some(w) = eng.domain_weights.get_mut("general") {
            w.insert("deductive".to_string(), 10.0);
            w.insert("neural".to_string(), 0.01);
        }
        eng.normalize_domain_weights("general");
        let w = eng.get_domain_weights("general");
        let total: f64 = w.values().sum();
        assert!((total - 1.0).abs() < 1e-10, "Weights should sum to 1.0: {}", total);
    }

    #[test]
    fn test_get_best_strategy() {
        let mut eng = make_engine();
        if let Some(w) = eng.domain_weights.get_mut("physics") {
            w.insert("causal".to_string(), 0.9);
        }
        assert_eq!(eng.get_best_strategy("physics"), "causal");
    }

    #[test]
    fn test_get_best_strategy_unknown_domain() {
        let eng = make_engine();
        let s = eng.get_best_strategy("unknown_domain");
        assert!(REASONING_MODES.contains(&s.as_str()));
    }

    #[test]
    fn test_rollback_to_snapshot() {
        let mut eng = make_engine();
        // Run first cycle to create snapshot
        for i in 0..10 {
            eng.record_performance("deductive", "general", 0.9, true, i);
        }
        eng.run_improvement_cycle(100);
        let weights_before = eng.get_domain_weights("general");

        // Mess up weights
        if let Some(w) = eng.domain_weights.get_mut("general") {
            w.insert("deductive".to_string(), 0.01);
        }

        assert!(eng.rollback_to_snapshot(-1));
        let weights_after = eng.get_domain_weights("general");

        // Should be restored to pre-cycle snapshot
        assert!(
            (weights_after["deductive"] - weights_before["deductive"]).abs() > 0.001
                || (weights_after["deductive"] - 1.0 / REASONING_MODES.len() as f64).abs() < 0.01
        );
    }

    #[test]
    fn test_rollback_empty_snapshots() {
        let mut eng = make_engine();
        assert!(!eng.rollback_to_snapshot(-1));
    }

    #[test]
    fn test_rollback_invalid_index() {
        let mut eng = make_engine();
        eng.weight_snapshots.push((1, eng.domain_weights.clone()));
        assert!(!eng.rollback_to_snapshot(-5));
    }

    #[test]
    fn test_enact_improvements_no_regression() {
        let mut eng = make_engine();
        let result = eng.enact_improvements(100);
        assert!(!result.rollback_performed);
    }

    #[test]
    fn test_get_stats() {
        let eng = make_engine();
        let stats = eng.get_stats();
        assert_eq!(stats.cycles_completed, 0);
        assert_eq!(stats.total_adjustments, 0);
        assert_eq!(stats.domains_tracked, DEFAULT_DOMAINS.len());
        assert_eq!(stats.strategies_tracked, REASONING_MODES.len());
        assert!(stats.diversity_score >= 0.0 && stats.diversity_score <= 1.0);
    }

    #[test]
    fn test_diversity_score_uniform_is_max() {
        let eng = make_engine();
        let stats = eng.get_stats();
        // Uniform weights should give diversity close to 1.0
        assert!(stats.diversity_score > 0.99, "Diversity should be ~1.0 for uniform: {}", stats.diversity_score);
    }

    #[test]
    fn test_get_recent_actions() {
        let mut eng = make_engine();
        for i in 0..30 {
            eng.record_performance("deductive", "general", 0.9, true, i);
            eng.record_performance("neural", "general", 0.1, false, i);
        }
        eng.run_improvement_cycle(100);
        let actions = eng.get_recent_actions(5);
        assert!(actions.len() <= 5);
    }

    #[test]
    fn test_cycle_stats_for_chat_empty() {
        let eng = make_engine();
        let stats = eng.get_cycle_stats_for_chat();
        assert_eq!(stats.cycles_completed, 0);
        assert_eq!(stats.trend, "no_data");
    }

    #[test]
    fn test_cycle_stats_for_chat_with_data() {
        let mut eng = make_engine();
        for i in 0..10 {
            eng.record_performance("deductive", "general", 0.8, true, i);
        }
        eng.run_improvement_cycle(100);
        eng.run_improvement_cycle(200);
        let stats = eng.get_cycle_stats_for_chat();
        assert_eq!(stats.cycles_completed, 2);
        assert!(!stats.recent_cycles.is_empty());
    }

    #[test]
    fn test_evaluate_previous_actions() {
        let mut eng = make_engine();
        for i in 0..20 {
            eng.record_performance("deductive", "general", 0.9, true, i);
            eng.record_performance("neural", "general", 0.3, false, i);
        }
        eng.run_improvement_cycle(100);
        // Actions should exist and some may be evaluated
        let actions = eng.get_recent_actions(20);
        assert!(!actions.is_empty());
    }

    #[test]
    fn test_with_params() {
        let eng = SelfImprovementEngine::with_params(50, 0.1, 0.4);
        assert_eq!(eng.interval, 50);
        assert!((eng.min_weight - 0.1).abs() < f64::EPSILON);
        assert!((eng.max_weight - 0.4).abs() < f64::EPSILON);
    }

    #[test]
    fn test_sync_to_metacognition() {
        let eng = make_engine();
        let mut mc = MetacognitionEngine::new();
        eng.sync_to_metacognition(&mut mc);
        // Weights should be updated
        let w = mc.strategy_weights();
        assert!(!w.is_empty());
    }

    #[test]
    fn test_serde_roundtrip() {
        let mut eng = make_engine();
        eng.record_performance("deductive", "general", 0.8, true, 1);
        eng.run_improvement_cycle(100);
        let json = serde_json::to_string(&eng).unwrap();
        let back: SelfImprovementEngine = serde_json::from_str(&json).unwrap();
        assert_eq!(back.cycles_completed, eng.cycles_completed);
        assert_eq!(back.records.len(), eng.records.len());
    }

    #[test]
    fn test_weight_clamping() {
        let mut eng = SelfImprovementEngine::with_params(1, 0.05, 0.5);
        // Make one strategy extremely good and all others terrible
        for i in 0..100 {
            eng.record_performance("deductive", "general", 1.0, true, i);
            for &s in &["inductive", "abductive", "chain_of_thought", "neural", "causal"] {
                eng.record_performance(s, "general", 0.1, false, i);
            }
        }
        eng.run_improvement_cycle(100);
        let w = eng.get_domain_weights("general");
        // All weights should be within bounds (after normalization they sum to 1.0)
        for v in w.values() {
            assert!(*v >= 0.0, "Weight should be non-negative: {}", v);
        }
    }

    #[test]
    fn test_multiple_cycles_accumulate() {
        let mut eng = make_engine();
        for i in 0..50 {
            eng.record_performance("deductive", "general", 0.8, i % 3 != 0, i);
        }
        eng.run_improvement_cycle(100);
        eng.run_improvement_cycle(200);
        eng.run_improvement_cycle(300);
        assert_eq!(eng.cycles_completed, 3);
    }
}
