//! 10-Gate AGI Milestone System (V4 quality-focused thresholds).
//!
//! Each gate unlocks +0.5 Phi ceiling (max 5.0). Gates require genuine
//! cognitive milestones emphasizing QUALITY over quantity. Volume alone
//! cannot pass higher gates -- they require validated predictions, genuine
//! cross-domain transfer, enacted self-improvement, and novel synthesis.
//!
//! Ported from: `phi_calculator.py` MILESTONE_GATES definitions.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing;

// ---------------------------------------------------------------------------
// Gate statistics (input to gate checking)
// ---------------------------------------------------------------------------

/// Statistics collected from the Aether engine subsystems, used to evaluate
/// whether each gate's requirements are met.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct GateStats {
    /// Total number of knowledge nodes.
    pub n_nodes: u64,
    /// Number of distinct knowledge domains.
    pub domain_count: u64,
    /// Average confidence across all nodes (0.0 - 1.0).
    pub avg_confidence: f64,
    /// Per node-type counts: type_name -> count.
    pub node_type_counts: HashMap<String, u64>,
    /// Per edge-type counts: edge_type -> count.
    pub edge_type_counts: HashMap<String, u64>,
    /// Graph-theoretic integration score (0.0 - 1.0).
    pub integration_score: f64,
    /// Number of externally verified predictions.
    pub verified_predictions: u64,
    /// Prediction accuracy (0.0 - 1.0).
    pub prediction_accuracy: f64,
    /// Number of adversarial debate verdicts.
    pub debate_verdicts: u64,
    /// Number of contradictions resolved via debate.
    pub contradiction_resolutions: u64,
    /// MIP-based phi score (spectral bisection).
    pub mip_phi: f64,
    /// Number of cross-domain inferences produced.
    pub cross_domain_inferences: u64,
    /// Average confidence of cross-domain inferences.
    pub cross_domain_inference_confidence: f64,
    /// Number of cross-domain edges (analogous_to, etc.).
    pub cross_domain_edges: u64,
    /// Number of enacted self-improvement cycles.
    pub improvement_cycles_enacted: u64,
    /// Performance delta from self-improvement (positive = improvement).
    pub improvement_performance_delta: f64,
    /// Whether FEP free energy is decreasing (convergence indicator).
    pub fep_free_energy_decreasing: bool,
    /// Expected calibration error (lower is better).
    pub calibration_error: f64,
    /// Number of calibration evaluations performed.
    pub calibration_evaluations: u64,
    /// Fraction of nodes that are grounded (0.0 - 1.0).
    pub grounding_ratio: f64,
    /// Number of autonomously generated goals.
    pub auto_goals_generated: u64,
    /// Number of auto-goals that produced inferences.
    pub auto_goals_with_inferences: u64,
    /// Number of curiosity-driven discoveries.
    pub curiosity_driven_discoveries: u64,
    /// Number of FEP domains with precision models.
    pub fep_domain_precisions: u64,
    /// Number of axioms consolidated from repeated patterns.
    pub axiom_from_consolidation: u64,
    /// Number of genuinely novel concepts synthesized.
    pub novel_concept_count: u64,
    /// Sephirot winner diversity (0.0 - 1.0, Shannon entropy normalized).
    pub sephirot_winner_diversity: f64,
}

// ---------------------------------------------------------------------------
// Gate definition and results
// ---------------------------------------------------------------------------

/// Definition of a single AGI milestone gate.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GateDefinition {
    /// Gate number (1-10).
    pub id: u32,
    /// Human-readable gate name.
    pub name: String,
    /// Detailed description.
    pub description: String,
    /// Minimum node count required.
    pub min_nodes: u64,
    /// Phi ceiling unlocked when passed (+0.5 per gate).
    pub phi_unlock: f64,
    /// Human-readable requirement summary.
    pub requirement: String,
}

/// Result of evaluating a single gate.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GateResult {
    /// Gate number (1-10).
    pub id: u32,
    /// Gate name.
    pub name: String,
    /// Whether the gate is currently passed.
    pub passed: bool,
    /// Phi ceiling this gate contributes.
    pub phi_unlock: f64,
    /// Human-readable requirement.
    pub requirement: String,
    /// Human-readable progress notes.
    pub progress: String,
}

// ---------------------------------------------------------------------------
// Gate system
// ---------------------------------------------------------------------------

/// The 10-gate AGI milestone system.
///
/// Evaluates the Aether engine's cognitive state against 10 quality-focused
/// gates. Each passed gate unlocks +0.5 Phi ceiling. The total Phi ceiling
/// is `0.5 * gates_passed`, capping at 5.0 when all 10 gates pass.
pub struct GateSystem {
    /// Configurable scale factor for node-count thresholds.
    /// When > 1.0 thresholds increase (harder); < 1.0 they decrease (easier).
    gate_scale: f64,
}

impl GateSystem {
    /// Create a new GateSystem with the given scale factor.
    pub fn new(gate_scale: f64) -> Self {
        Self {
            gate_scale: gate_scale.max(0.1),
        }
    }

    /// Return the canonical 10 gate definitions.
    pub fn definitions() -> Vec<GateDefinition> {
        vec![
            GateDefinition {
                id: 1,
                name: "Knowledge Foundation".into(),
                description: "Broad knowledge base with diverse domains".into(),
                min_nodes: 500,
                phi_unlock: 0.5,
                requirement: ">=500 nodes, >=5 domains, avg confidence >= 0.5".into(),
            },
            GateDefinition {
                id: 2,
                name: "Structural Diversity".into(),
                description: "Multiple reasoning types with real graph integration".into(),
                min_nodes: 2_000,
                phi_unlock: 1.0,
                requirement: ">=2K nodes, >=4 types with 50+ each, integration > 0.3".into(),
            },
            GateDefinition {
                id: 3,
                name: "Validated Predictions".into(),
                description: "Predictions verified against actual outcomes".into(),
                min_nodes: 5_000,
                phi_unlock: 1.5,
                requirement: ">=5K nodes, >=50 verified predictions, accuracy > 60%".into(),
            },
            GateDefinition {
                id: 4,
                name: "Self-Correction".into(),
                description: "Genuine adversarial debate with contradiction resolution".into(),
                min_nodes: 10_000,
                phi_unlock: 2.0,
                requirement: ">=10K nodes, >=20 debates, >=10 contradictions resolved, MIP > 0.3".into(),
            },
            GateDefinition {
                id: 5,
                name: "Cross-Domain Transfer".into(),
                description: "Genuine knowledge transfer using evidence from 2+ domains".into(),
                min_nodes: 15_000,
                phi_unlock: 2.5,
                requirement: ">=15K nodes, >=30 cross-domain inferences with conf > 0.5, >=50 cross-edges".into(),
            },
            GateDefinition {
                id: 6,
                name: "Enacted Self-Improvement".into(),
                description: "Self-improvement actions enacted AND producing measurable gains with FEP convergence".into(),
                min_nodes: 20_000,
                phi_unlock: 3.0,
                requirement: ">=20K nodes, >=10 enacted improvement cycles, positive performance delta, FEP free energy decreasing".into(),
            },
            GateDefinition {
                id: 7,
                name: "Calibrated Confidence".into(),
                description: "System knows what it knows -- calibration error below threshold".into(),
                min_nodes: 25_000,
                phi_unlock: 3.5,
                requirement: ">=25K nodes, ECE < 0.15, >=200 evaluations, >5% grounded".into(),
            },
            GateDefinition {
                id: 8,
                name: "Autonomous Curiosity".into(),
                description: "System generates its own research goals with FEP-guided exploration".into(),
                min_nodes: 35_000,
                phi_unlock: 4.0,
                requirement: ">=35K nodes, >=50 auto-goals, >=30 producing inferences, >=10 curiosity discoveries, FEP precision in >=3 domains".into(),
            },
            GateDefinition {
                id: 9,
                name: "Predictive Mastery".into(),
                description: "Sustained high accuracy across domains with large inference volume".into(),
                min_nodes: 50_000,
                phi_unlock: 4.5,
                requirement: ">=50K nodes, accuracy > 70%, >=5K inferences, >=20 consolidated axioms".into(),
            },
            GateDefinition {
                id: 10,
                name: "Novel Synthesis".into(),
                description: "Genuine novel concepts with diverse Sephirot cognitive participation".into(),
                min_nodes: 75_000,
                phi_unlock: 5.0,
                requirement: ">=75K nodes, >=50 novel concepts, >=100 cross-domain inferences, sustained self-improvement, Sephirot winner diversity >=0.5".into(),
            },
        ]
    }

    /// Apply the gate scale factor to a node-count threshold.
    fn scaled_nodes(&self, base: u64) -> u64 {
        ((base as f64) * self.gate_scale).round() as u64
    }

    /// Count the number of cross-domain edges (analogous_to) in stats.
    fn count_cross_domain_edges(stats: &GateStats) -> u64 {
        stats.cross_domain_edges
            .max(*stats.edge_type_counts.get("analogous_to").unwrap_or(&0))
    }

    /// Count node types with >= `min_count` nodes.
    fn types_above_threshold(stats: &GateStats, min_count: u64) -> usize {
        stats
            .node_type_counts
            .values()
            .filter(|&&c| c >= min_count)
            .count()
    }

    /// Evaluate a single gate against the given stats. Returns (passed, progress_msg).
    fn check_gate(&self, gate_id: u32, stats: &GateStats) -> (bool, String) {
        match gate_id {
            1 => {
                let need = self.scaled_nodes(500);
                let passed = stats.n_nodes >= need
                    && stats.domain_count >= 5
                    && stats.avg_confidence >= 0.5;
                let progress = format!(
                    "nodes={}/{}, domains={}/5, avg_conf={:.2}/0.50",
                    stats.n_nodes, need, stats.domain_count, stats.avg_confidence
                );
                (passed, progress)
            }
            2 => {
                let need = self.scaled_nodes(2_000);
                let types_ok = Self::types_above_threshold(stats, 50);
                let passed = stats.n_nodes >= need
                    && types_ok >= 4
                    && stats.integration_score > 0.3;
                let progress = format!(
                    "nodes={}/{}, types_50+={}/4, integration={:.2}/0.30",
                    stats.n_nodes, need, types_ok, stats.integration_score
                );
                (passed, progress)
            }
            3 => {
                let need = self.scaled_nodes(5_000);
                let passed = stats.n_nodes >= need
                    && stats.verified_predictions >= 50
                    && stats.prediction_accuracy > 0.6;
                let progress = format!(
                    "nodes={}/{}, verified_preds={}/50, accuracy={:.2}/0.60",
                    stats.n_nodes, need, stats.verified_predictions, stats.prediction_accuracy
                );
                (passed, progress)
            }
            4 => {
                let need = self.scaled_nodes(10_000);
                let passed = stats.n_nodes >= need
                    && stats.debate_verdicts >= 20
                    && stats.contradiction_resolutions >= 10
                    && stats.mip_phi > 0.3;
                let progress = format!(
                    "nodes={}/{}, debates={}/20, contradictions={}/10, mip={:.2}/0.30",
                    stats.n_nodes, need, stats.debate_verdicts,
                    stats.contradiction_resolutions, stats.mip_phi
                );
                (passed, progress)
            }
            5 => {
                let need = self.scaled_nodes(15_000);
                let xd_edges = Self::count_cross_domain_edges(stats);
                let passed = stats.n_nodes >= need
                    && stats.cross_domain_inferences >= 30
                    && stats.cross_domain_inference_confidence > 0.5
                    && xd_edges >= 50;
                let progress = format!(
                    "nodes={}/{}, xd_infer={}/30, xd_conf={:.2}/0.50, xd_edges={}/50",
                    stats.n_nodes, need, stats.cross_domain_inferences,
                    stats.cross_domain_inference_confidence, xd_edges
                );
                (passed, progress)
            }
            6 => {
                let need = self.scaled_nodes(20_000);
                let passed = stats.n_nodes >= need
                    && stats.improvement_cycles_enacted >= 10
                    && stats.improvement_performance_delta > 0.0
                    && stats.fep_free_energy_decreasing;
                let progress = format!(
                    "nodes={}/{}, si_cycles={}/10, perf_delta={:.3}/0.0, fep_decreasing={}",
                    stats.n_nodes, need, stats.improvement_cycles_enacted,
                    stats.improvement_performance_delta, stats.fep_free_energy_decreasing
                );
                (passed, progress)
            }
            7 => {
                let need = self.scaled_nodes(25_000);
                let passed = stats.n_nodes >= need
                    && stats.calibration_error < 0.15
                    && stats.calibration_evaluations >= 200
                    && stats.grounding_ratio > 0.05;
                let progress = format!(
                    "nodes={}/{}, ece={:.3}/0.15, cal_evals={}/200, grounding={:.3}/0.05",
                    stats.n_nodes, need, stats.calibration_error,
                    stats.calibration_evaluations, stats.grounding_ratio
                );
                (passed, progress)
            }
            8 => {
                let need = self.scaled_nodes(35_000);
                let passed = stats.n_nodes >= need
                    && stats.auto_goals_generated >= 50
                    && stats.auto_goals_with_inferences >= 30
                    && stats.curiosity_driven_discoveries >= 10
                    && stats.fep_domain_precisions >= 3;
                let progress = format!(
                    "nodes={}/{}, goals={}/50, goals_infer={}/30, discoveries={}/10, fep_domains={}/3",
                    stats.n_nodes, need, stats.auto_goals_generated,
                    stats.auto_goals_with_inferences, stats.curiosity_driven_discoveries,
                    stats.fep_domain_precisions
                );
                (passed, progress)
            }
            9 => {
                let need = self.scaled_nodes(50_000);
                let inferences = stats.node_type_counts.get("inference").copied().unwrap_or(0);
                let passed = stats.n_nodes >= need
                    && stats.prediction_accuracy > 0.70
                    && inferences >= 5_000
                    && stats.axiom_from_consolidation >= 20;
                let progress = format!(
                    "nodes={}/{}, accuracy={:.2}/0.70, inferences={}/5000, axioms={}/20",
                    stats.n_nodes, need, stats.prediction_accuracy,
                    inferences, stats.axiom_from_consolidation
                );
                (passed, progress)
            }
            10 => {
                let need = self.scaled_nodes(75_000);
                let passed = stats.n_nodes >= need
                    && stats.novel_concept_count >= 50
                    && stats.cross_domain_inferences >= 100
                    && stats.improvement_performance_delta > 0.05
                    && stats.sephirot_winner_diversity >= 0.5;
                let progress = format!(
                    "nodes={}/{}, novel={}/50, xd_infer={}/100, perf_delta={:.3}/0.05, diversity={:.2}/0.50",
                    stats.n_nodes, need, stats.novel_concept_count,
                    stats.cross_domain_inferences, stats.improvement_performance_delta,
                    stats.sephirot_winner_diversity
                );
                (passed, progress)
            }
            _ => (false, "Unknown gate".into()),
        }
    }

    /// Evaluate all 10 gates against the provided stats.
    ///
    /// Returns a vector of `GateResult` and the computed Phi ceiling
    /// (0.5 per passed gate, max 5.0).
    pub fn evaluate(&self, stats: &GateStats) -> (Vec<GateResult>, f64) {
        let definitions = Self::definitions();
        let mut results = Vec::with_capacity(10);
        let mut gates_passed = 0u32;

        for def in &definitions {
            let (passed, progress) = self.check_gate(def.id, stats);
            if passed {
                gates_passed += 1;
            }
            results.push(GateResult {
                id: def.id,
                name: def.name.clone(),
                passed,
                phi_unlock: def.phi_unlock,
                requirement: def.requirement.clone(),
                progress,
            });
        }

        let phi_ceiling = gates_passed as f64 * 0.5;

        tracing::debug!(
            gates_passed = gates_passed,
            phi_ceiling = phi_ceiling,
            n_nodes = stats.n_nodes,
            "Gate evaluation complete"
        );

        (results, phi_ceiling)
    }

    /// Compute the Phi ceiling from stats (convenience wrapper).
    pub fn phi_ceiling(&self, stats: &GateStats) -> f64 {
        let (_, ceiling) = self.evaluate(stats);
        ceiling
    }

    /// Return the number of gates passed.
    pub fn gates_passed(&self, stats: &GateStats) -> u32 {
        let (results, _) = self.evaluate(stats);
        results.iter().filter(|g| g.passed).count() as u32
    }

    /// Find the next unpassed gate (if any).
    pub fn next_gate(&self, stats: &GateStats) -> Option<GateDefinition> {
        let (results, _) = self.evaluate(stats);
        let defs = Self::definitions();
        for (result, def) in results.iter().zip(defs.iter()) {
            if !result.passed {
                return Some(def.clone());
            }
        }
        None
    }

    /// Get gate progress summary for logging/display.
    pub fn progress_summary(&self, stats: &GateStats) -> HashMap<String, serde_json::Value> {
        let (results, ceiling) = self.evaluate(stats);
        let passed = results.iter().filter(|g| g.passed).count();

        let mut summary = HashMap::new();
        summary.insert("gates_passed".into(), serde_json::json!(passed));
        summary.insert("gates_total".into(), serde_json::json!(10));
        summary.insert("phi_ceiling".into(), serde_json::json!(ceiling));
        summary.insert("n_nodes".into(), serde_json::json!(stats.n_nodes));

        let gate_details: Vec<serde_json::Value> = results
            .iter()
            .map(|g| {
                serde_json::json!({
                    "id": g.id,
                    "name": g.name,
                    "passed": g.passed,
                    "phi_unlock": g.phi_unlock,
                    "progress": g.progress,
                })
            })
            .collect();
        summary.insert("gates".into(), serde_json::json!(gate_details));

        summary
    }
}

impl Default for GateSystem {
    fn default() -> Self {
        Self::new(1.0)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn base_stats(n_nodes: u64) -> GateStats {
        GateStats {
            n_nodes,
            domain_count: 10,
            avg_confidence: 0.7,
            node_type_counts: {
                let mut m = HashMap::new();
                m.insert("assertion".into(), 200);
                m.insert("inference".into(), 6000);
                m.insert("observation".into(), 200);
                m.insert("prediction".into(), 200);
                m.insert("axiom".into(), 100);
                m
            },
            edge_type_counts: {
                let mut m = HashMap::new();
                m.insert("analogous_to".into(), 100);
                m
            },
            integration_score: 0.5,
            verified_predictions: 100,
            prediction_accuracy: 0.75,
            debate_verdicts: 50,
            contradiction_resolutions: 30,
            mip_phi: 0.6,
            cross_domain_inferences: 150,
            cross_domain_inference_confidence: 0.7,
            cross_domain_edges: 100,
            improvement_cycles_enacted: 20,
            improvement_performance_delta: 0.1,
            fep_free_energy_decreasing: true,
            calibration_error: 0.10,
            calibration_evaluations: 500,
            grounding_ratio: 0.15,
            auto_goals_generated: 100,
            auto_goals_with_inferences: 50,
            curiosity_driven_discoveries: 20,
            fep_domain_precisions: 5,
            axiom_from_consolidation: 30,
            novel_concept_count: 60,
            sephirot_winner_diversity: 0.7,
        }
    }

    #[test]
    fn test_all_gates_pass_with_sufficient_stats() {
        let gs = GateSystem::default();
        let stats = base_stats(100_000);
        let (results, ceiling) = gs.evaluate(&stats);
        assert_eq!(results.len(), 10);
        for r in &results {
            assert!(r.passed, "Gate {} should pass: {}", r.id, r.progress);
        }
        assert!((ceiling - 5.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_no_gates_pass_with_zero_stats() {
        let gs = GateSystem::default();
        let stats = GateStats::default();
        let (results, ceiling) = gs.evaluate(&stats);
        for r in &results {
            assert!(!r.passed, "Gate {} should not pass with zero stats", r.id);
        }
        assert!((ceiling - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_gate1_requires_500_nodes() {
        let gs = GateSystem::default();
        let mut stats = base_stats(499);
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[0].passed);

        stats.n_nodes = 500;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[0].passed);
    }

    #[test]
    fn test_gate1_requires_5_domains() {
        let gs = GateSystem::default();
        let mut stats = base_stats(1000);
        stats.domain_count = 4;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[0].passed);

        stats.domain_count = 5;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[0].passed);
    }

    #[test]
    fn test_gate1_requires_confidence() {
        let gs = GateSystem::default();
        let mut stats = base_stats(1000);
        stats.avg_confidence = 0.49;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[0].passed);

        stats.avg_confidence = 0.5;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[0].passed);
    }

    #[test]
    fn test_gate2_requires_4_types_with_50_each() {
        let gs = GateSystem::default();
        let mut stats = base_stats(5000);
        stats.node_type_counts.clear();
        stats.node_type_counts.insert("assertion".into(), 100);
        stats.node_type_counts.insert("inference".into(), 100);
        stats.node_type_counts.insert("observation".into(), 49); // below 50
        stats.node_type_counts.insert("prediction".into(), 100);
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[1].passed);

        stats.node_type_counts.insert("observation".into(), 50);
        let (results, _) = gs.evaluate(&stats);
        assert!(results[1].passed);
    }

    #[test]
    fn test_gate3_requires_verified_predictions() {
        let gs = GateSystem::default();
        let mut stats = base_stats(10_000);
        stats.verified_predictions = 49;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[2].passed);

        stats.verified_predictions = 50;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[2].passed);
    }

    #[test]
    fn test_gate3_requires_accuracy() {
        let gs = GateSystem::default();
        let mut stats = base_stats(10_000);
        stats.prediction_accuracy = 0.59;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[2].passed);

        stats.prediction_accuracy = 0.61;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[2].passed);
    }

    #[test]
    fn test_gate4_self_correction() {
        let gs = GateSystem::default();
        let mut stats = base_stats(15_000);
        stats.debate_verdicts = 19;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[3].passed);

        stats.debate_verdicts = 20;
        stats.contradiction_resolutions = 10;
        stats.mip_phi = 0.31;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[3].passed);
    }

    #[test]
    fn test_gate5_cross_domain_transfer() {
        let gs = GateSystem::default();
        let mut stats = base_stats(20_000);
        stats.cross_domain_inferences = 29;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[4].passed);

        stats.cross_domain_inferences = 30;
        stats.cross_domain_inference_confidence = 0.51;
        stats.cross_domain_edges = 50;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[4].passed);
    }

    #[test]
    fn test_gate6_enacted_self_improvement() {
        let gs = GateSystem::default();
        let mut stats = base_stats(25_000);
        stats.fep_free_energy_decreasing = false;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[5].passed);

        stats.fep_free_energy_decreasing = true;
        stats.improvement_cycles_enacted = 10;
        stats.improvement_performance_delta = 0.01;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[5].passed);
    }

    #[test]
    fn test_gate7_calibrated_confidence() {
        let gs = GateSystem::default();
        let mut stats = base_stats(30_000);
        stats.calibration_error = 0.16;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[6].passed);

        stats.calibration_error = 0.14;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[6].passed);
    }

    #[test]
    fn test_gate8_autonomous_curiosity() {
        let gs = GateSystem::default();
        let mut stats = base_stats(40_000);
        stats.curiosity_driven_discoveries = 9;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[7].passed);

        stats.curiosity_driven_discoveries = 10;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[7].passed);
    }

    #[test]
    fn test_gate9_predictive_mastery() {
        let gs = GateSystem::default();
        let mut stats = base_stats(60_000);
        stats.prediction_accuracy = 0.69;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[8].passed);

        stats.prediction_accuracy = 0.71;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[8].passed);
    }

    #[test]
    fn test_gate10_novel_synthesis() {
        let gs = GateSystem::default();
        let mut stats = base_stats(80_000);
        stats.novel_concept_count = 49;
        let (results, _) = gs.evaluate(&stats);
        assert!(!results[9].passed);

        stats.novel_concept_count = 50;
        stats.sephirot_winner_diversity = 0.5;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[9].passed);
    }

    #[test]
    fn test_phi_ceiling_incremental() {
        let gs = GateSystem::default();

        // Only gate 1 passes
        let mut stats = GateStats::default();
        stats.n_nodes = 600;
        stats.domain_count = 5;
        stats.avg_confidence = 0.6;
        let (_, ceiling) = gs.evaluate(&stats);
        assert!((ceiling - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_gate_scale_factor() {
        let gs = GateSystem::new(2.0); // Double the thresholds
        let mut stats = base_stats(999);
        let (results, _) = gs.evaluate(&stats);
        // Gate 1 normally needs 500, now needs 1000
        assert!(!results[0].passed);

        stats.n_nodes = 1000;
        let (results, _) = gs.evaluate(&stats);
        assert!(results[0].passed);
    }

    #[test]
    fn test_gate_scale_factor_low() {
        let gs = GateSystem::new(0.5); // Halve the thresholds
        let stats = base_stats(250);
        let (results, _) = gs.evaluate(&stats);
        // Gate 1 normally needs 500, now needs 250
        assert!(results[0].passed);
    }

    #[test]
    fn test_definitions_count() {
        let defs = GateSystem::definitions();
        assert_eq!(defs.len(), 10);
        for (i, d) in defs.iter().enumerate() {
            assert_eq!(d.id as usize, i + 1);
        }
    }

    #[test]
    fn test_next_gate_returns_first_unpassed() {
        let gs = GateSystem::default();
        let stats = GateStats::default();
        let next = gs.next_gate(&stats);
        assert!(next.is_some());
        assert_eq!(next.unwrap().id, 1);
    }

    #[test]
    fn test_next_gate_none_when_all_passed() {
        let gs = GateSystem::default();
        let stats = base_stats(100_000);
        let next = gs.next_gate(&stats);
        assert!(next.is_none());
    }

    #[test]
    fn test_progress_summary_fields() {
        let gs = GateSystem::default();
        let stats = base_stats(100_000);
        let summary = gs.progress_summary(&stats);
        assert!(summary.contains_key("gates_passed"));
        assert!(summary.contains_key("gates_total"));
        assert!(summary.contains_key("phi_ceiling"));
        assert!(summary.contains_key("gates"));
    }

    #[test]
    fn test_gates_passed_count() {
        let gs = GateSystem::default();
        let stats = base_stats(100_000);
        assert_eq!(gs.gates_passed(&stats), 10);

        let empty = GateStats::default();
        assert_eq!(gs.gates_passed(&empty), 0);
    }

    #[test]
    fn test_gate_result_serialization() {
        let result = GateResult {
            id: 1,
            name: "Test".into(),
            passed: true,
            phi_unlock: 0.5,
            requirement: "test req".into(),
            progress: "test progress".into(),
        };
        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("\"passed\":true"));
    }

    #[test]
    fn test_gate_stats_default_zeros() {
        let stats = GateStats::default();
        assert_eq!(stats.n_nodes, 0);
        assert_eq!(stats.domain_count, 0);
        assert!((stats.avg_confidence - 0.0).abs() < f64::EPSILON);
        assert!(stats.node_type_counts.is_empty());
    }
}
