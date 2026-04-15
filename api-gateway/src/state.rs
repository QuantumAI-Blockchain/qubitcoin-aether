//! Shared application state — injected into all Axum handlers.
//!
//! Contains: database pool, Substrate RPC proxy, Aether client, config.

use std::sync::Arc;

use sqlx::PgPool;
use subxt::backend::rpc::RpcClient;
use subxt::backend::legacy::LegacyRpcMethods;
use subxt::{OnlineClient, SubstrateConfig};

use crate::config::Config;

/// Shared state accessible by all route handlers.
#[derive(Clone)]
pub struct AppState {
    /// CockroachDB connection pool.
    pub db: PgPool,
    /// Substrate RPC client (for proxying chain queries).
    pub substrate: Arc<SubstrateRpc>,
    /// Aether service base URL.
    pub aether_url: String,
    /// Chain ID for JSON-RPC.
    pub chain_id: u64,
    /// HTTP client for Aether service proxy.
    pub http_client: reqwest::Client,
}

/// Substrate RPC connection.
pub struct SubstrateRpc {
    pub api: OnlineClient<SubstrateConfig>,
    pub rpc: LegacyRpcMethods<SubstrateConfig>,
}

impl SubstrateRpc {
    pub async fn connect(url: &str) -> anyhow::Result<Self> {
        // Use from_insecure_url for ws:// (non-TLS) connections.
        let rpc_client = if url.starts_with("ws://") {
            RpcClient::from_insecure_url(url).await?
        } else {
            RpcClient::from_url(url).await?
        };
        let api = OnlineClient::<SubstrateConfig>::from_rpc_client(rpc_client.clone()).await?;
        let rpc = LegacyRpcMethods::<SubstrateConfig>::new(rpc_client);
        Ok(Self { api, rpc })
    }
}
