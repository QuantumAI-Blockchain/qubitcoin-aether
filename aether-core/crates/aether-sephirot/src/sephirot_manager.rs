//! Sephirot Manager -- Core orchestrator for the 10 Tree of Life cognitive nodes.
//!
//! The 10 Sephirot form the cognitive backbone of the AGI system, each handling
//! a distinct function analogous to brain regions. They communicate via CSF
//! transport (QBC transactions) and maintain SUSY balance enforced by the
//! golden ratio.
//!
//! Ported from `src/qubitcoin/aether/sephirot.py`.

use crate::csf_transport::SephirahRole;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Golden ratio -- the fundamental constant of SUSY economics.
pub const PHI: f64 = 1.618033988749895;

/// SUSY expansion/constraint pairs -- must balance at golden ratio.
/// (Chesed/Gevurah, Chochmah/Binah, Netzach/Hod)
pub const SUSY_PAIRS: &[(SephirahRole, SephirahRole)] = &[
    (SephirahRole::Chesed, SephirahRole::Gevurah),
    (SephirahRole::Chochmah, SephirahRole::Binah),
    (SephirahRole::Netzach, SephirahRole::Hod),
];

/// Qubit allocations per Sephirah (from whitepaper).
pub const QUBIT_ALLOCATION: &[(SephirahRole, u32)] = &[
    (SephirahRole::Keter, 8),
    (SephirahRole::Chochmah, 6),
    (SephirahRole::Binah, 4),
    (SephirahRole::Chesed, 10),
    (SephirahRole::Gevurah, 3),
    (SephirahRole::Tiferet, 12),
    (SephirahRole::Netzach, 5),
    (SephirahRole::Hod, 7),
    (SephirahRole::Yesod, 16),
    (SephirahRole::Malkuth, 4),
];

/// Maximum number of SUSY violations to retain in history.
const MAX_VIOLATIONS_HISTORY: usize = 10_000;

/// Energy cap for stimulated nodes.
const MAX_ENERGY: f64 = 5.0;

/// Minimum energy floor (prevents nodes from dying).
const MIN_ENERGY: f64 = 0.1;

/// SUSY deviation tolerance for violation detection (20%).
const SUSY_TOLERANCE: f64 = 0.20;

/// Dead-zone threshold for enforcement (must exceed tolerance to correct).
const SUSY_DEAD_ZONE: f64 = 0.20;

/// Gradual correction factor (25% of deviation per tick).
const CORRECTION_FACTOR: f64 = 0.25;

// ---------------------------------------------------------------------------
// Helper: look up qubit allocation for a role
// ---------------------------------------------------------------------------

fn qubit_alloc(role: SephirahRole) -> u32 {
    for &(r, q) in QUBIT_ALLOCATION {
        if r == role {
            return q;
        }
    }
    4 // default
}

// ---------------------------------------------------------------------------
// SephirahState
// ---------------------------------------------------------------------------

/// Runtime state of a single Sephirah node.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SephirahState {
    /// Cognitive role of this node.
    pub role: SephirahRole,
    /// Current SUSY energy level (default 1.0).
    pub energy: f64,
    /// QBC staked on this node.
    pub qbc_stake: f64,
    /// Quantum state size (qubits allocated from whitepaper).
    pub qubits: u32,
    /// Whether this node is active.
    pub active: bool,
    /// Last block height at which this node was updated.
    pub last_update_block: u64,
    /// Total messages processed by this node.
    pub messages_processed: u64,
    /// Total reasoning operations performed.
    pub reasoning_ops: u64,
    /// Cognitive mass from the Higgs field.
    pub cognitive_mass: f64,
    /// Yukawa coupling constant.
    pub yukawa_coupling: f64,
}

impl SephirahState {
    /// Create a new node with default state for the given role.
    pub fn new(role: SephirahRole) -> Self {
        Self {
            role,
            energy: 1.0,
            qbc_stake: 0.0,
            qubits: qubit_alloc(role),
            active: true,
            last_update_block: 0,
            messages_processed: 0,
            reasoning_ops: 0,
            cognitive_mass: 0.0,
            yukawa_coupling: 0.0,
        }
    }
}

// ---------------------------------------------------------------------------
// SUSYViolation
// ---------------------------------------------------------------------------

/// Record of a SUSY balance violation between an expansion/constraint pair.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SUSYViolation {
    /// The expansion (creative/divergent) node.
    pub expansion_node: SephirahRole,
    /// The constraint (safety/convergent) node.
    pub constraint_node: SephirahRole,
    /// Actual energy ratio (expansion / constraint).
    pub ratio: f64,
    /// Expected ratio (golden ratio).
    pub expected_ratio: f64,
    /// QBC correction amount calculated.
    pub correction_qbc: f64,
    /// Block height at which the violation was detected.
    pub block_height: u64,
    /// Unix timestamp of detection.
    pub timestamp: f64,
}

// ---------------------------------------------------------------------------
// ConsensusResult
// ---------------------------------------------------------------------------

/// Result of a cross-Sephirot BFT consensus round.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsensusResult {
    /// Whether consensus was reached (winning weight >= threshold).
    pub consensus_reached: bool,
    /// The winning position (None if consensus not reached).
    pub winning_position: Option<String>,
    /// Weight accumulated by the winning position.
    pub winning_weight: f64,
    /// Total weight across all positions.
    pub total_weight: f64,
    /// BFT threshold required.
    pub threshold: f64,
    /// Per-node vote details.
    pub votes: Vec<VoteDetail>,
    /// Nodes that dissented from the winning position.
    pub dissenting: Vec<VoteDetail>,
    /// The query that was decided.
    pub query: String,
}

/// Detail of a single node's vote in a consensus round.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoteDetail {
    pub role: String,
    pub position: String,
    pub energy: f64,
    pub weight: f64,
    pub confidence: f64,
    pub effective_weight: f64,
}

// ---------------------------------------------------------------------------
// SephirotManager
// ---------------------------------------------------------------------------

/// Manages the 10 Sephirot nodes and their SUSY balance relationships.
///
/// Thread-safe via `parking_lot::RwLock` on the internal nodes map.
pub struct SephirotManager {
    nodes: Arc<RwLock<HashMap<SephirahRole, SephirahState>>>,
    violations: Arc<RwLock<Vec<SUSYViolation>>>,
    total_corrections: Arc<RwLock<u64>>,
}

impl SephirotManager {
    /// Create a new manager with all 10 Sephirot initialized to default state.
    pub fn new() -> Self {
        let mut nodes = HashMap::new();
        for &role in SephirahRole::all() {
            nodes.insert(role, SephirahState::new(role));
        }

        log::info!("SephirotManager initialized (10 Tree of Life nodes)");

        Self {
            nodes: Arc::new(RwLock::new(nodes)),
            violations: Arc::new(RwLock::new(Vec::new())),
            total_corrections: Arc::new(RwLock::new(0)),
        }
    }

    /// Get a clone of a specific node's state.
    pub fn get_node(&self, role: SephirahRole) -> SephirahState {
        let nodes = self.nodes.read();
        nodes.get(&role).cloned().unwrap_or_else(|| SephirahState::new(role))
    }

    /// Get all node states as a JSON-compatible map (role name -> state dict).
    pub fn get_all_states(&self) -> HashMap<String, serde_json::Value> {
        let nodes = self.nodes.read();
        nodes
            .iter()
            .map(|(role, node)| {
                let val = serde_json::json!({
                    "role": role.value(),
                    "energy": (node.energy * 1e6).round() / 1e6,
                    "qbc_stake": (node.qbc_stake * 1e4).round() / 1e4,
                    "qubits": node.qubits,
                    "active": node.active,
                    "messages_processed": node.messages_processed,
                    "reasoning_ops": node.reasoning_ops,
                    "cognitive_mass": (node.cognitive_mass * 1e4).round() / 1e4,
                    "yukawa_coupling": (node.yukawa_coupling * 1e6).round() / 1e6,
                });
                (role.value().to_string(), val)
            })
            .collect()
    }

    /// Update a node's SUSY energy level by a delta.
    pub fn update_energy(&self, role: SephirahRole, delta: f64, block_height: u64) {
        let mut nodes = self.nodes.write();
        if let Some(node) = nodes.get_mut(&role) {
            node.energy = (node.energy + delta).max(0.0);
            node.last_update_block = block_height;
            log::debug!(
                "Sephirah {} energy: {:.4} (delta={:+.4})",
                role.value(),
                node.energy,
                delta
            );
        }
    }

    /// Check SUSY balance across all expansion/constraint pairs.
    ///
    /// For each pair, the ratio of expansion energy to constraint energy should
    /// equal the golden ratio (phi). If deviation exceeds 20%, a violation is
    /// recorded.
    ///
    /// Returns the list of violations found.
    pub fn check_susy_balance(&self, block_height: u64) -> Vec<SUSYViolation> {
        let nodes = self.nodes.read();
        let mut found = Vec::new();

        for &(expansion, constraint) in SUSY_PAIRS {
            let e_expand = nodes.get(&expansion).map(|n| n.energy).unwrap_or(1.0);
            let e_constrain = nodes.get(&constraint).map(|n| n.energy).unwrap_or(1.0);

            if e_constrain <= 0.0 {
                continue;
            }

            let ratio = e_expand / e_constrain;
            let deviation = (ratio - PHI).abs() / PHI;

            if deviation > SUSY_TOLERANCE {
                let target_expand = e_constrain * PHI;
                let correction = (e_expand - target_expand).abs() * 0.5;

                let now = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs_f64();

                let violation = SUSYViolation {
                    expansion_node: expansion,
                    constraint_node: constraint,
                    ratio: (ratio * 1e6).round() / 1e6,
                    expected_ratio: PHI,
                    correction_qbc: (correction * 1e8).round() / 1e8,
                    block_height,
                    timestamp: now,
                };

                log::warn!(
                    "SUSY violation: {}/{} ratio={:.4} (expected phi={:.4}, dev={:.2}%)",
                    expansion.value(),
                    constraint.value(),
                    ratio,
                    PHI,
                    deviation * 100.0
                );

                found.push(violation);
            }
        }

        // Store violations (capped at MAX_VIOLATIONS_HISTORY)
        if !found.is_empty() {
            let mut violations = self.violations.write();
            violations.extend(found.iter().cloned());
            if violations.len() > MAX_VIOLATIONS_HISTORY {
                let excess = violations.len() - MAX_VIOLATIONS_HISTORY;
                violations.drain(..excess);
            }
        }

        found
    }

    /// Enforce SUSY balance by redistributing energy between pairs.
    ///
    /// Uses a dead zone (20% deviation threshold) and gradual correction (25%
    /// of deviation per tick) to prevent oscillation.
    ///
    /// Returns the number of corrections applied.
    pub fn enforce_susy_balance(&self, block_height: u64) -> u32 {
        let violations = self.check_susy_balance(block_height);
        let mut corrections: u32 = 0;

        let mut nodes = self.nodes.write();

        for v in &violations {
            let e_energy = nodes.get(&v.expansion_node).map(|n| n.energy).unwrap_or(1.0);
            let c_energy = nodes.get(&v.constraint_node).map(|n| n.energy).unwrap_or(1.0);

            if c_energy <= 0.0 {
                continue;
            }

            let ratio = e_energy / c_energy;
            let deviation = (ratio - PHI).abs() / PHI;

            // Skip if within dead zone
            if deviation <= SUSY_DEAD_ZONE {
                continue;
            }

            // Conserve total energy in the pair
            let total_energy = e_energy + c_energy;
            let target_constrain = total_energy / (1.0 + PHI);
            let target_expand = target_constrain * PHI;

            // Gradual 25% correction
            let new_expand =
                (e_energy + CORRECTION_FACTOR * (target_expand - e_energy)).max(0.01);
            let new_constrain =
                (c_energy + CORRECTION_FACTOR * (target_constrain - c_energy)).max(0.01);

            let delta_expand = new_expand - e_energy;
            let delta_constrain = new_constrain - c_energy;

            if let Some(enode) = nodes.get_mut(&v.expansion_node) {
                enode.energy = new_expand;
                enode.last_update_block = block_height;
            }
            if let Some(cnode) = nodes.get_mut(&v.constraint_node) {
                cnode.energy = new_constrain;
                cnode.last_update_block = block_height;
            }

            corrections += 1;

            log::info!(
                "SUSY correction: {}/{} dev={:.2}% expand {:+.4} constrain {:+.4} new_ratio={:.4}",
                v.expansion_node.value(),
                v.constraint_node.value(),
                deviation * 100.0,
                delta_expand,
                delta_constrain,
                new_expand / new_constrain.max(0.001)
            );
        }

        if corrections > 0 {
            let mut tc = self.total_corrections.write();
            *tc += corrections as u64;
        }

        corrections
    }

    /// Compute Kuramoto order parameter measuring phase synchronization.
    ///
    /// R = |1/N * sum(e^(i*theta_j))| where theta_j is the phase of each node.
    /// R = 1.0 means perfect sync, R = 0.0 means no sync.
    ///
    /// When all energies are equal, returns 0.0 (no meaningful sync signal).
    pub fn get_coherence(&self) -> f64 {
        let nodes = self.nodes.read();
        let n = nodes.len();
        if n == 0 {
            return 0.0;
        }

        let energies: Vec<f64> = nodes.values().map(|n| n.energy).collect();

        // If all energies identical, no meaningful synchronization
        let first = energies[0];
        if energies.iter().all(|&e| (e - first).abs() < 1e-12) {
            return 0.0;
        }

        let max_e = energies.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let max_e = if max_e > 0.0 { max_e } else { 1.0 };

        let phases: Vec<f64> = energies
            .iter()
            .map(|e| (e / max_e) * 2.0 * std::f64::consts::PI)
            .collect();

        let cos_sum: f64 = phases.iter().map(|p| p.cos()).sum();
        let sin_sum: f64 = phases.iter().map(|p| p.sin()).sum();
        let r = (cos_sum * cos_sum + sin_sum * sin_sum).sqrt() / n as f64;

        (r * 1e6).round() / 1e6
    }

    /// Achieve cross-Sephirot consensus on a reasoning query via energy-weighted
    /// BFT-style voting.
    ///
    /// Each participating Sephirah submits a proposal with at least a `position`
    /// key. Votes are weighted by energy * confidence. Consensus is reached when
    /// a position accumulates >= `threshold` of total weight.
    pub fn cross_sephirot_consensus(
        &self,
        query: &str,
        proposals: &HashMap<SephirahRole, ProposalInput>,
        threshold: f64,
    ) -> ConsensusResult {
        if proposals.is_empty() {
            return ConsensusResult {
                consensus_reached: false,
                winning_position: None,
                winning_weight: 0.0,
                total_weight: 0.0,
                threshold,
                votes: vec![],
                dissenting: vec![],
                query: query.to_string(),
            };
        }

        let nodes = self.nodes.read();

        // Total energy of participating active nodes
        let mut total_energy: f64 = 0.0;
        for role in proposals.keys() {
            if let Some(node) = nodes.get(role) {
                if node.active {
                    total_energy += node.energy;
                }
            }
        }
        if total_energy <= 0.0 {
            total_energy = 1.0;
        }

        // Tally votes by position
        let mut position_weights: HashMap<String, f64> = HashMap::new();
        let mut votes: Vec<VoteDetail> = Vec::new();

        for (role, proposal) in proposals {
            let node = match nodes.get(role) {
                Some(n) if n.active => n,
                _ => continue,
            };

            let weight = node.energy / total_energy;
            let effective_weight = weight * proposal.confidence;

            *position_weights
                .entry(proposal.position.clone())
                .or_insert(0.0) += effective_weight;

            votes.push(VoteDetail {
                role: role.value().to_string(),
                position: proposal.position.clone(),
                energy: (node.energy * 1e6).round() / 1e6,
                weight: (weight * 1e6).round() / 1e6,
                confidence: (proposal.confidence * 1e4).round() / 1e4,
                effective_weight: (effective_weight * 1e6).round() / 1e6,
            });
        }

        // Find winning position
        let (winning_position, winning_weight) = position_weights
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(pos, w)| (Some(pos.clone()), *w))
            .unwrap_or((None, 0.0));

        let consensus_reached = winning_weight >= threshold;

        // Identify dissenters
        let wp_str = winning_position.as_deref().unwrap_or("");
        let dissenting: Vec<VoteDetail> = votes
            .iter()
            .filter(|v| v.position != wp_str)
            .cloned()
            .collect();

        let total_weight: f64 = position_weights.values().sum();

        if consensus_reached {
            log::info!(
                "Cross-Sephirot consensus reached: '{}' weight={:.4} >= {:.2} ({}/{} agree)",
                wp_str,
                winning_weight,
                threshold,
                votes.len() - dissenting.len(),
                votes.len()
            );
        } else {
            log::info!(
                "Cross-Sephirot consensus NOT reached: best='{}' weight={:.4} < {:.2}",
                wp_str,
                winning_weight,
                threshold
            );
        }

        ConsensusResult {
            consensus_reached,
            winning_position: if consensus_reached {
                winning_position
            } else {
                None
            },
            winning_weight: (winning_weight * 1e6).round() / 1e6,
            total_weight: (total_weight * 1e6).round() / 1e6,
            threshold,
            votes,
            dissenting,
            query: query.to_string(),
        }
    }

    /// Route a query to the most relevant Sephirot nodes based on content.
    ///
    /// Analyzes query keywords and query-type hints to score each node,
    /// weighted by current energy levels. Returns nodes ordered by relevance.
    pub fn route_query(&self, query: &str, query_type: &str) -> Vec<SephirahRole> {
        let q = query.to_lowercase();
        let nodes = self.nodes.read();

        // Domain keyword mappings
        let domain_map: &[(SephirahRole, &[&str])] = &[
            (
                SephirahRole::Keter,
                &[
                    "goal", "plan", "strategy", "meta", "priority", "decide",
                    "what should", "objective", "purpose", "mission",
                ],
            ),
            (
                SephirahRole::Chochmah,
                &[
                    "pattern", "intuition", "similar", "trend", "analogy",
                    "insight", "recognize", "discover", "correlat",
                ],
            ),
            (
                SephirahRole::Binah,
                &[
                    "logic", "reason", "cause", "because", "therefore", "prove",
                    "deduc", "infer", "if then", "implies", "why",
                ],
            ),
            (
                SephirahRole::Chesed,
                &[
                    "creative", "idea", "brainstorm", "imagine", "what if",
                    "innovate", "novel", "explore", "possibilit",
                ],
            ),
            (
                SephirahRole::Gevurah,
                &[
                    "safe", "risk", "danger", "harm", "limit", "constrain",
                    "vulnerab", "threat", "protect", "security",
                ],
            ),
            (
                SephirahRole::Tiferet,
                &[
                    "balance", "integrat", "synthesize", "combin", "reconcile",
                    "both", "conflict", "tradeoff", "compromise",
                ],
            ),
            (
                SephirahRole::Netzach,
                &[
                    "learn", "train", "reward", "reinforce", "habit",
                    "practice", "improve", "optimize", "performance",
                ],
            ),
            (
                SephirahRole::Hod,
                &[
                    "language", "meaning", "semantic", "word", "defin",
                    "explain", "communicat", "express", "describe", "what is",
                ],
            ),
            (
                SephirahRole::Yesod,
                &[
                    "remember", "memory", "recall", "history", "previous",
                    "past", "store", "retrieve", "context", "before",
                ],
            ),
            (
                SephirahRole::Malkuth,
                &[
                    "do", "execute", "action", "implement", "run", "deploy",
                    "send", "transact", "build", "create", "make",
                ],
            ),
        ];

        let mut scores: HashMap<SephirahRole, f64> = HashMap::new();

        for &(role, keywords) in domain_map {
            let node = match nodes.get(&role) {
                Some(n) if n.active => n,
                _ => continue,
            };
            let keyword_score: f64 = keywords.iter().filter(|kw| q.contains(*kw)).count() as f64;
            let energy_weight = node.energy.min(2.0);
            scores.insert(role, keyword_score * energy_weight);
        }

        // Query type boosts
        let type_boosts: &[(&str, &[SephirahRole])] = &[
            ("reasoning", &[SephirahRole::Binah, SephirahRole::Chochmah]),
            ("safety", &[SephirahRole::Gevurah, SephirahRole::Tiferet]),
            ("creative", &[SephirahRole::Chesed, SephirahRole::Chochmah]),
            ("memory", &[SephirahRole::Yesod, SephirahRole::Hod]),
            ("action", &[SephirahRole::Malkuth, SephirahRole::Keter]),
        ];
        for &(qt, roles) in type_boosts {
            if query_type == qt {
                for &role in roles {
                    *scores.entry(role).or_insert(0.0) += 2.0;
                }
            }
        }

        // Tiferet and Hod always get a small fallback boost
        *scores.entry(SephirahRole::Tiferet).or_insert(0.0) += 0.5;
        *scores.entry(SephirahRole::Hod).or_insert(0.0) += 0.5;

        // Sort by score descending
        let mut ranked: Vec<(SephirahRole, f64)> = scores.into_iter().collect();
        ranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        let result: Vec<SephirahRole> = ranked
            .iter()
            .filter(|(_, s)| *s > 0.0)
            .map(|(r, _)| *r)
            .collect();

        // Track routing for top 3
        drop(nodes);
        {
            let mut nodes_w = self.nodes.write();
            for &role in result.iter().take(3) {
                if let Some(node) = nodes_w.get_mut(&role) {
                    node.messages_processed += 1;
                }
            }
        }

        if result.is_empty() {
            vec![SephirahRole::Tiferet, SephirahRole::Hod]
        } else {
            result
        }
    }

    /// Determine the dominant cognitive mode based on node energies.
    ///
    /// Returns a human-readable string like "analytical", "creative", or
    /// "communicative" based on which SUSY pair is most active.
    pub fn get_dominant_cognitive_mode(&self) -> String {
        let nodes = self.nodes.read();
        let modes: &[(&str, SephirahRole, SephirahRole)] = &[
            ("analytical", SephirahRole::Binah, SephirahRole::Chochmah),
            ("creative", SephirahRole::Chesed, SephirahRole::Gevurah),
            ("communicative", SephirahRole::Hod, SephirahRole::Netzach),
        ];

        let mut best_mode = "balanced";
        let mut best_energy = 0.0_f64;
        for &(name, a, b) in modes {
            let ea = nodes.get(&a).map(|n| n.energy).unwrap_or(0.0);
            let eb = nodes.get(&b).map(|n| n.energy).unwrap_or(0.0);
            let combined = ea + eb;
            if combined > best_energy {
                best_energy = combined;
                best_mode = name;
            }
        }

        best_mode.to_string()
    }

    /// Get normalized energy distribution across all nodes (percentage of total).
    pub fn get_energy_distribution(&self) -> HashMap<String, f64> {
        let nodes = self.nodes.read();
        let total: f64 = nodes.values().map(|n| n.energy).sum();
        if total <= 0.0 {
            return SephirahRole::all()
                .iter()
                .map(|r| (r.value().to_string(), 10.0))
                .collect();
        }
        nodes
            .iter()
            .map(|(role, node)| {
                let pct = (node.energy / total * 100.0 * 100.0).round() / 100.0;
                (role.value().to_string(), pct)
            })
            .collect()
    }

    /// Stimulate a node's energy in response to a relevant query.
    ///
    /// Implements use-it-or-lose-it dynamics: active nodes gain energy, up to
    /// a cap of 5.0.
    pub fn stimulate_node(&self, role: SephirahRole, amount: f64, block_height: u64) {
        let mut nodes = self.nodes.write();
        if let Some(node) = nodes.get_mut(&role) {
            node.energy = (node.energy + amount).min(MAX_ENERGY);
            node.reasoning_ops += 1;
            node.last_update_block = block_height;
        }
    }

    /// Apply small energy decay to nodes that haven't been used recently.
    ///
    /// Nodes inactive for more than 100 blocks lose energy at `decay_rate` per
    /// call, down to a floor of 0.1. Returns the number of nodes decayed.
    pub fn decay_unused_nodes(&self, block_height: u64, decay_rate: f64) -> u32 {
        let mut nodes = self.nodes.write();
        let mut decayed = 0u32;

        for node in nodes.values_mut() {
            if node.last_update_block > 0 && block_height.saturating_sub(node.last_update_block) > 100
            {
                let old = node.energy;
                node.energy = (node.energy - decay_rate).max(MIN_ENERGY);
                if node.energy < old {
                    decayed += 1;
                }
            }
        }

        decayed
    }

    /// Get comprehensive Sephirot status for API / dashboard.
    pub fn get_status(&self) -> serde_json::Value {
        let nodes = self.nodes.read();
        let violations = self.violations.read();

        let susy_pairs: Vec<serde_json::Value> = SUSY_PAIRS
            .iter()
            .map(|&(e, c)| {
                let e_energy = nodes.get(&e).map(|n| n.energy).unwrap_or(1.0);
                let c_energy = nodes.get(&c).map(|n| n.energy).unwrap_or(1.0);
                let ratio = e_energy / c_energy.max(0.001);
                serde_json::json!({
                    "expansion": e.value(),
                    "constraint": c.value(),
                    "ratio": (ratio * 1e4).round() / 1e4,
                    "target_ratio": PHI,
                })
            })
            .collect();

        let recent: Vec<serde_json::Value> = violations
            .iter()
            .rev()
            .take(10)
            .map(|v| {
                serde_json::json!({
                    "expansion": v.expansion_node.value(),
                    "constraint": v.constraint_node.value(),
                    "ratio": v.ratio,
                    "correction": v.correction_qbc,
                    "block": v.block_height,
                })
            })
            .collect();

        let total_violations = violations.len();
        let total_corr = *self.total_corrections.read();

        // Release locks before calling methods that also lock
        drop(nodes);
        drop(violations);

        serde_json::json!({
            "nodes": self.get_all_states(),
            "susy_pairs": susy_pairs,
            "coherence": self.get_coherence(),
            "dominant_mode": self.get_dominant_cognitive_mode(),
            "energy_distribution": self.get_energy_distribution(),
            "total_violations": total_violations,
            "total_corrections": total_corr,
            "recent_violations": recent,
        })
    }

    /// Number of initialized Sephirot nodes.
    pub fn node_count(&self) -> usize {
        self.nodes.read().len()
    }

    /// Total SUSY corrections applied since creation.
    pub fn total_corrections(&self) -> u64 {
        *self.total_corrections.read()
    }
}

impl Default for SephirotManager {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// ProposalInput -- lightweight input for consensus
// ---------------------------------------------------------------------------

/// Input for a single node's proposal in cross-Sephirot consensus.
#[derive(Debug, Clone)]
pub struct ProposalInput {
    /// The position this node advocates.
    pub position: String,
    /// Confidence in the position (0.0 - 1.0).
    pub confidence: f64,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_node_initialization() {
        let mgr = SephirotManager::new();
        assert_eq!(mgr.node_count(), 10);

        for &role in SephirahRole::all() {
            let node = mgr.get_node(role);
            assert_eq!(node.role, role);
            assert!((node.energy - 1.0).abs() < 1e-12);
            assert!(node.active);
            assert_eq!(node.qubits, qubit_alloc(role));
        }

        // Spot-check specific qubit allocations
        assert_eq!(mgr.get_node(SephirahRole::Keter).qubits, 8);
        assert_eq!(mgr.get_node(SephirahRole::Yesod).qubits, 16);
        assert_eq!(mgr.get_node(SephirahRole::Tiferet).qubits, 12);
        assert_eq!(mgr.get_node(SephirahRole::Gevurah).qubits, 3);
    }

    #[test]
    fn test_susy_balance_no_violation() {
        let mgr = SephirotManager::new();
        // All nodes start at energy=1.0, so ratio=1.0.
        // deviation = |1.0 - 1.618| / 1.618 = 0.382 > 0.20 => violations
        let violations = mgr.check_susy_balance(100);
        // At default (all 1.0), ratio is 1.0 which deviates ~38% from PHI
        assert_eq!(violations.len(), 3); // all 3 pairs violate

        // Now set energies so that expansion/constraint = PHI (within tolerance)
        {
            let mut nodes = mgr.nodes.write();
            for &(exp, con) in SUSY_PAIRS {
                nodes.get_mut(&con).unwrap().energy = 1.0;
                nodes.get_mut(&exp).unwrap().energy = PHI; // exact golden ratio
            }
        }
        let violations = mgr.check_susy_balance(101);
        assert_eq!(violations.len(), 0, "No violations when ratio = PHI exactly");
    }

    #[test]
    fn test_susy_balance_violation_detected() {
        let mgr = SephirotManager::new();
        // Set Chesed very high, Gevurah very low
        {
            let mut nodes = mgr.nodes.write();
            nodes.get_mut(&SephirahRole::Chesed).unwrap().energy = 4.0;
            nodes.get_mut(&SephirahRole::Gevurah).unwrap().energy = 1.0;
        }
        let violations = mgr.check_susy_balance(200);
        // Chesed/Gevurah ratio = 4.0, deviation = |4.0-1.618|/1.618 = ~147%
        let chesed_viol = violations
            .iter()
            .find(|v| v.expansion_node == SephirahRole::Chesed);
        assert!(chesed_viol.is_some(), "Chesed/Gevurah violation expected");
        let v = chesed_viol.unwrap();
        assert!((v.ratio - 4.0).abs() < 0.01);
        assert!(v.correction_qbc > 0.0);
    }

    #[test]
    fn test_susy_enforcement_corrects() {
        let mgr = SephirotManager::new();
        // Set extreme imbalance
        {
            let mut nodes = mgr.nodes.write();
            nodes.get_mut(&SephirahRole::Chesed).unwrap().energy = 5.0;
            nodes.get_mut(&SephirahRole::Gevurah).unwrap().energy = 0.5;
        }

        let corrections = mgr.enforce_susy_balance(300);
        assert!(corrections > 0, "Should have applied corrections");
        assert!(mgr.total_corrections() > 0);

        // After correction, Chesed energy should have decreased (moved toward target)
        let chesed = mgr.get_node(SephirahRole::Chesed);
        assert!(chesed.energy < 5.0, "Chesed should have lost energy");

        // Gevurah should have gained energy
        let gevurah = mgr.get_node(SephirahRole::Gevurah);
        assert!(gevurah.energy > 0.5, "Gevurah should have gained energy");

        // Verify 25% gradual correction: not fully at target
        // Total was 5.5, target_constrain = 5.5/(1+PHI) = 2.101, target_expand = 3.399
        // new_expand = 5.0 + 0.25*(3.399-5.0) = 5.0 - 0.400 = 4.600
        // new_constrain = 0.5 + 0.25*(2.101-0.5) = 0.5 + 0.400 = 0.900
        assert!(
            chesed.energy > 4.0 && chesed.energy < 5.0,
            "Gradual correction: chesed ~4.6, got {}",
            chesed.energy
        );
        assert!(
            gevurah.energy > 0.5 && gevurah.energy < 2.5,
            "Gradual correction: gevurah ~0.9, got {}",
            gevurah.energy
        );
    }

    #[test]
    fn test_coherence_equal_energies() {
        let mgr = SephirotManager::new();
        // All nodes at energy=1.0 => coherence = 0.0 (no meaningful signal)
        let c = mgr.get_coherence();
        assert!(
            c.abs() < 1e-6,
            "Equal energies should give coherence=0.0, got {}",
            c
        );
    }

    #[test]
    fn test_coherence_varied_energies() {
        let mgr = SephirotManager::new();
        {
            let mut nodes = mgr.nodes.write();
            // Create varied energies
            for (i, role) in SephirahRole::all().iter().enumerate() {
                nodes.get_mut(role).unwrap().energy = 0.5 + (i as f64) * 0.3;
            }
        }
        let c = mgr.get_coherence();
        assert!(c > 0.0, "Varied energies should give coherence > 0, got {}", c);
        assert!(c <= 1.0, "Coherence should be <= 1.0, got {}", c);
    }

    #[test]
    fn test_consensus_reached() {
        let mgr = SephirotManager::new();
        // Keter and Binah both vote "yes" with high confidence
        // They have equal energy (1.0 each) so combined weight = 2/3 of participants
        let mut proposals = HashMap::new();
        proposals.insert(
            SephirahRole::Keter,
            ProposalInput {
                position: "yes".to_string(),
                confidence: 1.0,
            },
        );
        proposals.insert(
            SephirahRole::Binah,
            ProposalInput {
                position: "yes".to_string(),
                confidence: 1.0,
            },
        );
        proposals.insert(
            SephirahRole::Chesed,
            ProposalInput {
                position: "no".to_string(),
                confidence: 1.0,
            },
        );

        let result = mgr.cross_sephirot_consensus("test query", &proposals, 0.66);
        assert!(result.consensus_reached);
        assert_eq!(result.winning_position.as_deref(), Some("yes"));
        assert!(result.winning_weight >= 0.66);
        assert_eq!(result.dissenting.len(), 1);
        assert_eq!(result.votes.len(), 3);
    }

    #[test]
    fn test_consensus_not_reached() {
        let mgr = SephirotManager::new();
        // Three equal-energy nodes, each with different position => max weight = 1/3
        let mut proposals = HashMap::new();
        proposals.insert(
            SephirahRole::Keter,
            ProposalInput {
                position: "yes".to_string(),
                confidence: 1.0,
            },
        );
        proposals.insert(
            SephirahRole::Binah,
            ProposalInput {
                position: "no".to_string(),
                confidence: 1.0,
            },
        );
        proposals.insert(
            SephirahRole::Chesed,
            ProposalInput {
                position: "maybe".to_string(),
                confidence: 1.0,
            },
        );

        let result = mgr.cross_sephirot_consensus("split query", &proposals, 0.67);
        assert!(!result.consensus_reached);
        assert!(result.winning_position.is_none());
        // ~0.333 weight for each
        assert!(result.winning_weight < 0.67);
    }

    #[test]
    fn test_query_routing_safety() {
        let mgr = SephirotManager::new();
        let routed = mgr.route_query("is this safe and what are the risks", "safety");
        // Gevurah should be near the top (keywords "safe" + "risk" + type boost)
        assert!(
            routed.iter().take(3).any(|r| *r == SephirahRole::Gevurah),
            "Safety query should route to Gevurah: {:?}",
            routed
        );
    }

    #[test]
    fn test_query_routing_reasoning() {
        let mgr = SephirotManager::new();
        let routed = mgr.route_query("why does this logic imply causation", "reasoning");
        // Binah should score high (keywords: "logic", "implies", "why" + type boost)
        assert!(
            routed.iter().take(3).any(|r| *r == SephirahRole::Binah),
            "Reasoning query should route to Binah: {:?}",
            routed
        );
    }

    #[test]
    fn test_query_routing_creative() {
        let mgr = SephirotManager::new();
        let routed = mgr.route_query("imagine a creative novel idea", "creative");
        assert!(
            routed.iter().take(3).any(|r| *r == SephirahRole::Chesed),
            "Creative query should route to Chesed: {:?}",
            routed
        );
    }

    #[test]
    fn test_query_routing_memory() {
        let mgr = SephirotManager::new();
        let routed = mgr.route_query("remember the previous context", "memory");
        assert!(
            routed.iter().take(3).any(|r| *r == SephirahRole::Yesod),
            "Memory query should route to Yesod: {:?}",
            routed
        );
    }

    #[test]
    fn test_stimulate_node() {
        let mgr = SephirotManager::new();
        let before = mgr.get_node(SephirahRole::Keter).energy;
        mgr.stimulate_node(SephirahRole::Keter, 0.5, 50);
        let after = mgr.get_node(SephirahRole::Keter);
        assert!((after.energy - (before + 0.5)).abs() < 1e-12);
        assert_eq!(after.reasoning_ops, 1);
        assert_eq!(after.last_update_block, 50);

        // Test cap at 5.0
        mgr.stimulate_node(SephirahRole::Keter, 10.0, 60);
        assert!((mgr.get_node(SephirahRole::Keter).energy - MAX_ENERGY).abs() < 1e-12);
    }

    #[test]
    fn test_decay_unused_nodes() {
        let mgr = SephirotManager::new();
        // Set all nodes to block 10
        {
            let mut nodes = mgr.nodes.write();
            for node in nodes.values_mut() {
                node.last_update_block = 10;
                node.energy = 2.0;
            }
        }

        // Decay at block 200 (190 blocks since update > 100 threshold)
        let decayed = mgr.decay_unused_nodes(200, 0.1);
        assert_eq!(decayed, 10, "All 10 nodes should decay");

        // Energy should have dropped by 0.1
        let energy = mgr.get_node(SephirahRole::Keter).energy;
        assert!((energy - 1.9).abs() < 1e-12);

        // Nodes at block 150 (only 50 blocks ago) should NOT decay
        {
            let mut nodes = mgr.nodes.write();
            nodes.get_mut(&SephirahRole::Keter).unwrap().last_update_block = 150;
        }
        let decayed = mgr.decay_unused_nodes(200, 0.1);
        assert_eq!(decayed, 9, "Keter should not decay (recently active)");
    }

    #[test]
    fn test_energy_distribution() {
        let mgr = SephirotManager::new();
        let dist = mgr.get_energy_distribution();
        assert_eq!(dist.len(), 10);
        // All at 1.0, so each should be 10%
        for (_, pct) in &dist {
            assert!((*pct - 10.0).abs() < 0.01, "Expected 10%, got {}", pct);
        }
    }

    #[test]
    fn test_energy_distribution_varied() {
        let mgr = SephirotManager::new();
        {
            let mut nodes = mgr.nodes.write();
            nodes.get_mut(&SephirahRole::Keter).unwrap().energy = 5.0;
            // Total = 5.0 + 9*1.0 = 14.0, Keter = 5/14 * 100 = ~35.71%
        }
        let dist = mgr.get_energy_distribution();
        let keter_pct = dist.get("keter").copied().unwrap_or(0.0);
        assert!(
            (keter_pct - 35.71).abs() < 0.1,
            "Keter should be ~35.71%, got {}",
            keter_pct
        );
    }

    #[test]
    fn test_dominant_cognitive_mode() {
        let mgr = SephirotManager::new();
        // Default: all equal => first mode checked wins (analytical: Binah+Chochmah)
        let mode = mgr.get_dominant_cognitive_mode();
        // All pairs have equal combined energy (2.0), so first checked wins
        assert!(
            ["analytical", "creative", "communicative"].contains(&mode.as_str()),
            "Should be a valid mode, got {}",
            mode
        );

        // Boost creative pair
        {
            let mut nodes = mgr.nodes.write();
            nodes.get_mut(&SephirahRole::Chesed).unwrap().energy = 4.0;
            nodes.get_mut(&SephirahRole::Gevurah).unwrap().energy = 3.0;
        }
        let mode = mgr.get_dominant_cognitive_mode();
        assert_eq!(mode, "creative", "Chesed+Gevurah boosted => creative mode");
    }

    #[test]
    fn test_update_energy() {
        let mgr = SephirotManager::new();
        mgr.update_energy(SephirahRole::Hod, 0.5, 42);
        let hod = mgr.get_node(SephirahRole::Hod);
        assert!((hod.energy - 1.5).abs() < 1e-12);
        assert_eq!(hod.last_update_block, 42);

        // Negative delta clamps at 0.0
        mgr.update_energy(SephirahRole::Hod, -10.0, 43);
        assert!((mgr.get_node(SephirahRole::Hod).energy - 0.0).abs() < 1e-12);
    }

    #[test]
    fn test_get_status_returns_json() {
        let mgr = SephirotManager::new();
        let status = mgr.get_status();
        assert!(status.get("nodes").is_some());
        assert!(status.get("susy_pairs").is_some());
        assert!(status.get("coherence").is_some());
        assert!(status.get("dominant_mode").is_some());
        assert!(status.get("energy_distribution").is_some());
        assert!(status.get("total_violations").is_some());
        assert!(status.get("total_corrections").is_some());
        assert!(status.get("recent_violations").is_some());
    }

    #[test]
    fn test_consensus_empty_proposals() {
        let mgr = SephirotManager::new();
        let result = mgr.cross_sephirot_consensus("empty", &HashMap::new(), 0.67);
        assert!(!result.consensus_reached);
        assert!(result.votes.is_empty());
        assert_eq!(result.total_weight, 0.0);
    }

    #[test]
    fn test_get_all_states() {
        let mgr = SephirotManager::new();
        let states = mgr.get_all_states();
        assert_eq!(states.len(), 10);
        assert!(states.contains_key("keter"));
        assert!(states.contains_key("malkuth"));

        let keter = &states["keter"];
        assert_eq!(keter["active"], true);
        assert_eq!(keter["qubits"], 8);
    }
}
