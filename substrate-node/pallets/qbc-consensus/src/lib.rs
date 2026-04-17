//! Pallet QBC Consensus — VQE proof validation and difficulty adjustment.
//!
//! Implements Qubitcoin's Proof-of-SUSY-Alignment (PoSA) consensus:
//! - Validate VQE mining proofs (energy < difficulty_target)
//! - Adjust difficulty every block (144-block window, ±10% max)
//! - Higher difficulty = easier mining (inverse of PoW)
//! - Create coinbase UTXOs via pallet-qbc-utxo
//! - Store Hamiltonian solutions in SUSY database
//!
//! FORK-PREVENTION: Seed derivation, coinbase txid, and difficulty adjustment
//! are aligned with the Python node (consensus/engine.py) to prevent chain forks
//! when both node implementations co-exist on the network.

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

#[cfg(test)]
mod tests;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_support::traits::Time;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::*;
    use sp_core::H256;
    use sp_runtime::BoundedVec;

    /// Maximum VQE parameters per proof.
    pub const MAX_VQE_PARAMS: u32 = 32;

    /// Number of blocks of SUSY solutions to retain. Older entries are pruned
    /// to prevent unbounded storage growth.
    pub const SUSY_RETENTION_WINDOW: u64 = 100_000;

    // ── Fork-Prevention Constants (must match Python node) ─────────────

    /// One-time difficulty reset heights from the Python node's consensus history.
    /// These correct historical difficulty anomalies and MUST be replicated exactly
    /// to stay in consensus with the Python chain.
    ///
    /// Height 167: ground state energy fix caused difficulty to diverge.
    /// Height 724: ratio inversion bug was fixed, difficulty reset needed.
    /// Height 2750: ceiling runaway where difficulty spiraled out of control.
    pub const DIFFICULTY_RESET_HEIGHT_167: u64 = 167;
    pub const DIFFICULTY_RESET_HEIGHT_724: u64 = 724;
    pub const DIFFICULTY_RESET_HEIGHT_2750: u64 = 2750;

    /// Difficulty floor: 0.5 scaled by 10^6. Prevents difficulty from dropping
    /// so low that mining becomes impossibly hard (remember: higher = easier).
    pub const DIFFICULTY_FLOOR: u64 = 500_000;

    /// Difficulty ceiling: 1000.0 scaled by 10^6. Prevents difficulty from
    /// climbing so high that block validation becomes trivial.
    pub const DIFFICULTY_CEILING: u64 = 1_000_000_000;

    /// Meaningful-max guard threshold: 10.0 scaled by 10^6. When ratio > 100
    /// (meaning "raise difficulty") AND current difficulty already exceeds this
    /// value, hold steady to prevent runaway when mining is compute-bound.
    pub const DIFFICULTY_MEANINGFUL_MAX: u64 = 10_000_000;

    /// Energy validation tolerance: 1e-3 scaled by 10^6 = 1000. When re-computing
    /// the VQE energy, allow a small tolerance for floating-point drift between
    /// the Python and Substrate nodes.
    pub const ENERGY_VALIDATION_TOLERANCE: i128 = 1_000;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config:
        frame_system::Config
        + pallet_qbc_economics::Config
        + pallet_qbc_utxo::Config
        + pallet_timestamp::Config<Moment = u64>
    {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
    }

    /// Current difficulty (scaled by 10^6; higher = easier).
    #[pallet::storage]
    #[pallet::getter(fn current_difficulty)]
    pub type CurrentDifficulty<T: Config> = StorageValue<_, Difficulty, ValueQuery>;

    /// Block timestamps for difficulty adjustment window.
    /// Stores last DIFFICULTY_WINDOW block timestamps (milliseconds).
    #[pallet::storage]
    #[pallet::getter(fn block_timestamps)]
    pub type BlockTimestamps<T: Config> = StorageValue<
        _,
        BoundedVec<u64, ConstU32<{ DIFFICULTY_WINDOW + 1 }>>,
        ValueQuery,
    >;

    /// Last miner address (for coinbase creation).
    #[pallet::storage]
    #[pallet::getter(fn last_miner)]
    pub type LastMiner<T: Config> = StorageValue<_, Address, OptionQuery>;

    /// Total blocks mined.
    #[pallet::storage]
    #[pallet::getter(fn blocks_mined)]
    pub type BlocksMined<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// SUSY solution database — solved Hamiltonians indexed by block height.
    #[pallet::storage]
    #[pallet::getter(fn susy_solution)]
    pub type SusySolutions<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        u64,  // block_height
        VqeProof,
        OptionQuery,
    >;

    /// Maximum number of recent proof hashes retained for replay prevention.
    /// Proofs older than this many blocks are implicitly expired because the
    /// block_height component of the hash makes them unique to their target height.
    pub const MAX_RECENT_PROOF_HASHES: u32 = 1000;

    /// Recent proof hashes — prevents replay attacks by storing up to
    /// MAX_RECENT_PROOF_HASHES recent proof hashes. This replaces the old
    /// single-hash approach that only caught consecutive duplicates.
    #[pallet::storage]
    #[pallet::getter(fn recent_proof_hash)]
    pub type RecentProofHashes<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        H256,  // proof_hash
        u64,   // block_height when submitted
        OptionQuery,
    >;

    /// Count of entries in RecentProofHashes for bounded cleanup.
    #[pallet::storage]
    pub type RecentProofHashCount<T: Config> = StorageValue<_, u32, ValueQuery>;

    /// Oldest block height tracked in RecentProofHashes — for efficient pruning.
    #[pallet::storage]
    pub type ProofHashOldestBlock<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Last block height at which each miner submitted a proof — rate limiting.
    #[pallet::storage]
    #[pallet::getter(fn last_miner_block)]
    pub type LastMinerBlock<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        Address,
        u64,
        ValueQuery,
    >;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// A mining proof was validated and accepted.
        BlockMined {
            block_height: u64,
            miner: Address,
            energy: i128,
            difficulty: Difficulty,
            reward: QbcBalance,
        },
        /// Difficulty was adjusted.
        DifficultyAdjusted {
            old_difficulty: Difficulty,
            new_difficulty: Difficulty,
            block_height: u64,
        },
        /// SUSY solution stored in scientific database.
        SusySolutionStored {
            block_height: u64,
            energy: i128,
            n_qubits: u8,
        },
    }

    #[pallet::error]
    pub enum Error<T> {
        /// VQE energy does not meet difficulty threshold.
        EnergyAboveDifficulty,
        /// Hamiltonian seed doesn't match expected value.
        InvalidHamiltonianSeed,
        /// Invalid VQE parameters.
        InvalidVqeParams,
        /// Miner address is invalid.
        InvalidMinerAddress,
        /// Duplicate mining proof (replay attack prevention).
        DuplicateProof,
        /// Rate limited — only one mining proof per block per miner.
        MinerRateLimited,
        /// VQE energy re-verification failed — submitted energy does not match
        /// re-computation from the submitted parameters and Hamiltonian seed.
        EnergyVerificationFailed,
    }

    #[pallet::genesis_config]
    #[derive(frame_support::DefaultNoBound)]
    pub struct GenesisConfig<T: Config> {
        /// Initial difficulty (default: 1_000_000 = 1.0).
        pub initial_difficulty: Difficulty,
        #[serde(skip)]
        pub _phantom: core::marker::PhantomData<T>,
    }

    #[pallet::genesis_build]
    impl<T: Config> BuildGenesisConfig for GenesisConfig<T> {
        fn build(&self) {
            CurrentDifficulty::<T>::put(self.initial_difficulty);
        }
    }

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Submit a VQE mining proof.
        ///
        /// Validates:
        /// 1. Hamiltonian seed matches derived value from previous block hash
        /// 2. Ground state energy < current difficulty threshold
        /// 3. VQE parameters are valid (n_qubits > 0, non-empty params)
        /// 4. Proof is unique (not a replay of a previous proof)
        /// 5. Rate limiting: one proof per block per miner
        ///
        /// On success:
        /// - Creates coinbase UTXO for miner
        /// - Adjusts difficulty using chain timestamp (not user-supplied)
        /// - Stores SUSY solution
        #[pallet::call_index(0)]
        // Analytical weight: VQE proof validation (100µs) + Hamiltonian verification (200µs)
        // + difficulty read (25µs) + coinbase UTXO write (25µs) + SUSY solution write (25µs)
        // + difficulty adjustment (50µs) + proof hash check (25µs) + rate limit check (25µs)
        // + fee accumulation read+reset (50µs) + SUSY pruning (25µs)
        // + 9 storage writes (225µs) = ~750µs ≈ 750_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(750_000)]
        pub fn submit_mining_proof(
            origin: OriginFor<T>,
            _miner_address: Address,
            vqe_proof: VqeProof,
        ) -> DispatchResult {
            // SECURITY: Derive miner_address from the transaction origin.
            // The submitter IS the miner — they cannot submit on behalf of
            // someone else. The `_miner_address` parameter is kept for API
            // compatibility but is ignored; the canonical address is derived
            // from the caller's AccountId.
            let caller = ensure_signed(origin)?;
            let miner_address = Self::account_to_address(&caller);

            let block_height = pallet_qbc_utxo::Pallet::<T>::current_height() + 1;
            let difficulty = CurrentDifficulty::<T>::get();

            // ── VQE Parameter Validation ─────────────────────────────────
            // Reject proofs with no qubits or empty parameter vectors
            ensure!(
                vqe_proof.n_qubits > 0,
                Error::<T>::InvalidVqeParams
            );
            ensure!(
                !vqe_proof.params.is_empty(),
                Error::<T>::InvalidVqeParams
            );

            // ── Hamiltonian Seed Verification ────────────────────────────
            // The seed must be deterministically derived from the parent block hash.
            // This prevents miners from choosing a favorable Hamiltonian.
            let expected_seed = Self::derive_hamiltonian_seed(block_height);
            ensure!(
                vqe_proof.hamiltonian_seed == expected_seed,
                Error::<T>::InvalidHamiltonianSeed
            );

            // ── Replay Prevention ────────────────────────────────────────
            // Compute a unique hash of this proof and check against the set of
            // recent proof hashes (last MAX_RECENT_PROOF_HASHES entries).
            // This prevents replay of ANY recent proof, not just the last one.
            let proof_hash = Self::compute_proof_hash(&vqe_proof, &miner_address, block_height);
            ensure!(
                !RecentProofHashes::<T>::contains_key(&proof_hash),
                Error::<T>::DuplicateProof
            );

            // ── Rate Limiting ────────────────────────────────────────────
            // Only one mining proof per block height per miner
            let last_block = LastMinerBlock::<T>::get(&miner_address);
            ensure!(
                block_height > last_block,
                Error::<T>::MinerRateLimited
            );

            // ── Energy Threshold Check ───────────────────────────────────
            // Energy is negative (ground state), difficulty is positive.
            // energy (scaled by 10^12) must be < difficulty (scaled by 10^6) * 10^6
            //
            // FORK-PREVENTION: Energy validation tolerance (matches Python node).
            // When the Substrate node re-computes VQE energy to verify a proof
            // from the Python node, floating-point drift between Qiskit versions
            // or platform differences can cause small energy discrepancies.
            // ENERGY_VALIDATION_TOLERANCE (1e-3 scaled to 10^6 = 1000) provides
            // slack: abs(submitted_energy - recomputed_energy) <= tolerance is
            // acceptable. For the threshold check, we add the tolerance to the
            // threshold so borderline proofs from the Python node are not
            // rejected due to rounding differences.
            let difficulty_threshold = (difficulty as i128) * 1_000_000;
            let tolerance_scaled = (ENERGY_VALIDATION_TOLERANCE as i128) * 1_000_000; // scale to 10^12
            ensure!(
                vqe_proof.energy < difficulty_threshold.saturating_add(tolerance_scaled),
                Error::<T>::EnergyAboveDifficulty
            );

            // ── VQE Proof Re-Verification ─────────────────────────────────
            // Re-derive the Hamiltonian from the seed, apply the submitted
            // parameters to the ansatz, and verify the computed energy matches
            // the claimed energy within tolerance.  This prevents malicious
            // miners from submitting arbitrary energy values below threshold.
            let params_vec: sp_std::vec::Vec<i64> = vqe_proof.params.to_vec();
            ensure!(
                vqe_verifier::verify_energy(
                    &expected_seed,
                    &params_vec,
                    vqe_proof.energy,
                ),
                Error::<T>::EnergyVerificationFailed
            );

            // ── Chain Timestamp ──────────────────────────────────────────
            // Use the chain's timestamp from pallet_timestamp instead of any
            // user-supplied value. This prevents timestamp manipulation attacks
            // that could skew difficulty adjustment.
            let chain_timestamp_ms = pallet_timestamp::Pallet::<T>::now();

            // Calculate reward and include accumulated transaction fees
            let reward = pallet_qbc_economics::Pallet::<T>::calculate_reward(block_height);
            pallet_qbc_economics::Pallet::<T>::on_block_authored(block_height);
            // Finalize fees with 50% burn — returns the miner's share (50%)
            let miner_fee_share = pallet_qbc_utxo::Pallet::<T>::finalize_fees_with_burn();
            let total_reward = reward.saturating_add(miner_fee_share);

            // Create coinbase UTXO (block reward + miner's fee share)
            let coinbase_txid = Self::coinbase_txid(block_height);
            pallet_qbc_utxo::Pallet::<T>::create_coinbase(
                coinbase_txid,
                miner_address.clone(),
                total_reward,
                block_height,
            );

            // Update block height
            pallet_qbc_utxo::Pallet::<T>::set_block_height(block_height);

            // Adjust difficulty using the chain timestamp (tamper-proof)
            Self::adjust_difficulty(chain_timestamp_ms, block_height);

            // Store SUSY solution and prune old entries beyond retention window
            SusySolutions::<T>::insert(block_height, &vqe_proof);
            if block_height > SUSY_RETENTION_WINDOW {
                SusySolutions::<T>::remove(block_height.saturating_sub(SUSY_RETENTION_WINDOW));
            }

            // Store proof hash for replay prevention and prune if over limit
            RecentProofHashes::<T>::insert(&proof_hash, block_height);
            RecentProofHashCount::<T>::mutate(|count| {
                *count = count.saturating_add(1);

                // Prune oldest entries if we exceed the limit.
                // We prune by removing entries from the oldest tracked block height
                // until we are back under the limit.
                while *count > MAX_RECENT_PROOF_HASHES {
                    let oldest = ProofHashOldestBlock::<T>::get();
                    // Remove all proof hashes at the oldest block height by
                    // iterating. In practice each block has 1 proof, so this is O(1).
                    let mut removed_any = false;
                    let mut to_remove = sp_std::vec::Vec::new();
                    for (hash, height) in RecentProofHashes::<T>::iter() {
                        if height <= oldest {
                            to_remove.push(hash);
                        }
                    }
                    for hash in &to_remove {
                        RecentProofHashes::<T>::remove(hash);
                        *count = count.saturating_sub(1);
                        removed_any = true;
                    }
                    if removed_any {
                        ProofHashOldestBlock::<T>::put(oldest.saturating_add(1));
                    } else {
                        // Safety: if nothing was removed, bump oldest to avoid infinite loop
                        ProofHashOldestBlock::<T>::put(oldest.saturating_add(1));
                        break;
                    }
                }
            });

            // Update rate limit tracker
            LastMinerBlock::<T>::insert(&miner_address, block_height);

            // Update counters
            LastMiner::<T>::put(miner_address.clone());
            BlocksMined::<T>::mutate(|n| *n = n.saturating_add(1));

            Self::deposit_event(Event::BlockMined {
                block_height,
                miner: miner_address,
                energy: vqe_proof.energy,
                difficulty,
                reward: total_reward,
            });

            Self::deposit_event(Event::SusySolutionStored {
                block_height,
                energy: vqe_proof.energy,
                n_qubits: vqe_proof.n_qubits,
            });

            Ok(())
        }
    }

    impl<T: Config> Pallet<T> {
        /// Convert a Substrate AccountId to a QBC Address.
        ///
        /// Uses the SCALE-encoded bytes of the AccountId and hashes them with
        /// SHA2-256 to produce a deterministic QBC address. Matches the same
        /// derivation used in pallet-qbc-reversibility.
        fn account_to_address(account: &T::AccountId) -> Address {
            use codec::Encode;
            use sp_core::hashing::sha2_256;
            let encoded = account.encode();
            Address(sha2_256(&encoded))
        }

        /// Derive the expected Hamiltonian seed from the parent block hash.
        ///
        /// FORK-PREVENTION: Must match Python exactly:
        ///   `hashlib.sha256(f"{prev_hash}:{height}".encode()).digest()`
        /// where prev_hash is the lowercase hex string of the parent block hash
        /// and height is the decimal string of the block height.
        ///
        /// Uses `frame_system::Pallet::parent_hash()` which returns the hash of the
        /// parent of the block currently being executed. This is tamper-proof because
        /// block hashes are committed by consensus before extrinsic execution.
        pub(crate) fn derive_hamiltonian_seed(block_height: u64) -> H256 {
            use sp_core::hashing::sha2_256;
            let parent_hash = <frame_system::Pallet<T>>::parent_hash();
            // Format: "{hex_of_parent_hash}:{block_height}" — matches Python's
            // f"{prev_hash}:{height}" where prev_hash is hex-encoded.
            let hex_str = Self::bytes_to_hex(parent_hash.as_ref());
            let mut data = sp_std::vec::Vec::new();
            data.extend_from_slice(&hex_str);
            data.push(b':');
            // Decimal string of block_height — matches Python's str(height)
            let height_str = Self::u64_to_decimal_bytes(block_height);
            data.extend_from_slice(&height_str);
            H256::from(sha2_256(&data))
        }

        /// Compute a unique hash of the mining proof for replay prevention.
        ///
        /// Includes the VQE proof data, miner address, and block height so that
        /// the same proof cannot be replayed at a different height or by a different miner.
        pub(crate) fn compute_proof_hash(proof: &VqeProof, miner: &Address, block_height: u64) -> H256 {
            use sp_core::hashing::sha2_256;
            let mut data = sp_std::vec::Vec::new();
            data.extend_from_slice(b"mining-proof-v1:");
            data.extend_from_slice(proof.hamiltonian_seed.as_bytes());
            data.extend_from_slice(&proof.energy.to_le_bytes());
            data.extend_from_slice(&[proof.n_qubits]);
            for p in proof.params.iter() {
                data.extend_from_slice(&p.to_le_bytes());
            }
            data.extend_from_slice(miner.as_ref());
            data.extend_from_slice(&block_height.to_le_bytes());
            H256::from(sha2_256(&data))
        }

        /// Adjust difficulty based on block timestamps.
        ///
        /// CRITICAL: Must match Python consensus/engine.py exactly.
        /// - ratio = actual_time / expected_time
        /// - Higher difficulty = easier mining (energy threshold more generous)
        /// - Slow blocks → raise difficulty (make easier)
        /// - Fast blocks → lower difficulty (make harder)
        /// - Clamped to ±10% per adjustment
        /// - Three one-time resets at heights 167, 724, 2750 (historical fixes)
        /// - Meaningful-max guard prevents runaway when compute-bound
        /// - Floor (0.5) and ceiling (1000.0) enforced
        pub(crate) fn adjust_difficulty(timestamp_ms: u64, block_height: u64) {
            // ── One-Time Difficulty Resets (fork-prevention) ────────────
            // These match the Python node's historical difficulty resets.
            // Without these, the Substrate node would diverge from the
            // existing chain at these exact heights.
            if block_height == DIFFICULTY_RESET_HEIGHT_167
                || block_height == DIFFICULTY_RESET_HEIGHT_724
                || block_height == DIFFICULTY_RESET_HEIGHT_2750
            {
                let old_difficulty = CurrentDifficulty::<T>::get();
                CurrentDifficulty::<T>::put(INITIAL_DIFFICULTY);
                Pallet::<T>::deposit_event(Event::DifficultyAdjusted {
                    old_difficulty,
                    new_difficulty: INITIAL_DIFFICULTY,
                    block_height,
                });
                // Still record the timestamp for future window calculations
                BlockTimestamps::<T>::mutate(|timestamps| {
                    if timestamps.try_push(timestamp_ms).is_err() {
                        if !timestamps.is_empty() {
                            timestamps.remove(0);
                        }
                        let _ = timestamps.try_push(timestamp_ms);
                    }
                });
                return;
            }

            // Add timestamp to window
            BlockTimestamps::<T>::mutate(|timestamps| {
                if timestamps.try_push(timestamp_ms).is_err() {
                    // Window full — remove oldest
                    if !timestamps.is_empty() {
                        timestamps.remove(0);
                    }
                    let _ = timestamps.try_push(timestamp_ms);
                }

                let len = timestamps.len();
                if len < 2 {
                    return;
                }

                // Calculate actual time for the window
                let window_size = len.min(DIFFICULTY_WINDOW as usize);
                let oldest = timestamps[len - window_size];
                let newest = timestamps[len - 1];
                let actual_time_ms = newest.saturating_sub(oldest);

                // Expected time: window_size * TARGET_BLOCK_TIME_MS
                let expected_time_ms = (window_size as u64 - 1) * TARGET_BLOCK_TIME_MS;

                if expected_time_ms == 0 {
                    return;
                }

                // ratio = actual / expected (scaled by 100)
                let ratio_100 = (actual_time_ms * 100) / expected_time_ms;

                let old_difficulty = CurrentDifficulty::<T>::get();

                // ── Meaningful-max guard (fork-prevention) ─────────────
                // When ratio > 100 (blocks are slow, want to raise difficulty)
                // AND difficulty is already above 10.0 (10_000_000 scaled),
                // hold steady. This prevents runaway difficulty when mining
                // is compute-bound rather than difficulty-bound.
                let ratio_100 = if ratio_100 > 100 && old_difficulty > DIFFICULTY_MEANINGFUL_MAX {
                    100 // Hold steady — do not raise further
                } else {
                    ratio_100
                };

                // Clamp to ±10%: ratio must be in [90, 110]
                let clamped = ratio_100.max(MIN_ADJUSTMENT_FACTOR as u64).min(MAX_ADJUSTMENT_FACTOR as u64);

                // new_difficulty = old_difficulty * clamped / 100
                let new_difficulty = (old_difficulty as u128 * clamped as u128 / 100) as u64;

                // ── Floor and ceiling (fork-prevention) ────────────────
                // Python has DIFFICULTY_FLOOR = 0.5 and DIFFICULTY_CEILING = 1000.0.
                // Scaled by 10^6: floor = 500_000, ceiling = 1_000_000_000.
                let new_difficulty = new_difficulty
                    .max(DIFFICULTY_FLOOR)
                    .min(DIFFICULTY_CEILING);

                if new_difficulty != old_difficulty {
                    CurrentDifficulty::<T>::put(new_difficulty);
                    Pallet::<T>::deposit_event(Event::DifficultyAdjusted {
                        old_difficulty,
                        new_difficulty,
                        block_height,
                    });
                }
            });
        }

        /// Generate deterministic coinbase transaction ID for a block.
        ///
        /// FORK-PREVENTION: Must match Python exactly:
        ///   `hashlib.sha256(f"coinbase-{height}-{prev_hash}".encode()).hexdigest()`
        /// where height is decimal and prev_hash is lowercase hex.
        pub(crate) fn coinbase_txid(block_height: u64) -> H256 {
            use sp_core::hashing::sha2_256;
            let parent_hash = <frame_system::Pallet<T>>::parent_hash();
            let hex_str = Self::bytes_to_hex(parent_hash.as_ref());
            // Format: "coinbase-{height}-{hex_of_parent_hash}"
            let mut data = sp_std::vec::Vec::new();
            data.extend_from_slice(b"coinbase-");
            let height_str = Self::u64_to_decimal_bytes(block_height);
            data.extend_from_slice(&height_str);
            data.push(b'-');
            data.extend_from_slice(&hex_str);
            H256::from(sha2_256(&data))
        }

        /// Convert a byte slice to lowercase hex string (no_std compatible).
        /// Produces the same output as Python's `bytes.hex()`.
        pub(crate) fn bytes_to_hex(bytes: &[u8]) -> sp_std::vec::Vec<u8> {
            const HEX_CHARS: &[u8; 16] = b"0123456789abcdef";
            let mut hex = sp_std::vec::Vec::with_capacity(bytes.len() * 2);
            for &b in bytes {
                hex.push(HEX_CHARS[(b >> 4) as usize]);
                hex.push(HEX_CHARS[(b & 0x0f) as usize]);
            }
            hex
        }

        /// Convert a u64 to its decimal ASCII representation (no_std compatible).
        /// Produces the same output as Python's `str(n)`.
        pub(crate) fn u64_to_decimal_bytes(mut n: u64) -> sp_std::vec::Vec<u8> {
            if n == 0 {
                return sp_std::vec![b'0'];
            }
            let mut digits = sp_std::vec::Vec::new();
            while n > 0 {
                digits.push(b'0' + (n % 10) as u8);
                n /= 10;
            }
            digits.reverse();
            digits
        }
    }
}
