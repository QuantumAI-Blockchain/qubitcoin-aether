//! gRPC bridge using latest tonic 0.14

use tonic::{transport::Server, Request, Response, Status};
use tokio::sync::mpsc;
use tracing::info;

use crate::protocol::NetworkMessage;

pub mod p2p_service {
    tonic::include_proto!("p2p_service");
}

use p2p_service::{
    p2p_server::{P2p, P2pServer},
    BroadcastRequest, BroadcastResponse, PeerStatsRequest, PeerStatsResponse,
};

pub struct P2PService {
    to_network_tx: mpsc::UnboundedSender<NetworkMessage>,
    peer_count: std::sync::Arc<std::sync::atomic::AtomicUsize>,
}

impl P2PService {
    pub fn new(
        to_network_tx: mpsc::UnboundedSender<NetworkMessage>,
        peer_count: std::sync::Arc<std::sync::atomic::AtomicUsize>,
    ) -> Self {
        Self { to_network_tx, peer_count }
    }
}

#[tonic::async_trait]
impl P2p for P2PService {
    async fn broadcast_block(
        &self,
        request: Request<BroadcastRequest>,
    ) -> Result<Response<BroadcastResponse>, Status> {
        let req = request.into_inner();
        
        info!("📦 gRPC: Broadcasting block height={}", req.height);
        
        let msg = NetworkMessage::NewBlock {
            height: req.height,
            hash: req.hash,
        };
        
        self.to_network_tx
            .send(msg)
            .map_err(|e| Status::internal(format!("Channel send error: {}", e)))?;
        
        Ok(Response::new(BroadcastResponse { success: true }))
    }
    
    async fn get_peer_stats(
        &self,
        _request: Request<PeerStatsRequest>,
    ) -> Result<Response<PeerStatsResponse>, Status> {
        let count = self.peer_count.load(std::sync::atomic::Ordering::Relaxed);
        
        Ok(Response::new(PeerStatsResponse {
            peer_count: count as u32,
        }))
    }
}

pub async fn start_grpc_server(
    addr: &str,
    to_network_tx: mpsc::UnboundedSender<NetworkMessage>,
    peer_count: std::sync::Arc<std::sync::atomic::AtomicUsize>,
) -> anyhow::Result<()> {
    let service = P2PService::new(to_network_tx, peer_count);
    let addr = addr.parse()?;
    
    info!("🔌 gRPC server (tonic 0.14) listening on {}", addr);
    
    Server::builder()
        .add_service(P2pServer::new(service))
        .serve(addr)
        .await?;
    
    Ok(())
}
