//! gRPC bridge between Python node and Rust P2P network.
//!
//! Implements all RPCs defined in proto/p2p_service.proto:
//! - Outbound: BroadcastBlock, BroadcastTransaction, SubmitBlock
//! - Inbound:  StreamBlocks, StreamTransactions, StreamEvents
//! - Queries:  GetPeerStats, GetPeerList, HealthCheck

use tonic::{transport::Server, Request, Response, Status};
use tokio::sync::{mpsc, broadcast};
use tokio_stream::wrappers::BroadcastStream;
use tokio_stream::StreamExt;
use tracing::info;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::protocol::NetworkMessage;

pub mod p2p_service {
    tonic::include_proto!("p2p_service");
}

use p2p_service::{
    p2p_server::{P2p, P2pServer},
    BroadcastBlockRequest, BroadcastTransactionRequest, BroadcastResponse,
    BlockData, TransactionData, NetworkEvent, StreamRequest,
    PeerStatsRequest, PeerStatsResponse,
    PeerListRequest, PeerListResponse,
    HealthRequest, HealthResponse,
};

/// Shared counters for network statistics.
pub struct P2PStats {
    pub peer_count: AtomicUsize,
    pub blocks_received: AtomicU64,
    pub blocks_sent: AtomicU64,
    pub txs_received: AtomicU64,
    pub txs_sent: AtomicU64,
    pub start_time: u64,
}

impl P2PStats {
    pub fn new() -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        Self {
            peer_count: AtomicUsize::new(0),
            blocks_received: AtomicU64::new(0),
            blocks_sent: AtomicU64::new(0),
            txs_received: AtomicU64::new(0),
            txs_sent: AtomicU64::new(0),
            start_time: now,
        }
    }

    pub fn uptime_seconds(&self) -> u64 {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        now.saturating_sub(self.start_time)
    }
}

/// gRPC service implementation.
pub struct P2PService {
    /// Send commands to the P2P network (outbound).
    to_network_tx: mpsc::UnboundedSender<NetworkMessage>,
    /// Broadcast channel for streaming events to Python clients.
    event_tx: broadcast::Sender<NetworkEvent>,
    /// Shared network statistics.
    stats: Arc<P2PStats>,
}

impl P2PService {
    pub fn new(
        to_network_tx: mpsc::UnboundedSender<NetworkMessage>,
        event_tx: broadcast::Sender<NetworkEvent>,
        stats: Arc<P2PStats>,
    ) -> Self {
        Self { to_network_tx, event_tx, stats }
    }
}

#[tonic::async_trait]
impl P2p for P2PService {
    // ── Outbound RPCs ───────────────────────────────────────────────

    async fn broadcast_block(
        &self,
        request: Request<BroadcastBlockRequest>,
    ) -> Result<Response<BroadcastResponse>, Status> {
        let req = request.into_inner();
        info!("gRPC: Broadcasting block height={}", req.height);

        let msg = NetworkMessage::NewBlock {
            height: req.height,
            hash: req.hash.clone(),
        };

        self.to_network_tx
            .send(msg)
            .map_err(|e| Status::internal(format!("Channel send error: {}", e)))?;

        self.stats.blocks_sent.fetch_add(1, Ordering::Relaxed);

        // Echo to event stream so other gRPC subscribers (e.g. Substrate bridge) see it
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let _ = self.event_tx.send(NetworkEvent {
            event_type: 0, // BLOCK_RECEIVED
            timestamp: now,
            block: Some(p2p_service::BlockData {
                height: req.height,
                hash: req.hash,
                prev_hash: String::new(),
                timestamp: now,
                difficulty: 0.0,
                nonce: 0,
                miner: String::new(),
            }),
            transaction: None,
            peer: None,
        });

        Ok(Response::new(BroadcastResponse {
            success: true,
            message: String::new(),
        }))
    }

    async fn broadcast_transaction(
        &self,
        request: Request<BroadcastTransactionRequest>,
    ) -> Result<Response<BroadcastResponse>, Status> {
        let req = request.into_inner();
        info!("gRPC: Broadcasting tx {}", &req.txid[..8.min(req.txid.len())]);

        let msg = NetworkMessage::NewTransaction(crate::protocol::TransactionData {
            txid: req.txid.clone(),
            size: req.size as usize,
            fee: req.fee.clone(),
        });

        self.to_network_tx
            .send(msg)
            .map_err(|e| Status::internal(format!("Channel send error: {}", e)))?;

        self.stats.txs_sent.fetch_add(1, Ordering::Relaxed);

        // Echo to event stream so other gRPC subscribers see it
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let _ = self.event_tx.send(NetworkEvent {
            event_type: 1, // TRANSACTION_RECEIVED
            timestamp: now,
            block: None,
            transaction: Some(p2p_service::TransactionData {
                txid: req.txid,
                size: req.size,
                fee: req.fee,
            }),
            peer: None,
        });

        Ok(Response::new(BroadcastResponse {
            success: true,
            message: String::new(),
        }))
    }

    async fn submit_block(
        &self,
        request: Request<BlockData>,
    ) -> Result<Response<BroadcastResponse>, Status> {
        let block = request.into_inner();
        info!("gRPC: Submitting full block height={}", block.height);

        let msg = NetworkMessage::Block(crate::protocol::BlockData {
            height: block.height,
            hash: block.hash.clone(),
            prev_hash: block.prev_hash.clone(),
            timestamp: block.timestamp,
            difficulty: block.difficulty,
            nonce: block.nonce,
            miner: block.miner.clone(),
        });

        self.to_network_tx
            .send(msg)
            .map_err(|e| Status::internal(format!("Channel send error: {}", e)))?;

        self.stats.blocks_sent.fetch_add(1, Ordering::Relaxed);

        // Echo to event stream so other gRPC subscribers (e.g. Substrate bridge) see it
        let _ = self.event_tx.send(NetworkEvent {
            event_type: 0, // BLOCK_RECEIVED
            timestamp: block.timestamp,
            block: Some(p2p_service::BlockData {
                height: block.height,
                hash: block.hash,
                prev_hash: block.prev_hash,
                timestamp: block.timestamp,
                difficulty: block.difficulty,
                nonce: block.nonce,
                miner: block.miner,
            }),
            transaction: None,
            peer: None,
        });

        Ok(Response::new(BroadcastResponse {
            success: true,
            message: String::new(),
        }))
    }

    // ── Inbound Streaming RPCs ──────────────────────────────────────

    type StreamBlocksStream = std::pin::Pin<
        Box<dyn futures::Stream<Item = Result<BlockData, Status>> + Send>
    >;

    async fn stream_blocks(
        &self,
        _request: Request<StreamRequest>,
    ) -> Result<Response<Self::StreamBlocksStream>, Status> {
        info!("gRPC: Python subscribed to block stream");
        let rx = self.event_tx.subscribe();

        let stream = BroadcastStream::new(rx)
            .filter_map(|result| {
                match result {
                    Ok(event) if event.event_type == 0 => {
                        // BLOCK_RECEIVED
                        event.block.map(|b| Ok(b))
                    }
                    _ => None,
                }
            });

        Ok(Response::new(Box::pin(stream)))
    }

    type StreamTransactionsStream = std::pin::Pin<
        Box<dyn futures::Stream<Item = Result<TransactionData, Status>> + Send>
    >;

    async fn stream_transactions(
        &self,
        _request: Request<StreamRequest>,
    ) -> Result<Response<Self::StreamTransactionsStream>, Status> {
        info!("gRPC: Python subscribed to transaction stream");
        let rx = self.event_tx.subscribe();

        let stream = BroadcastStream::new(rx)
            .filter_map(|result| {
                match result {
                    Ok(event) if event.event_type == 1 => {
                        // TRANSACTION_RECEIVED
                        event.transaction.map(|tx| Ok(tx))
                    }
                    _ => None,
                }
            });

        Ok(Response::new(Box::pin(stream)))
    }

    type StreamEventsStream = std::pin::Pin<
        Box<dyn futures::Stream<Item = Result<NetworkEvent, Status>> + Send>
    >;

    async fn stream_events(
        &self,
        _request: Request<StreamRequest>,
    ) -> Result<Response<Self::StreamEventsStream>, Status> {
        info!("gRPC: Python subscribed to all events stream");
        let rx = self.event_tx.subscribe();

        let stream = BroadcastStream::new(rx)
            .filter_map(|result: Result<NetworkEvent, _>| result.ok().map(Ok));

        Ok(Response::new(Box::pin(stream)))
    }

    // ── Query RPCs ──────────────────────────────────────────────────

    async fn get_peer_stats(
        &self,
        _request: Request<PeerStatsRequest>,
    ) -> Result<Response<PeerStatsResponse>, Status> {
        Ok(Response::new(PeerStatsResponse {
            peer_count: self.stats.peer_count.load(Ordering::Relaxed) as u32,
            gossipsub_peers: self.stats.peer_count.load(Ordering::Relaxed) as u32,
            blocks_received: self.stats.blocks_received.load(Ordering::Relaxed),
            blocks_sent: self.stats.blocks_sent.load(Ordering::Relaxed),
            txs_received: self.stats.txs_received.load(Ordering::Relaxed),
            txs_sent: self.stats.txs_sent.load(Ordering::Relaxed),
            uptime_seconds: self.stats.uptime_seconds(),
        }))
    }

    async fn get_peer_list(
        &self,
        _request: Request<PeerListRequest>,
    ) -> Result<Response<PeerListResponse>, Status> {
        // Peer list will be populated by the P2P network task via shared state.
        // For now return empty — RP2 will wire the shared peer HashMap.
        Ok(Response::new(PeerListResponse { peers: vec![] }))
    }

    async fn health_check(
        &self,
        _request: Request<HealthRequest>,
    ) -> Result<Response<HealthResponse>, Status> {
        Ok(Response::new(HealthResponse {
            healthy: true,
            version: "1.0.0".to_string(),
            peer_count: self.stats.peer_count.load(Ordering::Relaxed) as u32,
            uptime_seconds: self.stats.uptime_seconds(),
        }))
    }
}

/// Start the gRPC server.
pub async fn start_grpc_server(
    addr: &str,
    to_network_tx: mpsc::UnboundedSender<NetworkMessage>,
    event_tx: broadcast::Sender<NetworkEvent>,
    stats: Arc<P2PStats>,
) -> anyhow::Result<()> {
    let service = P2PService::new(to_network_tx, event_tx, stats);
    let addr = addr.parse()?;

    info!("gRPC server listening on {}", addr);

    Server::builder()
        .add_service(P2pServer::new(service))
        .serve(addr)
        .await?;

    Ok(())
}
