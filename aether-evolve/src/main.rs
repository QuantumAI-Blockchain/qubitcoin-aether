use aether_evolve_agents::{AnalyzeAgent, DiagnoseAgent, ExecuteAgent, ResearchAgent};
use aether_evolve_api::{AetherClient, CodePatcher, KnowledgeSeederImpl};
use aether_evolve_core::{EvolvePlan, EvolveConfig, PipelinePhase, PipelineState};
use aether_evolve_llm::{ClaudeClient, LlmBackend, OllamaClient, PromptManager};
use aether_evolve_memory::{CognitionStore, ExperimentDb};
use aether_evolve_safety::{AuditLog, SafetyGovernor};
use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use tracing::{error, info, warn};

#[derive(Parser)]
#[command(name = "aether-evolve", about = "Autonomous Aether Tree evolution agent")]
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

    /// Execute a plan from a JSON file (diffs, seeds, API calls)
    /// Claude writes the plan, this command applies it with safety checks
    ExecutePlan {
        /// Path to plan JSON file
        #[arg(long)]
        plan: PathBuf,
    },

    /// Run the full autonomous evolution loop (uses Ollama LLM)
    /// This is the original mode — works without Claude
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
        Some(Command::ExecutePlan { plan }) => cmd_execute_plan(&config, &plan).await,
        Some(Command::Loop { single_step }) => cmd_loop(&config, single_step).await,
        None => {
            // Default behavior: if claude mode is on, show help; otherwise run loop
            if config.claude.enabled {
                println!("Claude mode is enabled. Use subcommands:");
                println!("  aether-evolve snapshot       — current metrics JSON");
                println!("  aether-evolve diagnose       — prioritized issues JSON");
                println!("  aether-evolve execute-plan   — apply a plan JSON file");
                println!("  aether-evolve loop           — autonomous Ollama loop");
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

    // In claude mode, always use rule-based diagnosis only (fast, deterministic)
    // In ollama mode, optionally enhance with LLM
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

    // Use step 0 for manual executions — the audit log differentiates
    let result = execute_agent.execute(0, &plan).await?;

    // Output result as JSON
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

    // Record experiment
    let audit = AuditLog::new(&config.general.data_dir)?;
    audit.record(0, "execute-plan", &result.details, result.success)?;

    Ok(())
}

// ─── AUTONOMOUS LOOP (OLLAMA MODE) ─────────────────────────────────────

async fn cmd_loop(config: &EvolveConfig, single_step: bool) -> Result<()> {
    if config.claude.enabled {
        warn!("Running autonomous loop with claude.enabled=true — Ollama LLM calls may be slow.");
        warn!("Consider using subcommands (snapshot, diagnose, execute-plan) instead.");
    }

    info!(
        name = %config.general.name,
        data_dir = %config.general.data_dir.display(),
        aether_url = %config.aether.base_url,
        ollama_url = %config.ollama.base_url,
        claude_mode = config.claude.enabled,
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

    let prompts = PromptManager::with_defaults()?;
    let prompts2 = PromptManager::with_defaults()?;
    let prompts3 = PromptManager::with_defaults()?;

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

    // Check health with retry — node may be processing block backlog
    let max_health_retries = 30; // 30 x 10s = 5 minutes max wait
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

    // ─── EVOLUTION LOOP ─────────────────────────────────────────────
    loop {
        state.current_step += 1;
        let step = state.current_step;
        state.last_step_at = chrono::Utc::now();

        info!(step, phase = ?state.current_phase, "═══ Evolution Step ═══");

        // 1. DIAGNOSE
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

        let diagnosis = match diagnose_agent.diagnose(&metrics).await {
            Ok(d) => d,
            Err(e) => {
                error!("Diagnosis failed: {e}");
                tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                continue;
            }
        };

        if diagnosis.items.is_empty() {
            info!("No weaknesses found — system is healthy!");
            if single_step { break; }
            tokio::time::sleep(tokio::time::Duration::from_secs(config.pipeline.step_interval_secs)).await;
            continue;
        }

        let top_item = &diagnosis.items[0];
        info!(
            priority = ?top_item.priority,
            category = %top_item.category,
            description = %top_item.description,
            "Top diagnosis"
        );
        audit.record(step, "diagnose", &top_item.description, true)?;

        // 2. RESEARCH
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

        // 3. EXECUTE
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

        // 4. ANALYZE
        let analysis = match analyze_agent.analyze(step, &plan, &execution).await {
            Ok(a) => a,
            Err(e) => {
                error!("Analysis failed: {e}");
                audit.record(step, "analyze", &format!("Failed: {e}"), false)?;
                continue;
            }
        };

        let exp_id = db.insert(analysis.experiment)?;
        info!(
            exp_id,
            score = db.get(exp_id).map(|e| e.score).unwrap_or(0.0),
            lesson = %analysis.lesson,
            "Experiment recorded"
        );
        audit.record(step, "analyze", &analysis.lesson, true)?;

        // Update state
        state.total_experiments += 1;
        let exp_score = db.get(exp_id).map(|e| e.score).unwrap_or(0.0);
        if exp_score > state.best_score {
            state.best_score = exp_score;
            state.best_experiment_id = Some(exp_id);
        }

        state.current_phase = determine_phase(&metrics);

        if state.current_step % config.pipeline.save_interval == 0 {
            let state_json = serde_json::to_string_pretty(&state)?;
            std::fs::write(&state_path, state_json)?;
            info!("Pipeline state saved");
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

/// Build the appropriate LLM backend based on config.
/// If claude.enabled and an API key is available, use Claude. Otherwise use Ollama.
fn build_llm_backend(config: &EvolveConfig) -> Result<LlmBackend> {
    if config.claude.enabled {
        // Resolve API key: config field takes precedence, then env var
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

        // claude.enabled but no API key — fall back to Ollama
        warn!("claude.enabled=true but no API key found (ANTHROPIC_API_KEY / claude.api_key). Falling back to Ollama.");
    }

    info!(base_url = %config.ollama.base_url, "Using Ollama backend");
    let client = OllamaClient::new(&config.ollama.base_url, config.ollama.timeout_secs)?;
    Ok(LlmBackend::Ollama(client))
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
