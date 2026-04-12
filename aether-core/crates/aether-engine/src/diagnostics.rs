//! Diagnostics: health checks, stats, and mind state snapshots.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// Health status of a single subsystem.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SubsystemHealth {
    /// Name of the subsystem (e.g. "knowledge_graph", "phi_calculator").
    pub name: String,
    /// Current status.
    pub status: HealthStatus,
    /// Optional details (error message, latency, etc.).
    pub details: String,
    /// Timestamp of last successful operation (unix secs).
    pub last_active: f64,
}

/// Health status enum.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Unhealthy,
    NotInitialized,
}

impl Default for HealthStatus {
    fn default() -> Self {
        HealthStatus::NotInitialized
    }
}

impl std::fmt::Display for HealthStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HealthStatus::Healthy => write!(f, "healthy"),
            HealthStatus::Degraded => write!(f, "degraded"),
            HealthStatus::Unhealthy => write!(f, "unhealthy"),
            HealthStatus::NotInitialized => write!(f, "not_initialized"),
        }
    }
}

/// Snapshot of the Aether Tree's current "mind state".
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct MindState {
    /// Current Phi integration value.
    pub phi: f64,
    /// Number of AGI milestone gates passed.
    pub gates_passed: u32,
    /// Gate ceiling for Phi.
    pub gate_ceiling: f64,
    /// Current emotional state (emotion_name -> intensity).
    pub emotions: HashMap<String, f64>,
    /// Active curiosity goals count.
    pub active_goals: usize,
    /// Curiosity index (prediction error).
    pub curiosity_index: f64,
    /// Metacognitive confidence.
    pub self_confidence: f64,
    /// Recent insights (last 5).
    pub recent_insights: Vec<String>,
    /// Prediction accuracy.
    pub prediction_accuracy: f64,
    /// Block height this snapshot is from.
    pub block_height: u64,
    /// Sephirot activity (sephirah_name -> last active block).
    pub sephirot_activity: HashMap<String, u64>,
}

/// Comprehensive stats for the /aether/info endpoint.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct FullStats {
    /// Knowledge graph stats.
    pub node_count: usize,
    pub edge_count: usize,
    pub domain_distribution: HashMap<String, usize>,
    /// Phi metrics.
    pub phi: f64,
    pub phi_micro: f64,
    pub phi_meso: f64,
    pub phi_macro: f64,
    pub gates_passed: u32,
    pub gate_ceiling: f64,
    /// Reasoning stats.
    pub total_inferences: u64,
    pub debate_verdicts: u64,
    pub contradictions_resolved: u64,
    /// Cognitive stats.
    pub si_cycles: u64,
    pub curiosity_discoveries: u64,
    pub emotional_state: HashMap<String, f64>,
    /// Memory stats.
    pub working_memory_items: usize,
    pub long_term_patterns: usize,
    /// Protocol stats.
    pub blocks_processed: u64,
    pub thought_proofs_generated: u64,
    /// Subsystem health.
    pub subsystem_health: Vec<SubsystemHealth>,
    /// Version.
    pub aether_version: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_health_status_display() {
        assert_eq!(HealthStatus::Healthy.to_string(), "healthy");
        assert_eq!(HealthStatus::Degraded.to_string(), "degraded");
    }

    #[test]
    fn test_mind_state_default() {
        let ms = MindState::default();
        assert_eq!(ms.phi, 0.0);
        assert_eq!(ms.gates_passed, 0);
        assert!(ms.emotions.is_empty());
    }

    #[test]
    fn test_full_stats_default() {
        let stats = FullStats::default();
        assert_eq!(stats.node_count, 0);
        assert_eq!(stats.aether_version, "");
    }

    #[test]
    fn test_subsystem_health_serialization() {
        let h = SubsystemHealth {
            name: "phi_calculator".into(),
            status: HealthStatus::Healthy,
            details: "ok".into(),
            last_active: 1712000000.0,
        };
        let json = serde_json::to_string(&h).unwrap();
        assert!(json.contains("phi_calculator"));
        assert!(json.contains("Healthy"));
    }
}
