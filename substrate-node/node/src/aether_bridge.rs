//! Aether Mind ↔ Substrate bridge.
//!
//! Background task that watches for new blocks and submits Proof-of-Thought
//! attestations from the Aether Mind neural engine (port 5003) to the
//! `qbc-aether-anchor` pallet.
//!
//! ## Flow
//!
//! 1. Poll chain best block number every 5 seconds
//! 2. When a new block is detected, fetch PoT from aether-mind /aether/pot
//! 3. Build a `record_block_state` extrinsic signed with the node's Aura key
//! 4. Submit to the transaction pool
//!
//! This runs independently from block authoring — no latency impact on mining.

use codec::Encode;
use sc_transaction_pool_api::TransactionPool;
use sp_api::ProvideRuntimeApi;
use sp_blockchain::HeaderBackend;
use sp_core::H256;
use sp_keystore::KeystorePtr;
use std::sync::Arc;

use crate::service::{FullClient};
use qbc_runtime::opaque::Block;

type Pool = sc_transaction_pool::TransactionPoolHandle<Block, FullClient>;

/// Aether Mind PoT response (subset of fields we need).
#[derive(serde::Deserialize, Debug)]
struct PotResponse {
    proof_of_thought: PotData,
}

#[derive(serde::Deserialize, Debug)]
struct PotData {
    attestation_hash: String,
    phi: f64,
    phi_micro: f64,
    phi_meso: f64,
    phi_macro: f64,
    active_sephirot: u8,
    knowledge_vectors: u64,
    chain_height: u64,
}

/// Gates status response.
#[derive(serde::Deserialize, Debug)]
struct GatesResponse {
    gates_passed: u32,
    gates_total: u32,
    phi_ceiling: f64,
}

/// Run the Aether bridge loop. Spawned as a background task from service.rs.
pub async fn run_aether_bridge(
    client: Arc<FullClient>,
    pool: Arc<Pool>,
    keystore: KeystorePtr,
    aether_url: String,
) {
    let http = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .expect("HTTP client");

    let mut last_submitted_height: u64 = 0;
    let mut last_gates_check: u64 = 0;

    // Wait for the node to start up and produce a few blocks before submitting PoT.
    // This prevents nonce collisions with the mining proof extrinsics during startup.
    tokio::time::sleep(std::time::Duration::from_secs(60)).await;
    log::info!(target: "aether-bridge", "Aether bridge started — polling {} for PoT", aether_url);

    loop {
        // Poll every 30s instead of 5s to avoid nonce collisions with mining proofs.
        // Mining proofs are time-critical (must be included in the next block);
        // PoT attestations are not — they just record state and can lag by a few blocks.
        tokio::time::sleep(std::time::Duration::from_secs(30)).await;

        let best_number = client.info().best_number as u64;
        if best_number <= last_submitted_height {
            continue;
        }
        // Skip if only 1 block ahead — wait for a small batch to reduce tx pool contention
        if best_number < last_submitted_height + 3 {
            continue;
        }

        // Fetch PoT from aether-mind
        let pot_url = format!("{}/aether/pot", aether_url);
        let pot_data = match http.get(&pot_url).send().await {
            Ok(resp) => match resp.json::<PotResponse>().await {
                Ok(data) => data.proof_of_thought,
                Err(e) => {
                    log::debug!(target: "aether-bridge", "PoT parse error: {}", e);
                    continue;
                }
            },
            Err(e) => {
                log::debug!(target: "aether-bridge", "Aether unreachable: {}", e);
                continue;
            }
        };

        // Convert attestation hash to H256
        let attestation_hex = pot_data.attestation_hash.trim_start_matches("0x");
        let thought_proof_hash = match hex::decode(attestation_hex) {
            Ok(bytes) if bytes.len() == 32 => H256::from_slice(&bytes),
            _ => {
                log::warn!(target: "aether-bridge", "Invalid attestation hash length");
                continue;
            }
        };

        // Scale phi to u64 (phi * 1000)
        let phi_scaled = (pot_data.phi * 1000.0) as u64;
        let chain_height = pot_data.chain_height;
        let knowledge_vectors = pot_data.knowledge_vectors;

        // Build the record_block_state call
        let call = qbc_runtime::RuntimeCall::QbcAetherAnchor(
            pallet_qbc_aether_anchor::Call::record_block_state {
                block_height: chain_height,
                knowledge_root: H256::zero(), // Phase 2: real Merkle root of fabric
                phi_scaled,
                knowledge_nodes: knowledge_vectors,
                knowledge_edges: 0, // Phase 2: edge count
                thought_proof_hash,
                reasoning_ops: 0, // Phase 2: reasoning op count
            },
        );

        // Sign and submit
        match submit_extrinsic(&client, &pool, &keystore, call).await {
            Ok(hash) => {
                last_submitted_height = best_number;
                log::info!(
                    target: "aether-bridge",
                    "PoT submitted: height={}, phi={:.3}, vectors={}, sephirot={}, tx={:?}",
                    chain_height, pot_data.phi, knowledge_vectors,
                    pot_data.active_sephirot, hash
                );
            }
            Err(e) => {
                log::warn!(target: "aether-bridge", "PoT submit failed: {}", e);
            }
        }

        // Check gates every 100 blocks
        if best_number > last_gates_check + 100 {
            last_gates_check = best_number;
            let gates_url = format!("{}/aether/gates", aether_url);
            if let Ok(resp) = http.get(&gates_url).send().await {
                if let Ok(gates) = resp.json::<GatesResponse>().await {
                    log::info!(
                        target: "aether-bridge",
                        "V5 Gates: {}/{} passed, phi_ceiling={:.1}",
                        gates.gates_passed, gates.gates_total, gates.phi_ceiling,
                    );
                }
            }
        }
    }
}

/// Sign and submit an extrinsic using the node's Aura keystore key.
async fn submit_extrinsic(
    client: &Arc<FullClient>,
    pool: &Arc<Pool>,
    keystore: &KeystorePtr,
    call: qbc_runtime::RuntimeCall,
) -> Result<H256, String> {
    use sp_keyring::Sr25519Keyring;

    let best_hash = client.info().best_hash;

    // Get signer from keystore (AURA key) or fallback to Alice
    let signer_pub = {
        let keys = sp_keystore::Keystore::sr25519_public_keys(
            &**keystore,
            sp_core::crypto::key_types::AURA,
        );
        if let Some(pub_key) = keys.first() {
            *pub_key
        } else {
            Sr25519Keyring::Alice.public()
        }
    };

    let account_id: qbc_runtime::AccountId = signer_pub.into();

    // Get nonce — use pool-aware nonce (accounts for pending txs in the pool).
    // The mining proof extrinsic is typically already pending at base_nonce,
    // so we need to use the next available nonce AFTER all pending txs.
    // Using validated_pool().status() to count pending txs from this account
    // would be ideal, but the simplest reliable approach is base_nonce + 5
    // to leave room for mining proofs that may be queued.
    let nonce: qbc_runtime::Nonce = {
        use frame_system_rpc_runtime_api::AccountNonceApi;
        let base_nonce = client
            .runtime_api()
            .account_nonce(best_hash, account_id.clone())
            .map_err(|e| format!("Nonce error: {:?}", e))?;
        base_nonce + 5
    };

    let genesis_hash = client
        .hash(0u32.into())
        .map_err(|e| format!("Genesis hash error: {:?}", e))?
        .ok_or("No genesis block")?;

    let spec_version = qbc_runtime::VERSION.spec_version;
    let transaction_version = qbc_runtime::VERSION.transaction_version;

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

    let additional_signed = (
        (),
        spec_version,
        transaction_version,
        genesis_hash,
        genesis_hash,
        (),
        (),
        (),
    );

    let raw_payload = (&call, &extra, &additional_signed);
    let signature = raw_payload
        .using_encoded(|payload| {
            let msg = if payload.len() > 256 {
                sp_core::hashing::blake2_256(payload).to_vec()
            } else {
                payload.to_vec()
            };
            sp_keystore::Keystore::sr25519_sign(
                &**keystore,
                sp_core::crypto::key_types::AURA,
                &signer_pub,
                &msg,
            )
        })
        .map_err(|e| format!("Sign error: {:?}", e))?
        .ok_or("Key not in keystore")?;

    let multi_sig = sp_runtime::MultiSignature::Sr25519(signature);
    let extrinsic = qbc_runtime::UncheckedExtrinsic::new_signed(
        call,
        sp_runtime::MultiAddress::Id(account_id),
        multi_sig,
        extra,
    );

    let encoded = extrinsic.encode();
    let tx_hash = H256::from_slice(&sp_core::hashing::blake2_256(&encoded));

    #[allow(deprecated)]
    let opaque = sp_runtime::OpaqueExtrinsic::from_bytes(&encoded)
        .map_err(|_| "Encode error".to_string())?;

    pool.submit_one(
        best_hash,
        sp_runtime::transaction_validity::TransactionSource::Local,
        opaque.into(),
    )
    .await
    .map_err(|e| format!("Pool submit error: {:?}", e))?;

    Ok(tx_hash)
}
