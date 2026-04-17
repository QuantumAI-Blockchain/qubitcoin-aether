use anyhow::{Context, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, warn};

pub struct OllamaClient {
    client: Client,
    base_url: String,
}

#[derive(Debug, Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<ChatMessage>,
    stream: bool,
    options: Option<ChatOptions>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Serialize)]
struct ChatOptions {
    temperature: f32,
    num_predict: i32,
}

#[derive(Debug, Deserialize)]
struct ChatResponse {
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

    /// Generate a completion from Ollama.
    pub async fn generate(
        &self,
        model: &str,
        system: &str,
        user: &str,
        temperature: f32,
        max_tokens: i32,
    ) -> Result<String> {
        let url = format!("{}/api/chat", self.base_url);

        let request = ChatRequest {
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
            options: Some(ChatOptions {
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

        let chat_resp: ChatResponse = resp.json().await.context("Failed to parse Ollama response")?;
        debug!(
            model,
            len = chat_resp.message.content.len(),
            "Ollama response received"
        );

        Ok(chat_resp.message.content)
    }

    /// Check if Ollama is running and a model is available.
    pub async fn health(&self, model: &str) -> Result<bool> {
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
                        .map_or(false, |n| n.starts_with(model.split(':').next().unwrap_or(model)))
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
