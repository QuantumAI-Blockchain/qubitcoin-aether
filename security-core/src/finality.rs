//! BFT Finality vote tracking core.
//!
//! Pure computation — no DB access. Python wrapper handles persistence.

use std::collections::HashMap;

use parking_lot::RwLock;
use pyo3::prelude::*;

/// Validator info for stake-weighted voting.
#[derive(Debug, Clone)]
struct Validator {
    address: String,
    stake: f64,
}

/// Vote record.
#[derive(Debug, Clone)]
struct Vote {
    voter: String,
    block_height: u64,
    block_hash: String,
}

/// Core finality computation engine.
///
/// Thread-safe via parking_lot::RwLock.
#[pyclass]
pub struct FinalityCore {
    validators: RwLock<HashMap<String, Validator>>,
    votes: RwLock<HashMap<u64, Vec<Vote>>>,
    last_finalized: RwLock<u64>,
    threshold: f64,
    vote_expiry_blocks: u64,
}

#[pymethods]
impl FinalityCore {
    /// Create a new finality core.
    ///
    /// Args:
    ///     threshold: Fraction of stake required for finality (e.g. 0.667).
    ///     vote_expiry_blocks: Votes older than this are pruned.
    #[new]
    pub fn new(threshold: f64, vote_expiry_blocks: u64) -> Self {
        Self {
            validators: RwLock::new(HashMap::new()),
            votes: RwLock::new(HashMap::new()),
            last_finalized: RwLock::new(0),
            threshold,
            vote_expiry_blocks,
        }
    }

    /// Add or update a validator.
    pub fn add_validator(&self, address: &str, stake: f64) {
        let mut validators = self.validators.write();
        validators.insert(
            address.to_string(),
            Validator {
                address: address.to_string(),
                stake,
            },
        );
    }

    /// Remove a validator.
    pub fn remove_validator(&self, address: &str) {
        let mut validators = self.validators.write();
        validators.remove(address);
    }

    /// Record a finality vote.
    ///
    /// Returns True if the vote was accepted (voter is a validator and
    /// hasn't already voted for this height).
    pub fn record_vote(&self, voter: &str, block_height: u64, block_hash: &str) -> bool {
        let validators = self.validators.read();
        if !validators.contains_key(voter) {
            return false;
        }
        drop(validators);

        let mut votes = self.votes.write();
        let height_votes = votes.entry(block_height).or_insert_with(Vec::new);

        // Check for duplicate
        if height_votes.iter().any(|v| v.voter == voter) {
            return false;
        }

        height_votes.push(Vote {
            voter: voter.to_string(),
            block_height,
            block_hash: block_hash.to_string(),
        });

        true
    }

    /// Check if a block height has been finalized.
    pub fn check_finality(&self, block_height: u64) -> bool {
        let last = *self.last_finalized.read();
        if block_height <= last {
            return true;
        }

        let (voted_stake, total_stake) = self.calculate_vote_weight(block_height);
        if total_stake <= 0.0 {
            return false;
        }

        let ratio = voted_stake / total_stake;
        if ratio >= self.threshold {
            let mut last = self.last_finalized.write();
            if block_height > *last {
                *last = block_height;
            }
            true
        } else {
            false
        }
    }

    /// Get the last finalized block height.
    pub fn get_last_finalized(&self) -> u64 {
        *self.last_finalized.read()
    }

    /// Calculate vote weight for a block height.
    ///
    /// Returns (voted_stake, total_stake).
    pub fn calculate_vote_weight(&self, block_height: u64) -> (f64, f64) {
        let validators = self.validators.read();
        let total_stake: f64 = validators.values().map(|v| v.stake).sum();

        let votes = self.votes.read();
        let voted_stake: f64 = votes
            .get(&block_height)
            .map(|height_votes| {
                height_votes
                    .iter()
                    .filter_map(|vote| validators.get(&vote.voter).map(|v| v.stake))
                    .sum()
            })
            .unwrap_or(0.0);

        (voted_stake, total_stake)
    }

    /// Get the number of registered validators.
    pub fn validator_count(&self) -> usize {
        self.validators.read().len()
    }

    /// Get the number of votes for a block height.
    pub fn vote_count(&self, block_height: u64) -> usize {
        self.votes
            .read()
            .get(&block_height)
            .map(|v| v.len())
            .unwrap_or(0)
    }

    /// Prune old votes.
    pub fn prune_votes(&self, current_height: u64) {
        if current_height <= self.vote_expiry_blocks {
            return;
        }
        let cutoff = current_height - self.vote_expiry_blocks;
        let mut votes = self.votes.write();
        votes.retain(|&h, _| h >= cutoff);
    }

    /// Get total stake of all validators.
    pub fn total_stake(&self) -> f64 {
        self.validators.read().values().map(|v| v.stake).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_validator() {
        let fc = FinalityCore::new(0.667, 1000);
        fc.add_validator("v1", 100.0);
        assert_eq!(fc.validator_count(), 1);
        assert_eq!(fc.total_stake(), 100.0);
    }

    #[test]
    fn test_remove_validator() {
        let fc = FinalityCore::new(0.667, 1000);
        fc.add_validator("v1", 100.0);
        fc.remove_validator("v1");
        assert_eq!(fc.validator_count(), 0);
    }

    #[test]
    fn test_record_vote() {
        let fc = FinalityCore::new(0.667, 1000);
        fc.add_validator("v1", 100.0);
        assert!(fc.record_vote("v1", 1, "hash1"));
        assert_eq!(fc.vote_count(1), 1);
    }

    #[test]
    fn test_duplicate_vote_rejected() {
        let fc = FinalityCore::new(0.667, 1000);
        fc.add_validator("v1", 100.0);
        assert!(fc.record_vote("v1", 1, "hash1"));
        assert!(!fc.record_vote("v1", 1, "hash1"));
    }

    #[test]
    fn test_non_validator_rejected() {
        let fc = FinalityCore::new(0.667, 1000);
        assert!(!fc.record_vote("unknown", 1, "hash1"));
    }

    #[test]
    fn test_finality_reached() {
        let fc = FinalityCore::new(0.66, 1000);
        fc.add_validator("v1", 100.0);
        fc.add_validator("v2", 100.0);
        fc.add_validator("v3", 100.0);

        // 1/3 voted — not finalized
        fc.record_vote("v1", 10, "hash10");
        assert!(!fc.check_finality(10));

        // 2/3 voted (0.667 >= 0.66) — finalized
        fc.record_vote("v2", 10, "hash10");
        assert!(fc.check_finality(10));
    }

    #[test]
    fn test_finality_with_unequal_stakes() {
        let fc = FinalityCore::new(0.667, 1000);
        fc.add_validator("whale", 1000.0);
        fc.add_validator("small", 10.0);

        // Whale alone has 1000/1010 = 99% — sufficient
        fc.record_vote("whale", 5, "hash5");
        assert!(fc.check_finality(5));
    }

    #[test]
    fn test_last_finalized() {
        let fc = FinalityCore::new(0.667, 1000);
        fc.add_validator("v1", 100.0);
        fc.record_vote("v1", 5, "hash5");
        fc.check_finality(5);
        assert_eq!(fc.get_last_finalized(), 5);
    }

    #[test]
    fn test_already_finalized() {
        let fc = FinalityCore::new(0.667, 1000);
        fc.add_validator("v1", 100.0);
        fc.record_vote("v1", 10, "hash10");
        fc.check_finality(10);

        // Lower height is implicitly finalized
        assert!(fc.check_finality(5));
    }

    #[test]
    fn test_prune_votes() {
        let fc = FinalityCore::new(0.667, 100);
        fc.add_validator("v1", 100.0);
        fc.record_vote("v1", 10, "hash10");
        fc.record_vote("v1", 200, "hash200");
        fc.prune_votes(200);
        assert_eq!(fc.vote_count(10), 0);
        assert_eq!(fc.vote_count(200), 1);
    }

    #[test]
    fn test_calculate_vote_weight() {
        let fc = FinalityCore::new(0.667, 1000);
        fc.add_validator("v1", 100.0);
        fc.add_validator("v2", 200.0);
        fc.record_vote("v1", 1, "hash1");

        let (voted, total) = fc.calculate_vote_weight(1);
        assert_eq!(voted, 100.0);
        assert_eq!(total, 300.0);
    }
}
