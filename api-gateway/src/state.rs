//! Shared application state — injected into all Axum handlers.
//!
//! Contains: database pool, Substrate RPC client (raw JSON-RPC), Aether client, config.

use std::sync::Arc;

use reqwest::Client;
use serde::Deserialize;
use serde_json::json;
use sqlx::PgPool;
use tracing::{info, warn};

/// Shared state accessible by all route handlers.
#[derive(Clone)]
pub struct AppState {
    /// CockroachDB connection pool.
    pub db: PgPool,
    /// Substrate RPC client (optional — gateway works without it via DB).
    pub substrate: Option<Arc<SubstrateRpc>>,
    /// Aether service base URL.
    pub aether_url: String,
    /// Chain ID for JSON-RPC.
    pub chain_id: u64,
    /// HTTP client for Aether service proxy.
    pub http_client: Client,
}

/// Raw JSON-RPC client for Substrate — avoids subxt metadata fetch issues.
pub struct SubstrateRpc {
    url: String,
    client: Client,
}

#[derive(Deserialize)]
struct RpcResponse<T> {
    result: Option<T>,
}

#[derive(Deserialize)]
pub struct SystemHealth {
    pub peers: u64,
    #[serde(rename = "isSyncing")]
    pub is_syncing: bool,
}

#[derive(Deserialize)]
pub struct BlockHeader {
    pub number: String,
    #[serde(rename = "parentHash")]
    pub parent_hash: String,
}

impl SubstrateRpc {
    pub async fn connect(url: &str) -> Option<Self> {
        // Convert ws:// to http:// for JSON-RPC over HTTP
        let http_url = url
            .replace("ws://", "http://")
            .replace("wss://", "https://");

        let client = Client::new();

        // Test connection with a simple system_health call
        let body = json!({
            "jsonrpc": "2.0",
            "method": "system_health",
            "params": [],
            "id": 1
        });

        match client.post(&http_url).json(&body).send().await {
            Ok(resp) if resp.status().is_success() => {
                info!("Substrate RPC connected via HTTP at {}", http_url);
                Some(Self {
                    url: http_url,
                    client,
                })
            }
            Ok(resp) => {
                warn!(
                    "Substrate RPC returned status {} — running DB-only mode",
                    resp.status()
                );
                None
            }
            Err(e) => {
                warn!("Substrate RPC connect failed: {e} — running DB-only mode");
                None
            }
        }
    }

    /// Get system health (peer count, sync status).
    pub async fn system_health(&self) -> Option<SystemHealth> {
        let body = json!({
            "jsonrpc": "2.0",
            "method": "system_health",
            "params": [],
            "id": 1
        });
        let resp = self.client.post(&self.url).json(&body).send().await.ok()?;
        let rpc: RpcResponse<SystemHealth> = resp.json().await.ok()?;
        rpc.result
    }

    /// Get latest block header (best block).
    pub async fn chain_get_header(&self) -> Option<BlockHeader> {
        let body = json!({
            "jsonrpc": "2.0",
            "method": "chain_getHeader",
            "params": [],
            "id": 1
        });
        let resp = self.client.post(&self.url).json(&body).send().await.ok()?;
        let rpc: RpcResponse<BlockHeader> = resp.json().await.ok()?;
        rpc.result
    }
}
