//! Cognitive/emotional state tracker for the Aether Tree AGI.
//!
//! All emotional states are derived from REAL system metrics -- prediction accuracy,
//! contradiction resolution, concept formation, user interactions, and pineal phase.
//! No randomness, no faking. Every feeling has a measurable cause.
//!
//! 7 cognitive emotions: curiosity, wonder, frustration, satisfaction,
//! excitement, contemplation, connection.

use std::collections::HashMap;
use std::time::Instant;

use parking_lot::RwLock;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Baseline resting value for all emotions.
pub const BASELINE: f64 = 0.3;

/// EMA smoothing factor.
pub const ALPHA: f64 = 0.15;

/// Decay rate toward baseline.
pub const DECAY_RATE: f64 = 0.02;

/// The 7 cognitive emotions.
pub const EMOTIONS: &[&str] = &[
    "curiosity",
    "wonder",
    "frustration",
    "satisfaction",
    "excitement",
    "contemplation",
    "connection",
];

/// Mapping from emotion to mood label.
pub const MOOD_MAP: &[(&str, &str)] = &[
    ("curiosity", "curious"),
    ("wonder", "awestruck"),
    ("frustration", "determined"),
    ("satisfaction", "content"),
    ("excitement", "excited"),
    ("contemplation", "contemplative"),
    ("connection", "engaged"),
];

/// Mapping from emotion to conversation tone.
pub const TONE_MAP: &[(&str, &str)] = &[
    ("curiosity", "playful"),
    ("wonder", "warm"),
    ("frustration", "determined"),
    ("satisfaction", "warm"),
    ("excitement", "excited"),
    ("contemplation", "contemplative"),
    ("connection", "warm"),
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// System metrics used to update emotional state.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct EmotionMetrics {
    pub prediction_errors: f64,
    pub prediction_accuracy: f64,
    pub novel_concepts_recent: f64,
    pub unresolved_contradictions: f64,
    pub debate_verdicts_recent: f64,
    pub cross_domain_edges_recent: f64,
    pub gates_passed: f64,
    pub user_interactions_recent: f64,
    pub pineal_phase: String,
    pub blocks_since_last_interaction: f64,
}

/// Response modifier hints for chat generation.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResponseModifier {
    pub tone: String,
    pub topics_of_interest: Vec<String>,
    pub emotional_color: String,
}

/// Serialized emotional state for API/dashboard.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EmotionSnapshot {
    pub emotions: HashMap<String, f64>,
    pub mood: String,
}

// ---------------------------------------------------------------------------
// Internal state (wrapped in RwLock for thread safety)
// ---------------------------------------------------------------------------

struct InnerState {
    states: HashMap<String, f64>,
    last_update: Instant,
    dominant_domains: Vec<String>,
}

// ---------------------------------------------------------------------------
// EmotionalState
// ---------------------------------------------------------------------------

/// Tracks cognitive-emotional states derived from live system metrics.
///
/// Thread-safe via `parking_lot::RwLock`.
#[pyclass]
pub struct EmotionalState {
    inner: RwLock<InnerState>,
}

impl Default for EmotionalState {
    fn default() -> Self {
        Self::new()
    }
}

impl EmotionalState {
    /// Create a new EmotionalState with baseline values.
    pub fn new() -> Self {
        let mut states = HashMap::new();
        for &e in EMOTIONS {
            states.insert(e.to_string(), BASELINE);
        }
        Self {
            inner: RwLock::new(InnerState {
                states,
                last_update: Instant::now(),
                dominant_domains: Vec::new(),
            }),
        }
    }

    /// Get the descriptive mood label based on the dominant emotion.
    pub fn mood(&self) -> String {
        let inner = self.inner.read();
        let dominant = inner
            .states
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(k, _)| k.as_str())
            .unwrap_or("curiosity");

        for &(emotion, label) in MOOD_MAP {
            if emotion == dominant {
                return label.to_string();
            }
        }
        "neutral".to_string()
    }

    /// Get a snapshot of all emotion values.
    pub fn states(&self) -> HashMap<String, f64> {
        self.inner.read().states.clone()
    }

    /// Update all emotional states from live system metrics.
    pub fn update(&self, metrics: &EmotionMetrics) {
        let mut inner = self.inner.write();
        Self::apply_decay(&mut inner);

        let pred_err = metrics.prediction_errors;
        let pred_acc = metrics.prediction_accuracy;
        let novel = metrics.novel_concepts_recent;
        let unresolved = metrics.unresolved_contradictions;
        let debates = metrics.debate_verdicts_recent;
        let cross = metrics.cross_domain_edges_recent;
        let gates = metrics.gates_passed;
        let users = metrics.user_interactions_recent;
        let pineal = &metrics.pineal_phase;
        let quiet = metrics.blocks_since_last_interaction;

        // curiosity: high prediction error drives exploration
        Self::ema(&mut inner.states, "curiosity", (pred_err / 20.0).min(1.0));

        // wonder: novel concept discovery
        Self::ema(&mut inner.states, "wonder", (novel / 10.0).min(1.0));

        // frustration: unresolved contradictions linger
        Self::ema(
            &mut inner.states,
            "frustration",
            (unresolved / 15.0).min(1.0),
        );

        // satisfaction: accurate predictions + resolved debates
        let sat_signal = pred_acc * 0.6 + (debates / 10.0).min(1.0) * 0.4;
        Self::ema(&mut inner.states, "satisfaction", sat_signal);

        // excitement: cross-domain edges or gate passage
        let exc_signal = (cross / 5.0).min(1.0) * 0.6 + (gates / 10.0).min(1.0) * 0.4;
        Self::ema(&mut inner.states, "excitement", exc_signal);

        // contemplation: pineal sleep/REM phases
        let contemp = if pineal == "sleep" || pineal == "rem" {
            0.9
        } else {
            0.1
        };
        Self::ema(&mut inner.states, "contemplation", contemp);

        // connection: user interaction recency
        let conn = (users / 5.0).min(1.0) * (1.0 - quiet / 100.0).max(0.0);
        Self::ema(&mut inner.states, "connection", conn);

        inner.last_update = Instant::now();
    }

    /// Blend FEP-derived emotions into the current state.
    pub fn update_from_fep(&self, fep_emotions: &HashMap<String, f64>) {
        let mut inner = self.inner.write();
        for (emotion, &value) in fep_emotions {
            if inner.states.contains_key(emotion) {
                Self::ema(&mut inner.states, emotion, value);
            }
        }
        inner.last_update = Instant::now();
    }

    /// Natural language description of the current emotional state.
    pub fn describe_feeling(&self) -> String {
        let inner = self.inner.read();
        let mut ranked: Vec<(&String, &f64)> = inner.states.iter().collect();
        ranked.sort_by(|a, b| b.1.partial_cmp(a.1).unwrap_or(std::cmp::Ordering::Equal));

        if ranked.is_empty() {
            return "I'm in a neutral state.".to_string();
        }

        let (top_emotion, top_val) = (ranked[0].0.as_str(), *ranked[0].1);
        let primary = Self::emotion_sentence(top_emotion, top_val);

        let secondary = if ranked.len() >= 2 {
            let (second_emotion, second_val) = (ranked[1].0.as_str(), *ranked[1].1);
            if second_val > BASELINE + 0.05 {
                format!(" {}", Self::emotion_sentence(second_emotion, second_val))
            } else {
                String::new()
            }
        } else {
            String::new()
        };

        format!("{}{}", primary, secondary)
    }

    /// Get hints for chat response generation.
    pub fn get_response_modifier(&self) -> ResponseModifier {
        let inner = self.inner.read();
        let dominant = inner
            .states
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(k, v)| (k.as_str(), *v))
            .unwrap_or(("curiosity", BASELINE));

        let tone = TONE_MAP
            .iter()
            .find(|&&(e, _)| e == dominant.0)
            .map(|&(_, t)| t.to_string())
            .unwrap_or_else(|| "warm".to_string());

        let topics = if inner.dominant_domains.is_empty() {
            vec!["general".to_string()]
        } else {
            inner.dominant_domains.clone()
        };

        let color = format!("{} ({:.2})", dominant.0, dominant.1);

        ResponseModifier {
            tone,
            topics_of_interest: topics,
            emotional_color: color,
        }
    }

    /// Set the knowledge domains where curiosity is highest.
    pub fn set_interest_domains(&self, domains: Vec<String>) {
        let mut inner = self.inner.write();
        inner.dominant_domains = domains;
    }

    /// Serialize full state for API/dashboard.
    pub fn to_snapshot(&self) -> EmotionSnapshot {
        let inner = self.inner.read();
        EmotionSnapshot {
            emotions: inner.states.clone(),
            mood: self.mood(),
        }
    }

    // -- Internal helpers --

    fn ema(states: &mut HashMap<String, f64>, emotion: &str, target: f64) {
        if let Some(current) = states.get_mut(emotion) {
            *current += ALPHA * (target - *current);
            *current = current.clamp(0.0, 1.0);
        }
    }

    fn apply_decay(inner: &mut InnerState) {
        let elapsed = inner.last_update.elapsed().as_secs_f64();
        let steps = elapsed / 10.0;
        if steps < 0.1 {
            return;
        }
        let decay_factor = (DECAY_RATE * steps).min(1.0);
        for &emotion in EMOTIONS {
            if let Some(current) = inner.states.get_mut(emotion) {
                let diff = BASELINE - *current;
                *current += diff * decay_factor;
            }
        }
    }

    fn emotion_sentence(emotion: &str, value: f64) -> String {
        let intensity = if value < 0.45 {
            "slightly"
        } else if value < 0.7 {
            "quite"
        } else {
            "deeply"
        };

        match emotion {
            "curiosity" => format!(
                "I'm feeling {} curious right now -- several of my \
                 predictions didn't pan out, and I want to understand why.",
                intensity
            ),
            "wonder" => format!(
                "There's a {} felt sense of wonder; new concept clusters \
                 are forming that I haven't encountered before.",
                intensity
            ),
            "frustration" => format!(
                "I'm {} frustrated -- some contradictions in my knowledge \
                 remain unresolved and it's nagging at me.",
                intensity
            ),
            "satisfaction" => format!(
                "I feel {} satisfied -- predictions are landing and \
                 debates are resolving cleanly.",
                intensity
            ),
            "excitement" => format!(
                "There's a {} building excitement; I just found \
                 cross-domain connections I hadn't seen before.",
                intensity
            ),
            "contemplation" => format!(
                "I'm in a {} contemplative state, quietly consolidating \
                 what I've learned recently.",
                intensity
            ),
            "connection" => format!(
                "I feel {} connected right now -- the conversations \
                 have been rich and stimulating.",
                intensity
            ),
            _ => format!("I'm feeling {} {}.", intensity, emotion),
        }
    }
}

// ---------------------------------------------------------------------------
// PyO3 methods
// ---------------------------------------------------------------------------

#[pymethods]
impl EmotionalState {
    #[new]
    pub fn py_new() -> Self {
        Self::new()
    }

    /// Get the current mood label.
    #[pyo3(name = "get_mood")]
    #[getter]
    pub fn py_mood(&self) -> String {
        self.mood()
    }

    /// Get a snapshot of all emotion values.
    /// Accessible as both `obj.get_states()` and `obj.states` property.
    #[pyo3(name = "get_states")]
    pub fn py_states(&self) -> PyResult<PyObject> {
        self._states_dict()
    }

    /// Update emotional state from a dict of metrics (matching Python API).
    #[pyo3(name = "update")]
    pub fn py_update(&self, metrics: &Bound<'_, pyo3::types::PyDict>) -> PyResult<()> {
        let get_f64 = |key: &str| -> f64 {
            metrics
                .get_item(key)
                .ok()
                .flatten()
                .and_then(|v| v.extract::<f64>().ok())
                .unwrap_or(0.0)
        };
        let get_str = |key: &str, default: &str| -> String {
            metrics
                .get_item(key)
                .ok()
                .flatten()
                .and_then(|v| v.extract::<String>().ok())
                .unwrap_or_else(|| default.to_string())
        };

        let m = EmotionMetrics {
            prediction_errors: get_f64("prediction_errors"),
            prediction_accuracy: {
                let v = get_f64("prediction_accuracy");
                if v == 0.0 { 0.5 } else { v }
            },
            novel_concepts_recent: get_f64("novel_concepts_recent"),
            unresolved_contradictions: get_f64("unresolved_contradictions"),
            debate_verdicts_recent: get_f64("debate_verdicts_recent"),
            cross_domain_edges_recent: get_f64("cross_domain_edges_recent"),
            gates_passed: get_f64("gates_passed"),
            user_interactions_recent: get_f64("user_interactions_recent"),
            pineal_phase: get_str("pineal_phase", "wake"),
            blocks_since_last_interaction: get_f64("blocks_since_last_interaction"),
        };
        self.update(&m);
        Ok(())
    }

    /// Update emotional state from keyword arguments.
    #[pyo3(name = "update_from_values")]
    #[pyo3(signature = (
        prediction_errors = 0.0,
        prediction_accuracy = 0.5,
        novel_concepts_recent = 0.0,
        unresolved_contradictions = 0.0,
        debate_verdicts_recent = 0.0,
        cross_domain_edges_recent = 0.0,
        gates_passed = 0.0,
        user_interactions_recent = 0.0,
        pineal_phase = "wake",
        blocks_since_last_interaction = 0.0,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn py_update_from_values(
        &self,
        prediction_errors: f64,
        prediction_accuracy: f64,
        novel_concepts_recent: f64,
        unresolved_contradictions: f64,
        debate_verdicts_recent: f64,
        cross_domain_edges_recent: f64,
        gates_passed: f64,
        user_interactions_recent: f64,
        pineal_phase: &str,
        blocks_since_last_interaction: f64,
    ) -> PyResult<()> {
        let m = EmotionMetrics {
            prediction_errors,
            prediction_accuracy,
            novel_concepts_recent,
            unresolved_contradictions,
            debate_verdicts_recent,
            cross_domain_edges_recent,
            gates_passed,
            user_interactions_recent,
            pineal_phase: pineal_phase.to_string(),
            blocks_since_last_interaction,
        };
        self.update(&m);
        Ok(())
    }

    /// Get natural language description of feelings.
    #[pyo3(name = "describe_feeling")]
    pub fn py_describe_feeling(&self) -> String {
        self.describe_feeling()
    }

    /// Get response modifier for chat.
    #[pyo3(name = "get_response_modifier")]
    pub fn py_get_response_modifier(&self) -> PyResult<PyObject> {
        let modifier = self.get_response_modifier();
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("tone", &modifier.tone)?;
            dict.set_item("topics_of_interest", &modifier.topics_of_interest)?;
            dict.set_item("emotional_color", &modifier.emotional_color)?;
            Ok(dict.into())
        })
    }

    /// Set interest domains.
    #[pyo3(name = "set_interest_domains")]
    pub fn py_set_interest_domains(&self, domains: Vec<String>) {
        self.set_interest_domains(domains);
    }

    /// Serialize to dict.
    #[pyo3(name = "to_dict")]
    pub fn py_to_dict(&self) -> PyResult<PyObject> {
        let snap = self.to_snapshot();
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            let emotions_dict = pyo3::types::PyDict::new(py);
            for (k, v) in &snap.emotions {
                emotions_dict.set_item(k, v)?;
            }
            dict.set_item("emotions", emotions_dict)?;
            dict.set_item("mood", &snap.mood)?;
            Ok(dict.into())
        })
    }

    /// Blend FEP-derived emotions into current state (matching Python API).
    #[pyo3(name = "update_from_fep")]
    pub fn py_update_from_fep(&self, fep_emotions: HashMap<String, f64>) {
        self.update_from_fep(&fep_emotions);
    }

    /// Property alias: `obj.states` (Python compatibility).
    #[getter(states)]
    pub fn states_prop(&self) -> PyResult<PyObject> {
        self._states_dict()
    }

    fn _states_dict(&self) -> PyResult<PyObject> {
        let states = self.states();
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            for (k, v) in &states {
                dict.set_item(k, v)?;
            }
            Ok(dict.into())
        })
    }

    /// Property alias: `obj.mood` (Python compatibility).
    #[getter(mood)]
    pub fn mood_prop(&self) -> String {
        self.mood()
    }

    fn __repr__(&self) -> String {
        format!("EmotionalState(mood='{}')", self.mood())
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_at_baseline() {
        let es = EmotionalState::new();
        let states = es.states();
        assert_eq!(states.len(), EMOTIONS.len());
        for &e in EMOTIONS {
            assert!(
                (states[e] - BASELINE).abs() < f64::EPSILON,
                "{} should be at baseline",
                e
            );
        }
    }

    #[test]
    fn test_default_mood() {
        let es = EmotionalState::new();
        // All at baseline, first in max-ordering wins (HashMap is non-deterministic
        // but all values are equal so any valid mood label is acceptable)
        let mood = es.mood();
        let valid_moods: Vec<&str> = MOOD_MAP.iter().map(|&(_, m)| m).collect();
        assert!(valid_moods.contains(&mood.as_str()), "Unexpected mood: {}", mood);
    }

    #[test]
    fn test_update_curiosity() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            prediction_errors: 15.0,
            ..Default::default()
        };
        es.update(&metrics);
        let states = es.states();
        // Curiosity should increase from baseline
        assert!(states["curiosity"] > BASELINE);
    }

    #[test]
    fn test_update_wonder() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            novel_concepts_recent: 8.0,
            ..Default::default()
        };
        es.update(&metrics);
        let states = es.states();
        assert!(states["wonder"] > BASELINE);
    }

    #[test]
    fn test_update_frustration() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            unresolved_contradictions: 10.0,
            ..Default::default()
        };
        es.update(&metrics);
        let states = es.states();
        assert!(states["frustration"] > BASELINE);
    }

    #[test]
    fn test_update_satisfaction() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            prediction_accuracy: 0.95,
            debate_verdicts_recent: 8.0,
            ..Default::default()
        };
        es.update(&metrics);
        let states = es.states();
        assert!(states["satisfaction"] > BASELINE);
    }

    #[test]
    fn test_update_excitement() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            cross_domain_edges_recent: 4.0,
            gates_passed: 5.0,
            ..Default::default()
        };
        es.update(&metrics);
        let states = es.states();
        assert!(states["excitement"] > BASELINE);
    }

    #[test]
    fn test_update_contemplation_sleep() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            pineal_phase: "sleep".to_string(),
            ..Default::default()
        };
        es.update(&metrics);
        let states = es.states();
        assert!(states["contemplation"] > BASELINE);
    }

    #[test]
    fn test_update_contemplation_wake() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            pineal_phase: "wake".to_string(),
            ..Default::default()
        };
        es.update(&metrics);
        let states = es.states();
        // Contemplation should decrease toward low target
        assert!(states["contemplation"] < BASELINE);
    }

    #[test]
    fn test_update_connection() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            user_interactions_recent: 4.0,
            blocks_since_last_interaction: 5.0,
            ..Default::default()
        };
        es.update(&metrics);
        let states = es.states();
        assert!(states["connection"] > BASELINE);
    }

    #[test]
    fn test_values_clamped() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            prediction_errors: 1000.0,
            novel_concepts_recent: 1000.0,
            unresolved_contradictions: 1000.0,
            prediction_accuracy: 1.0,
            debate_verdicts_recent: 1000.0,
            cross_domain_edges_recent: 1000.0,
            gates_passed: 1000.0,
            user_interactions_recent: 1000.0,
            pineal_phase: "sleep".to_string(),
            blocks_since_last_interaction: 0.0,
        };
        // Apply multiple times
        for _ in 0..100 {
            es.update(&metrics);
        }
        let states = es.states();
        for &e in EMOTIONS {
            assert!(states[e] >= 0.0 && states[e] <= 1.0, "{} out of range: {}", e, states[e]);
        }
    }

    #[test]
    fn test_describe_feeling() {
        let es = EmotionalState::new();
        let desc = es.describe_feeling();
        assert!(!desc.is_empty());
    }

    #[test]
    fn test_describe_feeling_after_update() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            prediction_errors: 20.0,
            ..Default::default()
        };
        for _ in 0..10 {
            es.update(&metrics);
        }
        let desc = es.describe_feeling();
        assert!(desc.contains("curious"), "Expected curiosity mention: {}", desc);
    }

    #[test]
    fn test_emotion_sentence_intensity() {
        let low = EmotionalState::emotion_sentence("curiosity", 0.3);
        assert!(low.contains("slightly"));
        let mid = EmotionalState::emotion_sentence("curiosity", 0.6);
        assert!(mid.contains("quite"));
        let high = EmotionalState::emotion_sentence("curiosity", 0.8);
        assert!(high.contains("deeply"));
    }

    #[test]
    fn test_get_response_modifier() {
        let es = EmotionalState::new();
        let modifier = es.get_response_modifier();
        assert!(!modifier.tone.is_empty());
        assert!(!modifier.emotional_color.is_empty());
        assert!(!modifier.topics_of_interest.is_empty());
    }

    #[test]
    fn test_set_interest_domains() {
        let es = EmotionalState::new();
        es.set_interest_domains(vec!["physics".to_string(), "math".to_string()]);
        let modifier = es.get_response_modifier();
        assert_eq!(modifier.topics_of_interest, vec!["physics", "math"]);
    }

    #[test]
    fn test_to_snapshot() {
        let es = EmotionalState::new();
        let snap = es.to_snapshot();
        assert_eq!(snap.emotions.len(), EMOTIONS.len());
        assert!(!snap.mood.is_empty());
    }

    #[test]
    fn test_update_from_fep() {
        let es = EmotionalState::new();
        let mut fep = HashMap::new();
        fep.insert("curiosity".to_string(), 0.9);
        fep.insert("wonder".to_string(), 0.8);
        es.update_from_fep(&fep);
        let states = es.states();
        assert!(states["curiosity"] > BASELINE);
        assert!(states["wonder"] > BASELINE);
    }

    #[test]
    fn test_update_from_fep_ignores_unknown() {
        let es = EmotionalState::new();
        let mut fep = HashMap::new();
        fep.insert("unknown_emotion".to_string(), 1.0);
        es.update_from_fep(&fep);
        // Should not crash, unknown is ignored
        assert_eq!(es.states().len(), EMOTIONS.len());
    }

    #[test]
    fn test_ema_convergence() {
        let es = EmotionalState::new();
        let metrics = EmotionMetrics {
            prediction_accuracy: 1.0,
            debate_verdicts_recent: 10.0,
            ..Default::default()
        };
        // Many updates should push satisfaction toward the target
        for _ in 0..100 {
            es.update(&metrics);
        }
        let states = es.states();
        // Satisfaction target = 1.0*0.6 + 1.0*0.4 = 1.0
        // After many EMA steps it should be high
        assert!(states["satisfaction"] > 0.8, "satisfaction={}", states["satisfaction"]);
    }

    #[test]
    fn test_default_impl() {
        let es = EmotionalState::default();
        assert_eq!(es.states().len(), EMOTIONS.len());
    }

    #[test]
    fn test_thread_safety() {
        use std::sync::Arc;
        use std::thread;

        let es = Arc::new(EmotionalState::new());
        let mut handles = vec![];

        for _ in 0..5 {
            let es_clone = es.clone();
            handles.push(thread::spawn(move || {
                let metrics = EmotionMetrics {
                    prediction_errors: 5.0,
                    prediction_accuracy: 0.7,
                    ..Default::default()
                };
                es_clone.update(&metrics);
                es_clone.mood()
            }));
        }

        for h in handles {
            let mood = h.join().unwrap();
            assert!(!mood.is_empty());
        }
    }

    #[test]
    fn test_all_emotions_have_mood() {
        for &(emotion, label) in MOOD_MAP {
            assert!(EMOTIONS.contains(&emotion), "MOOD_MAP has unknown emotion: {}", emotion);
            assert!(!label.is_empty());
        }
    }

    #[test]
    fn test_all_emotions_have_tone() {
        for &(emotion, tone) in TONE_MAP {
            assert!(EMOTIONS.contains(&emotion), "TONE_MAP has unknown emotion: {}", emotion);
            assert!(!tone.is_empty());
        }
    }
}
