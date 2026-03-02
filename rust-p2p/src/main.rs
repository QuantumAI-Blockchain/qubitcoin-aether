mod network;
mod protocol;
mod bridge;

use anyhow::Result;
use tokio::sync::{mpsc, broadcast};
use tracing::{info, error};
use std::sync::Arc;

use bridge::p2p_service::NetworkEvent;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter("info,qubitcoin_p2p=debug")
        .init();

    info!("Qubitcoin Rust P2P Network v1.0.0");

    // Configuration (env-overridable in RP4)
    let p2p_port = std::env::var("P2P_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(4001u16);
    let grpc_addr = std::env::var("RUST_P2P_GRPC_ADDR")
        .unwrap_or_else(|_| "127.0.0.1:50051".to_string());

    // ── Channels ────────────────────────────────────────────────────
    // P2P network → main loop (blocks/txs received from gossipsub)
    let (to_python_tx, mut to_python_rx) = mpsc::unbounded_channel();
    // gRPC bridge → P2P network (blocks/txs to broadcast via gossipsub)
    let (to_network_tx, from_python_rx) = mpsc::unbounded_channel();
    // Broadcast channel for streaming events to Python gRPC clients
    let (event_tx, _) = broadcast::channel::<NetworkEvent>(256);

    // Shared statistics
    let stats = Arc::new(bridge::P2PStats::new());
    let stats_clone = stats.clone();
    let event_tx_clone = event_tx.clone();

    // ── Spawn P2P network ───────────────────────────────────────────
    tokio::spawn(async move {
        match network::P2PNetwork::new(p2p_port, to_python_tx, from_python_rx).await {
            Ok(p2p) => {
                p2p.run().await;
            }
            Err(e) => {
                error!("Failed to create P2P network: {}", e);
            }
        }
    });

    // ── Spawn gRPC server ───────────────────────────────────────────
    let grpc_addr_clone = grpc_addr.clone();
    tokio::spawn(async move {
        if let Err(e) = bridge::start_grpc_server(&grpc_addr_clone, to_network_tx, event_tx_clone, stats_clone).await {
            error!("Failed to start gRPC server: {}", e);
        }
    });

    info!("All services running");
    info!("P2P Port: {} (TCP) / {} (QUIC)", p2p_port, p2p_port + 1);
    info!("gRPC: {}", grpc_addr);

    // ── Event loop: forward P2P messages → gRPC broadcast channel ──
    // This is the critical bridge: messages from gossipsub are forwarded
    // to all subscribed Python gRPC streaming clients.
    loop {
        tokio::select! {
            Some(msg) = to_python_rx.recv() => {
                let now = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();

                let event = match &msg {
                    protocol::NetworkMessage::NewBlock { height, hash } => {
                        stats.blocks_received.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                        info!("Block received from P2P: height={}", height);
                        NetworkEvent {
                            event_type: 0, // BLOCK_RECEIVED
                            timestamp: now,
                            block: Some(bridge::p2p_service::BlockData {
                                height: *height,
                                hash: hash.clone(),
                                prev_hash: String::new(),
                                timestamp: now,
                                difficulty: 0.0,
                                nonce: 0,
                                miner: String::new(),
                            }),
                            transaction: None,
                            peer: None,
                        }
                    }
                    protocol::NetworkMessage::Block(b) => {
                        stats.blocks_received.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                        info!("Full block from P2P: height={}", b.height);
                        NetworkEvent {
                            event_type: 0,
                            timestamp: now,
                            block: Some(bridge::p2p_service::BlockData {
                                height: b.height,
                                hash: b.hash.clone(),
                                prev_hash: b.prev_hash.clone(),
                                timestamp: b.timestamp,
                                difficulty: b.difficulty,
                                nonce: b.nonce,
                                miner: b.miner.clone(),
                            }),
                            transaction: None,
                            peer: None,
                        }
                    }
                    protocol::NetworkMessage::NewTransaction(tx) => {
                        stats.txs_received.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                        info!("Tx received from P2P: {}", &tx.txid[..8.min(tx.txid.len())]);
                        NetworkEvent {
                            event_type: 1, // TRANSACTION_RECEIVED
                            timestamp: now,
                            block: None,
                            transaction: Some(bridge::p2p_service::TransactionData {
                                txid: tx.txid.clone(),
                                size: tx.size as u32,
                                fee: tx.fee.clone(),
                            }),
                            peer: None,
                        }
                    }
                    _ => {
                        // Other message types (Ping, Pong, GetInfo, etc.) are handled
                        // internally by the P2P network and don't need forwarding.
                        continue;
                    }
                };

                // Broadcast to all subscribed Python gRPC clients.
                // If no subscribers, the message is silently dropped (OK).
                let _ = event_tx.send(event);
            }
        }
    }
}
