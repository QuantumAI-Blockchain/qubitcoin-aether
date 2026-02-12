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
    let (_from_python_tx, from_python_rx) = mpsc::unbounded_channel();
    let (to_network_tx, _to_network_rx) = mpsc::unbounded_channel();
    
    // Peer count tracker
    let peer_count = Arc::new(AtomicUsize::new(0));
    
    // Spawn P2P network (takes ownership via run(self))
    tokio::spawn(async move {
        match network::P2PNetwork::new(p2p_port, to_python_tx, from_python_rx).await {
            Ok(p2p) => p2p.run().await,
            Err(e) => eprintln!("Failed to create P2P network: {}", e),
        }
    });
    
    // Spawn gRPC server
    let peer_count_clone = peer_count.clone();
    tokio::spawn(async move {
        if let Err(e) = bridge::start_grpc_server(grpc_addr, to_network_tx, peer_count_clone).await {
            eprintln!("gRPC server error: {}", e);
        }
    });
    
    info!("✅ All services running");
    info!("📡 P2P Port: {}", p2p_port);
    info!("🔌 gRPC: {}", grpc_addr);
    
    // Event loop
    loop {
        tokio::select! {
            Some(msg) = to_python_rx.recv() => {
                info!("To Python: {}", msg);
            }
        }
    }
}
