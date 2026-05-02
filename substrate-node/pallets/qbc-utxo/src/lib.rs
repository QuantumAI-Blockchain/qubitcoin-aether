//! Pallet QBC UTXO — UTXO model for Qubitcoin.
//!
//! Implements the full UTXO transaction model:
//! - Store and query the UTXO set
//! - Validate transactions (inputs exist, signatures valid, amounts balance)
//! - Maintain address balance cache for fast lookups
//! - Coinbase creation for mining rewards
//! - Fee accumulation with 50% burn on block finalization
//!
//! # Cross-Node Compatibility (Substrate ↔ Python Node)
//!
//! ## Transaction ID (txid) Calculation
//! The Python node computes txids as:
//!   `SHA-256(json.dumps({"inputs": ..., "outputs": ..., "fee": ..., "timestamp": ...},
//!                        sort_keys=True).encode())`
//! using canonical JSON with `sort_keys=True, separators=(',', ':')`.
//!
//! The Substrate node uses SCALE-encoded raw byte concatenation (prev_txid || prev_vout
//! || address || amount) for txid computation. This is intentional — Substrate
//! transactions are SCALE-encoded natively and cannot efficiently produce canonical
//! JSON in a no_std environment.
//!
//! **This difference is handled at the P2P bridge layer** (`rust-p2p/` and
//! `qbc_p2p_bridge`). The bridge daemon translates between Python JSON format
//! and Substrate SCALE format when relaying transactions between node types.
//! Each node type independently validates transactions using its own txid scheme.
//!
//! ## Signing Message Format
//! Similarly, the Python node signs canonical JSON representations of transactions,
//! while Substrate signs raw SCALE-encoded bytes. The P2P bridge handles signature
//! re-wrapping when translating between node types. Both nodes verify Dilithium5
//! signatures against their respective message formats.
//!
//! ## Fee Model
//! Both nodes agree: `fee = sum(inputs) - sum(outputs)`.
//! On block finalization, 50% of accumulated fees are burned (removed from
//! circulation) and the remaining 50% go to the miner via the coinbase UTXO.
//! This deflationary mechanism matches the Python node's fee handling.

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

/// Trait for checking if a UTXO has been frozen by an external pallet
/// (e.g., the reversibility pallet). This provides loose coupling between
/// the UTXO pallet and the reversibility pallet.
pub trait UtxoFreezeChecker {
    /// Returns true if the UTXO identified by (txid, vout) has been frozen
    /// and should not be spent.
    fn is_frozen(txid: &sp_core::H256, vout: u32) -> bool;
}

/// Default implementation that never freezes anything.
/// Used when no reversibility pallet is configured.
///
/// WARNING: Default implementation never freezes UTXOs. Override in production runtime.
impl UtxoFreezeChecker for () {
    fn is_frozen(_txid: &sp_core::H256, _vout: u32) -> bool {
        false
    }
}

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::*;
    use sp_core::H256;
    use sp_runtime::BoundedVec;
    use crate::UtxoFreezeChecker;

    /// Maximum transaction inputs.
    pub const MAX_INPUTS: u32 = 256;
    /// Maximum transaction outputs.
    pub const MAX_OUTPUTS: u32 = 256;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config: frame_system::Config + pallet_qbc_dilithium::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
        /// Maximum inputs per transaction.
        #[pallet::constant]
        type MaxInputs: Get<u32>;
        /// Maximum outputs per transaction.
        #[pallet::constant]
        type MaxOutputs: Get<u32>;
        /// Optional freeze checker for cross-pallet UTXO freezing
        /// (e.g., from the reversibility pallet).
        type FreezeChecker: crate::UtxoFreezeChecker;
    }

    /// UTXO set: (txid, vout) → Utxo.
    #[pallet::storage]
    #[pallet::getter(fn utxo_set)]
    pub type UtxoSet<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        (TxId, u32),
        Utxo,
        OptionQuery,
    >;

    /// Address balance cache (derived from UTXO set).
    #[pallet::storage]
    #[pallet::getter(fn balance_of)]
    pub type Balances<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        Address,
        QbcBalance,
        ValueQuery,
    >;

    /// Total number of UTXOs in the set.
    #[pallet::storage]
    #[pallet::getter(fn utxo_count)]
    pub type UtxoCount<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Total number of transactions processed.
    #[pallet::storage]
    #[pallet::getter(fn tx_count)]
    pub type TxCount<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Current block height (updated each block for UTXO tracking).
    #[pallet::storage]
    #[pallet::getter(fn current_height)]
    pub type CurrentHeight<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Accumulated transaction fees since the last coinbase. Fees are the
    /// difference between total inputs and total outputs in each transaction.
    /// On block finalization, 50% of fees are burned and the remaining 50%
    /// are included in the miner's coinbase UTXO by the consensus pallet.
    /// Reset to zero after being distributed/burned.
    #[pallet::storage]
    #[pallet::getter(fn accumulated_fees)]
    pub type AccumulatedFees<T: Config> = StorageValue<_, QbcBalance, ValueQuery>;

    /// Total fees burned since genesis. Tracks the cumulative amount of QBC
    /// permanently removed from circulation via the 50% fee burn mechanism.
    #[pallet::storage]
    #[pallet::getter(fn total_fees_burned)]
    pub type TotalFeesBurned<T: Config> = StorageValue<_, QbcBalance, ValueQuery>;

    /// UTXOs spent during the current block — prevents double-spend within a block.
    /// Cleared at the start of each new block via `set_block_height`.
    #[pallet::storage]
    pub type SpentUtxos<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        (TxId, u32),  // (prev_txid, prev_vout)
        bool,
        ValueQuery,
    >;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// A transaction was processed.
        TransactionProcessed { txid: TxId, inputs: u32, outputs: u32 },
        /// A new UTXO was created.
        UtxoCreated { txid: TxId, vout: u32, address: Address, amount: QbcBalance },
        /// A UTXO was spent.
        UtxoSpent { txid: TxId, vout: u32 },
        /// A coinbase UTXO was created (mining reward).
        CoinbaseCreated { txid: TxId, address: Address, reward: QbcBalance },
        /// Fees were burned (50% of accumulated fees on block finalization).
        FeesBurned { amount: QbcBalance, total_burned: QbcBalance },
    }

    #[pallet::error]
    pub enum Error<T> {
        /// Input UTXO not found in the set.
        UtxoNotFound,
        /// Dilithium signature verification failed.
        InvalidSignature,
        /// Input amounts don't cover output amounts + fee.
        InsufficientFunds,
        /// Transaction has no inputs.
        NoInputs,
        /// Transaction has no outputs.
        NoOutputs,
        /// Duplicate input reference.
        DuplicateInput,
        /// Zero-amount output.
        ZeroAmountOutput,
        /// Coinbase output not yet mature.
        CoinbaseNotMature,
        /// Overflow in amount calculation.
        AmountOverflow,
        /// UTXO already spent in this block (double-spend attempt).
        UtxoAlreadySpent,
        /// UTXO has been frozen by the reversibility pallet and cannot be spent.
        UtxoFrozen,
    }

    /// Storage flag to ensure the height migration runs exactly once.
    #[pallet::storage]
    pub type HeightMigrationDone<T: Config> = StorageValue<_, bool, ValueQuery>;

    #[pallet::hooks]
    impl<T: Config> Hooks<BlockNumberFor<T>> for Pallet<T> {
        fn on_initialize(_n: BlockNumberFor<T>) -> Weight {
            if !HeightMigrationDone::<T>::get() {
                // One-shot migration: add 80,000 to CurrentHeight to account for
                // blocks mined on the first Substrate chain (fork 1) before the
                // consensus upgrade fork (fork 2).
                // Fork 1 started at Python block 208,680, mined ~80K more blocks.
                // Fork 2 genesis was incorrectly set to 208,680 instead of 288,680.
                const HEIGHT_OFFSET: u64 = 80_000;
                let old_height = CurrentHeight::<T>::get();
                let new_height = old_height.saturating_add(HEIGHT_OFFSET);
                CurrentHeight::<T>::put(new_height);
                HeightMigrationDone::<T>::put(true);
                log::info!(
                    target: "utxo",
                    "Height migration: {} -> {} (+{})",
                    old_height, new_height, HEIGHT_OFFSET
                );
                T::DbWeight::get().reads_writes(2, 2)
            } else {
                T::DbWeight::get().reads(1)
            }
        }
    }

    #[pallet::genesis_config]
    #[derive(frame_support::DefaultNoBound)]
    pub struct GenesisConfig<T: Config> {
        /// Initial UTXOs (genesis coinbase outputs).
        pub genesis_utxos: sp_std::vec::Vec<Utxo>,
        #[serde(skip)]
        pub _phantom: core::marker::PhantomData<T>,
    }

    #[pallet::genesis_build]
    impl<T: Config> BuildGenesisConfig for GenesisConfig<T> {
        fn build(&self) {
            // For fork genesis: infer starting height from the UTXOs' block_height.
            // All fork UTXOs carry the fork height, so use the max as the chain's
            // starting height. This ensures the block counter continues from the
            // Python chain's fork point instead of resetting to 0.
            let max_height = self.genesis_utxos.iter()
                .map(|u| u.block_height)
                .max()
                .unwrap_or(0);
            if max_height > 0 {
                CurrentHeight::<T>::put(max_height);
            }
            for utxo in &self.genesis_utxos {
                UtxoSet::<T>::insert((&utxo.txid, utxo.vout), utxo.clone());
                Balances::<T>::mutate(&utxo.address, |bal| {
                    *bal = bal.saturating_add(utxo.amount);
                });
                UtxoCount::<T>::mutate(|n| *n = n.saturating_add(1));

                Pallet::<T>::deposit_event(Event::UtxoCreated {
                    txid: utxo.txid,
                    vout: utxo.vout,
                    address: utxo.address.clone(),
                    amount: utxo.amount,
                });
            }
        }
    }

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Submit a transaction that spends UTXOs and creates new ones.
        ///
        /// Validates:
        /// 1. All input UTXOs exist in the set
        /// 2. Coinbase inputs have sufficient maturity
        /// 3. Dilithium signatures are valid for each input
        /// 4. sum(inputs) >= sum(outputs) (difference is fee)
        /// 5. No duplicate inputs
        /// 6. No zero-amount outputs
        #[pallet::call_index(0)]
        // Analytical weight: N input reads (25µs each) + N Dilithium verifications (500µs each)
        // + M output writes (25µs each) + N input deletions (25µs each) + fee accumulation (25µs)
        // Estimate: 4 inputs × 550µs + 4 outputs × 25µs + 25µs fee = ~2.3ms ≈ 2_325_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(2_325_000)]
        pub fn submit_transaction(
            origin: OriginFor<T>,
            inputs: BoundedVec<TransactionInput, T::MaxInputs>,
            outputs: BoundedVec<TransactionOutput, T::MaxOutputs>,
            signatures: BoundedVec<BoundedVec<u8, ConstU32<MAX_DILITHIUM_SIG_SIZE>>, T::MaxInputs>,
        ) -> DispatchResult {
            ensure_signed(origin)?;

            ensure!(!inputs.is_empty(), Error::<T>::NoInputs);
            ensure!(!outputs.is_empty(), Error::<T>::NoOutputs);

            let current_height = CurrentHeight::<T>::get();

            // Check for duplicate inputs
            for i in 0..inputs.len() {
                for j in (i + 1)..inputs.len() {
                    if inputs[i].prev_txid == inputs[j].prev_txid
                        && inputs[i].prev_vout == inputs[j].prev_vout
                    {
                        return Err(Error::<T>::DuplicateInput.into());
                    }
                }
            }

            // Check that no input was already spent in this block (cross-tx double-spend)
            for input in inputs.iter() {
                ensure!(
                    !SpentUtxos::<T>::contains_key((&input.prev_txid, input.prev_vout)),
                    Error::<T>::UtxoAlreadySpent
                );
            }

            // Check that no input UTXO has been frozen by the reversibility pallet.
            // Frozen UTXOs are part of a reversal process and must not be spent.
            for input in inputs.iter() {
                ensure!(
                    !T::FreezeChecker::is_frozen(&input.prev_txid, input.prev_vout),
                    Error::<T>::UtxoFrozen
                );
            }

            // Validate all inputs exist and calculate total input amount
            let mut total_input: QbcBalance = 0;
            let mut input_utxos = sp_std::vec::Vec::new();

            for (i, input) in inputs.iter().enumerate() {
                let utxo = UtxoSet::<T>::get((&input.prev_txid, input.prev_vout))
                    .ok_or(Error::<T>::UtxoNotFound)?;

                // Check coinbase maturity
                if utxo.is_coinbase {
                    let age = current_height.saturating_sub(utxo.block_height);
                    ensure!(age >= COINBASE_MATURITY as u64, Error::<T>::CoinbaseNotMature);
                }

                // Verify Dilithium signature
                if let Some(sig) = signatures.get(i) {
                    log::info!(target: "utxo-verify", "Looking up PK for address: {:02x?}", &utxo.address.0[..8]);
                    if let Some(pk) = pallet_qbc_dilithium::Pallet::<T>::get_public_key(&utxo.address) {
                        log::info!(target: "utxo-verify", "Found PK: len={} first4={:02x?}", pk.len(), &pk[..4]);
                        let msg = Self::signing_message(&inputs, &outputs);
                        log::info!(target: "utxo-verify", "Signing msg len={}", msg.len());
                        ensure!(
                            pallet_qbc_dilithium::Pallet::<T>::verify_signature(
                                &pk, &msg, sig,
                            ),
                            Error::<T>::InvalidSignature
                        );
                    } else {
                        return Err(Error::<T>::InvalidSignature.into());
                    }
                } else {
                    return Err(Error::<T>::InvalidSignature.into());
                }

                total_input = total_input
                    .checked_add(utxo.amount)
                    .ok_or(Error::<T>::AmountOverflow)?;
                input_utxos.push(utxo);
            }

            // Validate outputs and calculate total output amount
            let mut total_output: QbcBalance = 0;
            for output in outputs.iter() {
                ensure!(output.amount > 0, Error::<T>::ZeroAmountOutput);
                total_output = total_output
                    .checked_add(output.amount)
                    .ok_or(Error::<T>::AmountOverflow)?;
            }

            // Inputs must cover outputs (difference is fee)
            ensure!(total_input >= total_output, Error::<T>::InsufficientFunds);

            // Accumulate the fee (difference between inputs and outputs)
            let fee = total_input.saturating_sub(total_output);
            if fee > 0 {
                AccumulatedFees::<T>::mutate(|f| *f = f.saturating_add(fee));
            }

            // Compute txid from inputs + outputs
            let txid = Self::compute_txid(&inputs, &outputs);

            // Remove spent UTXOs and mark them in SpentUtxos for this block
            for (input, utxo) in inputs.iter().zip(input_utxos.iter()) {
                UtxoSet::<T>::remove((&input.prev_txid, input.prev_vout));
                SpentUtxos::<T>::insert((&input.prev_txid, input.prev_vout), true);
                Balances::<T>::mutate(&utxo.address, |bal| {
                    *bal = bal.saturating_sub(utxo.amount);
                });
                UtxoCount::<T>::mutate(|n| *n = n.saturating_sub(1));
                Self::deposit_event(Event::UtxoSpent {
                    txid: input.prev_txid,
                    vout: input.prev_vout,
                });
            }

            // Create new UTXOs
            for (vout, output) in outputs.iter().enumerate() {
                let utxo = Utxo {
                    txid,
                    vout: vout as u32,
                    address: output.address.clone(),
                    amount: output.amount,
                    block_height: current_height,
                    is_coinbase: false,
                };
                UtxoSet::<T>::insert((&txid, vout as u32), utxo);
                Balances::<T>::mutate(&output.address, |bal| {
                    *bal = bal.saturating_add(output.amount);
                });
                UtxoCount::<T>::mutate(|n| *n = n.saturating_add(1));
                Self::deposit_event(Event::UtxoCreated {
                    txid,
                    vout: vout as u32,
                    address: output.address.clone(),
                    amount: output.amount,
                });
            }

            TxCount::<T>::mutate(|n| *n = n.saturating_add(1));
            Self::deposit_event(Event::TransactionProcessed {
                txid,
                inputs: inputs.len() as u32,
                outputs: outputs.len() as u32,
            });

            Ok(())
        }
    }

    impl<T: Config> Pallet<T> {
        /// Create a coinbase UTXO for the miner (called by consensus pallet).
        pub fn create_coinbase(
            txid: TxId,
            address: Address,
            reward: QbcBalance,
            block_height: u64,
        ) {
            // Mining reward output (vout=0)
            let utxo = Utxo {
                txid,
                vout: 0,
                address: address.clone(),
                amount: reward,
                block_height,
                is_coinbase: true,
            };
            UtxoSet::<T>::insert((&txid, 0u32), utxo);
            Balances::<T>::mutate(&address, |bal| {
                *bal = bal.saturating_add(reward);
            });
            UtxoCount::<T>::mutate(|n| *n = n.saturating_add(1));

            Self::deposit_event(Event::CoinbaseCreated {
                txid,
                address,
                reward,
            });
        }

        /// Finalize fees for the current block: burn 50% and return the
        /// remaining 50% for inclusion in the miner's coinbase UTXO.
        ///
        /// This implements the deflationary fee burn mechanism that matches
        /// the Python node's consensus rules. On every block:
        ///   - 50% of accumulated fees are permanently destroyed (burned)
        ///   - 50% of accumulated fees go to the miner as part of the coinbase
        ///
        /// Called by the consensus pallet during block finalization, BEFORE
        /// creating the coinbase UTXO. The returned value is the miner's
        /// fee share to add to the block reward.
        ///
        /// # Returns
        /// The miner's share of fees (50% of accumulated, rounded down).
        pub fn finalize_fees_with_burn() -> QbcBalance {
            let total_fees = AccumulatedFees::<T>::get();
            if total_fees == 0 {
                return 0;
            }

            // 50% burn (rounded up — burn favored to be deflationary)
            let burn_amount = (total_fees + 1) / 2;
            // 50% to miner (remainder)
            let miner_share = total_fees.saturating_sub(burn_amount);

            // Record the burn
            TotalFeesBurned::<T>::mutate(|burned| {
                *burned = burned.saturating_add(burn_amount);
            });

            // Reset accumulated fees
            AccumulatedFees::<T>::put(0u128);

            // Emit burn event
            let total_burned = TotalFeesBurned::<T>::get();
            Self::deposit_event(Event::FeesBurned {
                amount: burn_amount,
                total_burned,
            });

            miner_share
        }

        /// Reset accumulated fees to zero WITHOUT burning. Only used for
        /// backwards compatibility or emergency scenarios. Prefer
        /// `finalize_fees_with_burn()` for normal block production.
        pub fn reset_accumulated_fees() {
            AccumulatedFees::<T>::put(0u128);
        }

        /// Update the current block height and clear per-block spent UTXO set.
        pub fn set_block_height(height: u64) {
            // Clear the per-block spent set from the previous block.
            // `remove_all` with a limit drains the map efficiently.
            let _ = SpentUtxos::<T>::clear(u32::MAX, None);
            CurrentHeight::<T>::put(height);
        }

        /// Compute transaction ID from inputs and outputs.
        ///
        /// # Substrate vs Python Node Txid Divergence
        ///
        /// This function uses SCALE-friendly raw byte concatenation:
        ///   `SHA-256(prev_txid_0 || prev_vout_0_le || ... || addr_0 || amount_0_le || ...)`
        ///
        /// The Python node uses canonical JSON:
        ///   `SHA-256(json.dumps({"inputs": ..., "outputs": ..., "fee": ..., "timestamp": ...},
        ///                        sort_keys=True))`
        ///
        /// These produce DIFFERENT txids for the same logical transaction.
        /// This is by design — Substrate operates in a `no_std` environment where
        /// JSON serialization is impractical and non-deterministic across allocators.
        ///
        /// **Interoperability is handled at the P2P bridge layer** (`rust-p2p/` +
        /// `qbc_p2p_bridge`), which maintains a txid mapping table when relaying
        /// transactions between Python and Substrate nodes. Each node validates
        /// independently using its native txid scheme.
        ///
        /// When the network fully migrates to Substrate, this becomes the canonical
        /// txid format and the Python format is deprecated.
        fn compute_txid(
            inputs: &[TransactionInput],
            outputs: &[TransactionOutput],
        ) -> TxId {
            use sp_core::hashing::sha2_256;
            let mut data = sp_std::vec::Vec::new();
            for input in inputs {
                data.extend_from_slice(input.prev_txid.as_bytes());
                data.extend_from_slice(&input.prev_vout.to_le_bytes());
            }
            for output in outputs {
                data.extend_from_slice(output.address.as_ref());
                data.extend_from_slice(&output.amount.to_le_bytes());
            }
            H256::from(sha2_256(&data))
        }

        /// Create signing message for Dilithium signature verification.
        ///
        /// # Substrate vs Python Node Signing Divergence
        ///
        /// This function produces a raw byte message for Dilithium5 signing:
        ///   `msg = prev_txid_0 || prev_vout_0_le || ... || addr_0 || amount_0_le || ...`
        ///
        /// The Python node signs canonical JSON representations. The P2P bridge
        /// daemon handles re-signing or signature translation when relaying
        /// transactions between node types. Both nodes verify Dilithium5
        /// signatures against their respective message formats.
        ///
        /// See the module-level documentation for the full interop strategy.
        fn signing_message(
            inputs: &[TransactionInput],
            outputs: &[TransactionOutput],
        ) -> sp_std::vec::Vec<u8> {
            let mut msg = sp_std::vec::Vec::new();
            for input in inputs {
                msg.extend_from_slice(input.prev_txid.as_bytes());
                msg.extend_from_slice(&input.prev_vout.to_le_bytes());
            }
            for output in outputs {
                msg.extend_from_slice(output.address.as_ref());
                msg.extend_from_slice(&output.amount.to_le_bytes());
            }
            msg
        }
    }
}
