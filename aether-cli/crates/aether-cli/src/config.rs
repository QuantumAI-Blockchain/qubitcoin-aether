use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
pub struct CliConfig {
    pub api_url: String,
    pub substrate_url: String,
    pub temperature: f32,
    pub max_tokens: usize,
    pub mining_threads: u32,
}

impl Default for CliConfig {
    fn default() -> Self {
        Self {
            api_url: "https://ai.qbc.network".into(),
            substrate_url: "https://rpc.qbc.network".into(),
            temperature: 0.7,
            max_tokens: 256,
            mining_threads: 1,
        }
    }
}

impl CliConfig {
    pub fn config_path() -> PathBuf {
        dirs::config_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("aether-cli")
            .join("config.toml")
    }

    pub fn load() -> Self {
        let path = Self::config_path();
        if path.exists() {
            if let Ok(data) = std::fs::read_to_string(&path) {
                if let Ok(config) = toml::from_str(&data) {
                    return config;
                }
            }
        }
        Self::default()
    }
}
