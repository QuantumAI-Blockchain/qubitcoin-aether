//! Proof-of-Thought Task Protocol — reasoning task marketplace.
//!
//! Implements the economic protocol for Proof-of-Thought consensus:
//!   1. Task Submission: User/system submits reasoning task with QBC bounty.
//!   2. Node Solution: Sephirah node uses reasoning engine to solve.
//!   3. Proposal: Node submits solution + proof hash.
//!   4. Validation: Multiple validators verify via consensus.
//!   5. Reward/Slash: Correct solutions earn QBC bounty; incorrect lose stake.
//!
//! Ported from: `task_protocol.py` (TaskMarket, ValidatorRegistry,
//!              ProofOfThoughtProtocol).

use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

// ---------------------------------------------------------------------------
// Protocol constants
// ---------------------------------------------------------------------------

/// Minimum task bounty in QBC.
pub const MIN_TASK_BOUNTY: f64 = 1.0;

/// Minimum validator stake in QBC.
pub const MIN_VALIDATOR_STAKE: f64 = 100.0;

/// Slash penalty (fraction of stake).
pub const SLASH_PENALTY: f64 = 0.50;

/// BFT validation threshold (67%).
pub const VALIDATION_THRESHOLD: f64 = 0.67;

/// Unstaking delay in blocks (~7 days at 3.3s/block).
pub const UNSTAKING_DELAY_BLOCKS: u64 = 183272;

/// Maximum number of tasks in the market.
pub const MAX_TASKS: usize = 10000;

/// Default max vote weight per validator (33% cap).
pub const DEFAULT_MAX_VOTE_WEIGHT: f64 = 0.33;

// ---------------------------------------------------------------------------
// Task status
// ---------------------------------------------------------------------------

/// Lifecycle status of a reasoning task.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    /// Awaiting solutions.
    Open,
    /// A node is working on it.
    Claimed,
    /// Solution submitted, awaiting validation.
    Proposed,
    /// Validators are voting.
    Validating,
    /// Solution accepted, reward distributed.
    Completed,
    /// Solution rejected, solver slashed.
    Rejected,
    /// No valid solution within timeout.
    Expired,
}

impl std::fmt::Display for TaskStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TaskStatus::Open => write!(f, "open"),
            TaskStatus::Claimed => write!(f, "claimed"),
            TaskStatus::Proposed => write!(f, "proposed"),
            TaskStatus::Validating => write!(f, "validating"),
            TaskStatus::Completed => write!(f, "completed"),
            TaskStatus::Rejected => write!(f, "rejected"),
            TaskStatus::Expired => write!(f, "expired"),
        }
    }
}

// ---------------------------------------------------------------------------
// Reasoning task
// ---------------------------------------------------------------------------

/// A reasoning task in the Proof-of-Thought marketplace.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReasoningTask {
    /// Unique task identifier (SHA-256 derived).
    pub task_id: String,
    /// Address of the task submitter.
    pub submitter: String,
    /// Human-readable task description.
    pub description: String,
    /// Query type: general, deductive, inductive, abductive.
    pub query_type: String,
    /// Bounty in QBC.
    pub bounty_qbc: f64,
    /// Current lifecycle status.
    pub status: TaskStatus,
    /// Block height when the task was created.
    pub created_block: u64,
    /// Number of blocks before the task expires.
    pub timeout_blocks: u64,
    /// Address of the solver who claimed the task.
    pub claimed_by: String,
    /// SHA-256 hash of the solution.
    pub solution_hash: String,
    /// Solution data (key-value pairs).
    pub solution_data: HashMap<String, String>,
    /// Validation votes: validator_address -> approve.
    pub validation_votes: HashMap<String, bool>,
    /// Whether the reward has been distributed.
    pub reward_distributed: bool,
    /// Unix timestamp of creation.
    pub timestamp: f64,
}

impl ReasoningTask {
    /// Create a new reasoning task with an auto-generated ID.
    pub fn new(
        submitter: &str,
        description: &str,
        query_type: &str,
        bounty_qbc: f64,
        created_block: u64,
        timeout_blocks: u64,
    ) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let mut hasher = Sha256::new();
        hasher.update(format!("{}:{}:{}", submitter, description, now).as_bytes());
        let task_id = format!("{:x}", hasher.finalize());
        let task_id = task_id[..16].to_string();

        Self {
            task_id,
            submitter: submitter.to_string(),
            description: description.to_string(),
            query_type: query_type.to_string(),
            bounty_qbc,
            status: TaskStatus::Open,
            created_block,
            timeout_blocks,
            claimed_by: String::new(),
            solution_hash: String::new(),
            solution_data: HashMap::new(),
            validation_votes: HashMap::new(),
            reward_distributed: false,
            timestamp: now,
        }
    }
}

// ---------------------------------------------------------------------------
// Validator
// ---------------------------------------------------------------------------

/// A registered Proof-of-Thought validator.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Validator {
    /// Validator's address.
    pub address: String,
    /// Current staked amount in QBC.
    pub stake_qbc: f64,
    /// Block height when first staked.
    pub staked_block: u64,
    /// Block height when unstaking completes (0 = not unstaking).
    pub unstaking_block: u64,
    /// Whether the validator is currently active.
    pub is_active: bool,
    /// Total tasks validated.
    pub tasks_validated: u64,
    /// Number of correct validations.
    pub correct_validations: u64,
    /// Total QBC slashed.
    pub total_slashed: f64,
    /// Total QBC earned as rewards.
    pub total_rewards: f64,
}

impl Validator {
    /// Create a new validator.
    pub fn new(address: &str, stake_qbc: f64, staked_block: u64) -> Self {
        Self {
            address: address.to_string(),
            stake_qbc,
            staked_block,
            unstaking_block: 0,
            is_active: true,
            tasks_validated: 0,
            correct_validations: 0,
            total_slashed: 0.0,
            total_rewards: 0.0,
        }
    }

    /// Validation accuracy (0.0 - 1.0).
    pub fn accuracy(&self) -> f64 {
        if self.tasks_validated == 0 {
            return 0.0;
        }
        self.correct_validations as f64 / self.tasks_validated as f64
    }

    /// Whether the validator is in the unstaking cooldown period.
    pub fn is_unstaking(&self) -> bool {
        self.unstaking_block > 0
    }
}

// ---------------------------------------------------------------------------
// Task market
// ---------------------------------------------------------------------------

/// Reasoning task marketplace for Proof-of-Thought consensus.
pub struct TaskMarket {
    tasks: RwLock<HashMap<String, ReasoningTask>>,
    max_tasks: usize,
}

impl TaskMarket {
    /// Create a new TaskMarket.
    pub fn new() -> Self {
        Self {
            tasks: RwLock::new(HashMap::new()),
            max_tasks: MAX_TASKS,
        }
    }

    /// Submit a new reasoning task with a QBC bounty.
    pub fn submit_task(
        &self,
        submitter: &str,
        description: &str,
        bounty_qbc: f64,
        query_type: &str,
        block_height: u64,
        timeout_blocks: u64,
    ) -> Option<ReasoningTask> {
        if bounty_qbc < MIN_TASK_BOUNTY {
            tracing::warn!(
                bounty = bounty_qbc,
                min = MIN_TASK_BOUNTY,
                "Task bounty below minimum"
            );
            return None;
        }

        let task = ReasoningTask::new(
            submitter,
            description,
            query_type,
            bounty_qbc,
            block_height,
            timeout_blocks,
        );

        let mut tasks = self.tasks.write();
        let task_id = task.task_id.clone();
        tasks.insert(task_id, task.clone());

        // Evict old tasks if over capacity
        if tasks.len() > self.max_tasks {
            Self::evict_old_tasks(&mut tasks);
        }

        tracing::info!(task_id = %task.task_id, bounty = bounty_qbc, "Task submitted");
        Some(task)
    }

    /// Claim an open task for solving.
    pub fn claim_task(&self, task_id: &str, solver_address: &str) -> bool {
        let mut tasks = self.tasks.write();
        let task = match tasks.get_mut(task_id) {
            Some(t) if t.status == TaskStatus::Open => t,
            _ => return false,
        };

        task.status = TaskStatus::Claimed;
        task.claimed_by = solver_address.to_string();
        true
    }

    /// Submit a solution for a claimed task.
    pub fn submit_solution(
        &self,
        task_id: &str,
        solver_address: &str,
        solution_data: HashMap<String, String>,
    ) -> bool {
        let mut tasks = self.tasks.write();
        let task = match tasks.get_mut(task_id) {
            Some(t) if t.status == TaskStatus::Claimed && t.claimed_by == solver_address => t,
            _ => return false,
        };

        // Compute solution hash
        let mut sorted_items: Vec<_> = solution_data.iter().collect();
        sorted_items.sort_by_key(|(k, _)| (*k).clone());
        let mut hasher = Sha256::new();
        for (k, v) in &sorted_items {
            hasher.update(k.as_bytes());
            hasher.update(v.as_bytes());
        }
        let solution_hash = format!("{:x}", hasher.finalize());

        task.solution_hash = solution_hash;
        task.solution_data = solution_data;
        task.status = TaskStatus::Proposed;
        true
    }

    /// Get open tasks, sorted by priority (bounty * urgency).
    pub fn get_open_tasks(&self, limit: usize, current_block: u64) -> Vec<ReasoningTask> {
        let tasks = self.tasks.read();
        let mut open: Vec<_> = tasks
            .values()
            .filter(|t| t.status == TaskStatus::Open)
            .cloned()
            .collect();

        open.sort_by(|a, b| {
            let pa = Self::priority_score(a, current_block);
            let pb = Self::priority_score(b, current_block);
            pb.partial_cmp(&pa).unwrap_or(std::cmp::Ordering::Equal)
        });

        open.truncate(limit);
        open
    }

    /// Compute priority score: bounty * urgency factor.
    fn priority_score(task: &ReasoningTask, current_block: u64) -> f64 {
        let mut urgency = 1.0;
        if current_block > 0 && task.timeout_blocks > 0 {
            let elapsed = current_block.saturating_sub(task.created_block);
            let remaining_ratio = 1.0 - (elapsed as f64 / task.timeout_blocks as f64);
            let remaining_ratio = remaining_ratio.max(0.0);
            if remaining_ratio < 0.1 {
                urgency = 3.0;
            } else if remaining_ratio < 0.3 {
                urgency = 2.0;
            } else if remaining_ratio < 0.5 {
                urgency = 1.5;
            }
        }
        task.bounty_qbc * urgency
    }

    /// Get a specific task.
    pub fn get_task(&self, task_id: &str) -> Option<ReasoningTask> {
        self.tasks.read().get(task_id).cloned()
    }

    /// Get a mutable reference to a task (internal use).
    fn get_task_mut<F, R>(&self, task_id: &str, f: F) -> Option<R>
    where
        F: FnOnce(&mut ReasoningTask) -> R,
    {
        let mut tasks = self.tasks.write();
        tasks.get_mut(task_id).map(f)
    }

    /// Expire tasks that have exceeded their timeout.
    pub fn expire_tasks(&self, current_block: u64) -> u64 {
        let mut tasks = self.tasks.write();
        let mut expired = 0u64;
        for task in tasks.values_mut() {
            if matches!(task.status, TaskStatus::Open | TaskStatus::Claimed) {
                if current_block.saturating_sub(task.created_block) > task.timeout_blocks {
                    task.status = TaskStatus::Expired;
                    expired += 1;
                }
            }
        }
        expired
    }

    /// Remove oldest completed/expired tasks to bound memory.
    fn evict_old_tasks(tasks: &mut HashMap<String, ReasoningTask>) {
        let mut removable: Vec<(String, f64)> = tasks
            .iter()
            .filter(|(_, t)| {
                matches!(
                    t.status,
                    TaskStatus::Completed | TaskStatus::Rejected | TaskStatus::Expired
                )
            })
            .map(|(id, t)| (id.clone(), t.timestamp))
            .collect();

        removable.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));

        let remove_count = removable.len() / 2;
        for (id, _) in removable.into_iter().take(remove_count) {
            tasks.remove(&id);
        }
    }

    /// Total number of tasks.
    pub fn task_count(&self) -> usize {
        self.tasks.read().len()
    }

    /// Number of open tasks.
    pub fn open_count(&self) -> usize {
        self.tasks
            .read()
            .values()
            .filter(|t| t.status == TaskStatus::Open)
            .count()
    }

    /// Get market statistics.
    pub fn get_stats(&self) -> HashMap<String, serde_json::Value> {
        let tasks = self.tasks.read();
        let mut status_counts: HashMap<String, u64> = HashMap::new();
        let mut total_open_bounty = 0.0f64;

        for t in tasks.values() {
            *status_counts.entry(t.status.to_string()).or_insert(0) += 1;
            if t.status == TaskStatus::Open {
                total_open_bounty += t.bounty_qbc;
            }
        }

        let mut stats = HashMap::new();
        stats.insert("total_tasks".into(), serde_json::json!(tasks.len()));
        stats.insert("status_counts".into(), serde_json::json!(status_counts));
        stats.insert(
            "total_open_bounty".into(),
            serde_json::json!((total_open_bounty * 10000.0).round() / 10000.0),
        );
        stats
    }
}

impl Default for TaskMarket {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Validator registry
// ---------------------------------------------------------------------------

/// Manages Proof-of-Thought validators: staking, unstaking, and performance.
pub struct ValidatorRegistry {
    validators: RwLock<HashMap<String, Validator>>,
}

impl ValidatorRegistry {
    /// Create a new ValidatorRegistry.
    pub fn new() -> Self {
        Self {
            validators: RwLock::new(HashMap::new()),
        }
    }

    /// Register or increase stake for a validator.
    pub fn stake(&self, address: &str, amount: f64, block_height: u64) -> bool {
        if amount < MIN_VALIDATOR_STAKE {
            tracing::warn!(
                amount = amount,
                min = MIN_VALIDATOR_STAKE,
                "Stake below minimum"
            );
            return false;
        }

        let mut validators = self.validators.write();
        if let Some(v) = validators.get_mut(address) {
            v.stake_qbc += amount;
            v.is_active = true;
            v.unstaking_block = 0;
        } else {
            validators.insert(
                address.to_string(),
                Validator::new(address, amount, block_height),
            );
        }
        true
    }

    /// Request to unstake -- enters cooldown period.
    pub fn request_unstake(&self, address: &str, block_height: u64) -> bool {
        let mut validators = self.validators.write();
        let v = match validators.get_mut(address) {
            Some(v) if v.is_active => v,
            _ => return false,
        };

        v.unstaking_block = block_height + UNSTAKING_DELAY_BLOCKS;
        v.is_active = false;
        true
    }

    /// Complete unstaking after cooldown. Returns QBC to return.
    pub fn complete_unstake(&self, address: &str, block_height: u64) -> f64 {
        let mut validators = self.validators.write();
        let should_remove = {
            let v = match validators.get(address) {
                Some(v) if v.unstaking_block > 0 && block_height >= v.unstaking_block => v,
                _ => return 0.0,
            };
            v.stake_qbc
        };

        if should_remove > 0.0 {
            validators.remove(address);
        }
        should_remove
    }

    /// Slash a validator's stake. Returns the slashed amount.
    pub fn slash(&self, address: &str, _reason: &str) -> f64 {
        let mut validators = self.validators.write();
        let v = match validators.get_mut(address) {
            Some(v) => v,
            None => return 0.0,
        };

        let slash_amount = v.stake_qbc * SLASH_PENALTY;
        v.stake_qbc -= slash_amount;
        v.total_slashed += slash_amount;
        v.is_active = v.stake_qbc >= MIN_VALIDATOR_STAKE;
        slash_amount
    }

    /// Reward a validator for correct validation.
    pub fn reward(&self, address: &str, amount: f64) -> bool {
        let mut validators = self.validators.write();
        let v = match validators.get_mut(address) {
            Some(v) => v,
            None => return false,
        };
        v.total_rewards += amount;
        v.correct_validations += 1;
        true
    }

    /// Increment tasks_validated for a validator.
    pub fn record_validation(&self, address: &str) {
        let mut validators = self.validators.write();
        if let Some(v) = validators.get_mut(address) {
            v.tasks_validated += 1;
        }
    }

    /// Get all active validators sorted by stake (descending).
    pub fn get_active_validators(&self) -> Vec<Validator> {
        let validators = self.validators.read();
        let mut active: Vec<_> = validators.values().filter(|v| v.is_active).cloned().collect();
        active.sort_by(|a, b| {
            b.stake_qbc
                .partial_cmp(&a.stake_qbc)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        active
    }

    /// Get a specific validator.
    pub fn get_validator(&self, address: &str) -> Option<Validator> {
        self.validators.read().get(address).cloned()
    }

    /// Total number of validators.
    pub fn validator_count(&self) -> usize {
        self.validators.read().len()
    }

    /// Number of active validators.
    pub fn active_count(&self) -> usize {
        self.validators
            .read()
            .values()
            .filter(|v| v.is_active)
            .count()
    }

    /// Total staked QBC.
    pub fn total_stake(&self) -> f64 {
        self.validators.read().values().map(|v| v.stake_qbc).sum()
    }

    /// Get registry statistics.
    pub fn get_stats(&self) -> HashMap<String, serde_json::Value> {
        let active = self.get_active_validators();
        let avg_accuracy = if active.is_empty() {
            0.0
        } else {
            active.iter().map(|v| v.accuracy()).sum::<f64>() / active.len() as f64
        };

        let top: Vec<serde_json::Value> = active
            .iter()
            .take(5)
            .map(|v| {
                serde_json::json!({
                    "address": format!("{}...", &v.address[..16.min(v.address.len())]),
                    "stake": (v.stake_qbc * 10000.0).round() / 10000.0,
                    "accuracy": (v.accuracy() * 10000.0).round() / 10000.0,
                    "validations": v.tasks_validated,
                })
            })
            .collect();

        let mut stats = HashMap::new();
        stats.insert(
            "total_validators".into(),
            serde_json::json!(self.validator_count()),
        );
        stats.insert(
            "active_validators".into(),
            serde_json::json!(self.active_count()),
        );
        stats.insert(
            "total_stake".into(),
            serde_json::json!((self.total_stake() * 10000.0).round() / 10000.0),
        );
        stats.insert(
            "avg_accuracy".into(),
            serde_json::json!((avg_accuracy * 10000.0).round() / 10000.0),
        );
        stats.insert("top_validators".into(), serde_json::json!(top));
        stats
    }
}

impl Default for ValidatorRegistry {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Task finalization result
// ---------------------------------------------------------------------------

/// Result of finalizing a validated task.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TaskFinalization {
    /// Task ID.
    pub task_id: String,
    /// Whether the solution was approved.
    pub approved: bool,
    /// Approval ratio (0.0 - 1.0).
    pub approval_ratio: f64,
    /// Number of votes cast.
    pub votes: usize,
    /// Task bounty in QBC.
    pub bounty: f64,
    /// Solver address.
    pub solver: String,
}

// ---------------------------------------------------------------------------
// Proof-of-Thought protocol orchestrator
// ---------------------------------------------------------------------------

/// Orchestrates the full Proof-of-Thought lifecycle:
/// task submission -> claiming -> solving -> validation -> reward/slash.
pub struct ProofOfThoughtProtocol {
    /// Task marketplace.
    pub task_market: TaskMarket,
    /// Validator registry.
    pub validator_registry: ValidatorRegistry,
    /// Maximum vote weight per validator (as fraction of total stake).
    max_vote_weight: f64,
}

impl ProofOfThoughtProtocol {
    /// Create a new ProofOfThoughtProtocol.
    pub fn new() -> Self {
        Self {
            task_market: TaskMarket::new(),
            validator_registry: ValidatorRegistry::new(),
            max_vote_weight: DEFAULT_MAX_VOTE_WEIGHT,
        }
    }

    /// Submit a validation vote on a proposed solution.
    ///
    /// Rejects votes where the validator is the solver (no self-voting).
    pub fn validate_solution(
        &self,
        task_id: &str,
        validator_address: &str,
        approve: bool,
    ) -> bool {
        let task = match self.task_market.get_task(task_id) {
            Some(t) if matches!(t.status, TaskStatus::Proposed | TaskStatus::Validating) => t,
            _ => return false,
        };

        // Prevent self-voting
        if !task.claimed_by.is_empty() && task.claimed_by == validator_address {
            tracing::warn!(
                validator = validator_address,
                task_id = task_id,
                "Self-voting rejected"
            );
            return false;
        }

        // Validator must be active
        match self.validator_registry.get_validator(validator_address) {
            Some(v) if v.is_active => {}
            _ => return false,
        };

        // Record the vote
        self.task_market.get_task_mut(task_id, |t| {
            t.status = TaskStatus::Validating;
            t.validation_votes
                .insert(validator_address.to_string(), approve);
        });

        self.validator_registry.record_validation(validator_address);
        true
    }

    /// Finalize a task after validation voting.
    ///
    /// Uses stake-weighted approval with per-validator vote weight cap.
    /// If >=67% approve, reward solver. If rejected, slash solver's stake.
    pub fn finalize_task(&self, task_id: &str) -> Option<TaskFinalization> {
        let task = match self.task_market.get_task(task_id) {
            Some(t) if t.status == TaskStatus::Validating && !t.validation_votes.is_empty() => t,
            _ => return None,
        };

        // First pass: compute raw total stake for capping
        let mut raw_total = 0.0f64;
        let mut validator_stakes: HashMap<String, f64> = HashMap::new();
        for addr in task.validation_votes.keys() {
            if let Some(v) = self.validator_registry.get_validator(addr) {
                validator_stakes.insert(addr.clone(), v.stake_qbc);
                raw_total += v.stake_qbc;
            }
        }

        if raw_total == 0.0 {
            return None;
        }

        // Second pass: cap each validator's effective weight
        let mut total_stake = 0.0f64;
        let mut approve_stake = 0.0f64;
        for (addr, &vote) in &task.validation_votes {
            let raw = *validator_stakes.get(addr).unwrap_or(&0.0);
            let capped = raw.min(raw_total * self.max_vote_weight);
            total_stake += capped;
            if vote {
                approve_stake += capped;
            }
        }

        if total_stake == 0.0 {
            return None;
        }

        let approval_ratio = approve_stake / total_stake;
        let approved = approval_ratio >= VALIDATION_THRESHOLD;

        if approved {
            self.task_market.get_task_mut(task_id, |t| {
                t.status = TaskStatus::Completed;
                t.reward_distributed = true;
            });
            // Reward validators who voted correctly
            let vote_count = task.validation_votes.len().max(1);
            for (addr, &vote) in &task.validation_votes {
                if vote {
                    self.validator_registry
                        .reward(addr, task.bounty_qbc * 0.1 / vote_count as f64);
                }
            }
        } else {
            self.task_market.get_task_mut(task_id, |t| {
                t.status = TaskStatus::Rejected;
            });
            // Slash the solver
            if !task.claimed_by.is_empty() {
                self.validator_registry
                    .slash(&task.claimed_by, "Solution rejected by validators");
            }
        }

        let finalization = TaskFinalization {
            task_id: task_id.to_string(),
            approved,
            approval_ratio: (approval_ratio * 10000.0).round() / 10000.0,
            votes: task.validation_votes.len(),
            bounty: task.bounty_qbc,
            solver: task.claimed_by.clone(),
        };

        tracing::info!(
            task_id = task_id,
            approved = approved,
            ratio = format!("{:.0}%", approval_ratio * 100.0),
            "Task finalized"
        );

        Some(finalization)
    }

    /// Per-block maintenance: expire old tasks.
    pub fn process_block(&self, block_height: u64) -> HashMap<String, serde_json::Value> {
        let expired = self.task_market.expire_tasks(block_height);
        let mut result = HashMap::new();
        result.insert("expired_tasks".into(), serde_json::json!(expired));
        result.insert(
            "open_tasks".into(),
            serde_json::json!(self.task_market.open_count()),
        );
        result.insert(
            "active_validators".into(),
            serde_json::json!(self.validator_registry.active_count()),
        );
        result
    }

    /// Get combined statistics.
    pub fn get_stats(&self) -> HashMap<String, serde_json::Value> {
        let mut stats = HashMap::new();
        stats.insert(
            "task_market".into(),
            serde_json::json!(self.task_market.get_stats()),
        );
        stats.insert(
            "validators".into(),
            serde_json::json!(self.validator_registry.get_stats()),
        );
        stats
    }
}

impl Default for ProofOfThoughtProtocol {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_task_creation() {
        let task = ReasoningTask::new("alice", "What is 2+2?", "deductive", 5.0, 100, 1000);
        assert_eq!(task.task_id.len(), 16);
        assert_eq!(task.status, TaskStatus::Open);
        assert_eq!(task.bounty_qbc, 5.0);
        assert_eq!(task.submitter, "alice");
    }

    #[test]
    fn test_task_status_display() {
        assert_eq!(TaskStatus::Open.to_string(), "open");
        assert_eq!(TaskStatus::Completed.to_string(), "completed");
        assert_eq!(TaskStatus::Validating.to_string(), "validating");
    }

    #[test]
    fn test_validator_creation() {
        let v = Validator::new("bob", 200.0, 50);
        assert!(v.is_active);
        assert!(!v.is_unstaking());
        assert!((v.accuracy() - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_validator_accuracy() {
        let mut v = Validator::new("bob", 200.0, 50);
        v.tasks_validated = 10;
        v.correct_validations = 7;
        assert!((v.accuracy() - 0.7).abs() < f64::EPSILON);
    }

    #[test]
    fn test_task_market_submit_below_minimum() {
        let market = TaskMarket::new();
        let result = market.submit_task("alice", "test", 0.5, "general", 100, 1000);
        assert!(result.is_none());
    }

    #[test]
    fn test_task_market_submit_and_claim() {
        let market = TaskMarket::new();
        let task = market
            .submit_task("alice", "test task", 5.0, "general", 100, 1000)
            .unwrap();
        assert_eq!(market.task_count(), 1);
        assert_eq!(market.open_count(), 1);

        let claimed = market.claim_task(&task.task_id, "bob");
        assert!(claimed);
        assert_eq!(market.open_count(), 0);

        // Cannot claim already claimed task
        let claimed2 = market.claim_task(&task.task_id, "charlie");
        assert!(!claimed2);
    }

    #[test]
    fn test_task_market_submit_solution() {
        let market = TaskMarket::new();
        let task = market
            .submit_task("alice", "test", 5.0, "general", 100, 1000)
            .unwrap();
        market.claim_task(&task.task_id, "bob");

        let mut solution = HashMap::new();
        solution.insert("answer".into(), "4".into());

        // Wrong solver
        let result = market.submit_solution(&task.task_id, "charlie", solution.clone());
        assert!(!result);

        // Correct solver
        let result = market.submit_solution(&task.task_id, "bob", solution);
        assert!(result);

        let updated = market.get_task(&task.task_id).unwrap();
        assert_eq!(updated.status, TaskStatus::Proposed);
        assert!(!updated.solution_hash.is_empty());
    }

    #[test]
    fn test_task_market_open_tasks_sorted_by_priority() {
        let market = TaskMarket::new();
        market.submit_task("a", "low bounty", 2.0, "general", 100, 1000);
        market.submit_task("b", "high bounty", 10.0, "general", 100, 1000);
        market.submit_task("c", "medium bounty", 5.0, "general", 100, 1000);

        let open = market.get_open_tasks(10, 100);
        assert_eq!(open.len(), 3);
        assert!((open[0].bounty_qbc - 10.0).abs() < f64::EPSILON);
        assert!((open[1].bounty_qbc - 5.0).abs() < f64::EPSILON);
        assert!((open[2].bounty_qbc - 2.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_task_market_urgency_boost() {
        let market = TaskMarket::new();
        // Task about to expire (900 of 1000 blocks elapsed)
        market.submit_task("a", "urgent", 2.0, "general", 100, 1000);
        // Fresh task with higher bounty
        market.submit_task("b", "fresh", 3.0, "general", 1000, 1000);

        let open = market.get_open_tasks(10, 1000);
        // Urgent task (2.0 * 3.0 = 6.0) should beat fresh (3.0 * 1.0 = 3.0)
        assert!((open[0].bounty_qbc - 2.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_task_market_expire_tasks() {
        let market = TaskMarket::new();
        market.submit_task("a", "test", 5.0, "general", 100, 500);
        assert_eq!(market.open_count(), 1);

        let expired = market.expire_tasks(700);
        assert_eq!(expired, 1);
        assert_eq!(market.open_count(), 0);
    }

    #[test]
    fn test_validator_registry_stake() {
        let registry = ValidatorRegistry::new();
        assert!(registry.stake("bob", 200.0, 100));
        assert_eq!(registry.validator_count(), 1);
        assert_eq!(registry.active_count(), 1);

        // Below minimum
        assert!(!registry.stake("charlie", 50.0, 100));
    }

    #[test]
    fn test_validator_registry_stake_increase() {
        let registry = ValidatorRegistry::new();
        registry.stake("bob", 200.0, 100);
        registry.stake("bob", 100.0, 200);
        let v = registry.get_validator("bob").unwrap();
        assert!((v.stake_qbc - 300.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_validator_registry_unstake() {
        let registry = ValidatorRegistry::new();
        registry.stake("bob", 200.0, 100);

        assert!(registry.request_unstake("bob", 1000));
        let v = registry.get_validator("bob").unwrap();
        assert!(!v.is_active);
        assert!(v.is_unstaking());

        // Too early
        let amount = registry.complete_unstake("bob", 1000);
        assert!((amount - 0.0).abs() < f64::EPSILON);

        // After cooldown
        let amount = registry.complete_unstake("bob", 1000 + UNSTAKING_DELAY_BLOCKS);
        assert!((amount - 200.0).abs() < f64::EPSILON);
        assert!(registry.get_validator("bob").is_none());
    }

    #[test]
    fn test_validator_registry_slash() {
        let registry = ValidatorRegistry::new();
        registry.stake("bob", 200.0, 100);

        let slashed = registry.slash("bob", "bad behavior");
        assert!((slashed - 100.0).abs() < f64::EPSILON);

        let v = registry.get_validator("bob").unwrap();
        assert!((v.stake_qbc - 100.0).abs() < f64::EPSILON);
        assert!(v.is_active); // Still above minimum
    }

    #[test]
    fn test_validator_deactivated_after_heavy_slash() {
        let registry = ValidatorRegistry::new();
        registry.stake("bob", 150.0, 100);

        registry.slash("bob", "first slash"); // 75 slashed, 75 remaining
        let v = registry.get_validator("bob").unwrap();
        assert!(!v.is_active); // Below MIN_VALIDATOR_STAKE (100)
    }

    #[test]
    fn test_validator_reward() {
        let registry = ValidatorRegistry::new();
        registry.stake("bob", 200.0, 100);
        assert!(registry.reward("bob", 5.0));
        let v = registry.get_validator("bob").unwrap();
        assert!((v.total_rewards - 5.0).abs() < f64::EPSILON);
        assert_eq!(v.correct_validations, 1);
    }

    #[test]
    fn test_protocol_full_lifecycle() {
        let protocol = ProofOfThoughtProtocol::new();

        // Setup validator
        protocol.validator_registry.stake("validator1", 200.0, 0);

        // Submit task
        let task = protocol
            .task_market
            .submit_task("alice", "What is 2+2?", 5.0, "deductive", 100, 1000)
            .unwrap();

        // Claim
        protocol.task_market.claim_task(&task.task_id, "solver1");

        // Submit solution
        let mut solution = HashMap::new();
        solution.insert("answer".into(), "4".into());
        protocol
            .task_market
            .submit_solution(&task.task_id, "solver1", solution);

        // Validate (approve)
        let voted = protocol.validate_solution(&task.task_id, "validator1", true);
        assert!(voted);

        // Finalize
        let result = protocol.finalize_task(&task.task_id);
        assert!(result.is_some());
        let fin = result.unwrap();
        assert!(fin.approved);
        assert!(fin.approval_ratio >= VALIDATION_THRESHOLD);
    }

    #[test]
    fn test_protocol_self_voting_rejected() {
        let protocol = ProofOfThoughtProtocol::new();
        protocol.validator_registry.stake("solver1", 200.0, 0);

        let task = protocol
            .task_market
            .submit_task("alice", "test", 5.0, "general", 100, 1000)
            .unwrap();
        protocol.task_market.claim_task(&task.task_id, "solver1");

        let mut solution = HashMap::new();
        solution.insert("answer".into(), "42".into());
        protocol
            .task_market
            .submit_solution(&task.task_id, "solver1", solution);

        // Self-voting should be rejected
        let voted = protocol.validate_solution(&task.task_id, "solver1", true);
        assert!(!voted);
    }

    #[test]
    fn test_protocol_rejection_and_slash() {
        let protocol = ProofOfThoughtProtocol::new();
        protocol.validator_registry.stake("solver1", 200.0, 0);
        protocol.validator_registry.stake("v1", 200.0, 0);
        protocol.validator_registry.stake("v2", 200.0, 0);

        let task = protocol
            .task_market
            .submit_task("alice", "test", 5.0, "general", 100, 1000)
            .unwrap();
        protocol.task_market.claim_task(&task.task_id, "solver1");

        let mut solution = HashMap::new();
        solution.insert("answer".into(), "wrong".into());
        protocol
            .task_market
            .submit_solution(&task.task_id, "solver1", solution);

        // Both validators reject
        protocol.validate_solution(&task.task_id, "v1", false);
        protocol.validate_solution(&task.task_id, "v2", false);

        let result = protocol.finalize_task(&task.task_id).unwrap();
        assert!(!result.approved);

        // Solver should be slashed
        let solver = protocol
            .validator_registry
            .get_validator("solver1")
            .unwrap();
        assert!(solver.total_slashed > 0.0);
    }

    #[test]
    fn test_protocol_process_block() {
        let protocol = ProofOfThoughtProtocol::new();
        protocol
            .task_market
            .submit_task("alice", "test", 5.0, "general", 100, 500);

        let result = protocol.process_block(700);
        assert_eq!(result["expired_tasks"], serde_json::json!(1));
    }

    #[test]
    fn test_protocol_get_stats() {
        let protocol = ProofOfThoughtProtocol::new();
        let stats = protocol.get_stats();
        assert!(stats.contains_key("task_market"));
        assert!(stats.contains_key("validators"));
    }

    #[test]
    fn test_task_finalization_serialization() {
        let fin = TaskFinalization {
            task_id: "abc123".into(),
            approved: true,
            approval_ratio: 0.85,
            votes: 3,
            bounty: 5.0,
            solver: "solver1".into(),
        };
        let json = serde_json::to_string(&fin).unwrap();
        assert!(json.contains("\"approved\":true"));
    }

    #[test]
    fn test_task_market_stats() {
        let market = TaskMarket::new();
        market.submit_task("a", "t1", 5.0, "general", 0, 1000);
        market.submit_task("b", "t2", 10.0, "general", 0, 1000);

        let stats = market.get_stats();
        assert_eq!(stats["total_tasks"], serde_json::json!(2));
        assert_eq!(stats["total_open_bounty"], serde_json::json!(15.0));
    }

    #[test]
    fn test_validator_registry_stats() {
        let registry = ValidatorRegistry::new();
        registry.stake("alice", 200.0, 0);
        registry.stake("bob", 300.0, 0);

        let stats = registry.get_stats();
        assert_eq!(stats["total_validators"], serde_json::json!(2));
        assert_eq!(stats["active_validators"], serde_json::json!(2));
        assert_eq!(stats["total_stake"], serde_json::json!(500.0));
    }

    #[test]
    fn test_task_market_get_task_nonexistent() {
        let market = TaskMarket::new();
        assert!(market.get_task("nonexistent").is_none());
    }

    #[test]
    fn test_validator_registry_active_validators_sorted() {
        let registry = ValidatorRegistry::new();
        registry.stake("a", 100.0, 0);
        registry.stake("b", 300.0, 0);
        registry.stake("c", 200.0, 0);

        let active = registry.get_active_validators();
        assert_eq!(active.len(), 3);
        assert!((active[0].stake_qbc - 300.0).abs() < f64::EPSILON);
        assert!((active[1].stake_qbc - 200.0).abs() < f64::EPSILON);
        assert!((active[2].stake_qbc - 100.0).abs() < f64::EPSILON);
    }
}
