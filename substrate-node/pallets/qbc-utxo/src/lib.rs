//! Pallet QBC UTXO — UTXO model for Qubitcoin.
//!
//! Implements the full UTXO transaction model:
//! - Store and query the UTXO set
//! - Validate transactions (inputs exist, signatures valid, amounts balance)
//! - Maintain address balance cache for fast lookups
//! - Coinbase creation for mining rewards

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::*;
    use sp_core::H256;
    use sp_runtime::BoundedVec;

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
            for utxo in &self.genesis_utxos {
                UtxoSet::<T>::insert((&utxo.txid, utxo.vout), utxo.clone());
                Balances::<T>::mutate(&utxo.address, |bal| {
                    *bal = bal.saturating_add(utxo.amount);
                });
                UtxoCount::<T>::mutate(|n| *n += 1);

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
        #[pallet::weight(50_000)]
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
                    if let Some(pk) = pallet_qbc_dilithium::Pallet::<T>::get_public_key(&utxo.address) {
                        let msg = Self::signing_message(&inputs, &outputs);
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

            // Compute txid from inputs + outputs
            let txid = Self::compute_txid(&inputs, &outputs);

            // Remove spent UTXOs
            for (input, utxo) in inputs.iter().zip(input_utxos.iter()) {
                UtxoSet::<T>::remove((&input.prev_txid, input.prev_vout));
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
                UtxoCount::<T>::mutate(|n| *n += 1);
                Self::deposit_event(Event::UtxoCreated {
                    txid,
                    vout: vout as u32,
                    address: output.address.clone(),
                    amount: output.amount,
                });
            }

            TxCount::<T>::mutate(|n| *n += 1);
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
            UtxoCount::<T>::mutate(|n| *n += 1);

            Self::deposit_event(Event::CoinbaseCreated {
                txid,
                address,
                reward,
            });
        }

        /// Update the current block height.
        pub fn set_block_height(height: u64) {
            CurrentHeight::<T>::put(height);
        }

        /// Compute transaction ID from inputs and outputs.
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
