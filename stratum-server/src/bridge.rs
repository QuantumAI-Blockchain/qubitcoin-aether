//! gRPC bridge client to the Python node.
//!
//! Connects to the Python node's gRPC server (port 50053) to:
//! - Fetch work units (block templates)
//! - Submit mining solutions
//! - Subscribe to new block notifications

use tonic::transport::Channel;
use tracing::info;

use crate::stratum_proto::stratum_bridge_client::StratumBridgeClient;
use crate::stratum_proto::{Empty, Solution, HeightRequest};

/// Client wrapper for the Python node gRPC bridge.
pub struct NodeBridge {
    client: Option<StratumBridgeClient<Channel>>,
    addr: String,
}

impl NodeBridge {
    /// Create a new bridge (not yet connected).
    pub fn new(addr: &str) -> Self {
        Self {
            client: None,
            addr: addr.to_string(),
        }
    }

    /// Connect to the Python node gRPC server.
    pub async fn connect(&mut self) -> Result<(), tonic::transport::Error> {
        let channel = Channel::from_shared(self.addr.clone())
            .expect("Invalid gRPC address")
            .connect()
            .await?;
        self.client = Some(StratumBridgeClient::new(channel));
        info!("Connected to node gRPC at {}", self.addr);
        Ok(())
    }

    /// Check if connected.
    pub fn is_connected(&self) -> bool {
        self.client.is_some()
    }

    /// Get a work unit from the node.
    pub async fn get_work_unit(&mut self) -> Result<crate::stratum_proto::WorkUnit, tonic::Status> {
        let client = self.client.as_mut()
            .ok_or_else(|| tonic::Status::unavailable("Not connected to node"))?;
        let resp = client.get_work_unit(Empty {}).await?;
        Ok(resp.into_inner())
    }

    /// Submit a mining solution to the node.
    pub async fn submit_solution(
        &mut self,
        job_id: &str,
        worker_id: &str,
        worker_address: &str,
        vqe_params: Vec<f64>,
        energy: f64,
        nonce: u64,
    ) -> Result<crate::stratum_proto::SubmitResult, tonic::Status> {
        let client = self.client.as_mut()
            .ok_or_else(|| tonic::Status::unavailable("Not connected to node"))?;
        let solution = Solution {
            job_id: job_id.to_string(),
            worker_id: worker_id.to_string(),
            worker_address: worker_address.to_string(),
            vqe_params,
            ground_state_energy: energy,
            nonce,
        };
        let resp = client.submit_solution(solution).await?;
        Ok(resp.into_inner())
    }

    /// Get current difficulty from node.
    pub async fn get_difficulty(&mut self, height: u64) -> Result<f64, tonic::Status> {
        let client = self.client.as_mut()
            .ok_or_else(|| tonic::Status::unavailable("Not connected to node"))?;
        let resp = client.get_difficulty(HeightRequest { height }).await?;
        Ok(resp.into_inner().difficulty)
    }

    /// Subscribe to new block notifications.
    pub async fn stream_new_blocks(
        &mut self,
    ) -> Result<tonic::Streaming<crate::stratum_proto::NewBlockNotify>, tonic::Status> {
        let client = self.client.as_mut()
            .ok_or_else(|| tonic::Status::unavailable("Not connected to node"))?;
        let resp = client.stream_new_blocks(Empty {}).await?;
        Ok(resp.into_inner())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bridge_new() {
        let bridge = NodeBridge::new("http://127.0.0.1:50053");
        assert!(!bridge.is_connected());
    }
}
