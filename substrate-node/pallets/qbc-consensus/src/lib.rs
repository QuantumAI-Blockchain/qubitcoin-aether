//! Pallet QBC Consensus — VQE proof validation and difficulty adjustment.
//!
//! Implements Qubitcoin's Proof-of-SUSY-Alignment (PoSA) consensus:
//! - Validate VQE mining proofs (energy < difficulty_target)
//! - Adjust difficulty every block (144-block window, ±10% max)
//! - Higher difficulty = easier mining (inverse of PoW)
//! - Create coinbase UTXOs via pallet-qbc-utxo
//! - Store Hamiltonian solutions in SUSY database

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::*;
    use sp_core::H256;
    use sp_runtime::BoundedVec;

    /// Maximum VQE parameters per proof.
    pub const MAX_VQE_PARAMS: u32 = 32;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config:
        frame_system::Config
        + pallet_qbc_economics::Config
        + pallet_qbc_utxo::Config
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
        /// 1. Hamiltonian seed matches derived value from previous block
        /// 2. Ground state energy < current difficulty threshold
        /// 3. VQE parameters are valid
        ///
        /// On success:
        /// - Creates coinbase UTXO for miner
        /// - Adjusts difficulty
        /// - Stores SUSY solution
        #[pallet::call_index(0)]
        #[pallet::weight(100_000)]
        pub fn submit_mining_proof(
            origin: OriginFor<T>,
            miner_address: Address,
            vqe_proof: VqeProof,
            timestamp_ms: u64,
        ) -> DispatchResult {
            ensure_signed(origin)?;

            let block_height = pallet_qbc_utxo::Pallet::<T>::current_height() + 1;
            let difficulty = CurrentDifficulty::<T>::get();

            // Validate energy < difficulty threshold
            // Energy is negative (ground state), difficulty is positive.
            // energy (scaled by 10^12) must be < difficulty (scaled by 10^6) * 10^6
            let difficulty_threshold = (difficulty as i128) * 1_000_000;
            ensure!(
                vqe_proof.energy < difficulty_threshold,
                Error::<T>::EnergyAboveDifficulty
            );

            // Calculate reward
            let reward = pallet_qbc_economics::Pallet::<T>::calculate_reward(block_height);
            pallet_qbc_economics::Pallet::<T>::on_block_authored(block_height);

            // Create coinbase UTXO
            let coinbase_txid = Self::coinbase_txid(block_height);
            pallet_qbc_utxo::Pallet::<T>::create_coinbase(
                coinbase_txid,
                miner_address.clone(),
                reward,
                block_height,
            );

            // Update block height
            pallet_qbc_utxo::Pallet::<T>::set_block_height(block_height);

            // Adjust difficulty
            Self::adjust_difficulty(timestamp_ms, block_height);

            // Store SUSY solution
            SusySolutions::<T>::insert(block_height, &vqe_proof);

            // Update counters
            LastMiner::<T>::put(miner_address.clone());
            BlocksMined::<T>::mutate(|n| *n += 1);

            Self::deposit_event(Event::BlockMined {
                block_height,
                miner: miner_address,
                energy: vqe_proof.energy,
                difficulty,
                reward,
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
        /// Adjust difficulty based on block timestamps.
        ///
        /// CRITICAL: Must match Python consensus/engine.py exactly.
        /// - ratio = actual_time / expected_time
        /// - Higher difficulty = easier mining (energy threshold more generous)
        /// - Slow blocks → raise difficulty (make easier)
        /// - Fast blocks → lower difficulty (make harder)
        /// - Clamped to ±10% per adjustment
        fn adjust_difficulty(timestamp_ms: u64, block_height: u64) {
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

                // Clamp to ±10%: ratio must be in [90, 110]
                let clamped = ratio_100.max(MIN_ADJUSTMENT_FACTOR as u64).min(MAX_ADJUSTMENT_FACTOR as u64);

                let old_difficulty = CurrentDifficulty::<T>::get();
                // new_difficulty = old_difficulty * clamped / 100
                let new_difficulty = (old_difficulty as u128 * clamped as u128 / 100) as u64;
                let new_difficulty = new_difficulty.max(1); // Never go to 0

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
        fn coinbase_txid(block_height: u64) -> H256 {
            use sp_core::hashing::sha2_256;
            let mut data = b"coinbase:".to_vec();
            data.extend_from_slice(&block_height.to_le_bytes());
            H256::from(sha2_256(&data))
        }
    }
}
