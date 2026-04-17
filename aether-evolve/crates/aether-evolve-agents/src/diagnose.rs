use aether_evolve_core::{
    AetherMetrics, Diagnosis, DiagnosisItem, DiagnosisPriority, InterventionType,
};
use anyhow::Result;
use chrono::Utc;
use tracing::info;

use aether_evolve_llm::{ExtractedResponse, OllamaClient, PromptManager};

pub struct DiagnoseAgent {
    llm: OllamaClient,
    prompts: PromptManager,
    model: String,
}

impl DiagnoseAgent {
    pub fn new(llm: OllamaClient, prompts: PromptManager, model: String) -> Self {
        Self { llm, prompts, model }
    }

    /// Analyze current metrics and produce a ranked diagnosis.
    pub async fn diagnose(&self, metrics: &AetherMetrics) -> Result<Diagnosis> {
        // First: rule-based diagnosis (deterministic, no LLM needed)
        let mut items = self.rule_based_diagnosis(metrics);

        // If we have items already, we can optionally enhance with LLM
        // For speed, skip LLM if we have clear P0/P1 items
        if items.is_empty() || items.iter().all(|i| i.priority as u32 >= 3) {
            // Use LLM for deeper analysis
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

        // P0: Any phi component is zero
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

        // P1: Gate blockers
        for gate in &m.gates {
            if !gate.passed {
                let (intervention, files) = match gate.gate_number {
                    4 => (
                        InterventionType::KnowledgeSeed,
                        vec!["API: /aether/chat".into()],
                    ),
                    10 => (
                        InterventionType::KnowledgeSeed,
                        vec!["API: /aether/ingest/batch".into()],
                    ),
                    _ => (InterventionType::ApiCall, vec![]),
                };

                items.push(DiagnosisItem {
                    priority: DiagnosisPriority::P1GateBlocker,
                    category: format!("gate_{}_blocked", gate.gate_number),
                    description: format!(
                        "Gate {} ({}) not passed: {}",
                        gate.gate_number, gate.name, gate.details
                    ),
                    root_cause: format!("Requirements not met for gate {}", gate.gate_number),
                    recommended_intervention: intervention,
                    target_files: files,
                    expected_improvement: format!("Gate {} passed", gate.gate_number),
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

        let prompt = self.prompts.render("diagnose", &ctx)?;
        let response = self.llm.generate(&self.model, "", &prompt, 0.3, 2048).await?;

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
