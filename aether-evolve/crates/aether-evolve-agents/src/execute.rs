use aether_evolve_core::{AetherMetrics, InterventionType};
use aether_evolve_api::{AetherClient, CodePatcher, KnowledgeSeederImpl};
use aether_evolve_safety::SafetyGovernor;
use anyhow::Result;
use tracing::{error, info, warn};

use crate::research::ResearchPlan;

pub struct ExecuteAgent {
    aether_client: AetherClient,
    code_patcher: CodePatcher,
    seeder: KnowledgeSeederImpl,
    safety: SafetyGovernor,
}

pub struct ExecutionResult {
    pub success: bool,
    pub pre_metrics: AetherMetrics,
    pub post_metrics: AetherMetrics,
    pub branch_name: Option<String>,
    pub details: String,
}

impl ExecuteAgent {
    pub fn new(
        aether_client: AetherClient,
        code_patcher: CodePatcher,
        seeder: KnowledgeSeederImpl,
        safety: SafetyGovernor,
    ) -> Self {
        Self {
            aether_client,
            code_patcher,
            seeder,
            safety,
        }
    }

    pub async fn execute(
        &self,
        step: u64,
        plan: &ResearchPlan,
    ) -> Result<ExecutionResult> {
        // Snapshot pre-metrics
        let pre_metrics = self.aether_client.snapshot().await?;

        match plan.intervention_type {
            InterventionType::CodeChange => self.execute_code_change(step, plan, pre_metrics).await,
            InterventionType::KnowledgeSeed | InterventionType::SwarmSeed => {
                self.execute_seed(step, plan, pre_metrics).await
            }
            InterventionType::ApiCall => self.execute_api_call(step, plan, pre_metrics).await,
            InterventionType::CacheBust => self.execute_cache_bust(step, pre_metrics).await,
        }
    }

    async fn execute_code_change(
        &self,
        step: u64,
        plan: &ResearchPlan,
        pre_metrics: AetherMetrics,
    ) -> Result<ExecutionResult> {
        // Safety check
        self.safety.check_code_change(&plan.diffs).await?;

        // Create branch
        let branch = self.code_patcher.create_branch(step)?;

        // Apply diffs
        let changed_files = match self.code_patcher.apply_diffs(&plan.diffs) {
            Ok(files) => files,
            Err(e) => {
                error!("Failed to apply diffs: {e}");
                self.code_patcher.rollback_to_master()?;
                return Ok(ExecutionResult {
                    success: false,
                    pre_metrics: pre_metrics.clone(),
                    post_metrics: pre_metrics,
                    branch_name: Some(branch),
                    details: format!("Diff application failed: {e}"),
                });
            }
        };

        if changed_files.is_empty() {
            warn!("No files were changed by diffs");
            self.code_patcher.rollback_to_master()?;
            return Ok(ExecutionResult {
                success: false,
                pre_metrics: pre_metrics.clone(),
                post_metrics: pre_metrics,
                branch_name: Some(branch),
                details: "No matching code found for SEARCH strings".into(),
            });
        }

        // Syntax check
        if !self.code_patcher.syntax_check(&changed_files)? {
            error!("Syntax check failed — rolling back");
            self.code_patcher.rollback_to_master()?;
            return Ok(ExecutionResult {
                success: false,
                pre_metrics: pre_metrics.clone(),
                post_metrics: pre_metrics,
                branch_name: Some(branch),
                details: "Syntax check failed".into(),
            });
        }

        // Run tests
        let module_filter = changed_files
            .first()
            .and_then(|f| f.split('/').last())
            .and_then(|f| f.strip_suffix(".py"))
            .unwrap_or("phi");

        let (tests_pass, test_output) = self.code_patcher.run_tests(module_filter)?;
        if !tests_pass {
            warn!("Tests failed — rolling back");
            self.code_patcher.rollback_to_master()?;
            return Ok(ExecutionResult {
                success: false,
                pre_metrics: pre_metrics.clone(),
                post_metrics: pre_metrics,
                branch_name: Some(branch),
                details: format!("Tests failed:\n{test_output}"),
            });
        }

        // Commit
        self.code_patcher.commit(&format!(
            "evolve(step-{step}): {}",
            plan.hypothesis
        ))?;

        // Wait for stabilization
        tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;

        // Measure post-metrics
        let post_metrics = self.aether_client.snapshot().await?;

        // Check for regression
        if self.safety.should_rollback(&pre_metrics, &post_metrics) {
            warn!("Regression detected — rolling back to master");
            self.code_patcher.rollback_to_master()?;
            return Ok(ExecutionResult {
                success: false,
                pre_metrics,
                post_metrics,
                branch_name: Some(branch.clone()),
                details: format!("Regression detected, rolled back from {branch}"),
            });
        }

        // Merge to master
        self.code_patcher.merge_to_master(&branch)?;
        self.safety.record_code_change();

        info!(step, branch = %branch, "Code change merged successfully");

        Ok(ExecutionResult {
            success: true,
            pre_metrics,
            post_metrics,
            branch_name: Some(branch),
            details: format!("Changed files: {:?}", changed_files),
        })
    }

    async fn execute_seed(
        &self,
        step: u64,
        plan: &ResearchPlan,
        pre_metrics: AetherMetrics,
    ) -> Result<ExecutionResult> {
        self.safety.check_seed_count(plan.seeds.len() as u32)?;

        let seeded = self.seeder.seed_batch(&plan.seeds).await?;

        // Wait for processing
        let wait_secs = (plan.seeds.len() as u64 / 10).max(10).min(60);
        tokio::time::sleep(tokio::time::Duration::from_secs(wait_secs)).await;

        let post_metrics = self.aether_client.snapshot().await?;

        info!(step, seeded, "Knowledge seed complete");

        Ok(ExecutionResult {
            success: seeded > 0,
            pre_metrics,
            post_metrics,
            branch_name: None,
            details: format!("Seeded {seeded}/{} knowledge nodes", plan.seeds.len()),
        })
    }

    async fn execute_cache_bust(
        &self,
        step: u64,
        pre_metrics: AetherMetrics,
    ) -> Result<ExecutionResult> {
        info!(step, "Busting stale phi cache — forcing recalculation");

        match self.aether_client.recalculate_phi().await {
            Ok(phi_data) => {
                let phi_val = phi_data["phi_value"].as_f64().unwrap_or(0.0);
                let formula = phi_data["phi_formula"]
                    .as_str()
                    .unwrap_or("unknown")
                    .to_string();

                // Wait for metrics to stabilize
                tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
                let post_metrics = self.aether_client.snapshot().await?;

                info!(
                    step,
                    phi = phi_val,
                    formula = %formula,
                    "Cache bust complete"
                );

                Ok(ExecutionResult {
                    success: formula != "restored",
                    pre_metrics,
                    post_metrics,
                    branch_name: None,
                    details: format!(
                        "Phi recalculated: value={:.6}, formula={}, phi_meso={}, phi_micro={}, phi_macro={}",
                        phi_val,
                        formula,
                        phi_data["phi_meso"].as_f64().unwrap_or(0.0),
                        phi_data["phi_micro"].as_f64().unwrap_or(0.0),
                        phi_data["phi_macro"].as_f64().unwrap_or(0.0),
                    ),
                })
            }
            Err(e) => {
                warn!("Cache bust failed: {e}");
                Ok(ExecutionResult {
                    success: false,
                    pre_metrics: pre_metrics.clone(),
                    post_metrics: pre_metrics,
                    branch_name: None,
                    details: format!("Cache bust failed: {e}"),
                })
            }
        }
    }

    async fn execute_api_call(
        &self,
        step: u64,
        plan: &ResearchPlan,
        pre_metrics: AetherMetrics,
    ) -> Result<ExecutionResult> {
        self.safety.check_api_call().await?;

        // Use chat to exercise subsystems
        for seed in &plan.seeds {
            let _ = self.aether_client.chat(&seed.content).await;
            self.safety.record_api_call();
            tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
        }

        // Also trigger causal discovery and debate
        let _ = self.seeder.trigger_causal_discovery().await;
        let _ = self.seeder.trigger_debate(&plan.hypothesis).await;

        tokio::time::sleep(tokio::time::Duration::from_secs(15)).await;
        let post_metrics = self.aether_client.snapshot().await?;

        info!(step, "API call execution complete");

        Ok(ExecutionResult {
            success: true,
            pre_metrics,
            post_metrics,
            branch_name: None,
            details: format!("Executed {} API calls + debate + causal", plan.seeds.len()),
        })
    }
}
