use aether_evolve_core::{ExperimentNode, MetricsDelta};
use anyhow::Result;
use tracing::info;

use aether_evolve_llm::{ExtractedResponse, LlmBackend, LlmClient, PromptManager};

use crate::execute::ExecutionResult;
use crate::research::ResearchPlan;

pub struct AnalyzeAgent {
    llm: LlmBackend,
    prompts: PromptManager,
    model: String,
}

pub struct AnalysisResult {
    pub experiment: ExperimentNode,
    pub lesson: String,
}

impl AnalyzeAgent {
    pub fn new(llm: LlmBackend, prompts: PromptManager, model: String) -> Self {
        Self { llm, prompts, model }
    }

    pub async fn analyze(
        &self,
        step: u64,
        plan: &ResearchPlan,
        result: &ExecutionResult,
    ) -> Result<AnalysisResult> {
        let delta = MetricsDelta::compute(&result.pre_metrics, &result.post_metrics);
        let score = delta.score();

        // Get LLM analysis
        let (analysis_text, lesson) = match self.llm_analyze(step, plan, result, &delta).await {
            Ok((a, l)) => (a, l),
            Err(e) => {
                tracing::warn!("LLM analysis failed: {e}");
                let summary = format!(
                    "Delta phi: {:.6}, gates: {:+}, nodes: {:+}, score: {:.1}",
                    delta.delta_phi, delta.delta_gates, delta.delta_nodes, score
                );
                (summary.clone(), summary)
            }
        };

        let experiment = ExperimentNode {
            id: 0, // Will be set by database
            step,
            timestamp: chrono::Utc::now(),
            intervention_type: plan.intervention_type.clone(),
            diagnosis_summary: plan.hypothesis.clone(),
            hypothesis: plan.hypothesis.clone(),
            diffs: plan.diffs.clone(),
            seeds: plan.seeds.clone(),
            pre_metrics: result.pre_metrics.clone(),
            post_metrics: result.post_metrics.clone(),
            analysis: analysis_text,
            score,
            parent_ids: Vec::new(),
            tags: vec![format!("{:?}", plan.intervention_type)],
        };

        info!(
            step,
            score,
            delta_phi = delta.delta_phi,
            delta_gates = delta.delta_gates,
            "Analysis complete"
        );

        Ok(AnalysisResult { experiment, lesson })
    }

    async fn llm_analyze(
        &self,
        step: u64,
        plan: &ResearchPlan,
        result: &ExecutionResult,
        delta: &MetricsDelta,
    ) -> Result<(String, String)> {
        let mut ctx = tera::Context::new();
        ctx.insert("intervention_type", &format!("{:?}", plan.intervention_type));
        ctx.insert("hypothesis", &plan.hypothesis);
        ctx.insert("step", &step);
        ctx.insert("pre_phi", &result.pre_metrics.phi.hms_phi);
        ctx.insert("pre_nodes", &result.pre_metrics.total_nodes);
        ctx.insert("pre_gates", &result.pre_metrics.gates_passed);
        ctx.insert("pre_debates", &result.pre_metrics.debate_count);
        ctx.insert("post_phi", &result.post_metrics.phi.hms_phi);
        ctx.insert("post_nodes", &result.post_metrics.total_nodes);
        ctx.insert("post_gates", &result.post_metrics.gates_passed);
        ctx.insert("post_debates", &result.post_metrics.debate_count);
        ctx.insert("changes_summary", &result.details);

        let prompt = self.prompts.render("analyze", &ctx)?;
        let response = self
            .llm
            .generate(&self.model, "", &prompt, 0.3, 1024)
            .await?;

        let extracted = ExtractedResponse::new(response);
        let lessons = extracted.extract_xml("lesson");
        let lesson = lessons.first().cloned().unwrap_or_else(|| {
            format!(
                "Score {:.1}: delta_phi={:.6}, delta_gates={:+}",
                delta.score(),
                delta.delta_phi,
                delta.delta_gates
            )
        });

        let analyses = extracted.extract_xml("analysis");
        let analysis = analyses.first().cloned().unwrap_or_else(|| {
            format!("Automated analysis: {}", lesson)
        });

        Ok((analysis, lesson))
    }
}
