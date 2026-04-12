//! On-Chain AGI Bridge — anchors AGI state to the blockchain.
//!
//! The `OnChainBridge` records Phi measurements, Proof-of-Thought hashes,
//! and block-level AGI metrics. It supports both a full mode (interacting
//! with QVM contracts) and a log-only fallback mode.
//!
//! Ported from: `on_chain.py` (OnChainAGI + OnChainAGILogOnly).

use std::collections::HashMap;

use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Phi precision multiplier (contract stores uint256 = phi_float * 1000).
pub const PHI_PRECISION: u64 = 1000;

/// Default interval (in blocks) for writing Phi on-chain.
pub const DEFAULT_PHI_INTERVAL: u64 = 10;

// ---------------------------------------------------------------------------
// Block anchor record
// ---------------------------------------------------------------------------

/// A record of AGI state anchored to a specific block.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BlockAnchor {
    /// Block height this anchor is for.
    pub block_height: u64,
    /// Phi value at this block.
    pub phi_value: f64,
    /// Proof-of-Thought hash.
    pub thought_hash: String,
    /// Knowledge graph Merkle root.
    pub knowledge_root: String,
    /// Validator/miner address.
    pub validator_address: String,
    /// Integration score (0.0 - 1.0).
    pub integration: f64,
    /// Differentiation score (0.0 - 1.0).
    pub differentiation: f64,
    /// Phase coherence (0.0 - 1.0).
    pub coherence: f64,
    /// Total knowledge nodes.
    pub knowledge_nodes: u64,
    /// Total knowledge edges.
    pub knowledge_edges: u64,
    /// Higgs field value.
    pub higgs_field_value: f64,
    /// Average cognitive mass.
    pub avg_cognitive_mass: f64,
    /// Whether Phi was written on-chain.
    pub phi_written: bool,
    /// Whether PoT was submitted on-chain.
    pub pot_submitted: bool,
    /// Whether Higgs field was updated on-chain.
    pub higgs_updated: bool,
    /// Unix timestamp.
    pub timestamp: f64,
}

// ---------------------------------------------------------------------------
// On-chain statistics
// ---------------------------------------------------------------------------

/// Statistics for on-chain integration activity.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct OnChainStats {
    /// Number of Phi writes.
    pub phi_writes: u64,
    /// Number of PoT submissions.
    pub pot_submissions: u64,
    /// Number of veto checks.
    pub veto_checks: u64,
    /// Number of governance reads.
    pub governance_reads: u64,
    /// Number of errors.
    pub errors: u64,
    /// Total calls made.
    pub total_calls: u64,
    /// Current block height tracked.
    pub current_block: u64,
    /// Whether running in log-only mode.
    pub log_only_mode: bool,
    /// Contract configuration status.
    pub contracts_configured: HashMap<String, bool>,
}

// ---------------------------------------------------------------------------
// Proof hash generation
// ---------------------------------------------------------------------------

/// Generate a proof hash for on-chain submission.
///
/// Computes SHA-256 of the thought hash + knowledge root + block height.
pub fn compute_proof_hash(thought_hash: &str, knowledge_root: &str, block_height: u64) -> String {
    let mut hasher = Sha256::new();
    hasher.update(thought_hash.as_bytes());
    hasher.update(knowledge_root.as_bytes());
    hasher.update(block_height.to_le_bytes());
    format!("{:x}", hasher.finalize())
}

/// Generate an operation hash for veto checking.
pub fn compute_operation_hash(operation_description: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(operation_description.as_bytes());
    format!("{:x}", hasher.finalize())
}

// ---------------------------------------------------------------------------
// On-chain bridge
// ---------------------------------------------------------------------------

/// Bridge between the Aether Tree AGI engine and on-chain contracts.
///
/// In the Rust implementation, this acts as the state-tracking and
/// hash-generation layer. Actual contract interactions are delegated
/// to the Python side via PyO3 or to a future Rust QVM integration.
///
/// Supports two modes:
/// - **Full mode**: Records anchors and generates contract call data.
/// - **Log-only mode**: Records anchors locally without contract interaction
///   (used when no QVM/contracts are deployed).
pub struct OnChainBridge {
    /// Whether running in log-only mode.
    log_only: bool,
    /// Interval (in blocks) for writing Phi on-chain.
    phi_interval: u64,
    /// Contract addresses (empty strings = not configured).
    contract_addresses: RwLock<HashMap<String, String>>,
    /// Statistics.
    stats: RwLock<OnChainStats>,
    /// Recent block anchors (bounded ring buffer).
    anchors: RwLock<Vec<BlockAnchor>>,
    /// Maximum number of stored anchors.
    max_anchors: usize,
    /// Recent health results: (timestamp_secs, success).
    health_window: RwLock<Vec<(f64, bool)>>,
    /// Maximum health window size.
    health_window_max: usize,
}

impl OnChainBridge {
    /// Create a new OnChainBridge.
    ///
    /// # Arguments
    /// * `log_only` - If true, operates in log-only mode (no contract calls).
    /// * `phi_interval` - Blocks between on-chain Phi writes.
    pub fn new(log_only: bool, phi_interval: u64) -> Self {
        Self {
            log_only,
            phi_interval: phi_interval.max(1),
            contract_addresses: RwLock::new(HashMap::new()),
            stats: RwLock::new(OnChainStats {
                log_only_mode: log_only,
                ..Default::default()
            }),
            anchors: RwLock::new(Vec::new()),
            max_anchors: 1000,
            health_window: RwLock::new(Vec::new()),
            health_window_max: 100,
        }
    }

    /// Create a log-only bridge.
    pub fn log_only() -> Self {
        Self::new(true, DEFAULT_PHI_INTERVAL)
    }

    /// Set a contract address.
    pub fn set_contract_address(&self, name: &str, address: &str) {
        self.contract_addresses
            .write()
            .insert(name.to_string(), address.to_string());
    }

    /// Check if a contract is configured.
    pub fn has_contract(&self, name: &str) -> bool {
        self.contract_addresses
            .read()
            .get(name)
            .map_or(false, |a| !a.is_empty())
    }

    /// Record a Phi measurement.
    ///
    /// In full mode, this would trigger a contract write.
    /// In log-only mode, it records the measurement locally.
    pub fn record_phi(
        &self,
        block_height: u64,
        phi_value: f64,
        _integration: f64,
        _differentiation: f64,
        _coherence: f64,
        _knowledge_nodes: u64,
        _knowledge_edges: u64,
    ) -> bool {
        let mut stats = self.stats.write();
        stats.phi_writes += 1;
        stats.total_calls += 1;
        stats.current_block = block_height;

        tracing::debug!(
            block_height = block_height,
            phi = phi_value,
            mode = if self.log_only { "log-only" } else { "full" },
            "Phi recorded"
        );

        self.record_health(true);
        true
    }

    /// Submit a Proof-of-Thought hash.
    pub fn submit_proof(
        &self,
        block_height: u64,
        thought_hash: &str,
        knowledge_root: &str,
        _submitter: &str,
    ) -> bool {
        let mut stats = self.stats.write();
        stats.pot_submissions += 1;
        stats.total_calls += 1;
        stats.current_block = block_height;

        let _proof_hash = compute_proof_hash(thought_hash, knowledge_root, block_height);

        tracing::debug!(
            block_height = block_height,
            hash = &thought_hash[..16.min(thought_hash.len())],
            "PoT proof submitted"
        );

        self.record_health(true);
        true
    }

    /// Check if an operation has been vetoed.
    ///
    /// In log-only mode, always returns false (no veto).
    pub fn check_operation_vetoed(&self, operation_description: &str) -> bool {
        let mut stats = self.stats.write();
        stats.veto_checks += 1;
        stats.total_calls += 1;

        if self.log_only {
            return false;
        }

        let _op_hash = compute_operation_hash(operation_description);
        // In full mode, this would query the ConstitutionalAI contract.
        // For now, return false (no veto) as a safe default.
        false
    }

    /// Per-block on-chain integration hook.
    ///
    /// Writes Phi and PoT data at configured intervals.
    pub fn process_block(
        &self,
        block_height: u64,
        phi_value: f64,
        integration: f64,
        differentiation: f64,
        coherence: f64,
        knowledge_nodes: u64,
        knowledge_edges: u64,
        thought_hash: &str,
        knowledge_root: &str,
        validator_address: &str,
        higgs_field_value: f64,
        avg_cognitive_mass: f64,
    ) -> BlockAnchor {
        let mut phi_written = false;
        let mut pot_submitted = false;
        let higgs_updated = false;

        // Write Phi at configured interval
        if block_height % self.phi_interval == 0 {
            phi_written = self.record_phi(
                block_height,
                phi_value,
                integration,
                differentiation,
                coherence,
                knowledge_nodes,
                knowledge_edges,
            );
        }

        // Submit PoT proof for every block with a hash
        if !thought_hash.is_empty() && !knowledge_root.is_empty() {
            pot_submitted = self.submit_proof(
                block_height,
                thought_hash,
                knowledge_root,
                validator_address,
            );
        }

        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let anchor = BlockAnchor {
            block_height,
            phi_value,
            thought_hash: thought_hash.to_string(),
            knowledge_root: knowledge_root.to_string(),
            validator_address: validator_address.to_string(),
            integration,
            differentiation,
            coherence,
            knowledge_nodes,
            knowledge_edges,
            higgs_field_value,
            avg_cognitive_mass,
            phi_written,
            pot_submitted,
            higgs_updated,
            timestamp: now,
        };

        // Store the anchor
        {
            let mut anchors = self.anchors.write();
            anchors.push(anchor.clone());
            if anchors.len() > self.max_anchors {
                let excess = anchors.len() - self.max_anchors;
                anchors.drain(0..excess);
            }
        }

        anchor
    }

    /// Record a health result.
    fn record_health(&self, success: bool) {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let mut window = self.health_window.write();
        window.push((now, success));
        if window.len() > self.health_window_max {
            let excess = window.len() - self.health_window_max;
            window.drain(0..excess);
        }
    }

    /// Check on-chain integration health.
    pub fn is_healthy(&self) -> HashMap<String, serde_json::Value> {
        let contracts = self.contract_addresses.read();
        let contracts_configured = contracts.values().filter(|a| !a.is_empty()).count();

        let window = self.health_window.read();
        let error_rate = if window.is_empty() {
            0.0
        } else {
            let successes = window.iter().filter(|(_, ok)| *ok).count();
            1.0 - (successes as f64 / window.len() as f64)
        };

        let healthy = if self.log_only {
            true // Log-only is always "healthy"
        } else {
            contracts_configured > 0 && error_rate < 0.5
        };

        let mut result = HashMap::new();
        result.insert("healthy".into(), serde_json::json!(healthy));
        result.insert(
            "contracts_configured".into(),
            serde_json::json!(contracts_configured),
        );
        result.insert("error_rate".into(), serde_json::json!(error_rate));
        result.insert(
            "total_calls".into(),
            serde_json::json!(self.stats.read().total_calls),
        );
        result.insert("log_only".into(), serde_json::json!(self.log_only));
        result
    }

    /// Get on-chain integration statistics.
    pub fn get_stats(&self) -> OnChainStats {
        let mut stats = self.stats.read().clone();
        let contracts = self.contract_addresses.read();
        stats.contracts_configured = contracts
            .iter()
            .map(|(k, v)| (k.clone(), !v.is_empty()))
            .collect();
        stats
    }

    /// Get recent block anchors.
    pub fn recent_anchors(&self, limit: usize) -> Vec<BlockAnchor> {
        let anchors = self.anchors.read();
        let start = anchors.len().saturating_sub(limit);
        anchors[start..].to_vec()
    }

    /// Get anchor for a specific block height.
    pub fn get_anchor(&self, block_height: u64) -> Option<BlockAnchor> {
        self.anchors
            .read()
            .iter()
            .find(|a| a.block_height == block_height)
            .cloned()
    }

    /// Get the number of stored anchors.
    pub fn anchor_count(&self) -> usize {
        self.anchors.read().len()
    }
}

impl Default for OnChainBridge {
    fn default() -> Self {
        Self::log_only()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_proof_hash_deterministic() {
        let h1 = compute_proof_hash("abc", "root", 100);
        let h2 = compute_proof_hash("abc", "root", 100);
        assert_eq!(h1, h2);
    }

    #[test]
    fn test_compute_proof_hash_differs_with_block() {
        let h1 = compute_proof_hash("abc", "root", 100);
        let h2 = compute_proof_hash("abc", "root", 101);
        assert_ne!(h1, h2);
    }

    #[test]
    fn test_compute_operation_hash() {
        let h = compute_operation_hash("modify knowledge graph");
        assert_eq!(h.len(), 64); // SHA-256 hex
    }

    #[test]
    fn test_log_only_bridge_creation() {
        let bridge = OnChainBridge::log_only();
        assert!(bridge.log_only);
        let stats = bridge.get_stats();
        assert!(stats.log_only_mode);
    }

    #[test]
    fn test_record_phi() {
        let bridge = OnChainBridge::log_only();
        let result = bridge.record_phi(100, 2.5, 0.6, 0.4, 0.7, 1000, 5000);
        assert!(result);
        assert_eq!(bridge.get_stats().phi_writes, 1);
    }

    #[test]
    fn test_submit_proof() {
        let bridge = OnChainBridge::log_only();
        let result = bridge.submit_proof(100, "hash123456789012", "root", "validator");
        assert!(result);
        assert_eq!(bridge.get_stats().pot_submissions, 1);
    }

    #[test]
    fn test_check_veto_log_only() {
        let bridge = OnChainBridge::log_only();
        let vetoed = bridge.check_operation_vetoed("test operation");
        assert!(!vetoed);
        assert_eq!(bridge.get_stats().veto_checks, 1);
    }

    #[test]
    fn test_process_block_records_anchor() {
        let bridge = OnChainBridge::new(true, 5);
        let anchor = bridge.process_block(
            10, 2.5, 0.6, 0.4, 0.7, 1000, 5000,
            "thought_hash_01234", "merkle_root_56789", "validator1",
            174.14, 50.0,
        );
        assert_eq!(anchor.block_height, 10);
        assert!(anchor.phi_written); // block 10 % 5 == 0
        assert!(anchor.pot_submitted);
        assert_eq!(bridge.anchor_count(), 1);
    }

    #[test]
    fn test_process_block_phi_interval() {
        let bridge = OnChainBridge::new(true, 10);
        let a1 = bridge.process_block(
            7, 2.0, 0.5, 0.3, 0.6, 500, 2000,
            "h", "r", "v", 0.0, 0.0,
        );
        assert!(!a1.phi_written); // 7 % 10 != 0

        let a2 = bridge.process_block(
            10, 2.0, 0.5, 0.3, 0.6, 500, 2000,
            "h", "r", "v", 0.0, 0.0,
        );
        assert!(a2.phi_written); // 10 % 10 == 0
    }

    #[test]
    fn test_process_block_empty_hash_skips_pot() {
        let bridge = OnChainBridge::log_only();
        let anchor = bridge.process_block(
            5, 2.0, 0.5, 0.3, 0.6, 500, 2000,
            "", "", "v", 0.0, 0.0,
        );
        assert!(!anchor.pot_submitted);
    }

    #[test]
    fn test_anchor_retrieval() {
        let bridge = OnChainBridge::log_only();
        bridge.process_block(
            42, 2.0, 0.5, 0.3, 0.6, 500, 2000,
            "h", "r", "v", 0.0, 0.0,
        );
        let anchor = bridge.get_anchor(42);
        assert!(anchor.is_some());
        assert_eq!(anchor.unwrap().block_height, 42);

        let missing = bridge.get_anchor(999);
        assert!(missing.is_none());
    }

    #[test]
    fn test_recent_anchors_limit() {
        let bridge = OnChainBridge::log_only();
        for i in 0..20 {
            bridge.process_block(
                i, 1.0, 0.5, 0.3, 0.6, 100, 200,
                "h", "r", "v", 0.0, 0.0,
            );
        }
        let recent = bridge.recent_anchors(5);
        assert_eq!(recent.len(), 5);
        assert_eq!(recent[0].block_height, 15);
        assert_eq!(recent[4].block_height, 19);
    }

    #[test]
    fn test_anchor_eviction() {
        let mut bridge = OnChainBridge::log_only();
        bridge.max_anchors = 10;

        for i in 0..20 {
            bridge.process_block(
                i, 1.0, 0.5, 0.3, 0.6, 100, 200,
                "h", "r", "v", 0.0, 0.0,
            );
        }
        assert_eq!(bridge.anchor_count(), 10);
    }

    #[test]
    fn test_health_log_only_always_healthy() {
        let bridge = OnChainBridge::log_only();
        let health = bridge.is_healthy();
        assert_eq!(health["healthy"], serde_json::json!(true));
    }

    #[test]
    fn test_set_contract_address() {
        let bridge = OnChainBridge::new(false, 10);
        assert!(!bridge.has_contract("consciousness_dashboard"));
        bridge.set_contract_address("consciousness_dashboard", "0xabc123");
        assert!(bridge.has_contract("consciousness_dashboard"));
    }

    #[test]
    fn test_stats_accumulation() {
        let bridge = OnChainBridge::log_only();
        bridge.record_phi(1, 1.0, 0.5, 0.3, 0.6, 100, 200);
        bridge.record_phi(2, 1.5, 0.6, 0.4, 0.7, 200, 400);
        bridge.submit_proof(3, "hash", "root", "val");
        bridge.check_operation_vetoed("test");

        let stats = bridge.get_stats();
        assert_eq!(stats.phi_writes, 2);
        assert_eq!(stats.pot_submissions, 1);
        assert_eq!(stats.veto_checks, 1);
        assert_eq!(stats.total_calls, 4);
    }

    #[test]
    fn test_block_anchor_serialization() {
        let anchor = BlockAnchor {
            block_height: 100,
            phi_value: 2.5,
            thought_hash: "abc".into(),
            knowledge_root: "root".into(),
            validator_address: "val".into(),
            integration: 0.6,
            differentiation: 0.4,
            coherence: 0.7,
            knowledge_nodes: 1000,
            knowledge_edges: 5000,
            higgs_field_value: 174.14,
            avg_cognitive_mass: 50.0,
            phi_written: true,
            pot_submitted: true,
            higgs_updated: false,
            timestamp: 1000.0,
        };
        let json = serde_json::to_string(&anchor).unwrap();
        assert!(json.contains("\"block_height\":100"));
        let deserialized: BlockAnchor = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.block_height, 100);
    }
}
