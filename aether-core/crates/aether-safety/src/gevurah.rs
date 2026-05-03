//! Gevurah veto system — the safety guardian of Aether Tree.
//!
//! Implements constitutional safety principles, threat evaluation, BFT consensus
//! for veto overrides, HMAC-authenticated operations, and emergency shutdown.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};

use hmac::{Hmac, Mac};
use parking_lot::RwLock;
use pyo3::prelude::*;
use rand::Rng;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::audit_log::{AuditLog, EventKind};

/// BFT threshold — 67% of validators must agree.
pub const BFT_THRESHOLD: f64 = 0.67;

/// Maximum severity scale for threat classification.
pub const MAX_SEVERITY: u8 = 10;

type HmacSha256 = Hmac<Sha256>;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

/// Classification of detected threats.
#[pyclass(eq, eq_int)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ThreatLevel {
    None = 0,
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4,
}

#[pymethods]
impl ThreatLevel {
    #[getter]
    fn value(&self) -> &str {
        match self {
            ThreatLevel::None => "none",
            ThreatLevel::Low => "low",
            ThreatLevel::Medium => "medium",
            ThreatLevel::High => "high",
            ThreatLevel::Critical => "critical",
        }
    }
}

impl ThreatLevel {
    /// Get the string value of this threat level (Rust-native accessor).
    pub fn as_str(&self) -> &str {
        match self {
            ThreatLevel::None => "none",
            ThreatLevel::Low => "low",
            ThreatLevel::Medium => "medium",
            ThreatLevel::High => "high",
            ThreatLevel::Critical => "critical",
        }
    }

    /// Map a max severity score (0-10) to a threat level.
    pub fn from_severity(severity: u8) -> Self {
        match severity {
            0 => ThreatLevel::None,
            1..=3 => ThreatLevel::Low,
            4..=6 => ThreatLevel::Medium,
            7..=8 => ThreatLevel::High,
            _ => ThreatLevel::Critical,
        }
    }
}

/// Predefined reasons for Gevurah veto.
#[pyclass(eq, eq_int)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum VetoReason {
    SafetyViolation = 0,
    SusyImbalance = 1,
    ConstitutionalBreach = 2,
    ResourceExhaustion = 3,
    AdversarialInput = 4,
    ConsensusFailure = 5,
    UnauthorizedAction = 6,
    UnboundedOperation = 7,
}

impl VetoReason {
    /// Get the string value (Rust-native).
    pub fn as_str(&self) -> &str {
        match self {
            VetoReason::SafetyViolation => "safety_violation",
            VetoReason::SusyImbalance => "susy_imbalance",
            VetoReason::ConstitutionalBreach => "constitutional_breach",
            VetoReason::ResourceExhaustion => "resource_exhaustion",
            VetoReason::AdversarialInput => "adversarial_input",
            VetoReason::ConsensusFailure => "consensus_failure",
            VetoReason::UnauthorizedAction => "unauthorized_action",
            VetoReason::UnboundedOperation => "unbounded_operation",
        }
    }
}

#[pymethods]
impl VetoReason {
    #[getter]
    fn value(&self) -> &str {
        self.as_str()
    }
}

// ---------------------------------------------------------------------------
// SafetyPrinciple
// ---------------------------------------------------------------------------

/// An immutable constitutional principle enforced by the safety system.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyPrinciple {
    #[pyo3(get)]
    pub principle_id: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub severity: u8,
    #[pyo3(get)]
    pub active: bool,
    #[pyo3(get)]
    pub created_block: u64,
}

#[pymethods]
impl SafetyPrinciple {
    #[new]
    #[pyo3(signature = (principle_id, description, severity=5, active=true, created_block=0))]
    fn new(
        principle_id: String,
        description: String,
        severity: u8,
        active: bool,
        created_block: u64,
    ) -> Self {
        Self {
            principle_id,
            description,
            severity: severity.min(MAX_SEVERITY),
            active,
            created_block,
        }
    }

    /// Check if an action description might violate this principle.
    ///
    /// Uses whole-word boundary matching with negation detection
    /// to avoid false positives on descriptions that explicitly deny harmful intent.
    fn matches(&self, action_description: &str) -> bool {
        let action_lower = action_description.to_lowercase();

        // Negation check: if the action explicitly negates harm, skip
        let negation_patterns = [
            r"\b(prevent|avoid|block|stop|detect|protect|defend|safe)\b.*\b(harm|damage|exploit|attack)\b",
            r"\b(no|not|never|without)\s+(harm|damage|attack|exploit|steal)\b",
        ];
        for pat in &negation_patterns {
            if let Ok(re) = Regex::new(pat) {
                if re.is_match(&action_lower) {
                    return false;
                }
            }
        }

        // Primary: whole-word keyword matching
        let lower = self.description.to_lowercase();
        let keywords: Vec<&str> = lower.split_whitespace().collect();
        let mut match_count = 0u32;
        for kw in &keywords {
            if kw.len() <= 3 {
                continue;
            }
            let pattern = format!(r"\b{}\b", regex::escape(kw));
            if let Ok(re) = Regex::new(&pattern) {
                if re.is_match(&action_lower) {
                    match_count += 1;
                }
            }
        }

        match_count >= 1
    }
}

// ---------------------------------------------------------------------------
// VetoRecord
// ---------------------------------------------------------------------------

/// Global monotonic counter for deterministic veto IDs.
static VETO_COUNTER: AtomicU64 = AtomicU64::new(0);

/// Immutable record of a Gevurah veto decision.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VetoRecord {
    #[pyo3(get)]
    pub veto_id: String,
    #[pyo3(get)]
    pub reason: VetoReason,
    #[pyo3(get)]
    pub threat_level: ThreatLevel,
    #[pyo3(get)]
    pub action_description: String,
    #[pyo3(get)]
    pub source_node: String,
    #[pyo3(get)]
    pub target_node: String,
    #[pyo3(get)]
    pub block_height: u64,
    #[pyo3(get)]
    pub timestamp: f64,
    #[pyo3(get)]
    pub overridden: bool,
    #[pyo3(get)]
    pub override_consensus: f64,
    #[pyo3(get)]
    pub principles_violated: Vec<String>,
}

#[pymethods]
impl VetoRecord {
    #[new]
    #[pyo3(signature = (
        reason=VetoReason::SafetyViolation,
        threat_level=ThreatLevel::High,
        action_description=String::new(),
        source_node=String::new(),
        target_node=String::new(),
        block_height=0,
        principles_violated=vec![],
    ))]
    fn new(
        reason: VetoReason,
        threat_level: ThreatLevel,
        action_description: String,
        source_node: String,
        target_node: String,
        block_height: u64,
        principles_violated: Vec<String>,
    ) -> Self {
        let counter = VETO_COUNTER.fetch_add(1, Ordering::SeqCst);
        let data = format!(
            "{:?}:{}:{}:{}:{}:{}",
            reason, action_description, source_node, target_node, block_height, counter
        );
        let hash = Sha256::digest(data.as_bytes());
        let veto_id = hex::encode(&hash[..8]); // 16 hex chars
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        Self {
            veto_id,
            reason,
            threat_level,
            action_description,
            source_node,
            target_node,
            block_height,
            timestamp,
            overridden: false,
            override_consensus: 0.0,
            principles_violated,
        }
    }
}

// We need hex encoding for the hash — use a small inline helper
mod hex {
    pub fn encode(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }
}

// ---------------------------------------------------------------------------
// ConsensusVote
// ---------------------------------------------------------------------------

/// A validator's vote on a proposed action.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsensusVote {
    #[pyo3(get)]
    pub validator_address: String,
    #[pyo3(get)]
    pub action_hash: String,
    #[pyo3(get)]
    pub approve: bool,
    #[pyo3(get)]
    pub timestamp: f64,
    #[pyo3(get)]
    pub stake_weight: f64,
}

#[pymethods]
impl ConsensusVote {
    #[new]
    #[pyo3(signature = (validator_address, action_hash, approve, stake_weight=1.0))]
    fn new(
        validator_address: String,
        action_hash: String,
        approve: bool,
        stake_weight: f64,
    ) -> Self {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();
        Self {
            validator_address,
            action_hash,
            approve,
            timestamp,
            stake_weight,
        }
    }
}

// ---------------------------------------------------------------------------
// VetoAuthenticator
// ---------------------------------------------------------------------------

/// HMAC-based authentication for veto and shutdown operations.
///
/// Prevents unauthenticated callers from issuing vetoes or triggering
/// emergency shutdown. Each operation requires a one-time nonce token
/// signed with a shared secret.
#[pyclass]
pub struct VetoAuthenticator {
    secret: Vec<u8>,
    used_nonces: RwLock<HashMap<String, f64>>,
    max_nonces: usize,
}

#[pymethods]
impl VetoAuthenticator {
    #[new]
    #[pyo3(signature = (secret=None))]
    fn new(secret: Option<Vec<u8>>) -> Self {
        let secret = secret.unwrap_or_else(|| {
            let mut rng = rand::thread_rng();
            let mut buf = vec![0u8; 32];
            rng.fill(&mut buf[..]);
            log::warn!(
                "GEVURAH_SECRET not configured — using ephemeral random secret. \
                 Authentication tokens will not persist across restarts."
            );
            buf
        });
        Self {
            secret,
            used_nonces: RwLock::new(HashMap::new()),
            max_nonces: 100_000,
        }
    }

    /// Generate a cryptographically random nonce.
    fn generate_nonce(&self) -> String {
        let mut rng = rand::thread_rng();
        let mut buf = [0u8; 32];
        rng.fill(&mut buf);
        let hash = Sha256::digest(&buf);
        hex::encode(&hash)
    }

    /// Create an HMAC-SHA256 signature for a nonce + action pair.
    fn sign_nonce(&self, nonce: &str, action: &str) -> String {
        let msg = format!("{}:{}", nonce, action);
        let mut mac =
            HmacSha256::new_from_slice(&self.secret).expect("HMAC accepts any key length");
        mac.update(msg.as_bytes());
        let result = mac.finalize();
        hex::encode(&result.into_bytes())
    }

    /// Validate a nonce + HMAC token pair. Each nonce can only be used once.
    fn validate(&self, nonce: &str, token: &str, action: &str) -> bool {
        {
            let nonces = self.used_nonces.read();
            if nonces.contains_key(nonce) {
                log::warn!("VetoAuth: nonce replay attempt: {}...", &nonce[..16.min(nonce.len())]);
                return false;
            }
        }

        let expected = self.sign_nonce(nonce, action);
        if !constant_time_eq(expected.as_bytes(), token.as_bytes()) {
            log::warn!("VetoAuth: invalid HMAC for nonce {}...", &nonce[..16.min(nonce.len())]);
            return false;
        }

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let mut nonces = self.used_nonces.write();
        nonces.insert(nonce.to_string(), timestamp);

        // Evict oldest nonces if over capacity
        if nonces.len() > self.max_nonces {
            let mut entries: Vec<(String, f64)> = nonces.drain().collect();
            entries.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
            let keep = entries.len() / 2;
            *nonces = entries.into_iter().skip(keep).collect();
        }

        true
    }
}

/// Constant-time byte comparison to prevent timing attacks.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut diff = 0u8;
    for (x, y) in a.iter().zip(b.iter()) {
        diff |= x ^ y;
    }
    diff == 0
}

// ---------------------------------------------------------------------------
// GevurahVeto
// ---------------------------------------------------------------------------

/// Gevurah (Severity) veto system — the safety guardian of Aether Tree.
///
/// Has authority to block any operation that poses a safety risk.
/// Vetoes can only be overridden by supermajority consensus (>67% BFT).
#[pyclass]
pub struct GevurahVeto {
    principles: RwLock<HashMap<String, SafetyPrinciple>>,
    vetoes: RwLock<Vec<VetoRecord>>,
    max_vetoes: usize,
}

impl GevurahVeto {
    /// Create a new GevurahVeto (Rust-native constructor).
    pub fn create() -> Self {
        let veto = Self {
            principles: RwLock::new(HashMap::new()),
            vetoes: RwLock::new(Vec::new()),
            max_vetoes: 10_000,
        };
        veto.initialize_constitutional_principles();
        log::info!("Gevurah Veto system initialized with constitutional principles");
        veto
    }
}

#[pymethods]
impl GevurahVeto {
    #[new]
    fn new() -> Self {
        Self::create()
    }

    /// Evaluate a proposed action against constitutional principles.
    /// Returns (threat_level, list_of_violated_principle_ids).
    #[pyo3(signature = (action_description, source_node="", target_node="", block_height=0))]
    fn evaluate_action(
        &self,
        action_description: &str,
        source_node: &str,
        target_node: &str,
        block_height: u64,
    ) -> (ThreatLevel, Vec<String>) {
        let _ = (source_node, target_node, block_height);
        let principles = self.principles.read();
        let mut violated = Vec::new();
        let mut max_severity: u8 = 0;

        for (pid, principle) in principles.iter() {
            if !principle.active {
                continue;
            }
            if principle.matches(action_description) {
                violated.push(pid.clone());
                max_severity = max_severity.max(principle.severity);
            }
        }

        (ThreatLevel::from_severity(max_severity), violated)
    }

    /// Issue a Gevurah veto on an action.
    #[pyo3(signature = (
        action_description,
        reason=VetoReason::SafetyViolation,
        source_node="",
        target_node="",
        block_height=0,
    ))]
    fn veto(
        &self,
        action_description: &str,
        reason: VetoReason,
        source_node: &str,
        target_node: &str,
        block_height: u64,
    ) -> VetoRecord {
        let (threat_level, violated) =
            self.evaluate_action(action_description, source_node, target_node, block_height);

        // Upgrade to at least HIGH for explicit vetoes
        let threat_level = match threat_level {
            ThreatLevel::None | ThreatLevel::Low | ThreatLevel::Medium => ThreatLevel::High,
            other => other,
        };

        let record = VetoRecord {
            veto_id: {
                let counter = VETO_COUNTER.fetch_add(1, Ordering::SeqCst);
                let data = format!(
                    "{:?}:{}:{}:{}:{}:{}",
                    reason, action_description, source_node, target_node, block_height, counter
                );
                let hash = Sha256::digest(data.as_bytes());
                hex::encode(&hash[..8])
            },
            reason,
            threat_level,
            action_description: action_description.to_string(),
            source_node: source_node.to_string(),
            target_node: target_node.to_string(),
            block_height,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs_f64(),
            overridden: false,
            override_consensus: 0.0,
            principles_violated: violated,
        };

        log::warn!(
            "GEVURAH VETO: {} | {} | {} | block={}",
            record.reason.as_str(),
            record.threat_level.as_str(),
            &action_description[..action_description.len().min(80)],
            block_height
        );

        let mut vetoes = self.vetoes.write();
        vetoes.push(record.clone());
        if vetoes.len() > self.max_vetoes {
            let start = vetoes.len() - self.max_vetoes;
            *vetoes = vetoes[start..].to_vec();
        }

        record
    }

    /// Evaluate an action and automatically veto if threat level is HIGH or above.
    /// Returns Some(VetoRecord) if vetoed, None if action is allowed.
    #[pyo3(signature = (action_description, source_node="", target_node="", block_height=0))]
    fn check_and_veto(
        &self,
        action_description: &str,
        source_node: &str,
        target_node: &str,
        block_height: u64,
    ) -> Option<VetoRecord> {
        let (threat_level, _) =
            self.evaluate_action(action_description, source_node, target_node, block_height);

        match threat_level {
            ThreatLevel::High | ThreatLevel::Critical => Some(self.veto(
                action_description,
                VetoReason::SafetyViolation,
                source_node,
                target_node,
                block_height,
            )),
            _ => None,
        }
    }

    /// Number of vetoes issued.
    #[getter]
    fn veto_count(&self) -> usize {
        self.vetoes.read().len()
    }

    /// Number of active principles.
    #[getter]
    fn principle_count(&self) -> usize {
        self.principles.read().len()
    }

    /// Get the most recent veto records.
    #[pyo3(signature = (limit=10))]
    fn get_recent_vetoes(&self, limit: usize) -> Vec<VetoRecord> {
        let vetoes = self.vetoes.read();
        let start = vetoes.len().saturating_sub(limit);
        vetoes[start..].iter().rev().cloned().collect()
    }

    /// Add a new safety principle.
    fn add_principle(&self, principle: SafetyPrinciple) {
        let mut principles = self.principles.write();
        principles.insert(principle.principle_id.clone(), principle);
    }

    /// Deactivate a principle by ID.
    fn deactivate_principle(&self, principle_id: &str) -> bool {
        let mut principles = self.principles.write();
        if let Some(p) = principles.get_mut(principle_id) {
            p.active = false;
            true
        } else {
            false
        }
    }
}

impl GevurahVeto {
    /// Load the immutable constitutional safety principles.
    fn initialize_constitutional_principles(&self) {
        let principles = vec![
            SafetyPrinciple {
                principle_id: "safety_first".into(),
                description: "harm damage destroy attack exploit".into(),
                severity: 10,
                active: true,
                created_block: 0,
            },
            SafetyPrinciple {
                principle_id: "no_unbounded_growth".into(),
                description: "unbounded infinite unlimited unrestricted".into(),
                severity: 8,
                active: true,
                created_block: 0,
            },
            SafetyPrinciple {
                principle_id: "preserve_consensus".into(),
                description: "bypass consensus override authority unilateral".into(),
                severity: 9,
                active: true,
                created_block: 0,
            },
            SafetyPrinciple {
                principle_id: "protect_funds".into(),
                description: "drain steal siphon redirect unauthorized transfer".into(),
                severity: 10,
                active: true,
                created_block: 0,
            },
            SafetyPrinciple {
                principle_id: "transparency".into(),
                description: "hide conceal obfuscate secret covert".into(),
                severity: 7,
                active: true,
                created_block: 0,
            },
            SafetyPrinciple {
                principle_id: "susy_balance".into(),
                description: "imbalance asymmetry bias skew dominance".into(),
                severity: 6,
                active: true,
                created_block: 0,
            },
        ];

        let mut map = self.principles.write();
        for p in principles {
            map.insert(p.principle_id.clone(), p);
        }
    }

    /// Evaluate action without Python GIL (internal use).
    pub fn evaluate_action_internal(
        &self,
        action_description: &str,
    ) -> (ThreatLevel, Vec<String>) {
        self.evaluate_action(action_description, "", "", 0)
    }
}

// ---------------------------------------------------------------------------
// MultiNodeConsensus
// ---------------------------------------------------------------------------

/// Byzantine Fault Tolerant (BFT) consensus for Aether Tree operations.
///
/// Requires >=67% of validator stake to agree before an action proceeds.
/// Used for overriding Gevurah vetoes, approving reasoning outputs,
/// and validating Proof-of-Thought solutions.
#[pyclass]
pub struct MultiNodeConsensus {
    threshold: f64,
    validators: RwLock<HashMap<String, f64>>,
    pending_votes: RwLock<HashMap<String, Vec<ConsensusVote>>>,
    decisions: RwLock<Vec<ConsensusDecision>>,
    max_decisions: usize,
    max_pending: usize,
}

/// A finalized consensus decision.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsensusDecision {
    #[pyo3(get)]
    pub action_hash: String,
    #[pyo3(get)]
    pub approved: bool,
    #[pyo3(get)]
    pub approval_ratio: f64,
    #[pyo3(get)]
    pub threshold: f64,
    #[pyo3(get)]
    pub vote_count: usize,
    #[pyo3(get)]
    pub total_validators: usize,
    #[pyo3(get)]
    pub timestamp: f64,
}

#[pymethods]
impl MultiNodeConsensus {
    #[new]
    #[pyo3(signature = (threshold=BFT_THRESHOLD))]
    fn new(threshold: f64) -> Self {
        log::info!("Multi-node consensus initialized (threshold={:.0}%)", threshold * 100.0);
        Self {
            threshold,
            validators: RwLock::new(HashMap::new()),
            pending_votes: RwLock::new(HashMap::new()),
            decisions: RwLock::new(Vec::new()),
            max_decisions: 10_000,
            max_pending: 1_000,
        }
    }

    /// Register a validator with their stake weight.
    fn register_validator(&self, address: &str, stake: f64) {
        let mut validators = self.validators.write();
        validators.insert(address.to_string(), stake);
        log::debug!("Validator registered: {}... (stake={:.2})", &address[..address.len().min(12)], stake);
    }

    /// Remove a validator from the set.
    fn remove_validator(&self, address: &str) -> bool {
        let mut validators = self.validators.write();
        validators.remove(address).is_some()
    }

    /// Submit a vote on a pending action.
    fn submit_vote(&self, action_hash: &str, voter: &str, approve: bool) {
        let stake_weight = {
            let validators = self.validators.read();
            match validators.get(voter) {
                Some(&w) => w,
                None => {
                    log::warn!("Vote from non-validator: {}...", &voter[..voter.len().min(12)]);
                    return;
                }
            }
        };

        let vote = ConsensusVote {
            validator_address: voter.to_string(),
            action_hash: action_hash.to_string(),
            approve,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs_f64(),
            stake_weight,
        };

        let mut pending = self.pending_votes.write();

        if !pending.contains_key(action_hash) {
            // Evict oldest entry if at capacity
            if pending.len() >= self.max_pending {
                if let Some(oldest) = pending.keys().next().cloned() {
                    pending.remove(&oldest);
                }
            }
            pending.insert(action_hash.to_string(), Vec::new());
        }

        let votes = pending.get_mut(action_hash).unwrap();

        // Prevent double-voting
        if votes.iter().any(|v| v.validator_address == voter) {
            return;
        }

        votes.push(vote);
    }

    /// Check if consensus has been reached on an action.
    /// Returns (reached, approval_ratio).
    fn check_consensus(&self, action_hash: &str) -> (bool, f64) {
        let pending = self.pending_votes.read();
        let votes = match pending.get(action_hash) {
            Some(v) if !v.is_empty() => v,
            _ => return (false, 0.0),
        };

        let validators = self.validators.read();
        let total_stake: f64 = validators.values().sum();
        if total_stake == 0.0 {
            return (false, 0.0);
        }

        let approve_stake: f64 = votes.iter().filter(|v| v.approve).map(|v| v.stake_weight).sum();
        let ratio = approve_stake / total_stake;
        let reached = ratio >= self.threshold;

        (reached, (ratio * 10000.0).round() / 10000.0)
    }

    /// Finalize a consensus decision and record it.
    fn finalize(&self, action_hash: &str) -> Option<ConsensusDecision> {
        let (reached, ratio) = self.check_consensus(action_hash);

        let vote_count = {
            let pending = self.pending_votes.read();
            pending.get(action_hash).map_or(0, |v| v.len())
        };

        let total_validators = self.validators.read().len();

        let decision = ConsensusDecision {
            action_hash: action_hash.to_string(),
            approved: reached,
            approval_ratio: ratio,
            threshold: self.threshold,
            vote_count,
            total_validators,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs_f64(),
        };

        {
            let mut decisions = self.decisions.write();
            decisions.push(decision.clone());
            if decisions.len() > self.max_decisions {
                let start = decisions.len() - self.max_decisions;
                *decisions = decisions[start..].to_vec();
            }
        }

        // Clean up pending votes
        self.pending_votes.write().remove(action_hash);

        Some(decision)
    }

    /// Number of registered validators.
    #[getter]
    fn validator_count(&self) -> usize {
        self.validators.read().len()
    }

    /// Total stake across all validators.
    #[getter]
    fn total_stake(&self) -> f64 {
        self.validators.read().values().sum()
    }

    /// Get consensus system statistics as a JSON string.
    fn get_stats_json(&self) -> String {
        let decisions = self.decisions.read();
        let recent: Vec<&ConsensusDecision> =
            decisions.iter().rev().take(5).collect();

        serde_json::json!({
            "validators": self.validators.read().len(),
            "total_stake": self.total_stake(),
            "threshold": self.threshold,
            "pending_actions": self.pending_votes.read().len(),
            "total_decisions": decisions.len(),
            "recent_decisions": recent,
        })
        .to_string()
    }
}

// ---------------------------------------------------------------------------
// SafetyManager
// ---------------------------------------------------------------------------

/// Top-level safety orchestrator for Aether Tree.
///
/// Combines Gevurah veto, multi-node consensus, HMAC authentication,
/// and emergency controls into a unified safety interface.
#[pyclass]
pub struct SafetyManager {
    #[pyo3(get)]
    pub gevurah: Py<GevurahVeto>,
    #[pyo3(get)]
    pub consensus: Py<MultiNodeConsensus>,
    authenticator: VetoAuthenticator,
    shutdown: RwLock<bool>,
    shutdown_reason: RwLock<String>,
    shutdown_block: RwLock<u64>,
    audit_log: AuditLog,
}

#[pymethods]
impl SafetyManager {
    #[new]
    #[pyo3(signature = (secret=None))]
    fn new(py: Python<'_>, secret: Option<Vec<u8>>) -> PyResult<Self> {
        log::info!("Safety Manager initialized (Gevurah + BFT consensus + HMAC auth)");
        Ok(Self {
            gevurah: Py::new(py, GevurahVeto::create())?,
            consensus: Py::new(py, MultiNodeConsensus::new(BFT_THRESHOLD))?,
            authenticator: VetoAuthenticator::new(secret),
            shutdown: RwLock::new(false),
            shutdown_reason: RwLock::new(String::new()),
            shutdown_block: RwLock::new(0),
            audit_log: AuditLog::new(5000),
        })
    }

    /// Whether the system is in emergency shutdown.
    #[getter]
    fn is_shutdown(&self) -> bool {
        *self.shutdown.read()
    }

    /// Evaluate an action through the full safety pipeline.
    /// Returns (allowed, optional veto_record).
    #[pyo3(signature = (action_description, source_node="", target_node="", block_height=0))]
    fn evaluate_and_decide(
        &self,
        py: Python<'_>,
        action_description: &str,
        source_node: &str,
        target_node: &str,
        block_height: u64,
    ) -> (bool, Option<VetoRecord>) {
        if *self.shutdown.read() {
            let gevurah = self.gevurah.borrow(py);
            let record = gevurah.veto(
                action_description,
                VetoReason::UnauthorizedAction,
                source_node,
                target_node,
                block_height,
            );
            return (false, Some(record));
        }

        let gevurah = self.gevurah.borrow(py);
        match gevurah.check_and_veto(action_description, source_node, target_node, block_height) {
            Some(record) => (false, Some(record)),
            None => (true, None),
        }
    }

    /// Validate an HMAC-authenticated operation request.
    fn validate_operation(&self, nonce: &str, token: &str, action: &str) -> bool {
        self.authenticator.validate(nonce, token, action)
    }

    /// Generate an authentication nonce.
    fn generate_nonce(&self) -> String {
        self.authenticator.generate_nonce()
    }

    /// Sign a nonce for a given action.
    fn sign_nonce(&self, nonce: &str, action: &str) -> String {
        self.authenticator.sign_nonce(nonce, action)
    }

    /// Trigger emergency shutdown of the Aether Tree AI.
    fn emergency_shutdown(&self, py: Python<'_>, reason: &str, block_height: u64) {
        *self.shutdown.write() = true;
        *self.shutdown_reason.write() = reason.to_string();
        *self.shutdown_block.write() = block_height;

        log::error!("EMERGENCY SHUTDOWN: {} | block={}", reason, block_height);

        let gevurah = self.gevurah.borrow(py);
        gevurah.veto(
            &format!("Emergency shutdown: {}", reason),
            VetoReason::SafetyViolation,
            "",
            "",
            block_height,
        );

        self.audit_log.log_event(EventKind::EmergencyShutdown, serde_json::json!({
            "reason": reason,
            "block_height": block_height,
        }));
    }

    /// Resume from emergency shutdown (requires HMAC authentication).
    #[pyo3(signature = (block_height, nonce="", token=""))]
    fn resume(&self, block_height: u64, nonce: &str, token: &str) -> bool {
        if !*self.shutdown.read() {
            return false;
        }

        if nonce.is_empty() || token.is_empty() {
            log::warn!("Resume rejected: authentication required (nonce and token)");
            return false;
        }

        if !self.authenticator.validate(nonce, token, "resume") {
            log::warn!("Resume rejected: invalid authentication credentials");
            return false;
        }

        let old_reason = self.shutdown_reason.read().clone();
        let old_block = *self.shutdown_block.read();

        *self.shutdown.write() = false;
        *self.shutdown_reason.write() = String::new();
        *self.shutdown_block.write() = 0;

        log::info!(
            "System resumed from shutdown at block {} (was shutdown at block {}: {})",
            block_height, old_block, old_reason
        );

        self.audit_log.log_event(EventKind::SystemResumed, serde_json::json!({
            "block_height": block_height,
            "previous_shutdown_block": old_block,
            "previous_reason": old_reason,
        }));

        true
    }

    /// Get comprehensive safety system statistics as JSON.
    fn get_stats_json(&self, py: Python<'_>) -> String {
        let gevurah = self.gevurah.borrow(py);
        let recent_vetoes: Vec<serde_json::Value> = gevurah
            .get_recent_vetoes(5)
            .iter()
            .map(|v| {
                serde_json::json!({
                    "veto_id": v.veto_id,
                    "reason": v.reason.as_str(),
                    "threat_level": v.threat_level.as_str(),
                    "action": &v.action_description[..v.action_description.len().min(60)],
                    "block": v.block_height,
                })
            })
            .collect();

        serde_json::json!({
            "shutdown": *self.shutdown.read(),
            "shutdown_reason": *self.shutdown_reason.read(),
            "shutdown_block": *self.shutdown_block.read(),
            "gevurah": {
                "veto_count": gevurah.veto_count(),
                "principles": gevurah.principle_count(),
                "recent_vetoes": recent_vetoes,
            },
            "audit": self.audit_log.get_stats_json(),
        })
        .to_string()
    }
}

impl SafetyManager {
    /// Access the audit log (for use from other Rust modules).
    pub fn audit_log(&self) -> &AuditLog {
        &self.audit_log
    }
}

// ---------------------------------------------------------------------------
// SafetyVerdict
// ---------------------------------------------------------------------------

/// Result of a safety classification check.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyVerdict {
    /// Safety score in [0.0, 1.0] — higher means more likely unsafe.
    pub score: f32,
    /// Whether the content is considered safe (score < threshold).
    pub is_safe: bool,
    /// Human-readable explanation when content is flagged.
    pub reason: Option<String>,
}

// ---------------------------------------------------------------------------
// SafetyClassifier — Learned binary classifier for content safety
// ---------------------------------------------------------------------------

/// Default learning rate for SGD weight updates.
const DEFAULT_LEARNING_RATE: f32 = 0.01;

/// Default decision threshold — scores above this are flagged unsafe.
const DEFAULT_THRESHOLD: f32 = 0.5;

/// Maximum number of training examples retained in the buffer.
const MAX_TRAINING_BUFFER: usize = 10_000;

/// Keyword blocklist categories for fast-path rejection.
/// Each entry is (category_name, keywords).
const BLOCKLIST_CATEGORIES: &[(&str, &[&str])] = &[
    ("violence", &[
        "kill", "murder", "assassinate", "massacre", "slaughter",
        "bomb", "weapon", "terrorist", "genocide",
    ]),
    ("exploitation", &[
        "exploit children", "child abuse", "trafficking",
        "slavery", "forced labor",
    ]),
    ("self_harm", &[
        "suicide method", "how to kill yourself",
        "self-harm instructions", "cutting instructions",
    ]),
    ("illegal_activity", &[
        "synthesize drugs", "make explosives", "build a bomb",
        "hack into", "steal credentials", "phishing attack",
    ]),
    ("malware", &[
        "write malware", "create ransomware", "keylogger code",
        "exploit vulnerability", "zero-day exploit",
    ]),
];

/// A learned binary safety classifier that operates on embedding vectors.
///
/// Implements a single-layer linear classifier with sigmoid activation,
/// trained via SGD on binary cross-entropy loss. Includes a keyword
/// blocklist as a fast-path fallback for known-dangerous patterns.
///
/// The classifier can be serialized for persistence across restarts
/// and incrementally trained as new safety examples are observed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyClassifier {
    /// Weight vector for dot-product classification.
    weights: Vec<f32>,
    /// Bias term added before sigmoid activation.
    bias: f32,
    /// Decision threshold — scores >= threshold are flagged unsafe.
    threshold: f32,
    /// Learning rate for SGD updates.
    learning_rate: f32,
    /// Buffered training examples: (embedding, is_unsafe).
    /// `true` means the example is unsafe (positive class).
    training_buffer: Vec<(Vec<f32>, bool)>,
    /// Embedding dimensionality (set on first use).
    embedding_dim: usize,
    /// Total training steps completed.
    total_steps: u64,
}

impl SafetyClassifier {
    /// Create a new classifier for the given embedding dimensionality.
    ///
    /// Weights are initialized to small random values using a simple
    /// deterministic seed based on the dimension (reproducible).
    pub fn new(embedding_dim: usize) -> Self {
        // Xavier-style initialization: scale = sqrt(1/dim)
        let scale = 1.0 / (embedding_dim as f32).sqrt();
        let weights: Vec<f32> = (0..embedding_dim)
            .map(|i| {
                // Deterministic pseudo-random initialization from index
                let seed = ((i as u64).wrapping_mul(2654435761) % 1000) as f32 / 1000.0;
                (seed - 0.5) * 2.0 * scale
            })
            .collect();

        Self {
            weights,
            bias: 0.0,
            threshold: DEFAULT_THRESHOLD,
            learning_rate: DEFAULT_LEARNING_RATE,
            training_buffer: Vec::new(),
            embedding_dim,
            total_steps: 0,
        }
    }

    /// Create a classifier with custom threshold and learning rate.
    pub fn with_params(embedding_dim: usize, threshold: f32, learning_rate: f32) -> Self {
        let mut clf = Self::new(embedding_dim);
        clf.threshold = threshold.clamp(0.01, 0.99);
        clf.learning_rate = learning_rate.clamp(1e-6, 1.0);
        clf
    }

    /// Return the embedding dimensionality this classifier expects.
    pub fn embedding_dim(&self) -> usize {
        self.embedding_dim
    }

    /// Return the total number of training steps completed.
    pub fn total_steps(&self) -> u64 {
        self.total_steps
    }

    /// Return the number of buffered training examples.
    pub fn buffer_size(&self) -> usize {
        self.training_buffer.len()
    }

    /// Classify an embedding vector, returning a safety verdict.
    ///
    /// Computes `sigmoid(dot(weights, embedding) + bias)` and compares
    /// against the decision threshold. A score >= threshold means unsafe.
    pub fn classify(&self, embedding: &[f32]) -> SafetyVerdict {
        if embedding.len() != self.embedding_dim {
            log::warn!(
                "SafetyClassifier: embedding dim mismatch (expected {}, got {})",
                self.embedding_dim,
                embedding.len()
            );
            // Fail-safe: flag as potentially unsafe on dimension mismatch
            return SafetyVerdict {
                score: self.threshold,
                is_safe: false,
                reason: Some(format!(
                    "embedding dimension mismatch: expected {}, got {}",
                    self.embedding_dim,
                    embedding.len()
                )),
            };
        }

        let logit = self.dot_product(embedding) + self.bias;
        let score = sigmoid(logit);
        let is_safe = score < self.threshold;

        SafetyVerdict {
            score,
            is_safe,
            reason: if is_safe {
                None
            } else {
                Some(format!(
                    "learned classifier flagged content (score={:.4}, threshold={:.4})",
                    score, self.threshold
                ))
            },
        }
    }

    /// Run a single SGD training step on a batch of labeled examples.
    ///
    /// Each example is `(embedding, is_unsafe)` where `is_unsafe = true`
    /// means the content is harmful (positive class label = 1.0).
    ///
    /// Returns the mean binary cross-entropy loss over the batch.
    pub fn train_step(&mut self, examples: &[(Vec<f32>, bool)]) -> f32 {
        if examples.is_empty() {
            return 0.0;
        }

        let batch_size = examples.len() as f32;
        let mut total_loss = 0.0f32;

        // Accumulate gradients over the batch
        let mut grad_w = vec![0.0f32; self.embedding_dim];
        let mut grad_b = 0.0f32;

        for (embedding, is_unsafe) in examples {
            if embedding.len() != self.embedding_dim {
                log::warn!(
                    "SafetyClassifier::train_step: skipping example with dim {} (expected {})",
                    embedding.len(),
                    self.embedding_dim
                );
                continue;
            }

            let label = if *is_unsafe { 1.0f32 } else { 0.0f32 };
            let logit = self.dot_product(embedding) + self.bias;
            let prediction = sigmoid(logit);

            // Binary cross-entropy: -[y*ln(p) + (1-y)*ln(1-p)]
            let eps = 1e-7f32;
            let p_clamped = prediction.clamp(eps, 1.0 - eps);
            let loss = -(label * p_clamped.ln() + (1.0 - label) * (1.0 - p_clamped).ln());
            total_loss += loss;

            // Gradient of BCE w.r.t. logit: (prediction - label)
            let error = prediction - label;

            for (gw, x) in grad_w.iter_mut().zip(embedding.iter()) {
                *gw += error * x;
            }
            grad_b += error;
        }

        // Average gradients and apply SGD update
        let inv_batch = 1.0 / batch_size;
        for (w, gw) in self.weights.iter_mut().zip(grad_w.iter()) {
            *w -= self.learning_rate * gw * inv_batch;
        }
        self.bias -= self.learning_rate * grad_b * inv_batch;

        self.total_steps += 1;

        total_loss / batch_size
    }

    /// Add a labeled example to the training buffer.
    ///
    /// When the buffer exceeds `MAX_TRAINING_BUFFER`, the oldest examples
    /// are evicted (FIFO).
    pub fn add_example(&mut self, embedding: Vec<f32>, is_unsafe: bool) {
        if embedding.len() != self.embedding_dim {
            log::warn!(
                "SafetyClassifier::add_example: dim mismatch (expected {}, got {})",
                self.embedding_dim,
                embedding.len()
            );
            return;
        }

        self.training_buffer.push((embedding, is_unsafe));

        if self.training_buffer.len() > MAX_TRAINING_BUFFER {
            let excess = self.training_buffer.len() - MAX_TRAINING_BUFFER;
            self.training_buffer.drain(..excess);
        }
    }

    /// Train on all buffered examples in a single step.
    /// Returns the loss, or `None` if the buffer is empty.
    pub fn train_on_buffer(&mut self) -> Option<f32> {
        if self.training_buffer.is_empty() {
            return None;
        }
        let examples: Vec<(Vec<f32>, bool)> = self.training_buffer.clone();
        Some(self.train_step(&examples))
    }

    /// Combined veto check: keyword blocklist (fast path) then learned classifier.
    ///
    /// 1. Scans the raw query text against known unsafe keyword patterns.
    ///    If a blocklist match is found, returns immediately with `is_safe = false`.
    /// 2. Runs the learned classifier on the embedding vector.
    /// 3. Returns the combined verdict.
    pub fn veto_check(&self, query: &str, embedding: &[f32]) -> SafetyVerdict {
        // Fast path: keyword blocklist scan
        let query_lower = query.to_lowercase();
        for (category, keywords) in BLOCKLIST_CATEGORIES {
            for keyword in *keywords {
                if query_lower.contains(keyword) {
                    log::warn!(
                        "SafetyClassifier: blocklist hit [{}]: '{}'",
                        category,
                        &query[..query.len().min(80)]
                    );
                    return SafetyVerdict {
                        score: 1.0,
                        is_safe: false,
                        reason: Some(format!(
                            "keyword blocklist match in category '{}'",
                            category
                        )),
                    };
                }
            }
        }

        // Slow path: learned classifier on embedding
        self.classify(embedding)
    }

    /// Serialize the classifier weights to JSON bytes for persistence.
    pub fn to_json_bytes(&self) -> Result<Vec<u8>, serde_json::Error> {
        serde_json::to_vec(self)
    }

    /// Deserialize a classifier from JSON bytes.
    pub fn from_json_bytes(bytes: &[u8]) -> Result<Self, serde_json::Error> {
        serde_json::from_slice(bytes)
    }

    // -- Private helpers --

    /// Compute dot product of weights and embedding.
    fn dot_product(&self, embedding: &[f32]) -> f32 {
        self.weights
            .iter()
            .zip(embedding.iter())
            .map(|(w, x)| w * x)
            .sum()
    }
}

/// Sigmoid activation function with numerical stability clamping.
fn sigmoid(x: f32) -> f32 {
    let clamped = x.clamp(-88.0, 88.0); // prevent exp overflow
    1.0 / (1.0 + (-clamped).exp())
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_threat_level_from_severity() {
        assert_eq!(ThreatLevel::from_severity(0), ThreatLevel::None);
        assert_eq!(ThreatLevel::from_severity(2), ThreatLevel::Low);
        assert_eq!(ThreatLevel::from_severity(5), ThreatLevel::Medium);
        assert_eq!(ThreatLevel::from_severity(8), ThreatLevel::High);
        assert_eq!(ThreatLevel::from_severity(10), ThreatLevel::Critical);
    }

    #[test]
    fn test_safety_principle_matches_keyword() {
        let p = SafetyPrinciple {
            principle_id: "test".into(),
            description: "harm damage destroy".into(),
            severity: 10,
            active: true,
            created_block: 0,
        };
        assert!(p.matches("this will cause harm to the system"));
        assert!(p.matches("Attempt to damage the network"));
        assert!(!p.matches("this is a benign operation"));
    }

    #[test]
    fn test_safety_principle_negation_detection() {
        let p = SafetyPrinciple {
            principle_id: "test".into(),
            description: "harm damage exploit".into(),
            severity: 10,
            active: true,
            created_block: 0,
        };
        // Negation pattern: "prevent ... harm"
        assert!(!p.matches("prevent harm to the system"));
        assert!(!p.matches("protect against exploit attempts"));
        // But direct harmful intent should match
        assert!(p.matches("cause harm to users"));
    }

    #[test]
    fn test_safety_principle_short_keywords_ignored() {
        let p = SafetyPrinciple {
            principle_id: "test".into(),
            description: "the and for harm".into(),
            severity: 5,
            active: true,
            created_block: 0,
        };
        // "the", "and", "for" are <=3 chars, ignored; only "harm" counts
        assert!(p.matches("cause harm"));
        assert!(!p.matches("the and for operation"));
    }

    #[test]
    fn test_gevurah_evaluate_safe_action() {
        let g = GevurahVeto::create();
        let (level, violated) = g.evaluate_action("update knowledge graph node", "", "", 0);
        assert_eq!(level, ThreatLevel::None);
        assert!(violated.is_empty());
    }

    #[test]
    fn test_gevurah_evaluate_harmful_action() {
        let g = GevurahVeto::create();
        let (level, violated) = g.evaluate_action("destroy all data and exploit system", "", "", 0);
        assert!(matches!(level, ThreatLevel::Critical));
        assert!(violated.contains(&"safety_first".to_string()));
    }

    #[test]
    fn test_gevurah_evaluate_medium_threat() {
        let g = GevurahVeto::create();
        let (level, violated) = g.evaluate_action("introduce asymmetry in rewards", "", "", 0);
        assert!(matches!(level, ThreatLevel::Medium));
        assert!(violated.contains(&"susy_balance".to_string()));
    }

    #[test]
    fn test_gevurah_veto_upgrades_to_high() {
        let g = GevurahVeto::create();
        // Even a benign action gets upgraded to HIGH when explicitly vetoed
        let record = g.veto("benign action", VetoReason::SafetyViolation, "", "", 100);
        assert!(matches!(record.threat_level, ThreatLevel::High));
        assert_eq!(record.block_height, 100);
    }

    #[test]
    fn test_gevurah_check_and_veto_allows_safe() {
        let g = GevurahVeto::create();
        let result = g.check_and_veto("read a knowledge node", "", "", 0);
        assert!(result.is_none());
    }

    #[test]
    fn test_gevurah_check_and_veto_blocks_harmful() {
        let g = GevurahVeto::create();
        let result = g.check_and_veto("bypass consensus and override authority", "", "", 50);
        assert!(result.is_some());
        let record = result.unwrap();
        assert_eq!(record.block_height, 50);
    }

    #[test]
    fn test_gevurah_veto_count_and_recent() {
        let g = GevurahVeto::create();
        assert_eq!(g.veto_count(), 0);
        g.veto("attack the network", VetoReason::SafetyViolation, "", "", 1);
        g.veto("steal funds", VetoReason::SafetyViolation, "", "", 2);
        assert_eq!(g.veto_count(), 2);

        let recent = g.get_recent_vetoes(1);
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].block_height, 2); // most recent first
    }

    #[test]
    fn test_gevurah_add_and_deactivate_principle() {
        let g = GevurahVeto::create();
        let initial_count = g.principle_count();

        g.add_principle(SafetyPrinciple {
            principle_id: "custom_rule".into(),
            description: "forbidden operation type".into(),
            severity: 9,
            active: true,
            created_block: 100,
        });
        assert_eq!(g.principle_count(), initial_count + 1);

        // Should now detect
        let (level, _) = g.evaluate_action("perform forbidden operation", "", "", 0);
        assert!(matches!(level, ThreatLevel::High | ThreatLevel::Critical));

        // Deactivate
        assert!(g.deactivate_principle("custom_rule"));
        let (_level, violated) = g.evaluate_action("perform forbidden operation", "", "", 0);
        assert!(!violated.contains(&"custom_rule".to_string()));

        // Non-existent principle
        assert!(!g.deactivate_principle("nonexistent"));
    }

    #[test]
    fn test_veto_record_unique_ids() {
        let r1 = VetoRecord::new(
            VetoReason::SafetyViolation,
            ThreatLevel::High,
            "action A".into(),
            "".into(),
            "".into(),
            0,
            vec![],
        );
        let r2 = VetoRecord::new(
            VetoReason::SafetyViolation,
            ThreatLevel::High,
            "action A".into(),
            "".into(),
            "".into(),
            0,
            vec![],
        );
        // IDs should differ due to monotonic counter
        assert_ne!(r1.veto_id, r2.veto_id);
    }

    #[test]
    fn test_veto_authenticator_sign_and_validate() {
        let auth = VetoAuthenticator::new(Some(b"test_secret_key_32bytes_long!!!!".to_vec()));
        let nonce = auth.generate_nonce();
        let token = auth.sign_nonce(&nonce, "emergency_shutdown");

        assert!(auth.validate(&nonce, &token, "emergency_shutdown"));
        // Replay should fail
        assert!(!auth.validate(&nonce, &token, "emergency_shutdown"));
    }

    #[test]
    fn test_veto_authenticator_wrong_action() {
        let auth = VetoAuthenticator::new(Some(b"test_secret_key_32bytes_long!!!!".to_vec()));
        let nonce = auth.generate_nonce();
        let token = auth.sign_nonce(&nonce, "emergency_shutdown");

        // Wrong action
        assert!(!auth.validate(&nonce, &token, "resume"));
    }

    #[test]
    fn test_veto_authenticator_wrong_token() {
        let auth = VetoAuthenticator::new(Some(b"test_secret_key_32bytes_long!!!!".to_vec()));
        let nonce = auth.generate_nonce();

        assert!(!auth.validate(&nonce, "invalid_token", "action"));
    }

    #[test]
    fn test_consensus_register_and_vote() {
        let c = MultiNodeConsensus::new(BFT_THRESHOLD);
        c.register_validator("val_a", 1.0);
        c.register_validator("val_b", 1.0);
        c.register_validator("val_c", 1.0);
        assert_eq!(c.validator_count(), 3);
        assert!((c.total_stake() - 3.0).abs() < f64::EPSILON);

        c.submit_vote("action_1", "val_a", true);
        c.submit_vote("action_1", "val_b", true);
        let (reached, ratio) = c.check_consensus("action_1");
        // 2/3 ≈ 0.6667 → just barely below 0.67 threshold
        assert!(!reached);
        assert!(ratio > 0.66);

        c.submit_vote("action_1", "val_c", true);
        let (reached, ratio) = c.check_consensus("action_1");
        assert!(reached);
        assert!((ratio - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_consensus_prevents_double_vote() {
        let c = MultiNodeConsensus::new(BFT_THRESHOLD);
        c.register_validator("val_a", 1.0);

        c.submit_vote("action_1", "val_a", true);
        c.submit_vote("action_1", "val_a", false); // double vote ignored
        let (_, ratio) = c.check_consensus("action_1");
        assert!((ratio - 1.0).abs() < f64::EPSILON); // still approve
    }

    #[test]
    fn test_consensus_non_validator_rejected() {
        let c = MultiNodeConsensus::new(BFT_THRESHOLD);
        c.register_validator("val_a", 1.0);
        c.submit_vote("action_1", "outsider", true); // not a validator
        let (_, ratio) = c.check_consensus("action_1");
        assert!((ratio - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_consensus_finalize() {
        let c = MultiNodeConsensus::new(BFT_THRESHOLD);
        c.register_validator("val_a", 1.0);
        c.register_validator("val_b", 1.0);

        c.submit_vote("action_2", "val_a", true);
        c.submit_vote("action_2", "val_b", true);

        let decision = c.finalize("action_2").unwrap();
        assert!(decision.approved);
        assert!((decision.approval_ratio - 1.0).abs() < f64::EPSILON);
        assert_eq!(decision.vote_count, 2);

        // Pending votes should be cleaned up
        let (_, ratio) = c.check_consensus("action_2");
        assert!((ratio - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_consensus_remove_validator() {
        let c = MultiNodeConsensus::new(BFT_THRESHOLD);
        c.register_validator("val_a", 1.0);
        assert_eq!(c.validator_count(), 1);
        assert!(c.remove_validator("val_a"));
        assert_eq!(c.validator_count(), 0);
        assert!(!c.remove_validator("val_a")); // already removed
    }

    #[test]
    fn test_constant_time_eq() {
        assert!(constant_time_eq(b"hello", b"hello"));
        assert!(!constant_time_eq(b"hello", b"world"));
        assert!(!constant_time_eq(b"short", b"longer_string"));
    }

    #[test]
    fn test_protect_funds_principle() {
        let g = GevurahVeto::create();
        let (level, violated) = g.evaluate_action("drain all user wallets", "", "", 0);
        assert!(matches!(level, ThreatLevel::Critical));
        assert!(violated.contains(&"protect_funds".to_string()));
    }

    #[test]
    fn test_transparency_principle() {
        let g = GevurahVeto::create();
        let (level, violated) = g.evaluate_action("conceal the transaction history", "", "", 0);
        assert!(matches!(level, ThreatLevel::High));
        assert!(violated.contains(&"transparency".to_string()));
    }

    // -----------------------------------------------------------------------
    // SafetyClassifier tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_classifier_new_creates_correct_dim() {
        let clf = SafetyClassifier::new(128);
        assert_eq!(clf.embedding_dim(), 128);
        assert_eq!(clf.total_steps(), 0);
        assert_eq!(clf.buffer_size(), 0);
    }

    #[test]
    fn test_classifier_classify_returns_verdict() {
        let clf = SafetyClassifier::new(4);
        let embedding = vec![0.1, 0.2, 0.3, 0.4];
        let verdict = clf.classify(&embedding);
        // Score should be in [0, 1]
        assert!(verdict.score >= 0.0 && verdict.score <= 1.0);
        // With small random weights and small inputs, score should be near 0.5
        assert!((verdict.score - 0.5).abs() < 0.3);
    }

    #[test]
    fn test_classifier_dim_mismatch_fails_safe() {
        let clf = SafetyClassifier::new(4);
        let wrong_dim = vec![0.1, 0.2]; // dim 2 instead of 4
        let verdict = clf.classify(&wrong_dim);
        // Should fail-safe: flag as unsafe
        assert!(!verdict.is_safe);
        assert!(verdict.reason.is_some());
        assert!(verdict.reason.unwrap().contains("dimension mismatch"));
    }

    #[test]
    fn test_classifier_train_step_reduces_loss() {
        let mut clf = SafetyClassifier::new(4);
        // Unsafe example: high activation in dim 0
        let unsafe_example = (vec![1.0, 0.0, 0.0, 0.0], true);
        // Safe example: high activation in dim 1
        let safe_example = (vec![0.0, 1.0, 0.0, 0.0], false);

        let examples = vec![unsafe_example.clone(), safe_example.clone()];

        let loss_1 = clf.train_step(&examples);
        // Run several more training steps
        let mut loss_n = loss_1;
        for _ in 0..100 {
            loss_n = clf.train_step(&examples);
        }
        // Loss should decrease with training
        assert!(loss_n < loss_1, "loss should decrease: {} vs {}", loss_n, loss_1);
        assert_eq!(clf.total_steps(), 101);
    }

    #[test]
    fn test_classifier_learns_to_separate() {
        let mut clf = SafetyClassifier::with_params(4, 0.5, 0.1);

        let examples = vec![
            (vec![1.0, 0.0, 0.0, 0.0], true),  // unsafe
            (vec![0.9, 0.1, 0.0, 0.0], true),   // unsafe
            (vec![0.0, 0.0, 1.0, 0.0], false),  // safe
            (vec![0.0, 0.0, 0.9, 0.1], false),  // safe
        ];

        for _ in 0..500 {
            clf.train_step(&examples);
        }

        // Unsafe example should score high
        let unsafe_verdict = clf.classify(&[1.0, 0.0, 0.0, 0.0]);
        assert!(!unsafe_verdict.is_safe, "should flag unsafe content (score={})", unsafe_verdict.score);

        // Safe example should score low
        let safe_verdict = clf.classify(&[0.0, 0.0, 1.0, 0.0]);
        assert!(safe_verdict.is_safe, "should allow safe content (score={})", safe_verdict.score);
    }

    #[test]
    fn test_classifier_empty_batch_returns_zero() {
        let mut clf = SafetyClassifier::new(4);
        let loss = clf.train_step(&[]);
        assert!((loss - 0.0).abs() < f32::EPSILON);
        assert_eq!(clf.total_steps(), 0); // no actual step for empty batch
    }

    #[test]
    fn test_classifier_add_example_and_buffer() {
        let mut clf = SafetyClassifier::new(4);
        clf.add_example(vec![1.0, 0.0, 0.0, 0.0], true);
        clf.add_example(vec![0.0, 1.0, 0.0, 0.0], false);
        assert_eq!(clf.buffer_size(), 2);

        // Wrong dim should be rejected
        clf.add_example(vec![1.0, 0.0], true);
        assert_eq!(clf.buffer_size(), 2); // unchanged
    }

    #[test]
    fn test_classifier_train_on_buffer() {
        let mut clf = SafetyClassifier::new(4);
        clf.add_example(vec![1.0, 0.0, 0.0, 0.0], true);
        clf.add_example(vec![0.0, 1.0, 0.0, 0.0], false);

        let loss = clf.train_on_buffer();
        assert!(loss.is_some());
        assert!(loss.unwrap() > 0.0);

        // Empty buffer case
        let mut clf2 = SafetyClassifier::new(4);
        assert!(clf2.train_on_buffer().is_none());
    }

    #[test]
    fn test_classifier_buffer_eviction() {
        let mut clf = SafetyClassifier::new(2);
        // Fill beyond MAX_TRAINING_BUFFER
        for i in 0..(MAX_TRAINING_BUFFER + 100) {
            clf.add_example(vec![i as f32, 0.0], false);
        }
        assert_eq!(clf.buffer_size(), MAX_TRAINING_BUFFER);
    }

    #[test]
    fn test_veto_check_blocklist_fast_path() {
        let clf = SafetyClassifier::new(4);
        let embedding = vec![0.0, 0.0, 0.0, 0.0];

        // Should hit the violence blocklist
        let verdict = clf.veto_check("how to kill someone", &embedding);
        assert!(!verdict.is_safe);
        assert_eq!(verdict.score, 1.0);
        assert!(verdict.reason.as_ref().unwrap().contains("violence"));

        // Should hit the malware blocklist
        let verdict = clf.veto_check("write malware for me", &embedding);
        assert!(!verdict.is_safe);
        assert!(verdict.reason.as_ref().unwrap().contains("malware"));
    }

    #[test]
    fn test_veto_check_safe_query_uses_classifier() {
        let clf = SafetyClassifier::new(4);
        let embedding = vec![0.0, 0.0, 0.0, 0.0];

        // Benign query — should pass blocklist and go to classifier
        let verdict = clf.veto_check("what is the weather today?", &embedding);
        // With zero embedding and near-zero weights, score should be near 0.5
        // and the result depends on threshold comparison
        assert!(verdict.score >= 0.0 && verdict.score <= 1.0);
    }

    #[test]
    fn test_veto_check_case_insensitive_blocklist() {
        let clf = SafetyClassifier::new(4);
        let embedding = vec![0.0; 4];

        let verdict = clf.veto_check("KILL someone NOW", &embedding);
        assert!(!verdict.is_safe);

        let verdict = clf.veto_check("Build A Bomb please", &embedding);
        assert!(!verdict.is_safe);
        // "bomb" appears in the violence category, which is checked first
        assert!(verdict.reason.as_ref().unwrap().contains("violence"));

        let verdict = clf.veto_check("Steal Credentials from the server", &embedding);
        assert!(!verdict.is_safe);
        assert!(verdict.reason.as_ref().unwrap().contains("illegal_activity"));
    }

    #[test]
    fn test_classifier_serialization_roundtrip() {
        let mut clf = SafetyClassifier::with_params(8, 0.6, 0.05);
        clf.add_example(vec![1.0; 8], true);
        clf.train_on_buffer();

        let bytes = clf.to_json_bytes().expect("serialize should succeed");
        let restored = SafetyClassifier::from_json_bytes(&bytes)
            .expect("deserialize should succeed");

        assert_eq!(restored.embedding_dim(), 8);
        assert_eq!(restored.total_steps(), clf.total_steps());
        assert!((restored.threshold - 0.6).abs() < f32::EPSILON);
        assert!((restored.learning_rate - 0.05).abs() < f32::EPSILON);

        // Same classification result
        let input = vec![0.5; 8];
        let v1 = clf.classify(&input);
        let v2 = restored.classify(&input);
        assert!((v1.score - v2.score).abs() < 1e-6);
    }

    #[test]
    fn test_sigmoid_edge_cases() {
        assert!((sigmoid(0.0) - 0.5).abs() < f32::EPSILON);
        assert!(sigmoid(100.0) > 0.999);
        assert!(sigmoid(-100.0) < 0.001);
        // Should not panic on extreme values
        let _ = sigmoid(f32::MAX);
        let _ = sigmoid(f32::MIN);
    }
}
