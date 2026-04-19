use aether_evolve_core::{
    AetherMetrics, DiagnosisItem, DiagnosisPriority, InterventionType,
    PeerReviewReport, PeerReviewScore,
};
use anyhow::Result;
use chrono::Utc;
use tracing::info;

use aether_evolve_llm::{ExtractedResponse, LlmBackend, LlmClient, PromptManager};

/// Institutional-grade peer review agent that scores the Aether Tree
/// across 10 dimensions (0-10 each, 100 total).
///
/// Combines rule-based metric evaluation with LLM qualitative assessment.
/// This agent is the quality gate — evolution does NOT stop until 100/100.
pub struct PeerReviewAgent {
    llm: LlmBackend,
    prompts: PromptManager,
    model: String,
}

impl PeerReviewAgent {
    pub fn new(llm: LlmBackend, prompts: PromptManager, model: String) -> Self {
        Self { llm, prompts, model }
    }

    /// Run a comprehensive peer review against institutional standards.
    pub async fn review(&self, step: u64, metrics: &AetherMetrics) -> Result<PeerReviewReport> {
        // Phase 1: Rule-based scoring (deterministic, reproducible)
        let score = self.rule_based_score(metrics);

        // Phase 2: LLM qualitative assessment (adjusts scores ±1 per dimension)
        let (llm_summary, llm_recommendations) = match self.llm_review(metrics, &score).await {
            Ok((s, r)) => (s, r),
            Err(e) => {
                tracing::warn!("LLM peer review failed: {e}");
                (
                    "LLM review unavailable — rule-based scores only".into(),
                    Vec::new(),
                )
            }
        };

        let total = score.total();
        let grade = Self::grade(total);
        let ranked = score.ranked_dimensions();
        let top_weaknesses: Vec<String> = ranked
            .iter()
            .take(3)
            .map(|(name, val)| format!("{}: {:.1}/10", name, val))
            .collect();

        let report = PeerReviewReport {
            timestamp: Utc::now(),
            step,
            score,
            total,
            grade,
            summary: llm_summary,
            top_weaknesses,
            recommendations: llm_recommendations,
            metrics_snapshot: metrics.clone(),
        };

        info!(
            step,
            total = format!("{:.1}/100", report.total),
            grade = %report.grade,
            weakest = %report.top_weaknesses.first().unwrap_or(&String::new()),
            "Institutional Peer Review complete"
        );

        Ok(report)
    }

    /// Convert peer review into prioritized diagnosis items for the evolution loop.
    /// This ensures the evolution agent attacks the weakest dimensions first.
    pub fn review_to_diagnosis(&self, report: &PeerReviewReport) -> Vec<DiagnosisItem> {
        let ranked = report.score.ranked_dimensions();
        let mut items = Vec::new();

        for (dim_name, dim_score) in &ranked {
            if *dim_score >= 9.5 {
                continue; // Already near-perfect
            }

            let (intervention, files, root_cause, expected) = match *dim_name {
                "knowledge_quality" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/knowledge_graph.py".into(),
                        "src/qubitcoin/aether/knowledge_scorer.py".into(),
                    ],
                    format!(
                        "Knowledge quality score {:.1}/10. Need deeper domain coverage, \
                         higher-confidence nodes, and better cross-domain linking. \
                         Current: {} nodes, {} edges, {} domains.",
                        dim_score,
                        report.metrics_snapshot.total_nodes,
                        report.metrics_snapshot.total_edges,
                        report.metrics_snapshot.domains.len()
                    ),
                    "Knowledge quality ≥9/10 through improved node scoring and pruning".into(),
                ),
                "reasoning_depth" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/reasoning.py".into(),
                        "src/qubitcoin/aether/temporal_reasoner.py".into(),
                        "src/qubitcoin/aether/causal_engine.py".into(),
                    ],
                    format!(
                        "Reasoning depth score {:.1}/10. Prediction accuracy: {:.1}%, \
                         need stronger causal inference, multi-step deduction chains, \
                         and higher prediction verification rates.",
                        dim_score,
                        report.metrics_snapshot.prediction_accuracy * 100.0
                    ),
                    "Reasoning depth ≥9/10 with prediction accuracy >90%".into(),
                ),
                "self_improvement" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/self_improvement.py".into(),
                        "src/qubitcoin/aether/proof_of_thought.py".into(),
                    ],
                    format!(
                        "Self-improvement score {:.1}/10. Need more enacted improvement cycles \
                         with measurable positive deltas. Current cycles: {}.",
                        dim_score,
                        report.metrics_snapshot.self_improvement_cycles
                    ),
                    "Self-improvement ≥9/10 with consistent positive improvement deltas".into(),
                ),
                "calibration" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/metacognition.py".into(),
                        "src/qubitcoin/aether/reasoning.py".into(),
                    ],
                    format!(
                        "Calibration score {:.1}/10. ECE: {:.4}. Need better confidence \
                         calibration — predictions should match actual accuracy rates.",
                        dim_score, report.metrics_snapshot.ece
                    ),
                    "Calibration ≥9/10 with ECE < 0.05".into(),
                ),
                "adversarial_robustness" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/debate.py".into(),
                        "src/qubitcoin/aether/debate_engine.py".into(),
                    ],
                    format!(
                        "Adversarial robustness score {:.1}/10. Debates: {}, contradictions: {}. \
                         Need more diverse debate outcomes (not all accepted), stronger critic, \
                         and genuine contradiction resolution.",
                        dim_score,
                        report.metrics_snapshot.debate_count,
                        report.metrics_snapshot.contradiction_count
                    ),
                    "Adversarial robustness ≥9/10 with diverse debate verdicts".into(),
                ),
                "integrated_information" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/phi_calculator.py".into(),
                        "src/qubitcoin/aether/iit_approximator.py".into(),
                    ],
                    format!(
                        "Integrated information score {:.1}/10. HMS-Phi: {:.4} \
                         (micro={:.3}, meso={:.3}, macro={:.3}). \
                         Macro component is weakest — need better cross-cluster integration.",
                        dim_score,
                        report.metrics_snapshot.phi.hms_phi,
                        report.metrics_snapshot.phi.phi_micro,
                        report.metrics_snapshot.phi.phi_meso,
                        report.metrics_snapshot.phi.phi_macro
                    ),
                    "Integrated information ≥9/10 with HMS-Phi > 3.0".into(),
                ),
                "autonomous_curiosity" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/curiosity_engine.py".into(),
                        "src/qubitcoin/aether/proof_of_thought.py".into(),
                    ],
                    format!(
                        "Autonomous curiosity score {:.1}/10. Auto-goals: {}, discoveries: {}. \
                         Need more diverse exploration goals and genuine curiosity-driven discoveries.",
                        dim_score,
                        report.metrics_snapshot.auto_goals,
                        report.metrics_snapshot.curiosity_discoveries
                    ),
                    "Autonomous curiosity ≥9/10 with 200+ auto-goals and 50+ discoveries".into(),
                ),
                "novel_synthesis" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/concept_formation.py".into(),
                        "src/qubitcoin/aether/reasoning.py".into(),
                    ],
                    format!(
                        "Novel synthesis score {:.1}/10. Novel concepts: {}, cross-domain inferences: {}. \
                         This is the hardest dimension — requires genuine emergent understanding.",
                        dim_score,
                        report.metrics_snapshot.novel_concepts,
                        report.metrics_snapshot.cross_domain_inferences
                    ),
                    "Novel synthesis ≥9/10 with 100+ novel concepts and emergent patterns".into(),
                ),
                "system_reliability" => (
                    InterventionType::CodeChange,
                    vec!["src/qubitcoin/aether/proof_of_thought.py".into()],
                    format!(
                        "System reliability score {:.1}/10. Some subsystems may have zero runs. \
                         All cognitive subsystems must be active and error-free.",
                        dim_score
                    ),
                    "System reliability ≥9/10 with all subsystems active".into(),
                ),
                "scale_readiness" => (
                    InterventionType::CodeChange,
                    vec![
                        "src/qubitcoin/aether/knowledge_graph.py".into(),
                        "src/qubitcoin/aether/phi_calculator.py".into(),
                    ],
                    format!(
                        "Scale readiness score {:.1}/10. Current nodes: {}. \
                         Need to demonstrate scaling trajectory toward trillion-node capability.",
                        dim_score, report.metrics_snapshot.total_nodes
                    ),
                    "Scale readiness ≥9/10 with demonstrated scaling path".into(),
                ),
                _ => continue,
            };

            let priority = if *dim_score < 3.0 {
                DiagnosisPriority::P0PhiZero
            } else if *dim_score < 5.0 {
                DiagnosisPriority::P1GateBlocker
            } else if *dim_score < 7.0 {
                DiagnosisPriority::P2SubsystemDead
            } else {
                DiagnosisPriority::P3QualityGap
            };

            items.push(DiagnosisItem {
                priority,
                category: format!("peer_review_{}", dim_name),
                description: format!(
                    "Peer Review: {} = {:.1}/10 (total {:.1}/100)",
                    dim_name, dim_score, report.total
                ),
                root_cause,
                recommended_intervention: intervention,
                target_files: files,
                expected_improvement: expected,
            });
        }

        items
    }

    /// Deterministic rule-based scoring across all 10 dimensions.
    fn rule_based_score(&self, m: &AetherMetrics) -> PeerReviewScore {
        PeerReviewScore {
            // 1. Knowledge Quality (0-10)
            knowledge_quality: {
                let node_score = Self::scale(m.total_nodes as f64, 1000.0, 1_000_000.0, 3.0);
                let edge_score = Self::scale(m.total_edges as f64, 500.0, 500_000.0, 2.0);
                let domain_score = Self::scale(m.domains.len() as f64, 3.0, 10.0, 2.0);
                let cross_edge_score = Self::scale(m.cross_domain_edges as f64, 10.0, 1000.0, 3.0);
                (node_score + edge_score + domain_score + cross_edge_score).min(10.0)
            },
            // 2. Reasoning Depth (0-10)
            reasoning_depth: {
                let accuracy_score = Self::scale(m.prediction_accuracy, 0.3, 0.95, 5.0);
                let inference_score = Self::scale(m.cross_domain_inferences as f64, 5.0, 500.0, 3.0);
                let mip_score = Self::scale(m.mip_score, 0.1, 0.8, 2.0);
                (accuracy_score + inference_score + mip_score).min(10.0)
            },
            // 3. Self-Improvement (0-10)
            self_improvement: {
                let cycles_score = Self::scale(m.self_improvement_cycles as f64, 1.0, 100.0, 5.0);
                let gates_score = Self::scale(m.gates_passed as f64, 1.0, 10.0, 5.0);
                (cycles_score + gates_score).min(10.0)
            },
            // 4. Calibration (0-10)
            calibration: {
                // ECE: lower is better. 0.0 = perfect, 0.3 = terrible
                let ece_score = if m.ece < 0.001 {
                    0.0 // Not measured yet
                } else if m.ece < 0.05 {
                    10.0
                } else if m.ece < 0.10 {
                    8.0
                } else if m.ece < 0.15 {
                    6.0
                } else if m.ece < 0.20 {
                    4.0
                } else if m.ece < 0.30 {
                    2.0
                } else {
                    1.0
                };
                ece_score
            },
            // 5. Adversarial Robustness (0-10)
            adversarial_robustness: {
                let debate_score = Self::scale(m.debate_count as f64, 5.0, 200.0, 4.0);
                let contradiction_score = Self::scale(m.contradiction_count as f64, 3.0, 100.0, 3.0);
                // Bonus for having diverse debate outcomes
                let diversity_bonus = if m.contradiction_count > 0
                    && m.debate_count > 0
                    && (m.contradiction_count as f64 / m.debate_count as f64) > 0.1
                {
                    3.0
                } else {
                    0.0
                };
                (debate_score + contradiction_score + diversity_bonus).min(10.0)
            },
            // 6. Integrated Information (0-10)
            integrated_information: {
                let phi_score = Self::scale(m.phi.hms_phi, 0.1, 5.0, 4.0);
                let micro_score = Self::scale(m.phi.phi_micro, 0.1, 1.0, 2.0);
                let meso_score = Self::scale(m.phi.phi_meso, 0.1, 1.0, 2.0);
                let macro_score = Self::scale(m.phi.phi_macro, 0.1, 1.0, 2.0);
                (phi_score + micro_score + meso_score + macro_score).min(10.0)
            },
            // 7. Autonomous Curiosity (0-10)
            autonomous_curiosity: {
                let goals_score = Self::scale(m.auto_goals as f64, 10.0, 500.0, 4.0);
                let discovery_score = Self::scale(m.curiosity_discoveries as f64, 3.0, 100.0, 6.0);
                (goals_score + discovery_score).min(10.0)
            },
            // 8. Novel Synthesis (0-10)
            novel_synthesis: {
                let concept_score = Self::scale(m.novel_concepts as f64, 5.0, 200.0, 5.0);
                let cross_domain_score = Self::scale(m.cross_domain_inferences as f64, 10.0, 500.0, 5.0);
                (concept_score + cross_domain_score).min(10.0)
            },
            // 9. System Reliability (0-10)
            system_reliability: {
                let total_subs = m.subsystems.len().max(1) as f64;
                let active_subs = m.subsystems.iter().filter(|s| s.runs > 0).count() as f64;
                let active_ratio = active_subs / total_subs;
                let gate_ratio = m.gates_passed as f64 / m.gates_total.max(1) as f64;
                (active_ratio * 6.0 + gate_ratio * 4.0).min(10.0)
            },
            // 10. Scale Readiness (0-10)
            scale_readiness: {
                // Scored on logarithmic scale toward trillion-node target
                let node_log_score = if m.total_nodes > 0 {
                    let log_nodes = (m.total_nodes as f64).log10();
                    // 3 (1K) = 1, 6 (1M) = 4, 9 (1B) = 7, 12 (1T) = 10
                    Self::scale(log_nodes, 3.0, 12.0, 7.0)
                } else {
                    0.0
                };
                let edge_density = if m.total_nodes > 0 {
                    m.total_edges as f64 / m.total_nodes as f64
                } else {
                    0.0
                };
                let density_score = Self::scale(edge_density, 0.1, 2.0, 3.0);
                (node_log_score + density_score).min(10.0)
            },
        }
    }

    /// Scale a value from [min, max] range to [0, max_score].
    fn scale(value: f64, min: f64, max: f64, max_score: f64) -> f64 {
        if value <= min {
            return 0.0;
        }
        if value >= max {
            return max_score;
        }
        ((value - min) / (max - min)) * max_score
    }

    fn grade(total: f64) -> String {
        match total as u32 {
            95..=100 => "S+ (Institutional Grade)".into(),
            90..=94 => "S (World Class)".into(),
            85..=89 => "A+ (Production Ready)".into(),
            80..=84 => "A (Strong)".into(),
            70..=79 => "B (Good)".into(),
            60..=69 => "C (Developing)".into(),
            50..=59 => "D (Early Stage)".into(),
            30..=49 => "E (Prototype)".into(),
            _ => "F (Pre-Alpha)".into(),
        }
    }

    async fn llm_review(
        &self,
        metrics: &AetherMetrics,
        score: &PeerReviewScore,
    ) -> Result<(String, Vec<String>)> {
        let mut ctx = tera::Context::new();
        ctx.insert("total_nodes", &metrics.total_nodes);
        ctx.insert("total_edges", &metrics.total_edges);
        ctx.insert("hms_phi", &metrics.phi.hms_phi);
        ctx.insert("phi_micro", &metrics.phi.phi_micro);
        ctx.insert("phi_meso", &metrics.phi.phi_meso);
        ctx.insert("phi_macro", &metrics.phi.phi_macro);
        ctx.insert("gates_passed", &metrics.gates_passed);
        ctx.insert("gates_total", &metrics.gates_total);
        ctx.insert("debate_count", &metrics.debate_count);
        ctx.insert("contradiction_count", &metrics.contradiction_count);
        ctx.insert("prediction_accuracy", &(metrics.prediction_accuracy * 100.0));
        ctx.insert("novel_concepts", &metrics.novel_concepts);
        ctx.insert("auto_goals", &metrics.auto_goals);
        ctx.insert("curiosity_discoveries", &metrics.curiosity_discoveries);
        ctx.insert("self_improvement_cycles", &metrics.self_improvement_cycles);
        ctx.insert("ece", &metrics.ece);
        ctx.insert("mip_score", &metrics.mip_score);
        ctx.insert("total_score", &score.total());

        let ranked = score.ranked_dimensions();
        let dims_str: String = ranked
            .iter()
            .map(|(name, val)| format!("  {} = {:.1}/10", name, val))
            .collect::<Vec<_>>()
            .join("\n");
        ctx.insert("dimensions", &dims_str);

        let prompt = self.prompts.render("peer_review", &ctx)?;
        let response = self
            .llm
            .generate(&self.model, "", &prompt, 0.3, 2048)
            .await?;

        let extracted = ExtractedResponse::new(response);
        let summaries = extracted.extract_xml("summary");
        let summary = summaries
            .first()
            .cloned()
            .unwrap_or_else(|| format!("Score: {:.1}/100", score.total()));

        let rec_items = extracted.extract_xml("recommendation");
        let recommendations: Vec<String> = if rec_items.is_empty() {
            ranked
                .iter()
                .take(3)
                .map(|(name, val)| format!("Improve {}: {:.1}/10", name, val))
                .collect()
        } else {
            rec_items
        };

        Ok((summary, recommendations))
    }
}
