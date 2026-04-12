//! AIKGS gRPC client types, request/response structs, and circuit breaker.
//!
//! Provides all data structures exchanged with the Rust AIKGS sidecar, plus
//! a circuit breaker implementation to prevent cascading failures when the
//! sidecar is slow or unresponsive. Actual gRPC I/O is in the Python client
//! or future Rust orchestrator.
//!
//! Ported from: `src/qubitcoin/aether/aikgs_client.py` (734 LOC)

use std::collections::HashMap;

use chrono::Utc;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

// ─── Circuit Breaker ────────────────────────────────────────────────────────

/// Circuit breaker state machine.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[pyclass(eq, eq_int)]
pub enum CircuitState {
    /// Normal operation, requests flow through.
    Closed,
    /// Too many failures, requests are blocked.
    Open,
    /// Cooldown expired, one probe request allowed.
    HalfOpen,
}

/// Circuit breaker for protecting against cascading failures from the AIKGS sidecar.
///
/// Opens after `failure_threshold` consecutive failures, stays open for
/// `cooldown_secs`, then transitions to half-open for a probe.
#[derive(Debug, Clone)]
#[pyclass]
pub struct CircuitBreaker {
    failure_threshold: u32,
    cooldown_secs: f64,
    slow_threshold_secs: f64,

    failures: u32,
    open_since: f64,
    total_trips: u32,
    last_success_time: f64,
    last_failure_method: String,
}

#[pymethods]
impl CircuitBreaker {
    #[new]
    #[pyo3(signature = (failure_threshold=3, cooldown_secs=60.0, slow_threshold_secs=10.0))]
    pub fn new(
        failure_threshold: u32,
        cooldown_secs: f64,
        slow_threshold_secs: f64,
    ) -> Self {
        Self {
            failure_threshold,
            cooldown_secs,
            slow_threshold_secs,
            failures: 0,
            open_since: 0.0,
            total_trips: 0,
            last_success_time: 0.0,
            last_failure_method: String::new(),
        }
    }

    /// Current state of the circuit breaker.
    pub fn state(&self) -> CircuitState {
        if self.failures < self.failure_threshold {
            return CircuitState::Closed;
        }
        let now = Utc::now().timestamp() as f64;
        let elapsed = now - self.open_since;
        if elapsed >= self.cooldown_secs {
            CircuitState::HalfOpen
        } else {
            CircuitState::Open
        }
    }

    /// Returns true if the circuit is open and calls should be blocked.
    pub fn is_open(&self) -> bool {
        self.state() == CircuitState::Open
    }

    /// Remaining cooldown seconds (0 if closed or half-open).
    pub fn cooldown_remaining(&self) -> f64 {
        if self.state() != CircuitState::Open {
            return 0.0;
        }
        let now = Utc::now().timestamp() as f64;
        let remaining = self.cooldown_secs - (now - self.open_since);
        if remaining > 0.0 { remaining } else { 0.0 }
    }

    /// Record a successful call. Resets the failure counter.
    pub fn record_success(&mut self) {
        if self.failures > 0 {
            log::info!(
                "AIKGS circuit breaker closed after {} failures",
                self.failures
            );
        }
        self.failures = 0;
        self.last_success_time = Utc::now().timestamp() as f64;
    }

    /// Record a failed or slow call. Opens the circuit if threshold is reached.
    pub fn record_failure(&mut self, method: &str, elapsed_secs: f64, error: &str) {
        self.failures += 1;
        self.last_failure_method = method.to_string();

        if self.failures >= self.failure_threshold {
            self.open_since = Utc::now().timestamp() as f64;
            self.total_trips += 1;
            log::warn!(
                "AIKGS circuit breaker OPEN (trip #{}) after {} failures \
                 — last: {} ({:.1}s): {}. Cooling down {:.0}s",
                self.total_trips,
                self.failures,
                method,
                elapsed_secs,
                error,
                self.cooldown_secs,
            );
        }
    }

    /// Check if an elapsed call duration counts as "slow" (should be treated as failure).
    pub fn is_slow(&self, elapsed_secs: f64) -> bool {
        elapsed_secs > self.slow_threshold_secs
    }

    /// Total number of times the circuit has tripped open.
    #[getter]
    pub fn total_trips(&self) -> u32 {
        self.total_trips
    }

    /// Current consecutive failure count.
    #[getter]
    pub fn failures(&self) -> u32 {
        self.failures
    }

    /// Get circuit breaker status as a dict.
    pub fn get_status(&self) -> HashMap<String, String> {
        let mut m = HashMap::new();
        m.insert("state".to_string(), format!("{:?}", self.state()));
        m.insert("failures".to_string(), self.failures.to_string());
        m.insert("total_trips".to_string(), self.total_trips.to_string());
        m.insert(
            "cooldown_remaining".to_string(),
            format!("{:.1}", self.cooldown_remaining()),
        );
        m.insert(
            "last_failure_method".to_string(),
            self.last_failure_method.clone(),
        );
        m
    }
}

// ─── Connection Config ──────────────────────────────────────────────────────

/// Configuration for connecting to the AIKGS gRPC sidecar.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all, set_all)]
pub struct AikgsClientConfig {
    /// gRPC address (host:port).
    pub grpc_addr: String,
    /// Authentication token for x-auth-token header.
    pub auth_token: String,
    /// gRPC call timeout in seconds.
    pub timeout_secs: u32,
    /// Circuit breaker failure threshold.
    pub cb_failure_threshold: u32,
    /// Circuit breaker cooldown seconds.
    pub cb_cooldown_secs: f64,
    /// Calls taking longer than this are counted as slow failures.
    pub cb_slow_threshold_secs: f64,
}

#[pymethods]
impl AikgsClientConfig {
    #[new]
    #[pyo3(signature = (grpc_addr="127.0.0.1:50052".to_string(), auth_token="".to_string(), timeout_secs=30, cb_failure_threshold=3, cb_cooldown_secs=60.0, cb_slow_threshold_secs=10.0))]
    pub fn new(
        grpc_addr: String,
        auth_token: String,
        timeout_secs: u32,
        cb_failure_threshold: u32,
        cb_cooldown_secs: f64,
        cb_slow_threshold_secs: f64,
    ) -> Self {
        Self {
            grpc_addr,
            auth_token,
            timeout_secs,
            cb_failure_threshold,
            cb_cooldown_secs,
            cb_slow_threshold_secs,
        }
    }

    /// Create a CircuitBreaker from this config.
    pub fn create_circuit_breaker(&self) -> CircuitBreaker {
        CircuitBreaker::new(
            self.cb_failure_threshold,
            self.cb_cooldown_secs,
            self.cb_slow_threshold_secs,
        )
    }
}

// ─── Data Structures (Protobuf → Rust equivalents) ──────────────────────────

/// A knowledge contribution record.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsContribution {
    pub contribution_id: u64,
    pub contributor_address: String,
    pub content_hash: String,
    pub knowledge_node_id: String,
    pub quality_score: f64,
    pub novelty_score: f64,
    pub combined_score: f64,
    pub tier: String,
    pub domain: String,
    pub reward_amount: f64,
    pub affiliate_l1_amount: f64,
    pub affiliate_l2_amount: f64,
    pub is_bounty_fulfillment: bool,
    pub bounty_id: u64,
    pub badges_earned: Vec<String>,
    pub block_height: u64,
    pub timestamp: u64,
    pub status: String,
}

#[pymethods]
impl AikgsContribution {
    #[new]
    #[pyo3(signature = (contribution_id=0, contributor_address="".to_string(), content_hash="".to_string(), knowledge_node_id="".to_string(), quality_score=0.0, novelty_score=0.0, combined_score=0.0, tier="bronze".to_string(), domain="".to_string(), reward_amount=0.0, affiliate_l1_amount=0.0, affiliate_l2_amount=0.0, is_bounty_fulfillment=false, bounty_id=0, badges_earned=vec![], block_height=0, timestamp=0, status="pending".to_string()))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        contribution_id: u64,
        contributor_address: String,
        content_hash: String,
        knowledge_node_id: String,
        quality_score: f64,
        novelty_score: f64,
        combined_score: f64,
        tier: String,
        domain: String,
        reward_amount: f64,
        affiliate_l1_amount: f64,
        affiliate_l2_amount: f64,
        is_bounty_fulfillment: bool,
        bounty_id: u64,
        badges_earned: Vec<String>,
        block_height: u64,
        timestamp: u64,
        status: String,
    ) -> Self {
        Self {
            contribution_id,
            contributor_address,
            content_hash,
            knowledge_node_id,
            quality_score,
            novelty_score,
            combined_score,
            tier,
            domain,
            reward_amount,
            affiliate_l1_amount,
            affiliate_l2_amount,
            is_bounty_fulfillment,
            bounty_id,
            badges_earned,
            block_height,
            timestamp,
            status,
        }
    }

    /// Convert to a Python dict.
    pub fn to_dict(&self) -> HashMap<String, PyObject> {
        Python::with_gil(|py| {
            let mut m = HashMap::new();
            m.insert("contribution_id".into(), self.contribution_id.into_pyobject(py).unwrap().into_any().unbind());
            m.insert("contributor_address".into(), self.contributor_address.clone().into_pyobject(py).unwrap().into_any().unbind());
            m.insert("content_hash".into(), self.content_hash.clone().into_pyobject(py).unwrap().into_any().unbind());
            m.insert("quality_score".into(), self.quality_score.into_pyobject(py).unwrap().into_any().unbind());
            m.insert("novelty_score".into(), self.novelty_score.into_pyobject(py).unwrap().into_any().unbind());
            m.insert("combined_score".into(), self.combined_score.into_pyobject(py).unwrap().into_any().unbind());
            m.insert("tier".into(), self.tier.clone().into_pyobject(py).unwrap().into_any().unbind());
            m.insert("domain".into(), self.domain.clone().into_pyobject(py).unwrap().into_any().unbind());
            m.insert("reward_amount".into(), self.reward_amount.into_pyobject(py).unwrap().into_any().unbind());
            m.insert("status".into(), self.status.clone().into_pyobject(py).unwrap().into_any().unbind());
            m
        })
    }
}

/// Affiliate record.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsAffiliate {
    pub address: String,
    pub referrer_address: String,
    pub referral_code: String,
    pub l1_referrals: u32,
    pub l2_referrals: u32,
    pub total_l1_commission: f64,
    pub total_l2_commission: f64,
    pub is_active: bool,
}

#[pymethods]
impl AikgsAffiliate {
    #[new]
    #[pyo3(signature = (address="".to_string(), referrer_address="".to_string(), referral_code="".to_string(), l1_referrals=0, l2_referrals=0, total_l1_commission=0.0, total_l2_commission=0.0, is_active=true))]
    pub fn new(
        address: String,
        referrer_address: String,
        referral_code: String,
        l1_referrals: u32,
        l2_referrals: u32,
        total_l1_commission: f64,
        total_l2_commission: f64,
        is_active: bool,
    ) -> Self {
        Self {
            address,
            referrer_address,
            referral_code,
            l1_referrals,
            l2_referrals,
            total_l1_commission,
            total_l2_commission,
            is_active,
        }
    }
}

/// Knowledge bounty record.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsBounty {
    pub bounty_id: u64,
    pub domain: String,
    pub description: String,
    pub gap_hash: String,
    pub reward_amount: f64,
    pub boost_multiplier: f64,
    pub status: String,
    pub claimer_address: String,
    pub contribution_id: u64,
    pub created_at: u64,
    pub expires_at: u64,
}

#[pymethods]
impl AikgsBounty {
    #[new]
    #[pyo3(signature = (bounty_id=0, domain="".to_string(), description="".to_string(), gap_hash="".to_string(), reward_amount=0.0, boost_multiplier=1.0, status="open".to_string(), claimer_address="".to_string(), contribution_id=0, created_at=0, expires_at=0))]
    pub fn new(
        bounty_id: u64,
        domain: String,
        description: String,
        gap_hash: String,
        reward_amount: f64,
        boost_multiplier: f64,
        status: String,
        claimer_address: String,
        contribution_id: u64,
        created_at: u64,
        expires_at: u64,
    ) -> Self {
        Self {
            bounty_id,
            domain,
            description,
            gap_hash,
            reward_amount,
            boost_multiplier,
            status,
            claimer_address,
            contribution_id,
            created_at,
            expires_at,
        }
    }
}

/// Contributor profile record.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsProfile {
    pub address: String,
    pub reputation_points: f64,
    pub level: u32,
    pub level_name: String,
    pub total_contributions: u32,
    pub best_streak: u32,
    pub current_streak: u32,
    pub gold_count: u32,
    pub diamond_count: u32,
    pub bounties_fulfilled: u32,
    pub referrals: u32,
    pub badges: Vec<String>,
    pub unlocked_features: Vec<String>,
    pub last_contribution_at: u64,
}

#[pymethods]
impl AikgsProfile {
    #[new]
    #[pyo3(signature = (address="".to_string(), reputation_points=0.0, level=0, level_name="".to_string(), total_contributions=0, best_streak=0, current_streak=0, gold_count=0, diamond_count=0, bounties_fulfilled=0, referrals=0, badges=vec![], unlocked_features=vec![], last_contribution_at=0))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        address: String,
        reputation_points: f64,
        level: u32,
        level_name: String,
        total_contributions: u32,
        best_streak: u32,
        current_streak: u32,
        gold_count: u32,
        diamond_count: u32,
        bounties_fulfilled: u32,
        referrals: u32,
        badges: Vec<String>,
        unlocked_features: Vec<String>,
        last_contribution_at: u64,
    ) -> Self {
        Self {
            address,
            reputation_points,
            level,
            level_name,
            total_contributions,
            best_streak,
            current_streak,
            gold_count,
            diamond_count,
            bounties_fulfilled,
            referrals,
            badges,
            unlocked_features,
            last_contribution_at,
        }
    }
}

/// Curation review from a curator.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsReview {
    pub curator_address: String,
    pub contribution_id: u64,
    pub vote: bool,
    pub comment: String,
    pub timestamp: u64,
}

#[pymethods]
impl AikgsReview {
    #[new]
    #[pyo3(signature = (curator_address="".to_string(), contribution_id=0, vote=true, comment="".to_string(), timestamp=0))]
    pub fn new(
        curator_address: String,
        contribution_id: u64,
        vote: bool,
        comment: String,
        timestamp: u64,
    ) -> Self {
        Self {
            curator_address,
            contribution_id,
            vote,
            comment,
            timestamp,
        }
    }
}

/// Curation round record.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsCurationRound {
    pub contribution_id: u64,
    pub required_votes: u32,
    pub votes_for: u32,
    pub votes_against: u32,
    pub reviews: Vec<AikgsReview>,
    pub status: String,
    pub finalized_at: u64,
}

#[pymethods]
impl AikgsCurationRound {
    #[new]
    #[pyo3(signature = (contribution_id=0, required_votes=3, votes_for=0, votes_against=0, status="pending".to_string(), finalized_at=0))]
    pub fn new(
        contribution_id: u64,
        required_votes: u32,
        votes_for: u32,
        votes_against: u32,
        status: String,
        finalized_at: u64,
    ) -> Self {
        Self {
            contribution_id,
            required_votes,
            votes_for,
            votes_against,
            reviews: Vec::new(),
            status,
            finalized_at,
        }
    }

    /// Add a review to this curation round.
    pub fn add_review(&mut self, review: AikgsReview) {
        if review.vote {
            self.votes_for += 1;
        } else {
            self.votes_against += 1;
        }
        self.reviews.push(review);
    }

    /// Check if the round has reached quorum.
    pub fn has_quorum(&self) -> bool {
        (self.votes_for + self.votes_against) >= self.required_votes
    }

    /// Determine the outcome: "approved", "rejected", or "pending".
    pub fn outcome(&self) -> String {
        if !self.has_quorum() {
            return "pending".to_string();
        }
        if self.votes_for > self.votes_against {
            "approved".to_string()
        } else {
            "rejected".to_string()
        }
    }
}

/// API key info record.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsKeyInfo {
    pub key_id: String,
    pub provider: String,
    pub model: String,
    pub owner_address: String,
    pub is_shared: bool,
    pub shared_reward_bps: u32,
    pub label: String,
    pub use_count: u64,
    pub is_active: bool,
}

#[pymethods]
impl AikgsKeyInfo {
    #[new]
    #[pyo3(signature = (key_id="".to_string(), provider="".to_string(), model="".to_string(), owner_address="".to_string(), is_shared=false, shared_reward_bps=1500, label="".to_string(), use_count=0, is_active=true))]
    pub fn new(
        key_id: String,
        provider: String,
        model: String,
        owner_address: String,
        is_shared: bool,
        shared_reward_bps: u32,
        label: String,
        use_count: u64,
        is_active: bool,
    ) -> Self {
        Self {
            key_id,
            provider,
            model,
            owner_address,
            is_shared,
            shared_reward_bps,
            label,
            use_count,
            is_active,
        }
    }
}

// ─── Aggregate Stats Structs ────────────────────────────────────────────────

/// Reward pool statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsRewardStats {
    pub pool_balance: f64,
    pub total_distributed: f64,
    pub distribution_count: u64,
    pub total_contributions: u64,
    pub base_reward: f64,
    pub max_reward: f64,
    pub early_threshold: u64,
    pub contributors_with_streaks: u64,
}

#[pymethods]
impl AikgsRewardStats {
    #[new]
    pub fn new() -> Self {
        Self {
            pool_balance: 0.0,
            total_distributed: 0.0,
            distribution_count: 0,
            total_contributions: 0,
            base_reward: 0.0,
            max_reward: 0.0,
            early_threshold: 0,
            contributors_with_streaks: 0,
        }
    }
}

/// Contribution aggregate statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsContributionStats {
    pub total_contributions: u64,
    pub unique_contributors: u64,
    pub total_rewards_distributed: f64,
    pub tier_distribution: HashMap<String, u64>,
    pub bounty_fulfillments: u64,
}

#[pymethods]
impl AikgsContributionStats {
    #[new]
    pub fn new() -> Self {
        Self {
            total_contributions: 0,
            unique_contributors: 0,
            total_rewards_distributed: 0.0,
            tier_distribution: HashMap::new(),
            bounty_fulfillments: 0,
        }
    }
}

/// Bounty aggregate statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsBountyStats {
    pub total_bounties: u64,
    pub open_bounties: u64,
    pub fulfilled_bounties: u64,
    pub total_reward_pool: f64,
}

#[pymethods]
impl AikgsBountyStats {
    #[new]
    pub fn new() -> Self {
        Self {
            total_bounties: 0,
            open_bounties: 0,
            fulfilled_bounties: 0,
            total_reward_pool: 0.0,
        }
    }
}

/// Curator statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsCuratorStats {
    pub address: String,
    pub reputation: f64,
    pub total_reviews: u64,
    pub correct_votes: u64,
    pub accuracy: f64,
}

#[pymethods]
impl AikgsCuratorStats {
    #[new]
    #[pyo3(signature = (address="".to_string(), reputation=0.0, total_reviews=0, correct_votes=0, accuracy=0.0))]
    pub fn new(
        address: String,
        reputation: f64,
        total_reviews: u64,
        correct_votes: u64,
        accuracy: f64,
    ) -> Self {
        Self {
            address,
            reputation,
            total_reviews,
            correct_votes,
            accuracy,
        }
    }
}

/// Curation aggregate statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsCurationStats {
    pub total_rounds: u64,
    pub status_distribution: HashMap<String, u64>,
    pub total_curators: u64,
    pub avg_reputation: f64,
}

#[pymethods]
impl AikgsCurationStats {
    #[new]
    pub fn new() -> Self {
        Self {
            total_rounds: 0,
            status_distribution: HashMap::new(),
            total_curators: 0,
            avg_reputation: 0.0,
        }
    }
}

/// Affiliate aggregate statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsAffiliateStats {
    pub total_affiliates: u64,
    pub total_l1_commissions: f64,
    pub total_l2_commissions: f64,
}

#[pymethods]
impl AikgsAffiliateStats {
    #[new]
    pub fn new() -> Self {
        Self {
            total_affiliates: 0,
            total_l1_commissions: 0.0,
            total_l2_commissions: 0.0,
        }
    }
}

/// Unlocks aggregate statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass(get_all)]
pub struct AikgsUnlocksStats {
    pub total_profiles: u64,
    pub global_contributions: u64,
    pub level_distribution: HashMap<String, u64>,
    pub total_badges_awarded: u64,
}

#[pymethods]
impl AikgsUnlocksStats {
    #[new]
    pub fn new() -> Self {
        Self {
            total_profiles: 0,
            global_contributions: 0,
            level_distribution: HashMap::new(),
            total_badges_awarded: 0,
        }
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_circuit_breaker_starts_closed() {
        let cb = CircuitBreaker::new(3, 60.0, 10.0);
        assert_eq!(cb.state(), CircuitState::Closed);
        assert!(!cb.is_open());
        assert_eq!(cb.failures(), 0);
        assert_eq!(cb.total_trips(), 0);
    }

    #[test]
    fn test_circuit_breaker_opens_on_failures() {
        let mut cb = CircuitBreaker::new(3, 60.0, 10.0);
        cb.record_failure("test1", 1.0, "err1");
        assert_eq!(cb.state(), CircuitState::Closed);

        cb.record_failure("test2", 1.0, "err2");
        assert_eq!(cb.state(), CircuitState::Closed);

        cb.record_failure("test3", 1.0, "err3");
        assert_eq!(cb.state(), CircuitState::Open);
        assert!(cb.is_open());
        assert_eq!(cb.total_trips(), 1);
    }

    #[test]
    fn test_circuit_breaker_resets_on_success() {
        let mut cb = CircuitBreaker::new(3, 60.0, 10.0);
        cb.record_failure("m", 1.0, "e");
        cb.record_failure("m", 1.0, "e");
        assert_eq!(cb.failures(), 2);

        cb.record_success();
        assert_eq!(cb.failures(), 0);
        assert_eq!(cb.state(), CircuitState::Closed);
    }

    #[test]
    fn test_circuit_breaker_half_open_after_cooldown() {
        let mut cb = CircuitBreaker::new(2, 0.0, 10.0); // 0 cooldown = immediate half-open
        cb.record_failure("m", 1.0, "e");
        cb.record_failure("m", 1.0, "e");
        // With 0 cooldown, should be half-open immediately
        assert_eq!(cb.state(), CircuitState::HalfOpen);
    }

    #[test]
    fn test_circuit_breaker_is_slow() {
        let cb = CircuitBreaker::new(3, 60.0, 10.0);
        assert!(!cb.is_slow(5.0));
        assert!(!cb.is_slow(10.0));
        assert!(cb.is_slow(10.1));
    }

    #[test]
    fn test_circuit_breaker_get_status() {
        let cb = CircuitBreaker::new(3, 60.0, 10.0);
        let status = cb.get_status();
        assert_eq!(status.get("state").unwrap(), "Closed");
        assert_eq!(status.get("failures").unwrap(), "0");
    }

    #[test]
    fn test_config_defaults() {
        let config = AikgsClientConfig::new(
            "127.0.0.1:50052".to_string(),
            "".to_string(),
            30,
            3,
            60.0,
            10.0,
        );
        assert_eq!(config.grpc_addr, "127.0.0.1:50052");
        assert_eq!(config.timeout_secs, 30);
    }

    #[test]
    fn test_config_creates_circuit_breaker() {
        let config = AikgsClientConfig::new(
            "host:5000".to_string(),
            "token".to_string(),
            10,
            5,
            30.0,
            5.0,
        );
        let cb = config.create_circuit_breaker();
        assert_eq!(cb.state(), CircuitState::Closed);
    }

    #[test]
    fn test_contribution_creation() {
        let c = AikgsContribution::new(
            1, "addr".into(), "hash".into(), "node1".into(),
            0.9, 0.8, 0.85, "gold".into(), "physics".into(),
            1.5, 0.1, 0.05, false, 0, vec!["first_contrib".into()],
            1000, 1234567890, "accepted".into(),
        );
        assert_eq!(c.contribution_id, 1);
        assert_eq!(c.quality_score, 0.9);
        assert_eq!(c.tier, "gold");
        assert_eq!(c.badges_earned, vec!["first_contrib"]);
    }

    #[test]
    fn test_affiliate_creation() {
        let a = AikgsAffiliate::new(
            "addr1".into(), "addr0".into(), "REF-123".into(),
            5, 2, 1.5, 0.3, true,
        );
        assert_eq!(a.l1_referrals, 5);
        assert_eq!(a.total_l1_commission, 1.5);
        assert!(a.is_active);
    }

    #[test]
    fn test_bounty_creation() {
        let b = AikgsBounty::new(
            42, "physics".into(), "explain gravity".into(), "hash".into(),
            10.0, 2.0, "open".into(), "".into(), 0, 100, 200,
        );
        assert_eq!(b.bounty_id, 42);
        assert_eq!(b.boost_multiplier, 2.0);
        assert_eq!(b.status, "open");
    }

    #[test]
    fn test_profile_creation() {
        let p = AikgsProfile::new(
            "addr".into(), 1500.0, 5, "Expert".into(),
            100, 30, 10, 5, 2, 3, 8,
            vec!["gold_star".into()], vec!["advanced_chat".into()], 999,
        );
        assert_eq!(p.level, 5);
        assert_eq!(p.level_name, "Expert");
        assert_eq!(p.badges, vec!["gold_star"]);
    }

    #[test]
    fn test_curation_round() {
        let mut round = AikgsCurationRound::new(1, 3, 0, 0, "pending".into(), 0);
        assert!(!round.has_quorum());
        assert_eq!(round.outcome(), "pending");

        round.add_review(AikgsReview::new("c1".into(), 1, true, "good".into(), 100));
        round.add_review(AikgsReview::new("c2".into(), 1, true, "nice".into(), 101));
        round.add_review(AikgsReview::new("c3".into(), 1, false, "meh".into(), 102));

        assert!(round.has_quorum());
        assert_eq!(round.outcome(), "approved");
        assert_eq!(round.votes_for, 2);
        assert_eq!(round.votes_against, 1);
        assert_eq!(round.reviews.len(), 3);
    }

    #[test]
    fn test_curation_round_rejected() {
        let mut round = AikgsCurationRound::new(2, 2, 0, 0, "pending".into(), 0);
        round.add_review(AikgsReview::new("c1".into(), 2, false, "bad".into(), 100));
        round.add_review(AikgsReview::new("c2".into(), 2, false, "worse".into(), 101));
        assert_eq!(round.outcome(), "rejected");
    }

    #[test]
    fn test_key_info_creation() {
        let k = AikgsKeyInfo::new(
            "key123".into(), "openai".into(), "gpt-4".into(),
            "addr".into(), true, 1500, "My key".into(), 42, true,
        );
        assert_eq!(k.provider, "openai");
        assert!(k.is_shared);
        assert_eq!(k.shared_reward_bps, 1500);
    }

    #[test]
    fn test_reward_stats_defaults() {
        let rs = AikgsRewardStats::new();
        assert_eq!(rs.pool_balance, 0.0);
        assert_eq!(rs.total_distributed, 0.0);
    }

    #[test]
    fn test_contribution_stats_defaults() {
        let cs = AikgsContributionStats::new();
        assert_eq!(cs.total_contributions, 0);
        assert!(cs.tier_distribution.is_empty());
    }

    #[test]
    fn test_bounty_stats_defaults() {
        let bs = AikgsBountyStats::new();
        assert_eq!(bs.total_bounties, 0);
        assert_eq!(bs.open_bounties, 0);
    }
}
