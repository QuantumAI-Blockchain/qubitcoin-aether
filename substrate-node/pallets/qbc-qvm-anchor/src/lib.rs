//! Pallet QBC QVM Anchor — bridge between Substrate runtime and external Go QVM.
//!
//! The actual QVM (167 opcodes, compliance, plugins) runs as a separate Go process.
//! This pallet only:
//! 1. Stores the QVM state root per block
//! 2. Validates QVM execution receipts included in blocks
//! 3. Tracks deployed contract count and gas usage

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use sp_core::H256;

    /// Maximum endpoint URL length.
    pub const MAX_ENDPOINT_LEN: u32 = 256;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config: frame_system::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
    }

    /// QVM state root (Merkle Patricia Trie root of all contract storage).
    #[pallet::storage]
    #[pallet::getter(fn qvm_state_root)]
    pub type QvmStateRoot<T: Config> = StorageValue<_, H256, ValueQuery>;

    /// QVM gRPC service endpoint URL.
    #[pallet::storage]
    #[pallet::getter(fn service_endpoint)]
    pub type ServiceEndpoint<T: Config> = StorageValue<
        _,
        BoundedVec<u8, ConstU32<MAX_ENDPOINT_LEN>>,
        ValueQuery,
    >;

    /// Total contracts deployed on QVM.
    #[pallet::storage]
    #[pallet::getter(fn total_contracts)]
    pub type TotalContracts<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Total gas consumed across all QVM executions.
    #[pallet::storage]
    #[pallet::getter(fn total_gas_consumed)]
    pub type TotalGasConsumed<T: Config> = StorageValue<_, u128, ValueQuery>;

    /// QVM state root history — maps block height to state root.
    #[pallet::storage]
    #[pallet::getter(fn state_root_at)]
    pub type StateRootHistory<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        u64,  // block_height
        H256,
        OptionQuery,
    >;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// QVM state root was updated.
        StateRootUpdated { block_height: u64, state_root: H256 },
        /// A contract was deployed on QVM.
        ContractDeployed { address: H256, gas_used: u64 },
        /// QVM execution receipt was validated.
        ExecutionValidated { block_height: u64, receipts: u32 },
        /// Service endpoint was updated.
        EndpointUpdated,
    }

    #[pallet::error]
    pub enum Error<T> {
        /// QVM service is not available.
        ServiceUnavailable,
        /// Invalid state root.
        InvalidStateRoot,
        /// Execution receipt validation failed.
        InvalidReceipt,
        /// State root is all zeros (invalid empty root).
        ZeroStateRoot,
        /// State root is identical to the previous block (no-op update).
        DuplicateStateRoot,
    }

    #[pallet::genesis_config]
    #[derive(frame_support::DefaultNoBound)]
    pub struct GenesisConfig<T: Config> {
        /// QVM gRPC endpoint URL.
        pub service_endpoint: sp_std::vec::Vec<u8>,
        #[serde(skip)]
        pub _phantom: core::marker::PhantomData<T>,
    }

    #[pallet::genesis_build]
    impl<T: Config> BuildGenesisConfig for GenesisConfig<T> {
        fn build(&self) {
            if let Ok(bounded) = BoundedVec::try_from(self.service_endpoint.clone()) {
                ServiceEndpoint::<T>::put(bounded);
            }
        }
    }

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Update the QVM state root for the current block.
        /// Called by the block author after processing QVM transactions.
        #[pallet::call_index(0)]
        // Analytical weight: 2 storage writes (state root + history) + event = ~75µs ≈ 75_000
        #[pallet::weight(75_000)]
        pub fn update_state_root(
            origin: OriginFor<T>,
            block_height: u64,
            state_root: H256,
        ) -> DispatchResult {
            ensure_root(origin)?;

            // Reject all-zero state root (indicates uninitialized or corrupt state)
            ensure!(state_root != H256::zero(), Error::<T>::ZeroStateRoot);

            // Reject duplicate state root (no actual state transition occurred)
            let prev_root = QvmStateRoot::<T>::get();
            // Allow duplicate only if previous is zero (genesis / first update)
            if prev_root != H256::zero() {
                ensure!(state_root != prev_root, Error::<T>::DuplicateStateRoot);
            }

            QvmStateRoot::<T>::put(state_root);
            StateRootHistory::<T>::insert(block_height, state_root);

            Self::deposit_event(Event::StateRootUpdated { block_height, state_root });
            Ok(())
        }

        /// Update the QVM service endpoint.
        #[pallet::call_index(1)]
        // Analytical weight: 1 storage write + event = ~50µs ≈ 50_000
        #[pallet::weight(50_000)]
        pub fn set_endpoint(
            origin: OriginFor<T>,
            endpoint: BoundedVec<u8, ConstU32<MAX_ENDPOINT_LEN>>,
        ) -> DispatchResult {
            ensure_root(origin)?;

            ServiceEndpoint::<T>::put(endpoint);
            Self::deposit_event(Event::EndpointUpdated);
            Ok(())
        }

        /// Record a contract deployment.
        #[pallet::call_index(2)]
        // Analytical weight: 2 storage writes (contract + count) + event = ~75µs ≈ 75_000
        #[pallet::weight(75_000)]
        pub fn record_deployment(
            origin: OriginFor<T>,
            contract_address: H256,
            gas_used: u64,
        ) -> DispatchResult {
            ensure_root(origin)?;

            TotalContracts::<T>::mutate(|n| *n = n.saturating_add(1));
            TotalGasConsumed::<T>::mutate(|g| *g = g.saturating_add(gas_used as u128));

            Self::deposit_event(Event::ContractDeployed {
                address: contract_address,
                gas_used,
            });
            Ok(())
        }
    }
}
