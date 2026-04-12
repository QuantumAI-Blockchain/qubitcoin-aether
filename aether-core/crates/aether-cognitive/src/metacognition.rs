//! Metacognitive Self-Evaluation Loop — Reasoning About Reasoning.
//!
//! Tracks the accuracy and effectiveness of all reasoning strategies,
//! evaluates which approaches produce the best results, and adjusts
//! the system's reasoning parameters accordingly.
//!
//! Key features:
//! - Confidence calibration via adaptive temperature scaling (conf^T)
//! - Expected Calibration Error (ECE) computation
//! - Per-strategy and per-domain accuracy tracking
//! - Temporally-weighted strategy adaptation
//! - Calibration trend monitoring

use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Default reasoning strategies tracked by the metacognition engine.
pub const STRATEGIES: &[&str] = &[
    "deductive",
    "inductive",
    "abductive",
    "chain_of_thought",
    "neural",
    "causal",
];

const MAX_HISTORY: usize = 500;
const DEFAULT_TEMPERATURE: f64 = 0.8;
const TEMPERATURE_EMA_ALPHA: f64 = 0.3;
const MIN_EVALS_FOR_TEMPERATURE: usize = 30;
const NUM_BINS: usize = 10;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// A single evaluation record in the metacognition history.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EvaluationEntry {
    pub strategy: String,
    pub confidence: f64,
    pub correct: bool,
    pub domain: String,
    pub block_height: u64,
    pub timestamp: f64,
}

/// Accumulated stats for a single reasoning strategy.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct StrategyStats {
    pub attempts: u64,
    pub correct: u64,
    pub total_confidence: f64,
    pub total_actual: f64,
}

impl StrategyStats {
    pub fn accuracy(&self) -> f64 {
        if self.attempts == 0 {
            return 0.0;
        }
        self.correct as f64 / self.attempts as f64
    }
}

/// Accumulated stats for a single knowledge domain.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct DomainStats {
    pub attempts: u64,
    pub correct: u64,
}

impl DomainStats {
    pub fn accuracy(&self) -> f64 {
        if self.attempts == 0 {
            return 0.0;
        }
        self.correct as f64 / self.attempts as f64
    }
}

/// Per-bin confidence calibration data.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct CalibrationBin {
    pub count: u64,
    pub correct: u64,
}

/// Calibration info for a single bin, returned by `get_confidence_calibration`.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CalibrationInfo {
    pub stated_confidence: f64,
    pub actual_accuracy: f64,
    pub calibration_error: f64,
    pub count: u64,
}

// ---------------------------------------------------------------------------
// MetacognitionEngine
// ---------------------------------------------------------------------------

/// Self-evaluation system that monitors reasoning quality.
///
/// Tracks strategy effectiveness, prediction accuracy, confidence calibration,
/// per-domain reasoning success rates, and overall cognitive health metrics.
/// Uses adaptive temperature scaling (conf^T) to calibrate confidence values.
#[pyclass]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MetacognitionEngine {
    strategy_stats: HashMap<String, StrategyStats>,
    domain_stats: HashMap<String, DomainStats>,
    confidence_bins: HashMap<usize, CalibrationBin>,
    total_evaluations: u64,
    total_correct: u64,
    evaluation_history: Vec<EvaluationEntry>,
    temperature: f64,
    strategy_weights: HashMap<String, f64>,
}

impl Default for MetacognitionEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl MetacognitionEngine {
    /// Create a new MetacognitionEngine with default strategy weights.
    pub fn new() -> Self {
        let mut strategy_weights = HashMap::new();
        for &s in STRATEGIES {
            strategy_weights.insert(s.to_string(), 1.0);
        }

        Self {
            strategy_stats: HashMap::new(),
            domain_stats: HashMap::new(),
            confidence_bins: HashMap::new(),
            total_evaluations: 0,
            total_correct: 0,
            evaluation_history: Vec::new(),
            temperature: DEFAULT_TEMPERATURE,
            strategy_weights,
        }
    }

    /// Record the outcome of a reasoning operation.
    ///
    /// Uses RAW (pre-temperature) confidence for bin placement and ECE
    /// evaluation, preventing the self-referential feedback loop where
    /// calibrated values train the calibrator.
    pub fn evaluate_reasoning(
        &mut self,
        strategy: &str,
        confidence: f64,
        outcome_correct: bool,
        domain: &str,
        block_height: u64,
    ) -> StrategyStats {
        self.total_evaluations += 1;
        if outcome_correct {
            self.total_correct += 1;
        }

        // Update strategy stats
        let stats = self
            .strategy_stats
            .entry(strategy.to_string())
            .or_default();
        stats.attempts += 1;
        if outcome_correct {
            stats.correct += 1;
        }
        stats.total_confidence += confidence;
        stats.total_actual += if outcome_correct { 1.0 } else { 0.0 };
        let ret = stats.clone();

        // Update domain stats
        let ds = self.domain_stats.entry(domain.to_string()).or_default();
        ds.attempts += 1;
        if outcome_correct {
            ds.correct += 1;
        }

        // Confidence bin (raw confidence)
        let bin_idx = (confidence * 10.0).floor().min(9.0) as usize;
        let bin = self.confidence_bins.entry(bin_idx).or_default();
        bin.count += 1;
        if outcome_correct {
            bin.correct += 1;
        }

        // History
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        self.evaluation_history.push(EvaluationEntry {
            strategy: strategy.to_string(),
            confidence: (confidence * 10000.0).round() / 10000.0,
            correct: outcome_correct,
            domain: domain.to_string(),
            block_height,
            timestamp,
        });
        if self.evaluation_history.len() > MAX_HISTORY {
            let start = self.evaluation_history.len() - MAX_HISTORY;
            self.evaluation_history = self.evaluation_history[start..].to_vec();
        }

        ret
    }

    /// Learn the optimal temperature from calibration bin data.
    ///
    /// Computes the ratio of mean actual accuracy to mean stated confidence
    /// across all populated bins. Updates via EMA for smooth transitions.
    fn update_temperature(&mut self) {
        if (self.total_evaluations as usize) < MIN_EVALS_FOR_TEMPERATURE {
            return;
        }

        let mut sum_stated = 0.0_f64;
        let mut sum_actual = 0.0_f64;
        let mut total_count = 0_u64;

        for bin_idx in 0..NUM_BINS {
            if let Some(data) = self.confidence_bins.get(&bin_idx) {
                if data.count < 3 {
                    continue;
                }
                let stated = (bin_idx as f64 + 0.5) / 10.0;
                let actual = data.correct as f64 / data.count as f64;
                sum_stated += stated * data.count as f64;
                sum_actual += actual * data.count as f64;
                total_count += data.count;
            }
        }

        if total_count == 0 || sum_stated < 0.01 {
            return;
        }

        let mean_stated = sum_stated / total_count as f64;
        let mean_actual = sum_actual / total_count as f64;

        // Target temperature: overconfident (stated > actual) -> T > 1
        let gap = mean_stated - mean_actual;
        let t_target = (1.0 + gap * 2.5).clamp(0.5, 3.0);

        // EMA update
        self.temperature =
            self.temperature * (1.0 - TEMPERATURE_EMA_ALPHA) + t_target * TEMPERATURE_EMA_ALPHA;
    }

    /// Adjust strategy weights based on accumulated performance data.
    ///
    /// Uses exponential moving average with temporal weighting to favor
    /// recent evidence while avoiding overreaction to noise.
    pub fn adapt_strategy_weights(&mut self) -> HashMap<String, f64> {
        self.update_temperature();

        // Compute temporally-weighted accuracy from recent history
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        let decay_half_life = 3600.0_f64;

        let mut recent_stats: HashMap<String, (f64, f64)> = HashMap::new(); // (weighted_correct, weighted_total)

        for entry in &self.evaluation_history {
            let age = now - entry.timestamp;
            let temporal_weight = 0.5_f64.powf(age / decay_half_life);

            let (wc, wt) = recent_stats
                .entry(entry.strategy.clone())
                .or_insert((0.0, 0.0));
            *wt += temporal_weight;
            if entry.correct {
                *wc += temporal_weight;
            }
        }

        for (strategy, stats) in &self.strategy_stats {
            if stats.attempts < 10 {
                continue;
            }

            let accuracy = if let Some((wc, wt)) = recent_stats.get(strategy) {
                if *wt > 3.0 {
                    wc / wt
                } else {
                    stats.accuracy()
                }
            } else {
                stats.accuracy()
            };

            let old_weight = *self.strategy_weights.get(strategy).unwrap_or(&1.0);
            let new_evidence = accuracy * 2.0; // Scale: 0.0-2.0
            let new_weight = old_weight * 0.7 + new_evidence * 0.3;
            self.strategy_weights.insert(strategy.clone(), new_weight);
        }

        self.strategy_weights.clone()
    }

    /// Recommend the best reasoning strategy for a given domain and question type.
    ///
    /// Uses both global strategy weights and domain-specific performance history.
    pub fn get_recommended_strategy(&self, domain: &str, question_type: &str) -> String {
        if self.strategy_weights.is_empty() {
            return "deductive".to_string();
        }

        // Question type heuristic bonus
        let mut question_bonus: HashMap<&str, f64> = HashMap::new();
        match question_type {
            "causal" => {
                question_bonus.insert("causal", 0.15);
                question_bonus.insert("abductive", 0.1);
                question_bonus.insert("deductive", 0.05);
            }
            "predictive" => {
                question_bonus.insert("inductive", 0.15);
                question_bonus.insert("neural", 0.1);
                question_bonus.insert("chain_of_thought", 0.05);
            }
            "factual" => {
                question_bonus.insert("deductive", 0.15);
                question_bonus.insert("chain_of_thought", 0.05);
            }
            _ => {}
        }

        // Domain-specific performance bonus from recent history
        let mut domain_bonus: HashMap<String, f64> = HashMap::new();
        let recent_start = self.evaluation_history.len().saturating_sub(100);
        for entry in &self.evaluation_history[recent_start..] {
            if entry.domain == domain && entry.correct {
                *domain_bonus.entry(entry.strategy.clone()).or_default() += 0.05;
            }
        }

        // Hard vs easy domain distinction
        if let Some(dstats) = self.domain_stats.get(domain) {
            if dstats.attempts > 20 {
                let acc = dstats.accuracy();
                if acc > 0.8 {
                    *question_bonus.entry("deductive").or_default() += 0.1;
                } else if acc < 0.4 {
                    *question_bonus.entry("chain_of_thought").or_default() += 0.1;
                    *question_bonus.entry("abductive").or_default() += 0.1;
                }
            }
        }

        // Compute weighted scores
        self.strategy_weights
            .iter()
            .map(|(s, w)| {
                let qb = question_bonus.get(s.as_str()).copied().unwrap_or(0.0);
                let db = domain_bonus.get(s).copied().unwrap_or(0.0);
                (s.clone(), w + qb + db)
            })
            .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(s, _)| s)
            .unwrap_or_else(|| "deductive".to_string())
    }

    /// Compute confidence calibration across all 10 bins.
    ///
    /// Returns stated confidence vs actual accuracy per bin.
    pub fn get_confidence_calibration(&self) -> HashMap<String, CalibrationInfo> {
        let mut calibration = HashMap::new();
        for bin_idx in 0..NUM_BINS {
            if let Some(data) = self.confidence_bins.get(&bin_idx) {
                if data.count > 0 {
                    let stated = (bin_idx as f64 + 0.5) / 10.0;
                    let actual = data.correct as f64 / data.count as f64;
                    let label = format!("{}-{}%", bin_idx * 10, (bin_idx + 1) * 10);
                    calibration.insert(
                        label,
                        CalibrationInfo {
                            stated_confidence: (stated * 100.0).round() / 100.0,
                            actual_accuracy: (actual * 10000.0).round() / 10000.0,
                            calibration_error: ((stated - actual).abs() * 10000.0).round()
                                / 10000.0,
                            count: data.count,
                        },
                    );
                }
            }
        }
        calibration
    }

    /// Apply temperature-scaled calibration to a stated confidence value.
    ///
    /// Uses the adaptive temperature parameter: conf^T.
    /// T > 1 softens overconfident predictions; T < 1 sharpens underconfident.
    pub fn calibrate_confidence(&self, stated_confidence: f64) -> f64 {
        if (self.total_evaluations as usize) < MIN_EVALS_FOR_TEMPERATURE {
            return stated_confidence;
        }
        let t = self.temperature.clamp(0.5, 3.0);
        if stated_confidence <= 0.0 {
            return 0.01;
        }
        stated_confidence.powf(t).clamp(0.01, 1.0)
    }

    /// Compute Expected Calibration Error (ECE).
    ///
    /// Uses the last 500 evaluations with temperature-scaled confidence values.
    /// Bins with fewer than 3 samples are skipped to avoid noise.
    pub fn get_overall_calibration_error(&self) -> f64 {
        let t = self.temperature.clamp(0.5, 3.0);

        // Use recent evaluations if we have enough
        let use_recent = self.evaluation_history.len() >= 10;

        if use_recent {
            let start = self.evaluation_history.len().saturating_sub(500);
            let recent = &self.evaluation_history[start..];

            // Build bins from calibrated confidence values
            let mut bins: HashMap<usize, (u64, u64, f64)> = HashMap::new(); // (count, correct, conf_sum)
            for entry in recent {
                let cal_conf = if t != 1.0 && entry.confidence > 0.0 {
                    entry.confidence.powf(t).clamp(0.01, 1.0)
                } else {
                    entry.confidence
                };
                let bin_idx = (cal_conf * 10.0).floor().min(9.0) as usize;
                let (count, correct, conf_sum) = bins.entry(bin_idx).or_insert((0, 0, 0.0));
                *count += 1;
                *conf_sum += cal_conf;
                if entry.correct {
                    *correct += 1;
                }
            }

            let mut total_samples = 0_u64;
            let mut weighted_error = 0.0_f64;
            for bin_idx in 0..NUM_BINS {
                if let Some(&(count, correct, conf_sum)) = bins.get(&bin_idx) {
                    if count < 3 {
                        continue;
                    }
                    let stated = conf_sum / count as f64;
                    let actual = correct as f64 / count as f64;
                    weighted_error += count as f64 * (stated - actual).abs();
                    total_samples += count;
                }
            }

            if total_samples == 0 {
                0.0
            } else {
                weighted_error / total_samples as f64
            }
        } else {
            // Fall back to raw bins
            let mut total_samples = 0_u64;
            let mut weighted_error = 0.0_f64;
            for bin_idx in 0..NUM_BINS {
                if let Some(data) = self.confidence_bins.get(&bin_idx) {
                    if data.count < 3 {
                        continue;
                    }
                    let stated = (bin_idx as f64 + 0.5) / 10.0;
                    let actual = data.correct as f64 / data.count as f64;
                    weighted_error += data.count as f64 * (stated - actual).abs();
                    total_samples += data.count;
                }
            }
            if total_samples == 0 {
                0.0
            } else {
                weighted_error / total_samples as f64
            }
        }
    }

    /// Track calibration error over time via sliding windows.
    pub fn get_calibration_trend(&self, window: usize) -> Vec<f64> {
        if self.evaluation_history.len() < window {
            return vec![self.get_overall_calibration_error()];
        }

        let mut trend = Vec::new();
        let step = window / 2;
        let mut start = 0;
        while start + window <= self.evaluation_history.len() {
            let window_entries = &self.evaluation_history[start..start + window];
            let mut bins: HashMap<usize, (u64, u64)> = HashMap::new();
            for entry in window_entries {
                let bin_idx = (entry.confidence * 10.0).floor().min(9.0) as usize;
                let (count, correct) = bins.entry(bin_idx).or_insert((0, 0));
                *count += 1;
                if entry.correct {
                    *correct += 1;
                }
            }

            let mut total_weight = 0.0_f64;
            let mut weighted_error = 0.0_f64;
            for (&bin_idx, &(count, correct)) in &bins {
                if count == 0 {
                    continue;
                }
                let stated = (bin_idx as f64 + 0.5) / 10.0;
                let actual = correct as f64 / count as f64;
                weighted_error += count as f64 * (stated - actual).abs();
                total_weight += count as f64;
            }

            let ece = if total_weight > 0.0 {
                weighted_error / total_weight
            } else {
                0.0
            };
            trend.push((ece * 10000.0).round() / 10000.0);

            start += step;
        }

        trend
    }

    /// Per-block metacognitive processing.
    ///
    /// Every 50 blocks: adapt strategy weights.
    /// Every 20 blocks: create meta-observation (returns true).
    pub fn process_block(&mut self, block_height: u64) -> (bool, bool) {
        let mut weights_adapted = false;
        let mut meta_node_due = false;

        if block_height > 0 && block_height % 50 == 0 {
            self.adapt_strategy_weights();
            weights_adapted = true;
        }

        if block_height > 0 && block_height % 20 == 0 {
            meta_node_due = self.total_evaluations >= 10;
        }

        (weights_adapted, meta_node_due)
    }

    /// Export comprehensive metacognitive state for monitoring.
    pub fn export_state(&self) -> MetacognitionSnapshot {
        let calibration = self.get_confidence_calibration();
        let trend = self.get_calibration_trend(50);

        let improving = if trend.len() >= 2 {
            let n = trend.len().min(3);
            let recent_avg: f64 = trend[trend.len() - n..].iter().sum::<f64>() / n as f64;
            let older_avg: f64 = trend[..n].iter().sum::<f64>() / n as f64;
            recent_avg < older_avg
        } else {
            false
        };

        let overall_accuracy = if self.total_evaluations > 0 {
            self.total_correct as f64 / self.total_evaluations as f64
        } else {
            0.0
        };

        // Find strongest/weakest domains
        let mut strongest_domain = String::new();
        let mut weakest_domain = String::new();
        let mut best_acc = -1.0_f64;
        let mut worst_acc = 2.0_f64;
        for (d, data) in &self.domain_stats {
            if data.attempts >= 5 {
                let acc = data.accuracy();
                if acc > best_acc {
                    best_acc = acc;
                    strongest_domain = d.clone();
                }
                if acc < worst_acc {
                    worst_acc = acc;
                    weakest_domain = d.clone();
                }
            }
        }

        MetacognitionSnapshot {
            overall_accuracy: (overall_accuracy * 10000.0).round() / 10000.0,
            total_evaluations: self.total_evaluations,
            calibration_error: (self.get_overall_calibration_error() * 10000.0).round() / 10000.0,
            calibration_temperature: (self.temperature * 10000.0).round() / 10000.0,
            calibration_improving: improving,
            calibration_trend: trend.iter().rev().take(10).copied().collect::<Vec<_>>().into_iter().rev().collect(),
            recommended_strategy: self.get_recommended_strategy("general", "general"),
            strategy_weights: self
                .strategy_weights
                .iter()
                .map(|(k, v)| (k.clone(), (*v * 10000.0).round() / 10000.0))
                .collect(),
            strongest_domain,
            weakest_domain,
            calibration,
        }
    }

    /// Get stats suitable for serialization/display.
    pub fn get_stats(&self) -> MetacognitionStats {
        let strategy_accuracies: HashMap<String, f64> = self
            .strategy_stats
            .iter()
            .filter(|(_, s)| s.attempts > 0)
            .map(|(name, s)| (name.clone(), (s.accuracy() * 10000.0).round() / 10000.0))
            .collect();

        let domain_accuracies: HashMap<String, f64> = self
            .domain_stats
            .iter()
            .filter(|(_, d)| d.attempts > 0)
            .map(|(name, d)| (name.clone(), (d.accuracy() * 10000.0).round() / 10000.0))
            .collect();

        let overall_accuracy = if self.total_evaluations > 0 {
            (self.total_correct as f64 / self.total_evaluations as f64 * 10000.0).round() / 10000.0
        } else {
            0.0
        };

        let cal_trend = self.get_calibration_trend(50);
        let calibration_improving = cal_trend.len() >= 2 && cal_trend.last() < cal_trend.first();

        MetacognitionStats {
            total_evaluations: self.total_evaluations,
            total_correct: self.total_correct,
            overall_accuracy,
            calibration_error: (self.get_overall_calibration_error() * 10000.0).round() / 10000.0,
            calibration_temperature: (self.temperature * 10000.0).round() / 10000.0,
            calibration_improving,
            strategy_accuracies,
            strategy_weights: self
                .strategy_weights
                .iter()
                .map(|(k, v)| (k.clone(), (*v * 10000.0).round() / 10000.0))
                .collect(),
            domain_accuracies,
        }
    }

    // -- Accessors for other modules --

    /// Get the current temperature.
    pub fn temperature(&self) -> f64 {
        self.temperature
    }

    /// Get total evaluations count.
    pub fn total_evaluations(&self) -> u64 {
        self.total_evaluations
    }

    /// Get total correct count.
    pub fn total_correct(&self) -> u64 {
        self.total_correct
    }

    /// Get mutable reference to strategy weights (for SelfImprovement sync).
    pub fn strategy_weights_mut(&mut self) -> &mut HashMap<String, f64> {
        &mut self.strategy_weights
    }

    /// Get reference to strategy weights.
    pub fn strategy_weights(&self) -> &HashMap<String, f64> {
        &self.strategy_weights
    }
}

// ---------------------------------------------------------------------------
// Snapshot / Stats types
// ---------------------------------------------------------------------------

/// Full metacognitive state snapshot for API/dashboard exposure.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MetacognitionSnapshot {
    pub overall_accuracy: f64,
    pub total_evaluations: u64,
    pub calibration_error: f64,
    pub calibration_temperature: f64,
    pub calibration_improving: bool,
    pub calibration_trend: Vec<f64>,
    pub recommended_strategy: String,
    pub strategy_weights: HashMap<String, f64>,
    pub strongest_domain: String,
    pub weakest_domain: String,
    pub calibration: HashMap<String, CalibrationInfo>,
}

/// Compact stats for get_stats().
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MetacognitionStats {
    pub total_evaluations: u64,
    pub total_correct: u64,
    pub overall_accuracy: f64,
    pub calibration_error: f64,
    pub calibration_temperature: f64,
    pub calibration_improving: bool,
    pub strategy_accuracies: HashMap<String, f64>,
    pub strategy_weights: HashMap<String, f64>,
    pub domain_accuracies: HashMap<String, f64>,
}

// ---------------------------------------------------------------------------
// PyO3 methods
// ---------------------------------------------------------------------------

#[pymethods]
impl MetacognitionEngine {
    #[new]
    pub fn py_new() -> Self {
        Self::new()
    }

    /// Record the outcome of a reasoning operation.
    #[pyo3(name = "evaluate_reasoning")]
    #[pyo3(signature = (strategy, confidence, outcome_correct, domain = "general", block_height = 0))]
    pub fn py_evaluate_reasoning(
        &mut self,
        strategy: &str,
        confidence: f64,
        outcome_correct: bool,
        domain: &str,
        block_height: u64,
    ) -> PyResult<PyObject> {
        let stats = self.evaluate_reasoning(strategy, confidence, outcome_correct, domain, block_height);
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("attempts", stats.attempts)?;
            dict.set_item("correct", stats.correct)?;
            dict.set_item("total_confidence", stats.total_confidence)?;
            dict.set_item("total_actual", stats.total_actual)?;
            Ok(dict.into())
        })
    }

    /// Adapt strategy weights based on performance data.
    #[pyo3(name = "adapt_strategy_weights")]
    pub fn py_adapt_strategy_weights(&mut self) -> PyResult<PyObject> {
        let weights = self.adapt_strategy_weights();
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            for (k, v) in &weights {
                dict.set_item(k, v)?;
            }
            Ok(dict.into())
        })
    }

    /// Get recommended strategy for domain/question type.
    #[pyo3(name = "get_recommended_strategy")]
    #[pyo3(signature = (domain = "general", question_type = "general"))]
    pub fn py_get_recommended_strategy(&self, domain: &str, question_type: &str) -> String {
        self.get_recommended_strategy(domain, question_type)
    }

    /// Apply temperature calibration to a confidence value.
    #[pyo3(name = "calibrate_confidence")]
    pub fn py_calibrate_confidence(&self, stated_confidence: f64) -> f64 {
        self.calibrate_confidence(stated_confidence)
    }

    /// Get the Expected Calibration Error.
    #[pyo3(name = "get_overall_calibration_error")]
    pub fn py_get_overall_calibration_error(&self) -> f64 {
        self.get_overall_calibration_error()
    }

    /// Process a block (periodic adaptation).
    #[pyo3(name = "process_block")]
    pub fn py_process_block(&mut self, block_height: u64) -> PyResult<PyObject> {
        let (weights_adapted, meta_node_due) = self.process_block(block_height);
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("weights_adapted", weights_adapted)?;
            dict.set_item("meta_node_created", meta_node_due)?;
            Ok(dict.into())
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
            let result = json_mod.call_method1("loads", (json,))?;
            Ok(result.into())
        })
    }

    /// Get the current temperature value.
    #[pyo3(name = "get_temperature")]
    pub fn py_get_temperature(&self) -> f64 {
        self.temperature
    }

    /// Get total evaluations.
    #[pyo3(name = "get_total_evaluations")]
    pub fn py_get_total_evaluations(&self) -> u64 {
        self.total_evaluations
    }

    fn __repr__(&self) -> String {
        format!(
            "MetacognitionEngine(evaluations={}, accuracy={:.3}, ECE={:.4}, T={:.3})",
            self.total_evaluations,
            if self.total_evaluations > 0 {
                self.total_correct as f64 / self.total_evaluations as f64
            } else {
                0.0
            },
            self.get_overall_calibration_error(),
            self.temperature,
        )
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_engine() -> MetacognitionEngine {
        MetacognitionEngine::new()
    }

    #[test]
    fn test_new_has_default_weights() {
        let eng = make_engine();
        assert_eq!(eng.strategy_weights.len(), STRATEGIES.len());
        for &s in STRATEGIES {
            assert!((eng.strategy_weights[s] - 1.0).abs() < f64::EPSILON);
        }
    }

    #[test]
    fn test_evaluate_reasoning_increments() {
        let mut eng = make_engine();
        let stats = eng.evaluate_reasoning("deductive", 0.8, true, "general", 1);
        assert_eq!(stats.attempts, 1);
        assert_eq!(stats.correct, 1);
        assert_eq!(eng.total_evaluations, 1);
        assert_eq!(eng.total_correct, 1);
    }

    #[test]
    fn test_evaluate_reasoning_failure() {
        let mut eng = make_engine();
        let stats = eng.evaluate_reasoning("neural", 0.6, false, "physics", 2);
        assert_eq!(stats.attempts, 1);
        assert_eq!(stats.correct, 0);
        assert_eq!(eng.total_evaluations, 1);
        assert_eq!(eng.total_correct, 0);
    }

    #[test]
    fn test_confidence_bin_placement() {
        let mut eng = make_engine();
        eng.evaluate_reasoning("deductive", 0.75, true, "general", 1);
        // 0.75 -> bin 7
        assert!(eng.confidence_bins.contains_key(&7));
        assert_eq!(eng.confidence_bins[&7].count, 1);
    }

    #[test]
    fn test_confidence_bin_edge_case_one() {
        let mut eng = make_engine();
        eng.evaluate_reasoning("deductive", 1.0, true, "general", 1);
        // 1.0 -> bin 9 (clamped)
        assert!(eng.confidence_bins.contains_key(&9));
    }

    #[test]
    fn test_confidence_bin_edge_case_zero() {
        let mut eng = make_engine();
        eng.evaluate_reasoning("deductive", 0.0, false, "general", 1);
        assert!(eng.confidence_bins.contains_key(&0));
    }

    #[test]
    fn test_history_bounded() {
        let mut eng = make_engine();
        for i in 0..600 {
            eng.evaluate_reasoning("deductive", 0.5, i % 2 == 0, "general", i as u64);
        }
        assert!(eng.evaluation_history.len() <= MAX_HISTORY);
    }

    #[test]
    fn test_calibrate_confidence_below_threshold() {
        let eng = make_engine();
        // No evaluations yet, should return raw confidence
        assert!((eng.calibrate_confidence(0.8) - 0.8).abs() < f64::EPSILON);
    }

    #[test]
    fn test_calibrate_confidence_zero() {
        let mut eng = make_engine();
        // Fill enough evaluations
        for i in 0..50 {
            eng.evaluate_reasoning("deductive", 0.5, i % 2 == 0, "general", i as u64);
        }
        assert!((eng.calibrate_confidence(0.0) - 0.01).abs() < f64::EPSILON);
    }

    #[test]
    fn test_calibrate_confidence_after_training() {
        let mut eng = make_engine();
        for i in 0..50 {
            eng.evaluate_reasoning("deductive", 0.9, i % 3 != 0, "general", i as u64);
        }
        eng.update_temperature();
        let calibrated = eng.calibrate_confidence(0.9);
        // Temperature should adjust, so calibrated != raw
        assert!(calibrated > 0.0 && calibrated <= 1.0);
    }

    #[test]
    fn test_temperature_not_updated_below_threshold() {
        let mut eng = make_engine();
        for i in 0..10 {
            eng.evaluate_reasoning("deductive", 0.5, true, "general", i as u64);
        }
        let old_t = eng.temperature;
        eng.update_temperature();
        assert!((eng.temperature - old_t).abs() < f64::EPSILON);
    }

    #[test]
    fn test_temperature_updated_above_threshold() {
        let mut eng = make_engine();
        // Overconfident predictions: high confidence, low accuracy
        for i in 0..40 {
            eng.evaluate_reasoning("deductive", 0.9, i % 5 == 0, "general", i as u64);
        }
        let old_t = eng.temperature;
        eng.update_temperature();
        // Temperature should increase (to correct overconfidence)
        assert!(eng.temperature > old_t);
    }

    #[test]
    fn test_adapt_strategy_weights_no_data() {
        let mut eng = make_engine();
        let w = eng.adapt_strategy_weights();
        // No changes with insufficient data
        for &s in STRATEGIES {
            assert!((w[s] - 1.0).abs() < f64::EPSILON);
        }
    }

    #[test]
    fn test_adapt_strategy_weights_with_data() {
        let mut eng = make_engine();
        // Deductive always correct, neural always wrong
        for i in 0..20 {
            eng.evaluate_reasoning("deductive", 0.8, true, "general", i as u64);
            eng.evaluate_reasoning("neural", 0.8, false, "general", i as u64);
        }
        let w = eng.adapt_strategy_weights();
        assert!(w["deductive"] > w["neural"]);
    }

    #[test]
    fn test_get_recommended_strategy_default() {
        let eng = make_engine();
        let s = eng.get_recommended_strategy("general", "general");
        // Should be one of the strategies
        assert!(STRATEGIES.contains(&s.as_str()));
    }

    #[test]
    fn test_get_recommended_strategy_causal() {
        let eng = make_engine();
        let s = eng.get_recommended_strategy("physics", "causal");
        // Causal question type should boost causal strategy
        assert_eq!(s, "causal");
    }

    #[test]
    fn test_get_recommended_strategy_factual() {
        let eng = make_engine();
        let s = eng.get_recommended_strategy("physics", "factual");
        assert_eq!(s, "deductive");
    }

    #[test]
    fn test_domain_stats_tracking() {
        let mut eng = make_engine();
        eng.evaluate_reasoning("deductive", 0.8, true, "quantum_physics", 1);
        eng.evaluate_reasoning("neural", 0.6, false, "quantum_physics", 2);
        assert_eq!(eng.domain_stats["quantum_physics"].attempts, 2);
        assert_eq!(eng.domain_stats["quantum_physics"].correct, 1);
    }

    #[test]
    fn test_get_overall_calibration_error_empty() {
        let eng = make_engine();
        assert!((eng.get_overall_calibration_error()).abs() < f64::EPSILON);
    }

    #[test]
    fn test_get_overall_calibration_error_perfect() {
        let mut eng = make_engine();
        // Perfect calibration: confidence matches outcome rate
        for _ in 0..10 {
            eng.evaluate_reasoning("deductive", 0.55, true, "general", 1);
            eng.evaluate_reasoning("deductive", 0.55, false, "general", 2);
        }
        // With 50% correct at 0.55 confidence, error should be small
        let ece = eng.get_overall_calibration_error();
        assert!(ece < 0.2);
    }

    #[test]
    fn test_get_calibration_trend_insufficient() {
        let mut eng = make_engine();
        eng.evaluate_reasoning("deductive", 0.5, true, "general", 1);
        let trend = eng.get_calibration_trend(50);
        assert_eq!(trend.len(), 1); // Just the overall ECE
    }

    #[test]
    fn test_get_calibration_trend_sufficient() {
        let mut eng = make_engine();
        for i in 0..200 {
            eng.evaluate_reasoning("deductive", 0.5, i % 2 == 0, "general", i as u64);
        }
        let trend = eng.get_calibration_trend(50);
        assert!(trend.len() >= 2);
    }

    #[test]
    fn test_process_block_adaptation_interval() {
        let mut eng = make_engine();
        let (adapted, _) = eng.process_block(50);
        assert!(adapted);
        let (adapted, _) = eng.process_block(51);
        assert!(!adapted);
    }

    #[test]
    fn test_process_block_meta_observation_interval() {
        let mut eng = make_engine();
        // Need at least 10 evaluations for meta node
        for i in 0..15 {
            eng.evaluate_reasoning("deductive", 0.5, true, "general", i as u64);
        }
        let (_, meta_due) = eng.process_block(20);
        assert!(meta_due);
        let (_, meta_due) = eng.process_block(21);
        assert!(!meta_due);
    }

    #[test]
    fn test_process_block_zero() {
        let mut eng = make_engine();
        let (adapted, meta_due) = eng.process_block(0);
        assert!(!adapted);
        assert!(!meta_due);
    }

    #[test]
    fn test_export_state() {
        let mut eng = make_engine();
        for i in 0..30 {
            eng.evaluate_reasoning("deductive", 0.8, i % 3 != 0, "physics", i as u64);
            eng.evaluate_reasoning("neural", 0.6, i % 4 == 0, "math", i as u64);
        }
        let snap = eng.export_state();
        assert!(snap.total_evaluations == 60);
        assert!(!snap.recommended_strategy.is_empty());
    }

    #[test]
    fn test_get_stats() {
        let mut eng = make_engine();
        for i in 0..20 {
            eng.evaluate_reasoning("deductive", 0.7, i % 2 == 0, "general", i as u64);
        }
        let stats = eng.get_stats();
        assert_eq!(stats.total_evaluations, 20);
        assert_eq!(stats.total_correct, 10);
        assert!((stats.overall_accuracy - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_get_confidence_calibration_empty() {
        let eng = make_engine();
        let cal = eng.get_confidence_calibration();
        assert!(cal.is_empty());
    }

    #[test]
    fn test_get_confidence_calibration_populated() {
        let mut eng = make_engine();
        for _ in 0..5 {
            eng.evaluate_reasoning("deductive", 0.85, true, "general", 1);
        }
        let cal = eng.get_confidence_calibration();
        assert!(cal.contains_key("80-90%"));
        assert_eq!(cal["80-90%"].count, 5);
    }

    #[test]
    fn test_strategy_stats_accuracy() {
        let stats = StrategyStats {
            attempts: 10,
            correct: 7,
            total_confidence: 0.0,
            total_actual: 0.0,
        };
        assert!((stats.accuracy() - 0.7).abs() < f64::EPSILON);
    }

    #[test]
    fn test_strategy_stats_accuracy_zero() {
        let stats = StrategyStats::default();
        assert!((stats.accuracy()).abs() < f64::EPSILON);
    }

    #[test]
    fn test_domain_stats_accuracy() {
        let ds = DomainStats {
            attempts: 20,
            correct: 15,
        };
        assert!((ds.accuracy() - 0.75).abs() < f64::EPSILON);
    }

    #[test]
    fn test_multiple_strategies_tracked() {
        let mut eng = make_engine();
        eng.evaluate_reasoning("deductive", 0.9, true, "general", 1);
        eng.evaluate_reasoning("inductive", 0.7, false, "general", 2);
        eng.evaluate_reasoning("causal", 0.5, true, "general", 3);
        assert_eq!(eng.strategy_stats.len(), 3);
        assert_eq!(eng.strategy_stats["deductive"].correct, 1);
        assert_eq!(eng.strategy_stats["inductive"].correct, 0);
        assert_eq!(eng.strategy_stats["causal"].correct, 1);
    }

    #[test]
    fn test_serde_roundtrip() {
        let mut eng = make_engine();
        for i in 0..5 {
            eng.evaluate_reasoning("deductive", 0.5, i % 2 == 0, "general", i as u64);
        }
        let json = serde_json::to_string(&eng).unwrap();
        let back: MetacognitionEngine = serde_json::from_str(&json).unwrap();
        assert_eq!(back.total_evaluations, eng.total_evaluations);
        assert_eq!(back.total_correct, eng.total_correct);
    }
}
