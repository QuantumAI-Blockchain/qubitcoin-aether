//! Stratum worker (miner connection) tracking.

use chrono::{DateTime, Utc};
use uuid::Uuid;

/// Represents a connected mining worker.
#[derive(Debug, Clone)]
pub struct StratumWorker {
    /// Unique worker ID
    pub id: String,
    /// Worker name (from mining.authorize)
    pub name: String,
    /// Miner address for reward payouts
    pub address: String,
    /// When the worker connected
    pub connected_at: DateTime<Utc>,
    /// Total shares submitted
    pub shares_submitted: u64,
    /// Accepted shares
    pub shares_accepted: u64,
    /// Rejected shares
    pub shares_rejected: u64,
    /// Blocks found by this worker
    pub blocks_found: u64,
    /// Current share difficulty for this worker
    pub difficulty: f64,
    /// Whether the worker is authorized
    pub authorized: bool,
    /// Whether the worker has subscribed
    pub subscribed: bool,
}

impl StratumWorker {
    /// Create a new worker with default state.
    pub fn new(share_difficulty: f64) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            name: String::new(),
            address: String::new(),
            connected_at: Utc::now(),
            shares_submitted: 0,
            shares_accepted: 0,
            shares_rejected: 0,
            blocks_found: 0,
            difficulty: share_difficulty,
            authorized: false,
            subscribed: false,
        }
    }

    /// Record a submitted share.
    pub fn record_share(&mut self, accepted: bool, block_found: bool) {
        self.shares_submitted += 1;
        if accepted {
            self.shares_accepted += 1;
            if block_found {
                self.blocks_found += 1;
            }
        } else {
            self.shares_rejected += 1;
        }
    }

    /// Get the worker's hashrate estimate based on accepted shares.
    pub fn estimated_hashrate(&self) -> f64 {
        let elapsed = (Utc::now() - self.connected_at).num_seconds() as f64;
        if elapsed <= 0.0 {
            return 0.0;
        }
        self.shares_accepted as f64 * self.difficulty / elapsed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_worker() {
        let w = StratumWorker::new(1.0);
        assert!(!w.id.is_empty());
        assert_eq!(w.shares_submitted, 0);
        assert!(!w.authorized);
    }

    #[test]
    fn test_record_share() {
        let mut w = StratumWorker::new(1.0);
        w.record_share(true, false);
        assert_eq!(w.shares_accepted, 1);
        assert_eq!(w.shares_rejected, 0);
        w.record_share(false, false);
        assert_eq!(w.shares_rejected, 1);
        w.record_share(true, true);
        assert_eq!(w.blocks_found, 1);
    }
}
