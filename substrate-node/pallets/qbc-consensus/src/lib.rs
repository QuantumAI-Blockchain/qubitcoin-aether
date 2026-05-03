//! Pallet QBC Consensus — VQE proof validation and difficulty adjustment.
//!
//! Implements Qubitcoin's Proof-of-SUSY-Alignment (PoSA) consensus:
//! - Validate VQE mining proofs (energy < difficulty_target)
//! - Adjust difficulty every block (144-block window, ±10% max)
//! - Higher difficulty = easier mining (inverse of PoW)
//! - Create coinbase UTXOs via pallet-qbc-utxo
//! - Store Hamiltonian solutions in SUSY database
//!
//! Mining proofs are submitted as UNSIGNED extrinsics with an embedded
//! Ed25519 signature binding the miner's identity to their VQE work.
//! This means miners never need pre-existing balance — the proof IS the work.
//!
//! FORK-PREVENTION: Seed derivation, coinbase txid, and difficulty adjustment
//! are aligned with the Python node (consensus/engine.py) to prevent chain forks
//! when both node implementations co-exist on the network.

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;
pub mod weights;

#[cfg(test)]
mod tests;

#[cfg(feature = "runtime-benchmarks")]
mod benchmarks;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_support::traits::Time;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::*;
    use sp_core::H256;
    use sp_runtime::BoundedVec;
    use crate::weights::WeightInfo;
    use sp_runtime::transaction_validity::{
        InvalidTransaction, TransactionPriority, TransactionSource, TransactionValidity,
        ValidTransaction,
    };

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
    /// Height 215469: difficulty hit old floor (0.5) due to equivocation-induced
    /// fast blocks, making Hamiltonians with positive eigenvalues unsolvable.
    /// Reset to INITIAL_DIFFICULTY (1.0) to resume block production.
    pub const DIFFICULTY_RESET_HEIGHT_215469: u64 = 215_469;

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
        /// Weight information for extrinsics in this pallet.
        type WeightInfo: crate::weights::WeightInfo;
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
    /// MAX_RECENT_PROOF_HASHES recent proof hashes. Indexed by
    /// (block_height, proof_hash) so that pruning old heights is O(k)
    /// via `remove_prefix` instead of iterating all entries.
    #[pallet::storage]
    #[pallet::getter(fn recent_proof_hash)]
    pub type RecentProofHashes<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        u64,   // block_height when submitted
        Blake2_128Concat,
        H256,  // proof_hash
        (),
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

    // ── SUGRA Bimetric Consensus State ────────────────────────────────

    /// Current network bimetric phase θ (scaled by 10^12, radians).
    /// Advances by THETA_ADVANCE_PER_BLOCK each block.
    /// This creates a rotating energy landscape that miners must track.
    #[pallet::storage]
    #[pallet::getter(fn network_theta)]
    pub type NetworkTheta<T: Config> = StorageValue<_, i64, ValueQuery>;

    /// Current network geometric coupling α (scaled by 10^12).
    /// Exponential moving average of recent mining solutions' phase alignment
    /// with the Sephirot cognitive geometry.
    #[pallet::storage]
    #[pallet::getter(fn network_alpha)]
    pub type NetworkAlpha<T: Config> = StorageValue<_, i64, ValueQuery>;

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
        /// Network bimetric phase advanced.
        PhaseAdvanced {
            block_height: u64,
            theta: i64,
            alpha: i64,
            active_sephirot: u8,
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
        /// Ed25519 signature over the mining proof is invalid.
        InvalidMinerSignature,
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
        /// Submit a VQE mining proof (UNSIGNED — no fees required).
        ///
        /// The miner proves their identity via an Ed25519 signature embedded
        /// in the call data, binding their public key to the VQE work. The
        /// miner's QBC address is derived from this public key.
        ///
        /// Validates:
        /// 1. Ed25519 signature binds miner identity to proof
        /// 2. Hamiltonian seed matches derived value from previous block hash
        /// 3. Ground state energy < current difficulty threshold
        /// 4. VQE parameters are valid (n_qubits > 0, non-empty params)
        /// 5. Proof is unique (not a replay of a previous proof)
        /// 6. Rate limiting: one proof per block per miner
        /// 7. VQE energy re-verification (recompute from params + seed)
        ///
        /// On success:
        /// - Creates coinbase UTXO for miner
        /// - Adjusts difficulty using chain timestamp (not user-supplied)
        /// - Stores SUSY solution
        #[pallet::call_index(0)]
        #[pallet::weight((<T as crate::pallet::Config>::WeightInfo::submit_mining_proof(), DispatchClass::Normal, Pays::No))]
        pub fn submit_mining_proof(
            origin: OriginFor<T>,
            vqe_proof: VqeProof,
            miner_public_key: [u8; 32],
            miner_signature: [u8; 64],
        ) -> DispatchResult {
            ensure_none(origin)?;

            // ── Ed25519 Signature Verification ────────────────────────────
            // The miner signs the proof data with their Ed25519 key, binding
            // their identity to the VQE work. This prevents proof theft where
            // an attacker intercepts a broadcast proof and resubmits it with
            // their own address.
            let msg = Self::mining_proof_signing_message(&vqe_proof);
            let sig = sp_core::ed25519::Signature::from_raw(miner_signature);
            let pubkey = sp_core::ed25519::Public::from_raw(miner_public_key);
            ensure!(
                sp_io::crypto::ed25519_verify(&sig, &msg, &pubkey),
                Error::<T>::InvalidMinerSignature
            );

            // Derive miner address from public key (SHA-256, matches pallet convention)
            let miner_address = Self::pubkey_to_address(&miner_public_key);
            let block_height = pallet_qbc_utxo::Pallet::<T>::current_height() + 1;
            let difficulty = CurrentDifficulty::<T>::get();

            // ── VQE Parameter Validation ─────────────────────────────────
            ensure!(
                vqe_proof.n_qubits > 0,
                Error::<T>::InvalidVqeParams
            );
            ensure!(
                !vqe_proof.params.is_empty(),
                Error::<T>::InvalidVqeParams
            );

            // ── Hamiltonian Seed Verification ────────────────────────────
            let expected_seed = Self::derive_hamiltonian_seed(block_height);
            log::info!(
                target: "runtime::consensus",
                "Seed check: height={}, expected={:?}, submitted={:?}, parent={:?}, match={}",
                block_height, expected_seed, vqe_proof.hamiltonian_seed,
                <frame_system::Pallet<T>>::parent_hash(),
                vqe_proof.hamiltonian_seed == expected_seed
            );
            ensure!(
                vqe_proof.hamiltonian_seed == expected_seed,
                Error::<T>::InvalidHamiltonianSeed
            );

            // ── Replay Prevention ────────────────────────────────────────
            let proof_hash = Self::compute_proof_hash(&vqe_proof, &miner_address, block_height);
            ensure!(
                !RecentProofHashes::<T>::contains_key(block_height, &proof_hash),
                Error::<T>::DuplicateProof
            );

            // ── Rate Limiting ────────────────────────────────────────────
            let last_block = LastMinerBlock::<T>::get(&miner_address);
            ensure!(
                block_height > last_block,
                Error::<T>::MinerRateLimited
            );

            // ── Energy Threshold Check ───────────────────────────────────
            let difficulty_threshold = (difficulty as i128) * 1_000_000;
            let tolerance_scaled = (ENERGY_VALIDATION_TOLERANCE as i128) * 1_000_000;
            ensure!(
                vqe_proof.energy < difficulty_threshold.saturating_add(tolerance_scaled),
                Error::<T>::EnergyAboveDifficulty
            );

            // ── VQE Proof Re-Verification ─────────────────────────────────
            // The runtime is the sole authority on energy computation.
            // The miner submits params; the runtime recomputes energy itself
            // and checks computed_energy < difficulty. This eliminates FP
            // divergence between native (mining) and WASM (runtime) execution.
            let params_vec: sp_std::vec::Vec<i64> = vqe_proof.params.to_vec();
            let theta = NetworkTheta::<T>::get();
            let computed_energy = vqe_verifier::compute_energy_versioned(
                &expected_seed,
                &params_vec,
                theta,
                HAMILTONIAN_V2,
            );
            let computed_energy = match computed_energy {
                Some(e) => e,
                None => {
                    log::error!(
                        target: "runtime",
                        "VQE VERIFY FAILED: invalid params, height={}, seed={:?}",
                        block_height, expected_seed
                    );
                    return Err(Error::<T>::InvalidVqeParams.into());
                }
            };
            log::info!(
                target: "runtime::consensus",
                "VQE verify: height={}, computed_energy={}, difficulty_threshold={}, theta={}",
                block_height, computed_energy, difficulty_threshold, theta
            );
            ensure!(
                computed_energy < difficulty_threshold,
                Error::<T>::EnergyAboveDifficulty
            );

            // ── Advance Network Bimetric Phase ───────────────────────────
            // θ advances by THETA_ADVANCE_PER_BLOCK each block (golden angle / 100).
            // This creates a slowly rotating energy landscape that miners track.
            let new_theta = (theta + THETA_ADVANCE_PER_BLOCK) % TWO_PI_SCALED;
            NetworkTheta::<T>::put(new_theta);

            // Compute geometric weight of this solution and update network α
            // via exponential moving average (α = 0.9·α_old + 0.1·α_block).
            let alpha_block = bimetric_physics::coupling::geometric_weight_from_scaled(
                &params_vec,
            );
            let alpha_scaled = (alpha_block * BIMETRIC_SCALE as f64) as i64;
            let old_alpha = NetworkAlpha::<T>::get();
            let new_alpha = (old_alpha * 9 + alpha_scaled) / 10;
            NetworkAlpha::<T>::put(new_alpha);

            // Determine active Sephirot (closest phase to current θ)
            let theta_f64 = new_theta as f64 / BIMETRIC_SCALE as f64;
            let active_sephirot = bimetric_physics::sephirot::active_sephirot(theta_f64);

            // ── Chain Timestamp ──────────────────────────────────────────
            let chain_timestamp_ms = pallet_timestamp::Pallet::<T>::now();

            // Calculate reward and include accumulated transaction fees
            let reward = pallet_qbc_economics::Pallet::<T>::calculate_reward(block_height);
            pallet_qbc_economics::Pallet::<T>::on_block_authored(block_height);
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

            // Store SUSY solution with runtime-computed energy (authoritative)
            let mut verified_proof = vqe_proof.clone();
            verified_proof.energy = computed_energy;
            SusySolutions::<T>::insert(block_height, &verified_proof);
            if block_height > SUSY_RETENTION_WINDOW {
                SusySolutions::<T>::remove(block_height.saturating_sub(SUSY_RETENTION_WINDOW));
            }

            // Store proof hash for replay prevention and prune if over limit.
            // The double-map is keyed by (block_height, proof_hash) so pruning
            // an entire height is O(k) via remove_prefix instead of full iteration.
            RecentProofHashes::<T>::insert(block_height, &proof_hash, ());
            RecentProofHashCount::<T>::mutate(|count| {
                *count = count.saturating_add(1);

                while *count > MAX_RECENT_PROOF_HASHES {
                    let oldest = ProofHashOldestBlock::<T>::get();
                    // Remove all entries at the oldest tracked height — O(k)
                    let result = RecentProofHashes::<T>::clear_prefix(oldest, u32::MAX, None);
                    let removed = result.unique.saturating_add(result.loops);
                    if removed > 0 {
                        *count = count.saturating_sub(removed);
                    }
                    ProofHashOldestBlock::<T>::put(oldest.saturating_add(1));
                    if removed == 0 {
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
                energy: computed_energy,
                difficulty,
                reward: total_reward,
            });

            Self::deposit_event(Event::SusySolutionStored {
                block_height,
                energy: computed_energy,
                n_qubits: vqe_proof.n_qubits,
            });

            Self::deposit_event(Event::PhaseAdvanced {
                block_height,
                theta: new_theta,
                alpha: new_alpha,
                active_sephirot,
            });

            Ok(())
        }
    }

    // ── ValidateUnsigned ─────────────────────────────────────────────────
    // Mining proofs are unsigned extrinsics. The miner's Ed25519 signature
    // embedded in the call data provides authentication without requiring
    // any on-chain balance for transaction fees.

    #[pallet::validate_unsigned]
    impl<T: Config> ValidateUnsigned for Pallet<T> {
        type Call = Call<T>;

        fn validate_unsigned(_source: TransactionSource, call: &Self::Call) -> TransactionValidity {
            let Call::submit_mining_proof {
                vqe_proof,
                miner_public_key,
                miner_signature,
            } = call else {
                return InvalidTransaction::Call.into();
            };

            // 1. Basic parameter validation (cheap, no storage reads)
            if vqe_proof.n_qubits == 0 || vqe_proof.params.is_empty() {
                return InvalidTransaction::Custom(1).into();
            }

            // 2. Verify Ed25519 signature — proves miner identity
            let msg = Pallet::<T>::mining_proof_signing_message(vqe_proof);
            let sig = sp_core::ed25519::Signature::from_raw(*miner_signature);
            let pubkey = sp_core::ed25519::Public::from_raw(*miner_public_key);
            if !sp_io::crypto::ed25519_verify(&sig, &msg, &pubkey) {
                return InvalidTransaction::BadProof.into();
            }

            // 3. Energy plausibility check (lightweight — real check in dispatch)
            // The miner's claimed energy may differ from the runtime's computation
            // due to native vs WASM FP differences. Allow generous margin here;
            // the dispatch will recompute and do the authoritative check.
            let difficulty = CurrentDifficulty::<T>::get();
            let difficulty_threshold = (difficulty as i128) * 1_000_000;
            // Allow 1.0 scaled energy margin for tx pool admission
            let pool_margin: i128 = 1_000_000_000_000;
            if vqe_proof.energy >= difficulty_threshold.saturating_add(pool_margin) {
                return InvalidTransaction::Custom(2).into();
            }

            // NOTE: Hamiltonian seed verification is SKIPPED here because
            // parent_hash() during tx pool validation returns the parent of the
            // best block (H-1), not the parent of the block being mined (H).
            // The seed is fully validated during dispatch (inside block execution)
            // where parent_hash() correctly returns the mining block's parent.

            // 4. Rate limiting — one proof per block per miner
            let block_height = pallet_qbc_utxo::Pallet::<T>::current_height() + 1;
            let miner_address = Pallet::<T>::pubkey_to_address(miner_public_key);
            let last_block = LastMinerBlock::<T>::get(&miner_address);
            if block_height <= last_block {
                return InvalidTransaction::Stale.into();
            }

            // Valid — highest priority, propagate to peers
            ValidTransaction::with_tag_prefix("QbcMiningProof")
                .priority(TransactionPriority::MAX)
                .longevity(5)
                .and_provides(("mining_proof", block_height, miner_address))
                .propagate(true)
                .build()
        }
    }

    impl<T: Config> Pallet<T> {
        /// Build the message that the miner must sign with Ed25519.
        /// Deterministic serialization of all proof fields.
        pub(crate) fn mining_proof_signing_message(proof: &VqeProof) -> sp_std::vec::Vec<u8> {
            let mut msg = sp_std::vec::Vec::new();
            msg.extend_from_slice(b"qbc-mining-v1:");
            msg.extend_from_slice(proof.hamiltonian_seed.as_bytes());
            msg.extend_from_slice(&proof.energy.to_le_bytes());
            for p in proof.params.iter() {
                msg.extend_from_slice(&p.to_le_bytes());
            }
            msg.push(proof.n_qubits);
            msg
        }

        /// Derive a QBC Address from an Ed25519 public key.
        /// SHA-256 of the raw 32-byte public key (same as account_to_address
        /// since AccountId32 SCALE-encodes as raw 32 bytes).
        pub(crate) fn pubkey_to_address(pubkey: &[u8; 32]) -> Address {
            use sp_core::hashing::sha2_256;
            Address(sha2_256(pubkey))
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
            let hex_str = Self::bytes_to_hex(parent_hash.as_ref());
            let mut data = sp_std::vec::Vec::new();
            data.extend_from_slice(&hex_str);
            data.push(b':');
            let height_str = Self::u64_to_decimal_bytes(block_height);
            data.extend_from_slice(&height_str);
            H256::from(sha2_256(&data))
        }

        /// Compute a unique hash of the mining proof for replay prevention.
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
            if block_height == DIFFICULTY_RESET_HEIGHT_167
                || block_height == DIFFICULTY_RESET_HEIGHT_724
                || block_height == DIFFICULTY_RESET_HEIGHT_2750
                || block_height == DIFFICULTY_RESET_HEIGHT_215469
            {
                let old_difficulty = CurrentDifficulty::<T>::get();
                CurrentDifficulty::<T>::put(INITIAL_DIFFICULTY);
                Pallet::<T>::deposit_event(Event::DifficultyAdjusted {
                    old_difficulty,
                    new_difficulty: INITIAL_DIFFICULTY,
                    block_height,
                });
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
                    if !timestamps.is_empty() {
                        timestamps.remove(0);
                    }
                    let _ = timestamps.try_push(timestamp_ms);
                }

                let len = timestamps.len();
                if len < 2 {
                    return;
                }

                let window_size = len.min(DIFFICULTY_WINDOW as usize);
                let oldest = timestamps[len - window_size];
                let newest = timestamps[len - 1];
                let actual_time_ms = newest.saturating_sub(oldest);

                let expected_time_ms = (window_size as u64 - 1) * TARGET_BLOCK_TIME_MS;

                if expected_time_ms == 0 {
                    return;
                }

                let ratio_100 = (actual_time_ms * 100) / expected_time_ms;

                let old_difficulty = CurrentDifficulty::<T>::get();

                // ── Meaningful-max guard (fork-prevention) ─────────────
                let ratio_100 = if ratio_100 > 100 && old_difficulty > DIFFICULTY_MEANINGFUL_MAX {
                    100
                } else {
                    ratio_100
                };

                // Clamp to ±10%
                let clamped = ratio_100.max(MIN_ADJUSTMENT_FACTOR as u64).min(MAX_ADJUSTMENT_FACTOR as u64);

                let new_difficulty = (old_difficulty as u128 * clamped as u128 / 100) as u64;

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
        pub(crate) fn coinbase_txid(block_height: u64) -> H256 {
            use sp_core::hashing::sha2_256;
            let parent_hash = <frame_system::Pallet<T>>::parent_hash();
            let hex_str = Self::bytes_to_hex(parent_hash.as_ref());
            let mut data = sp_std::vec::Vec::new();
            data.extend_from_slice(b"coinbase-");
            let height_str = Self::u64_to_decimal_bytes(block_height);
            data.extend_from_slice(&height_str);
            data.push(b'-');
            data.extend_from_slice(&hex_str);
            H256::from(sha2_256(&data))
        }

        /// Convert a byte slice to lowercase hex string (no_std compatible).
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
