use anyhow::{Context, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, info, warn};

// ─── Trait ────────────────────────────────────────────────────────────

/// Common interface for LLM backends (Ollama, Claude, etc.).
pub trait LlmClient: Send + Sync {
    /// Generate a completion given system + user prompts.
    fn generate(
        &self,
        model: &str,
        system: &str,
        user: &str,
        temperature: f32,
        max_tokens: i32,
    ) -> impl std::future::Future<Output = Result<String>> + Send;

    /// Check if the backend is reachable and the model is available.
    fn health(
        &self,
        model: &str,
    ) -> impl std::future::Future<Output = Result<bool>> + Send;
}

// ─── Ollama ───────────────────────────────────────────────────────────

pub struct OllamaClient {
    client: Client,
    base_url: String,
}

#[derive(Debug, Serialize)]
struct OllamaChatRequest {
    model: String,
    messages: Vec<ChatMessage>,
    stream: bool,
    options: Option<OllamaChatOptions>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Serialize)]
struct OllamaChatOptions {
    temperature: f32,
    num_predict: i32,
}

#[derive(Debug, Deserialize)]
struct OllamaChatResponse {
    message: ChatMessage,
}

impl OllamaClient {
    pub fn new(base_url: &str, timeout_secs: u64) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_secs))
            .build()
            .context("Failed to build Ollama HTTP client")?;

        Ok(Self {
            client,
            base_url: base_url.trim_end_matches('/').to_string(),
        })
    }
}

impl LlmClient for OllamaClient {
    async fn generate(
        &self,
        model: &str,
        system: &str,
        user: &str,
        temperature: f32,
        max_tokens: i32,
    ) -> Result<String> {
        let url = format!("{}/api/chat", self.base_url);

        let request = OllamaChatRequest {
            model: model.to_string(),
            messages: vec![
                ChatMessage {
                    role: "system".into(),
                    content: system.into(),
                },
                ChatMessage {
                    role: "user".into(),
                    content: user.into(),
                },
            ],
            stream: false,
            options: Some(OllamaChatOptions {
                temperature,
                num_predict: max_tokens,
            }),
        };

        debug!(model, "Sending request to Ollama");

        let resp = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .context("Ollama request failed")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            anyhow::bail!("Ollama error {status}: {body}");
        }

        let chat_resp: OllamaChatResponse =
            resp.json().await.context("Failed to parse Ollama response")?;
        debug!(
            model,
            len = chat_resp.message.content.len(),
            "Ollama response received"
        );

        Ok(chat_resp.message.content)
    }

    async fn health(&self, model: &str) -> Result<bool> {
        let url = format!("{}/api/tags", self.base_url);
        match self.client.get(&url).send().await {
            Ok(resp) => {
                if !resp.status().is_success() {
                    return Ok(false);
                }
                let data: serde_json::Value = resp.json().await.unwrap_or_default();
                let models = data["models"].as_array().unwrap_or(&Vec::new()).clone();
                let available = models.iter().any(|m| {
                    m["name"]
                        .as_str()
                        .map_or(false, |n| {
                            n.starts_with(model.split(':').next().unwrap_or(model))
                        })
                });
                if !available {
                    warn!(model, "Model not found in Ollama");
                }
                Ok(available)
            }
            Err(_) => Ok(false),
        }
    }
}

// ─── Claude (Anthropic) ──────────────────────────────────────────────

pub struct ClaudeClient {
    client: Client,
    api_key: String,
    default_model: String,
}

#[derive(Debug, Serialize)]
struct ClaudeRequest {
    model: String,
    max_tokens: i32,
    #[serde(skip_serializing_if = "String::is_empty")]
    system: String,
    messages: Vec<ClaudeMessage>,
    temperature: f32,
}

#[derive(Debug, Serialize, Deserialize)]
struct ClaudeMessage {
    role: String,
    content: String,
}

#[derive(Debug, Deserialize)]
struct ClaudeResponse {
    content: Vec<ClaudeContentBlock>,
}

#[derive(Debug, Deserialize)]
struct ClaudeContentBlock {
    #[serde(rename = "type")]
    block_type: String,
    text: Option<String>,
}

impl ClaudeClient {
    pub fn new(api_key: &str, model: &str, timeout_secs: u64) -> Result<Self> {
        if api_key.is_empty() {
            anyhow::bail!("Claude API key is empty — set ANTHROPIC_API_KEY or claude.api_key in config");
        }

        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_secs))
            .build()
            .context("Failed to build Claude HTTP client")?;

        info!(model, "Claude client initialized");

        Ok(Self {
            client,
            api_key: api_key.to_string(),
            default_model: model.to_string(),
        })
    }
}

impl LlmClient for ClaudeClient {
    async fn generate(
        &self,
        model: &str,
        system: &str,
        user: &str,
        temperature: f32,
        max_tokens: i32,
    ) -> Result<String> {
        let actual_model = if model.is_empty() {
            &self.default_model
        } else {
            model
        };

        let request = ClaudeRequest {
            model: actual_model.to_string(),
            max_tokens,
            system: system.to_string(),
            messages: vec![ClaudeMessage {
                role: "user".into(),
                content: user.into(),
            }],
            temperature,
        };

        debug!(model = actual_model, "Sending request to Claude API");

        let resp = self
            .client
            .post("https://api.anthropic.com/v1/messages")
            .header("x-api-key", &self.api_key)
            .header("anthropic-version", "2023-06-01")
            .header("content-type", "application/json")
            .json(&request)
            .send()
            .await
            .context("Claude API request failed")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            anyhow::bail!("Claude API error {status}: {body}");
        }

        let claude_resp: ClaudeResponse =
            resp.json().await.context("Failed to parse Claude response")?;

        let text = claude_resp
            .content
            .iter()
            .filter(|b| b.block_type == "text")
            .filter_map(|b| b.text.as_deref())
            .collect::<Vec<_>>()
            .join("");

        debug!(
            model = actual_model,
            len = text.len(),
            "Claude response received"
        );

        Ok(text)
    }

    async fn health(&self, model: &str) -> Result<bool> {
        let actual_model = if model.is_empty() {
            &self.default_model
        } else {
            model
        };

        // Quick validation: try a minimal request
        let request = ClaudeRequest {
            model: actual_model.to_string(),
            max_tokens: 1,
            system: String::new(),
            messages: vec![ClaudeMessage {
                role: "user".into(),
                content: "ping".into(),
            }],
            temperature: 0.0,
        };

        match self
            .client
            .post("https://api.anthropic.com/v1/messages")
            .header("x-api-key", &self.api_key)
            .header("anthropic-version", "2023-06-01")
            .header("content-type", "application/json")
            .json(&request)
            .send()
            .await
        {
            Ok(resp) => Ok(resp.status().is_success()),
            Err(_) => Ok(false),
        }
    }
}

// ─── Backend enum ────────────────────────────────────────────────────

/// Unified LLM backend that wraps either Ollama or Claude.
pub enum LlmBackend {
    Ollama(OllamaClient),
    Claude(ClaudeClient),
}

impl LlmClient for LlmBackend {
    async fn generate(
        &self,
        model: &str,
        system: &str,
        user: &str,
        temperature: f32,
        max_tokens: i32,
    ) -> Result<String> {
        match self {
            LlmBackend::Ollama(c) => c.generate(model, system, user, temperature, max_tokens).await,
            LlmBackend::Claude(c) => c.generate(model, system, user, temperature, max_tokens).await,
        }
    }

    async fn health(&self, model: &str) -> Result<bool> {
        match self {
            LlmBackend::Ollama(c) => c.health(model).await,
            LlmBackend::Claude(c) => c.health(model).await,
        }
    }
}
