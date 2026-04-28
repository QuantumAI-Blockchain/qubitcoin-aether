use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use aether_client::substrate::{SubstrateClient, VqeProofEncoded};
use ed25519_dalek::{Signer, SigningKey};
use log::{debug, info, warn};
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use sha2::{Digest, Sha256};

use crate::hamiltonian;
use crate::vqe;

const ENERGY_SCALE: f64 = 1e12;
const DIFFICULTY_SCALE: f64 = 1e6;
const POLL_INTERVAL: Duration = Duration::from_millis(500);

/// Default pallet indices in the QBC runtime.
/// These must match the order in construct_runtime! in the Substrate node.
const CONSENSUS_PALLET_INDEX: u8 = 5;

#[derive(Debug, Clone)]
pub struct MinerConfig {
    pub substrate_rpc: String,
    pub max_attempts: usize,
    pub threads: u32,
    /// Ed25519 signing key for Substrate account (used to sign extrinsics).
    /// If None, falls back to a deterministic key derived from a seed.
    pub substrate_secret_key: Option<[u8; 32]>,
}

impl Default for MinerConfig {
    fn default() -> Self {
        Self {
            substrate_rpc: "http://localhost:9944".into(),
            max_attempts: 100,
            threads: 1,
            substrate_secret_key: None,
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
            hashrate: 0.0,
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

/// Derive the miner's QBC address from their Substrate AccountId.
/// Matches the Substrate pallet: SHA-256(SCALE(AccountId)).
fn account_to_miner_address(public_key: &[u8; 32]) -> [u8; 32] {
    // AccountId32 SCALE-encodes as just the 32 raw bytes
    let hash = Sha256::digest(public_key);
    let mut addr = [0u8; 32];
    addr.copy_from_slice(&hash);
    addr
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
            let substrate = SubstrateClient::new(&config.substrate_rpc);
            let mut rng = ChaCha8Rng::from_entropy();

            // Create or use the Ed25519 signing key for Substrate extrinsics
            let signing_key = match config.substrate_secret_key {
                Some(bytes) => SigningKey::from_bytes(&bytes),
                None => {
                    // Generate a deterministic key from thread ID (for development)
                    let mut seed = [0u8; 32];
                    seed[0] = thread_id as u8;
                    seed[31] = 0x42;
                    SigningKey::from_bytes(&seed)
                }
            };
            let verifying_key = signing_key.verifying_key();
            let account_id: [u8; 32] = verifying_key.to_bytes();
            let miner_address = account_to_miner_address(&account_id);

            info!(
                "[miner-{thread_id}] VQE mining thread started (account: 0x{})",
                hex::encode(&account_id[..8])
            );

            // Fetch runtime metadata once
            let (spec_version, tx_version) = match substrate.get_runtime_version().await {
                Ok(v) => v,
                Err(e) => {
                    warn!("[miner-{thread_id}] Failed to get runtime version: {e}. Using defaults.");
                    (1, 1)
                }
            };
            let genesis_hash = match substrate.get_genesis_hash().await {
                Ok(h) => h,
                Err(e) => {
                    warn!("[miner-{thread_id}] Failed to get genesis hash: {e}. Using zeros.");
                    [0u8; 32]
                }
            };

            let mut last_hash = String::new();

            while running.load(Ordering::Relaxed) {
                // Get chain state
                let chain_state = match substrate.get_chain_state().await {
                    Ok(state) => state,
                    Err(e) => {
                        debug!("[miner-{thread_id}] RPC error: {e}");
                        tokio::time::sleep(Duration::from_secs(3)).await;
                        continue;
                    }
                };

                height_atomic.store(chain_state.height, Ordering::Relaxed);
                difficulty_atomic.store(chain_state.difficulty, Ordering::Relaxed);

                if chain_state.best_hash == last_hash {
                    tokio::time::sleep(POLL_INTERVAL).await;
                    continue;
                }

                let mining_height = chain_state.height + 1;

                if last_proved.load(Ordering::Relaxed) >= mining_height {
                    tokio::time::sleep(POLL_INTERVAL).await;
                    continue;
                }

                // Decode parent hash for seed derivation
                let hash_bytes = hex::decode(chain_state.best_hash.trim_start_matches("0x"))
                    .unwrap_or_else(|_| vec![0u8; 32]);
                let mut parent = [0u8; 32];
                let len = hash_bytes.len().min(32);
                parent[..len].copy_from_slice(&hash_bytes[..len]);

                let seed = hamiltonian::derive_seed(&parent, mining_height);
                let ham = hamiltonian::generate_hamiltonian(&seed);
                let difficulty_f64 = chain_state.difficulty as f64 / DIFFICULTY_SCALE;

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

                        // Build proper SCALE-encoded signed extrinsic
                        let scaled_params: Vec<i64> = result.params.iter()
                            .map(|&p| (p * ENERGY_SCALE) as i64)
                            .collect();
                        let scaled_energy = (result.energy * ENERGY_SCALE) as i128;

                        let proof = VqeProofEncoded {
                            params: scaled_params,
                            energy: scaled_energy,
                            hamiltonian_seed: seed,
                            n_qubits: 4,
                        };

                        // Encode the call
                        let call_data = SubstrateClient::encode_mining_proof_call(
                            CONSENSUS_PALLET_INDEX,
                            miner_address,
                            proof,
                        );

                        // Get nonce
                        let nonce = match substrate.get_nonce(&format!("0x{}", hex::encode(account_id))).await {
                            Ok(n) => n,
                            Err(e) => {
                                warn!("[miner-{thread_id}] Failed to get nonce: {e}");
                                0
                            }
                        };

                        // Build signing payload
                        let payload = SubstrateClient::build_signing_payload(
                            &call_data,
                            nonce,
                            spec_version,
                            tx_version,
                            &genesis_hash,
                        );

                        // Sign with Ed25519
                        let signature = signing_key.sign(&payload);
                        let sig_bytes: [u8; 64] = signature.to_bytes();

                        // Build the complete signed extrinsic
                        let extrinsic = SubstrateClient::build_signed_extrinsic(
                            &call_data,
                            &account_id,
                            &sig_bytes,
                            nonce,
                        );

                        let ext_hex = format!("0x{}", hex::encode(&extrinsic));

                        match substrate.submit_extrinsic(&ext_hex).await {
                            Ok(hash) => {
                                last_proved.store(mining_height, Ordering::Release);
                                blocks_found.fetch_add(1, Ordering::Relaxed);
                                info!(
                                    "[miner-{thread_id}] Proof submitted for height {mining_height} (tx: {hash})"
                                );
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

                last_hash = chain_state.best_hash;
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
