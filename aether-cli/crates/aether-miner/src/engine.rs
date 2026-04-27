use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use log::{debug, info, warn};
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use serde::Deserialize;

use crate::hamiltonian;
use crate::vqe;

const ENERGY_SCALE: f64 = 1e12;
const DIFFICULTY_SCALE: f64 = 1e6;
const POLL_INTERVAL: Duration = Duration::from_millis(500);

#[derive(Debug, Clone)]
pub struct MinerConfig {
    pub substrate_rpc: String,
    pub max_attempts: usize,
    pub threads: u32,
}

impl Default for MinerConfig {
    fn default() -> Self {
        Self {
            substrate_rpc: "http://localhost:9944".into(),
            max_attempts: 100,
            threads: 1,
        }
    }
}

/// Live statistics from the mining engine.
#[derive(Debug, Clone, Default)]
pub struct MinerStats {
    pub running: bool,
    pub blocks_found: u64,
    pub attempts_total: u64,
    pub current_height: u64,
    pub current_difficulty: f64,
    pub hashrate: f64,
}

/// Handle to a running miner. Drop to stop.
pub struct MinerHandle {
    running: Arc<AtomicBool>,
    blocks_found: Arc<AtomicU64>,
    attempts: Arc<AtomicU64>,
    height: Arc<AtomicU64>,
    difficulty: Arc<AtomicU64>,
    join_handles: Vec<tokio::task::JoinHandle<()>>,
}

impl MinerHandle {
    pub fn stats(&self) -> MinerStats {
        let attempts = self.attempts.load(Ordering::Relaxed);
        MinerStats {
            running: self.running.load(Ordering::Relaxed),
            blocks_found: self.blocks_found.load(Ordering::Relaxed),
            attempts_total: attempts,
            current_height: self.height.load(Ordering::Relaxed),
            current_difficulty: self.difficulty.load(Ordering::Relaxed) as f64 / DIFFICULTY_SCALE,
            hashrate: 0.0, // computed externally from attempt rate
        }
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::Release);
    }
}

impl Drop for MinerHandle {
    fn drop(&mut self) {
        self.stop();
        for h in self.join_handles.drain(..) {
            h.abort();
        }
    }
}

#[derive(Deserialize)]
struct RpcResponse<T> {
    result: Option<T>,
    #[allow(dead_code)]
    error: Option<serde_json::Value>,
}

/// Query Substrate RPC for chain head and mining state.
async fn get_chain_state(
    client: &reqwest::Client,
    rpc_url: &str,
) -> Result<(String, u64, u64)> {
    // Get best block hash
    let resp: RpcResponse<String> = client
        .post(rpc_url)
        .json(&serde_json::json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "chain_getBlockHash",
            "params": []
        }))
        .send()
        .await?
        .json()
        .await?;
    let best_hash = resp.result.context("no best hash")?;

    // Get block header for height
    let resp: RpcResponse<serde_json::Value> = client
        .post(rpc_url)
        .json(&serde_json::json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "chain_getHeader",
            "params": [&best_hash]
        }))
        .send()
        .await?
        .json()
        .await?;
    let header = resp.result.context("no header")?;
    let number_hex = header["number"].as_str().unwrap_or("0x0");
    let height = u64::from_str_radix(number_hex.trim_start_matches("0x"), 16).unwrap_or(0);

    // Get difficulty from consensus pallet storage
    // Key: twox128("QbcConsensus") ++ twox128("CurrentDifficulty")
    let resp: RpcResponse<Option<String>> = client
        .post(rpc_url)
        .json(&serde_json::json!({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "state_getStorage",
            "params": [
                "0x5eb06b846137e590e33517b51ad3b12d2f22ee84e3d2e52be17e50de7cead31a",
                &best_hash
            ]
        }))
        .send()
        .await?
        .json()
        .await?;

    let difficulty = if let Some(Some(hex_val)) = resp.result {
        let bytes = hex::decode(hex_val.trim_start_matches("0x")).unwrap_or_default();
        if bytes.len() >= 8 {
            u64::from_le_bytes(bytes[..8].try_into().unwrap_or([0; 8]))
        } else {
            10_640_000 // default ~10.64
        }
    } else {
        10_640_000
    };

    Ok((best_hash, height, difficulty))
}

/// Start the mining engine. Returns a handle to monitor/stop it.
pub fn start(config: MinerConfig) -> MinerHandle {
    let running = Arc::new(AtomicBool::new(true));
    let blocks_found = Arc::new(AtomicU64::new(0));
    let attempts = Arc::new(AtomicU64::new(0));
    let height = Arc::new(AtomicU64::new(0));
    let difficulty = Arc::new(AtomicU64::new(0));
    let last_proved = Arc::new(AtomicU64::new(0));

    let mut handles = Vec::new();

    for thread_id in 0..config.threads {
        let running = running.clone();
        let blocks_found = blocks_found.clone();
        let attempts = attempts.clone();
        let height_atomic = height.clone();
        let difficulty_atomic = difficulty.clone();
        let last_proved = last_proved.clone();
        let config = config.clone();

        let handle = tokio::spawn(async move {
            let client = reqwest::Client::new();
            let mut rng = ChaCha8Rng::from_entropy();
            let mut last_hash = String::new();

            info!("[miner-{thread_id}] VQE mining thread started");

            while running.load(Ordering::Relaxed) {
                // Get chain state
                let (best_hash, chain_height, diff) = match get_chain_state(&client, &config.substrate_rpc).await {
                    Ok(state) => state,
                    Err(e) => {
                        debug!("[miner-{thread_id}] RPC error: {e}");
                        tokio::time::sleep(Duration::from_secs(3)).await;
                        continue;
                    }
                };

                height_atomic.store(chain_height, Ordering::Relaxed);
                difficulty_atomic.store(diff, Ordering::Relaxed);

                if best_hash == last_hash {
                    tokio::time::sleep(POLL_INTERVAL).await;
                    continue;
                }

                let mining_height = chain_height + 1;

                if last_proved.load(Ordering::Relaxed) >= mining_height {
                    tokio::time::sleep(POLL_INTERVAL).await;
                    continue;
                }

                // Decode parent hash for seed derivation
                let hash_bytes = hex::decode(best_hash.trim_start_matches("0x")).unwrap_or_else(|_| vec![0u8; 32]);
                let mut parent = [0u8; 32];
                let len = hash_bytes.len().min(32);
                parent[..len].copy_from_slice(&hash_bytes[..len]);

                let seed = hamiltonian::derive_seed(&parent, mining_height);
                let ham = hamiltonian::generate_hamiltonian(&seed);
                let difficulty_f64 = diff as f64 / DIFFICULTY_SCALE;

                debug!(
                    "[miner-{thread_id}] Mining height {mining_height} (difficulty={difficulty_f64:.6})"
                );

                let start = Instant::now();
                let mut found = false;

                for attempt in 0..config.max_attempts {
                    if !running.load(Ordering::Relaxed) {
                        break;
                    }
                    if last_proved.load(Ordering::Relaxed) >= mining_height {
                        break;
                    }

                    attempts.fetch_add(1, Ordering::Relaxed);
                    let result = vqe::optimize(&ham, &mut rng);

                    if result.energy < difficulty_f64 {
                        let elapsed = start.elapsed();
                        info!(
                            "[miner-{thread_id}] VQE solution: energy={:.6} < difficulty={:.6} (attempt {}/{}, {:.1}ms)",
                            result.energy, difficulty_f64, attempt + 1, config.max_attempts,
                            elapsed.as_secs_f64() * 1000.0
                        );

                        // Submit proof via RPC
                        let scaled_params: Vec<i64> = result.params.iter()
                            .map(|&p| (p * ENERGY_SCALE) as i64)
                            .collect();
                        let scaled_energy = (result.energy * ENERGY_SCALE) as i128;

                        let submit_result = client
                            .post(&config.substrate_rpc)
                            .json(&serde_json::json!({
                                "jsonrpc": "2.0",
                                "id": 10,
                                "method": "author_submitExtrinsic",
                                "params": [{
                                    "mining_proof": {
                                        "params": scaled_params,
                                        "energy": scaled_energy,
                                        "seed": hex::encode(seed),
                                        "n_qubits": 4
                                    }
                                }]
                            }))
                            .send()
                            .await;

                        match submit_result {
                            Ok(_) => {
                                last_proved.store(mining_height, Ordering::Release);
                                blocks_found.fetch_add(1, Ordering::Relaxed);
                                info!("[miner-{thread_id}] Proof submitted for height {mining_height}");
                                found = true;
                            }
                            Err(e) => {
                                warn!("[miner-{thread_id}] Submit failed: {e}");
                            }
                        }
                        break;
                    }
                }

                if !found {
                    debug!(
                        "[miner-{thread_id}] No solution for height {mining_height} after {} attempts",
                        config.max_attempts
                    );
                }

                last_hash = best_hash;
                tokio::time::sleep(POLL_INTERVAL).await;
            }

            info!("[miner-{thread_id}] Mining thread stopped");
        });

        handles.push(handle);
    }

    MinerHandle {
        running,
        blocks_found,
        attempts,
        height,
        difficulty,
        join_handles: handles,
    }
}
