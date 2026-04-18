use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvolveConfig {
    pub general: GeneralConfig,
    pub aether: AetherConfig,
    pub ollama: OllamaConfig,
    #[serde(default)]
    pub claude: ClaudeConfig,
    pub pipeline: PipelineConfig,
    pub sampling: SamplingConfig,
    pub safety: SafetyConfig,
}

/// When claude mode is enabled, the binary acts as a CLI tool that Claude Code
/// orchestrates. LLM calls are skipped — Claude provides the intelligence,
/// the binary provides the infrastructure (metrics, git, tests, seeding).
///
/// Alternatively, when `enabled = true` AND `api_key` is set, the autonomous
/// loop uses the Anthropic Messages API instead of Ollama.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaudeConfig {
    /// When true, subcommands (snapshot, diagnose, execute-plan) are the primary interface.
    /// When false, the autonomous loop uses Ollama for all reasoning.
    pub enabled: bool,

    /// Anthropic API key. If empty, falls back to ANTHROPIC_API_KEY env var.
    #[serde(default)]
    pub api_key: String,

    /// Claude model to use (default: claude-sonnet-4-20250514).
    #[serde(default = "default_claude_model")]
    pub model: String,
}

fn default_claude_model() -> String {
    "claude-sonnet-4-20250514".to_string()
}

impl Default for ClaudeConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            api_key: String::new(),
            model: default_claude_model(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeneralConfig {
    pub name: String,
    pub log_level: String,
    pub data_dir: PathBuf,
    pub aether_source: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AetherConfig {
    pub base_url: String,
    pub timeout_secs: u64,
    pub max_retries: u32,
    #[serde(default)]
    pub admin_key: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OllamaConfig {
    pub base_url: String,
    pub primary_model: String,
    pub fast_model: String,
    pub bulk_model: String,
    pub timeout_secs: u64,
    pub max_concurrent: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineConfig {
    pub max_steps: u64,
    pub step_interval_secs: u64,
    pub parallel_workers: usize,
    pub save_interval: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SamplingConfig {
    pub algorithm: String,
    pub sample_n: usize,
    pub exploration_weight: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyConfig {
    pub max_api_calls_per_minute: u32,
    pub max_code_changes_per_hour: u32,
    pub max_seeds_per_step: u32,
    pub min_test_pass_rate: f64,
    pub max_memory_mb: u64,
    pub auto_rollback_threshold: f64,
    pub forbidden_files: Vec<String>,
}

impl Default for EvolveConfig {
    fn default() -> Self {
        Self {
            general: GeneralConfig {
                name: "aether-evolve".into(),
                log_level: "info".into(),
                data_dir: PathBuf::from("/root/aether-evolve/data"),
                aether_source: PathBuf::from("/root/Qubitcoin/src/qubitcoin/aether"),
            },
            aether: AetherConfig {
                base_url: "http://localhost:5000".into(),
                timeout_secs: 30,
                max_retries: 3,
                admin_key: String::new(),
            },
            ollama: OllamaConfig {
                base_url: "http://localhost:11434".into(),
                primary_model: "qwen2.5:7b".into(),
                fast_model: "qwen2.5:3b".into(),
                bulk_model: "qwen2.5:0.5b".into(),
                timeout_secs: 120,
                max_concurrent: 2,
            },
            claude: ClaudeConfig::default(),
            pipeline: PipelineConfig {
                max_steps: 0,
                step_interval_secs: 60,
                parallel_workers: 4,
                save_interval: 10,
            },
            sampling: SamplingConfig {
                algorithm: "ucb1".into(),
                sample_n: 3,
                exploration_weight: 1.414,
            },
            safety: SafetyConfig {
                max_api_calls_per_minute: 60,
                max_code_changes_per_hour: 5,
                max_seeds_per_step: 1000,
                min_test_pass_rate: 0.95,
                max_memory_mb: 2048,
                auto_rollback_threshold: -0.05,
                forbidden_files: vec![
                    ".env".into(),
                    "secure_key.env".into(),
                    "genesis.py".into(),
                ],
            },
        }
    }
}

impl EvolveConfig {
    pub fn from_file(path: &std::path::Path) -> anyhow::Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: Self = toml::from_str(&content)?;
        Ok(config)
    }
}
