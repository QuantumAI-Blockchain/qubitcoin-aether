//! Substrate RPC client — connects to the QBC Substrate node via WebSocket.
//!
//! Uses subxt in dynamic mode (no compile-time metadata required).
//! Subscribes to finalized block headers and fetches block details + events.

use anyhow::{Context, Result};
use subxt::backend::rpc::RpcClient;
use subxt::backend::legacy::LegacyRpcMethods;
use subxt::{OnlineClient, SubstrateConfig};
use tracing::info;

use crate::config::Config;

/// Wrapper around the subxt online client for QBC Substrate node.
pub struct SubstrateClient {
    pub api: OnlineClient<SubstrateConfig>,
    pub rpc: LegacyRpcMethods<SubstrateConfig>,
}

impl SubstrateClient {
    /// Connect to the Substrate node and download runtime metadata.
    pub async fn connect(config: &Config) -> Result<Self> {
        info!("Connecting to Substrate node: {}", config.substrate_ws_url);

        // Use from_insecure_url for ws:// (non-TLS) connections.
        let rpc_client = if config.substrate_ws_url.starts_with("ws://") {
            RpcClient::from_insecure_url(&config.substrate_ws_url).await
        } else {
            RpcClient::from_url(&config.substrate_ws_url).await
        }
        .context("Failed to connect to Substrate WebSocket")?;

        let api = OnlineClient::<SubstrateConfig>::from_rpc_client(rpc_client.clone())
            .await
            .context("Failed to initialize subxt client")?;

        let rpc = LegacyRpcMethods::<SubstrateConfig>::new(rpc_client);

        // Log chain info
        let genesis = rpc.genesis_hash().await?;
        let runtime_version = api.runtime_version();
        info!(
            "Connected! Genesis: 0x{}, Runtime spec_version: {}",
            hex::encode(genesis.0),
            runtime_version.spec_version,
        );

        Ok(Self { api, rpc })
    }

    /// Get the current finalized block number.
    pub async fn get_finalized_height(&self) -> Result<u64> {
        let hash = self.rpc.chain_get_finalized_head().await?;
        let header = self.rpc.chain_get_header(Some(hash)).await?;
        match header {
            Some(h) => Ok(h.number as u64),
            None => Ok(0),
        }
    }

    /// Get block hash by number.
    pub async fn get_block_hash(
        &self,
        number: u64,
    ) -> Result<Option<subxt::utils::H256>> {
        let hash = self
            .rpc
            .chain_get_block_hash(Some(number.into()))
            .await?;
        Ok(hash)
    }
}
