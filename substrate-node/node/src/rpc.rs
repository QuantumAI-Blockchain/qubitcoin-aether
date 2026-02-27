//! Custom RPC extensions for the Qubitcoin node.
//!
//! Provides standard Substrate RPC plus QBC-specific endpoints for:
//! - UTXO balance queries
//! - Mining statistics
//! - Aether Tree metrics (Phi, knowledge graph)
//! - QVM state

use std::sync::Arc;

use jsonrpsee::RpcModule;
use qbc_runtime::{opaque::Block, AccountId, Balance, Nonce};
use sc_transaction_pool_api::TransactionPool;
use sp_api::ProvideRuntimeApi;
use sp_block_builder::BlockBuilder;
use sp_blockchain::{Error as BlockChainError, HeaderBackend, HeaderMetadata};

/// Full client dependencies.
pub struct FullDeps<C, P> {
    /// The client instance to use.
    pub client: Arc<C>,
    /// Transaction pool instance.
    pub pool: Arc<P>,
}

/// Instantiate all full RPC extensions.
pub fn create_full<C, P>(
    deps: FullDeps<C, P>,
) -> Result<RpcModule<()>, Box<dyn std::error::Error + Send + Sync>>
where
    C: ProvideRuntimeApi<Block>,
    C: HeaderBackend<Block> + HeaderMetadata<Block, Error = BlockChainError> + 'static,
    C: Send + Sync + 'static,
    C::Api: substrate_frame_rpc_system::AccountNonceApi<Block, AccountId, Nonce>,
    C::Api: pallet_transaction_payment_rpc::TransactionPaymentRuntimeApi<Block, Balance>,
    C::Api: BlockBuilder<Block>,
    P: TransactionPool + 'static,
{
    use pallet_transaction_payment_rpc::{TransactionPayment, TransactionPaymentApiServer};
    use substrate_frame_rpc_system::{System, SystemApiServer};

    let mut module = RpcModule::new(());
    let FullDeps { client, pool } = deps;

    // Standard Substrate RPC
    module.merge(System::new(client.clone(), pool).into_rpc())?;
    module.merge(TransactionPayment::new(client).into_rpc())?;

    // QBC-specific RPC endpoints will be wired here as runtime APIs are added:
    // - qbc_getUtxoBalance: Query UTXO-based balance for a Dilithium address
    // - qbc_listUtxos: List all UTXOs for an address
    // - qbc_getMiningStats: Current difficulty, blocks mined, last miner
    // - qbc_getPhiValue: Current Phi consciousness metric from Aether anchor
    // - qbc_getKnowledgeStats: Knowledge graph node/edge counts
    // - qbc_getQvmState: QVM state root and contract count
    //
    // These require corresponding runtime APIs to be defined in the runtime crate.
    // For now, the pallet storage is accessible via the standard state_getStorage RPC.

    Ok(module)
}
