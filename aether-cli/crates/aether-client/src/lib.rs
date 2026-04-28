pub mod substrate;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

/// HTTP client for the Aether Mind API.
#[derive(Clone)]
pub struct AetherClient {
    base_url: String,
    http: reqwest::Client,
    /// Optional wallet address sent as X-QBC-Address for subscription auth.
    wallet_address: Option<String>,
}

#[derive(Serialize)]
struct ChatRequestBody {
    message: String,
    temperature: f32,
    max_tokens: usize,
}

#[derive(Serialize)]
struct GradientSubmitBody {
    indices: Vec<u32>,
    values: Vec<f32>,
    total_params: u64,
    sparsity: f32,
    full_norm: f32,
    residual_norm: f32,
    miner_id: String,
}

#[derive(Serialize)]
struct ClaimBody {
    miner_id: String,
    wallet_address: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ChatResponse {
    pub response: String,
    pub phi: f64,
    pub phi_micro: f64,
    pub phi_meso: f64,
    pub phi_macro: f64,
    pub tokens_generated: usize,
    pub latency_ms: u64,
    pub model: String,
    pub knowledge_vectors: usize,
    pub knowledge_context: Vec<String>,
    pub active_sephirot: u8,
    pub chain_height: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub model: String,
    pub architecture: String,
    pub parameters: usize,
    pub memory_mb: usize,
    pub knowledge_vectors: usize,
    pub phi: f64,
    pub emotional_state: EmotionalState,
    pub chain_height: u64,
    pub version: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EmotionalState {
    pub curiosity: f32,
    pub satisfaction: f32,
    pub frustration: f32,
    pub wonder: f32,
    pub excitement: f32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct InfoResponse {
    pub version: String,
    pub architecture: String,
    pub model: String,
    pub parameters: usize,
    pub embed_dim: usize,
    pub num_layers: usize,
    pub num_sephirot_heads: usize,
    pub num_global_heads: usize,
    pub num_kv_heads: usize,
    pub knowledge_vectors: usize,
    pub phi: f64,
    pub chain_height: u64,
    pub sephirot: Vec<SephirotInfo>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SephirotInfo {
    pub name: String,
    pub function: String,
    pub higgs_mass: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct GatesResponse {
    pub gates_passed: u8,
    pub gates: Vec<GateInfo>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct GateInfo {
    pub gate: u8,
    pub name: String,
    pub passed: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct KnowledgeSearchResponse {
    pub results: Vec<KnowledgeResult>,
    #[serde(alias = "total_vectors")]
    pub total: usize,
}

#[derive(Debug, Clone, Deserialize)]
pub struct KnowledgeResult {
    #[serde(alias = "content")]
    pub text: String,
    pub domain: u8,
    pub similarity: f32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct GradientSubmitResponse {
    pub status: String,
    pub peer_gradients_queued: usize,
    pub fedavg_triggered: bool,
    pub embeddings_ingested: usize,
    pub total_knowledge_vectors: usize,
    pub reward_qbc: f64,
    pub pool_remaining_qbc: f64,
    pub miner_id: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RewardsResponse {
    pub miner_id: String,
    pub earned_qbc: f64,
    pub claimed_qbc: f64,
    pub unclaimed_qbc: f64,
    pub submissions: u64,
    pub last_block: u64,
    pub avg_improvement_ratio: f32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RewardPoolResponse {
    pub pool_address: String,
    pub pool_balance_qbc: f64,
    pub total_distributed_qbc: f64,
    pub total_claimed_qbc: f64,
    pub total_unclaimed_qbc: f64,
    pub base_reward_qbc: f64,
    pub max_multiplier: f64,
    pub total_miners: usize,
    pub total_submissions: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RewardClaimResponse {
    pub status: String,
    pub miner_id: String,
    pub amount_qbc: f64,
    pub wallet_address: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct GradientStatusResponse {
    pub peer_gradients_queued: usize,
    pub embedding_delta_norm: f32,
    pub embedding_delta_size: usize,
    pub current_validation_loss: f32,
}

impl AetherClient {
    pub fn new(base_url: &str) -> Self {
        let base = base_url.trim_end_matches('/');
        // Add /v1 prefix if not already present and not a direct service URL (port-based)
        let base_url = if base.contains("localhost") || base.contains("127.0.0.1") {
            base.to_string()
        } else {
            format!("{}/v1", base)
        };
        Self {
            base_url,
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(120))
                .build()
                .expect("failed to create HTTP client"),
            wallet_address: None,
        }
    }

    /// Set the wallet address for subscription-based auth (sent as X-QBC-Address header).
    pub fn with_wallet(mut self, address: String) -> Self {
        self.wallet_address = Some(address);
        self
    }

    pub async fn chat(
        &self,
        message: &str,
        temperature: f32,
        max_tokens: usize,
    ) -> Result<ChatResponse> {
        let mut req = self
            .http
            .post(format!("{}/aether/chat", self.base_url))
            .json(&ChatRequestBody {
                message: message.to_string(),
                temperature,
                max_tokens,
            });

        // Attach wallet address for subscription auth if available
        if let Some(addr) = &self.wallet_address {
            req = req.header("X-QBC-Address", addr);
        }

        let resp = req.send().await.context("failed to reach aether-mind")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            anyhow::bail!("aether-mind returned {status}: {body}");
        }

        resp.json().await.context("failed to parse chat response")
    }

    pub async fn health(&self) -> Result<HealthResponse> {
        let resp = self
            .http
            .get(format!("{}/aether/health", self.base_url))
            .send()
            .await
            .context("failed to reach aether-mind")?;

        resp.json().await.context("failed to parse health response")
    }

    pub async fn info(&self) -> Result<InfoResponse> {
        let resp = self
            .http
            .get(format!("{}/aether/info", self.base_url))
            .send()
            .await
            .context("failed to reach aether-mind")?;

        resp.json().await.context("failed to parse info response")
    }

    pub async fn gates(&self) -> Result<GatesResponse> {
        let resp = self
            .http
            .get(format!("{}/aether/gates", self.base_url))
            .send()
            .await
            .context("failed to reach aether-mind")?;

        resp.json().await.context("failed to parse gates response")
    }

    pub async fn knowledge_search(&self, query: &str, limit: usize) -> Result<KnowledgeSearchResponse> {
        let resp = self
            .http
            .get(format!("{}/aether/knowledge/search", self.base_url))
            .query(&[("q", query), ("limit", &limit.to_string())])
            .send()
            .await
            .context("failed to reach aether-mind")?;

        resp.json()
            .await
            .context("failed to parse knowledge search response")
    }

    pub async fn gradient_status(&self) -> Result<GradientStatusResponse> {
        let resp = self
            .http
            .get(format!("{}/aether/gradients", self.base_url))
            .send()
            .await
            .context("failed to reach aether-mind")?;

        resp.json().await.context("failed to parse gradient status")
    }

    pub async fn submit_gradients(
        &self,
        miner_id: &str,
        indices: Vec<u32>,
        values: Vec<f32>,
        total_params: u64,
    ) -> Result<GradientSubmitResponse> {
        let sparsity = if total_params > 0 {
            indices.len() as f32 / total_params as f32
        } else {
            0.0
        };
        let full_norm: f32 = values.iter().map(|v| v * v).sum::<f32>().sqrt();

        let resp = self
            .http
            .post(format!("{}/aether/gradients", self.base_url))
            .json(&GradientSubmitBody {
                indices,
                values,
                total_params,
                sparsity,
                full_norm,
                residual_norm: 0.0,
                miner_id: miner_id.to_string(),
            })
            .send()
            .await
            .context("failed to reach aether-mind")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            anyhow::bail!("gradient submit failed {status}: {body}");
        }

        resp.json().await.context("failed to parse gradient submit response")
    }

    pub async fn rewards(&self, miner_id: &str) -> Result<RewardsResponse> {
        let resp = self
            .http
            .get(format!("{}/aether/rewards/{}", self.base_url, miner_id))
            .send()
            .await
            .context("failed to reach aether-mind")?;

        resp.json().await.context("failed to parse rewards response")
    }

    pub async fn reward_pool(&self) -> Result<RewardPoolResponse> {
        let resp = self
            .http
            .get(format!("{}/aether/rewards/pool", self.base_url))
            .send()
            .await
            .context("failed to reach aether-mind")?;

        resp.json().await.context("failed to parse reward pool response")
    }

    pub async fn claim_rewards(&self, miner_id: &str, wallet_address: &str) -> Result<RewardClaimResponse> {
        let resp = self
            .http
            .post(format!("{}/aether/rewards/claim", self.base_url))
            .json(&ClaimBody {
                miner_id: miner_id.to_string(),
                wallet_address: wallet_address.to_string(),
            })
            .send()
            .await
            .context("failed to reach aether-mind")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            anyhow::bail!("claim failed {status}: {body}");
        }

        resp.json().await.context("failed to parse claim response")
    }
}
