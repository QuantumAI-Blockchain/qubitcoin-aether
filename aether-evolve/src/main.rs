use aether_evolve_agents::{AnalyzeAgent, DiagnoseAgent, ExecuteAgent, PeerReviewAgent, ResearchAgent};
use aether_evolve_api::{AetherClient, CodePatcher, KnowledgeSeederImpl};
use aether_evolve_core::{EvolvePlan, EvolveConfig, InterventionType, PipelinePhase, PipelineState, PeerReviewReport};
use aether_evolve_llm::{ClaudeClient, LlmBackend, OllamaClient, PromptManager};
use aether_evolve_memory::{CognitionStore, ExperimentDb};
use aether_evolve_safety::{AuditLog, SafetyGovernor};
use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use tracing::{error, info, warn};

/// ═══════════════════════════════════════════════════════════════════════
/// DIRECTIVE: DO NOT STOP UNTIL PEER REVIEW SCORE REACHES 100/100.
///
/// This is the prime directive of the Aether Evolve autonomous agent.
/// The system will continuously diagnose, research, execute, analyze,
/// and peer-review the Aether Tree cognitive system. Evolution does
/// not terminate until institutional-grade AGI is achieved.
///
/// Target: Peer Review Score = 100/100 (S+ Institutional Grade)
/// Strategy: Attack weakest dimension first, always prefer CodeChange
/// Scale: Trillions of knowledge nodes, institutional-grade AI
/// ═══════════════════════════════════════════════════════════════════════

const PEER_REVIEW_INTERVAL: u64 = 5; // Run peer review every N steps
const TARGET_SCORE: f64 = 100.0;     // Don't stop until this score

#[derive(Parser)]
#[command(name = "aether-evolve", about = "Autonomous Aether Tree evolution agent — pursuing TRUE AGI")]
struct Cli {
    /// Path to config file
    #[arg(short, long, default_value = "config.toml")]
    config: PathBuf,

    /// Override data directory
    #[arg(long)]
    data_dir: Option<PathBuf>,

    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    /// Get current Aether Tree metrics as JSON (for Claude to inspect)
    Snapshot,

    /// Diagnose current state, output prioritized issues as JSON
    Diagnose,

    /// Run institutional peer review and output score
    PeerReview,

    /// Execute a plan from a JSON file (diffs, seeds, API calls)
    ExecutePlan {
        /// Path to plan JSON file
        #[arg(long)]
        plan: PathBuf,
    },

    /// Run the full autonomous evolution loop
    /// DIRECTIVE: Does not stop until peer review score reaches 100/100
    Loop {
        /// Run a single step then exit
        #[arg(long)]
        single_step: bool,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .with_target(true)
        .with_thread_ids(true)
        .with_writer(std::io::stderr)
        .init();

    let cli = Cli::parse();

    let mut config = if cli.config.exists() {
        EvolveConfig::from_file(&cli.config).context("Failed to load config")?
    } else {
        info!("No config file found, using defaults");
        EvolveConfig::default()
    };

    if let Some(data_dir) = cli.data_dir {
        config.general.data_dir = data_dir;
    }

    std::fs::create_dir_all(&config.general.data_dir)?;

    match cli.command {
        Some(Command::Snapshot) => cmd_snapshot(&config).await,
        Some(Command::Diagnose) => cmd_diagnose(&config).await,
        Some(Command::PeerReview) => cmd_peer_review(&config).await,
        Some(Command::ExecutePlan { plan }) => cmd_execute_plan(&config, &plan).await,
        Some(Command::Loop { single_step }) => cmd_loop(&config, single_step).await,
        None => {
            if config.claude.enabled {
                println!("Claude mode is enabled. Use subcommands:");
                println!("  aether-evolve snapshot       — current metrics JSON");
                println!("  aether-evolve diagnose       — prioritized issues JSON");
                println!("  aether-evolve peer-review    — institutional peer review");
                println!("  aether-evolve execute-plan   — apply a plan JSON file");
                println!("  aether-evolve loop           — autonomous evolution (TARGET: 100/100)");
                Ok(())
            } else {
                cmd_loop(&config, false).await
            }
        }
    }
}

// ─── SNAPSHOT ───────────────────────────────────────────────────────────

async fn cmd_snapshot(config: &EvolveConfig) -> Result<()> {
    let client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;

    let metrics = client.snapshot().await?;
    println!("{}", serde_json::to_string_pretty(&metrics)?);
    Ok(())
}

// ─── DIAGNOSE ───────────────────────────────────────────────────────────

async fn cmd_diagnose(config: &EvolveConfig) -> Result<()> {
    let client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;

    let metrics = client.snapshot().await?;

    if config.claude.enabled {
        let diagnose = DiagnoseAgent::new_without_llm();
        let diagnosis = diagnose.diagnose(&metrics).await?;
        println!("{}", serde_json::to_string_pretty(&diagnosis)?);
    } else {
        let backend = build_llm_backend(config)?;
        let prompts = PromptManager::with_defaults()?;
        let diagnose = DiagnoseAgent::new(backend, prompts, config.ollama.primary_model.clone());
        let diagnosis = diagnose.diagnose(&metrics).await?;
        println!("{}", serde_json::to_string_pretty(&diagnosis)?);
    }

    Ok(())
}

// ─── PEER REVIEW ────────────────────────────────────────────────────────

async fn cmd_peer_review(config: &EvolveConfig) -> Result<()> {
    let client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;

    let metrics = client.snapshot().await?;
    let backend = build_llm_backend(config)?;
    let prompts = PromptManager::with_defaults()?;
    let reviewer = PeerReviewAgent::new(backend, prompts, config.ollama.primary_model.clone());
    let report = reviewer.review(0, &metrics).await?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

// ─── EXECUTE PLAN ───────────────────────────────────────────────────────

async fn cmd_execute_plan(config: &EvolveConfig, plan_path: &PathBuf) -> Result<()> {
    let plan_json = std::fs::read_to_string(plan_path)
        .with_context(|| format!("Failed to read plan file: {}", plan_path.display()))?;
    let plan: EvolvePlan = serde_json::from_str(&plan_json)
        .with_context(|| "Failed to parse plan JSON")?;

    info!(
        intervention = ?plan.intervention_type,
        diffs = plan.diffs.len(),
        seeds = plan.seeds.len(),
        hypothesis = %plan.hypothesis,
        "Executing plan"
    );

    let aether_client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;

    let code_patcher = CodePatcher::new("/root/Qubitcoin");

    let seeder_client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;
    let seeder = KnowledgeSeederImpl::new(seeder_client, config.aether.admin_key.clone());
    let safety = SafetyGovernor::new(config.clone());

    let execute_agent = ExecuteAgent::new(aether_client, code_patcher, seeder, safety);

    let result = execute_agent.execute(0, &plan).await?;

    let output = serde_json::json!({
        "success": result.success,
        "details": result.details,
        "branch": result.branch_name,
        "pre_metrics": {
            "phi": result.pre_metrics.phi.hms_phi,
            "nodes": result.pre_metrics.total_nodes,
            "gates": result.pre_metrics.gates_passed,
        },
        "post_metrics": {
            "phi": result.post_metrics.phi.hms_phi,
            "nodes": result.post_metrics.total_nodes,
            "gates": result.post_metrics.gates_passed,
        },
        "delta_phi": result.post_metrics.phi.hms_phi - result.pre_metrics.phi.hms_phi,
        "delta_nodes": result.post_metrics.total_nodes as i64 - result.pre_metrics.total_nodes as i64,
        "delta_gates": result.post_metrics.gates_passed as i32 - result.pre_metrics.gates_passed as i32,
    });

    println!("{}", serde_json::to_string_pretty(&output)?);

    let audit = AuditLog::new(&config.general.data_dir)?;
    audit.record(0, "execute-plan", &result.details, result.success)?;

    Ok(())
}

// ─── AUTONOMOUS LOOP ─────────────────────────────────────────────────────
//
// DIRECTIVE: DO NOT STOP UNTIL PEER REVIEW SCORE = 100/100
//
// Strategy:
// 1. Every PEER_REVIEW_INTERVAL steps, run institutional peer review
// 2. Use peer review to generate targeted diagnosis items (weakest-first)
// 3. Alternate between peer-review-driven and standard diagnosis
// 4. Always prefer CodeChange interventions over KnowledgeSeed/ApiCall
// 5. Track progress toward 100/100 — log trajectory

async fn cmd_loop(config: &EvolveConfig, single_step: bool) -> Result<()> {
    if config.claude.enabled {
        warn!("Running autonomous loop with claude.enabled=true — Ollama LLM calls may be slow.");
    }

    info!(
        "╔══════════════════════════════════════════════════════════════╗"
    );
    info!(
        "║  AETHER EVOLVE — AUTONOMOUS AGI EVOLUTION ENGINE            ║"
    );
    info!(
        "║  DIRECTIVE: DO NOT STOP UNTIL PEER REVIEW = 100/100        ║"
    );
    info!(
        "║  TARGET: Institutional-Grade AGI (S+ Rating)                ║"
    );
    info!(
        "╚══════════════════════════════════════════════════════════════╝"
    );

    info!(
        name = %config.general.name,
        data_dir = %config.general.data_dir.display(),
        aether_url = %config.aether.base_url,
        ollama_url = %config.ollama.base_url,
        "Starting Aether-Evolve loop"
    );

    let aether_client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;

    let llm_primary = build_llm_backend(config)?;
    let llm_fast = build_llm_backend(config)?;
    let llm_analyze = build_llm_backend(config)?;
    let llm_review = build_llm_backend(config)?;

    let prompts = PromptManager::with_defaults()?;
    let prompts2 = PromptManager::with_defaults()?;
    let prompts3 = PromptManager::with_defaults()?;
    let prompts4 = PromptManager::with_defaults()?;

    let audit = AuditLog::new(&config.general.data_dir)?;
    let mut db = ExperimentDb::open(&config.general.data_dir)?;

    let cognition_dir = config.general.data_dir.parent()
        .unwrap_or(&config.general.data_dir)
        .join("cognition");
    let cognition = CognitionStore::load(&cognition_dir).unwrap_or_else(|e| {
        warn!("Cognition store failed to load: {e}, starting empty");
        CognitionStore::load(std::path::Path::new("/nonexistent")).unwrap()
    });

    // Create agents
    let diagnose_agent = DiagnoseAgent::new(llm_primary, prompts, config.ollama.primary_model.clone());
    let research_agent = ResearchAgent::new(
        llm_fast, prompts2,
        config.ollama.primary_model.clone(),
        config.ollama.fast_model.clone(),
        "/root/Qubitcoin".into(),
    );
    let execute_agent_client = AetherClient::new(
        &config.aether.base_url, config.aether.timeout_secs, config.aether.max_retries,
    )?;
    let execute_seeder_client = AetherClient::new(
        &config.aether.base_url, config.aether.timeout_secs, config.aether.max_retries,
    )?;
    let execute_seeder = KnowledgeSeederImpl::new(execute_seeder_client, config.aether.admin_key.clone());
    let execute_safety = SafetyGovernor::new(config.clone());
    let execute_patcher = CodePatcher::new("/root/Qubitcoin");
    let execute_agent = ExecuteAgent::new(execute_agent_client, execute_patcher, execute_seeder, execute_safety);
    let analyze_agent = AnalyzeAgent::new(llm_analyze, prompts3, config.ollama.fast_model.clone());
    let peer_review_agent = PeerReviewAgent::new(llm_review, prompts4, config.ollama.primary_model.clone());

    // Check health with retry
    let max_health_retries = 30;
    let mut healthy = false;
    for attempt in 1..=max_health_retries {
        match aether_client.health().await {
            Ok(true) => {
                info!("Aether Tree API is healthy (attempt {})", attempt);
                healthy = true;
                break;
            }
            Ok(false) | Err(_) => {
                warn!(
                    "Aether Tree API not reachable (attempt {}/{}), retrying in 10s...",
                    attempt, max_health_retries
                );
                tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
            }
        }
    }
    if !healthy {
        error!("Aether Tree API is not reachable at {} after {} attempts", config.aether.base_url, max_health_retries);
        anyhow::bail!("Cannot reach Aether Tree API");
    }

    // Load or init pipeline state
    let state_path = config.general.data_dir.join("pipeline_state.json");
    let mut state = if state_path.exists() {
        let content = std::fs::read_to_string(&state_path)?;
        serde_json::from_str::<PipelineState>(&content).unwrap_or_default()
    } else {
        PipelineState::default()
    };

    info!(
        step = state.current_step,
        phase = ?state.current_phase,
        experiments = state.total_experiments,
        best_score = state.best_score,
        "Pipeline state loaded"
    );

    // ─── LOAD CLAUDE'S EXTERNAL PEER REVIEW (PRIMARY SOURCE) ────────
    // Claude (Opus 4.6) writes institutional-grade reviews to master_audit.json.
    // This is the PRIMARY diagnosis source — much higher quality than Ollama reviews.
    let claude_review_path = config.general.data_dir.join("reviews/master_audit.json");
    let mut claude_review_items: Vec<aether_evolve_core::DiagnosisItem> = Vec::new();
    let mut claude_review_score: f64 = 0.0;

    if claude_review_path.exists() {
        match load_claude_review(&claude_review_path) {
            Ok((score, grade, items)) => {
                info!(
                    "╔══════════════════════════════════════════════════════════╗"
                );
                info!(
                    "║  CLAUDE MASTER AUDIT: {:.1}/100 — {}", score, grade
                );
                info!(
                    "║  {} prioritized diagnosis items from expert panel", items.len()
                );
                info!(
                    "╚══════════════════════════════════════════════════════════╝"
                );
                claude_review_score = score;
                claude_review_items = items;
            }
            Err(e) => warn!("Failed to load Claude review: {e}"),
        }
    } else {
        warn!("No Claude master audit at {}", claude_review_path.display());
    }

    // Also run Ollama's quick review for tracking
    let initial_metrics = aether_client.snapshot().await?;
    let mut last_review = match peer_review_agent.review(state.current_step, &initial_metrics).await {
        Ok(r) => {
            save_review(&config.general.data_dir, &r)?;
            audit.record(state.current_step, "peer-review",
                &format!("Ollama: {:.1}/100 | Claude: {:.1}/100", r.total, claude_review_score), true)?;
            info!("Ollama review: {:.1}/100 | Claude audit: {:.1}/100", r.total, claude_review_score);
            Some(r)
        }
        Err(e) => {
            warn!("Initial peer review failed: {e}");
            None
        }
    };

    // ─── EVOLUTION LOOP ─────────────────────────────────────────────
    let mut last_category = String::new();
    let mut consecutive_zero_scores: u32 = 0;
    let mut peer_review_items: Vec<aether_evolve_core::DiagnosisItem> = Vec::new();

    loop {
        state.current_step += 1;
        let step = state.current_step;
        state.last_step_at = chrono::Utc::now();

        // Check if we've reached the target
        if let Some(ref review) = last_review {
            if review.total >= TARGET_SCORE {
                info!(
                    "╔══════════════════════════════════════════════════════════╗"
                );
                info!(
                    "║  TARGET REACHED: {:.1}/100 — {}",
                    review.total, review.grade
                );
                info!(
                    "║  TRUE AGI ACHIEVED. EVOLUTION COMPLETE.                  ║"
                );
                info!(
                    "╚══════════════════════════════════════════════════════════╝"
                );
                break;
            }
        }

        info!(step, phase = ?state.current_phase, "═══ Evolution Step ═══");

        // 1. SNAPSHOT
        let metrics = match aether_client.snapshot().await {
            Ok(m) => m,
            Err(e) => {
                error!("Failed to snapshot metrics: {e}");
                tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                continue;
            }
        };

        info!(
            phi = metrics.phi.hms_phi,
            phi_micro = metrics.phi.phi_micro,
            phi_meso = metrics.phi.phi_meso,
            phi_macro = metrics.phi.phi_macro,
            nodes = metrics.total_nodes,
            gates = format!("{}/{}", metrics.gates_passed, metrics.gates_total),
            "Current state"
        );

        // 2. PEER REVIEW (every N steps)
        if step % PEER_REVIEW_INTERVAL == 0 {
            match peer_review_agent.review(step, &metrics).await {
                Ok(review) => {
                    save_review(&config.general.data_dir, &review)?;
                    audit.record(step, "peer-review",
                        &format!("Score: {:.1}/100 ({})", review.total, review.grade), true)?;

                    info!(
                        "── Peer Review #{}: {:.1}/100 ({}) ──",
                        step, review.total, review.grade
                    );
                    for w in &review.top_weaknesses {
                        info!("  Weakness: {w}");
                    }
                    for r in &review.recommendations {
                        info!("  Recommendation: {r}");
                    }

                    // Generate diagnosis items from peer review
                    peer_review_items = peer_review_agent.review_to_diagnosis(&review);
                    last_review = Some(review);
                }
                Err(e) => {
                    warn!("Peer review failed: {e}");
                }
            }
        }

        // 3. DIAGNOSE — Claude review items FIRST, then Ollama peer review, then standard diagnosis
        // Re-read Claude's review file each cycle (it may be updated externally)
        if claude_review_path.exists() {
            if let Ok((score, _grade, items)) = load_claude_review(&claude_review_path) {
                if (score - claude_review_score).abs() > 0.1 {
                    info!("Claude review updated: {:.1}/100 -> {:.1}/100", claude_review_score, score);
                    claude_review_score = score;
                }
                claude_review_items = items;
            }
        }

        let diagnosis = match diagnose_agent.diagnose(&metrics).await {
            Ok(d) => d,
            Err(e) => {
                error!("Diagnosis failed: {e}");
                tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                continue;
            }
        };

        // Merge: Claude items (highest priority) + Ollama peer review + standard diagnosis
        let mut all_items = claude_review_items.clone();
        // Add Ollama peer review items that don't overlap with Claude
        for item in &peer_review_items {
            let dominated = all_items.iter().any(|pr| {
                pr.target_files.iter().any(|f| item.target_files.contains(f))
            });
            if !dominated {
                all_items.push(item.clone());
            }
        }
        // Add standard diagnosis items that don't overlap
        for item in &diagnosis.items {
            let dominated = all_items.iter().any(|pr| {
                pr.target_files.iter().any(|f| item.target_files.contains(f))
                    && (pr.priority as u32) <= (item.priority as u32)
            });
            if !dominated {
                all_items.push(item.clone());
            }
        }

        // Sort by priority
        all_items.sort_by_key(|i| i.priority);

        if all_items.is_empty() {
            info!("No weaknesses found — system is healthy!");
            if single_step { break; }
            tokio::time::sleep(tokio::time::Duration::from_secs(config.pipeline.step_interval_secs)).await;
            continue;
        }

        // Select item with diversity + stuck detection
        let selected_idx = select_diagnosis_item(
            &all_items,
            &last_category,
            consecutive_zero_scores,
        );

        let top_item = &all_items[selected_idx];
        info!(
            priority = ?top_item.priority,
            category = %top_item.category,
            intervention = ?top_item.recommended_intervention,
            selected_idx,
            description = %top_item.description,
            "Top diagnosis"
        );
        last_category = top_item.category.clone();
        audit.record(step, "diagnose", &top_item.description, true)?;

        // 4. RESEARCH
        let plan = match research_agent.research(top_item, &cognition).await {
            Ok(p) => p,
            Err(e) => {
                error!("Research failed: {e}");
                audit.record(step, "research", &format!("Failed: {e}"), false)?;
                tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                continue;
            }
        };

        info!(
            intervention = ?plan.intervention_type,
            diffs = plan.diffs.len(),
            seeds = plan.seeds.len(),
            "Research plan ready"
        );
        audit.record(step, "research", &plan.hypothesis, true)?;

        // 5. EXECUTE
        let execution = match execute_agent.execute(step, &plan).await {
            Ok(r) => r,
            Err(e) => {
                error!("Execution failed: {e}");
                audit.record(step, "execute", &format!("Failed: {e}"), false)?;
                tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                continue;
            }
        };

        info!(
            success = execution.success,
            details = %execution.details,
            "Execution complete"
        );
        audit.record(step, "execute", &execution.details, execution.success)?;

        // 6. ANALYZE
        let analysis = match analyze_agent.analyze(step, &plan, &execution).await {
            Ok(a) => a,
            Err(e) => {
                error!("Analysis failed: {e}");
                audit.record(step, "analyze", &format!("Failed: {e}"), false)?;
                continue;
            }
        };

        let exp_id = db.insert(analysis.experiment)?;
        let exp_score = db.get(exp_id).map(|e| e.score).unwrap_or(0.0);
        info!(
            exp_id,
            score = exp_score,
            lesson = %analysis.lesson,
            "Experiment recorded"
        );
        audit.record(step, "analyze", &analysis.lesson, true)?;

        // Track consecutive zero scores for stuck detection
        if exp_score < 0.01 {
            consecutive_zero_scores += 1;
        } else {
            consecutive_zero_scores = 0;
        }

        // Update state
        state.total_experiments += 1;
        if exp_score > state.best_score {
            state.best_score = exp_score;
            state.best_experiment_id = Some(exp_id);
        }

        state.current_phase = determine_phase(&metrics);

        // Save state periodically
        if state.current_step % config.pipeline.save_interval == 0 {
            let state_json = serde_json::to_string_pretty(&state)?;
            std::fs::write(&state_path, state_json)?;
            info!("Pipeline state saved");
        }

        // Log progress toward target
        if let Some(ref review) = last_review {
            info!(
                "Progress: {:.1}/100 -> target {:.0}/100 | Step {} | Best experiment score: {:.1}",
                review.total, TARGET_SCORE, step, state.best_score
            );
        }

        if single_step {
            info!("Single step mode — exiting");
            break;
        }

        tokio::time::sleep(tokio::time::Duration::from_secs(config.pipeline.step_interval_secs)).await;
    }

    let state_json = serde_json::to_string_pretty(&state)?;
    std::fs::write(&state_path, state_json)?;
    info!("Aether-Evolve shutdown complete");

    Ok(())
}

/// Select the best diagnosis item with diversity and stuck detection.
fn select_diagnosis_item(
    items: &[aether_evolve_core::DiagnosisItem],
    last_category: &str,
    consecutive_zeros: u32,
) -> usize {
    if items.is_empty() {
        return 0;
    }

    if consecutive_zeros >= 2 {
        // After 2 zero-score experiments, force rotation to a DIFFERENT category
        info!(
            consecutive_zeros,
            "Stuck detector: rotating to different category (was: {})", last_category
        );
        // Pick the first item from a different category, preferring CodeChange
        items.iter().position(|item| {
            item.category != last_category
                && item.recommended_intervention == InterventionType::CodeChange
        }).unwrap_or_else(|| {
            items.iter().position(|item| item.category != last_category)
                .unwrap_or_else(|| {
                    // All same category — just rotate to a different index
                    if items.len() > 1 { 1 } else { 0 }
                })
        })
    } else if !last_category.is_empty() && items[0].category == last_category && items.len() > 1 {
        items.iter().position(|item| {
            item.category != last_category
                && item.recommended_intervention == InterventionType::CodeChange
        }).unwrap_or_else(|| {
            items.iter().position(|item| item.category != last_category).unwrap_or(0)
        })
    } else {
        0
    }
}

/// Save a peer review report to disk.
fn save_review(data_dir: &std::path::Path, report: &PeerReviewReport) -> Result<()> {
    let reviews_dir = data_dir.join("reviews");
    std::fs::create_dir_all(&reviews_dir)?;
    let filename = format!("review_step_{}.json", report.step);
    let json = serde_json::to_string_pretty(report)?;
    std::fs::write(reviews_dir.join(filename), json)?;
    std::fs::write(reviews_dir.join("latest.json"), serde_json::to_string_pretty(report)?)?;
    Ok(())
}

/// Build the appropriate LLM backend based on config.
fn build_llm_backend(config: &EvolveConfig) -> Result<LlmBackend> {
    if config.claude.enabled {
        let api_key = if !config.claude.api_key.is_empty() {
            config.claude.api_key.clone()
        } else {
            std::env::var("ANTHROPIC_API_KEY").unwrap_or_default()
        };

        if !api_key.is_empty() {
            info!(model = %config.claude.model, "Using Claude API backend");
            let client = ClaudeClient::new(&api_key, &config.claude.model, config.ollama.timeout_secs)?;
            return Ok(LlmBackend::Claude(client));
        }

        warn!("claude.enabled=true but no API key found. Falling back to Ollama.");
    }

    info!(base_url = %config.ollama.base_url, "Using Ollama backend");
    let client = OllamaClient::new(&config.ollama.base_url, config.ollama.timeout_secs)?;
    Ok(LlmBackend::Ollama(client))
}

/// Load Claude's external peer review file and convert to diagnosis items.
/// Claude writes master_audit.json with a 10-expert panel review.
/// This function extracts the top issues and converts them into DiagnosisItems
/// that the evolution loop can act on.
fn load_claude_review(
    path: &std::path::Path,
) -> Result<(f64, String, Vec<aether_evolve_core::DiagnosisItem>)> {
    let content = std::fs::read_to_string(path)
        .with_context(|| format!("Reading Claude review: {}", path.display()))?;
    let review: serde_json::Value = serde_json::from_str(&content)
        .with_context(|| "Parsing Claude review JSON")?;

    let score = review["overall_score"].as_f64().unwrap_or(0.0);
    let grade = review["grade"].as_str().unwrap_or("Unknown").to_string();

    let mut items = Vec::new();

    // Extract from top_10_critical_issues
    if let Some(issues) = review["top_10_critical_issues"].as_array() {
        for issue in issues {
            let rank = issue["rank"].as_u64().unwrap_or(99);
            let description = issue["issue"].as_str().unwrap_or("Unknown issue");
            let severity = issue["severity"].as_str().unwrap_or("MEDIUM");
            let fix = issue["fix_status"].as_str()
                .or_else(|| issue["fix"].as_str())
                .unwrap_or("Needs investigation");
            let root_cause = issue["root_cause"].as_str().unwrap_or(description);

            let priority = match severity {
                "CRITICAL" => aether_evolve_core::DiagnosisPriority::P0PhiZero,
                "HIGH" => aether_evolve_core::DiagnosisPriority::P1GateBlocker,
                "MEDIUM" => aether_evolve_core::DiagnosisPriority::P2SubsystemDead,
                _ => aether_evolve_core::DiagnosisPriority::P3QualityGap,
            };

            // Skip issues already fixed
            let fix_lower = fix.to_lowercase();
            if fix_lower.contains("applied") || fix_lower.contains("resolved") {
                info!("Claude issue #{}: ALREADY FIXED — {}", rank, description);
                continue;
            }

            // Map issues to target files
            let target_files = match rank {
                1 => vec!["src/qubitcoin/aether/proof_of_thought.py".into()],
                2 => vec!["src/qubitcoin/aether/phi_calculator.py".into(), "src/qubitcoin/aether/iit_approximator.py".into()],
                3 => vec!["src/qubitcoin/aether/knowledge_graph.py".into(), "src/qubitcoin/aether/reasoning.py".into()],
                4 => vec!["src/qubitcoin/aether/temporal_reasoner.py".into(), "src/qubitcoin/aether/proof_of_thought.py".into()],
                5 => vec!["src/qubitcoin/aether/proof_of_thought.py".into()],
                6 => vec!["src/qubitcoin/aether/reasoning.py".into()],
                7 => vec!["src/qubitcoin/aether/proof_of_thought.py".into()],
                8 => vec!["src/qubitcoin/aether/metacognition.py".into()],
                9 => vec!["src/qubitcoin/aether/proof_of_thought.py".into()],
                10 => vec!["src/qubitcoin/aether/knowledge_graph.py".into()],
                _ => vec!["src/qubitcoin/aether/proof_of_thought.py".into()],
            };

            items.push(aether_evolve_core::DiagnosisItem {
                priority,
                category: format!("claude_audit_issue_{}", rank),
                description: format!("Claude Audit #{}: {}", rank, description),
                root_cause: root_cause.to_string(),
                recommended_intervention: InterventionType::CodeChange,
                target_files,
                expected_improvement: fix.to_string(),
            });
        }
    }

    // Also extract from dimension scores — attack weakest dimensions
    if let Some(dims) = review["dimensions"].as_object() {
        let mut dim_scores: Vec<(&str, f64)> = dims.iter()
            .filter_map(|(name, dim)| {
                dim["score"].as_f64().map(|s| (name.as_str(), s))
            })
            .collect();
        dim_scores.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));

        for (dim_name, dim_score) in dim_scores.iter().take(5) {
            if *dim_score >= 8.0 { continue; }
            let fix = dims[*dim_name]["critical_fix"].as_str().unwrap_or("Needs improvement");
            let target = match *dim_name {
                "reasoning_depth" => vec!["src/qubitcoin/aether/reasoning.py".into(), "src/qubitcoin/aether/proof_of_thought.py".into()],
                "self_improvement" => vec!["src/qubitcoin/aether/self_improvement.py".into()],
                "calibration" => vec!["src/qubitcoin/aether/metacognition.py".into()],
                "adversarial_robustness" => vec!["src/qubitcoin/aether/debate.py".into()],
                "integrated_information" => vec!["src/qubitcoin/aether/phi_calculator.py".into(), "src/qubitcoin/aether/iit_approximator.py".into()],
                "autonomous_curiosity" => vec!["src/qubitcoin/aether/curiosity_engine.py".into(), "src/qubitcoin/aether/proof_of_thought.py".into()],
                "novel_synthesis" => vec!["src/qubitcoin/aether/concept_formation.py".into()],
                "knowledge_quality" => vec!["src/qubitcoin/aether/knowledge_graph.py".into()],
                "system_reliability" => vec!["src/qubitcoin/aether/proof_of_thought.py".into()],
                "scale_readiness" => vec!["src/qubitcoin/aether/knowledge_graph.py".into()],
                _ => vec!["src/qubitcoin/aether/proof_of_thought.py".into()],
            };

            let priority = if *dim_score < 1.0 {
                aether_evolve_core::DiagnosisPriority::P0PhiZero
            } else if *dim_score < 3.0 {
                aether_evolve_core::DiagnosisPriority::P1GateBlocker
            } else if *dim_score < 5.0 {
                aether_evolve_core::DiagnosisPriority::P2SubsystemDead
            } else {
                aether_evolve_core::DiagnosisPriority::P3QualityGap
            };

            items.push(aether_evolve_core::DiagnosisItem {
                priority,
                category: format!("claude_dimension_{}", dim_name),
                description: format!("Claude Dimension: {} = {:.1}/10", dim_name, dim_score),
                root_cause: fix.to_string(),
                recommended_intervention: InterventionType::CodeChange,
                target_files: target,
                expected_improvement: format!("Improve {} from {:.1} toward 10.0", dim_name, dim_score),
            });
        }
    }

    info!(
        "Claude review loaded: {:.1}/100 ({}) — {} actionable items",
        score, grade, items.len()
    );

    Ok((score, grade, items))
}

fn determine_phase(metrics: &aether_evolve_core::AetherMetrics) -> PipelinePhase {
    if metrics.phi.phi_meso == 0.0 || metrics.phi.phi_micro == 0.0 {
        PipelinePhase::FixZeros
    } else if metrics.total_nodes < 150_000 {
        PipelinePhase::KnowledgeExplosion
    } else if metrics.gates_passed < 9 {
        PipelinePhase::CognitiveIntegration
    } else if metrics.phi.hms_phi < 1.0 {
        PipelinePhase::SelfEvolution
    } else {
        PipelinePhase::NovelSynthesis
    }
}
