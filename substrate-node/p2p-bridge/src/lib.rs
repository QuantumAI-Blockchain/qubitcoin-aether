//! Qubitcoin Substrate ↔ Rust P2P Bridge
//!
//! Connects the Substrate node to the existing Qubitcoin Rust P2P daemon via gRPC.
//! The P2P daemon handles gossipsub networking (block/tx propagation, peer discovery).
//! This bridge:
//!
//! 1. **Inbound**: Streams blocks/txs from the P2P daemon and feeds them into
//!    the Substrate import pipeline.
//! 2. **Outbound**: Broadcasts locally-authored blocks/txs to the P2P network
//!    via the daemon's gRPC API.
//! 3. **Monitoring**: Periodically fetches peer stats for telemetry.

use std::sync::Arc;
use std::time::Duration;

use futures::StreamExt;
use sc_client_api::HeaderBackend;
use tokio::sync::mpsc;

mod proto {
    tonic::include_proto!("p2p_service");
}

pub use proto::*;

// ═══════════════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════════════

/// Configuration for the P2P bridge.
#[derive(Debug, Clone)]
pub struct P2pBridgeConfig {
    /// gRPC address of the Rust P2P daemon (e.g., "http://127.0.0.1:50051")
    pub grpc_addr: String,
    /// Reconnection interval on connection failure
    pub reconnect_interval: Duration,
    /// Interval for peer stats polling
    pub stats_interval: Duration,
    /// Whether to relay blocks from P2P to Substrate import queue
    pub relay_blocks: bool,
    /// Whether to relay transactions from P2P to Substrate tx pool
    pub relay_transactions: bool,
}

impl Default for P2pBridgeConfig {
    fn default() -> Self {
        Self {
            grpc_addr: "http://127.0.0.1:50051".to_string(),
            reconnect_interval: Duration::from_secs(5),
            stats_interval: Duration::from_secs(30),
            relay_blocks: true,
            relay_transactions: true,
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Block Announcement (inbound from P2P)
// ═══════════════════════════════════════════════════════════════════════

/// Block data received from the P2P network, ready for Substrate processing.
#[derive(Debug, Clone)]
pub struct InboundBlock {
    pub height: u64,
    pub hash: String,
    pub prev_hash: String,
    pub timestamp: u64,
    pub difficulty: f64,
    pub nonce: u64,
    pub miner: String,
}

impl From<BlockData> for InboundBlock {
    fn from(bd: BlockData) -> Self {
        Self {
            height: bd.height,
            hash: bd.hash,
            prev_hash: bd.prev_hash,
            timestamp: bd.timestamp,
            difficulty: bd.difficulty,
            nonce: bd.nonce,
            miner: bd.miner,
        }
    }
}

/// Transaction data received from the P2P network.
#[derive(Debug, Clone)]
pub struct InboundTransaction {
    pub txid: String,
    pub size: u32,
    pub fee: String,
}

impl From<TransactionData> for InboundTransaction {
    fn from(td: TransactionData) -> Self {
        Self {
            txid: td.txid,
            size: td.size,
            fee: td.fee,
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// P2P Bridge Service
// ═══════════════════════════════════════════════════════════════════════

/// The main P2P bridge that connects Substrate to the Rust P2P daemon.
pub struct P2pBridge {
    config: P2pBridgeConfig,
    /// Channel sender for inbound blocks (consumed by Substrate import task)
    block_tx: mpsc::UnboundedSender<InboundBlock>,
    /// Channel sender for inbound transactions
    tx_tx: mpsc::UnboundedSender<InboundTransaction>,
}

impl P2pBridge {
    /// Create a new P2P bridge.
    ///
    /// Returns the bridge and receivers for blocks and transactions.
    pub fn new(
        config: P2pBridgeConfig,
    ) -> (
        Self,
        mpsc::UnboundedReceiver<InboundBlock>,
        mpsc::UnboundedReceiver<InboundTransaction>,
    ) {
        let (block_tx, block_rx) = mpsc::unbounded_channel();
        let (tx_tx, tx_rx) = mpsc::unbounded_channel();

        let bridge = Self {
            config,
            block_tx,
            tx_tx,
        };

        (bridge, block_rx, tx_rx)
    }

    /// Run the bridge. This is the main loop that:
    /// 1. Connects to the P2P daemon via gRPC
    /// 2. Streams blocks and transactions
    /// 3. Sends them to the Substrate import pipeline via channels
    ///
    /// Automatically reconnects on failure.
    pub async fn run(self) {
        log::info!(
            target: "p2p-bridge",
            "Starting P2P bridge to {}",
            self.config.grpc_addr
        );

        loop {
            match self.run_connected().await {
                Ok(()) => {
                    log::info!(
                        target: "p2p-bridge",
                        "P2P bridge stream ended, reconnecting in {:?}",
                        self.config.reconnect_interval
                    );
                }
                Err(e) => {
                    log::warn!(
                        target: "p2p-bridge",
                        "P2P bridge connection failed: {}, retrying in {:?}",
                        e, self.config.reconnect_interval
                    );
                }
            }

            tokio::time::sleep(self.config.reconnect_interval).await;
        }
    }

    /// Single connection attempt — streams events until disconnect.
    async fn run_connected(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let mut client = p2p_client::P2pClient::connect(self.config.grpc_addr.clone()).await?;

        log::info!(
            target: "p2p-bridge",
            "Connected to P2P daemon at {}",
            self.config.grpc_addr
        );

        // Health check
        let health = client
            .health_check(HealthRequest {})
            .await?
            .into_inner();

        log::info!(
            target: "p2p-bridge",
            "P2P daemon healthy: version={}, peers={}, uptime={}s",
            health.version, health.peer_count, health.uptime_seconds
        );

        // Start streaming events (blocks + txs + peer changes in one stream)
        let mut event_stream = client
            .stream_events(StreamRequest {})
            .await?
            .into_inner();

        // Also spawn a stats poller
        let stats_addr = self.config.grpc_addr.clone();
        let stats_interval = self.config.stats_interval;
        tokio::spawn(async move {
            poll_peer_stats(stats_addr, stats_interval).await;
        });

        // Process events
        while let Some(event) = event_stream.next().await {
            match event {
                Ok(network_event) => {
                    self.handle_event(network_event);
                }
                Err(status) => {
                    log::warn!(
                        target: "p2p-bridge",
                        "P2P event stream error: {}",
                        status
                    );
                    return Err(Box::new(status));
                }
            }
        }

        Ok(())
    }

    /// Handle a single network event from the P2P daemon.
    fn handle_event(&self, event: NetworkEvent) {
        let event_type = event.event_type();

        match event_type {
            network_event::EventType::BlockReceived => {
                if let Some(block_data) = event.block {
                    if self.config.relay_blocks {
                        log::debug!(
                            target: "p2p-bridge",
                            "Received block #{} hash={} from P2P",
                            block_data.height, block_data.hash
                        );
                        let inbound = InboundBlock::from(block_data);
                        if self.block_tx.send(inbound).is_err() {
                            log::warn!(
                                target: "p2p-bridge",
                                "Block channel closed, stopping bridge"
                            );
                        }
                    }
                }
            }
            network_event::EventType::TransactionReceived => {
                if let Some(tx_data) = event.transaction {
                    if self.config.relay_transactions {
                        log::debug!(
                            target: "p2p-bridge",
                            "Received tx {} from P2P",
                            tx_data.txid
                        );
                        let inbound = InboundTransaction::from(tx_data);
                        if self.tx_tx.send(inbound).is_err() {
                            log::warn!(
                                target: "p2p-bridge",
                                "Transaction channel closed, stopping bridge"
                            );
                        }
                    }
                }
            }
            network_event::EventType::PeerConnected => {
                if let Some(peer) = &event.peer {
                    log::info!(
                        target: "p2p-bridge",
                        "P2P peer connected: {} ({})",
                        peer.peer_id, peer.address
                    );
                }
            }
            network_event::EventType::PeerDisconnected => {
                if let Some(peer) = &event.peer {
                    log::info!(
                        target: "p2p-bridge",
                        "P2P peer disconnected: {}",
                        peer.peer_id
                    );
                }
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Outbound — Broadcast blocks/txs TO the P2P network
// ═══════════════════════════════════════════════════════════════════════

/// Client handle for broadcasting blocks and transactions to the P2P network.
/// Used by the Substrate block authoring pipeline to announce new blocks.
#[derive(Clone)]
pub struct P2pBroadcaster {
    grpc_addr: String,
}

impl P2pBroadcaster {
    pub fn new(grpc_addr: String) -> Self {
        Self { grpc_addr }
    }

    /// Broadcast a newly authored block to the P2P network.
    pub async fn broadcast_block(
        &self,
        height: u64,
        hash: String,
        prev_hash: String,
        timestamp: u64,
        difficulty: f64,
        nonce: u64,
        miner: String,
    ) -> Result<bool, tonic::Status> {
        let mut client = p2p_client::P2pClient::connect(self.grpc_addr.clone())
            .await
            .map_err(|e| tonic::Status::unavailable(format!("P2P daemon unreachable: {}", e)))?;

        let block = BlockData {
            height,
            hash: hash.clone(),
            prev_hash,
            timestamp,
            difficulty,
            nonce,
            miner,
        };

        let resp = client.submit_block(block).await?.into_inner();

        if resp.success {
            log::info!(
                target: "p2p-bridge",
                "Broadcast block #{} hash={} to P2P network",
                height, hash
            );
        } else {
            log::warn!(
                target: "p2p-bridge",
                "Failed to broadcast block #{}: {}",
                height, resp.message
            );
        }

        Ok(resp.success)
    }

    /// Broadcast a transaction to the P2P network.
    pub async fn broadcast_transaction(
        &self,
        txid: String,
        size: u32,
        fee: String,
    ) -> Result<bool, tonic::Status> {
        let mut client = p2p_client::P2pClient::connect(self.grpc_addr.clone())
            .await
            .map_err(|e| tonic::Status::unavailable(format!("P2P daemon unreachable: {}", e)))?;

        let resp = client
            .broadcast_transaction(BroadcastTransactionRequest {
                txid: txid.clone(),
                size,
                fee,
            })
            .await?
            .into_inner();

        if resp.success {
            log::debug!(
                target: "p2p-bridge",
                "Broadcast tx {} to P2P network",
                txid
            );
        }

        Ok(resp.success)
    }

    /// Get current P2P network statistics.
    pub async fn get_peer_stats(&self) -> Result<PeerStatsResponse, tonic::Status> {
        let mut client = p2p_client::P2pClient::connect(self.grpc_addr.clone())
            .await
            .map_err(|e| tonic::Status::unavailable(format!("P2P daemon unreachable: {}", e)))?;

        let resp = client.get_peer_stats(PeerStatsRequest {}).await?.into_inner();
        Ok(resp)
    }

    /// Get detailed peer list.
    pub async fn get_peer_list(&self) -> Result<Vec<PeerInfo>, tonic::Status> {
        let mut client = p2p_client::P2pClient::connect(self.grpc_addr.clone())
            .await
            .map_err(|e| tonic::Status::unavailable(format!("P2P daemon unreachable: {}", e)))?;

        let resp = client.get_peer_list(PeerListRequest {}).await?.into_inner();
        Ok(resp.peers)
    }

    /// Health check the P2P daemon.
    pub async fn health_check(&self) -> Result<HealthResponse, tonic::Status> {
        let mut client = p2p_client::P2pClient::connect(self.grpc_addr.clone())
            .await
            .map_err(|e| tonic::Status::unavailable(format!("P2P daemon unreachable: {}", e)))?;

        let resp = client.health_check(HealthRequest {}).await?.into_inner();
        Ok(resp)
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Inbound — Process blocks from P2P into Substrate
// ═══════════════════════════════════════════════════════════════════════

/// Processes inbound blocks from the P2P channel and logs them.
///
/// In the Substrate model, blocks received from the custom P2P gossip are
/// announcements — the actual block import happens through sc-network's
/// standard block sync protocol. This task monitors the P2P daemon's gossip
/// stream and can trigger chain sync when the local chain falls behind.
///
/// For blocks that arrive via the custom P2P but not via Substrate's native
/// networking, this task can request them through a REST API (chain sync).
pub async fn process_inbound_blocks<C>(
    client: Arc<C>,
    mut block_rx: mpsc::UnboundedReceiver<InboundBlock>,
    sync_peer_url: Option<String>,
) where
    C: HeaderBackend<qbc_runtime::opaque::Block> + Send + Sync + 'static,
{
    log::info!(
        target: "p2p-bridge",
        "Inbound block processor started{}",
        if sync_peer_url.is_some() { " (with chain sync)" } else { "" }
    );

    while let Some(block) = block_rx.recv().await {
        let local_best = client.info().best_number as u64;
        let gap = block.height.saturating_sub(local_best);

        if gap == 0 {
            // Already at or past this height
            log::trace!(
                target: "p2p-bridge",
                "Ignoring block #{} (local best: #{})",
                block.height, local_best
            );
            continue;
        }

        if gap == 1 {
            // Next expected block — Substrate's native sync should handle this
            // via block announcements. Log it for monitoring.
            log::info!(
                target: "p2p-bridge",
                "P2P block #{} is next expected (local: #{}), Substrate sync should import",
                block.height, local_best
            );
        } else {
            // Gap > 1 — we're behind. If we have a sync peer URL, we could
            // trigger RPC-based chain sync (same approach as Python node).
            log::warn!(
                target: "p2p-bridge",
                "P2P reports block #{} but local is at #{} (gap: {}). \
                 Chain sync may be needed.",
                block.height, local_best, gap
            );

            if let Some(ref peer_url) = sync_peer_url {
                log::info!(
                    target: "p2p-bridge",
                    "Sync peer configured at {} — Substrate warp sync should catch up",
                    peer_url
                );
            }
        }
    }

    log::warn!(
        target: "p2p-bridge",
        "Inbound block channel closed, processor shutting down"
    );
}

/// Processes inbound transactions from the P2P channel.
///
/// Transactions received via the custom P2P gossip are logged. In the Substrate
/// model, transaction propagation happens through sc-network's native tx pool
/// protocol. This task monitors the custom P2P daemon's transaction stream for
/// telemetry and can be extended to inject transactions into the Substrate pool.
pub async fn process_inbound_transactions(
    mut tx_rx: mpsc::UnboundedReceiver<InboundTransaction>,
) {
    log::info!(
        target: "p2p-bridge",
        "Inbound transaction processor started"
    );

    let mut count: u64 = 0;

    while let Some(tx) = tx_rx.recv().await {
        count += 1;
        log::debug!(
            target: "p2p-bridge",
            "P2P tx #{}: txid={} size={} fee={}",
            count, tx.txid, tx.size, tx.fee
        );
    }

    log::warn!(
        target: "p2p-bridge",
        "Inbound transaction channel closed, processor shutting down"
    );
}

// ═══════════════════════════════════════════════════════════════════════
// Stats Poller
// ═══════════════════════════════════════════════════════════════════════

/// Periodically polls P2P daemon for network statistics.
async fn poll_peer_stats(grpc_addr: String, interval: Duration) {
    loop {
        tokio::time::sleep(interval).await;

        match p2p_client::P2pClient::connect(grpc_addr.clone()).await {
            Ok(mut client) => {
                if let Ok(resp) = client.get_peer_stats(PeerStatsRequest {}).await {
                    let stats = resp.into_inner();
                    log::info!(
                        target: "p2p-bridge",
                        "P2P stats: peers={}, gossip_peers={}, blocks_recv={}, \
                         blocks_sent={}, txs_recv={}, txs_sent={}, uptime={}s",
                        stats.peer_count,
                        stats.gossipsub_peers,
                        stats.blocks_received,
                        stats.blocks_sent,
                        stats.txs_received,
                        stats.txs_sent,
                        stats.uptime_seconds,
                    );
                }
            }
            Err(e) => {
                log::debug!(
                    target: "p2p-bridge",
                    "Stats poll failed (P2P daemon may be down): {}",
                    e
                );
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// Convenience — spawn all bridge tasks
// ═══════════════════════════════════════════════════════════════════════

/// Spawn the P2P bridge as background tasks on the Substrate task manager.
///
/// This is the main entry point called from `service.rs::new_full()`.
///
/// # Arguments
/// * `spawn_handle` - Substrate task manager spawn handle
/// * `client` - Substrate full client
/// * `grpc_addr` - gRPC address of the Rust P2P daemon
/// * `sync_peer_url` - Optional REST URL for chain sync fallback
pub fn spawn_p2p_bridge<C>(
    spawn_handle: sc_service::SpawnTaskHandle,
    client: Arc<C>,
    grpc_addr: String,
    sync_peer_url: Option<String>,
) -> P2pBroadcaster
where
    C: HeaderBackend<qbc_runtime::opaque::Block> + Send + Sync + 'static,
{
    let config = P2pBridgeConfig {
        grpc_addr: grpc_addr.clone(),
        ..Default::default()
    };

    let (bridge, block_rx, tx_rx) = P2pBridge::new(config);

    // Spawn the main bridge event stream (connects to P2P daemon, streams events)
    spawn_handle.spawn("p2p-bridge-stream", Some("p2p"), bridge.run());

    // Spawn inbound block processor
    spawn_handle.spawn(
        "p2p-bridge-blocks",
        Some("p2p"),
        process_inbound_blocks(client, block_rx, sync_peer_url),
    );

    // Spawn inbound transaction processor
    spawn_handle.spawn(
        "p2p-bridge-txs",
        Some("p2p"),
        process_inbound_transactions(tx_rx),
    );

    log::info!(
        target: "p2p-bridge",
        "P2P bridge tasks spawned (3 tasks: stream, blocks, txs)"
    );

    // Return broadcaster for outbound use
    P2pBroadcaster::new(grpc_addr)
}
