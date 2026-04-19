//! Service configuration for the Qubitcoin node.
//!
//! Sets up networking, consensus (Aura + GRANDPA), transaction pool, RPC,
//! and optional VQE mining engine.

use codec::Encode;
use qbc_runtime::{self, opaque::Block, RuntimeApi};
use sc_client_api::{Backend, StorageProvider};
use sc_consensus_aura::{ImportQueueParams, SlotProportion, StartAuraParams};
use sc_consensus_grandpa::SharedVoterState;
use sc_service::{error::Error as ServiceError, Configuration, TaskManager, WarpSyncConfig};
use sc_telemetry::{Telemetry, TelemetryWorker};
use sc_transaction_pool_api::OffchainTransactionPoolFactory;
use sp_api::ProvideRuntimeApi;
use sp_blockchain::HeaderBackend;
use futures::FutureExt;
use sp_consensus_aura::sr25519::AuthorityPair as AuraPair;
use std::sync::Arc;

/// The full client type.
pub type FullClient = sc_service::TFullClient<Block, RuntimeApi, sc_executor::WasmExecutor<sp_io::SubstrateHostFunctions>>;
pub(crate) type FullBackend = sc_service::TFullBackend<Block>;

// ═══════════════════════════════════════════════════════════════════════
// Fork Choice Rule — Weighted Chain Selection
// ═══════════════════════════════════════════════════════════════════════
//
// Matches the Python node's fork choice rule exactly:
//   weight_per_block = DIFFICULTY_SCALE / difficulty
//   chain_weight     = sum(weight_i for each block)
//   tiebreak:          lexicographically smaller block hash wins
//
// In QBC's PoSA consensus, HIGHER difficulty = EASIER mining. Lower
// difficulty numbers represent MORE work, so get higher weight (1/d).
//
// See `weighted_chain.rs` for the full implementation with aux-DB caching.
type FullSelectChain = crate::weighted_chain::WeightedChain<FullBackend, FullClient>;

// ═══════════════════════════════════════════════════════════════════════
// Substrate ↔ Mining Engine Bridge
// ═══════════════════════════════════════════════════════════════════════

/// Bridge from Substrate client to mining engine's `ChainReader` trait.
struct SubstrateChainReader {
    client: Arc<FullClient>,
}

impl qbc_mining::ChainReader for SubstrateChainReader {
    fn best_hash(&self) -> sp_core::H256 {
        self.client.info().best_hash
    }

    fn best_number(&self) -> u64 {
        self.client.info().best_number as u64
    }

    fn parent_hash(&self, hash: &sp_core::H256) -> Option<sp_core::H256> {
        self.client
            .header(*hash)
            .ok()
            .flatten()
            .map(|h| h.parent_hash)
    }

    fn current_difficulty(&self, at: &sp_core::H256) -> Option<u64> {
        // Read CurrentDifficulty from pallet-qbc-consensus storage.
        // Storage key: twox_128("QbcConsensus") ++ twox_128("CurrentDifficulty")
        let key = current_difficulty_storage_key();
        self.client
            .storage(*at, &sc_client_api::StorageKey(key))
            .ok()
            .flatten()
            .and_then(|data| {
                codec::Decode::decode(&mut &data.0[..]).ok()
            })
    }

    fn current_height(&self, at: &sp_core::H256) -> Option<u64> {
        // Read CurrentHeight from pallet-qbc-utxo storage.
        // Storage key: twox_128("QbcUtxo") ++ twox_128("CurrentHeight")
        let key = current_height_storage_key();
        self.client
            .storage(*at, &sc_client_api::StorageKey(key))
            .ok()
            .flatten()
            .and_then(|data| {
                codec::Decode::decode(&mut &data.0[..]).ok()
            })
    }
}

/// Bridge from Substrate to mining engine's `ProofSubmitter` trait.
struct SubstrateProofSubmitter {
    client: Arc<FullClient>,
    pool: Arc<sc_transaction_pool::TransactionPoolHandle<Block, FullClient>>,
    keystore: sp_keystore::KeystorePtr,
}

impl qbc_mining::ProofSubmitter for SubstrateProofSubmitter {
    fn submit_proof(
        &self,
        params: Vec<i64>,
        energy: i128,
        hamiltonian_seed: sp_core::H256,
        n_qubits: u8,
    ) -> Result<sp_core::H256, String> {
        use sp_keyring::Sr25519Keyring;
        use sp_runtime::BoundedVec;
        use sp_runtime::traits::ConstU32;

        // Build the VqeProof
        let bounded_params: BoundedVec<i64, ConstU32<32>> =
            params.try_into().map_err(|_| "Too many VQE params (max 32)".to_string())?;

        let proof = qbc_primitives::VqeProof {
            params: bounded_params,
            energy,
            hamiltonian_seed,
            n_qubits,
        };

        // The miner_address parameter is ignored by the pallet (it derives
        // the address from the signed origin), but we must pass it for the call.
        let miner_address = qbc_primitives::Address([0u8; 32]);

        // Construct the RuntimeCall for submit_mining_proof
        let call = qbc_runtime::RuntimeCall::QbcConsensus(
            pallet_qbc_consensus::Call::submit_mining_proof {
                miner_address,
                vqe_proof: proof,
            },
        );

        let best_hash = self.client.info().best_hash;

        // Get signer public key from keystore (AURA key) or fall back to Alice
        let signer_pub = {
            let keys = sp_keystore::Keystore::sr25519_public_keys(
                &*self.keystore,
                sp_core::crypto::key_types::AURA,
            );
            if let Some(pub_key) = keys.first() {
                *pub_key
            } else {
                Sr25519Keyring::Alice.public()
            }
        };

        let account_id: qbc_runtime::AccountId = signer_pub.into();

        // Get the account nonce via runtime API
        let nonce: qbc_runtime::Nonce = {
            use frame_system_rpc_runtime_api::AccountNonceApi;
            self.client
                .runtime_api()
                .account_nonce(best_hash, account_id.clone())
                .map_err(|e| format!("Failed to get nonce: {:?}", e))?
        };

        // Get genesis hash and runtime version for the signed extra
        let genesis_hash = self.client
            .hash(0u32.into())
            .map_err(|e| format!("Failed to get genesis hash: {:?}", e))?
            .ok_or_else(|| "Genesis block not found".to_string())?;

        let spec_version = qbc_runtime::VERSION.spec_version;
        let transaction_version = qbc_runtime::VERSION.transaction_version;

        // Construct SignedExtra (must match runtime's SignedExtra type exactly)
        let extra: qbc_runtime::SignedExtra = (
            frame_system::CheckNonZeroSender::new(),
            frame_system::CheckSpecVersion::new(),
            frame_system::CheckTxVersion::new(),
            frame_system::CheckGenesis::new(),
            frame_system::CheckEra::from(sp_runtime::generic::Era::Immortal),
            frame_system::CheckNonce::from(nonce),
            frame_system::CheckWeight::new(),
            pallet_transaction_payment::ChargeTransactionPayment::from(0u128),
        );

        // Build the raw payload to sign: (call, extra, additional_signed)
        // additional_signed = ((), spec_version, tx_version, genesis_hash, genesis_hash, (), (), ())
        let additional_signed = (
            (),                    // CheckNonZeroSender
            spec_version,          // CheckSpecVersion
            transaction_version,   // CheckTxVersion
            genesis_hash,          // CheckGenesis
            genesis_hash,          // CheckEra (immortal → genesis_hash)
            (),                    // CheckNonce
            (),                    // CheckWeight
            (),                    // ChargeTransactionPayment
        );

        let raw_payload = (&call, &extra, &additional_signed);
        let signature = raw_payload.using_encoded(|payload| {
            // If > 256 bytes, hash first (Substrate convention)
            let msg = if payload.len() > 256 {
                sp_core::hashing::blake2_256(payload).to_vec()
            } else {
                payload.to_vec()
            };
            sp_keystore::Keystore::sr25519_sign(
                &*self.keystore,
                sp_core::crypto::key_types::AURA,
                &signer_pub,
                &msg,
            )
        })
        .map_err(|e| format!("Keystore sign error: {:?}", e))?
        .ok_or_else(|| "Key not found in keystore".to_string())?;

        let multi_sig = sp_runtime::MultiSignature::Sr25519(signature);

        // Build the unchecked extrinsic
        let extrinsic = qbc_runtime::UncheckedExtrinsic::new_signed(
            call,
            sp_runtime::MultiAddress::Id(account_id),
            multi_sig,
            extra,
        );

        // Compute a hash for logging
        let encoded = extrinsic.encode();
        let tx_hash = sp_core::H256::from_slice(
            &sp_core::hashing::blake2_256(&encoded),
        );

        // Convert to opaque extrinsic for pool submission
        #[allow(deprecated)]
        let opaque = sp_runtime::OpaqueExtrinsic::from_bytes(&encoded)
            .map_err(|_| "Failed to encode extrinsic".to_string())?;

        // Submit to the transaction pool
        use sc_transaction_pool_api::TransactionPool;
        let submit_future = self.pool.submit_one(
            best_hash,
            sp_runtime::transaction_validity::TransactionSource::Local,
            opaque.into(),
        );

        // Block on submission (we're already in a blocking thread)
        let result = tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(submit_future)
        });

        match result {
            Ok(_) => {
                log::info!(
                    target: "mining",
                    "Mining proof submitted to pool: energy={}, n_qubits={}, tx_hash={:?}",
                    energy, n_qubits, tx_hash
                );
                Ok(tx_hash)
            }
            Err(e) => {
                Err(format!("Failed to submit to pool: {:?}", e))
            }
        }
    }
}

/// Compute the storage key for `QbcConsensus::CurrentDifficulty`.
fn current_difficulty_storage_key() -> Vec<u8> {
    let mut key = Vec::new();
    key.extend_from_slice(&sp_core::twox_128(b"QbcConsensus"));
    key.extend_from_slice(&sp_core::twox_128(b"CurrentDifficulty"));
    key
}

/// Compute the storage key for `QbcUtxo::CurrentHeight`.
fn current_height_storage_key() -> Vec<u8> {
    let mut key = Vec::new();
    key.extend_from_slice(&sp_core::twox_128(b"QbcUtxo"));
    key.extend_from_slice(&sp_core::twox_128(b"CurrentHeight"));
    key
}

// ═══════════════════════════════════════════════════════════════════════
// Node Service
// ═══════════════════════════════════════════════════════════════════════

/// Creates a new partial node (shared components between full and light).
pub fn new_partial(
    config: &Configuration,
) -> Result<
    sc_service::PartialComponents<
        FullClient,
        FullBackend,
        FullSelectChain,
        sc_consensus::DefaultImportQueue<Block>,
        sc_transaction_pool::TransactionPoolHandle<Block, FullClient>,
        (
            sc_consensus_grandpa::GrandpaBlockImport<FullBackend, Block, FullClient, FullSelectChain>,
            sc_consensus_grandpa::LinkHalf<Block, FullClient, FullSelectChain>,
            Option<Telemetry>,
        ),
    >,
    ServiceError,
> {
    let telemetry = config
        .telemetry_endpoints
        .clone()
        .filter(|x| !x.is_empty())
        .map(|endpoints| -> Result<_, sc_telemetry::Error> {
            let worker = TelemetryWorker::new(16)?;
            let telemetry = worker.handle().new_telemetry(endpoints);
            Ok((worker, telemetry))
        })
        .transpose()?;

    let executor = sc_service::new_wasm_executor::<sp_io::SubstrateHostFunctions>(&config.executor);

    let (client, backend, keystore_container, task_manager) =
        sc_service::new_full_parts::<Block, RuntimeApi, _>(
            config,
            telemetry.as_ref().map(|(_, telemetry)| telemetry.handle()),
            executor,
        )?;
    let client = Arc::new(client);

    let telemetry = telemetry.map(|(worker, telemetry)| {
        task_manager
            .spawn_handle()
            .spawn("telemetry", None, worker.run());
        telemetry
    });

    let select_chain = crate::weighted_chain::WeightedChain::new(backend.clone(), client.clone());

    let transaction_pool = sc_transaction_pool::Builder::new(
        task_manager.spawn_essential_handle(),
        client.clone(),
        config.role.is_authority().into(),
    )
    .with_options(config.transaction_pool.clone())
    .with_prometheus(config.prometheus_registry())
    .build();

    let (grandpa_block_import, grandpa_link) = sc_consensus_grandpa::block_import(
        client.clone(),
        512,
        &client,
        select_chain.clone(),
        telemetry.as_ref().map(|x| x.handle()),
    )?;

    let slot_duration = sc_consensus_aura::slot_duration(&*client)?;

    let import_queue =
        sc_consensus_aura::import_queue::<AuraPair, _, _, _, _, _>(ImportQueueParams {
            block_import: grandpa_block_import.clone(),
            justification_import: Some(Box::new(grandpa_block_import.clone())),
            client: client.clone(),
            create_inherent_data_providers: move |_, ()| async move {
                let timestamp = sp_timestamp::InherentDataProvider::from_system_time();

                let slot =
                    sp_consensus_aura::inherents::InherentDataProvider::from_timestamp_and_slot_duration(
                        *timestamp,
                        slot_duration,
                    );

                Ok((slot, timestamp))
            },
            spawner: &task_manager.spawn_essential_handle(),
            registry: config.prometheus_registry(),
            check_for_equivocation: Default::default(),
            telemetry: telemetry.as_ref().map(|x| x.handle()),
            compatibility_mode: Default::default(),
        })?;

    Ok(sc_service::PartialComponents {
        client,
        backend,
        task_manager,
        import_queue,
        keystore_container,
        select_chain,
        transaction_pool: Arc::new(transaction_pool),
        other: (grandpa_block_import, grandpa_link, telemetry),
    })
}

/// Builds a new service for a full client.
///
/// # Arguments
/// * `config` - Substrate service configuration.
/// * `mining_enabled` - Whether to start VQE mining threads.
/// * `mining_threads` - Number of mining threads to spawn.
pub fn new_full(
    config: Configuration,
    mining_enabled: bool,
    mining_threads: u32,
    p2p_bridge_addr: Option<String>,
    sync_peer_url: Option<String>,
) -> Result<TaskManager, ServiceError> {
    let sc_service::PartialComponents {
        client,
        backend,
        mut task_manager,
        import_queue,
        keystore_container,
        select_chain,
        transaction_pool,
        other: (block_import, grandpa_link, mut telemetry),
    } = new_partial(&config)?;

    let grandpa_protocol_name = sc_consensus_grandpa::protocol_standard_name(
        &client
            .hash(0u32.into())
            .ok()
            .flatten()
            .expect("Genesis block exists; qed"),
        &config.chain_spec,
    );

    let metrics = sc_network::NotificationMetrics::new(
        config.prometheus_registry(),
    );

    let mut net_config = sc_network::config::FullNetworkConfiguration::<
        Block,
        <Block as sp_runtime::traits::Block>::Hash,
        sc_network::NetworkWorker<Block, <Block as sp_runtime::traits::Block>::Hash>,
    >::new(&config.network, config.prometheus_registry().cloned());

    let peer_store_handle = net_config.peer_store_handle();

    let (grandpa_protocol_config, grandpa_notification_service) =
        sc_consensus_grandpa::grandpa_peers_set_config::<Block, sc_network::NetworkWorker<Block, <Block as sp_runtime::traits::Block>::Hash>>(
            grandpa_protocol_name.clone(),
            metrics.clone(),
            peer_store_handle,
        );

    net_config.add_notification_protocol(grandpa_protocol_config);

    let warp_sync_config = WarpSyncConfig::WithProvider(
        Arc::new(sc_consensus_grandpa::warp_proof::NetworkProvider::new(
            backend.clone(),
            grandpa_link.shared_authority_set().clone(),
            Vec::default(),
        )),
    );

    let (network, system_rpc_tx, tx_handler_controller, sync_service) =
        sc_service::build_network(sc_service::BuildNetworkParams {
            config: &config,
            net_config,
            client: client.clone(),
            transaction_pool: transaction_pool.clone(),
            spawn_handle: task_manager.spawn_handle(),
            import_queue,
            block_announce_validator_builder: None,
            warp_sync_config: Some(warp_sync_config),
            block_relay: None,
            metrics,
        })?;

    if config.offchain_worker.enabled {
        let offchain_workers = sc_offchain::OffchainWorkers::new(sc_offchain::OffchainWorkerOptions {
            runtime_api_provider: client.clone(),
            is_validator: config.role.is_authority(),
            keystore: Some(keystore_container.keystore()),
            offchain_db: backend.offchain_storage(),
            transaction_pool: Some(OffchainTransactionPoolFactory::new(
                transaction_pool.clone(),
            )),
            network_provider: Arc::new(network.clone()),
            enable_http_requests: true,
            custom_extensions: |_| vec![],
        })
        .expect("Failed to create offchain workers");

        task_manager.spawn_handle().spawn(
            "offchain-workers-runner",
            "offchain-worker",
            offchain_workers
                .run(client.clone(), task_manager.spawn_handle())
                .boxed(),
        );
    }

    let role = config.role;
    let force_authoring = config.force_authoring;
    let backoff_authoring_blocks: Option<()> = None;
    let name = config.network.node_name.clone();
    let enable_grandpa = !config.disable_grandpa;
    let prometheus_registry = config.prometheus_registry().cloned();

    let rpc_extensions_builder = {
        let client = client.clone();
        let pool = transaction_pool.clone();

        Box::new(move |_| {
            let deps = crate::rpc::FullDeps {
                client: client.clone(),
                pool: pool.clone(),
            };
            crate::rpc::create_full::<_, _, FullBackend>(deps).map_err(Into::into)
        })
    };

    let _rpc_handlers = sc_service::spawn_tasks(sc_service::SpawnTasksParams {
        network: network.clone(),
        client: client.clone(),
        keystore: keystore_container.keystore(),
        task_manager: &mut task_manager,
        transaction_pool: transaction_pool.clone(),
        rpc_builder: rpc_extensions_builder,
        backend: backend.clone(),
        system_rpc_tx,
        tx_handler_controller,
        sync_service: sync_service.clone(),
        config,
        telemetry: telemetry.as_mut(),
        tracing_execute_block: None,
    })?;

    // ── Block Authoring Strategy ────────────────────────────────────
    //
    // When mining is enabled (--mine):
    //   VQE-gated block authoring. Blocks are ONLY produced when the
    //   mining engine finds a VQE solution. Aura authoring is NOT started.
    //
    // When mining is disabled:
    //   Standard Aura slot-based block authoring (for validator nodes
    //   that don't mine but still need to produce blocks in dev mode).
    //
    // In both cases, the Aura import queue is active for validating
    // incoming blocks from peers.

    if mining_enabled {
        log::info!(
            target: "mining",
            "VQE-gated block authoring enabled — Aura authoring disabled"
        );
        log::info!(
            target: "mining",
            "Starting {} VQE mining thread(s)",
            mining_threads
        );

        // Create channel for mining engine → block author notifications.
        // Buffer of 4: one per mining thread + headroom.
        let (proof_tx, proof_rx) =
            std::sync::mpsc::sync_channel::<qbc_mining::MiningProofReady>(4);

        // Shared atomic: tracks the last block height for which a proof was
        // successfully submitted. Prevents multiple threads from submitting
        // duplicate proofs for the same height (causes TooLowPriority errors).
        let last_proved_height: qbc_mining::engine::LastProvedHeight =
            Arc::new(std::sync::atomic::AtomicU64::new(0));

        // Spawn mining threads
        for i in 0..mining_threads {
            let mining_client = client.clone();
            let mining_pool = transaction_pool.clone();
            let mining_keystore = keystore_container.keystore();
            let mining_proof_tx = proof_tx.clone();
            let mining_last_proved = last_proved_height.clone();
            let task_name: &'static str = Box::leak(format!("vqe-miner-{}", i).into_boxed_str());

            task_manager
                .spawn_essential_handle()
                .spawn_blocking(
                    task_name,
                    Some("mining"),
                    async move {
                        let reader = Arc::new(SubstrateChainReader {
                            client: mining_client.clone(),
                        });
                        let submitter = Arc::new(SubstrateProofSubmitter {
                            client: mining_client,
                            pool: mining_pool,
                            keystore: mining_keystore,
                        });
                        let config = qbc_mining::MiningConfig {
                            thread_id: i,
                            max_attempts: qbc_mining::engine::MAX_ATTEMPTS,
                        };

                        // Run the blocking mining loop with proof notification
                        tokio::task::spawn_blocking(move || {
                            qbc_mining::engine::run_mining_with_notify(
                                reader,
                                submitter,
                                config,
                                Some(mining_proof_tx),
                                mining_last_proved,
                            );
                        })
                        .await
                        .expect("Mining thread panicked");
                    },
                );
        }
        // Drop the original sender so the channel closes when all miners stop
        drop(proof_tx);

        // Spawn VQE-gated block author
        let author_proposer_factory = sc_basic_authorship::ProposerFactory::new(
            task_manager.spawn_handle(),
            client.clone(),
            transaction_pool.clone(),
            prometheus_registry.as_ref(),
            telemetry.as_ref().map(|x| x.handle()),
        );

        task_manager
            .spawn_essential_handle()
            .spawn_blocking(
                "vqe-block-author",
                Some("block-authoring"),
                crate::block_author::run_vqe_block_author(
                    client.clone(),
                    author_proposer_factory,
                    block_import,
                    keystore_container.keystore(),
                    proof_rx,
                ),
            );
    } else if role.is_authority() {
        // Standard Aura block authoring (dev/validator mode without mining)
        let proposer_factory = sc_basic_authorship::ProposerFactory::new(
            task_manager.spawn_handle(),
            client.clone(),
            transaction_pool.clone(),
            prometheus_registry.as_ref(),
            telemetry.as_ref().map(|x| x.handle()),
        );

        let slot_duration = sc_consensus_aura::slot_duration(&*client)?;

        let aura = sc_consensus_aura::start_aura::<AuraPair, _, _, _, _, _, _, _, _, _, _>(
            StartAuraParams {
                slot_duration,
                client: client.clone(),
                select_chain,
                block_import,
                proposer_factory,
                create_inherent_data_providers: move |_, ()| async move {
                    let timestamp = sp_timestamp::InherentDataProvider::from_system_time();

                    let slot =
                        sp_consensus_aura::inherents::InherentDataProvider::from_timestamp_and_slot_duration(
                            *timestamp,
                            slot_duration,
                        );

                    Ok((slot, timestamp))
                },
                force_authoring,
                backoff_authoring_blocks,
                keystore: keystore_container.keystore(),
                sync_oracle: sync_service.clone(),
                justification_sync_link: sync_service.clone(),
                block_proposal_slot_portion: SlotProportion::new(2f32 / 3f32),
                max_block_proposal_slot_portion: None,
                telemetry: telemetry.as_ref().map(|x| x.handle()),
                compatibility_mode: Default::default(),
            },
        )?;

        task_manager
            .spawn_essential_handle()
            .spawn_blocking("aura", Some("block-authoring"), aura);
    }

    if enable_grandpa {
        let grandpa_config = sc_consensus_grandpa::Config {
            gossip_duration: std::time::Duration::from_millis(333),
            justification_generation_period: 512,
            name: Some(name),
            observer_enabled: false,
            keystore: Some(keystore_container.keystore()),
            local_role: role,
            telemetry: telemetry.as_ref().map(|x| x.handle()),
            protocol_name: grandpa_protocol_name,
        };

        let grandpa = sc_consensus_grandpa::run_grandpa_voter(sc_consensus_grandpa::GrandpaParams {
            config: grandpa_config,
            link: grandpa_link,
            network,
            sync: sync_service,
            notification_service: grandpa_notification_service,
            voting_rule: sc_consensus_grandpa::VotingRulesBuilder::default().build(),
            prometheus_registry,
            shared_voter_state: SharedVoterState::empty(),
            telemetry: telemetry.as_ref().map(|x| x.handle()),
            offchain_tx_pool_factory: OffchainTransactionPoolFactory::new(
                transaction_pool,
            ),
        })?;

        task_manager
            .spawn_essential_handle()
            .spawn_blocking("grandpa-voter", None, grandpa);
    }

    // ── P2P Bridge ────────────────────────────────────────────────
    // Connect to the existing Rust P2P daemon via gRPC.
    // The bridge relays blocks and transactions between Substrate and
    // the custom gossipsub network.
    if let Some(ref bridge_addr) = p2p_bridge_addr {
        log::info!(
            target: "p2p-bridge",
            "Spawning P2P bridge to {}",
            bridge_addr
        );

        let _broadcaster = qbc_p2p_bridge::spawn_p2p_bridge(
            task_manager.spawn_handle(),
            client.clone(),
            bridge_addr.clone(),
            sync_peer_url,
        );

        // The broadcaster can be stored for outbound block/tx propagation.
        // For now, inbound streaming is the primary use case.
    }

    Ok(task_manager)
}

/// Create chain ops for CLI commands.
pub fn new_chain_ops(
    config: &Configuration,
) -> Result<
    (
        Arc<FullClient>,
        Arc<FullBackend>,
        sc_consensus::DefaultImportQueue<Block>,
        TaskManager,
    ),
    ServiceError,
> {
    let sc_service::PartialComponents {
        client,
        backend,
        import_queue,
        task_manager,
        ..
    } = new_partial(config)?;
    Ok((client, backend, import_queue, task_manager))
}
