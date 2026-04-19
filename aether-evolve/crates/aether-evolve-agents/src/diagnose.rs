use aether_evolve_core::{
    AetherMetrics, Diagnosis, DiagnosisItem, DiagnosisPriority, InterventionType,
};
use anyhow::Result;
use chrono::Utc;
use tracing::info;

use aether_evolve_llm::{ExtractedResponse, LlmBackend, LlmClient, PromptManager};

pub struct DiagnoseAgent {
    /// None when running in Claude mode (rule-based only)
    llm: Option<LlmBackend>,
    prompts: Option<PromptManager>,
    model: String,
}

impl DiagnoseAgent {
    /// Create with an LLM backend for autonomous mode.
    pub fn new(llm: LlmBackend, prompts: PromptManager, model: String) -> Self {
        Self {
            llm: Some(llm),
            prompts: Some(prompts),
            model,
        }
    }

    /// Create without LLM — rule-based diagnosis only (Claude mode).
    pub fn new_without_llm() -> Self {
        Self {
            llm: None,
            prompts: None,
            model: String::new(),
        }
    }

    /// Analyze current metrics and produce a ranked diagnosis.
    pub async fn diagnose(&self, metrics: &AetherMetrics) -> Result<Diagnosis> {
        // First: rule-based diagnosis (deterministic, no LLM needed)
        let mut items = self.rule_based_diagnosis(metrics);

        // If we have LLM and only low-priority items, enhance with LLM
        if self.llm.is_some()
            && (items.is_empty() || items.iter().all(|i| i.priority as u32 >= 3))
        {
            match self.llm_diagnosis(metrics).await {
                Ok(mut llm_items) => items.append(&mut llm_items),
                Err(e) => {
                    tracing::warn!("LLM diagnosis failed, using rule-based only: {e}");
                }
            }
        }

        // Sort by priority
        items.sort_by_key(|i| i.priority);

        info!(
            count = items.len(),
            top_priority = ?items.first().map(|i| &i.priority),
            llm_available = self.llm.is_some(),
            "Diagnosis complete"
        );

        Ok(Diagnosis {
            timestamp: Utc::now(),
            items,
            metrics_snapshot: metrics.clone(),
        })
    }

    fn rule_based_diagnosis(&self, m: &AetherMetrics) -> Vec<DiagnosisItem> {
        let mut items = Vec::new();

        // P0: Stale/restored phi cache — must recalculate before any code changes
        let is_stale_cache = m.phi.formula == "restored"
            || (m.phi.phi_meso == 0.0 && m.phi.phi_micro == 0.0 && m.phi.phi_macro == 0.0
                && m.total_nodes > 1000);

        if is_stale_cache {
            items.push(DiagnosisItem {
                priority: DiagnosisPriority::P0PhiZero,
                category: "phi_cache_stale".into(),
                description: format!(
                    "Phi cache is stale (formula='{}') — all HMS components are zero despite {} nodes. \
                     Need to force recalculation.",
                    m.phi.formula, m.total_nodes
                ),
                root_cause: "Phi was restored from DB on startup with zeros. \
                             No new blocks have triggered recomputation."
                    .into(),
                recommended_intervention: InterventionType::CacheBust,
                target_files: vec!["API: /aether/phi/recalculate".into()],
                expected_improvement: "phi_meso > 0, phi_micro > 0 after fresh computation".into(),
            });
            return items;
        }

        // P0: Any phi component is zero (after cache bust)
        if m.phi.phi_meso == 0.0 {
            items.push(DiagnosisItem {
                priority: DiagnosisPriority::P0PhiZero,
                category: "phi_meso_zero".into(),
                description: "phi_meso = 0.0 — multiplicative death kills HMS-Phi".into(),
                root_cause: "Meso-level MIP spectral bisection returning degenerate values, \
                             or domain clusters are empty/disconnected"
                    .into(),
                recommended_intervention: InterventionType::CodeChange,
                target_files: vec!["src/qubitcoin/aether/phi_calculator.py".into()],
                expected_improvement: "phi_meso > 0 → HMS-Phi becomes non-zero".into(),
            });
        }

        if m.phi.phi_micro == 0.0 {
            items.push(DiagnosisItem {
                priority: DiagnosisPriority::P0PhiZero,
                category: "phi_micro_zero".into(),
                description: "phi_micro = 0.0 — IIT micro-level integration is zero".into(),
                root_cause: "IIT approximator not running or returning degenerate results".into(),
                recommended_intervention: InterventionType::CodeChange,
                target_files: vec!["src/qubitcoin/aether/iit_approximator.py".into()],
                expected_improvement: "phi_micro > 0 → HMS-Phi micro component non-zero".into(),
            });
        }

        // P1: Gate blockers — targeted diagnosis per gate
        for gate in &m.gates {
            if !gate.passed {
                let (intervention, files, root_cause, expected) = match gate.gate_number {
                    4 => {
                        // Gate 4: Self-Correction — needs debates, contradictions, MIP
                        // Diagnose WHICH sub-requirement is failing
                        if m.debate_count < 20 {
                            (
                                InterventionType::CodeChange,
                                vec![
                                    "src/qubitcoin/aether/debate.py".into(),
                                    "src/qubitcoin/aether/proof_of_thought.py".into(),
                                ],
                                format!(
                                    "Only {} debates (need 20). Debate interval too high or \
                                     max_debates too low. Verdict logic may be imbalanced.",
                                    m.debate_count
                                ),
                                "Debate frequency increased, verdict diversity improved".into(),
                            )
                        } else if m.contradiction_count < 10 {
                            (
                                InterventionType::CodeChange,
                                vec!["src/qubitcoin/aether/debate.py".into()],
                                format!(
                                    "Only {} contradictions resolved (need 10). All debate \
                                     verdicts may be 'accepted' — critic too weak or verdict \
                                     thresholds too tight.",
                                    m.contradiction_count
                                ),
                                "Debate verdicts include modified/rejected → contradiction nodes created".into(),
                            )
                        } else {
                            (
                                InterventionType::CodeChange,
                                vec!["src/qubitcoin/aether/phi_calculator.py".into()],
                                format!(
                                    "MIP score {} < 0.3. Graph integration too low — \
                                     too many disconnected observation nodes.",
                                    m.mip_score
                                ),
                                "MIP computation improved or graph pruned for higher integration".into(),
                            )
                        }
                    }
                    10 => (
                        InterventionType::KnowledgeSeed,
                        vec!["API: /aether/ingest/batch".into()],
                        "Novel synthesis requires diverse cross-domain knowledge".into(),
                        "Gate 10 passed".into(),
                    ),
                    8 => (
                        InterventionType::KnowledgeSeed,
                        vec!["API: /aether/ingest/batch".into()],
                        "Autonomous curiosity needs diverse domains to explore".into(),
                        "Gate 8 passed with curiosity discoveries".into(),
                    ),
                    6 => (
                        InterventionType::CodeChange,
                        vec![
                            "src/qubitcoin/aether/self_improvement.py".into(),
                            "src/qubitcoin/aether/proof_of_thought.py".into(),
                        ],
                        "Gate 6 needs enacted self-improvement cycles with positive \
                         performance delta. Check if improvement strategies are being \
                         enacted (not just proposed)."
                            .into(),
                        "Self-improvement actively enacting and measuring improvements".into(),
                    ),
                    7 => (
                        InterventionType::CodeChange,
                        vec![
                            "src/qubitcoin/aether/metacognition.py".into(),
                            "src/qubitcoin/aether/phi_calculator.py".into(),
                        ],
                        format!(
                            "Gate 7 needs ECE < 0.15 and ≥200 evaluations. \
                             Current calibration may be using raw confidence instead \
                             of calibrated values."
                        ),
                        "ECE below 0.15 with calibrated confidence scores".into(),
                    ),
                    9 => (
                        InterventionType::CodeChange,
                        vec![
                            "src/qubitcoin/aether/reasoning.py".into(),
                            "src/qubitcoin/aether/knowledge_graph.py".into(),
                        ],
                        format!(
                            "Gate 9 needs prediction accuracy > 70%% and ≥20 consolidated \
                             axioms. Prediction verification or axiom consolidation may be \
                             too conservative."
                        ),
                        "Prediction accuracy > 70% with axiom consolidation active".into(),
                    ),
                    _ => (
                        InterventionType::KnowledgeSeed,
                        vec!["API: /aether/ingest/batch".into()],
                        format!("Requirements not met for gate {}", gate.gate_number),
                        format!("Gate {} passed", gate.gate_number),
                    ),
                };

                items.push(DiagnosisItem {
                    priority: DiagnosisPriority::P1GateBlocker,
                    category: format!("gate_{}_blocked", gate.gate_number),
                    description: format!(
                        "Gate {} ({}) not passed: {}",
                        gate.gate_number, gate.name, gate.details
                    ),
                    root_cause,
                    recommended_intervention: intervention,
                    target_files: files,
                    expected_improvement: expected,
                });
            }
        }

        // P2: Dead subsystems
        for sub in &m.subsystems {
            if sub.runs == 0 {
                items.push(DiagnosisItem {
                    priority: DiagnosisPriority::P2SubsystemDead,
                    category: format!("{}_dead", sub.name),
                    description: format!("{} has 0 runs — never activated", sub.name),
                    root_cause: "Activation threshold too high or never triggered".into(),
                    recommended_intervention: InterventionType::ApiCall,
                    target_files: vec![],
                    expected_improvement: format!("{} activated with > 0 runs", sub.name),
                });
            }
        }

        // P3: Quality gaps
        if m.debate_count < 20 {
            items.push(DiagnosisItem {
                priority: DiagnosisPriority::P3QualityGap,
                category: "low_debates".into(),
                description: format!("Only {} debates (need 20+)", m.debate_count),
                root_cause: "Debate triggered too infrequently".into(),
                recommended_intervention: InterventionType::KnowledgeSeed,
                target_files: vec!["API: /aether/chat".into()],
                expected_improvement: "Debate count reaches 20+".into(),
            });
        }

        if m.novel_concepts < 50 {
            items.push(DiagnosisItem {
                priority: DiagnosisPriority::P4ScaleGap,
                category: "low_novel_concepts".into(),
                description: format!("Only {} novel concepts (need 50+)", m.novel_concepts),
                root_cause: "Concept formation not active or not producing novel output".into(),
                recommended_intervention: InterventionType::KnowledgeSeed,
                target_files: vec!["API: /aether/ingest/batch".into()],
                expected_improvement: "Novel concepts count increases".into(),
            });
        }

        items
    }

    async fn llm_diagnosis(&self, metrics: &AetherMetrics) -> Result<Vec<DiagnosisItem>> {
        let llm = self.llm.as_ref().ok_or_else(|| anyhow::anyhow!("No LLM available"))?;
        let prompts = self.prompts.as_ref().ok_or_else(|| anyhow::anyhow!("No prompts available"))?;

        let mut ctx = tera::Context::new();
        ctx.insert("block_height", &metrics.block_height);
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
        ctx.insert("mip_score", &metrics.mip_score);
        ctx.insert("subsystems", &metrics.subsystems);

        let prompt = prompts.render("diagnose", &ctx)?;
        let response = llm.generate(&self.model, "", &prompt, 0.3, 2048).await?;

        let extracted = ExtractedResponse::new(response);
        let xml_items = extracted.extract_diagnosis_items();

        let items: Vec<DiagnosisItem> = xml_items
            .into_iter()
            .map(|x| DiagnosisItem {
                priority: DiagnosisPriority::P3QualityGap,
                category: "llm_identified".into(),
                description: x.description,
                root_cause: x.root_cause,
                recommended_intervention: match x.intervention.to_uppercase().as_str() {
                    "CODE_CHANGE" => InterventionType::CodeChange,
                    "KNOWLEDGE_SEED" => InterventionType::KnowledgeSeed,
                    "SWARM_SEED" => InterventionType::SwarmSeed,
                    _ => InterventionType::ApiCall,
                },
                target_files: x
                    .target_files
                    .split(',')
                    .map(|s| s.trim().to_string())
                    .collect(),
                expected_improvement: x.expected_improvement,
            })
            .collect();

        Ok(items)
    }
}
