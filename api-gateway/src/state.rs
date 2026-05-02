//! Shared application state — injected into all Axum handlers.
//!
//! Contains: database pool, Substrate RPC client (raw JSON-RPC), Aether client, config.

use std::sync::Arc;

use reqwest::Client;
use serde::Deserialize;
use serde_json::json;
use sqlx::PgPool;
use tracing::{info, warn};

/// Fork offset: Substrate block 0 = Python chain block 208,680.
pub const FORK_OFFSET: u64 = 208_680;

/// Genesis premine in QBC (raw u128 with 8 decimals).
pub const GENESIS_PREMINE: f64 = 33_000_000.0;

/// Difficulty scaling factor (pallet stores difficulty * 1e6).
pub const DIFFICULTY_SCALE: f64 = 1_000_000.0;

/// QBC balance decimals (u128 stores value * 10^8).
pub const BALANCE_DECIMALS: f64 = 100_000_000.0;

// ═══════════════════════════════════════════════════════════════════════
// Precomputed Substrate storage keys (twox_128 hashes)
// ═══════════════════════════════════════════════════════════════════════
// Computed via: twox_128("PalletName") ++ twox_128("StorageName")
// where twox_128(x) = xxh64(x, seed=0).to_le_bytes() ++ xxh64(x, seed=1).to_le_bytes()

/// QbcEconomics::TotalEmitted (u128 / QbcBalance)
const KEY_TOTAL_EMITTED: &str =
    "0xbff54c5d15edb82ee0a6e5a00a256541ece1b90f966544723fca5e686553e59c";
/// QbcEconomics::CurrentEra (u32)
const KEY_CURRENT_ERA: &str =
    "0xbff54c5d15edb82ee0a6e5a00a2565410b6a45321efae92aea15e0740ec7afe7";
/// QbcConsensus::CurrentDifficulty (u64 / Difficulty)
const KEY_CURRENT_DIFFICULTY: &str =
    "0xa950945326674bfd85ee09d4109b3aec59769e16105568cee9f916e870cb6e6f";
/// QbcConsensus::BlocksMined (u64)
const KEY_BLOCKS_MINED: &str =
    "0xa950945326674bfd85ee09d4109b3aeca8c3702e58cebda658630b7a44f9d864";
/// QbcUtxo::CurrentHeight (u64) — fork-aware height
const KEY_CURRENT_HEIGHT: &str =
    "0x65aafe7b9e357728da13fce53a638188de182e0f37f4dafeea1589cb0af23389";

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

/// Live chain state read directly from Substrate storage.
#[derive(Debug, Clone)]
pub struct ChainState {
    /// Fork-aware block height (includes FORK_OFFSET).
    pub height: u64,
    /// Substrate-only block count.
    pub substrate_height: u64,
    /// Current difficulty (raw u64, scaled by 1e6).
    pub difficulty_raw: u64,
    /// Current difficulty as float.
    pub difficulty: f64,
    /// Total emitted supply in QBC (float, 8-decimal precision).
    pub total_supply: f64,
    /// Current era (0-indexed).
    pub era: u32,
    /// Total blocks mined on Substrate.
    pub blocks_mined: u64,
    /// Number of connected peers.
    pub peers: u64,
    /// Whether node is syncing.
    pub is_syncing: bool,
    /// Current block reward in QBC.
    pub block_reward: f64,
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

    // ═══════════════════════════════════════════════════════════════════
    // Standard Substrate RPC methods
    // ═══════════════════════════════════════════════════════════════════

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

    // ═══════════════════════════════════════════════════════════════════
    // Substrate storage queries
    // ═══════════════════════════════════════════════════════════════════

    /// Read a raw storage value by key (hex-encoded).
    async fn state_get_storage(&self, key: &str) -> Option<Vec<u8>> {
        let body = json!({
            "jsonrpc": "2.0",
            "method": "state_getStorage",
            "params": [key],
            "id": 1
        });
        let resp = self.client.post(&self.url).json(&body).send().await.ok()?;
        let rpc: RpcResponse<String> = resp.json().await.ok()?;
        let hex_str = rpc.result?;
        hex::decode(hex_str.trim_start_matches("0x")).ok()
    }

    /// Call a runtime API method.
    async fn state_call(&self, method: &str) -> Option<Vec<u8>> {
        let body = json!({
            "jsonrpc": "2.0",
            "method": "state_call",
            "params": [method, "0x"],
            "id": 1
        });
        let resp = self.client.post(&self.url).json(&body).send().await.ok()?;
        let rpc: RpcResponse<String> = resp.json().await.ok()?;
        let hex_str = rpc.result?;
        hex::decode(hex_str.trim_start_matches("0x")).ok()
    }

    // ═══════════════════════════════════════════════════════════════════
    // Typed storage readers
    // ═══════════════════════════════════════════════════════════════════

    /// Read CurrentDifficulty from QbcConsensus pallet (u64, scaled by 1e6).
    /// Falls back to runtime API if storage read fails.
    pub async fn current_difficulty(&self) -> Option<u64> {
        // Try storage first
        if let Some(bytes) = self.state_get_storage(KEY_CURRENT_DIFFICULTY).await {
            if bytes.len() >= 8 {
                return Some(u64::from_le_bytes(bytes[..8].try_into().ok()?));
            }
        }
        // Fallback: runtime API
        if let Some(bytes) = self.state_call("QbcConsensusApi_current_difficulty").await {
            if bytes.len() >= 8 {
                return Some(u64::from_le_bytes(bytes[..8].try_into().ok()?));
            }
        }
        None
    }

    /// Read TotalEmitted from QbcEconomics pallet (u128 / QbcBalance, 8 decimals).
    pub async fn total_emitted(&self) -> Option<u128> {
        let bytes = self.state_get_storage(KEY_TOTAL_EMITTED).await?;
        if bytes.len() >= 16 {
            Some(u128::from_le_bytes(bytes[..16].try_into().ok()?))
        } else {
            None
        }
    }

    /// Read CurrentEra from QbcEconomics pallet (u32).
    pub async fn current_era(&self) -> Option<u32> {
        let bytes = self.state_get_storage(KEY_CURRENT_ERA).await?;
        if bytes.len() >= 4 {
            Some(u32::from_le_bytes(bytes[..4].try_into().ok()?))
        } else {
            None
        }
    }

    /// Read BlocksMined from QbcConsensus pallet (u64).
    pub async fn blocks_mined(&self) -> Option<u64> {
        let bytes = self.state_get_storage(KEY_BLOCKS_MINED).await?;
        if bytes.len() >= 8 {
            Some(u64::from_le_bytes(bytes[..8].try_into().ok()?))
        } else {
            None
        }
    }

    /// Read CurrentHeight from QbcUtxo pallet (u64, fork-aware).
    pub async fn current_height(&self) -> Option<u64> {
        let bytes = self.state_get_storage(KEY_CURRENT_HEIGHT).await?;
        if bytes.len() >= 8 {
            Some(u64::from_le_bytes(bytes[..8].try_into().ok()?))
        } else {
            None
        }
    }

    /// Read the Substrate block number from the header.
    pub async fn substrate_block_number(&self) -> Option<u64> {
        let header = self.chain_get_header().await?;
        let num_str = header.number.trim_start_matches("0x");
        u64::from_str_radix(num_str, 16).ok()
    }

    // ═══════════════════════════════════════════════════════════════════
    // Aggregate: full chain state in one call
    // ═══════════════════════════════════════════════════════════════════

    /// Fetch all live chain state from Substrate in parallel.
    /// Returns None only if Substrate is completely unreachable.
    pub async fn chain_state(&self) -> Option<ChainState> {
        let phi: f64 = 1.618033988749895;

        // Fire all queries in parallel
        let (health, header, difficulty, total_emitted, era, blocks_mined, height) = tokio::join!(
            self.system_health(),
            self.chain_get_header(),
            self.current_difficulty(),
            self.total_emitted(),
            self.current_era(),
            self.blocks_mined(),
            self.current_height(),
        );

        // We need at least the header to return meaningful data
        let substrate_height = header.and_then(|h| {
            let num_str = h.number.trim_start_matches("0x");
            u64::from_str_radix(num_str, 16).ok()
        })?;

        let era_val = era.unwrap_or(0);
        let block_reward = 15.27 / phi.powi(era_val as i32);
        let diff_raw = difficulty.unwrap_or(500_000);
        let fork_height = height.unwrap_or(FORK_OFFSET + substrate_height);

        let supply = match total_emitted {
            Some(raw) => raw as f64 / BALANCE_DECIMALS,
            // Fallback: premine + all blocks (fork offset + substrate) × reward
            None => GENESIS_PREMINE + ((FORK_OFFSET as f64 + substrate_height as f64) * block_reward),
        };

        let (peers, is_syncing) = match health {
            Some(h) => (h.peers, h.is_syncing),
            None => (0, false),
        };

        Some(ChainState {
            height: fork_height,
            substrate_height,
            difficulty_raw: diff_raw,
            difficulty: diff_raw as f64 / DIFFICULTY_SCALE,
            total_supply: supply,
            era: era_val,
            blocks_mined: blocks_mined.unwrap_or(substrate_height),
            peers,
            is_syncing,
            block_reward,
        })
    }
}
