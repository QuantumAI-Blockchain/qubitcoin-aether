//! Autonomous Curiosity Engine for Aether Tree AI.
//!
//! Provides intrinsic motivation by tracking prediction errors per domain
//! and suggesting exploration goals based on knowledge gaps. Higher
//! prediction error signals more interesting (less understood) territory,
//! driving the system to explore what it does not yet know.

use std::collections::HashMap;

use parking_lot::RwLock;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROLLING_WINDOW: usize = 100;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// A curiosity-driven discovery record.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Discovery {
    pub domain: String,
    pub topic: String,
    pub block_height: u64,
}

/// An exploration goal suggestion.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExplorationGoal {
    pub domain: String,
    pub curiosity_score: f64,
    pub question: String,
}

/// Curiosity stats snapshot.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CuriosityStats {
    pub curiosity_scores: HashMap<String, f64>,
    pub top_interests: Vec<String>,
    pub discoveries_count: usize,
    pub domains_tracked: usize,
}

// ---------------------------------------------------------------------------
// CuriosityEngine
// ---------------------------------------------------------------------------

/// Drives autonomous exploration via prediction-error curiosity.
///
/// Tracks prediction errors per domain in a rolling window and suggests
/// exploration goals targeting the domains with the highest mean error.
#[pyclass]
pub struct CuriosityEngine {
    /// domain -> rolling list of |predicted - actual| values (max ROLLING_WINDOW)
    prediction_errors: RwLock<HashMap<String, Vec<f64>>>,
    /// (domain, topic, block_height) tuples
    exploration_history: RwLock<Vec<Discovery>>,
}

impl Default for CuriosityEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl CuriosityEngine {
    /// Create a new CuriosityEngine.
    pub fn new() -> Self {
        Self {
            prediction_errors: RwLock::new(HashMap::new()),
            exploration_history: RwLock::new(Vec::new()),
        }
    }

    /// Compute curiosity score per domain (mean prediction error).
    pub fn compute_curiosity_scores(&self) -> HashMap<String, f64> {
        let errors = self.prediction_errors.read();
        let mut scores = HashMap::new();
        for (domain, errs) in errors.iter() {
            if !errs.is_empty() {
                let mean = errs.iter().sum::<f64>() / errs.len() as f64;
                scores.insert(domain.clone(), mean);
            }
        }
        scores
    }

    /// Pick the highest-curiosity domain and generate a question.
    pub fn suggest_exploration_goal(&self) -> Option<ExplorationGoal> {
        let scores = self.compute_curiosity_scores();
        if scores.is_empty() {
            return None;
        }

        let best_domain = scores
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(k, _)| k.clone())?;

        let score = scores[&best_domain];
        let question = self.generate_exploration_question(&best_domain);

        Some(ExplorationGoal {
            domain: best_domain,
            curiosity_score: score,
            question,
        })
    }

    /// Record the absolute error of a prediction for a domain.
    pub fn record_prediction_outcome(
        &self,
        domain: &str,
        predicted: f64,
        actual: f64,
        _topic: &str,
    ) {
        let error = (predicted - actual).abs();
        let mut errors = self.prediction_errors.write();
        let buf = errors.entry(domain.to_string()).or_default();
        buf.push(error);
        if buf.len() > ROLLING_WINDOW {
            let excess = buf.len() - ROLLING_WINDOW;
            buf.drain(..excess);
        }
    }

    /// Log a curiosity-driven discovery.
    pub fn record_discovery(&self, domain: &str, topic: &str, block_height: u64) {
        let mut history = self.exploration_history.write();
        history.push(Discovery {
            domain: domain.to_string(),
            topic: topic.to_string(),
            block_height,
        });
    }

    /// Get curiosity stats summary.
    pub fn get_curiosity_stats(&self) -> CuriosityStats {
        let scores = self.compute_curiosity_scores();
        let mut sorted: Vec<(String, f64)> = scores.clone().into_iter().collect();
        sorted.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        let top_interests: Vec<String> = sorted.iter().take(5).map(|(d, _)| d.clone()).collect();
        let history = self.exploration_history.read();

        CuriosityStats {
            curiosity_scores: scores.clone(),
            top_interests,
            discoveries_count: history.len(),
            domains_tracked: scores.len(),
        }
    }

    /// Total curiosity-driven discoveries (used by gate 8 checks).
    pub fn discoveries_count(&self) -> usize {
        self.exploration_history.read().len()
    }

    /// Generate an exploration question for a domain.
    fn generate_exploration_question(&self, domain: &str) -> String {
        format!(
            "What are the foundational principles of {} that remain uncertain, \
             and what evidence would resolve them?",
            domain
        )
    }
}

// ---------------------------------------------------------------------------
// PyO3 methods
// ---------------------------------------------------------------------------

#[pymethods]
impl CuriosityEngine {
    #[new]
    pub fn py_new() -> Self {
        Self::new()
    }

    /// Compute curiosity scores per domain.
    #[pyo3(name = "compute_curiosity_scores")]
    pub fn py_compute_curiosity_scores(&self) -> PyResult<PyObject> {
        let scores = self.compute_curiosity_scores();
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            for (k, v) in &scores {
                dict.set_item(k, v)?;
            }
            Ok(dict.into())
        })
    }

    /// Suggest an exploration goal.
    #[pyo3(name = "suggest_exploration_goal")]
    pub fn py_suggest_exploration_goal(&self) -> PyResult<Option<PyObject>> {
        let goal = self.suggest_exploration_goal();
        match goal {
            None => Ok(None),
            Some(g) => Python::with_gil(|py| {
                let dict = pyo3::types::PyDict::new(py);
                dict.set_item("domain", &g.domain)?;
                dict.set_item("curiosity_score", g.curiosity_score)?;
                dict.set_item("question", &g.question)?;
                Ok(Some(dict.into()))
            }),
        }
    }

    /// Record a prediction outcome.
    #[pyo3(name = "record_prediction_outcome")]
    pub fn py_record_prediction_outcome(
        &self,
        domain: &str,
        predicted: f64,
        actual: f64,
        topic: &str,
    ) {
        self.record_prediction_outcome(domain, predicted, actual, topic);
    }

    /// Record a curiosity-driven discovery.
    #[pyo3(name = "record_discovery")]
    pub fn py_record_discovery(&self, domain: &str, topic: &str, block_height: u64) {
        self.record_discovery(domain, topic, block_height);
    }

    /// Get curiosity stats.
    #[pyo3(name = "get_curiosity_stats")]
    pub fn py_get_curiosity_stats(&self) -> PyResult<PyObject> {
        let stats = self.get_curiosity_stats();
        Python::with_gil(|py| {
            let json = serde_json::to_string(&stats)
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let json_mod = py.import("json")?;
            let obj = json_mod.call_method1("loads", (json,))?;
            Ok(obj.into())
        })
    }

    /// Get total discovery count.
    #[pyo3(name = "discoveries_count")]
    #[getter]
    pub fn py_discoveries_count(&self) -> usize {
        self.discoveries_count()
    }

    fn __repr__(&self) -> String {
        let scores = self.compute_curiosity_scores();
        let discoveries = self.discoveries_count();
        format!(
            "CuriosityEngine(domains={}, discoveries={})",
            scores.len(),
            discoveries,
        )
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_engine_empty() {
        let eng = CuriosityEngine::new();
        assert!(eng.compute_curiosity_scores().is_empty());
        assert_eq!(eng.discoveries_count(), 0);
    }

    #[test]
    fn test_record_prediction_outcome() {
        let eng = CuriosityEngine::new();
        eng.record_prediction_outcome("physics", 0.8, 0.5, "gravity");
        let scores = eng.compute_curiosity_scores();
        assert!(scores.contains_key("physics"));
        assert!((scores["physics"] - 0.3).abs() < 1e-10);
    }

    #[test]
    fn test_record_multiple_outcomes() {
        let eng = CuriosityEngine::new();
        eng.record_prediction_outcome("physics", 0.8, 0.5, "gravity");
        eng.record_prediction_outcome("physics", 0.9, 0.7, "quantum");
        let scores = eng.compute_curiosity_scores();
        // Mean of 0.3 and 0.2
        assert!((scores["physics"] - 0.25).abs() < 1e-10);
    }

    #[test]
    fn test_rolling_window_bounded() {
        let eng = CuriosityEngine::new();
        for i in 0..150 {
            eng.record_prediction_outcome("math", i as f64, 0.0, "test");
        }
        let errors = eng.prediction_errors.read();
        assert!(errors["math"].len() <= ROLLING_WINDOW);
    }

    #[test]
    fn test_suggest_exploration_goal_empty() {
        let eng = CuriosityEngine::new();
        assert!(eng.suggest_exploration_goal().is_none());
    }

    #[test]
    fn test_suggest_exploration_goal() {
        let eng = CuriosityEngine::new();
        eng.record_prediction_outcome("physics", 0.9, 0.1, "gravity");
        eng.record_prediction_outcome("math", 0.6, 0.5, "algebra");
        let goal = eng.suggest_exploration_goal().unwrap();
        assert_eq!(goal.domain, "physics"); // Higher error
        assert!(goal.curiosity_score > 0.0);
        assert!(!goal.question.is_empty());
    }

    #[test]
    fn test_record_discovery() {
        let eng = CuriosityEngine::new();
        eng.record_discovery("physics", "dark matter", 100);
        eng.record_discovery("math", "prime patterns", 200);
        assert_eq!(eng.discoveries_count(), 2);
    }

    #[test]
    fn test_get_curiosity_stats() {
        let eng = CuriosityEngine::new();
        eng.record_prediction_outcome("physics", 0.8, 0.3, "test");
        eng.record_prediction_outcome("math", 0.9, 0.1, "test");
        eng.record_discovery("physics", "topic1", 100);

        let stats = eng.get_curiosity_stats();
        assert_eq!(stats.domains_tracked, 2);
        assert_eq!(stats.discoveries_count, 1);
        assert_eq!(stats.top_interests.len(), 2);
        // Math has higher error (0.8 vs 0.5), so should be first
        assert_eq!(stats.top_interests[0], "math");
    }

    #[test]
    fn test_curiosity_scores_multiple_domains() {
        let eng = CuriosityEngine::new();
        eng.record_prediction_outcome("a", 1.0, 0.0, "t");
        eng.record_prediction_outcome("b", 0.5, 0.5, "t");
        eng.record_prediction_outcome("c", 0.3, 0.1, "t");
        let scores = eng.compute_curiosity_scores();
        assert_eq!(scores.len(), 3);
        assert!((scores["a"] - 1.0).abs() < 1e-10);
        assert!((scores["b"] - 0.0).abs() < 1e-10);
        assert!((scores["c"] - 0.2).abs() < 1e-10);
    }

    #[test]
    fn test_generate_exploration_question() {
        let eng = CuriosityEngine::new();
        let q = eng.generate_exploration_question("quantum_physics");
        assert!(q.contains("quantum_physics"));
        assert!(q.contains("uncertain"));
    }

    #[test]
    fn test_default_impl() {
        let eng = CuriosityEngine::default();
        assert!(eng.compute_curiosity_scores().is_empty());
    }

    #[test]
    fn test_concurrent_access() {
        use std::sync::Arc;
        use std::thread;

        let eng = Arc::new(CuriosityEngine::new());
        let mut handles = vec![];

        for i in 0..10 {
            let eng_clone = eng.clone();
            handles.push(thread::spawn(move || {
                eng_clone.record_prediction_outcome(
                    &format!("domain_{}", i % 3),
                    i as f64 * 0.1,
                    0.0,
                    "topic",
                );
            }));
        }

        for h in handles {
            h.join().unwrap();
        }

        let scores = eng.compute_curiosity_scores();
        assert!(!scores.is_empty());
    }
}
