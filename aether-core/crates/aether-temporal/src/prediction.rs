//! Prediction engine with verification and accuracy tracking.
//!
//! Predictions are first-class objects: they have a unique ID, a target metric,
//! a deadline (block height), and a declared confidence. After the deadline,
//! predictions are verified against actual values. The accuracy tracker maintains
//! per-method rolling statistics so the engine can select the best forecasting
//! method for each target.

use crate::time_series::TimeSeries;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Errors from prediction operations.
#[derive(Debug, Error)]
pub enum PredictionError {
    #[error("no history for target '{0}'")]
    NoHistory(String),
    #[error("prediction {0} not found")]
    NotFound(u64),
    #[error("prediction {0} already resolved")]
    AlreadyResolved(u64),
    #[error("time series error: {0}")]
    TimeSeries(#[from] crate::time_series::TimeSeriesError),
}

/// Method used to generate a prediction.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PredictionMethod {
    /// Linear extrapolation from trend line.
    LinearExtrapolation,
    /// Exponential moving average (flat forecast).
    EMA,
    /// Pattern matching from detected periodicity.
    PatternMatch,
    /// Derived from a temporal invariant (e.g., "difficulty always increases").
    TemporalInvariant,
}

impl std::fmt::Display for PredictionMethod {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PredictionMethod::LinearExtrapolation => write!(f, "linear_extrapolation"),
            PredictionMethod::EMA => write!(f, "ema"),
            PredictionMethod::PatternMatch => write!(f, "pattern_match"),
            PredictionMethod::TemporalInvariant => write!(f, "temporal_invariant"),
        }
    }
}

/// Status of a prediction.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum PredictionStatus {
    /// Not yet verified.
    Pending,
    /// Verified correct: actual value was within tolerance.
    Verified(f64),
    /// Falsified: actual value was outside tolerance.
    Falsified(f64),
    /// Deadline passed without verification data.
    Expired,
}

/// A prediction made by the engine.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Prediction {
    /// Unique prediction ID.
    pub id: u64,
    /// Domain this prediction belongs to (e.g., "consensus", "network").
    pub domain: String,
    /// Target metric (e.g., "block_difficulty", "tx_count").
    pub target: String,
    /// Predicted value.
    pub predicted_value: f64,
    /// Confidence in this prediction (0.0 to 1.0).
    pub confidence: f64,
    /// Block height when the prediction was made.
    pub block_created: u64,
    /// Block height by which the prediction should be verified.
    pub block_deadline: u64,
    /// Method used to generate this prediction.
    pub method: PredictionMethod,
    /// Current status.
    pub status: PredictionStatus,
}

/// Result of verifying a prediction against reality.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VerificationResult {
    /// The prediction ID that was verified.
    pub prediction_id: u64,
    /// Predicted value.
    pub predicted: f64,
    /// Actual observed value.
    pub actual: f64,
    /// Absolute error.
    pub absolute_error: f64,
    /// Relative error (absolute_error / |actual|), or NaN if actual is 0.
    pub relative_error: f64,
    /// Whether the prediction was within tolerance.
    pub correct: bool,
    /// The tolerance used for verification.
    pub tolerance: f64,
}

/// Tracks prediction accuracy for a specific method on a specific target.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AccuracyTracker {
    /// Rolling window of (predicted, actual) pairs.
    pub history: Vec<(f64, f64)>,
    /// Maximum history size (oldest entries evicted).
    pub max_history: usize,
}

impl AccuracyTracker {
    /// Create a new tracker with the given window size.
    pub fn new(max_history: usize) -> Self {
        Self {
            history: Vec::new(),
            max_history,
        }
    }

    /// Record a (predicted, actual) observation.
    pub fn record(&mut self, predicted: f64, actual: f64) {
        self.history.push((predicted, actual));
        if self.history.len() > self.max_history {
            self.history.remove(0);
        }
    }

    /// Fraction of predictions within the given tolerance.
    ///
    /// Tolerance is relative: |predicted - actual| / |actual| < tolerance,
    /// or |predicted - actual| < abs_tolerance for values near zero.
    pub fn accuracy(&self, relative_tolerance: f64, abs_tolerance: f64) -> f64 {
        if self.history.is_empty() {
            return 0.0;
        }
        let correct = self
            .history
            .iter()
            .filter(|(p, a)| {
                let err = (p - a).abs();
                if a.abs() < abs_tolerance {
                    err < abs_tolerance
                } else {
                    err / a.abs() < relative_tolerance
                }
            })
            .count();
        correct as f64 / self.history.len() as f64
    }

    /// Mean absolute error across all recorded predictions.
    pub fn mean_absolute_error(&self) -> f64 {
        if self.history.is_empty() {
            return f64::INFINITY;
        }
        let sum: f64 = self.history.iter().map(|(p, a)| (p - a).abs()).sum();
        sum / self.history.len() as f64
    }

    /// Calibration score: correlation between stated confidence levels and
    /// actual accuracy. Returns a value in [-1, 1]. Higher = better calibrated.
    ///
    /// Requires paired (confidence, was_correct) data, which we don't track here
    /// directly. Returns 0.0 as a default since we track (predicted, actual).
    pub fn count(&self) -> usize {
        self.history.len()
    }
}

/// The prediction engine: manages predictions, selects methods, verifies outcomes.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PredictionEngine {
    /// All predictions (active and resolved).
    pub predictions: Vec<Prediction>,
    /// Per-target time series history.
    pub history: HashMap<String, TimeSeries>,
    /// Per-(target, method) accuracy trackers.
    pub accuracy: HashMap<(String, String), AccuracyTracker>,
    /// Next prediction ID.
    next_id: u64,
    /// Default EMA alpha.
    pub ema_alpha: f64,
    /// Relative tolerance for verification (fraction of actual value).
    pub relative_tolerance: f64,
    /// Absolute tolerance for verification (for values near zero).
    pub abs_tolerance: f64,
}

impl Default for PredictionEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl PredictionEngine {
    /// Create a new prediction engine with default parameters.
    pub fn new() -> Self {
        Self {
            predictions: Vec::new(),
            history: HashMap::new(),
            accuracy: HashMap::new(),
            next_id: 1,
            ema_alpha: 0.3,
            relative_tolerance: 0.10, // 10% tolerance
            abs_tolerance: 1.0,
        }
    }

    /// Record an observed value for a target metric.
    pub fn observe(&mut self, target: &str, time: f64, value: f64) {
        self.history
            .entry(target.to_string())
            .or_insert_with(|| TimeSeries::new(target))
            .push(time, value);
    }

    /// Make a prediction for a target metric.
    ///
    /// Tries multiple forecasting methods and picks the one with the best
    /// historical accuracy for this target. If no history exists, defaults
    /// to linear extrapolation.
    pub fn make_prediction(
        &mut self,
        target: &str,
        domain: &str,
        current_block: u64,
        horizon: u64,
    ) -> Result<Prediction, PredictionError> {
        let ts = self
            .history
            .get(target)
            .ok_or_else(|| PredictionError::NoHistory(target.to_string()))?;

        if ts.len() < 2 {
            return Err(PredictionError::TimeSeries(
                crate::time_series::TimeSeriesError::InsufficientData {
                    need: 2,
                    have: ts.len(),
                },
            ));
        }

        // Try each method and collect (method, predicted_value).
        let mut candidates: Vec<(PredictionMethod, f64)> = Vec::new();

        // Linear extrapolation.
        if let Ok(forecast) = ts.forecast_linear(horizon as usize) {
            if let Some(last) = forecast.last() {
                candidates.push((PredictionMethod::LinearExtrapolation, last.1));
            }
        }

        // EMA forecast.
        if let Ok(forecast) = ts.forecast_ema(self.ema_alpha, horizon as usize) {
            if let Some(last) = forecast.last() {
                candidates.push((PredictionMethod::EMA, last.1));
            }
        }

        // Pattern match: if periodicity detected, use the value from one period ago.
        if ts.len() >= 10 {
            if let Ok(periods) = ts.detect_periodicity(ts.len() / 2, 0.5) {
                if let Some(&period) = periods.first() {
                    let values = ts.values();
                    let idx = values.len() - period;
                    if idx < values.len() {
                        candidates.push((PredictionMethod::PatternMatch, values[idx]));
                    }
                }
            }
        }

        if candidates.is_empty() {
            return Err(PredictionError::NoHistory(target.to_string()));
        }

        // Select best method by historical accuracy.
        let (best_method, predicted_value) = candidates
            .into_iter()
            .max_by(|(m_a, _), (m_b, _)| {
                let acc_a = self.method_accuracy(target, m_a);
                let acc_b = self.method_accuracy(target, m_b);
                acc_a.partial_cmp(&acc_b).unwrap_or(std::cmp::Ordering::Equal)
            })
            .unwrap(); // Safe: candidates is non-empty.

        let confidence = self.method_accuracy(target, &best_method).max(0.1).min(0.95);

        let prediction = Prediction {
            id: self.next_id,
            domain: domain.to_string(),
            target: target.to_string(),
            predicted_value,
            confidence,
            block_created: current_block,
            block_deadline: current_block + horizon,
            method: best_method,
            status: PredictionStatus::Pending,
        };

        self.next_id += 1;
        self.predictions.push(prediction.clone());
        Ok(prediction)
    }

    /// Verify a prediction against an actual observed value.
    pub fn verify_prediction(
        &mut self,
        pred_id: u64,
        actual_value: f64,
    ) -> Result<VerificationResult, PredictionError> {
        let pred = self
            .predictions
            .iter_mut()
            .find(|p| p.id == pred_id)
            .ok_or(PredictionError::NotFound(pred_id))?;

        if !matches!(pred.status, PredictionStatus::Pending) {
            return Err(PredictionError::AlreadyResolved(pred_id));
        }

        let absolute_error = (pred.predicted_value - actual_value).abs();
        let relative_error = if actual_value.abs() < self.abs_tolerance {
            absolute_error / self.abs_tolerance
        } else {
            absolute_error / actual_value.abs()
        };

        let correct = relative_error < self.relative_tolerance
            || absolute_error < self.abs_tolerance;

        // Update prediction status.
        pred.status = if correct {
            PredictionStatus::Verified(actual_value)
        } else {
            PredictionStatus::Falsified(actual_value)
        };

        // Update accuracy tracker.
        let key = (pred.target.clone(), pred.method.to_string());
        self.accuracy
            .entry(key)
            .or_insert_with(|| AccuracyTracker::new(100))
            .record(pred.predicted_value, actual_value);

        Ok(VerificationResult {
            prediction_id: pred_id,
            predicted: pred.predicted_value,
            actual: actual_value,
            absolute_error,
            relative_error,
            correct,
            tolerance: self.relative_tolerance,
        })
    }

    /// Expire all pending predictions past their deadline.
    pub fn expire_pending(&mut self, current_block: u64) {
        for pred in &mut self.predictions {
            if matches!(pred.status, PredictionStatus::Pending)
                && current_block > pred.block_deadline
            {
                pred.status = PredictionStatus::Expired;
            }
        }
    }

    /// Get the historical accuracy for a (target, method) pair.
    /// Returns 0.5 (neutral prior) if no history.
    fn method_accuracy(&self, target: &str, method: &PredictionMethod) -> f64 {
        let key = (target.to_string(), method.to_string());
        self.accuracy
            .get(&key)
            .map(|t| {
                if t.count() < 3 {
                    0.5 // Not enough data -- neutral prior.
                } else {
                    t.accuracy(self.relative_tolerance, self.abs_tolerance)
                }
            })
            .unwrap_or(0.5)
    }

    /// Get overall prediction statistics.
    pub fn stats(&self) -> PredictionStats {
        let total = self.predictions.len();
        let pending = self
            .predictions
            .iter()
            .filter(|p| matches!(p.status, PredictionStatus::Pending))
            .count();
        let verified = self
            .predictions
            .iter()
            .filter(|p| matches!(p.status, PredictionStatus::Verified(_)))
            .count();
        let falsified = self
            .predictions
            .iter()
            .filter(|p| matches!(p.status, PredictionStatus::Falsified(_)))
            .count();
        let expired = self
            .predictions
            .iter()
            .filter(|p| matches!(p.status, PredictionStatus::Expired))
            .count();
        let accuracy = if verified + falsified > 0 {
            verified as f64 / (verified + falsified) as f64
        } else {
            0.0
        };

        PredictionStats {
            total,
            pending,
            verified,
            falsified,
            expired,
            accuracy,
        }
    }
}

/// Summary statistics for the prediction engine.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PredictionStats {
    pub total: usize,
    pub pending: usize,
    pub verified: usize,
    pub falsified: usize,
    pub expired: usize,
    pub accuracy: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_accuracy_tracker() {
        let mut tracker = AccuracyTracker::new(10);
        // 10% tolerance.
        tracker.record(100.0, 105.0); // 5% error -- within tolerance
        tracker.record(100.0, 120.0); // 20% error -- outside
        tracker.record(100.0, 95.0); // 5% error -- within
        assert_eq!(tracker.count(), 3);
        let acc = tracker.accuracy(0.10, 1.0);
        assert!((acc - 2.0 / 3.0).abs() < 1e-10);
    }

    #[test]
    fn test_accuracy_tracker_mae() {
        let mut tracker = AccuracyTracker::new(10);
        tracker.record(10.0, 12.0); // err = 2
        tracker.record(10.0, 8.0); // err = 2
        tracker.record(10.0, 10.0); // err = 0
        assert!((tracker.mean_absolute_error() - 4.0 / 3.0).abs() < 1e-10);
    }

    #[test]
    fn test_prediction_engine_observe_and_predict() {
        let mut engine = PredictionEngine::new();
        // Feed a linear trend: value = 2 * block + 10.
        for i in 0..50 {
            engine.observe("difficulty", i as f64, 2.0 * i as f64 + 10.0);
        }

        let pred = engine
            .make_prediction("difficulty", "consensus", 50, 10)
            .unwrap();
        assert_eq!(pred.target, "difficulty");
        assert_eq!(pred.block_deadline, 60);
        // The engine picks the best method among linear extrapolation, EMA, and
        // pattern match. With no prior accuracy data, all methods start at 0.5
        // confidence and the max_by picks one. The predicted value should be
        // a reasonable extrapolation from y=2x+10 at x=0..49.
        // Linear extrapolation: ~128, EMA(0.3): ~103. Either is valid.
        assert!(
            pred.predicted_value > 50.0 && pred.predicted_value < 200.0,
            "predicted {} should be a reasonable extrapolation",
            pred.predicted_value
        );
    }

    #[test]
    fn test_prediction_verification() {
        let mut engine = PredictionEngine::new();
        for i in 0..50 {
            engine.observe("tx_count", i as f64, 100.0);
        }

        let pred = engine
            .make_prediction("tx_count", "network", 50, 5)
            .unwrap();
        let result = engine.verify_prediction(pred.id, 100.0).unwrap();
        assert!(result.correct);
        assert!(result.absolute_error < 1.0);
    }

    #[test]
    fn test_prediction_falsified() {
        let mut engine = PredictionEngine::new();
        for i in 0..50 {
            engine.observe("metric", i as f64, 10.0);
        }

        let pred = engine
            .make_prediction("metric", "test", 50, 5)
            .unwrap();
        // Actual is wildly different.
        let result = engine.verify_prediction(pred.id, 1000.0).unwrap();
        assert!(!result.correct);
    }

    #[test]
    fn test_double_verify_fails() {
        let mut engine = PredictionEngine::new();
        for i in 0..50 {
            engine.observe("m", i as f64, 1.0);
        }
        let pred = engine.make_prediction("m", "d", 50, 5).unwrap();
        engine.verify_prediction(pred.id, 1.0).unwrap();
        assert!(engine.verify_prediction(pred.id, 1.0).is_err());
    }

    #[test]
    fn test_expire_pending() {
        let mut engine = PredictionEngine::new();
        for i in 0..50 {
            engine.observe("m", i as f64, 1.0);
        }
        let pred = engine.make_prediction("m", "d", 50, 5).unwrap();
        assert!(matches!(pred.status, PredictionStatus::Pending));
        engine.expire_pending(100);
        let p = engine.predictions.iter().find(|p| p.id == pred.id).unwrap();
        assert!(matches!(p.status, PredictionStatus::Expired));
    }

    #[test]
    fn test_stats() {
        let mut engine = PredictionEngine::new();
        for i in 0..50 {
            engine.observe("m", i as f64, 10.0);
        }
        engine.make_prediction("m", "d", 50, 5).unwrap();
        engine.make_prediction("m", "d", 50, 10).unwrap();
        let stats = engine.stats();
        assert_eq!(stats.total, 2);
        assert_eq!(stats.pending, 2);
    }

    #[test]
    fn test_no_history_error() {
        let mut engine = PredictionEngine::new();
        let err = engine.make_prediction("nonexistent", "d", 0, 5);
        assert!(err.is_err());
    }
}
