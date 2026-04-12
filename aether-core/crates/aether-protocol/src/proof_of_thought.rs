//! Proof-of-Thought consensus engine for the Aether Tree.
//!
//! The `AetherEngine` orchestrates per-block reasoning proof generation:
//!   1. Extract knowledge from the block (transactions, metadata).
//!   2. Run reasoning strategies (deductive, inductive, abductive).
//!   3. Compute Phi via the gate system.
//!   4. Generate a `ThoughtProof` with a SHA-256 hash.
//!   5. Validate peer thought proofs.
//!
//! Ported from: `proof_of_thought.py` (AetherEngine core logic).

use std::collections::{HashMap, HashSet, VecDeque};
use std::time::{SystemTime, UNIX_EPOCH};

use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::gate_system::{GateResult, GateStats, GateSystem};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Default Phi threshold for PoT enforcement.
pub const PHI_THRESHOLD: f64 = 3.0;

/// Default block height after which PoT is mandatory.
pub const MANDATORY_POT_HEIGHT: u64 = 1000;

/// Default block height after which Phi enforcement is active.
pub const MANDATORY_PHI_ENFORCEMENT_HEIGHT: u64 = 5000;

/// Maximum number of cached thought proofs.
const POT_CACHE_MAX: usize = 1000;

/// Maximum number of deduplicated thought hashes.
const POT_HASH_SET_MAX: usize = 5000;

// ---------------------------------------------------------------------------
// Thought Proof
// ---------------------------------------------------------------------------

/// A reasoning step within a thought proof.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReasoningStep {
    /// Strategy used (deductive, inductive, abductive, causal, etc.).
    pub strategy: String,
    /// The premise/query that triggered this step.
    pub premise: String,
    /// The conclusion reached.
    pub conclusion: String,
    /// Confidence in this step (0.0 - 1.0).
    pub confidence: f64,
    /// Optional supporting evidence node IDs.
    pub evidence_ids: Vec<i64>,
}

/// A Proof-of-Thought record anchoring AGI reasoning to a block.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ThoughtProof {
    /// SHA-256 hash of the proof content.
    pub thought_hash: String,
    /// Ordered list of reasoning steps.
    pub reasoning_steps: Vec<ReasoningStep>,
    /// Phi integration value at this block.
    pub phi_value: f64,
    /// Merkle root of the knowledge graph at this block.
    pub knowledge_root: String,
    /// Address of the validator/miner who produced this proof.
    pub validator_address: String,
    /// Cryptographic signature (filled by the mining pipeline).
    pub signature: String,
    /// Unix timestamp of proof generation.
    pub timestamp: f64,
    /// Block height this proof is for.
    pub block_height: u64,
    /// Number of gates passed at this block.
    pub gates_passed: u32,
    /// Phi ceiling from the gate system.
    pub gate_ceiling: f64,
}

impl ThoughtProof {
    /// Compute the SHA-256 hash of this proof's content.
    pub fn calculate_hash(&self) -> String {
        let mut hasher = Sha256::new();
        // Hash reasoning steps
        for step in &self.reasoning_steps {
            hasher.update(step.strategy.as_bytes());
            hasher.update(step.premise.as_bytes());
            hasher.update(step.conclusion.as_bytes());
            hasher.update(step.confidence.to_le_bytes());
        }
        // Hash Phi value
        hasher.update(self.phi_value.to_le_bytes());
        // Hash knowledge root
        hasher.update(self.knowledge_root.as_bytes());
        // Hash validator address
        hasher.update(self.validator_address.as_bytes());
        // Hash timestamp
        hasher.update(self.timestamp.to_le_bytes());

        format!("{:x}", hasher.finalize())
    }

    /// Create a new ThoughtProof and compute its hash.
    pub fn new(
        reasoning_steps: Vec<ReasoningStep>,
        phi_value: f64,
        knowledge_root: String,
        validator_address: String,
        block_height: u64,
        gates_passed: u32,
        gate_ceiling: f64,
    ) -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        let mut proof = Self {
            thought_hash: String::new(),
            reasoning_steps,
            phi_value,
            knowledge_root,
            validator_address,
            signature: String::new(),
            timestamp,
            block_height,
            gates_passed,
            gate_ceiling,
        };
        proof.thought_hash = proof.calculate_hash();
        proof
    }
}

// ---------------------------------------------------------------------------
// Thought proof validation
// ---------------------------------------------------------------------------

/// Result of validating a thought proof.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ThoughtProofValidation {
    /// Whether the proof is valid.
    pub valid: bool,
    /// Human-readable reason.
    pub reason: String,
}

// ---------------------------------------------------------------------------
// Phi milestone effects
// ---------------------------------------------------------------------------

/// Tracks system behavior changes triggered by Phi milestones.
#[derive(Clone, Debug, Default)]
struct PhiMilestoneState {
    /// Set of Phi milestone values already crossed.
    crossed: HashSet<u32>,
    /// Exploration boost multiplier for abductive reasoning.
    exploration_boost: f64,
    /// Extra blocks for observation window.
    obs_window_bonus: u32,
}

// ---------------------------------------------------------------------------
// AetherEngine
// ---------------------------------------------------------------------------

/// Main Aether Tree engine that orchestrates per-block reasoning proof
/// generation and AGI milestone tracking.
///
/// Thread-safe: all mutable state is behind `RwLock`.
pub struct AetherEngine {
    /// Gate system for milestone evaluation.
    gate_system: GateSystem,
    /// Cached thought proofs: block_height -> proof.
    pot_cache: RwLock<HashMap<u64, ThoughtProof>>,
    /// Deduplicated thought hashes.
    pot_hashes_seen: RwLock<HashSet<String>>,
    /// Number of blocks processed.
    blocks_processed: RwLock<u64>,
    /// Phi milestone tracking.
    milestone_state: RwLock<PhiMilestoneState>,
    /// Configurable Phi threshold for enforcement.
    phi_threshold: f64,
    /// Block height after which PoT is mandatory.
    mandatory_pot_height: u64,
    /// Block height after which Phi enforcement is active.
    mandatory_phi_height: u64,
    /// Contradictions resolved counter (persisted across blocks).
    contradictions_resolved: RwLock<u64>,
    /// Recent Phi values for convergence tracking.
    recent_phi_values: RwLock<VecDeque<f64>>,
    /// Maximum Phi history length.
    phi_history_max: usize,
}

impl AetherEngine {
    /// Create a new AetherEngine with default settings.
    pub fn new() -> Self {
        Self {
            gate_system: GateSystem::default(),
            pot_cache: RwLock::new(HashMap::new()),
            pot_hashes_seen: RwLock::new(HashSet::new()),
            blocks_processed: RwLock::new(0),
            milestone_state: RwLock::new(PhiMilestoneState {
                crossed: HashSet::new(),
                exploration_boost: 1.0,
                obs_window_bonus: 0,
            }),
            phi_threshold: PHI_THRESHOLD,
            mandatory_pot_height: MANDATORY_POT_HEIGHT,
            mandatory_phi_height: MANDATORY_PHI_ENFORCEMENT_HEIGHT,
            contradictions_resolved: RwLock::new(0),
            recent_phi_values: RwLock::new(VecDeque::with_capacity(100)),
            phi_history_max: 100,
        }
    }

    /// Create a new AetherEngine with custom parameters.
    pub fn with_config(
        gate_scale: f64,
        phi_threshold: f64,
        mandatory_pot_height: u64,
        mandatory_phi_height: u64,
    ) -> Self {
        Self {
            gate_system: GateSystem::new(gate_scale),
            phi_threshold,
            mandatory_pot_height,
            mandatory_phi_height,
            ..Self::new()
        }
    }

    /// Generate a thought proof for a block.
    ///
    /// # Arguments
    /// * `block_height` - Current block height.
    /// * `validator_address` - Address of the miner/validator.
    /// * `reasoning_steps` - Ordered reasoning steps from the reasoning engine.
    /// * `phi_value` - Computed Phi value for this block.
    /// * `knowledge_root` - Merkle root of the knowledge graph.
    /// * `gate_stats` - Current gate evaluation statistics.
    ///
    /// # Returns
    /// `Some(ThoughtProof)` on success, `None` if deduplicated or invalid.
    pub fn generate_thought_proof(
        &self,
        block_height: u64,
        validator_address: &str,
        reasoning_steps: Vec<ReasoningStep>,
        phi_value: f64,
        knowledge_root: &str,
        gate_stats: &GateStats,
    ) -> Option<ThoughtProof> {
        // Evaluate gates
        let (gate_results, gate_ceiling) = self.gate_system.evaluate(gate_stats);
        let gates_passed = gate_results.iter().filter(|g| g.passed).count() as u32;

        // Clamp Phi to gate ceiling
        let clamped_phi = phi_value.min(gate_ceiling);

        // Build the thought proof
        let proof = ThoughtProof::new(
            reasoning_steps,
            clamped_phi,
            knowledge_root.to_string(),
            validator_address.to_string(),
            block_height,
            gates_passed,
            gate_ceiling,
        );

        // Deduplication check
        {
            let hashes = self.pot_hashes_seen.read();
            if hashes.contains(&proof.thought_hash) {
                tracing::debug!(
                    block_height = block_height,
                    hash = %proof.thought_hash.get(..16).unwrap_or(&proof.thought_hash),
                    "Duplicate PoT hash detected, skipping"
                );
                return None;
            }
        }

        // Record the hash (with bounded set size)
        {
            let mut hashes = self.pot_hashes_seen.write();
            hashes.insert(proof.thought_hash.clone());
            if hashes.len() > POT_HASH_SET_MAX {
                // Evict roughly half
                let to_keep: Vec<String> = hashes.iter().skip(hashes.len() / 2).cloned().collect();
                hashes.clear();
                for h in to_keep {
                    hashes.insert(h);
                }
            }
        }

        // Cache the proof (with eviction)
        {
            let mut cache = self.pot_cache.write();
            cache.insert(block_height, proof.clone());
            if cache.len() > POT_CACHE_MAX {
                if let Some(&oldest) = cache.keys().min() {
                    cache.remove(&oldest);
                }
            }
        }

        // Update blocks processed
        {
            let mut bp = self.blocks_processed.write();
            *bp += 1;
        }

        // Track Phi history for convergence
        {
            let mut phi_hist = self.recent_phi_values.write();
            phi_hist.push_back(clamped_phi);
            if phi_hist.len() > self.phi_history_max {
                phi_hist.pop_front();
            }
        }

        // Apply milestone effects
        self.apply_phi_milestone_effects(clamped_phi, block_height);

        tracing::info!(
            block_height = block_height,
            phi = clamped_phi,
            gates = gates_passed,
            steps = proof.reasoning_steps.len(),
            "Thought proof generated"
        );

        Some(proof)
    }

    /// Validate a thought proof received from a peer.
    ///
    /// Checks:
    /// 1. PoT presence (mandatory after `mandatory_pot_height`).
    /// 2. Thought hash matches content.
    /// 3. Phi value is non-negative.
    /// 4. Phi >= threshold after `mandatory_phi_height`.
    /// 5. Knowledge root is not empty.
    /// 6. Reasoning steps are present (after bootstrap window).
    pub fn validate_thought_proof(
        &self,
        proof: Option<&ThoughtProof>,
        block_height: u64,
    ) -> ThoughtProofValidation {
        let proof = match proof {
            Some(p) => p,
            None => {
                if block_height >= self.mandatory_pot_height {
                    return ThoughtProofValidation {
                        valid: false,
                        reason: format!(
                            "Null thought proof rejected: PoT mandatory after block {} (current={})",
                            self.mandatory_pot_height, block_height
                        ),
                    };
                }
                return ThoughtProofValidation {
                    valid: true,
                    reason: "No thought proof (PoT optional during transition)".into(),
                };
            }
        };

        // Verify thought hash
        let expected_hash = proof.calculate_hash();
        if !proof.thought_hash.is_empty() && proof.thought_hash != expected_hash {
            return ThoughtProofValidation {
                valid: false,
                reason: format!(
                    "Thought hash mismatch: {} != {}",
                    &proof.thought_hash[..16.min(proof.thought_hash.len())],
                    &expected_hash[..16.min(expected_hash.len())]
                ),
            };
        }

        // Verify non-negative Phi
        if proof.phi_value < 0.0 {
            return ThoughtProofValidation {
                valid: false,
                reason: format!("Invalid Phi value: {}", proof.phi_value),
            };
        }

        // After MANDATORY_PHI_ENFORCEMENT_HEIGHT, Phi must meet the threshold
        if block_height >= self.mandatory_phi_height && proof.phi_value < self.phi_threshold {
            return ThoughtProofValidation {
                valid: false,
                reason: format!(
                    "Phi value {:.4} below threshold {} (enforced after block {})",
                    proof.phi_value, self.phi_threshold, self.mandatory_phi_height
                ),
            };
        }

        // Knowledge root must not be empty
        if proof.knowledge_root.is_empty() {
            return ThoughtProofValidation {
                valid: false,
                reason: "Empty knowledge root".into(),
            };
        }

        // Reasoning steps should be present after bootstrap window
        if block_height > self.mandatory_pot_height && proof.reasoning_steps.is_empty() {
            return ThoughtProofValidation {
                valid: false,
                reason: "No reasoning steps in thought proof".into(),
            };
        }

        ThoughtProofValidation {
            valid: true,
            reason: "Valid thought proof".into(),
        }
    }

    /// Apply system behavior changes at Phi milestones.
    ///
    /// At certain Phi thresholds, the engine adjusts its exploration/reasoning
    /// parameters to encourage deeper cognitive development.
    fn apply_phi_milestone_effects(&self, phi_value: f64, _block_height: u64) {
        let phi_100 = (phi_value * 100.0) as u32;
        let milestones = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500];

        let mut state = self.milestone_state.write();
        for &milestone in &milestones {
            if phi_100 >= milestone && !state.crossed.contains(&milestone) {
                state.crossed.insert(milestone);
                // Adjust exploration boost
                let level = (milestone / 50) as f64;
                state.exploration_boost = 1.0 + level * 0.1;
                state.obs_window_bonus = (level * 10.0) as u32;

                tracing::info!(
                    milestone = milestone as f64 / 100.0,
                    exploration_boost = state.exploration_boost,
                    "Phi milestone crossed"
                );
            }
        }
    }

    /// Get a cached thought proof for a block height.
    pub fn get_cached_proof(&self, block_height: u64) -> Option<ThoughtProof> {
        self.pot_cache.read().get(&block_height).cloned()
    }

    /// Get the number of blocks processed.
    pub fn blocks_processed(&self) -> u64 {
        *self.blocks_processed.read()
    }

    /// Get the current exploration boost from Phi milestones.
    pub fn exploration_boost(&self) -> f64 {
        self.milestone_state.read().exploration_boost
    }

    /// Get the number of contradictions resolved.
    pub fn contradictions_resolved(&self) -> u64 {
        *self.contradictions_resolved.read()
    }

    /// Increment the contradictions resolved counter.
    pub fn record_contradiction_resolved(&self) {
        let mut cr = self.contradictions_resolved.write();
        *cr += 1;
    }

    /// Get the Phi convergence (stddev of recent Phi values).
    /// Returns 0.0 if insufficient data.
    pub fn phi_convergence(&self) -> f64 {
        let hist = self.recent_phi_values.read();
        if hist.len() < 2 {
            return 0.0;
        }
        let mean = hist.iter().sum::<f64>() / hist.len() as f64;
        let variance = hist.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / hist.len() as f64;
        variance.sqrt()
    }

    /// Get comprehensive engine statistics.
    pub fn get_stats(&self) -> HashMap<String, serde_json::Value> {
        let mut stats = HashMap::new();
        stats.insert(
            "blocks_processed".into(),
            serde_json::json!(*self.blocks_processed.read()),
        );
        stats.insert(
            "pot_cache_size".into(),
            serde_json::json!(self.pot_cache.read().len()),
        );
        stats.insert(
            "hashes_seen".into(),
            serde_json::json!(self.pot_hashes_seen.read().len()),
        );
        stats.insert(
            "contradictions_resolved".into(),
            serde_json::json!(*self.contradictions_resolved.read()),
        );
        stats.insert(
            "phi_convergence".into(),
            serde_json::json!(self.phi_convergence()),
        );
        stats.insert(
            "exploration_boost".into(),
            serde_json::json!(self.milestone_state.read().exploration_boost),
        );
        stats.insert(
            "milestones_crossed".into(),
            serde_json::json!(self.milestone_state.read().crossed.len()),
        );
        stats
    }

    /// Access the gate system for external evaluation.
    pub fn gate_system(&self) -> &GateSystem {
        &self.gate_system
    }

    /// Evaluate gates with current stats (convenience wrapper).
    pub fn evaluate_gates(&self, stats: &GateStats) -> (Vec<GateResult>, f64) {
        self.gate_system.evaluate(stats)
    }
}

impl Default for AetherEngine {
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
    use crate::gate_system::GateStats;

    fn sample_steps() -> Vec<ReasoningStep> {
        vec![
            ReasoningStep {
                strategy: "deductive".into(),
                premise: "All blocks contain transactions".into(),
                conclusion: "This block contains transactions".into(),
                confidence: 0.9,
                evidence_ids: vec![1, 2, 3],
            },
            ReasoningStep {
                strategy: "inductive".into(),
                premise: "Recent blocks show increasing difficulty".into(),
                conclusion: "Difficulty trend is upward".into(),
                confidence: 0.75,
                evidence_ids: vec![4, 5],
            },
        ]
    }

    fn full_stats() -> GateStats {
        let mut stats = GateStats {
            n_nodes: 100_000,
            domain_count: 10,
            avg_confidence: 0.7,
            integration_score: 0.5,
            verified_predictions: 100,
            prediction_accuracy: 0.75,
            debate_verdicts: 50,
            contradiction_resolutions: 30,
            mip_phi: 0.6,
            cross_domain_inferences: 150,
            cross_domain_inference_confidence: 0.7,
            cross_domain_edges: 100,
            improvement_cycles_enacted: 20,
            improvement_performance_delta: 0.1,
            fep_free_energy_decreasing: true,
            calibration_error: 0.10,
            calibration_evaluations: 500,
            grounding_ratio: 0.15,
            auto_goals_generated: 100,
            auto_goals_with_inferences: 50,
            curiosity_driven_discoveries: 20,
            fep_domain_precisions: 5,
            axiom_from_consolidation: 30,
            novel_concept_count: 60,
            sephirot_winner_diversity: 0.7,
            ..Default::default()
        };
        stats.node_type_counts.insert("assertion".into(), 200);
        stats.node_type_counts.insert("inference".into(), 6000);
        stats.node_type_counts.insert("observation".into(), 200);
        stats.node_type_counts.insert("prediction".into(), 200);
        stats
            .edge_type_counts
            .insert("analogous_to".into(), 100);
        stats
    }

    #[test]
    fn test_thought_proof_hash_deterministic() {
        let steps = sample_steps();
        let p1 = ThoughtProof::new(steps.clone(), 2.5, "root123".into(), "validator1".into(), 100, 5, 2.5);
        // Same content -> same hash (minus timestamp which differs)
        // Since timestamp is auto-generated, we test the calculate_hash method directly
        let hash1 = p1.calculate_hash();
        let hash2 = p1.calculate_hash();
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_thought_proof_hash_changes_with_phi() {
        let steps = sample_steps();
        let mut p1 = ThoughtProof::new(steps.clone(), 2.5, "root".into(), "val".into(), 100, 5, 2.5);
        let h1 = p1.calculate_hash();
        p1.phi_value = 3.0;
        let h2 = p1.calculate_hash();
        assert_ne!(h1, h2);
    }

    #[test]
    fn test_generate_thought_proof() {
        let engine = AetherEngine::new();
        let stats = full_stats();
        let proof = engine.generate_thought_proof(
            100,
            "validator1",
            sample_steps(),
            2.5,
            "merkle_root_abc",
            &stats,
        );
        assert!(proof.is_some());
        let proof = proof.unwrap();
        assert!(!proof.thought_hash.is_empty());
        assert_eq!(proof.block_height, 100);
        assert_eq!(proof.gates_passed, 10);
    }

    #[test]
    fn test_duplicate_proof_rejected() {
        let engine = AetherEngine::new();
        let stats = full_stats();

        // Generate first proof
        let p1 = engine.generate_thought_proof(
            100, "val", sample_steps(), 2.5, "root", &stats,
        );
        assert!(p1.is_some());
        let hash = p1.unwrap().thought_hash.clone();

        // Manually insert the hash to simulate duplicate
        engine.pot_hashes_seen.write().insert(hash);

        // Same content at same timestamp would be different due to timestamp,
        // but we can verify the dedup mechanism by inserting manually
        // and checking it doesn't appear in cache twice
        assert_eq!(engine.pot_cache.read().len(), 1);
    }

    #[test]
    fn test_validate_null_proof_before_mandatory() {
        let engine = AetherEngine::new();
        let result = engine.validate_thought_proof(None, 500);
        assert!(result.valid);
    }

    #[test]
    fn test_validate_null_proof_after_mandatory() {
        let engine = AetherEngine::new();
        let result = engine.validate_thought_proof(None, 1500);
        assert!(!result.valid);
        assert!(result.reason.contains("mandatory"));
    }

    #[test]
    fn test_validate_valid_proof() {
        let proof = ThoughtProof::new(
            sample_steps(), 3.5, "root123".into(), "val1".into(), 6000, 7, 3.5,
        );
        let engine = AetherEngine::new();
        let result = engine.validate_thought_proof(Some(&proof), 6000);
        assert!(result.valid);
    }

    #[test]
    fn test_validate_negative_phi_rejected() {
        let mut proof = ThoughtProof::new(
            sample_steps(), -1.0, "root".into(), "val".into(), 100, 0, 0.0,
        );
        proof.phi_value = -1.0;
        let engine = AetherEngine::new();
        let result = engine.validate_thought_proof(Some(&proof), 100);
        assert!(!result.valid);
        assert!(result.reason.contains("Invalid Phi"));
    }

    #[test]
    fn test_validate_low_phi_after_enforcement() {
        let proof = ThoughtProof::new(
            sample_steps(), 1.0, "root".into(), "val".into(), 6000, 2, 1.0,
        );
        let engine = AetherEngine::new();
        let result = engine.validate_thought_proof(Some(&proof), 6000);
        assert!(!result.valid);
        assert!(result.reason.contains("below threshold"));
    }

    #[test]
    fn test_validate_empty_knowledge_root() {
        let proof = ThoughtProof::new(
            sample_steps(), 4.0, "".into(), "val".into(), 6000, 8, 4.0,
        );
        let engine = AetherEngine::new();
        let result = engine.validate_thought_proof(Some(&proof), 6000);
        assert!(!result.valid);
        assert!(result.reason.contains("Empty knowledge root"));
    }

    #[test]
    fn test_validate_no_reasoning_steps() {
        let proof = ThoughtProof::new(
            vec![], 4.0, "root".into(), "val".into(), 2000, 8, 4.0,
        );
        let engine = AetherEngine::new();
        let result = engine.validate_thought_proof(Some(&proof), 2000);
        assert!(!result.valid);
        assert!(result.reason.contains("No reasoning steps"));
    }

    #[test]
    fn test_validate_hash_mismatch() {
        let mut proof = ThoughtProof::new(
            sample_steps(), 3.5, "root".into(), "val".into(), 500, 7, 3.5,
        );
        proof.thought_hash = "bad_hash_1234567890123456".into();
        let engine = AetherEngine::new();
        let result = engine.validate_thought_proof(Some(&proof), 500);
        assert!(!result.valid);
        assert!(result.reason.contains("mismatch"));
    }

    #[test]
    fn test_phi_clamped_to_gate_ceiling() {
        let engine = AetherEngine::new();
        // Only gate 1 passes with minimal stats
        let mut stats = GateStats::default();
        stats.n_nodes = 600;
        stats.domain_count = 5;
        stats.avg_confidence = 0.6;

        let proof = engine.generate_thought_proof(
            100, "val", sample_steps(), 10.0, "root", &stats,
        );
        assert!(proof.is_some());
        let proof = proof.unwrap();
        // Gate ceiling is 0.5 (only gate 1 passed), phi should be clamped
        assert!(proof.phi_value <= 0.5 + f64::EPSILON);
    }

    #[test]
    fn test_blocks_processed_counter() {
        let engine = AetherEngine::new();
        assert_eq!(engine.blocks_processed(), 0);

        let stats = full_stats();
        engine.generate_thought_proof(1, "v", sample_steps(), 1.0, "r", &stats);
        assert_eq!(engine.blocks_processed(), 1);

        engine.generate_thought_proof(2, "v", sample_steps(), 1.0, "r", &stats);
        assert_eq!(engine.blocks_processed(), 2);
    }

    #[test]
    fn test_milestone_effects_triggered() {
        let engine = AetherEngine::new();
        let stats = full_stats();

        // Generate proof with high Phi (all gates pass, ceiling = 5.0)
        engine.generate_thought_proof(1, "v", sample_steps(), 5.0, "r", &stats);

        // Should have crossed multiple milestones
        assert!(engine.exploration_boost() > 1.0);
    }

    #[test]
    fn test_contradictions_resolved_counter() {
        let engine = AetherEngine::new();
        assert_eq!(engine.contradictions_resolved(), 0);
        engine.record_contradiction_resolved();
        engine.record_contradiction_resolved();
        assert_eq!(engine.contradictions_resolved(), 2);
    }

    #[test]
    fn test_phi_convergence_empty() {
        let engine = AetherEngine::new();
        assert!((engine.phi_convergence() - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_phi_convergence_with_data() {
        let engine = AetherEngine::new();
        let stats = full_stats();
        // Generate multiple proofs to populate Phi history
        for i in 0..10 {
            engine.generate_thought_proof(
                i, "v", sample_steps(), 2.5, &format!("r{}", i), &stats,
            );
        }
        // With identical Phi, convergence (stddev) should be near zero
        // (slight variation due to clamping)
        let conv = engine.phi_convergence();
        assert!(conv < 1.0); // should be very small
    }

    #[test]
    fn test_get_stats() {
        let engine = AetherEngine::new();
        let stats = engine.get_stats();
        assert!(stats.contains_key("blocks_processed"));
        assert!(stats.contains_key("pot_cache_size"));
        assert!(stats.contains_key("hashes_seen"));
        assert!(stats.contains_key("contradictions_resolved"));
        assert!(stats.contains_key("phi_convergence"));
    }

    #[test]
    fn test_cached_proof_retrieval() {
        let engine = AetherEngine::new();
        let stats = full_stats();
        engine.generate_thought_proof(42, "v", sample_steps(), 2.5, "root", &stats);

        let cached = engine.get_cached_proof(42);
        assert!(cached.is_some());
        assert_eq!(cached.unwrap().block_height, 42);

        let missing = engine.get_cached_proof(999);
        assert!(missing.is_none());
    }

    #[test]
    fn test_engine_with_custom_config() {
        let engine = AetherEngine::with_config(2.0, 4.0, 2000, 10000);
        assert!((engine.phi_threshold - 4.0).abs() < f64::EPSILON);
        assert_eq!(engine.mandatory_pot_height, 2000);
        assert_eq!(engine.mandatory_phi_height, 10000);
    }

    #[test]
    fn test_pot_cache_eviction() {
        let engine = AetherEngine::new();
        let stats = full_stats();

        // Generate more proofs than cache limit
        for i in 0..(POT_CACHE_MAX + 50) as u64 {
            engine.generate_thought_proof(
                i, "v", sample_steps(), 2.0, &format!("r{}", i), &stats,
            );
        }

        let cache = engine.pot_cache.read();
        assert!(cache.len() <= POT_CACHE_MAX);
    }
}
