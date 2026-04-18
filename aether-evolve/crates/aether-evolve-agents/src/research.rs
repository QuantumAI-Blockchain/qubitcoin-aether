use aether_evolve_core::{CodeDiff, DiagnosisItem, EvolvePlan, InterventionType, KnowledgePayload};
use anyhow::{Context, Result};
use tracing::{info, warn};

use aether_evolve_llm::{ExtractedResponse, LlmBackend, LlmClient, PromptManager};
use aether_evolve_memory::CognitionStore;

/// Maximum lines of code context to send to the LLM.
/// On CPU Ollama with small models, full files (700+ lines) cause timeouts.
const MAX_CONTEXT_LINES: usize = 120;

/// Lines of context to include above/below a keyword match.
const CONTEXT_MARGIN: usize = 40;

/// Type alias — ResearchPlan is now the shared EvolvePlan from core.
pub type ResearchPlan = EvolvePlan;

pub struct ResearchAgent {
    llm: LlmBackend,
    prompts: PromptManager,
    primary_model: String,
    fast_model: String,
    repo_root: String,
}

impl ResearchAgent {
    pub fn new(
        llm: LlmBackend,
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
            InterventionType::CacheBust => {
                // No LLM research needed — just bust the cache
                info!("CacheBust intervention — skipping LLM research");
                Ok(ResearchPlan {
                    intervention_type: InterventionType::CacheBust,
                    hypothesis: "Bust stale phi cache to trigger fresh computation".into(),
                    diffs: Vec::new(),
                    seeds: Vec::new(),
                })
            }
        }
    }

    /// Extract the most relevant section of a file based on keywords from the diagnosis.
    /// Returns (extracted_content, start_line) so patches can be context-aware.
    fn extract_relevant_section(
        file_content: &str,
        description: &str,
        root_cause: &str,
    ) -> String {
        let lines: Vec<&str> = file_content.lines().collect();
        let total_lines = lines.len();

        // If file is small enough, return it all
        if total_lines <= MAX_CONTEXT_LINES {
            return file_content.to_string();
        }

        // Extract keywords from diagnosis to find relevant code
        let keywords: Vec<&str> = description
            .split_whitespace()
            .chain(root_cause.split_whitespace())
            .filter(|w| w.len() > 3)
            .filter(|w| {
                // Skip common English words, keep code-relevant terms
                !matches!(
                    w.to_lowercase().as_str(),
                    "the" | "this" | "that" | "with" | "from" | "into"
                        | "have" | "been" | "will" | "should" | "could"
                        | "would" | "must" | "which" | "where" | "when"
                        | "what" | "zero" | "level" | "needs" | "more"
                        | "than" | "most" | "some" | "very" | "also"
                        | "does" | "kills" | "returning" | "values"
                )
            })
            .collect();

        // Find lines that match keywords (case-insensitive)
        let mut match_scores: Vec<(usize, usize)> = Vec::new(); // (line_idx, score)
        for (idx, line) in lines.iter().enumerate() {
            let lower = line.to_lowercase();
            let score = keywords
                .iter()
                .filter(|kw| lower.contains(&kw.to_lowercase()))
                .count();
            if score > 0 {
                match_scores.push((idx, score));
            }
        }

        // Also look for Python function/class definitions near matches
        for (idx, line) in lines.iter().enumerate() {
            if line.trim_start().starts_with("def ")
                || line.trim_start().starts_with("class ")
                || line.trim_start().starts_with("async def ")
            {
                let lower = line.to_lowercase();
                let score = keywords
                    .iter()
                    .filter(|kw| lower.contains(&kw.to_lowercase()))
                    .count();
                if score > 0 {
                    // Boost function/class definitions
                    match_scores.push((idx, score + 3));
                }
            }
        }

        if match_scores.is_empty() {
            // No keyword matches — return the first MAX_CONTEXT_LINES
            warn!("No keyword matches found, returning file head");
            return lines[..MAX_CONTEXT_LINES.min(total_lines)]
                .join("\n");
        }

        // Sort by score descending, take the best match center
        match_scores.sort_by(|a, b| b.1.cmp(&a.1));
        let best_line = match_scores[0].0;

        // Expand to include surrounding context
        let start = best_line.saturating_sub(CONTEXT_MARGIN);
        let end = (best_line + CONTEXT_MARGIN).min(total_lines);

        // Try to align to function boundaries
        let mut func_start = start;
        for i in (0..=start).rev() {
            let trimmed = lines[i].trim_start();
            if trimmed.starts_with("def ")
                || trimmed.starts_with("class ")
                || trimmed.starts_with("async def ")
            {
                func_start = i;
                break;
            }
        }

        let actual_start = func_start.min(start);
        let actual_end = end.min(actual_start + MAX_CONTEXT_LINES);

        let mut result = format!("# ... (lines 1-{} omitted) ...\n", actual_start);
        result.push_str(&lines[actual_start..actual_end].join("\n"));
        if actual_end < total_lines {
            result.push_str(&format!(
                "\n# ... (lines {}-{} omitted) ...",
                actual_end + 1,
                total_lines
            ));
        }

        info!(
            total_lines,
            extracted_start = actual_start,
            extracted_end = actual_end,
            best_match_line = best_line,
            "Extracted relevant code section"
        );

        result
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

            // Extract only the relevant section to keep prompt small for CPU LLM
            let relevant_section = Self::extract_relevant_section(
                &file_content,
                &item.description,
                &item.root_cause,
            );

            info!(
                file = %target_file,
                full_lines = file_content.lines().count(),
                context_lines = relevant_section.lines().count(),
                "Sending truncated context to LLM"
            );

            let mut ctx = tera::Context::new();
            ctx.insert("diagnosis_description", &item.description);
            ctx.insert("root_cause", &item.root_cause);
            ctx.insert("file_content", &relevant_section);
            ctx.insert("file_path", target_file);

            let prompt = self.prompts.render("research_code", &ctx)?;
            // Use fast_model for code research — primary is too slow on CPU
            let response = self
                .llm
                .generate(&self.fast_model, "", &prompt, 0.2, 2048)
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
        // For gate blockers, generate deterministic seeds — skip LLM entirely
        if item.category.starts_with("gate_") {
            info!(category = %item.category, "Gate blocker — generating deterministic seeds");
            let seeds = Self::gate_blocker_seeds(&item.category, &item.description);
            return Ok(ResearchPlan {
                intervention_type: InterventionType::KnowledgeSeed,
                hypothesis: format!("Targeted seeds for: {}", item.description),
                diffs: Vec::new(),
                seeds,
            });
        }

        // Get relevant cognition items for context
        let relevant = cognition.search(&item.category, 5);
        let domains_str = relevant
            .iter()
            .map(|c| format!("{}: {}", c.domain, c.title))
            .collect::<Vec<_>>()
            .join("\n");

        let count = match item.priority as u32 {
            0..=1 => 5,
            2 => 3,
            _ => 2,
        };

        let mut ctx = tera::Context::new();
        ctx.insert("total_nodes", &0u64);
        ctx.insert("domains", &domains_str);
        ctx.insert("diagnosis_description", &item.description);
        ctx.insert("count", &count);

        let prompt = self.prompts.render("research_seed", &ctx)?;
        let response = self
            .llm
            .generate(&self.fast_model, "", &prompt, 0.7, 1024)
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

    /// Generate deterministic seeds for gate blocker interventions (no LLM needed).
    fn gate_blocker_seeds(category: &str, description: &str) -> Vec<KnowledgePayload> {
        let domains = ["physics", "mathematics", "philosophy", "computation", "biology",
                       "economics", "meta", "logic", "emergence", "information"];
        let mut seeds = Vec::new();

        // Generate cross-domain knowledge seeds to exercise the system
        for (i, domain) in domains.iter().enumerate().take(5) {
            seeds.push(KnowledgePayload {
                content: format!(
                    "Cross-domain insight for {}: {} — connecting {} principles to knowledge integration",
                    category, description, domain
                ),
                domain: domain.to_string(),
                node_type: if i % 2 == 0 { "hypothesis" } else { "observation" }.into(),
                confidence: 0.6 + (i as f64 * 0.05),
                connections: Vec::new(),
            });
        }

        seeds
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
