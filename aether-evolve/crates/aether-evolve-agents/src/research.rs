use aether_evolve_core::{CodeDiff, DiagnosisItem, InterventionType, KnowledgePayload};
use anyhow::{Context, Result};
use tracing::info;

use aether_evolve_llm::{ExtractedResponse, OllamaClient, PromptManager};
use aether_evolve_memory::CognitionStore;

/// Output of the research phase.
pub struct ResearchPlan {
    pub intervention_type: InterventionType,
    pub hypothesis: String,
    pub diffs: Vec<CodeDiff>,
    pub seeds: Vec<KnowledgePayload>,
}

pub struct ResearchAgent {
    llm: OllamaClient,
    prompts: PromptManager,
    primary_model: String,
    fast_model: String,
    repo_root: String,
}

impl ResearchAgent {
    pub fn new(
        llm: OllamaClient,
        prompts: PromptManager,
        primary_model: String,
        fast_model: String,
        repo_root: String,
    ) -> Self {
        Self {
            llm,
            prompts,
            primary_model,
            fast_model,
            repo_root,
        }
    }

    /// Generate a research plan for the top diagnosis item.
    pub async fn research(
        &self,
        item: &DiagnosisItem,
        cognition: &CognitionStore,
    ) -> Result<ResearchPlan> {
        match item.recommended_intervention {
            InterventionType::CodeChange => self.research_code(item).await,
            InterventionType::KnowledgeSeed | InterventionType::SwarmSeed => {
                self.research_seed(item, cognition).await
            }
            InterventionType::ApiCall => self.research_api_call(item).await,
        }
    }

    async fn research_code(&self, item: &DiagnosisItem) -> Result<ResearchPlan> {
        let mut all_diffs = Vec::new();

        for target_file in &item.target_files {
            if target_file.starts_with("API:") {
                continue;
            }

            let full_path = format!("{}/{}", self.repo_root, target_file);
            let file_content = std::fs::read_to_string(&full_path)
                .with_context(|| format!("Failed to read {full_path}"))?;

            let mut ctx = tera::Context::new();
            ctx.insert("diagnosis_description", &item.description);
            ctx.insert("root_cause", &item.root_cause);
            ctx.insert("file_content", &file_content);
            ctx.insert("file_path", target_file);

            let prompt = self.prompts.render("research_code", &ctx)?;
            let response = self
                .llm
                .generate(&self.primary_model, "", &prompt, 0.2, 4096)
                .await?;

            let extracted = ExtractedResponse::new(response);
            let patches = extracted.extract_patches();

            for (search, replace) in patches {
                all_diffs.push(CodeDiff {
                    file_path: target_file.clone(),
                    search,
                    replace,
                });
            }
        }

        info!(
            diffs = all_diffs.len(),
            "Code research complete"
        );

        Ok(ResearchPlan {
            intervention_type: InterventionType::CodeChange,
            hypothesis: format!("Fix: {}", item.description),
            diffs: all_diffs,
            seeds: Vec::new(),
        })
    }

    async fn research_seed(
        &self,
        item: &DiagnosisItem,
        cognition: &CognitionStore,
    ) -> Result<ResearchPlan> {
        // Get relevant cognition items for context
        let relevant = cognition.search(&item.category, 5);
        let domains_str = relevant
            .iter()
            .map(|c| format!("{}: {}", c.domain, c.title))
            .collect::<Vec<_>>()
            .join("\n");

        let count = match item.priority as u32 {
            0..=1 => 20,
            2 => 10,
            _ => 5,
        };

        let mut ctx = tera::Context::new();
        ctx.insert("total_nodes", &0u64);
        ctx.insert("domains", &domains_str);
        ctx.insert("diagnosis_description", &item.description);
        ctx.insert("count", &count);

        let prompt = self.prompts.render("research_seed", &ctx)?;
        let response = self
            .llm
            .generate(&self.fast_model, "", &prompt, 0.7, 4096)
            .await?;

        let extracted = ExtractedResponse::new(response);
        let seeds: Vec<KnowledgePayload> = extracted
            .parse_json()
            .unwrap_or_else(|_| Vec::new());

        info!(seeds = seeds.len(), "Seed research complete");

        Ok(ResearchPlan {
            intervention_type: InterventionType::KnowledgeSeed,
            hypothesis: format!("Seed knowledge to address: {}", item.description),
            diffs: Vec::new(),
            seeds,
        })
    }

    async fn research_api_call(&self, item: &DiagnosisItem) -> Result<ResearchPlan> {
        // For API calls, generate chat prompts that exercise the target subsystem
        let seeds = vec![KnowledgePayload {
            content: format!(
                "Trigger {} — {}",
                item.category, item.description
            ),
            domain: "meta".into(),
            node_type: "observation".into(),
            confidence: 0.7,
            connections: Vec::new(),
        }];

        Ok(ResearchPlan {
            intervention_type: InterventionType::ApiCall,
            hypothesis: format!("Activate subsystem: {}", item.category),
            diffs: Vec::new(),
            seeds,
        })
    }
}
