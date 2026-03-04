//! Qubitcoin Stratum Mining Server
//!
//! WebSocket-based mining pool server that bridges miners to the
//! Qubitcoin node via gRPC. Supports the VQE mining protocol.

use std::sync::Arc;

use futures_util::{SinkExt, StreamExt};
use tokio::net::TcpListener;
use tokio_tungstenite::accept_async;
use tracing::{error, info, warn};

use qbc_stratum::bridge::NodeBridge;
use qbc_stratum::config::StratumConfig;
use qbc_stratum::pool::MiningPool;
use qbc_stratum::protocol::{
    self, MiningMessage,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    // Load config
    let _ = dotenvy::dotenv();
    let config = StratumConfig::from_env();

    info!(
        "Qubitcoin Stratum Server starting on {}:{}",
        config.host, config.port
    );
    info!("Max workers: {}", config.max_workers);
    info!("Node gRPC: {}", config.node_grpc_addr);

    // Create mining pool
    let pool = Arc::new(MiningPool::new(config.clone()));

    // Create node bridge
    let bridge = Arc::new(tokio::sync::Mutex::new(NodeBridge::new(&config.node_grpc_addr)));

    // Try to connect to node (non-fatal if node not running)
    {
        let mut b = bridge.lock().await;
        match b.connect().await {
            Ok(()) => info!("Connected to node gRPC"),
            Err(e) => warn!("Node gRPC not available (will retry): {}", e),
        }
    }

    // Start WebSocket server
    let addr = format!("{}:{}", config.host, config.port);
    let listener = TcpListener::bind(&addr).await?;
    info!("Stratum server listening on {}", addr);

    while let Ok((stream, peer_addr)) = listener.accept().await {
        let pool = pool.clone();
        let bridge = bridge.clone();

        tokio::spawn(async move {
            let ws = match accept_async(stream).await {
                Ok(ws) => ws,
                Err(e) => {
                    error!("WebSocket handshake failed from {}: {}", peer_addr, e);
                    return;
                }
            };

            let worker = match pool.add_worker() {
                Some(w) => w,
                None => {
                    warn!("Rejected connection from {} (pool full)", peer_addr);
                    return;
                }
            };

            let worker_id = worker.id.clone();
            info!("Worker {} connected from {}", worker_id, peer_addr);

            let (mut ws_tx, mut ws_rx) = ws.split();

            // Send initial difficulty
            let diff_msg = protocol::set_difficulty(worker.difficulty);
            if let Err(e) = ws_tx
                .send(tokio_tungstenite::tungstenite::Message::Text(diff_msg.into()))
                .await
            {
                error!("Failed to send difficulty to {}: {}", worker_id, e);
                pool.remove_worker(&worker_id);
                return;
            }

            // Message loop
            while let Some(msg) = ws_rx.next().await {
                let msg = match msg {
                    Ok(tokio_tungstenite::tungstenite::Message::Text(text)) => text,
                    Ok(tokio_tungstenite::tungstenite::Message::Close(_)) => {
                        info!("Worker {} closed connection", worker_id);
                        break;
                    }
                    Ok(_) => continue,
                    Err(e) => {
                        warn!("WebSocket error from {}: {}", worker_id, e);
                        break;
                    }
                };

                let parsed = match MiningMessage::parse(&msg) {
                    Ok(m) => m,
                    Err(e) => {
                        warn!("Invalid message from {}: {}", worker_id, e);
                        continue;
                    }
                };

                let response = match parsed {
                    MiningMessage::Subscribe { id } => {
                        if let Some(mut w) = pool.get_worker_mut(&worker_id) {
                            w.subscribed = true;
                        }
                        protocol::subscribe_response(id, &worker_id)
                    }

                    MiningMessage::Authorize { id, worker_name, address } => {
                        let success = pool.authorize_worker(&worker_id, &worker_name, &address);
                        protocol::authorize_response(id, success)
                    }

                    MiningMessage::Submit {
                        id, job_id, vqe_params, energy, nonce, ..
                    } => {
                        let worker_address = pool
                            .get_worker_mut(&worker_id)
                            .map(|w| w.address.clone())
                            .unwrap_or_default();

                        let mut b = bridge.lock().await;
                        let (accepted, block_found, reason) = if b.is_connected() {
                            match b
                                .submit_solution(
                                    &job_id,
                                    &worker_id,
                                    &worker_address,
                                    vqe_params,
                                    energy,
                                    nonce,
                                )
                                .await
                            {
                                Ok(result) => (result.accepted, result.block_found, result.reason),
                                Err(e) => {
                                    warn!("gRPC submit error: {}", e);
                                    (false, false, "Node unavailable".to_string())
                                }
                            }
                        } else {
                            (false, false, "Node not connected".to_string())
                        };

                        pool.record_share(&worker_id, accepted, block_found);
                        protocol::submit_response(id, accepted, &reason)
                    }

                    MiningMessage::Unknown { id, method } => {
                        warn!("Unknown method from {}: {}", worker_id, method);
                        let resp = protocol::submit_response(
                            id.unwrap_or(serde_json::Value::Null),
                            false,
                            &format!("Unknown method: {}", method),
                        );
                        resp
                    }
                };

                if let Err(e) = ws_tx
                    .send(tokio_tungstenite::tungstenite::Message::Text(response.into()))
                    .await
                {
                    error!("Failed to send to {}: {}", worker_id, e);
                    break;
                }
            }

            pool.remove_worker(&worker_id);
        });
    }

    Ok(())
}
