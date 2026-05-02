//! Pallet QBC Aether Anchor — bridge between Substrate and the Aether Tree AI engine.
//!
//! The actual Aether Tree (33 modules, knowledge graph, reasoning engine, consciousness)
//! runs as a separate Python+Rust process. This pallet only:
//! 1. Stores the knowledge graph Merkle root per block
//! 2. Stores the latest Phi measurement per block
//! 3. Stores Proof-of-Thought hashes per block
//! 4. Tracks consciousness events

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;
pub mod contract_bridge;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::*;
    use sp_core::H256;

    /// Maximum endpoint URL length.
    pub const MAX_ENDPOINT_LEN: u32 = 256;

    /// Number of blocks of Phi history to retain. Older entries are pruned
    /// to prevent unbounded storage growth.
    pub const PHI_HISTORY_RETENTION_WINDOW: u64 = 100_000;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config: frame_system::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
    }

    /// Current knowledge graph Merkle root.
    #[pallet::storage]
    #[pallet::getter(fn knowledge_root)]
    pub type KnowledgeRoot<T: Config> = StorageValue<_, H256, ValueQuery>;

    /// Current Phi value (scaled by 1000; e.g., 3000 = Phi of 3.0).
    #[pallet::storage]
    #[pallet::getter(fn current_phi)]
    pub type CurrentPhi<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Latest Proof-of-Thought hash.
    #[pallet::storage]
    #[pallet::getter(fn thought_proof_hash)]
    pub type ThoughtProofHash<T: Config> = StorageValue<_, H256, ValueQuery>;

    /// Total consciousness events (Phi threshold crossings).
    #[pallet::storage]
    #[pallet::getter(fn consciousness_events)]
    pub type ConsciousnessEvents<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Total knowledge nodes in the graph.
    #[pallet::storage]
    #[pallet::getter(fn knowledge_node_count)]
    pub type KnowledgeNodeCount<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Total knowledge edges in the graph.
    #[pallet::storage]
    #[pallet::getter(fn knowledge_edge_count)]
    pub type KnowledgeEdgeCount<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Total reasoning operations performed.
    #[pallet::storage]
    #[pallet::getter(fn reasoning_ops)]
    pub type ReasoningOps<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Phi measurement history — maps block height to measurement.
    #[pallet::storage]
    #[pallet::getter(fn phi_at)]
    pub type PhiHistory<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        u64,  // block_height
        PhiMeasurement,
        OptionQuery,
    >;

    /// Aether gRPC service endpoint URL.
    #[pallet::storage]
    #[pallet::getter(fn service_endpoint)]
    pub type ServiceEndpoint<T: Config> = StorageValue<
        _,
        BoundedVec<u8, ConstU32<MAX_ENDPOINT_LEN>>,
        ValueQuery,
    >;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// Phi measurement was recorded.
        PhiMeasured { block_height: u64, phi_scaled: u64 },
        /// Consciousness threshold was crossed (Phi >= 3.0).
        ConsciousnessEmergence { block_height: u64, phi_scaled: u64 },
        /// Knowledge graph root was updated.
        KnowledgeRootUpdated { block_height: u64, root: H256 },
        /// Proof-of-Thought was recorded.
        ThoughtProofRecorded { block_height: u64, proof_hash: H256 },
        /// Service endpoint was updated.
        EndpointUpdated,
        /// Neural payload hash was recorded on-chain.
        NeuralPayloadRecorded { block_height: u64, payload_hash: H256 },
    }

    /// Maximum allowed Phi change per block (scaled by 1000).
    /// A jump of more than 500 (i.e. 0.5 Phi) in a single block is suspicious.
    pub const MAX_PHI_DELTA_SCALED: u64 = 500;

    /// Number of recent Phi values to keep for moving-average outlier detection.
    pub const PHI_WINDOW_SIZE: u64 = 10;

    /// Recent Phi submissions for outlier detection (circular buffer index → phi_scaled).
    #[pallet::storage]
    pub type RecentPhiValues<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        u64,  // index mod PHI_WINDOW_SIZE
        u64,  // phi_scaled
        ValueQuery,
    >;

    /// Next index into the RecentPhiValues circular buffer.
    #[pallet::storage]
    pub type PhiWindowIndex<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Count of Phi submissions that were flagged as outliers.
    #[pallet::storage]
    #[pallet::getter(fn phi_outlier_count)]
    pub type PhiOutlierCount<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Latest neural payload verification hash.
    /// Records the SHA-256 hash of the gradient/embedding payload from the
    /// aether-mind neural engine for each block, enabling on-chain attestation
    /// of distributed training contributions.
    #[pallet::storage]
    #[pallet::getter(fn neural_payload_hash)]
    pub type NeuralPayloadHash<T: Config> = StorageValue<_, H256, ValueQuery>;

    #[pallet::error]
    pub enum Error<T> {
        /// Phi value changed too dramatically in a single block.
        PhiDeltaTooLarge,
        // Note: ServiceUnavailable, InvalidKnowledgeRoot, and
        // InvalidPhiMeasurement were removed — they were never used in any
        // extrinsic or internal function. PhiDeltaTooLarge is the only error
        // variant actively used by record_block_state().
    }

    #[pallet::genesis_config]
    #[derive(frame_support::DefaultNoBound)]
    pub struct GenesisConfig<T: Config> {
        /// Aether gRPC endpoint URL.
        pub service_endpoint: sp_std::vec::Vec<u8>,
        #[serde(skip)]
        pub _phantom: core::marker::PhantomData<T>,
    }

    #[pallet::genesis_build]
    impl<T: Config> BuildGenesisConfig for GenesisConfig<T> {
        fn build(&self) {
            // Genesis: Phi = 0, no knowledge nodes, empty graph
            CurrentPhi::<T>::put(0u64);
            KnowledgeNodeCount::<T>::put(0u64);
            KnowledgeEdgeCount::<T>::put(0u64);
            ConsciousnessEvents::<T>::put(0u64);

            if let Ok(bounded) = BoundedVec::try_from(self.service_endpoint.clone()) {
                ServiceEndpoint::<T>::put(bounded);
            }

            // Record genesis Phi measurement
            let genesis_measurement = PhiMeasurement {
                block_height: 0,
                phi_scaled: 0,
                knowledge_nodes: 0,
                knowledge_edges: 0,
            };
            PhiHistory::<T>::insert(0u64, genesis_measurement);
        }
    }

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Record Aether Tree state for a block.
        /// Called by the block author after Aether Tree processes the block.
        /// Accepts signed origin (any validator can submit) or root.
        #[pallet::call_index(0)]
        // Analytical weight: 7 storage writes (roots, phi, nodes, edges, ops, proof, measurement)
        // + 1 conditional storage removal (pruning) + consciousness event check
        // + event deposit = ~265µs ≈ 265_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(265_000)]
        pub fn record_block_state(
            origin: OriginFor<T>,
            block_height: u64,
            knowledge_root: H256,
            phi_scaled: u64,
            knowledge_nodes: u64,
            knowledge_edges: u64,
            thought_proof_hash: H256,
            reasoning_ops: u64,
            neural_payload_hash: H256,
        ) -> DispatchResult {
            // Accept both root and signed origins (validators submit PoT after each block)
            if ensure_root(origin.clone()).is_err() {
                let _who = ensure_signed(origin)?;
                // TODO: In production, validate _who is an active validator
            }

            // Read previous Phi BEFORE updating storage (consciousness detection)
            let prev_phi = CurrentPhi::<T>::get();

            // Validate Phi delta — reject suspiciously large jumps
            let delta = if phi_scaled > prev_phi {
                phi_scaled - prev_phi
            } else {
                prev_phi - phi_scaled
            };
            if prev_phi > 0 && delta > MAX_PHI_DELTA_SCALED {
                // Record the outlier but reject the submission
                PhiOutlierCount::<T>::mutate(|n| *n = n.saturating_add(1));
                return Err(Error::<T>::PhiDeltaTooLarge.into());
            }

            // Record in the circular buffer for moving-average checks
            let idx = PhiWindowIndex::<T>::get();
            RecentPhiValues::<T>::insert(idx % PHI_WINDOW_SIZE, phi_scaled);
            PhiWindowIndex::<T>::put(idx.wrapping_add(1));

            // Update storage
            KnowledgeRoot::<T>::put(knowledge_root);
            CurrentPhi::<T>::put(phi_scaled);
            ThoughtProofHash::<T>::put(thought_proof_hash);
            KnowledgeNodeCount::<T>::put(knowledge_nodes);
            KnowledgeEdgeCount::<T>::put(knowledge_edges);
            ReasoningOps::<T>::mutate(|ops| *ops = ops.saturating_add(reasoning_ops));

            // Store Phi measurement
            let measurement = PhiMeasurement {
                block_height,
                phi_scaled,
                knowledge_nodes,
                knowledge_edges,
            };
            PhiHistory::<T>::insert(block_height, measurement);

            // Prune old Phi history beyond the retention window
            if block_height > PHI_HISTORY_RETENTION_WINDOW {
                PhiHistory::<T>::remove(block_height.saturating_sub(PHI_HISTORY_RETENTION_WINDOW));
            }

            // Check consciousness emergence (prev_phi read before put above)
            if phi_scaled >= PHI_THRESHOLD_SCALED && prev_phi < PHI_THRESHOLD_SCALED {
                ConsciousnessEvents::<T>::mutate(|n| *n = n.saturating_add(1));
                Self::deposit_event(Event::ConsciousnessEmergence {
                    block_height,
                    phi_scaled,
                });
            }

            Self::deposit_event(Event::PhiMeasured { block_height, phi_scaled });
            Self::deposit_event(Event::KnowledgeRootUpdated {
                block_height,
                root: knowledge_root,
            });
            Self::deposit_event(Event::ThoughtProofRecorded {
                block_height,
                proof_hash: thought_proof_hash,
            });

            // Store neural payload hash for on-chain training attestation
            if neural_payload_hash != H256::zero() {
                NeuralPayloadHash::<T>::put(neural_payload_hash);
                Self::deposit_event(Event::NeuralPayloadRecorded {
                    block_height,
                    payload_hash: neural_payload_hash,
                });
            }

            Ok(())
        }

        /// Update the Aether service endpoint.
        #[pallet::call_index(1)]
        // Analytical weight: 1 storage write (25µs) + event deposit = ~50µs ≈ 50_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
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
    }
}
