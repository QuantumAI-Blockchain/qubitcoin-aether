//! Mining engine — watches for new blocks and submits VQE proofs.
//!
//! The mining loop:
//! 1. Get latest block hash + height
//! 2. Derive Hamiltonian seed (matching the pallet's derivation)
//! 3. Generate Hamiltonian from seed
//! 4. Run VQE optimization (multiple attempts)
//! 5. If energy < difficulty, submit proof as an extrinsic

use crate::hamiltonian;
use crate::vqe;
use log::{debug, info, warn};
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use sp_core::H256;
use std::sync::Arc;
use std::time::{Duration, Instant};

/// Number of VQE optimization attempts per block.
pub const MAX_ATTEMPTS: usize = 50;
/// Energy scaling factor (must match pallet: values stored as i128 * 10^12).
pub const ENERGY_SCALE: f64 = 1e12;
/// Difficulty scaling factor (stored as u64 * 10^6 in pallet).
pub const DIFFICULTY_SCALE: f64 = 1e6;
/// Polling interval between mining attempts when no new block.
pub const POLL_INTERVAL: Duration = Duration::from_millis(100);

/// Configuration for the mining engine.
#[derive(Debug, Clone)]
pub struct MiningConfig {
    /// Thread index (for logging).
    pub thread_id: u32,
    /// Maximum VQE attempts per block.
    pub max_attempts: usize,
}

impl Default for MiningConfig {
    fn default() -> Self {
        Self {
            thread_id: 0,
            max_attempts: MAX_ATTEMPTS,
        }
    }
}

/// Trait abstracting the node client for reading chain state.
///
/// This allows unit testing with mock clients.
pub trait ChainReader: Send + Sync {
    /// Get the best (latest) block hash.
    fn best_hash(&self) -> H256;
    /// Get the best block number.
    fn best_number(&self) -> u64;
    /// Get the parent hash of a given block.
    fn parent_hash(&self, hash: &H256) -> Option<H256>;
    /// Read the current difficulty from pallet storage.
    fn current_difficulty(&self, at: &H256) -> Option<u64>;
    /// Read the current block height from pallet-qbc-utxo storage.
    fn current_height(&self, at: &H256) -> Option<u64>;
}

/// Trait abstracting extrinsic submission.
pub trait ProofSubmitter: Send + Sync {
    /// Submit a mining proof extrinsic.
    fn submit_proof(
        &self,
        params: Vec<i64>,
        energy: i128,
        hamiltonian_seed: H256,
        n_qubits: u8,
    ) -> Result<H256, String>;
}

/// Run the mining loop. This is the main entry point spawned as a blocking task.
///
/// The loop continuously:
/// 1. Checks for a new block
/// 2. Derives the Hamiltonian
/// 3. Runs VQE optimization
/// 4. Submits proof if energy < difficulty
pub fn run_mining<C: ChainReader, S: ProofSubmitter>(
    client: Arc<C>,
    submitter: Arc<S>,
    config: MiningConfig,
) {
    let thread_id = config.thread_id;
    info!(
        target: "mining",
        "[miner-{}] VQE mining engine started (max {} attempts/block)",
        thread_id, config.max_attempts
    );

    let mut rng = ChaCha8Rng::from_entropy();
    let mut last_mined_height: u64 = 0;

    loop {
        // 1. Get current chain state
        let best_hash = client.best_hash();
        let best_number = client.best_number();

        // The mining target is the NEXT block
        let current_height = client
            .current_height(&best_hash)
            .unwrap_or(best_number);
        let mining_height = current_height + 1;

        // Skip if we already mined this height
        if mining_height <= last_mined_height {
            std::thread::sleep(POLL_INTERVAL);
            continue;
        }

        // 2. Read difficulty
        let difficulty = match client.current_difficulty(&best_hash) {
            Some(d) => d,
            None => {
                warn!(target: "mining", "[miner-{}] Could not read difficulty, retrying...", thread_id);
                std::thread::sleep(POLL_INTERVAL);
                continue;
            }
        };

        // 3. Get parent hash and derive Hamiltonian seed
        let parent_hash = match client.parent_hash(&best_hash) {
            Some(h) => h,
            None => {
                // For genesis block, parent hash is zero
                H256::zero()
            }
        };

        let seed = hamiltonian::derive_seed(&parent_hash, mining_height);
        let hamiltonian = hamiltonian::generate_hamiltonian(&seed);

        debug!(
            target: "mining",
            "[miner-{}] Mining height {} (difficulty={}e-6, seed={:?})",
            thread_id, mining_height, difficulty, seed
        );

        // 4. Run VQE optimization attempts
        let difficulty_f64 = difficulty as f64 / DIFFICULTY_SCALE;
        let start = Instant::now();
        let mut found = false;

        for attempt in 0..config.max_attempts {
            let result = vqe::optimize(&hamiltonian, &mut rng);

            if result.energy < difficulty_f64 {
                let elapsed = start.elapsed();
                info!(
                    target: "mining",
                    "[miner-{}] VQE solution found: energy={:.6} < difficulty={:.6} \
                     (attempt {}/{}, {:.1}ms)",
                    thread_id,
                    result.energy,
                    difficulty_f64,
                    attempt + 1,
                    config.max_attempts,
                    elapsed.as_secs_f64() * 1000.0
                );

                // 5. Scale and submit
                let scaled_params: Vec<i64> = result
                    .params
                    .iter()
                    .map(|&p| (p * ENERGY_SCALE) as i64)
                    .collect();
                let scaled_energy = (result.energy * ENERGY_SCALE) as i128;

                match submitter.submit_proof(scaled_params, scaled_energy, seed, 4) {
                    Ok(tx_hash) => {
                        info!(
                            target: "mining",
                            "[miner-{}] Mining proof submitted: tx_hash={:?}",
                            thread_id, tx_hash
                        );
                        last_mined_height = mining_height;
                        found = true;
                        break;
                    }
                    Err(e) => {
                        warn!(
                            target: "mining",
                            "[miner-{}] Failed to submit proof: {}",
                            thread_id, e
                        );
                    }
                }
            }

            // Check if a new block arrived (invalidates our work)
            if client.best_number() > best_number {
                debug!(
                    target: "mining",
                    "[miner-{}] New block arrived during mining, restarting",
                    thread_id
                );
                break;
            }
        }

        if !found {
            debug!(
                target: "mining",
                "[miner-{}] No solution found for height {} after {} attempts ({:.1}ms)",
                thread_id, mining_height, config.max_attempts, start.elapsed().as_secs_f64() * 1000.0
            );
        }

        // Brief pause before next iteration
        std::thread::sleep(POLL_INTERVAL);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::Mutex;

    struct MockClient {
        best_hash: H256,
        best_number: AtomicU64,
        parent_hash: H256,
        difficulty: u64,
        height: u64,
    }

    impl ChainReader for MockClient {
        fn best_hash(&self) -> H256 {
            self.best_hash
        }
        fn best_number(&self) -> u64 {
            self.best_number.load(Ordering::Relaxed)
        }
        fn parent_hash(&self, _hash: &H256) -> Option<H256> {
            Some(self.parent_hash)
        }
        fn current_difficulty(&self, _at: &H256) -> Option<u64> {
            Some(self.difficulty)
        }
        fn current_height(&self, _at: &H256) -> Option<u64> {
            Some(self.height)
        }
    }

    struct MockSubmitter {
        submissions: Mutex<Vec<(Vec<i64>, i128, H256, u8)>>,
    }

    impl ProofSubmitter for MockSubmitter {
        fn submit_proof(
            &self,
            params: Vec<i64>,
            energy: i128,
            seed: H256,
            n_qubits: u8,
        ) -> Result<H256, String> {
            self.submissions
                .lock()
                .unwrap()
                .push((params, energy, seed, n_qubits));
            Ok(H256::from([0xAA; 32]))
        }
    }

    #[test]
    fn test_mining_config_default() {
        let config = MiningConfig::default();
        assert_eq!(config.thread_id, 0);
        assert_eq!(config.max_attempts, MAX_ATTEMPTS);
    }

    #[test]
    fn test_energy_scaling() {
        let energy = -0.5_f64;
        let scaled = (energy * ENERGY_SCALE) as i128;
        assert_eq!(scaled, -500_000_000_000);
    }

    #[test]
    fn test_difficulty_comparison() {
        // Difficulty 1_000_000 (= 1.0 in pallet) should be 1.0 as f64
        let difficulty: u64 = 1_000_000;
        let diff_f64 = difficulty as f64 / DIFFICULTY_SCALE;
        assert!((diff_f64 - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_hamiltonian_seed_derivation_matches_pallet() {
        // Verify our seed derivation matches the pallet's logic
        use sha2::{Digest, Sha256};
        let parent = H256::from([0x42u8; 32]);
        let height: u64 = 100;

        let seed = hamiltonian::derive_seed(&parent, height);

        // Manual computation
        let mut hasher = Sha256::new();
        hasher.update(b"hamiltonian-seed-v1:");
        hasher.update(parent.as_bytes());
        hasher.update(&height.to_le_bytes());
        let expected = H256::from_slice(&hasher.finalize());

        assert_eq!(seed, expected);
    }
}
