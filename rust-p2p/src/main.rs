mod network;
mod protocol;
mod bridge;

use anyhow::Result;
use tokio::sync::mpsc;
use tracing::info;
use std::sync::{Arc, atomic::AtomicUsize};

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter("info,qubitcoin_p2p=debug")
        .init();
    
    info!("🦀 Qubitcoin Rust P2P Network v1.0.0");
    
    // Configuration
    let p2p_port = 4001;
    let grpc_addr = "127.0.0.1:50051";
    
    // Create channels
    let (to_python_tx, mut to_python_rx) = mpsc::unbounded_channel();
    let (from_python_tx, from_python_rx) = mpsc::unbounded_channel();
    let (to_network_tx, to_network_rx) = mpsc::unbounded_channel();
    
    // Peer count tracker
    let peer_count = Arc::new(AtomicUsize::new(0));
    let peer_count_clone = peer_count.clone();
    
    // Spawn P2P network
    tokio::spawn(async move {
        let mut p2p = network::P2PNetwork::new(p2p_port, to_python_tx, from_python_rx)
            .await
            .expect("Failed to create P2P network");
        
        p2p.run().await;
    });
    
    // Spawn gRPC server
    tokio::spawn(async move {
        bridge::start_grpc_server(grpc_addr, to_network_tx, peer_count)
            .await
            .expect("Failed to start gRPC server");
    });
    
    info!("✅ All services running");
    info!("📡 P2P Port: {}", p2p_port);
    info!("🔌 gRPC: {}", grpc_addr);
    
    // Event loop (forward messages between Python and network)
    loop {
        tokio::select! {
            Some(msg) = to_python_rx.recv() => {
                info!("To Python: {}", msg);
                // In production, forward via gRPC to Python
            }
        }
    }
}
