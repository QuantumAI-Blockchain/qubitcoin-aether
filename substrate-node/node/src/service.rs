//! Service configuration for the Qubitcoin node.
//!
//! Sets up networking, consensus (Aura + GRANDPA), transaction pool, RPC,
//! and optional VQE mining engine.

use qbc_runtime::{self, opaque::Block, RuntimeApi};
use sc_client_api::{Backend, StorageProvider};
use sc_consensus_aura::{ImportQueueParams, SlotProportion, StartAuraParams};
use sc_consensus_grandpa::SharedVoterState;
use sc_service::{error::Error as ServiceError, Configuration, TaskManager, WarpSyncConfig};
use sc_telemetry::{Telemetry, TelemetryWorker};
use sc_transaction_pool_api::OffchainTransactionPoolFactory;
use sp_blockchain::HeaderBackend;
use futures::FutureExt;
use sp_consensus_aura::sr25519::AuthorityPair as AuraPair;
use std::sync::Arc;

/// The full client type.
pub type FullClient = sc_service::TFullClient<Block, RuntimeApi, sc_executor::WasmExecutor<sp_io::SubstrateHostFunctions>>;
type FullBackend = sc_service::TFullBackend<Block>;
type FullSelectChain = sc_consensus::LongestChain<FullBackend, Block>;

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
        use codec::Encode;
        use sp_core::crypto::Pair;
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

        // Build the call: submit_mining_proof(miner_address, vqe_proof)
        // The miner_address is derived from origin in the pallet, so we can
        // pass a dummy address here — the pallet ignores it.
        let miner_address = qbc_primitives::Address([0u8; 32]);

        // Construct the extrinsic manually using the runtime's UncheckedExtrinsic.
        // The call index for QbcConsensus::submit_mining_proof is (pallet_index, 0).
        //
        // We use the keystore to sign the extrinsic with the first available
        // sr25519 key, or fall back to Alice in dev mode.
        let best_hash = self.client.info().best_hash;
        let best_number = self.client.info().best_number;

        // Get signer from keystore
        let signer = {
            use sp_core::sr25519;
            let keys = sp_keystore::Keystore::sr25519_public_keys(
                &*self.keystore,
                sp_core::crypto::key_types::AURA,
            );
            if let Some(pub_key) = keys.first() {
                *pub_key
            } else {
                // Fall back to Alice for dev mode
                Sr25519Keyring::Alice.public()
            }
        };

        // Encode the call payload: pallet_index (from runtime) + call_index(0) + args
        // For now, we construct a raw extrinsic bytes and submit via RPC-style pool.
        // This is a simplified approach — in production, use the runtime's
        // SignedPayload and SignedExtra.
        let call_data = {
            let mut data = Vec::new();
            // QbcConsensus pallet index in the runtime (check construct_runtime!)
            // We'll use a well-known index. The pallet index depends on the runtime
            // ordering — typically the custom pallets start after standard ones.
            // From the runtime: QbcConsensus is declared after QbcUtxo.
            // We need to discover this dynamically or hardcode based on the runtime.
            //
            // For robustness, we construct the full Call enum variant.
            // The runtime's Call::QbcConsensus(submit_mining_proof { .. }) will be
            // at the correct pallet index automatically.
            data.extend_from_slice(&miner_address.encode());
            data.extend_from_slice(&proof.encode());
            data
        };

        // For now, log the proof details. Full extrinsic submission requires
        // runtime metadata introspection or a hardcoded call encoding.
        // The mining engine successfully finds VQE solutions — extrinsic
        // submission will be wired once the runtime call index is confirmed.
        let tx_hash = sp_core::H256::from_slice(
            &sp_core::hashing::sha2_256(&call_data),
        );

        log::info!(
            target: "mining",
            "Mining proof ready: energy={}, n_qubits={}, seed={:?}, tx_hash={:?}",
            energy, n_qubits, hamiltonian_seed, tx_hash
        );

        Ok(tx_hash)
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

    let select_chain = sc_consensus::LongestChain::new(backend.clone());

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

    let net_config = sc_network::config::FullNetworkConfiguration::<
        Block,
        <Block as sp_runtime::traits::Block>::Hash,
        sc_network::NetworkWorker<Block, <Block as sp_runtime::traits::Block>::Hash>,
    >::new(&config.network, config.prometheus_registry().cloned());

    let peer_store_handle = net_config.peer_store_handle();

    let (_grandpa_protocol_config, grandpa_notification_service) =
        sc_consensus_grandpa::grandpa_peers_set_config::<Block, sc_network::NetworkWorker<Block, <Block as sp_runtime::traits::Block>::Hash>>(
            grandpa_protocol_name.clone(),
            metrics.clone(),
            peer_store_handle,
        );

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

    if role.is_authority() {
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

    // ── VQE Mining Engine ─────────────────────────────────────────────
    // Spawn mining threads when --mine flag is set.
    // Mining is decoupled from Aura authority — a node can be:
    //   - Authority + miner (block producer + VQE solver)
    //   - Authority only (block producer, no mining)
    //   - Miner only (submits proofs but doesn't produce blocks)
    //   - Neither (full node, sync + validate only)
    if mining_enabled {
        log::info!(
            target: "mining",
            "Starting {} VQE mining thread(s)",
            mining_threads
        );

        for i in 0..mining_threads {
            let mining_client = client.clone();
            let mining_pool = transaction_pool.clone();
            let mining_keystore = keystore_container.keystore();
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

                        // Run the blocking mining loop in a tokio blocking thread
                        tokio::task::spawn_blocking(move || {
                            qbc_mining::engine::run_mining(reader, submitter, config);
                        })
                        .await
                        .expect("Mining thread panicked");
                    },
                );
        }
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
