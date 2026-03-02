//! Treasury Disbursement Client — Calls the Python node RPC to create
//! reward transactions on the QBC blockchain.
//!
//! The sidecar does not hold private keys or create transactions directly.
//! Instead, it calls an internal endpoint on the Python node which signs
//! and broadcasts the transaction using the treasury wallet's Dilithium
//! private key (stored in `secure_key.env`).

use serde::{Deserialize, Serialize};

// ════════════════════════════════════════════════════════════════════════════
// Error type
// ════════════════════════════════════════════════════════════════════════════

#[derive(Debug, thiserror::Error)]
pub enum TreasuryError {
    #[error("HTTP request failed: {0}")]
    Http(#[from] reqwest::Error),
    #[error("node returned error: {0}")]
    NodeError(String),
    #[error("node is unreachable at {0}")]
    NodeUnreachable(String),
    #[error("unexpected response format: {0}")]
    BadResponse(String),
}

// ════════════════════════════════════════════════════════════════════════════
// Public types
// ════════════════════════════════════════════════════════════════════════════

/// Result of a treasury disbursement request.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisburseResult {
    /// Whether the disbursement was accepted by the node.
    pub success: bool,
    /// Transaction ID if successful (hex-encoded hash).
    pub txid: Option<String>,
    /// Error message if unsuccessful.
    pub error: Option<String>,
}

/// Request body sent to the Python node's internal disbursement endpoint.
#[derive(Debug, Serialize)]
struct DisburseRequest {
    recipient_address: String,
    amount: f64,
    reason: String,
}

/// Expected response body from the node.
#[derive(Debug, Deserialize)]
struct NodeDisburseResponse {
    #[serde(default)]
    success: bool,
    #[serde(default)]
    txid: Option<String>,
    #[serde(default)]
    error: Option<String>,
}

// ════════════════════════════════════════════════════════════════════════════
// TreasuryClient
// ════════════════════════════════════════════════════════════════════════════

/// HTTP client for treasury disbursement via the Python node RPC.
pub struct TreasuryClient {
    client: reqwest::Client,
    node_rpc_url: String,
}

impl TreasuryClient {
    /// Create a new treasury client pointing at the given node RPC URL
    /// (e.g. `http://localhost:5000`).
    pub fn new(node_rpc_url: &str) -> Self {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .unwrap_or_else(|_| reqwest::Client::new());

        Self {
            client,
            node_rpc_url: node_rpc_url.trim_end_matches('/').to_string(),
        }
    }

    // ── Disburse reward ─────────────────────────────────────────────────

    /// Request the node to create a treasury transaction sending `amount`
    /// QBC to `recipient_address` with the given `reason` tag.
    ///
    /// The node handles signing with the treasury Dilithium key, UTXO
    /// selection, and broadcast. We just get back a txid on success.
    pub async fn disburse(
        &self,
        recipient_address: &str,
        amount: f64,
        reason: &str,
    ) -> Result<DisburseResult, TreasuryError> {
        let url = format!("{}/internal/aikgs/disburse", self.node_rpc_url);

        let body = DisburseRequest {
            recipient_address: recipient_address.to_string(),
            amount,
            reason: reason.to_string(),
        };

        let response = self
            .client
            .post(&url)
            .json(&body)
            .send()
            .await
            .map_err(|e| {
                if e.is_connect() || e.is_timeout() {
                    TreasuryError::NodeUnreachable(self.node_rpc_url.clone())
                } else {
                    TreasuryError::Http(e)
                }
            })?;

        let status = response.status();

        if !status.is_success() {
            let text = response.text().await.unwrap_or_default();
            log::error!(
                "Treasury disburse failed: status={} body={}",
                status,
                text
            );
            return Ok(DisburseResult {
                success: false,
                txid: None,
                error: Some(format!("HTTP {}: {}", status, text)),
            });
        }

        let node_resp: NodeDisburseResponse = response.json().await.map_err(|e| {
            TreasuryError::BadResponse(format!("failed to parse node response: {}", e))
        })?;

        if node_resp.success {
            log::info!(
                "Treasury disbursed {:.8} QBC to {} (reason: {}) txid={}",
                amount,
                recipient_address,
                reason,
                node_resp.txid.as_deref().unwrap_or("unknown")
            );
        } else {
            log::warn!(
                "Treasury disburse rejected: recipient={} amount={:.8} error={}",
                recipient_address,
                amount,
                node_resp.error.as_deref().unwrap_or("unknown")
            );
        }

        Ok(DisburseResult {
            success: node_resp.success,
            txid: node_resp.txid,
            error: node_resp.error,
        })
    }

    // ── Health check ────────────────────────────────────────────────────

    /// Check if the Python node is reachable by hitting its `/health`
    /// endpoint. Returns `true` if the node responds with a 2xx status.
    pub async fn check_health(&self) -> bool {
        let url = format!("{}/health", self.node_rpc_url);

        match self.client.get(&url).send().await {
            Ok(resp) => {
                let healthy = resp.status().is_success();
                if !healthy {
                    log::warn!(
                        "Node health check returned non-success: {}",
                        resp.status()
                    );
                }
                healthy
            }
            Err(e) => {
                log::warn!("Node health check failed: {}", e);
                false
            }
        }
    }

    /// Get the configured node RPC URL.
    pub fn node_rpc_url(&self) -> &str {
        &self.node_rpc_url
    }
}
