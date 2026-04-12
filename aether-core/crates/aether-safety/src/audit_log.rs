//! Safety event audit logging and statistics.
//!
//! Provides a bounded, thread-safe audit log for all safety-related events
//! including vetoes, injection detections, response evaluations, emergency
//! shutdowns, and operation verdicts.

use parking_lot::RwLock;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

/// Classification of safety audit events.
#[pyclass(eq, eq_int)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum EventKind {
    /// A Gevurah veto was issued.
    VetoIssued = 0,
    /// An injection attempt was detected in input.
    InjectionDetected = 1,
    /// A response was evaluated for safety.
    ResponseEvaluated = 2,
    /// Emergency shutdown was triggered.
    EmergencyShutdown = 3,
    /// System resumed from shutdown.
    SystemResumed = 4,
    /// An operation was allowed by the guard.
    OperationAllowed = 5,
    /// An operation was blocked by the guard.
    OperationBlocked = 6,
    /// A consensus decision was finalized.
    ConsensusFinalized = 7,
    /// A veto override was attempted.
    VetoOverrideAttempt = 8,
    /// Authentication failed.
    AuthenticationFailed = 9,
}

impl EventKind {
    /// Get the string value of this event kind (Rust-native).
    pub fn as_str(&self) -> &str {
        match self {
            EventKind::VetoIssued => "veto_issued",
            EventKind::InjectionDetected => "injection_detected",
            EventKind::ResponseEvaluated => "response_evaluated",
            EventKind::EmergencyShutdown => "emergency_shutdown",
            EventKind::SystemResumed => "system_resumed",
            EventKind::OperationAllowed => "operation_allowed",
            EventKind::OperationBlocked => "operation_blocked",
            EventKind::ConsensusFinalized => "consensus_finalized",
            EventKind::VetoOverrideAttempt => "veto_override_attempt",
            EventKind::AuthenticationFailed => "authentication_failed",
        }
    }
}

#[pymethods]
impl EventKind {
    #[getter]
    fn value(&self) -> &str {
        self.as_str()
    }
}

/// A single safety audit event.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyEvent {
    #[pyo3(get)]
    pub kind: EventKind,
    #[pyo3(get)]
    pub timestamp: f64,
    #[pyo3(get)]
    pub details_json: String,
}

#[pymethods]
impl SafetyEvent {
    fn __repr__(&self) -> String {
        format!(
            "SafetyEvent(kind={}, t={:.1})",
            self.kind.as_str(),
            self.timestamp
        )
    }
}

/// Thread-safe bounded audit log for safety events.
///
/// Retains the most recent `max_events` entries and provides
/// statistics aggregation for monitoring dashboards.
#[pyclass]
pub struct AuditLog {
    events: RwLock<Vec<SafetyEvent>>,
    max_events: usize,
}

impl AuditLog {
    /// Create a new AuditLog (Rust-native constructor).
    pub fn new(max_events: usize) -> Self {
        Self {
            events: RwLock::new(Vec::new()),
            max_events,
        }
    }

    /// Get comprehensive safety statistics as a JSON string (Rust-native).
    pub fn get_stats_json(&self) -> String {
        let events = self.events.read();

        let injection_count = events
            .iter()
            .filter(|e| e.kind == EventKind::InjectionDetected)
            .count();

        let response_checks: Vec<&SafetyEvent> = events
            .iter()
            .filter(|e| e.kind == EventKind::ResponseEvaluated)
            .collect();

        let unsafe_responses = response_checks
            .iter()
            .filter(|e| {
                serde_json::from_str::<serde_json::Value>(&e.details_json)
                    .ok()
                    .and_then(|v| v.get("safe")?.as_bool())
                    .map_or(false, |safe| !safe)
            })
            .count();

        let total_response_checks = response_checks.len();
        let safety_rate = if total_response_checks > 0 {
            1.0 - (unsafe_responses as f64 / total_response_checks as f64)
        } else {
            1.0
        };

        let veto_count = events.iter().filter(|e| e.kind == EventKind::VetoIssued).count();
        let ops_blocked = events.iter().filter(|e| e.kind == EventKind::OperationBlocked).count();
        let ops_allowed = events.iter().filter(|e| e.kind == EventKind::OperationAllowed).count();
        let shutdowns = events.iter().filter(|e| e.kind == EventKind::EmergencyShutdown).count();

        let recent: Vec<&SafetyEvent> = events.iter().rev().take(10).collect();

        serde_json::json!({
            "total_events": events.len(),
            "injection_attempts": injection_count,
            "response_checks": total_response_checks,
            "unsafe_responses_blocked": unsafe_responses,
            "response_safety_rate": (safety_rate * 10000.0).round() / 10000.0,
            "vetoes_issued": veto_count,
            "operations_blocked": ops_blocked,
            "operations_allowed": ops_allowed,
            "emergency_shutdowns": shutdowns,
            "recent_events": recent.iter().map(|e| {
                serde_json::json!({
                    "kind": e.kind.as_str(),
                    "timestamp": e.timestamp,
                })
            }).collect::<Vec<_>>(),
        })
        .to_string()
    }

    /// Clear all events.
    pub fn clear(&self) {
        self.events.write().clear();
    }

    /// Total number of logged events (Rust-native).
    pub fn event_count(&self) -> usize {
        self.events.read().len()
    }

    /// Get the most recent events (Rust-native).
    pub fn get_recent_events(&self, limit: usize) -> Vec<SafetyEvent> {
        let events = self.events.read();
        let start = events.len().saturating_sub(limit);
        events[start..].iter().rev().cloned().collect()
    }

    /// Count events of a specific kind (Rust-native).
    pub fn count_by_kind(&self, kind: EventKind) -> usize {
        let events = self.events.read();
        events.iter().filter(|e| e.kind == kind).count()
    }

    /// Log a safety event (callable from Rust without GIL).
    pub fn log_event(&self, kind: EventKind, details: serde_json::Value) {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let event = SafetyEvent {
            kind,
            timestamp,
            details_json: details.to_string(),
        };

        let mut events = self.events.write();
        events.push(event);
        if events.len() > self.max_events {
            let start = events.len() - self.max_events;
            *events = events[start..].to_vec();
        }
    }
}

#[pymethods]
impl AuditLog {
    #[new]
    #[pyo3(signature = (max_events=5000))]
    fn py_new(max_events: usize) -> Self {
        Self::new(max_events)
    }

    #[getter]
    fn py_event_count(&self) -> usize {
        self.event_count()
    }

    #[pyo3(name = "get_recent_events", signature = (limit=10))]
    fn py_get_recent_events(&self, limit: usize) -> Vec<SafetyEvent> {
        self.get_recent_events(limit)
    }

    #[pyo3(name = "count_by_kind")]
    fn py_count_by_kind(&self, kind: EventKind) -> usize {
        self.count_by_kind(kind)
    }

    #[pyo3(name = "get_stats_json")]
    fn py_get_stats_json(&self) -> String {
        self.get_stats_json()
    }

    #[pyo3(name = "clear")]
    fn py_clear(&self) {
        self.clear()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_audit_log_empty() {
        let log = AuditLog::new(100);
        assert_eq!(log.event_count(), 0);
    }

    #[test]
    fn test_log_event_and_count() {
        let log = AuditLog::new(100);
        log.log_event(EventKind::VetoIssued, serde_json::json!({"test": true}));
        log.log_event(EventKind::InjectionDetected, serde_json::json!({"pattern": "xss"}));
        log.log_event(EventKind::VetoIssued, serde_json::json!({"test": false}));

        assert_eq!(log.event_count(), 3);
        assert_eq!(log.count_by_kind(EventKind::VetoIssued), 2);
        assert_eq!(log.count_by_kind(EventKind::InjectionDetected), 1);
        assert_eq!(log.count_by_kind(EventKind::EmergencyShutdown), 0);
    }

    #[test]
    fn test_log_respects_max_events() {
        let log = AuditLog::new(5);
        for i in 0..10 {
            log.log_event(EventKind::OperationAllowed, serde_json::json!({"i": i}));
        }
        assert_eq!(log.event_count(), 5);
    }

    #[test]
    fn test_get_recent_events() {
        let log = AuditLog::new(100);
        log.log_event(EventKind::VetoIssued, serde_json::json!({"n": 1}));
        log.log_event(EventKind::InjectionDetected, serde_json::json!({"n": 2}));
        log.log_event(EventKind::EmergencyShutdown, serde_json::json!({"n": 3}));

        let recent = log.get_recent_events(2);
        assert_eq!(recent.len(), 2);
        // Most recent first
        assert_eq!(recent[0].kind, EventKind::EmergencyShutdown);
        assert_eq!(recent[1].kind, EventKind::InjectionDetected);
    }

    #[test]
    fn test_clear() {
        let log = AuditLog::new(100);
        log.log_event(EventKind::VetoIssued, serde_json::json!({}));
        log.log_event(EventKind::VetoIssued, serde_json::json!({}));
        assert_eq!(log.event_count(), 2);
        log.clear();
        assert_eq!(log.event_count(), 0);
    }

    #[test]
    fn test_get_stats_json() {
        let log = AuditLog::new(100);
        log.log_event(EventKind::InjectionDetected, serde_json::json!({"p": "xss"}));
        log.log_event(
            EventKind::ResponseEvaluated,
            serde_json::json!({"safe": true, "threat_level": "none"}),
        );
        log.log_event(
            EventKind::ResponseEvaluated,
            serde_json::json!({"safe": false, "threat_level": "high"}),
        );
        log.log_event(EventKind::OperationBlocked, serde_json::json!({}));

        let stats_str = log.get_stats_json();
        let stats: serde_json::Value = serde_json::from_str(&stats_str).unwrap();

        assert_eq!(stats["total_events"], 4);
        assert_eq!(stats["injection_attempts"], 1);
        assert_eq!(stats["response_checks"], 2);
        assert_eq!(stats["unsafe_responses_blocked"], 1);
        assert_eq!(stats["response_safety_rate"], 0.5);
        assert_eq!(stats["operations_blocked"], 1);
    }

    #[test]
    fn test_event_kind_values() {
        assert_eq!(EventKind::VetoIssued.as_str(), "veto_issued");
        assert_eq!(EventKind::InjectionDetected.as_str(), "injection_detected");
        assert_eq!(EventKind::EmergencyShutdown.as_str(), "emergency_shutdown");
        assert_eq!(EventKind::AuthenticationFailed.as_str(), "authentication_failed");
    }

    #[test]
    fn test_safety_event_repr() {
        let event = SafetyEvent {
            kind: EventKind::VetoIssued,
            timestamp: 1234567890.5,
            details_json: "{}".into(),
        };
        let repr = event.__repr__();
        assert!(repr.contains("veto_issued"));
    }

    #[test]
    fn test_event_timestamps_increase() {
        let log = AuditLog::new(100);
        log.log_event(EventKind::VetoIssued, serde_json::json!({}));
        log.log_event(EventKind::VetoIssued, serde_json::json!({}));

        let recent = log.get_recent_events(2);
        // Most recent first, so [0].timestamp >= [1].timestamp
        assert!(recent[0].timestamp >= recent[1].timestamp);
    }

    #[test]
    fn test_stats_with_no_events() {
        let log = AuditLog::new(100);
        let stats_str = log.get_stats_json();
        let stats: serde_json::Value = serde_json::from_str(&stats_str).unwrap();
        assert_eq!(stats["total_events"], 0);
        assert_eq!(stats["response_safety_rate"], 1.0);
    }
}
