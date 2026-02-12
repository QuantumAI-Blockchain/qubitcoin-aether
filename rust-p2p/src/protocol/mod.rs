//! Protocol definitions for Qubitcoin P2P network

use serde::{Deserialize, Serialize};
use std::fmt;

/// Network message types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NetworkMessage {
    /// Request node info
    GetInfo,
    
    /// Node info response
    NodeInfo(NodeInfo),
    
    /// Request blocks by height range
    GetBlocks { start: u64, end: u64 },
    
    /// Block data
    Block(BlockData),
    
    /// New block announcement
    NewBlock { height: u64, hash: String },
    
    /// New transaction broadcast
    NewTransaction(TransactionData),
    
    /// Request mempool
    GetMempool,
    
    /// Mempool response
    Mempool(Vec<TransactionData>),
    
    /// Ping for health check
    Ping,
    
    /// Pong response
    Pong,
    
    /// Request peer list
    GetPeers,
    
    /// Peer list response
    Peers(Vec<PeerInfo>),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeInfo {
    pub version: String,
    pub height: u64,
    pub best_hash: String,
    pub difficulty: f64,
    pub peer_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockData {
    pub height: u64,
    pub hash: String,
    pub prev_hash: String,
    pub timestamp: u64,
    pub difficulty: f64,
    pub nonce: u64,
    pub miner: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionData {
    pub txid: String,
    pub size: usize,
    pub fee: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeerInfo {
    pub peer_id: String,
    pub address: String,
    pub last_seen: u64,
}

impl fmt::Display for NetworkMessage {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::GetInfo => write!(f, "GetInfo"),
            Self::NodeInfo(_) => write!(f, "NodeInfo"),
            Self::GetBlocks { start, end } => write!(f, "GetBlocks({}-{})", start, end),
            Self::Block(b) => write!(f, "Block({})", b.height),
            Self::NewBlock { height, .. } => write!(f, "NewBlock({})", height),
            Self::NewTransaction(tx) => write!(f, "NewTx({})", &tx.txid[..8.min(tx.txid.len())]),
            Self::GetMempool => write!(f, "GetMempool"),
            Self::Mempool(txs) => write!(f, "Mempool({} txs)", txs.len()),
            Self::Ping => write!(f, "Ping"),
            Self::Pong => write!(f, "Pong"),
            Self::GetPeers => write!(f, "GetPeers"),
            Self::Peers(p) => write!(f, "Peers({})", p.len()),
        }
    }
}
