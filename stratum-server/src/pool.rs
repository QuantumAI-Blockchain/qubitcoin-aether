//! Mining pool — manages connected workers and distributes work.

use std::sync::Arc;

use dashmap::DashMap;
use tracing::{info, warn};

use crate::config::StratumConfig;
use crate::worker::StratumWorker;

/// Statistics for the mining pool.
#[derive(Debug, Clone, serde::Serialize)]
pub struct PoolStats {
    pub workers_connected: usize,
    pub total_shares_submitted: u64,
    pub total_shares_accepted: u64,
    pub total_shares_rejected: u64,
    pub total_blocks_found: u64,
    pub current_difficulty: f64,
}

/// Mining pool that tracks workers and validates shares.
pub struct MiningPool {
    config: StratumConfig,
    workers: Arc<DashMap<String, StratumWorker>>,
    current_job_id: Arc<tokio::sync::RwLock<String>>,
    network_difficulty: Arc<tokio::sync::RwLock<f64>>,
    total_blocks_found: Arc<std::sync::atomic::AtomicU64>,
}

impl MiningPool {
    /// Create a new mining pool.
    pub fn new(config: StratumConfig) -> Self {
        Self {
            config,
            workers: Arc::new(DashMap::new()),
            current_job_id: Arc::new(tokio::sync::RwLock::new(String::new())),
            network_difficulty: Arc::new(tokio::sync::RwLock::new(1.0)),
            total_blocks_found: Arc::new(std::sync::atomic::AtomicU64::new(0)),
        }
    }

    /// Register a new worker.
    pub fn add_worker(&self) -> Option<StratumWorker> {
        if self.workers.len() >= self.config.max_workers {
            warn!("Max workers reached ({})", self.config.max_workers);
            return None;
        }
        let share_diff = self.share_difficulty_sync();
        let worker = StratumWorker::new(share_diff);
        let id = worker.id.clone();
        self.workers.insert(id, worker.clone());
        info!("Worker connected: {}", worker.id);
        Some(worker)
    }

    /// Remove a disconnected worker.
    pub fn remove_worker(&self, worker_id: &str) {
        if self.workers.remove(worker_id).is_some() {
            info!("Worker disconnected: {}", worker_id);
        }
    }

    /// Get a mutable reference to a worker.
    pub fn get_worker_mut(&self, worker_id: &str) -> Option<dashmap::mapref::one::RefMut<'_, String, StratumWorker>> {
        self.workers.get_mut(worker_id)
    }

    /// Authorize a worker.
    pub fn authorize_worker(&self, worker_id: &str, name: &str, address: &str) -> bool {
        if let Some(mut worker) = self.workers.get_mut(worker_id) {
            worker.name = name.to_string();
            worker.address = address.to_string();
            worker.authorized = true;
            true
        } else {
            false
        }
    }

    /// Record a share submission result.
    pub fn record_share(&self, worker_id: &str, accepted: bool, block_found: bool) {
        if let Some(mut worker) = self.workers.get_mut(worker_id) {
            worker.record_share(accepted, block_found);
        }
        if block_found {
            self.total_blocks_found.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        }
    }

    /// Update the current job ID.
    pub async fn set_current_job(&self, job_id: String) {
        let mut jid = self.current_job_id.write().await;
        *jid = job_id;
    }

    /// Get the current job ID.
    pub async fn get_current_job(&self) -> String {
        self.current_job_id.read().await.clone()
    }

    /// Update network difficulty.
    pub async fn set_network_difficulty(&self, difficulty: f64) {
        let mut d = self.network_difficulty.write().await;
        *d = difficulty;
    }

    /// Get current network difficulty.
    pub async fn get_network_difficulty(&self) -> f64 {
        *self.network_difficulty.read().await
    }

    /// Calculate share difficulty (network / divisor).
    fn share_difficulty_sync(&self) -> f64 {
        // Use a default during initialization; updated later via set_network_difficulty
        1.0 / self.config.share_difficulty_divisor
    }

    /// Get current share difficulty.
    pub async fn share_difficulty(&self) -> f64 {
        let net = self.get_network_difficulty().await;
        net / self.config.share_difficulty_divisor
    }

    /// Get pool statistics.
    pub async fn stats(&self) -> PoolStats {
        let mut total_submitted = 0u64;
        let mut total_accepted = 0u64;
        let mut total_rejected = 0u64;
        for entry in self.workers.iter() {
            total_submitted += entry.shares_submitted;
            total_accepted += entry.shares_accepted;
            total_rejected += entry.shares_rejected;
        }
        PoolStats {
            workers_connected: self.workers.len(),
            total_shares_submitted: total_submitted,
            total_shares_accepted: total_accepted,
            total_shares_rejected: total_rejected,
            total_blocks_found: self.total_blocks_found.load(std::sync::atomic::Ordering::Relaxed),
            current_difficulty: self.get_network_difficulty().await,
        }
    }

    /// Get worker count.
    pub fn worker_count(&self) -> usize {
        self.workers.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> StratumConfig {
        StratumConfig {
            host: "0.0.0.0".to_string(),
            port: 3333,
            max_workers: 10,
            share_difficulty_divisor: 16.0,
            node_grpc_addr: "http://127.0.0.1:50053".to_string(),
        }
    }

    #[test]
    fn test_add_worker() {
        let pool = MiningPool::new(test_config());
        let w = pool.add_worker().unwrap();
        assert!(!w.id.is_empty());
        assert_eq!(pool.worker_count(), 1);
    }

    #[test]
    fn test_max_workers() {
        let pool = MiningPool::new(test_config());
        for _ in 0..10 {
            assert!(pool.add_worker().is_some());
        }
        assert!(pool.add_worker().is_none());
    }

    #[test]
    fn test_remove_worker() {
        let pool = MiningPool::new(test_config());
        let w = pool.add_worker().unwrap();
        pool.remove_worker(&w.id);
        assert_eq!(pool.worker_count(), 0);
    }

    #[test]
    fn test_authorize() {
        let pool = MiningPool::new(test_config());
        let w = pool.add_worker().unwrap();
        assert!(pool.authorize_worker(&w.id, "miner1", "qbc1addr"));
        let worker = pool.get_worker_mut(&w.id).unwrap();
        assert!(worker.authorized);
        assert_eq!(worker.name, "miner1");
    }

    #[test]
    fn test_record_share() {
        let pool = MiningPool::new(test_config());
        let w = pool.add_worker().unwrap();
        pool.record_share(&w.id, true, false);
        pool.record_share(&w.id, true, true);
        pool.record_share(&w.id, false, false);
        let worker = pool.get_worker_mut(&w.id).unwrap();
        assert_eq!(worker.shares_accepted, 2);
        assert_eq!(worker.shares_rejected, 1);
        assert_eq!(worker.blocks_found, 1);
    }
}
