//! Shared application state — injected into all Axum handlers.
//!
//! Contains: database pool, Substrate RPC proxy (optional), Aether client, config.

use std::sync::Arc;

use sqlx::PgPool;
use subxt::backend::rpc::RpcClient;
use subxt::backend::legacy::LegacyRpcMethods;
use subxt::{OnlineClient, SubstrateConfig};
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
    pub http_client: reqwest::Client,
}

/// Substrate RPC connection.
pub struct SubstrateRpc {
    pub api: OnlineClient<SubstrateConfig>,
    pub rpc: LegacyRpcMethods<SubstrateConfig>,
}

impl SubstrateRpc {
    pub async fn connect(url: &str) -> Option<Self> {
        let rpc_client = if url.starts_with("ws://") {
            match RpcClient::from_insecure_url(url).await {
                Ok(c) => c,
                Err(e) => {
                    warn!("Substrate RPC connect failed: {e} — running DB-only mode");
                    return None;
                }
            }
        } else {
            match RpcClient::from_url(url).await {
                Ok(c) => c,
                Err(e) => {
                    warn!("Substrate RPC connect failed: {e} — running DB-only mode");
                    return None;
                }
            }
        };
        match OnlineClient::<SubstrateConfig>::from_rpc_client(rpc_client.clone()).await {
            Ok(api) => {
                let rpc = LegacyRpcMethods::<SubstrateConfig>::new(rpc_client);
                info!("Substrate RPC connected");
                Some(Self { api, rpc })
            }
            Err(e) => {
                warn!("Substrate metadata fetch failed: {e} — running DB-only mode");
                None
            }
        }
    }
}
