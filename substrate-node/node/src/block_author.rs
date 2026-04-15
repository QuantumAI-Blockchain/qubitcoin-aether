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
//! 5. `VqeBlockAuthor` creates a block proposal via `ProposerFactory`
//!    (which pulls the proof extrinsic from the pool)
//! 6. The block is imported into the local chain

use qbc_runtime::opaque::Block;
use sc_consensus::{BlockImport, BlockImportParams, ForkChoiceStrategy};
use sp_blockchain::HeaderBackend;
use sp_inherents::InherentDataProvider;
use sp_runtime::traits::Block as BlockT;
use std::sync::Arc;

use crate::service::{FullBackend, FullClient};

type FullGrandpaBlockImport = sc_consensus_grandpa::GrandpaBlockImport<
    FullBackend,
    Block,
    FullClient,
    sc_consensus::LongestChain<FullBackend, Block>,
>;

type Pool = sc_transaction_pool::TransactionPoolHandle<Block, FullClient>;

type FullProposerFactory = sc_basic_authorship::ProposerFactory<
    sc_service::SpawnTaskHandle,
    FullClient,
    Pool,
>;

/// Run the VQE-gated block authoring loop.
///
/// This replaces Aura's block production when `--mine` is enabled.
/// Blocks are only produced when the mining engine finds a VQE solution.
pub async fn run_vqe_block_author(
    client: Arc<FullClient>,
    mut proposer_factory: FullProposerFactory,
    mut block_import: FullGrandpaBlockImport,
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

        // Small delay to ensure the proof extrinsic has propagated in the pool
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;

        // Build inherent data (timestamp + Aura slot)
        let inherent_data = match build_inherent_data(&*client).await {
            Ok(data) => data,
            Err(e) => {
                log::error!(
                    target: "block-author",
                    "Failed to build inherent data: {:?}",
                    e
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
                    "Failed to get parent header for {:?}",
                    best_hash
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
                    "Failed to create proposer: {:?}",
                    e
                );
                continue;
            }
        };

        // Propose a block (10 second deadline)
        let proposal = match proposer
            .propose(
                inherent_data,
                Default::default(), // digest
                std::time::Duration::from_secs(10),
                None, // max block size
            )
            .await
        {
            Ok(proposal) => proposal,
            Err(e) => {
                log::error!(
                    target: "block-author",
                    "Block proposal failed: {:?}",
                    e
                );
                continue;
            }
        };

        let block: Block = proposal.block;
        let (header, body) = block.deconstruct();
        let block_number = header.number;
        let post_hash = header.hash();

        log::info!(
            target: "block-author",
            "Proposed block #{} ({:?}) with {} extrinsics",
            block_number,
            post_hash,
            body.len()
        );

        // Import the block
        let mut import_params = BlockImportParams::new(
            sc_consensus::BlockOrigin::Own,
            header,
        );
        import_params.body = Some(body);
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
