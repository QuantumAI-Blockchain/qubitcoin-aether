//! Domain types for the block indexer.
//!
//! These are the internal representations used between the Substrate decoder
//! and the database writer. They are NOT the on-chain SCALE types — those are
//! decoded via subxt's dynamic mode.

use bigdecimal::BigDecimal;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// A finalized block with all its parsed data.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexedBlock {
    pub block_hash: Vec<u8>,
    pub block_height: u64,
    pub parent_hash: Vec<u8>,
    pub state_root: Vec<u8>,
    pub extrinsics_root: Vec<u8>,
    pub timestamp: DateTime<Utc>,
    pub miner_address: Option<Vec<u8>>,
    pub difficulty: BigDecimal,
    pub energy: Option<BigDecimal>,
    pub reward: Option<BigDecimal>,
    pub era: u32,
    pub transaction_count: u32,
    pub total_fees: BigDecimal,
    pub extrinsic_count: u32,
}

/// A parsed mining event from the consensus pallet.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningEvent {
    pub block_height: u64,
    pub miner: Vec<u8>,
    pub energy: i128,
    pub difficulty: u64,
    pub reward: u128,
}

/// A difficulty adjustment event.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DifficultyEvent {
    pub old_difficulty: u64,
    pub new_difficulty: u64,
    pub block_height: u64,
}

/// A SUSY solution stored event.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SusySolutionEvent {
    pub block_height: u64,
    pub energy: i128,
    pub n_qubits: u8,
}

/// A UTXO created from a coinbase or transfer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexedUtxo {
    pub txid: Vec<u8>,
    pub vout: u32,
    pub address: Vec<u8>,
    pub amount: BigDecimal,
    pub block_height: u64,
    pub is_coinbase: bool,
}

/// A UTXO that was spent (input reference).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpentUtxo {
    pub prev_txid: Vec<u8>,
    pub prev_vout: u32,
    pub spent_in_tx: Vec<u8>,
    pub spent_at_height: u64,
    pub spent_at_timestamp: DateTime<Utc>,
}

/// A transaction parsed from a block.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexedTransaction {
    pub tx_hash: Vec<u8>,
    pub block_hash: Vec<u8>,
    pub block_height: u64,
    pub tx_index: u32,
    pub timestamp: DateTime<Utc>,
    pub tx_type: String,
    pub total_input: BigDecimal,
    pub total_output: BigDecimal,
    pub fee: BigDecimal,
    pub inputs: Vec<SpentUtxo>,
    pub outputs: Vec<IndexedUtxo>,
}

/// Chain state snapshot (singleton row in chain_state table).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChainState {
    pub best_block_hash: Vec<u8>,
    pub best_block_height: u64,
    pub total_blocks: u64,
    pub total_transactions: u64,
    pub total_addresses: u64,
    pub total_supply: BigDecimal,
    pub current_era: u32,
    pub current_difficulty: BigDecimal,
    pub average_block_time: BigDecimal,
}
