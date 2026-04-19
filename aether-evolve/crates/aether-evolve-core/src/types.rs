use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ── Intervention types ──────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum InterventionType {
    CodeChange,
    KnowledgeSeed,
    SwarmSeed,
    ApiCall,
    CacheBust,
}

// ── Diagnosis ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum DiagnosisPriority {
    P0PhiZero = 0,
    P1GateBlocker = 1,
    P2SubsystemDead = 2,
    P3QualityGap = 3,
    P4ScaleGap = 4,
    P5NovelSynthesis = 5,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiagnosisItem {
    pub priority: DiagnosisPriority,
    pub category: String,
    pub description: String,
    pub root_cause: String,
    pub recommended_intervention: InterventionType,
    pub target_files: Vec<String>,
    pub expected_improvement: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Diagnosis {
    pub timestamp: DateTime<Utc>,
    pub items: Vec<DiagnosisItem>,
    pub metrics_snapshot: AetherMetrics,
}

// ── Aether Tree Metrics ─────────────────────────────────────────────────

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PhiComponents {
    pub phi_micro: f64,
    pub phi_meso: f64,
    pub phi_macro: f64,
    pub hms_phi: f64,
    /// "restored", "python_fallback", "additive_v3", "hms_v4", etc.
    pub formula: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GateStatus {
    pub gate_number: u32,
    pub name: String,
    pub passed: bool,
    pub details: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SubsystemStatus {
    pub name: String,
    pub runs: u64,
    pub last_run: Option<DateTime<Utc>>,
    pub active: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AetherMetrics {
    pub timestamp: DateTime<Utc>,
    pub block_height: u64,
    pub total_nodes: u64,
    pub total_edges: u64,
    pub phi: PhiComponents,
    pub gates: Vec<GateStatus>,
    pub gates_passed: u32,
    pub gates_total: u32,
    pub debate_count: u64,
    pub contradiction_count: u64,
    pub prediction_accuracy: f64,
    pub mip_score: f64,
    pub ece: f64,
    pub novel_concepts: u64,
    pub auto_goals: u64,
    pub curiosity_discoveries: u64,
    pub self_improvement_cycles: u64,
    pub subsystems: Vec<SubsystemStatus>,
    pub domains: HashMap<String, u64>,
    pub cross_domain_edges: u64,
    pub cross_domain_inferences: u64,
}

// ── Experiment tracking ─────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeDiff {
    pub file_path: String,
    pub search: String,
    pub replace: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KnowledgePayload {
    pub content: String,
    pub domain: String,
    pub node_type: String,
    pub confidence: f64,
    pub connections: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExperimentNode {
    pub id: u64,
    pub step: u64,
    pub timestamp: DateTime<Utc>,
    pub intervention_type: InterventionType,
    pub diagnosis_summary: String,
    pub hypothesis: String,
    pub diffs: Vec<CodeDiff>,
    pub seeds: Vec<KnowledgePayload>,
    pub pre_metrics: AetherMetrics,
    pub post_metrics: AetherMetrics,
    pub analysis: String,
    pub score: f64,
    pub parent_ids: Vec<u64>,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsDelta {
    pub delta_phi: f64,
    pub delta_nodes: i64,
    pub delta_edges: i64,
    pub delta_gates: i32,
    pub delta_debates: i64,
    pub delta_novel_concepts: i64,
    pub subsystems_activated: Vec<String>,
}

impl MetricsDelta {
    pub fn compute(pre: &AetherMetrics, post: &AetherMetrics) -> Self {
        let activated: Vec<String> = post
            .subsystems
            .iter()
            .filter(|s| {
                s.active
                    && pre
                        .subsystems
                        .iter()
                        .find(|p| p.name == s.name)
                        .map_or(true, |p| !p.active)
            })
            .map(|s| s.name.clone())
            .collect();

        Self {
            delta_phi: post.phi.hms_phi - pre.phi.hms_phi,
            delta_nodes: post.total_nodes as i64 - pre.total_nodes as i64,
            delta_edges: post.total_edges as i64 - pre.total_edges as i64,
            delta_gates: post.gates_passed as i32 - pre.gates_passed as i32,
            delta_debates: post.debate_count as i64 - pre.debate_count as i64,
            delta_novel_concepts: post.novel_concepts as i64 - pre.novel_concepts as i64,
            subsystems_activated: activated,
        }
    }

    /// Composite score 0-100. No free points — zero improvement = zero score.
    pub fn score(&self) -> f64 {
        // Phi improvement: 0-35 points (requires actual positive delta)
        let phi_norm = if self.delta_phi > 0.001 {
            (self.delta_phi * 100.0).clamp(0.0, 35.0)
        } else {
            0.0
        };
        // Gate progress: 0-25 points
        let gates = (self.delta_gates.max(0) as f64 * 25.0).min(25.0);
        // Subsystem activation: 0-15 points
        let subsys = (self.subsystems_activated.len() as f64 * 5.0).min(15.0);
        // Quality: debates + novel concepts: 0-15 points
        let quality = (self.delta_debates.max(0) as f64 * 1.0
            + self.delta_novel_concepts.max(0) as f64 * 2.0)
            .min(15.0);
        // Stability: 10 points only if phi actually improved (not just didn't crash)
        let stability = if self.delta_phi > 0.0 { 10.0 } else { 0.0 };

        phi_norm + gates + subsys + quality + stability
    }
}

// ── Evolution plan (shared between Claude mode and Ollama mode) ─────────

/// A research plan that can be produced by Claude or by the Ollama-powered
/// research agent. Serializable to/from JSON for file-based handoff.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvolvePlan {
    pub intervention_type: InterventionType,
    pub hypothesis: String,
    #[serde(default)]
    pub diffs: Vec<CodeDiff>,
    #[serde(default)]
    pub seeds: Vec<KnowledgePayload>,
}

// ── Evolution pipeline state ────────────────────────────────────────────

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PipelinePhase {
    FixZeros,
    KnowledgeExplosion,
    CognitiveIntegration,
    SelfEvolution,
    NovelSynthesis,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineState {
    pub current_step: u64,
    pub current_phase: PipelinePhase,
    pub total_experiments: u64,
    pub best_score: f64,
    pub best_experiment_id: Option<u64>,
    pub started_at: DateTime<Utc>,
    pub last_step_at: DateTime<Utc>,
}

impl Default for PipelineState {
    fn default() -> Self {
        let now = Utc::now();
        Self {
            current_step: 0,
            current_phase: PipelinePhase::FixZeros,
            total_experiments: 0,
            best_score: 0.0,
            best_experiment_id: None,
            started_at: now,
            last_step_at: now,
        }
    }
}
