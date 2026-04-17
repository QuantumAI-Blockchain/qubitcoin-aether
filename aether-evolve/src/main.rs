use aether_evolve_agents::{AnalyzeAgent, DiagnoseAgent, ExecuteAgent, ResearchAgent};
use aether_evolve_api::{AetherClient, CodePatcher, KnowledgeSeederImpl};
use aether_evolve_core::{EvolveConfig, PipelinePhase, PipelineState};
use aether_evolve_llm::{OllamaClient, PromptManager};
use aether_evolve_memory::{CognitionStore, ExperimentDb};
use aether_evolve_safety::{AuditLog, SafetyGovernor};
use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use tracing::{error, info, warn};

#[derive(Parser)]
#[command(name = "aether-evolve", about = "Autonomous Aether Tree evolution agent")]
struct Cli {
    /// Path to config file
    #[arg(short, long, default_value = "config.toml")]
    config: PathBuf,

    /// Run a single step then exit (for testing)
    #[arg(long)]
    single_step: bool,

    /// Override data directory
    #[arg(long)]
    data_dir: Option<PathBuf>,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .with_target(true)
        .with_thread_ids(true)
        .init();

    let cli = Cli::parse();

    // Load config
    let mut config = if cli.config.exists() {
        EvolveConfig::from_file(&cli.config).context("Failed to load config")?
    } else {
        info!("No config file found, using defaults");
        EvolveConfig::default()
    };

    if let Some(data_dir) = cli.data_dir {
        config.general.data_dir = data_dir;
    }

    info!(
        name = %config.general.name,
        data_dir = %config.general.data_dir.display(),
        aether_url = %config.aether.base_url,
        ollama_url = %config.ollama.base_url,
        "Starting Aether-Evolve"
    );

    // Ensure data directory exists
    std::fs::create_dir_all(&config.general.data_dir)?;

    // Initialize components
    let aether_client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;

    let ollama_primary = OllamaClient::new(
        &config.ollama.base_url,
        config.ollama.timeout_secs,
    )?;

    let ollama_fast = OllamaClient::new(
        &config.ollama.base_url,
        config.ollama.timeout_secs,
    )?;

    let ollama_analyze = OllamaClient::new(
        &config.ollama.base_url,
        config.ollama.timeout_secs,
    )?;

    let prompts = PromptManager::with_defaults()?;
    let prompts2 = PromptManager::with_defaults()?;
    let prompts3 = PromptManager::with_defaults()?;

    let seeder_client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;
    let seeder = KnowledgeSeederImpl::new(seeder_client);

    let code_patcher = CodePatcher::new(
        config.general.aether_source
            .parent()
            .and_then(|p| p.parent())
            .and_then(|p| p.parent())
            .map(|p| p.to_str().unwrap_or("/root/Qubitcoin"))
            .unwrap_or("/root/Qubitcoin"),
    );

    let safety = SafetyGovernor::new(config.clone());
    let audit = AuditLog::new(&config.general.data_dir)?;
    let mut db = ExperimentDb::open(&config.general.data_dir)?;

    let cognition_dir = config.general.data_dir.parent()
        .unwrap_or(&config.general.data_dir)
        .join("cognition");
    let mut cognition = CognitionStore::load(&cognition_dir).unwrap_or_else(|e| {
        warn!("Cognition store failed to load: {e}, starting empty");
        CognitionStore::load(std::path::Path::new("/nonexistent")).unwrap()
    });

    // Create agents
    let diagnose_agent = DiagnoseAgent::new(
        ollama_primary,
        prompts,
        config.ollama.primary_model.clone(),
    );
    let research_agent = ResearchAgent::new(
        ollama_fast,
        prompts2,
        config.ollama.primary_model.clone(),
        config.ollama.fast_model.clone(),
        "/root/Qubitcoin".into(),
    );
    let execute_agent_client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;
    let execute_seeder_client = AetherClient::new(
        &config.aether.base_url,
        config.aether.timeout_secs,
        config.aether.max_retries,
    )?;
    let execute_seeder = KnowledgeSeederImpl::new(execute_seeder_client);
    let execute_safety = SafetyGovernor::new(config.clone());
    let execute_patcher = CodePatcher::new("/root/Qubitcoin");
    let execute_agent = ExecuteAgent::new(
        execute_agent_client,
        execute_patcher,
        execute_seeder,
        execute_safety,
    );
    let analyze_agent = AnalyzeAgent::new(
        ollama_analyze,
        prompts3,
        config.ollama.primary_model.clone(),
    );

    // Check health
    let aether_healthy = aether_client.health().await?;
    if !aether_healthy {
        error!("Aether Tree API is not reachable at {}", config.aether.base_url);
        anyhow::bail!("Cannot reach Aether Tree API");
    }
    info!("Aether Tree API is healthy");

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
            if cli.single_step {
                break;
            }
            tokio::time::sleep(tokio::time::Duration::from_secs(
                config.pipeline.step_interval_secs,
            )).await;
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

        // Phase transitions
        state.current_phase = determine_phase(&metrics);

        // Save state
        if state.current_step % config.pipeline.save_interval == 0 {
            let state_json = serde_json::to_string_pretty(&state)?;
            std::fs::write(&state_path, state_json)?;
            info!("Pipeline state saved");
        }

        if cli.single_step {
            info!("Single step mode — exiting");
            break;
        }

        // Wait between steps
        tokio::time::sleep(tokio::time::Duration::from_secs(
            config.pipeline.step_interval_secs,
        )).await;
    }

    // Final save
    let state_json = serde_json::to_string_pretty(&state)?;
    std::fs::write(&state_path, state_json)?;
    info!("Aether-Evolve shutdown complete");

    Ok(())
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
