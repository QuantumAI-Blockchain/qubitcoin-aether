//! Custom RPC extensions for the Qubitcoin node.
//!
//! Provides standard Substrate RPC plus QBC-specific endpoints for:
//! - UTXO balance queries
//! - Mining statistics
//! - Aether Tree metrics (Phi, knowledge graph)
//! - QVM state

use std::sync::Arc;

use codec::Decode;
use jsonrpsee::{core::RpcResult, proc_macros::rpc, RpcModule};
use qbc_runtime::{opaque::Block, AccountId, Balance, Nonce};
use sc_client_api::{backend::Backend, StorageProvider};
use sc_transaction_pool_api::TransactionPool;
use sp_api::ProvideRuntimeApi;
use sp_block_builder::BlockBuilder;
use sp_blockchain::{Error as BlockChainError, HeaderBackend, HeaderMetadata};
use sp_core::storage::StorageKey;


// ═══════════════════════════════════════════════════════════════════════
// Storage key helpers — compute Substrate storage keys from pallet/item names
// ═══════════════════════════════════════════════════════════════════════

fn twox_128(data: &[u8]) -> [u8; 16] {
    sp_core::hashing::twox_128(data)
}

fn storage_key(pallet: &str, item: &str) -> StorageKey {
    let mut key = Vec::with_capacity(32);
    key.extend_from_slice(&twox_128(pallet.as_bytes()));
    key.extend_from_slice(&twox_128(item.as_bytes()));
    StorageKey(key)
}

fn read_storage_value<T: Decode, C, B>(
    client: &C,
    pallet: &str,
    item: &str,
) -> Option<T>
where
    C: StorageProvider<Block, B> + HeaderBackend<Block>,
    B: Backend<Block>,
{
    let best = client.info().best_hash;
    let key = storage_key(pallet, item);
    let data = client.storage(best, &key).ok()??;
    T::decode(&mut &data.0[..]).ok()
}

// ═══════════════════════════════════════════════════════════════════════
// QBC Custom RPC trait
// ═══════════════════════════════════════════════════════════════════════

#[rpc(server, client)]
pub trait QbcApi {
    /// Get UTXO-based balance for a Dilithium address (hex-encoded).
    #[method(name = "qbc_getChainStats")]
    fn get_chain_stats(&self) -> RpcResult<serde_json::Value>;

    /// Get current mining statistics.
    #[method(name = "qbc_getMiningStats")]
    fn get_mining_stats(&self) -> RpcResult<serde_json::Value>;

    /// Get current Aether Tree consciousness metrics.
    #[method(name = "qbc_getAetherStats")]
    fn get_aether_stats(&self) -> RpcResult<serde_json::Value>;

    /// Get current QVM state summary.
    #[method(name = "qbc_getQvmState")]
    fn get_qvm_state(&self) -> RpcResult<serde_json::Value>;

    /// Get current Phi consciousness value (scaled by 1000).
    #[method(name = "qbc_getPhiValue")]
    fn get_phi_value(&self) -> RpcResult<u64>;
}

// ═══════════════════════════════════════════════════════════════════════
// Implementation
// ═══════════════════════════════════════════════════════════════════════

pub struct QbcRpc<C, B> {
    client: Arc<C>,
    _marker: std::marker::PhantomData<B>,
}

impl<C, B> QbcRpc<C, B> {
    pub fn new(client: Arc<C>) -> Self {
        Self {
            client,
            _marker: std::marker::PhantomData,
        }
    }
}

impl<C, B> QbcApiServer for QbcRpc<C, B>
where
    C: StorageProvider<Block, B> + HeaderBackend<Block> + Send + Sync + 'static,
    B: Backend<Block> + 'static,
{
    fn get_chain_stats(&self) -> RpcResult<serde_json::Value> {
        let utxo_count: u64 = read_storage_value(&*self.client, "QbcUtxo", "UtxoCount")
            .unwrap_or(0);
        let tx_count: u64 = read_storage_value(&*self.client, "QbcUtxo", "TxCount")
            .unwrap_or(0);
        let current_height: u64 = read_storage_value(&*self.client, "QbcUtxo", "CurrentHeight")
            .unwrap_or(0);
        let total_emitted: u128 = read_storage_value(&*self.client, "QbcEconomics", "TotalEmitted")
            .unwrap_or(0);
        let current_era: u32 = read_storage_value(&*self.client, "QbcEconomics", "CurrentEra")
            .unwrap_or(0);

        Ok(serde_json::json!({
            "utxo_count": utxo_count,
            "tx_count": tx_count,
            "current_height": current_height,
            "total_emitted": total_emitted.to_string(),
            "current_era": current_era,
        }))
    }

    fn get_mining_stats(&self) -> RpcResult<serde_json::Value> {
        let difficulty: u64 = read_storage_value(&*self.client, "QbcConsensus", "CurrentDifficulty")
            .unwrap_or(0);
        let blocks_mined: u64 = read_storage_value(&*self.client, "QbcConsensus", "BlocksMined")
            .unwrap_or(0);

        Ok(serde_json::json!({
            "difficulty": difficulty,
            "blocks_mined": blocks_mined,
        }))
    }

    fn get_aether_stats(&self) -> RpcResult<serde_json::Value> {
        let phi: u64 = read_storage_value(&*self.client, "QbcAetherAnchor", "CurrentPhi")
            .unwrap_or(0);
        let knowledge_nodes: u64 = read_storage_value(&*self.client, "QbcAetherAnchor", "KnowledgeNodeCount")
            .unwrap_or(0);
        let knowledge_edges: u64 = read_storage_value(&*self.client, "QbcAetherAnchor", "KnowledgeEdgeCount")
            .unwrap_or(0);
        let consciousness_events: u64 = read_storage_value(&*self.client, "QbcAetherAnchor", "ConsciousnessEvents")
            .unwrap_or(0);
        let reasoning_ops: u64 = read_storage_value(&*self.client, "QbcAetherAnchor", "ReasoningOps")
            .unwrap_or(0);

        Ok(serde_json::json!({
            "phi": phi,
            "phi_float": (phi as f64) / 1000.0,
            "knowledge_nodes": knowledge_nodes,
            "knowledge_edges": knowledge_edges,
            "consciousness_events": consciousness_events,
            "reasoning_operations": reasoning_ops,
        }))
    }

    fn get_qvm_state(&self) -> RpcResult<serde_json::Value> {
        let total_contracts: u64 = read_storage_value(&*self.client, "QbcQvmAnchor", "TotalContracts")
            .unwrap_or(0);
        let total_gas: u128 = read_storage_value(&*self.client, "QbcQvmAnchor", "TotalGasConsumed")
            .unwrap_or(0);

        Ok(serde_json::json!({
            "total_contracts": total_contracts,
            "total_gas_consumed": total_gas.to_string(),
        }))
    }

    fn get_phi_value(&self) -> RpcResult<u64> {
        Ok(read_storage_value(&*self.client, "QbcAetherAnchor", "CurrentPhi")
            .unwrap_or(0))
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Full client dependencies
// ═══════════════════════════════════════════════════════════════════════

/// Full client dependencies.
pub struct FullDeps<C, P> {
    /// The client instance to use.
    pub client: Arc<C>,
    /// Transaction pool instance.
    pub pool: Arc<P>,
}

/// Instantiate all full RPC extensions.
pub fn create_full<C, P, B>(
    deps: FullDeps<C, P>,
) -> Result<RpcModule<()>, Box<dyn std::error::Error + Send + Sync>>
where
    C: ProvideRuntimeApi<Block>,
    C: HeaderBackend<Block> + HeaderMetadata<Block, Error = BlockChainError> + 'static,
    C: StorageProvider<Block, B>,
    C: Send + Sync + 'static,
    C::Api: substrate_frame_rpc_system::AccountNonceApi<Block, AccountId, Nonce>,
    C::Api: pallet_transaction_payment_rpc::TransactionPaymentRuntimeApi<Block, Balance>,
    C::Api: BlockBuilder<Block>,
    P: TransactionPool + 'static,
    B: Backend<Block> + 'static,
{
    use pallet_transaction_payment_rpc::{TransactionPayment, TransactionPaymentApiServer};
    use substrate_frame_rpc_system::{System, SystemApiServer};

    let mut module = RpcModule::new(());
    let FullDeps { client, pool } = deps;

    // Standard Substrate RPC
    module.merge(System::new(client.clone(), pool).into_rpc())?;
    module.merge(TransactionPayment::new(client.clone()).into_rpc())?;

    // QBC-specific RPC endpoints
    module.merge(QbcRpc::<C, B>::new(client).into_rpc())?;

    Ok(module)
}
