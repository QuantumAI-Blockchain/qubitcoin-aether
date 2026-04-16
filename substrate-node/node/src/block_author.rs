//! VQE-gated block authoring.
//!
//! Replaces Aura's unconditional slot-based block production with
//! proof-driven authoring: a block is proposed ONLY after the mining
//! engine has found a VQE solution and submitted it to the transaction pool.
//!
//! ## Flow
//!
//! 1. Mining engine finds a VQE solution with energy < difficulty
//! 2. Mining engine submits the proof extrinsic to the tx pool
//! 3. Mining engine sends `MiningProofReady` via mpsc channel
//! 4. `VqeBlockAuthor` receives the notification
//! 5. `VqeBlockAuthor` waits for the next valid Aura slot
//! 6. `VqeBlockAuthor` creates a block proposal with proper Aura digest
//! 7. The block is sealed with the authority's signature and imported

use qbc_runtime::opaque::Block;
use sc_consensus::{BlockImport, BlockImportParams, ForkChoiceStrategy};
use sc_consensus_aura::standalone::{pre_digest, seal};
use sp_api::ProvideRuntimeApi;
use sp_blockchain::HeaderBackend;
use sp_consensus::{Environment, Proposer};
use sp_consensus_aura::sr25519::AuthorityPair as AuraPair;
use sp_consensus_aura::{AuraApi, AURA_ENGINE_ID};
use sp_inherents::InherentDataProvider;
use sp_keystore::KeystorePtr;
use sp_runtime::{
    traits::{Block as BlockT, Header as HeaderT},
    Digest, DigestItem,
};
use std::sync::Arc;

use crate::service::{FullBackend, FullClient};

type FullGrandpaBlockImport = sc_consensus_grandpa::GrandpaBlockImport<
    FullBackend,
    Block,
    FullClient,
    crate::weighted_chain::WeightedChain<FullBackend, FullClient>,
>;

type Pool = sc_transaction_pool::TransactionPoolHandle<Block, FullClient>;

type FullProposerFactory = sc_basic_authorship::ProposerFactory<
    Pool,
    FullClient,
    sp_consensus::DisableProofRecording,
>;

/// Run the VQE-gated block authoring loop.
///
/// This replaces Aura's block production when `--mine` is enabled.
/// Blocks are only produced when the mining engine finds a VQE solution,
/// but we still respect Aura's slot timing and produce valid Aura digests.
pub async fn run_vqe_block_author(
    client: Arc<FullClient>,
    mut proposer_factory: FullProposerFactory,
    mut block_import: FullGrandpaBlockImport,
    keystore: KeystorePtr,
    proof_rx: std::sync::mpsc::Receiver<qbc_mining::MiningProofReady>,
) {
    loop {
        // Wait for mining proof notification.
        let proof_ready = {
            let recv_result = tokio::task::block_in_place(|| proof_rx.recv());
            match recv_result {
                Ok(proof) => proof,
                Err(_) => {
                    log::warn!(
                        target: "block-author",
                        "Mining proof channel closed, stopping block author"
                    );
                    return;
                }
            }
        };

        log::info!(
            target: "block-author",
            "Mining proof received for height {}, proposing block...",
            proof_ready.block_height
        );

        // Get slot duration
        let slot_duration_ms = match sc_consensus_aura::slot_duration(&*client) {
            Ok(d) => d.as_millis() as u64,
            Err(e) => {
                log::error!(
                    target: "block-author",
                    "Failed to get slot duration: {:?}", e
                );
                continue;
            }
        };

        // Get the best block as parent
        let best_hash = client.info().best_hash;
        let parent_header = match client.header(best_hash) {
            Ok(Some(h)) => h,
            _ => {
                log::error!(
                    target: "block-author",
                    "Failed to get parent header for {:?}", best_hash
                );
                continue;
            }
        };

        // Extract the parent block's Aura slot from its digest
        let parent_slot = extract_aura_slot(&parent_header);
        let next_slot = parent_slot + 1;
        let next_slot_start_ms = next_slot * slot_duration_ms;

        // Wait until system time reaches the next valid slot
        let now_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("system time after epoch")
            .as_millis() as u64;

        if now_ms < next_slot_start_ms {
            let wait_ms = next_slot_start_ms - now_ms;
            log::info!(
                target: "block-author",
                "VQE proof ready, waiting {}ms for Aura slot {} (parent was slot {})...",
                wait_ms, next_slot, parent_slot
            );
            tokio::time::sleep(std::time::Duration::from_millis(wait_ms)).await;
        } else {
            // Already past the next slot boundary — small delay for tx pool propagation
            tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        }

        // Compute the actual slot from current system time
        let proposal_time_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("system time after epoch")
            .as_millis() as u64;
        let current_slot = sp_consensus_aura::Slot::from(proposal_time_ms / slot_duration_ms);

        // Claim the slot — verify we have the authority key for this slot
        let authorities: Vec<sp_consensus_aura::sr25519::AuthorityId> =
            match client.runtime_api().authorities(best_hash) {
                Ok(a) => a,
                Err(e) => {
                    log::error!(
                        target: "block-author",
                        "Failed to get Aura authorities: {:?}", e
                    );
                    continue;
                }
            };

        let authority_public = match sc_consensus_aura::standalone::claim_slot::<AuraPair>(
            current_slot,
            &authorities,
            &keystore,
        )
        .await
        {
            Some(public) => public,
            None => {
                // We don't own this slot — wait for the next one we do own
                log::debug!(
                    target: "block-author",
                    "Slot {} not owned by our authority, skipping", *current_slot
                );
                // Try the next slot
                let next_own_slot_ms = (*current_slot + 1) * slot_duration_ms;
                let now2 = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .expect("time")
                    .as_millis() as u64;
                if next_own_slot_ms > now2 {
                    tokio::time::sleep(std::time::Duration::from_millis(
                        next_own_slot_ms - now2,
                    ))
                    .await;
                }
                continue;
            }
        };

        // Create the Aura pre-digest for this slot
        let aura_pre_digest = pre_digest::<AuraPair>(current_slot);
        let digest = Digest {
            logs: vec![aura_pre_digest],
        };

        // Build inherent data (timestamp + Aura slot)
        let inherent_data = match build_inherent_data(&*client).await {
            Ok(data) => data,
            Err(e) => {
                log::error!(
                    target: "block-author",
                    "Failed to build inherent data: {:?}", e
                );
                continue;
            }
        };

        // Create a proposer for this parent
        let proposer = match proposer_factory.init(&parent_header).await {
            Ok(p) => p,
            Err(e) => {
                log::error!(
                    target: "block-author",
                    "Failed to create proposer: {:?}", e
                );
                continue;
            }
        };

        // Propose a block with the Aura pre-digest (10 second deadline)
        let proposal = match proposer
            .propose(
                inherent_data,
                digest,
                std::time::Duration::from_secs(10),
                None,
            )
            .await
        {
            Ok(proposal) => proposal,
            Err(e) => {
                log::error!(
                    target: "block-author",
                    "Block proposal failed: {:?}", e
                );
                continue;
            }
        };

        let block: Block = proposal.block;
        let (header, body) = block.deconstruct();
        let block_number = *header.number();

        // Seal the block — sign the header hash with our Aura authority key.
        // The seal is a post-digest: it must NOT be part of the header during
        // block execution (state root is computed without it), but IS included
        // in the final block hash for verification.
        let header_hash = header.hash();
        let seal_digest = match seal::<_, AuraPair>(
            &header_hash,
            &authority_public,
            &keystore,
        ) {
            Ok(s) => s,
            Err(e) => {
                log::error!(
                    target: "block-author",
                    "Failed to seal block #{}: {:?}", block_number, e
                );
                continue;
            }
        };

        log::info!(
            target: "block-author",
            "Proposed block #{} ({:?}) with {} extrinsics (slot {})",
            block_number,
            header_hash,
            body.len(),
            *current_slot
        );

        // Import the block with the seal as a post-digest
        let mut import_params =
            BlockImportParams::new(sp_consensus::BlockOrigin::Own, header);
        import_params.body = Some(body);
        import_params.post_digests.push(seal_digest);
        import_params.fork_choice = Some(ForkChoiceStrategy::LongestChain);

        match block_import.import_block(import_params).await {
            Ok(result) => {
                log::info!(
                    target: "block-author",
                    "Block #{} imported: {:?}",
                    block_number, result
                );
            }
            Err(e) => {
                log::error!(
                    target: "block-author",
                    "Block #{} import failed: {:?}",
                    block_number, e
                );
            }
        }
    }
}

/// Build inherent data providers (timestamp + Aura slot).
async fn build_inherent_data(
    client: &FullClient,
) -> Result<sp_inherents::InherentData, Box<dyn std::error::Error + Send + Sync>> {
    let timestamp = sp_timestamp::InherentDataProvider::from_system_time();

    let slot_duration = sc_consensus_aura::slot_duration(client)?;
    let slot =
        sp_consensus_aura::inherents::InherentDataProvider::from_timestamp_and_slot_duration(
            *timestamp,
            slot_duration,
        );

    let mut inherent_data = sp_inherents::InherentData::new();
    timestamp.provide_inherent_data(&mut inherent_data).await?;
    slot.provide_inherent_data(&mut inherent_data).await?;

    Ok(inherent_data)
}

/// Extract the Aura slot number from a block header's digest.
///
/// Returns 0 for genesis (no Aura digest) so that the first mined block
/// targets slot 1.
fn extract_aura_slot(header: &<Block as BlockT>::Header) -> u64 {
    for log in header.digest.logs() {
        if let DigestItem::PreRuntime(engine_id, data) = log {
            if *engine_id == AURA_ENGINE_ID {
                if data.len() >= 8 {
                    return u64::from_le_bytes(data[..8].try_into().unwrap_or([0; 8]));
                }
            }
        }
    }
    0
}
