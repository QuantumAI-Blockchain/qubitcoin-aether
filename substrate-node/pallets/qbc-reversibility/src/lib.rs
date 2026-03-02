//! Pallet QBC Reversibility — Governed Transaction Reversal
//!
//! Allows a governed reversal of transactions within a configurable time window
//! (default: 24 hours / ~26,182 blocks at 3.3s/block) via multi-sig governance vote.
//!
//! ## How It Works
//!
//! 1. User/authority submits reversal request to this pallet
//! 2. Request enters a voting window (24h default)
//! 3. N-of-M governance signers must approve (configurable, default 3-of-5)
//! 4. If approved: pallet creates "reversal transaction" that:
//!    a. Marks original UTXOs as "reversed" (frozen)
//!    b. Creates new UTXOs returning funds to the original sender
//!    c. Emits ReversalExecuted event
//! 5. If expired without approval: request is archived, no action taken
//!
//! ## Constraints
//!
//! - Only works within REVERSAL_WINDOW (configurable, default 24h)
//! - Coinbase transactions are NOT reversible
//! - Already-spent UTXOs cannot be reversed (chain has moved on)
//! - Requires governance multi-sig (not any single party)
//! - All reversals are on-chain, auditable, transparent

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;
    use qbc_primitives::*;
    use sp_core::H256;
    use sp_runtime::BoundedVec;

    /// Maximum number of governance signers.
    pub const MAX_GOVERNORS: u32 = 10;

    /// Maximum reason length for reversal requests (in bytes).
    pub const MAX_REASON_LENGTH: u32 = 512;

    /// Default reversal window: ~24 hours at 3.3s/block = 26,182 blocks.
    pub const DEFAULT_REVERSAL_WINDOW: u64 = 26_182;

    /// Default approval threshold: 3 of 5 governors must approve.
    pub const DEFAULT_APPROVAL_THRESHOLD: u32 = 3;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config:
        frame_system::Config + pallet_qbc_utxo::Config + pallet_qbc_dilithium::Config
    {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;

        /// Maximum number of governance signers allowed.
        #[pallet::constant]
        type MaxGovernors: Get<u32>;

        /// Maximum length of the reversal reason string.
        #[pallet::constant]
        type MaxReasonLength: Get<u32>;
    }

    // ═══════════════════════════════════════════════════════════════════
    // Storage
    // ═══════════════════════════════════════════════════════════════════

    /// Reversal window in blocks (how long after a tx it can be reversed).
    #[pallet::storage]
    #[pallet::getter(fn reversal_window)]
    pub type ReversalWindow<T: Config> = StorageValue<_, u64, ValueQuery, DefaultReversalWindow>;

    /// Default reversal window value provider.
    pub struct DefaultReversalWindow;
    impl Get<u64> for DefaultReversalWindow {
        fn get() -> u64 {
            DEFAULT_REVERSAL_WINDOW
        }
    }

    /// Approval threshold — minimum number of governor approvals needed.
    #[pallet::storage]
    #[pallet::getter(fn approval_threshold)]
    pub type ApprovalThreshold<T: Config> =
        StorageValue<_, u32, ValueQuery, DefaultApprovalThreshold>;

    pub struct DefaultApprovalThreshold;
    impl Get<u32> for DefaultApprovalThreshold {
        fn get() -> u32 {
            DEFAULT_APPROVAL_THRESHOLD
        }
    }

    /// Set of governance addresses authorized to vote on reversals.
    #[pallet::storage]
    #[pallet::getter(fn governors)]
    pub type Governors<T: Config> =
        StorageValue<_, BoundedVec<Address, ConstU32<MAX_GOVERNORS>>, ValueQuery>;

    /// Pending reversal requests: request_id → ReversalRequest.
    #[pallet::storage]
    #[pallet::getter(fn reversal_request)]
    pub type ReversalRequests<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        H256, // request_id
        ReversalRequest,
        OptionQuery,
    >;

    /// Votes on reversal requests: request_id → list of governor addresses that approved.
    #[pallet::storage]
    #[pallet::getter(fn reversal_votes)]
    pub type ReversalVotes<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        H256, // request_id
        BoundedVec<Address, ConstU32<MAX_GOVERNORS>>,
        ValueQuery,
    >;

    /// Executed reversals archive: request_id → execution details.
    #[pallet::storage]
    #[pallet::getter(fn executed_reversal)]
    pub type ExecutedReversals<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        H256,
        ReversalExecution,
        OptionQuery,
    >;

    /// Expired (not approved) reversal archive: request_id → request.
    #[pallet::storage]
    #[pallet::getter(fn expired_reversal)]
    pub type ExpiredReversals<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        H256,
        ReversalRequest,
        OptionQuery,
    >;

    /// Counter for total reversal requests submitted.
    #[pallet::storage]
    #[pallet::getter(fn total_requests)]
    pub type TotalRequests<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Counter for total reversals executed.
    #[pallet::storage]
    #[pallet::getter(fn total_executed)]
    pub type TotalExecuted<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Counter for total reversals expired.
    #[pallet::storage]
    #[pallet::getter(fn total_expired)]
    pub type TotalExpired<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Frozen UTXOs (reversed — cannot be spent).
    #[pallet::storage]
    #[pallet::getter(fn is_frozen)]
    pub type FrozenUtxos<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        (TxId, u32), // (txid, vout)
        bool,
        ValueQuery,
    >;

    /// Index of request IDs by their expiry block height.
    ///
    /// Maps `expiry_block_height → Vec<request_id>`. This allows efficient
    /// lookup of which requests expire at a given block height, avoiding
    /// full iteration of the `ReversalRequests` map when pruning or
    /// auto-expiring entries.
    #[pallet::storage]
    pub type ExpiryIndex<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        u64,  // expiry_block_height
        BoundedVec<H256, ConstU32<MAX_GOVERNORS>>,  // request_ids (bounded per block)
        ValueQuery,
    >;

    // ═══════════════════════════════════════════════════════════════════
    // Types
    // ═══════════════════════════════════════════════════════════════════

    /// Status of a reversal request.
    #[derive(Clone, PartialEq, Eq, Encode, Decode, MaxEncodedLen, TypeInfo, RuntimeDebug)]
    pub enum ReversalStatus {
        /// Pending — still within the voting window.
        Pending,
        /// Approved — threshold met, ready to execute.
        Approved,
        /// Executed — funds returned.
        Executed,
        /// Expired — voting window closed without sufficient approval.
        Expired,
        /// Rejected — explicitly rejected by governance.
        Rejected,
    }

    /// A reversal request.
    #[derive(Clone, PartialEq, Eq, Encode, Decode, MaxEncodedLen, TypeInfo, RuntimeDebug)]
    pub struct ReversalRequest {
        /// Unique request identifier.
        pub request_id: H256,
        /// The transaction ID to reverse.
        pub target_txid: TxId,
        /// The original sender address (who gets funds back).
        pub original_sender: Address,
        /// Total amount to reverse (sum of target tx outputs).
        pub amount: QbcBalance,
        /// Block height when the target transaction was included.
        pub target_block_height: u64,
        /// Block height when this request was submitted.
        pub request_block_height: u64,
        /// Block height when the voting window expires.
        pub expiry_block_height: u64,
        /// Current approval count.
        pub approval_count: u32,
        /// Current status.
        pub status: ReversalStatus,
        /// Reason for the reversal (bounded).
        pub reason: BoundedVec<u8, ConstU32<MAX_REASON_LENGTH>>,
        /// Address that submitted the request.
        pub requester: Address,
    }

    /// Record of an executed reversal.
    #[derive(Clone, PartialEq, Eq, Encode, Decode, MaxEncodedLen, TypeInfo, RuntimeDebug)]
    pub struct ReversalExecution {
        /// The original request.
        pub request_id: H256,
        /// The reversal transaction ID (new UTXOs created).
        pub reversal_txid: TxId,
        /// Block height when executed.
        pub execution_block_height: u64,
        /// Amount reversed.
        pub amount: QbcBalance,
        /// The target transaction that was reversed.
        pub original_txid: TxId,
        /// Who received the funds back.
        pub recipient: Address,
    }

    // ═══════════════════════════════════════════════════════════════════
    // Genesis
    // ═══════════════════════════════════════════════════════════════════

    #[pallet::genesis_config]
    #[derive(frame_support::DefaultNoBound)]
    pub struct GenesisConfig<T: Config> {
        /// Initial set of governance addresses.
        pub governors: sp_std::vec::Vec<Address>,
        /// Reversal window in blocks (0 = use default).
        pub reversal_window: u64,
        /// Approval threshold (0 = use default).
        pub approval_threshold: u32,
        #[serde(skip)]
        pub _phantom: core::marker::PhantomData<T>,
    }

    #[pallet::genesis_build]
    impl<T: Config> BuildGenesisConfig for GenesisConfig<T> {
        fn build(&self) {
            if !self.governors.is_empty() {
                let bounded: BoundedVec<Address, ConstU32<MAX_GOVERNORS>> =
                    self.governors.clone().try_into().expect(
                        "genesis governors count must not exceed MAX_GOVERNORS",
                    );
                Governors::<T>::put(bounded);
            }
            if self.reversal_window > 0 {
                ReversalWindow::<T>::put(self.reversal_window);
            }
            if self.approval_threshold > 0 {
                ApprovalThreshold::<T>::put(self.approval_threshold);
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // Events
    // ═══════════════════════════════════════════════════════════════════

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// A new reversal request was submitted.
        ReversalRequested {
            request_id: H256,
            target_txid: TxId,
            amount: QbcBalance,
            requester: Address,
            expiry_block: u64,
        },
        /// A governor voted to approve a reversal.
        ReversalApproved {
            request_id: H256,
            governor: Address,
            approval_count: u32,
            threshold: u32,
        },
        /// A reversal was executed (funds returned).
        ReversalExecuted {
            request_id: H256,
            target_txid: TxId,
            reversal_txid: TxId,
            amount: QbcBalance,
            recipient: Address,
        },
        /// A reversal request expired without sufficient approval.
        ReversalExpired {
            request_id: H256,
            target_txid: TxId,
        },
        /// A governor was added.
        GovernorAdded { address: Address },
        /// A governor was removed.
        GovernorRemoved { address: Address },
        /// Reversal window was updated.
        ReversalWindowUpdated { old: u64, new: u64 },
        /// Approval threshold was updated.
        ThresholdUpdated { old: u32, new: u32 },
        /// A UTXO was frozen as part of a reversal.
        UtxoFrozen { txid: TxId, vout: u32 },
    }

    // ═══════════════════════════════════════════════════════════════════
    // Errors
    // ═══════════════════════════════════════════════════════════════════

    #[pallet::error]
    pub enum Error<T> {
        /// The target transaction was not found in the UTXO set.
        TransactionNotFound,
        /// The target transaction is a coinbase — coinbase txs are NOT reversible.
        CoinbaseNotReversible,
        /// The target UTXOs have already been spent (chain has moved on).
        UtxoAlreadySpent,
        /// The reversal window has passed — too late to reverse.
        ReversalWindowExpired,
        /// The caller is not an authorized governor.
        NotGovernor,
        /// The governor has already voted on this request.
        AlreadyVoted,
        /// The reversal request was not found.
        RequestNotFound,
        /// The request is not in Pending status.
        RequestNotPending,
        /// The request has already been executed.
        AlreadyExecuted,
        /// Governor list is full.
        GovernorListFull,
        /// Governor not found in the list.
        GovernorNotFound,
        /// Threshold cannot exceed the number of governors.
        ThresholdExceedsGovernors,
        /// Threshold must be at least 1.
        ThresholdTooLow,
        /// A reversal request for this txid already exists.
        DuplicateRequest,
        /// The UTXO is already frozen from a previous reversal.
        UtxoAlreadyFrozen,
        /// Amount overflow during reversal calculation.
        AmountOverflow,
        /// The reason string is too long.
        ReasonTooLong,
        /// No governors have been configured.
        NoGovernors,
    }

    // ═══════════════════════════════════════════════════════════════════
    // Extrinsics
    // ═══════════════════════════════════════════════════════════════════

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Submit a reversal request for a specific transaction.
        ///
        /// Anyone can submit a request, but only governors can approve it.
        /// The request enters a voting window determined by `ReversalWindow`.
        #[pallet::call_index(0)]
        // Analytical weight: up to 256 UTXO reads (25µs each, worst case ~6.4ms)
        // + governor read (25µs) + request write (25µs) + counter write (25µs)
        // + SHA2-256 hash (10µs) + event = ~6.5ms ≈ 6_500_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(6_500_000)]
        pub fn submit_reversal_request(
            origin: OriginFor<T>,
            target_txid: TxId,
            original_sender: Address,
            reason: BoundedVec<u8, ConstU32<MAX_REASON_LENGTH>>,
        ) -> DispatchResult {
            let caller = ensure_signed(origin)?;
            let requester_address = Self::account_to_address(&caller);

            // Ensure we have governors configured
            let governors = Governors::<T>::get();
            ensure!(!governors.is_empty(), Error::<T>::NoGovernors);

            let current_height = pallet_qbc_utxo::CurrentHeight::<T>::get();
            let window = ReversalWindow::<T>::get();

            // Find the target UTXOs — scan for UTXOs matching this txid
            // We need at least one UTXO from this txid to still exist
            let mut total_amount: QbcBalance = 0;
            let mut target_block_height: u64 = 0;
            let mut found_any = false;

            // Check vouts 0..MAX_OUTPUTS for UTXOs belonging to this txid
            for vout in 0..256u32 {
                if let Some(utxo) = pallet_qbc_utxo::UtxoSet::<T>::get((&target_txid, vout)) {
                    // Coinbase outputs cannot be reversed
                    ensure!(!utxo.is_coinbase, Error::<T>::CoinbaseNotReversible);
                    // Check not already frozen
                    ensure!(
                        !FrozenUtxos::<T>::get((&target_txid, vout)),
                        Error::<T>::UtxoAlreadyFrozen
                    );

                    total_amount = total_amount
                        .checked_add(utxo.amount)
                        .ok_or(Error::<T>::AmountOverflow)?;
                    target_block_height = utxo.block_height;
                    found_any = true;
                }
            }

            ensure!(found_any, Error::<T>::TransactionNotFound);

            // Check reversal window
            let block_age = current_height.saturating_sub(target_block_height);
            ensure!(block_age <= window, Error::<T>::ReversalWindowExpired);

            // Compute unique request ID
            let request_id = Self::compute_request_id(&target_txid, current_height);

            // Ensure no duplicate request
            ensure!(
                !ReversalRequests::<T>::contains_key(&request_id),
                Error::<T>::DuplicateRequest
            );

            let expiry = current_height.saturating_add(window);

            let request = ReversalRequest {
                request_id,
                target_txid,
                original_sender: original_sender.clone(),
                amount: total_amount,
                target_block_height,
                request_block_height: current_height,
                expiry_block_height: expiry,
                approval_count: 0,
                status: ReversalStatus::Pending,
                reason,
                requester: requester_address.clone(),
            };

            ReversalRequests::<T>::insert(&request_id, request);
            TotalRequests::<T>::mutate(|n| *n = n.saturating_add(1));

            // Add to expiry index for efficient pruning
            ExpiryIndex::<T>::mutate(expiry, |ids| {
                let _ = ids.try_push(request_id);
            });

            Self::deposit_event(Event::ReversalRequested {
                request_id,
                target_txid,
                amount: total_amount,
                requester: requester_address,
                expiry_block: expiry,
            });

            Ok(())
        }

        /// Approve a pending reversal request (governor only).
        ///
        /// The governor identity is derived from the transaction sender (`origin`),
        /// NOT from a user-supplied parameter. This prevents impersonation attacks
        /// where a non-governor could pass another governor's address.
        ///
        /// When the approval threshold is met, the reversal is automatically executed:
        /// - Target UTXOs are frozen
        /// - New UTXOs are created returning funds to the original sender
        #[pallet::call_index(1)]
        // Analytical weight: governor read (25µs) + request read (25µs) + votes read/write (50µs)
        // + AccountId→Address conversion (10µs) + if threshold met: execute_reversal →
        //   up to 256 UTXO reads + freezes + removal + reversal UTXO write + balance
        //   updates + counters = ~7ms worst case
        // Total: ~7.2ms ≈ 7_200_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(7_200_000)]
        pub fn approve_reversal(
            origin: OriginFor<T>,
            request_id: H256,
        ) -> DispatchResult {
            // Derive the governor address from the actual transaction sender.
            // This is critical for security — we must verify WHO is calling,
            // not trust a parameter that anyone could forge.
            let caller = ensure_signed(origin)?;
            let governor_address = Self::account_to_address(&caller);

            // Verify the actual caller is an authorized governor
            let governors = Governors::<T>::get();
            ensure!(
                governors.iter().any(|g| *g == governor_address),
                Error::<T>::NotGovernor
            );

            // Get the request
            let mut request = ReversalRequests::<T>::get(&request_id)
                .ok_or(Error::<T>::RequestNotFound)?;

            ensure!(
                request.status == ReversalStatus::Pending,
                Error::<T>::RequestNotPending
            );

            // Check not expired
            let current_height = pallet_qbc_utxo::CurrentHeight::<T>::get();
            if current_height > request.expiry_block_height {
                // Auto-expire
                request.status = ReversalStatus::Expired;
                let req_clone = request.clone();
                ExpiredReversals::<T>::insert(&request_id, req_clone);
                ReversalRequests::<T>::remove(&request_id);
                TotalExpired::<T>::mutate(|n| *n = n.saturating_add(1));

                Self::deposit_event(Event::ReversalExpired {
                    request_id,
                    target_txid: request.target_txid,
                });

                return Ok(());
            }

            // Check not already voted
            let mut votes = ReversalVotes::<T>::get(&request_id);
            ensure!(
                !votes.iter().any(|v| *v == governor_address),
                Error::<T>::AlreadyVoted
            );

            // Record vote
            votes
                .try_push(governor_address.clone())
                .map_err(|_| Error::<T>::GovernorListFull)?;
            ReversalVotes::<T>::insert(&request_id, votes.clone());

            request.approval_count += 1;

            let threshold = ApprovalThreshold::<T>::get();

            Self::deposit_event(Event::ReversalApproved {
                request_id,
                governor: governor_address,
                approval_count: request.approval_count,
                threshold,
            });

            // Check if threshold is met → execute the reversal
            if request.approval_count >= threshold {
                request.status = ReversalStatus::Approved;
                ReversalRequests::<T>::insert(&request_id, request.clone());

                Self::execute_reversal(&request_id, &request)?;
            } else {
                ReversalRequests::<T>::insert(&request_id, request);
            }

            Ok(())
        }

        /// Add a new governor address (root/sudo only).
        #[pallet::call_index(2)]
        // Analytical weight: 1 storage read + mutate (50µs) + event = ~75µs ≈ 75_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(75_000)]
        pub fn add_governor(
            origin: OriginFor<T>,
            address: Address,
        ) -> DispatchResult {
            ensure_root(origin)?;

            Governors::<T>::try_mutate(|governors| -> DispatchResult {
                ensure!(
                    !governors.iter().any(|g| *g == address),
                    Error::<T>::GovernorListFull
                );
                governors
                    .try_push(address.clone())
                    .map_err(|_| Error::<T>::GovernorListFull)?;
                Ok(())
            })?;

            Self::deposit_event(Event::GovernorAdded { address });
            Ok(())
        }

        /// Remove a governor address (root/sudo only).
        #[pallet::call_index(3)]
        // Analytical weight: 1 storage read + mutate (50µs) + threshold check (25µs) + event = ~100µs ≈ 100_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(100_000)]
        pub fn remove_governor(
            origin: OriginFor<T>,
            address: Address,
        ) -> DispatchResult {
            ensure_root(origin)?;

            Governors::<T>::try_mutate(|governors| -> DispatchResult {
                let pos = governors
                    .iter()
                    .position(|g| *g == address)
                    .ok_or(Error::<T>::GovernorNotFound)?;
                governors.remove(pos);

                // Ensure threshold doesn't exceed remaining governors
                let threshold = ApprovalThreshold::<T>::get();
                if !governors.is_empty() && threshold > governors.len() as u32 {
                    ApprovalThreshold::<T>::put(governors.len() as u32);
                }

                Ok(())
            })?;

            Self::deposit_event(Event::GovernorRemoved { address });
            Ok(())
        }

        /// Update the reversal window (root/sudo only).
        #[pallet::call_index(4)]
        // Analytical weight: 1 storage read + 1 write (50µs) + event = ~75µs ≈ 75_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(75_000)]
        pub fn set_reversal_window(
            origin: OriginFor<T>,
            new_window: u64,
        ) -> DispatchResult {
            ensure_root(origin)?;

            let old = ReversalWindow::<T>::get();
            ReversalWindow::<T>::put(new_window);

            Self::deposit_event(Event::ReversalWindowUpdated {
                old,
                new: new_window,
            });
            Ok(())
        }

        /// Update the approval threshold (root/sudo only).
        #[pallet::call_index(5)]
        // Analytical weight: 1 governor read (25µs) + 1 threshold read + write (50µs) + event = ~100µs ≈ 100_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(100_000)]
        pub fn set_approval_threshold(
            origin: OriginFor<T>,
            new_threshold: u32,
        ) -> DispatchResult {
            ensure_root(origin)?;

            ensure!(new_threshold >= 1, Error::<T>::ThresholdTooLow);
            let governors = Governors::<T>::get();
            ensure!(
                new_threshold as usize <= governors.len(),
                Error::<T>::ThresholdExceedsGovernors
            );

            let old = ApprovalThreshold::<T>::get();
            ApprovalThreshold::<T>::put(new_threshold);

            Self::deposit_event(Event::ThresholdUpdated {
                old,
                new: new_threshold,
            });
            Ok(())
        }

        /// Expire a reversal request that has passed its window (callable by anyone).
        ///
        /// This is a cleanup function — anyone can call it to move expired
        /// requests out of the pending queue.
        #[pallet::call_index(6)]
        // Analytical weight: request read (25µs) + height read (25µs) + expired write (25µs)
        // + request removal (25µs) + votes removal (25µs) + counter (25µs) + event = ~175µs ≈ 175_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(175_000)]
        pub fn expire_request(
            origin: OriginFor<T>,
            request_id: H256,
        ) -> DispatchResult {
            ensure_signed(origin)?;

            let mut request = ReversalRequests::<T>::get(&request_id)
                .ok_or(Error::<T>::RequestNotFound)?;

            ensure!(
                request.status == ReversalStatus::Pending,
                Error::<T>::RequestNotPending
            );

            let current_height = pallet_qbc_utxo::CurrentHeight::<T>::get();
            ensure!(
                current_height > request.expiry_block_height,
                Error::<T>::RequestNotPending // Not yet expired
            );

            request.status = ReversalStatus::Expired;
            ExpiredReversals::<T>::insert(&request_id, request.clone());
            ReversalRequests::<T>::remove(&request_id);
            ReversalVotes::<T>::remove(&request_id);
            TotalExpired::<T>::mutate(|n| *n = n.saturating_add(1));

            Self::deposit_event(Event::ReversalExpired {
                request_id,
                target_txid: request.target_txid,
            });

            Ok(())
        }

        /// Prune old expired reversal records from storage (root/sudo only).
        ///
        /// Removes entries from `ExpiredReversals` where the request expired
        /// more than `max_age_blocks` ago.  This prevents unbounded storage growth.
        ///
        /// `max_entries` limits how many entries are pruned per call to bound
        /// the execution weight.
        #[pallet::call_index(7)]
        // Analytical weight: height read (25µs) + up to max_entries iteration reads (25µs each)
        // + removals (25µs each). For max_entries=100: ~100*50µs = 5ms ≈ 5_000_000
        // NOTE: These are analytical estimates and should be replaced with
        // benchmarked weights before mainnet.
        #[pallet::weight(5_000_000)]
        pub fn prune_expired_reversals(
            origin: OriginFor<T>,
            max_age_blocks: u64,
            max_entries: u32,
        ) -> DispatchResult {
            ensure_root(origin)?;

            let current_height = pallet_qbc_utxo::CurrentHeight::<T>::get();
            let mut pruned: u32 = 0;

            // SECURITY [SUB-H7]: Use the ExpiryIndex for efficient pruning instead
            // of iterating the entire ReversalRequests or ExpiredReversals storage map.
            //
            // Strategy: probe individual block heights from 0 up to the cutoff.
            // This avoids calling `ExpiryIndex::<T>::iter()` which would enumerate
            // ALL entries in the map (including future ones), causing O(total_entries)
            // reads even when only a few need pruning.
            //
            // We walk backwards from the cutoff to find entries efficiently. Since
            // the reversal window is ~26,182 blocks (~24h), the expiry index is
            // sparse (one entry per block that had a reversal request), so most
            // lookups will be misses (cheap: single storage read returning None).
            let cutoff = current_height.saturating_sub(max_age_blocks);

            // Walk from oldest possible expiry up to the cutoff. To bound work,
            // we scan at most `max_entries * 4` block heights (generous factor
            // since most heights won't have entries).
            let scan_limit = (max_entries as u64).saturating_mul(4).max(1000);
            let scan_start = cutoff.saturating_sub(scan_limit);
            let mut blocks_to_clean: sp_std::vec::Vec<u64> = sp_std::vec::Vec::new();

            let mut height = scan_start;
            while height <= cutoff && pruned < max_entries {
                let request_ids = ExpiryIndex::<T>::get(height);
                if !request_ids.is_empty() {
                    for request_id in request_ids.iter() {
                        if pruned >= max_entries {
                            break;
                        }
                        ExpiredReversals::<T>::remove(request_id);
                        pruned += 1;
                    }
                    blocks_to_clean.push(height);
                }
                height = height.saturating_add(1);
            }

            // Remove cleaned expiry index entries
            for block_height in blocks_to_clean {
                ExpiryIndex::<T>::remove(block_height);
            }

            log::info!(
                "Pruned {} expired reversal records (max_age={} blocks, scanned heights {}..={})",
                pruned,
                max_age_blocks,
                scan_start,
                cutoff.min(height),
            );

            Ok(())
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // Internal functions
    // ═══════════════════════════════════════════════════════════════════

    impl<T: Config> Pallet<T> {
        /// Convert a Substrate AccountId to a QBC Address.
        ///
        /// Uses the SCALE-encoded bytes of the AccountId (typically 32 bytes for
        /// AccountId32) and hashes them with SHA2-256 to produce a deterministic
        /// QBC address. This ensures a consistent mapping from Substrate accounts
        /// to QBC addresses across the system.
        fn account_to_address(account: &T::AccountId) -> Address {
            use codec::Encode;
            use sp_core::hashing::sha2_256;
            let encoded = account.encode();
            Address(sha2_256(&encoded))
        }

        /// Execute an approved reversal.
        ///
        /// 1. Freeze the target UTXOs (mark as reversed)
        /// 2. Create new UTXOs returning funds to the original sender
        /// 3. Update all storage and emit events
        fn execute_reversal(
            request_id: &H256,
            request: &ReversalRequest,
        ) -> DispatchResult {
            let current_height = pallet_qbc_utxo::CurrentHeight::<T>::get();
            let mut total_reversed: QbcBalance = 0;

            // Step 1: Freeze target UTXOs
            for vout in 0..256u32 {
                if let Some(utxo) = pallet_qbc_utxo::UtxoSet::<T>::get((&request.target_txid, vout)) {
                    // Skip already-frozen UTXOs
                    if FrozenUtxos::<T>::get((&request.target_txid, vout)) {
                        continue;
                    }

                    // Skip coinbase (should have been caught earlier, but double-check)
                    if utxo.is_coinbase {
                        continue;
                    }

                    // Freeze the UTXO
                    FrozenUtxos::<T>::insert((&request.target_txid, vout), true);

                    // Remove from UTXO set (makes it unspendable)
                    pallet_qbc_utxo::UtxoSet::<T>::remove((&request.target_txid, vout));

                    // Update balance cache
                    pallet_qbc_utxo::Balances::<T>::mutate(&utxo.address, |bal| {
                        *bal = bal.saturating_sub(utxo.amount);
                    });
                    pallet_qbc_utxo::UtxoCount::<T>::mutate(|n| *n = n.saturating_sub(1));

                    total_reversed = total_reversed.saturating_add(utxo.amount);

                    Self::deposit_event(Event::UtxoFrozen {
                        txid: request.target_txid,
                        vout,
                    });
                }
            }

            // Step 2: Create reversal UTXOs returning funds to original sender
            let reversal_txid = Self::compute_reversal_txid(request_id, current_height);

            if total_reversed > 0 {
                // Create a single UTXO returning all reversed funds
                let reversal_utxo = Utxo {
                    txid: reversal_txid,
                    vout: 0,
                    address: request.original_sender.clone(),
                    amount: total_reversed,
                    block_height: current_height,
                    is_coinbase: false,
                };

                pallet_qbc_utxo::UtxoSet::<T>::insert((&reversal_txid, 0u32), reversal_utxo);
                pallet_qbc_utxo::Balances::<T>::mutate(&request.original_sender, |bal| {
                    *bal = bal.saturating_add(total_reversed);
                });
                pallet_qbc_utxo::UtxoCount::<T>::mutate(|n| *n = n.saturating_add(1));
                pallet_qbc_utxo::TxCount::<T>::mutate(|n| *n = n.saturating_add(1));
            }

            // Step 3: Record execution
            let execution = ReversalExecution {
                request_id: *request_id,
                reversal_txid,
                execution_block_height: current_height,
                amount: total_reversed,
                original_txid: request.target_txid,
                recipient: request.original_sender.clone(),
            };

            ExecutedReversals::<T>::insert(request_id, execution);

            // Update request status
            ReversalRequests::<T>::mutate(request_id, |req| {
                if let Some(r) = req {
                    r.status = ReversalStatus::Executed;
                }
            });

            // Clean up votes
            ReversalVotes::<T>::remove(request_id);

            TotalExecuted::<T>::mutate(|n| *n = n.saturating_add(1));

            Self::deposit_event(Event::ReversalExecuted {
                request_id: *request_id,
                target_txid: request.target_txid,
                reversal_txid,
                amount: total_reversed,
                recipient: request.original_sender.clone(),
            });

            log::info!(
                "Reversal executed: {} QBC returned to {:?} (tx {:?})",
                total_reversed,
                request.original_sender,
                request.target_txid,
            );

            Ok(())
        }

        /// Compute a unique request ID from the target txid and block height.
        fn compute_request_id(target_txid: &TxId, block_height: u64) -> H256 {
            use sp_core::hashing::sha2_256;
            let mut data = sp_std::vec::Vec::new();
            data.extend_from_slice(b"reversal-request-v1:");
            data.extend_from_slice(target_txid.as_bytes());
            data.extend_from_slice(&block_height.to_le_bytes());
            H256::from(sha2_256(&data))
        }

        /// Compute the reversal transaction ID.
        fn compute_reversal_txid(request_id: &H256, block_height: u64) -> TxId {
            use sp_core::hashing::sha2_256;
            let mut data = sp_std::vec::Vec::new();
            data.extend_from_slice(b"reversal-tx-v1:");
            data.extend_from_slice(request_id.as_bytes());
            data.extend_from_slice(&block_height.to_le_bytes());
            H256::from(sha2_256(&data))
        }

        /// Check if a UTXO is frozen (reversed).
        pub fn utxo_is_frozen(txid: &TxId, vout: u32) -> bool {
            FrozenUtxos::<T>::get((txid, vout))
        }

        /// Get the current number of governors.
        pub fn governor_count() -> u32 {
            Governors::<T>::get().len() as u32
        }

        /// Get statistics about the reversibility system.
        pub fn stats() -> (u64, u64, u64) {
            (
                TotalRequests::<T>::get(),
                TotalExecuted::<T>::get(),
                TotalExpired::<T>::get(),
            )
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::pallet::*;
    use qbc_primitives::*;
    use sp_core::H256;
    use sp_runtime::BoundedVec;

    #[test]
    fn test_default_reversal_window() {
        assert_eq!(DEFAULT_REVERSAL_WINDOW, 26_182);
        // ~24 hours at 3.3s/block: 24 * 3600 / 3.3 ≈ 26,182
        let expected = (24.0_f64 * 3600.0 / 3.3).round() as u64;
        assert!((DEFAULT_REVERSAL_WINDOW as i64 - expected as i64).unsigned_abs() <= 1);
    }

    #[test]
    fn test_default_approval_threshold() {
        assert_eq!(DEFAULT_APPROVAL_THRESHOLD, 3);
    }

    #[test]
    fn test_max_governors() {
        assert_eq!(MAX_GOVERNORS, 10);
    }

    #[test]
    fn test_max_reason_length() {
        assert_eq!(MAX_REASON_LENGTH, 512);
    }

    #[test]
    fn test_reversal_status_variants() {
        let statuses = [
            ReversalStatus::Pending,
            ReversalStatus::Approved,
            ReversalStatus::Executed,
            ReversalStatus::Expired,
            ReversalStatus::Rejected,
        ];
        // All variants are distinct
        for i in 0..statuses.len() {
            for j in (i + 1)..statuses.len() {
                assert_ne!(statuses[i], statuses[j]);
            }
        }
    }

    #[test]
    fn test_reversal_request_encoding_roundtrip() {
        use codec::{Encode, Decode};

        let reason_bytes: BoundedVec<u8, sp_runtime::traits::ConstU32<MAX_REASON_LENGTH>> =
            b"test reason".to_vec().try_into().unwrap();

        let request = ReversalRequest {
            request_id: H256::from([1u8; 32]),
            target_txid: H256::from([2u8; 32]),
            original_sender: Address::from([3u8; 32]),
            amount: 1000,
            target_block_height: 100,
            request_block_height: 200,
            expiry_block_height: 26_382,
            approval_count: 2,
            status: ReversalStatus::Pending,
            reason: reason_bytes,
            requester: Address::from([3u8; 32]),
        };

        let encoded = request.encode();
        let decoded = ReversalRequest::decode(&mut &encoded[..]).unwrap();
        assert_eq!(request, decoded);
    }

    #[test]
    fn test_reversal_execution_encoding_roundtrip() {
        use codec::{Encode, Decode};

        let execution = ReversalExecution {
            request_id: H256::from([1u8; 32]),
            reversal_txid: H256::from([2u8; 32]),
            execution_block_height: 500,
            amount: 50_000,
            original_txid: H256::from([3u8; 32]),
            recipient: Address::from([4u8; 32]),
        };

        let encoded = execution.encode();
        let decoded = ReversalExecution::decode(&mut &encoded[..]).unwrap();
        assert_eq!(execution, decoded);
    }

    #[test]
    fn test_reason_bounded_vec_max_length() {
        // Should fit within MAX_REASON_LENGTH
        let short: Result<BoundedVec<u8, sp_runtime::traits::ConstU32<MAX_REASON_LENGTH>>, _> =
            b"short reason".to_vec().try_into();
        assert!(short.is_ok());

        // Should reject data exceeding MAX_REASON_LENGTH
        let too_long: Result<BoundedVec<u8, sp_runtime::traits::ConstU32<MAX_REASON_LENGTH>>, _> =
            vec![0u8; MAX_REASON_LENGTH as usize + 1].try_into();
        assert!(too_long.is_err());

        // Exactly MAX_REASON_LENGTH should work
        let exact: Result<BoundedVec<u8, sp_runtime::traits::ConstU32<MAX_REASON_LENGTH>>, _> =
            vec![0u8; MAX_REASON_LENGTH as usize].try_into();
        assert!(exact.is_ok());
    }

    #[test]
    fn test_governor_bounded_vec() {
        let mut governors: BoundedVec<Address, sp_runtime::traits::ConstU32<MAX_GOVERNORS>> =
            BoundedVec::new();

        // Add up to MAX_GOVERNORS
        for i in 0..MAX_GOVERNORS {
            let addr = Address::from([i as u8; 32]);
            assert!(governors.try_push(addr).is_ok());
        }

        // One more should fail
        let extra = Address::from([0xFF; 32]);
        assert!(governors.try_push(extra).is_err());
    }

    #[test]
    fn test_reversal_status_clone_eq() {
        let s1 = ReversalStatus::Pending;
        let s2 = s1.clone();
        assert_eq!(s1, s2);

        let s3 = ReversalStatus::Executed;
        assert_ne!(s1, s3);
    }
}
