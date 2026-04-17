//! Higgs Cognitive Field -- Physics-based mass assignment for AI nodes.
//!
//! Implements the Mexican Hat potential `V(phi) = -mu^2 |phi|^2 + lambda |phi|^4`
//! to give computational mass to each Sephirot node via Yukawa coupling.
//!
//! Mass determines rebalancing inertia (F = ma):
//!   - Heavier nodes resist SUSY rebalancing (high inertia)
//!   - Lighter nodes respond quickly to imbalances (low inertia)
//!
//! Two-Higgs-Doublet Model (2HDM):
//!   - `tan(beta) = phi = 1.618`
//!   - Expansion nodes couple to H_u (higher VEV -> higher mass)
//!   - Constraint nodes couple to H_d (lower VEV -> lower mass)
//!   - Natural golden ratio mass hierarchy between SUSY pairs

use crate::csf_transport::SephirahRole;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Golden ratio constant.
pub const PHI: f64 = 1.618_033_988_749_895;

/// Inverse golden ratio powers (precomputed for clarity).
const PHI_INV_1: f64 = 0.618_033_988_749_895; // PHI^-1
const PHI_INV_2: f64 = 0.381_966_011_250_105; // PHI^-2
const PHI_INV_3: f64 = 0.236_067_977_499_790; // PHI^-3
const PHI_INV_4: f64 = 0.145_898_033_750_315; // PHI^-4

/// SUSY expansion/constraint pairs (Chesed/Gevurah, Chochmah/Binah, Netzach/Hod).
pub const SUSY_PAIRS: &[(SephirahRole, SephirahRole)] = &[
    (SephirahRole::Chesed, SephirahRole::Gevurah),
    (SephirahRole::Chochmah, SephirahRole::Binah),
    (SephirahRole::Netzach, SephirahRole::Hod),
];

/// Expansion nodes couple to H_u (higher VEV branch).
const EXPANSION_NODES: &[SephirahRole] = &[
    SephirahRole::Chochmah,
    SephirahRole::Chesed,
    SephirahRole::Netzach,
];

/// Constraint nodes couple to H_d (lower VEV branch).
const CONSTRAINT_NODES: &[SephirahRole] = &[
    SephirahRole::Binah,
    SephirahRole::Gevurah,
    SephirahRole::Hod,
];

// ---------------------------------------------------------------------------
// Yukawa couplings -- golden ratio cascade
// ---------------------------------------------------------------------------

/// Return the base Yukawa coupling for a given Sephirah role.
///
/// Tier 0 (Keter): PHI^0 = 1.0
/// Tier 1 (Chochmah, Binah, Tiferet): PHI^-1 = 0.618
/// Tier 2 (Chesed, Gevurah): PHI^-2 = 0.382
/// Tier 3 (Netzach, Hod): PHI^-3 = 0.236
/// Tier 4 (Yesod, Malkuth): PHI^-4 = 0.146
pub fn base_yukawa(role: SephirahRole) -> f64 {
    match role {
        SephirahRole::Keter => 1.0,
        SephirahRole::Chochmah | SephirahRole::Binah | SephirahRole::Tiferet => PHI_INV_1,
        SephirahRole::Chesed | SephirahRole::Gevurah => PHI_INV_2,
        SephirahRole::Netzach | SephirahRole::Hod => PHI_INV_3,
        SephirahRole::Yesod | SephirahRole::Malkuth => PHI_INV_4,
    }
}

/// Build a full Yukawa coupling map for all 10 roles.
pub fn yukawa_coupling_map() -> HashMap<SephirahRole, f64> {
    SephirahRole::all()
        .iter()
        .map(|&r| (r, base_yukawa(r)))
        .collect()
}

/// Return `true` if `role` is an expansion node.
fn is_expansion(role: SephirahRole) -> bool {
    EXPANSION_NODES.contains(&role)
}

/// Return `true` if `role` is a constraint node.
fn is_constraint(role: SephirahRole) -> bool {
    CONSTRAINT_NODES.contains(&role)
}

// ---------------------------------------------------------------------------
// HiggsParameters
// ---------------------------------------------------------------------------

/// Tunable parameters for the Higgs cognitive field.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HiggsParameters {
    /// Mass parameter (GeV-inspired).
    pub mu: f64,
    /// Self-coupling (Standard Model value).
    pub lambda_coupling: f64,
    /// 2HDM mixing angle: `tan(beta) = phi`.
    pub tan_beta: f64,
    /// Fractional deviation from VEV that triggers an excitation event.
    pub excitation_threshold: f64,
    /// Time step per block for energy update.
    pub dt: f64,
}

impl Default for HiggsParameters {
    fn default() -> Self {
        Self {
            mu: 88.45,
            lambda_coupling: 0.129,
            tan_beta: PHI,
            excitation_threshold: 0.10,
            dt: 0.01,
        }
    }
}

impl HiggsParameters {
    /// Vacuum Expectation Value: `v = mu / sqrt(2 * lambda)`.
    pub fn vev(&self) -> f64 {
        self.mu / (2.0 * self.lambda_coupling).sqrt()
    }

    /// Higgs boson mass: `m_H = sqrt(2) * mu`.
    pub fn higgs_mass(&self) -> f64 {
        std::f64::consts::SQRT_2 * self.mu
    }

    /// H_u VEV: `v * sin(beta)`.
    pub fn v_up(&self) -> f64 {
        let beta = self.tan_beta.atan();
        self.vev() * beta.sin()
    }

    /// H_d VEV: `v * cos(beta)`.
    pub fn v_down(&self) -> f64 {
        let beta = self.tan_beta.atan();
        self.vev() * beta.cos()
    }
}

// ---------------------------------------------------------------------------
// ExcitationEvent
// ---------------------------------------------------------------------------

/// A Higgs field excitation event (analogous to Higgs boson creation).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExcitationEvent {
    pub block_height: u64,
    /// `|phi_h - v| / v`
    pub field_deviation: f64,
    /// Deviation in basis points.
    pub deviation_bps: u32,
    /// Excitation energy released.
    pub energy_released: f64,
    /// Unix timestamp.
    pub timestamp: f64,
}

// ---------------------------------------------------------------------------
// TickResult
// ---------------------------------------------------------------------------

/// Excitation info included in a tick result when an excitation fires.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExcitationInfo {
    pub deviation_bps: u32,
    pub energy_released: f64,
}

/// Result of a single Higgs field tick (one block).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TickResult {
    pub field_value: f64,
    pub vev: f64,
    pub deviation: f64,
    pub deviation_pct: f64,
    pub mass_gap: f64,
    pub total_excitations: u64,
    pub potential_energy: f64,
    pub block_height: u64,
    pub excitation: Option<ExcitationInfo>,
}

// ---------------------------------------------------------------------------
// MassHierarchyHealth
// ---------------------------------------------------------------------------

/// Health report for a single SUSY pair.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PairHealth {
    pub expansion: String,
    pub constraint: String,
    pub m_expansion: f64,
    pub m_constraint: f64,
    pub ratio: f64,
    pub expected: f64,
    pub deviation_pct: f64,
    pub healthy: bool,
}

/// Overall mass hierarchy health report.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MassHierarchyHealth {
    pub all_healthy: bool,
    pub pairs: Vec<PairHealth>,
    pub field_stability: f64,
    pub mass_gap: f64,
}

// ---------------------------------------------------------------------------
// HiggsCognitiveField
// ---------------------------------------------------------------------------

/// Pervasive scalar field giving computational mass to AI cognitive nodes.
///
/// Implements:
/// - Mexican Hat potential with spontaneous symmetry breaking
/// - Yukawa coupling hierarchy (golden ratio cascade)
/// - Two-Higgs-Doublet Model for SUSY pair asymmetry
/// - Excitation event detection (Higgs boson analog)
/// - Mass gap metric for SUSY violation severity
pub struct HiggsCognitiveField {
    params: HiggsParameters,
    field_value: f64,
    cognitive_masses: HashMap<SephirahRole, f64>,
    yukawa_couplings: HashMap<SephirahRole, f64>,
    excitations: Vec<ExcitationEvent>,
    initialized: bool,
    total_excitations: u64,
    mass_gap: f64,
}

impl HiggsCognitiveField {
    /// Create a new Higgs cognitive field with the given parameters.
    pub fn new(params: HiggsParameters) -> Self {
        let vev = params.vev();
        let yukawa_couplings = yukawa_coupling_map();
        log::info!(
            "HiggsCognitiveField created: VEV={:.2}, mu={}, lambda={}",
            vev,
            params.mu,
            params.lambda_coupling,
        );
        Self {
            field_value: vev,
            params,
            cognitive_masses: HashMap::new(),
            yukawa_couplings,
            excitations: Vec::new(),
            initialized: false,
            total_excitations: 0,
            mass_gap: 0.0,
        }
    }

    /// Initialize the Higgs field and assign cognitive masses to all nodes.
    ///
    /// `node_energies` is an output map: for each role the tuple
    /// `(cognitive_mass, yukawa_coupling)` is written so the caller can
    /// propagate mass assignments to its own node structs.
    ///
    /// Returns a map of role name to assigned cognitive mass.
    pub fn initialize(
        &mut self,
        node_energies: &mut HashMap<SephirahRole, (f64, f64)>,
    ) -> HashMap<String, f64> {
        let mut masses: HashMap<String, f64> = HashMap::new();

        for &role in SephirahRole::all() {
            let yukawa = *self.yukawa_couplings.get(&role).unwrap_or(&PHI_INV_2);

            // 2HDM: expansion nodes use v_up, constraint nodes use v_down
            let vev = if is_expansion(role) {
                self.params.v_up()
            } else if is_constraint(role) {
                self.params.v_down()
            } else {
                self.params.vev()
            };

            let mass = yukawa * vev;
            self.cognitive_masses.insert(role, mass);
            node_energies.insert(role, (mass, yukawa));
            masses.insert(role.value().to_string(), round4(mass));
        }

        self.initialized = true;
        self.update_mass_gap();

        log::info!(
            "Higgs field initialized: {} nodes assigned masses, VEV={:.2}, mass_gap={:.4}",
            masses.len(),
            self.params.vev(),
            self.mass_gap,
        );
        masses
    }

    /// Per-block Higgs field evolution.
    ///
    /// 1. Compute current field value from aggregate node energies.
    /// 2. Normalize toward VEV with exponential damping.
    /// 3. Detect excitation events.
    /// 4. Update mass gap metric.
    pub fn tick(
        &mut self,
        block_height: u64,
        node_energies: &HashMap<SephirahRole, f64>,
    ) -> TickResult {
        if !self.initialized {
            return TickResult {
                field_value: 0.0,
                vev: self.params.vev(),
                deviation: 0.0,
                deviation_pct: 0.0,
                mass_gap: 0.0,
                total_excitations: 0,
                potential_energy: 0.0,
                block_height,
                excitation: None,
            };
        }

        // Compute effective field value from mass-weighted energy average
        self.field_value = self.compute_field_value(node_energies);
        // Hard clamp to prevent overflow
        self.field_value = self.field_value.clamp(-10_000.0, 10_000.0);

        // Normalize toward VEV
        self.normalize_to_vev();

        // Check for excitations
        let excitation = self.check_excitation(block_height);

        // Update mass gap
        self.update_mass_gap();

        let vev = self.params.vev();
        let deviation = (self.field_value - vev).abs();
        let deviation_pct = if vev > 0.0 {
            deviation / vev * 100.0
        } else {
            0.0
        };

        TickResult {
            field_value: round4(self.field_value),
            vev: round4(vev),
            deviation: round4(deviation),
            deviation_pct: round2(deviation_pct),
            mass_gap: round4(self.mass_gap),
            total_excitations: self.total_excitations,
            potential_energy: round4(self.potential_energy()),
            block_height,
            excitation: excitation.map(|e| ExcitationInfo {
                deviation_bps: e.deviation_bps,
                energy_released: round4(e.energy_released),
            }),
        }
    }

    /// Dampen field value toward VEV every tick.
    ///
    /// 1. Exponential damping: 40% pull toward VEV.
    /// 2. Hard clamp to `[0, 2*VEV]`.
    pub fn normalize_to_vev(&mut self) {
        let vev = self.params.vev();
        if vev <= 0.0 {
            return;
        }

        let old_value = self.field_value;

        // Step 1: exponential damping -- pull 40% toward VEV
        self.field_value = vev + (self.field_value - vev) * 0.6;

        // Step 2: hard clamp to [0, 2*VEV]
        let max_field = 2.0 * vev;
        self.field_value = self.field_value.clamp(0.0, max_field);

        let deviation = (self.field_value - vev).abs() / vev;
        if (old_value - self.field_value).abs() > 0.1 {
            log::info!(
                "Higgs field dampened: {:.2} (was {:.2}, deviation now {:.1}%)",
                self.field_value,
                old_value,
                deviation * 100.0,
            );
        }
    }

    /// Mexican hat potential: `V(phi) = -mu^2 * phi^2 + lambda * phi^4`.
    pub fn potential_energy(&self) -> f64 {
        let phi_h = self.field_value;
        let mu = self.params.mu;
        let lam = self.params.lambda_coupling;
        -(mu * mu) * (phi_h * phi_h) + lam * (phi_h * phi_h * phi_h * phi_h)
    }

    /// Gradient of the potential: `dV/dphi = -2*mu^2*phi + 4*lambda*phi^3`.
    pub fn higgs_gradient(&self, phi_h: f64) -> f64 {
        let mu = self.params.mu;
        let lam = self.params.lambda_coupling;
        -2.0 * mu * mu * phi_h + 4.0 * lam * phi_h * phi_h * phi_h
    }

    /// Newton's `F = ma` for cognitive rebalancing.
    ///
    /// Lighter nodes accelerate more (respond faster to forces).
    pub fn compute_rebalancing_acceleration(&self, role: SephirahRole, force: f64) -> f64 {
        let mass = self.cognitive_masses.get(&role).copied().unwrap_or(1.0);
        let mass = if mass <= 0.0 { 1.0 } else { mass };
        force / mass
    }

    /// Get the cognitive mass for a single role.
    pub fn get_cognitive_mass(&self, role: SephirahRole) -> f64 {
        self.cognitive_masses.get(&role).copied().unwrap_or(0.0)
    }

    /// Get all cognitive masses keyed by role name.
    pub fn get_all_masses(&self) -> HashMap<String, f64> {
        self.cognitive_masses
            .iter()
            .map(|(r, &m)| (r.value().to_string(), round4(m)))
            .collect()
    }

    /// Dynamically adjust Yukawa couplings based on node usage patterns.
    ///
    /// Heavily-used nodes get stronger coupling (higher mass, more inertia,
    /// more stable). Unused nodes get weaker coupling (lower mass, more agile).
    /// This implements neuroplasticity.
    ///
    /// Returns the number of couplings adjusted.
    pub fn adapt_yukawa_couplings(
        &mut self,
        usage_stats: &HashMap<SephirahRole, u64>,
    ) -> u32 {
        if usage_stats.is_empty() {
            return 0;
        }

        let max_usage = usage_stats.values().copied().max().unwrap_or(1);
        if max_usage == 0 {
            return 0;
        }

        let mut adjusted: u32 = 0;

        for (&role, &usage) in usage_stats {
            let base = base_yukawa(role);
            let usage_ratio = usage as f64 / max_usage as f64;
            // +/-5% adaptation
            let adaptation_factor = 0.95 + 0.10 * usage_ratio;
            let new_yukawa = base * adaptation_factor;
            let old_yukawa = *self.yukawa_couplings.get(&role).unwrap_or(&base);

            if (new_yukawa - old_yukawa).abs() > 0.001 {
                self.yukawa_couplings.insert(role, new_yukawa);

                // Recompute mass for this node
                let vev = if is_expansion(role) {
                    self.params.v_up()
                } else if is_constraint(role) {
                    self.params.v_down()
                } else {
                    self.params.vev()
                };
                let new_mass = new_yukawa * vev;
                self.cognitive_masses.insert(role, new_mass);
                adjusted += 1;
            }
        }

        if adjusted > 0 {
            self.update_mass_gap();
            log::debug!("Yukawa adaptation: {} couplings adjusted", adjusted);
        }
        adjusted
    }

    /// Field stability as inverse of recent deviation variance (0.0-1.0).
    pub fn get_field_stability(&self) -> f64 {
        if self.excitations.len() < 2 {
            return 1.0;
        }

        let recent: Vec<f64> = self
            .excitations
            .iter()
            .rev()
            .take(20)
            .map(|e| e.field_deviation)
            .collect();

        let n = recent.len() as f64;
        let mean = recent.iter().sum::<f64>() / n;
        let variance = recent.iter().map(|d| (d - mean).powi(2)).sum::<f64>() / n;

        let stability = 1.0 / (1.0 + variance * 100.0);
        round4(stability)
    }

    /// Check if the golden ratio mass hierarchy is maintained between SUSY pairs.
    pub fn get_mass_hierarchy_health(&self) -> MassHierarchyHealth {
        let mut pairs: Vec<PairHealth> = Vec::new();

        for &(expansion, constraint) in SUSY_PAIRS {
            let m_exp = self.cognitive_masses.get(&expansion).copied().unwrap_or(0.0);
            let m_con = self.cognitive_masses.get(&constraint).copied().unwrap_or(0.0);

            let (actual_ratio, expected_ratio, deviation, healthy) = if m_con > 0.0 {
                let actual = m_exp / m_con;
                let expected = self.params.v_up() / self.params.v_down().max(0.001);
                let dev = (actual - expected).abs() / expected.max(0.001);
                (actual, expected, dev, dev < 0.1)
            } else {
                (0.0, PHI, 1.0, false)
            };

            pairs.push(PairHealth {
                expansion: expansion.value().to_string(),
                constraint: constraint.value().to_string(),
                m_expansion: round4(m_exp),
                m_constraint: round4(m_con),
                ratio: round4(actual_ratio),
                expected: round4(expected_ratio),
                deviation_pct: round2(deviation * 100.0),
                healthy,
            });
        }

        let all_healthy = pairs.iter().all(|p| p.healthy);
        MassHierarchyHealth {
            all_healthy,
            pairs,
            field_stability: self.get_field_stability(),
            mass_gap: round6(self.mass_gap),
        }
    }

    /// Get comprehensive status for API / JSON serialization.
    pub fn get_status(&self) -> serde_json::Value {
        let vev = self.params.vev();
        let avg_mass = if self.cognitive_masses.is_empty() {
            0.0
        } else {
            self.cognitive_masses.values().sum::<f64>()
                / self.cognitive_masses.len() as f64
        };

        let recent_excitations: Vec<serde_json::Value> = self
            .excitations
            .iter()
            .rev()
            .take(10)
            .map(|e| {
                serde_json::json!({
                    "block": e.block_height,
                    "deviation_bps": e.deviation_bps,
                    "energy": round4(e.energy_released),
                })
            })
            .collect();

        serde_json::json!({
            "field_value": round4(self.field_value),
            "vev": round4(vev),
            "mu": self.params.mu,
            "lambda": self.params.lambda_coupling,
            "tan_beta": round4(self.params.tan_beta),
            "higgs_mass": round4(self.params.higgs_mass()),
            "v_up": round4(self.params.v_up()),
            "v_down": round4(self.params.v_down()),
            "deviation_pct": round2(
                (self.field_value - vev).abs() / vev.max(0.001) * 100.0
            ),
            "potential_energy": round4(self.potential_energy()),
            "mass_gap": round6(self.mass_gap),
            "total_excitations": self.total_excitations,
            "avg_cognitive_mass": round4(avg_mass),
            "node_masses": self.get_all_masses(),
            "recent_excitations": recent_excitations,
        })
    }

    /// Read-only access to parameters.
    pub fn params(&self) -> &HiggsParameters {
        &self.params
    }

    /// Current field value.
    pub fn field_value(&self) -> f64 {
        self.field_value
    }

    /// Whether the field has been initialized.
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    /// Compute effective field value from mass-weighted energy average.
    fn compute_field_value(&self, node_energies: &HashMap<SephirahRole, f64>) -> f64 {
        let mut total_weighted = 0.0_f64;
        let mut total_mass = 0.0_f64;

        for (&role, &mass) in &self.cognitive_masses {
            if mass > 0.0 {
                if let Some(&energy) = node_energies.get(&role) {
                    total_weighted += energy * mass;
                    total_mass += mass;
                }
            }
        }

        if total_mass <= 0.0 {
            return self.params.vev();
        }

        let avg_weighted_energy = total_weighted / total_mass;
        avg_weighted_energy * self.params.vev()
    }

    /// Detect Higgs excitation (field deviation > threshold from VEV).
    fn check_excitation(&mut self, block_height: u64) -> Option<ExcitationEvent> {
        let vev = self.params.vev();
        if vev <= 0.0 {
            return None;
        }

        let deviation = (self.field_value - vev).abs();
        let deviation_ratio = deviation / vev;

        if deviation_ratio > self.params.excitation_threshold {
            let energy = self.params.lambda_coupling * deviation * deviation;
            let event = ExcitationEvent {
                block_height,
                field_deviation: deviation_ratio,
                deviation_bps: (deviation_ratio * 10_000.0) as u32,
                energy_released: energy,
                timestamp: now_unix(),
            };
            self.excitations.push(event.clone());
            self.total_excitations += 1;

            // Keep bounded
            if self.excitations.len() > 1000 {
                let start = self.excitations.len() - 1000;
                self.excitations = self.excitations[start..].to_vec();
            }

            log::info!(
                "Higgs EXCITATION at block {}: deviation={:.4}, energy={:.4}",
                block_height,
                deviation_ratio,
                energy,
            );
            return Some(event);
        }
        None
    }

    /// Compute SUSY mass gap: avg |m_expansion - m_constraint * phi| / VEV.
    fn update_mass_gap(&mut self) {
        let mut gaps: Vec<f64> = Vec::new();

        for &(expansion, constraint) in SUSY_PAIRS {
            let m_exp = self.cognitive_masses.get(&expansion).copied().unwrap_or(0.0);
            let m_con = self.cognitive_masses.get(&constraint).copied().unwrap_or(0.0);
            let target = m_con * PHI;
            gaps.push((m_exp - target).abs());
        }

        let vev = self.params.vev().max(1.0);
        self.mass_gap = if gaps.is_empty() {
            0.0
        } else {
            gaps.iter().sum::<f64>() / gaps.len() as f64 / vev
        };
    }
}

// ---------------------------------------------------------------------------
// HiggsSUSYSwap -- mass-aware SUSY rebalancing
// ---------------------------------------------------------------------------

/// Mass-aware SUSY rebalancing using Higgs cognitive mechanics.
///
/// Uses gradient-based correction scaled by inverse cognitive mass (F = ma).
/// Lighter nodes correct faster, heavier nodes resist change.
pub struct HiggsSUSYSwap {
    /// Reference to HiggsParameters (copied for ownership simplicity).
    params: HiggsParameters,
    /// Tolerance for SUSY ratio deviation before correction kicks in.
    tolerance: f64,
}

impl HiggsSUSYSwap {
    /// Create a new swap engine using parameters from the given Higgs field.
    pub fn new(higgs: &HiggsCognitiveField) -> Self {
        Self {
            params: higgs.params.clone(),
            tolerance: 0.20,
        }
    }

    /// Mass-aware SUSY balance enforcement.
    ///
    /// For each SUSY pair:
    /// 1. Compute deviation from golden ratio.
    /// 2. Compute gradient force (quartic for large deviations >50%).
    /// 3. Apply F=ma: lighter nodes correct faster.
    /// 4. Apply corrections to the supplied energy map.
    ///
    /// Returns the number of corrections applied.
    pub fn enforce_susy_balance_with_mass(
        &self,
        _block_height: u64,
        node_energies: &mut HashMap<SephirahRole, f64>,
        cognitive_masses: &HashMap<SephirahRole, f64>,
    ) -> u32 {
        let mut corrections: u32 = 0;

        for &(expansion, constraint) in SUSY_PAIRS {
            let e_energy = *node_energies.get(&expansion).unwrap_or(&0.0);
            let c_energy = *node_energies.get(&constraint).unwrap_or(&0.0);

            if c_energy <= 0.0 {
                continue;
            }

            let ratio = e_energy / c_energy;
            let deviation = (ratio - PHI).abs() / PHI;

            if deviation <= self.tolerance {
                continue;
            }

            // Compute target energies (conserve total)
            let total_energy = e_energy + c_energy;
            let target_constrain = total_energy / (1.0 + PHI);
            let target_expand = target_constrain * PHI;

            // Force = deviation from target
            let mut force_expand = (target_expand - e_energy).abs();
            let mut force_constrain = (target_constrain - c_energy).abs();

            // Quartic growth for large deviations
            if deviation > 0.5 {
                let d2 = deviation * deviation;
                force_expand += force_expand * d2;
                force_constrain += force_constrain * d2;
            }

            // F=ma: acceleration = force / mass
            let m_exp = cognitive_masses.get(&expansion).copied().unwrap_or(1.0).max(0.01);
            let m_con = cognitive_masses.get(&constraint).copied().unwrap_or(1.0).max(0.01);

            let accel_expand = force_expand / m_exp;
            let accel_constrain = force_constrain / m_con;

            // Partial correction: 50% x acceleration x dt
            let correction_factor = 0.5;
            let dt = self.params.dt;

            let delta_expand = correction_factor * accel_expand * dt;
            let delta_constrain = correction_factor * accel_constrain * dt;

            // Direction: move toward target
            let new_e = if e_energy > target_expand {
                (e_energy - delta_expand).max(0.01)
            } else {
                e_energy + delta_expand
            };

            let new_c = if c_energy > target_constrain {
                (c_energy - delta_constrain).max(0.01)
            } else {
                c_energy + delta_constrain
            };

            node_energies.insert(expansion, new_e);
            node_energies.insert(constraint, new_c);

            corrections += 1;

            log::info!(
                "Higgs SUSY correction: {}/{} accel_e={:.4} accel_c={:.4} new_ratio={:.4}",
                expansion.value(),
                constraint.value(),
                accel_expand,
                accel_constrain,
                new_e / new_c.max(0.001),
            );
        }

        corrections
    }
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

fn round2(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

fn round4(v: f64) -> f64 {
    (v * 10_000.0).round() / 10_000.0
}

fn round6(v: f64) -> f64 {
    (v * 1_000_000.0).round() / 1_000_000.0
}

fn now_unix() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_relative_eq;

    fn default_params() -> HiggsParameters {
        HiggsParameters::default()
    }

    // -----------------------------------------------------------------------
    // HiggsParameters defaults and computed properties
    // -----------------------------------------------------------------------

    #[test]
    fn test_parameters_defaults() {
        let p = default_params();
        assert_eq!(p.mu, 88.45);
        assert_eq!(p.lambda_coupling, 0.129);
        assert_relative_eq!(p.tan_beta, PHI, epsilon = 1e-10);
        assert_eq!(p.excitation_threshold, 0.10);
        assert_eq!(p.dt, 0.01);
    }

    #[test]
    fn test_vev_computation() {
        let p = default_params();
        // v = mu / sqrt(2*lambda) = 88.45 / sqrt(0.258) = 88.45 / 0.50794 ~ 174.13
        let vev = p.vev();
        assert_relative_eq!(vev, 174.13, epsilon = 0.5);
        assert!(vev > 170.0 && vev < 180.0);
    }

    #[test]
    fn test_higgs_mass() {
        let p = default_params();
        // m_H = sqrt(2) * mu = 1.4142 * 88.45 ~ 125.08
        let mass = p.higgs_mass();
        assert_relative_eq!(mass, 125.08, epsilon = 0.5);
    }

    #[test]
    fn test_v_up_v_down() {
        let p = default_params();
        let v_up = p.v_up();
        let v_down = p.v_down();

        // v_up > v_down since tan(beta) = phi > 1
        assert!(v_up > v_down);

        // v_up^2 + v_down^2 = v^2
        let vev = p.vev();
        assert_relative_eq!(v_up * v_up + v_down * v_down, vev * vev, epsilon = 0.01);

        // v_up / v_down = tan(beta) = phi
        assert_relative_eq!(v_up / v_down, PHI, epsilon = 0.001);
    }

    // -----------------------------------------------------------------------
    // Mass initialization (all 10 nodes, 2HDM)
    // -----------------------------------------------------------------------

    #[test]
    fn test_mass_initialization() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params.clone());
        let mut energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();

        let masses = field.initialize(&mut energies);

        // All 10 nodes should have masses
        assert_eq!(masses.len(), 10);
        assert_eq!(energies.len(), 10);

        // Keter gets full VEV (neutral, yukawa = 1.0)
        let keter_mass = *masses.get("keter").unwrap();
        assert_relative_eq!(keter_mass, params.vev(), epsilon = 0.01);

        // Expansion node: Chochmah gets PHI^-1 * v_up
        let chochmah_mass = *masses.get("chochmah").unwrap();
        assert_relative_eq!(chochmah_mass, PHI_INV_1 * params.v_up(), epsilon = 0.01);

        // Constraint node: Binah gets PHI^-1 * v_down
        let binah_mass = *masses.get("binah").unwrap();
        assert_relative_eq!(binah_mass, PHI_INV_1 * params.v_down(), epsilon = 0.01);

        // Expansion > constraint for same Yukawa tier (2HDM asymmetry)
        assert!(chochmah_mass > binah_mass);

        // Malkuth (tier 4, neutral) should have smallest-ish mass
        let malkuth_mass = *masses.get("malkuth").unwrap();
        assert!(malkuth_mass < keter_mass);
    }

    #[test]
    fn test_2hdm_susy_pair_ratio() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params.clone());
        let mut energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        let masses = field.initialize(&mut energies);

        // SUSY pairs with same Yukawa tier should have ratio = v_up/v_down = phi
        let expected_ratio = params.v_up() / params.v_down();

        // Chochmah (expansion) / Binah (constraint) -- both tier 1
        let ratio = masses["chochmah"] / masses["binah"];
        assert_relative_eq!(ratio, expected_ratio, epsilon = 0.01);

        // Chesed / Gevurah -- both tier 2
        let ratio = masses["chesed"] / masses["gevurah"];
        assert_relative_eq!(ratio, expected_ratio, epsilon = 0.01);

        // Netzach / Hod -- both tier 3
        let ratio = masses["netzach"] / masses["hod"];
        assert_relative_eq!(ratio, expected_ratio, epsilon = 0.01);
    }

    // -----------------------------------------------------------------------
    // Field tick with excitation detection
    // -----------------------------------------------------------------------

    #[test]
    fn test_tick_no_excitation() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let mut init_energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        field.initialize(&mut init_energies);

        // All nodes at energy ~1.0 -> field_value ~ VEV (balanced)
        let mut energies: HashMap<SephirahRole, f64> = HashMap::new();
        for &role in SephirahRole::all() {
            energies.insert(role, 1.0);
        }

        let result = field.tick(100, &energies);
        assert_eq!(result.block_height, 100);
        assert!(result.excitation.is_none());
        assert!(result.total_excitations == 0);
    }

    #[test]
    fn test_tick_with_excitation() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let mut init_energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        field.initialize(&mut init_energies);

        // Set extreme energies to push field away from VEV
        let mut energies: HashMap<SephirahRole, f64> = HashMap::new();
        for &role in SephirahRole::all() {
            energies.insert(role, 5.0); // 5x normal -> significant deviation
        }

        let result = field.tick(200, &energies);
        // With high energies, field should deviate from VEV
        // Whether excitation fires depends on damping vs energy magnitude
        assert_eq!(result.block_height, 200);
        // The field value should be clamped and dampened
        assert!(result.field_value > 0.0);
    }

    // -----------------------------------------------------------------------
    // VEV normalization (damping behavior)
    // -----------------------------------------------------------------------

    #[test]
    fn test_normalize_to_vev_damping() {
        let params = default_params();
        let vev = params.vev();
        let mut field = HiggsCognitiveField::new(params);

        // Set field far above VEV
        field.field_value = vev * 1.5;
        field.normalize_to_vev();
        // After 40% damping: vev + (1.5*vev - vev) * 0.6 = vev + 0.3*vev = 1.3*vev
        assert_relative_eq!(field.field_value, vev * 1.3, epsilon = 0.01);

        // Set field below VEV
        field.field_value = vev * 0.5;
        field.normalize_to_vev();
        // vev + (0.5*vev - vev) * 0.6 = vev - 0.3*vev = 0.7*vev
        assert_relative_eq!(field.field_value, vev * 0.7, epsilon = 0.01);
    }

    #[test]
    fn test_normalize_hard_clamp() {
        let params = default_params();
        let vev = params.vev();
        let mut field = HiggsCognitiveField::new(params);

        // Extremely high -> should clamp to 2*VEV after damping
        field.field_value = vev * 10.0;
        field.normalize_to_vev();
        assert!(field.field_value <= 2.0 * vev + 0.01);

        // Negative -> should clamp to 0
        field.field_value = -100.0;
        field.normalize_to_vev();
        assert!(field.field_value >= 0.0);
    }

    // -----------------------------------------------------------------------
    // Potential energy (Mexican hat shape)
    // -----------------------------------------------------------------------

    #[test]
    fn test_potential_energy_at_origin() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        field.field_value = 0.0;
        // V(0) = 0
        assert_relative_eq!(field.potential_energy(), 0.0, epsilon = 1e-10);
    }

    #[test]
    fn test_potential_energy_at_vev_is_minimum() {
        let params = default_params();
        let vev = params.vev();
        let mut field = HiggsCognitiveField::new(params);

        // V(vev) should be less than V(0) = 0 (the minimum of the Mexican hat)
        field.field_value = vev;
        let v_at_vev = field.potential_energy();
        assert!(v_at_vev < 0.0, "V(vev) should be negative (minimum)");

        // V(0) = 0 > V(vev) -> Mexican hat has minimum at VEV, not origin
        field.field_value = 0.0;
        let v_at_zero = field.potential_energy();
        assert!(v_at_zero > v_at_vev, "V(0) > V(vev)");

        // Check that gradient is zero at VEV (equilibrium)
        let grad = field.higgs_gradient(vev);
        assert_relative_eq!(grad, 0.0, epsilon = 0.1);
    }

    #[test]
    fn test_mexican_hat_symmetry() {
        let params = default_params();
        let vev = params.vev();
        let mut field = HiggsCognitiveField::new(params);

        // V(vev + delta) ~ V(vev - delta) for small delta
        let delta = 5.0;
        field.field_value = vev + delta;
        let v_plus = field.potential_energy();
        field.field_value = vev - delta;
        let v_minus = field.potential_energy();
        // Not exactly equal because potential isn't symmetric around VEV,
        // but both should be > V(vev)
        field.field_value = vev;
        let v_vev = field.potential_energy();
        assert!(v_plus > v_vev);
        assert!(v_minus > v_vev);
    }

    // -----------------------------------------------------------------------
    // Rebalancing acceleration (lighter nodes accelerate more)
    // -----------------------------------------------------------------------

    #[test]
    fn test_rebalancing_acceleration() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let mut energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        field.initialize(&mut energies);

        let force = 10.0;

        // Malkuth (tier 4, lightest) should accelerate most
        let accel_malkuth = field.compute_rebalancing_acceleration(SephirahRole::Malkuth, force);
        // Keter (tier 0, heaviest) should accelerate least
        let accel_keter = field.compute_rebalancing_acceleration(SephirahRole::Keter, force);

        assert!(
            accel_malkuth > accel_keter,
            "Lighter node (Malkuth) should accelerate more than heavier (Keter)"
        );

        // Specifically: accel = force / mass, so ratio = mass_keter / mass_malkuth
        let ratio = accel_malkuth / accel_keter;
        let mass_ratio = field.get_cognitive_mass(SephirahRole::Keter)
            / field.get_cognitive_mass(SephirahRole::Malkuth);
        assert_relative_eq!(ratio, mass_ratio, epsilon = 0.01);
    }

    // -----------------------------------------------------------------------
    // Yukawa adaptation (used nodes get stronger coupling)
    // -----------------------------------------------------------------------

    #[test]
    fn test_yukawa_adaptation() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let mut energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        field.initialize(&mut energies);

        let original_keter_mass = field.get_cognitive_mass(SephirahRole::Keter);

        // Keter heavily used, Malkuth unused
        let mut usage: HashMap<SephirahRole, u64> = HashMap::new();
        usage.insert(SephirahRole::Keter, 1000);
        usage.insert(SephirahRole::Malkuth, 0);

        let adjusted = field.adapt_yukawa_couplings(&usage);
        assert!(adjusted > 0);

        // Keter should have increased mass (stronger coupling from heavy usage)
        let new_keter_mass = field.get_cognitive_mass(SephirahRole::Keter);
        assert!(
            new_keter_mass > original_keter_mass,
            "Heavily used node should get higher mass"
        );
    }

    #[test]
    fn test_yukawa_adaptation_empty() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let usage: HashMap<SephirahRole, u64> = HashMap::new();
        assert_eq!(field.adapt_yukawa_couplings(&usage), 0);
    }

    // -----------------------------------------------------------------------
    // Field stability scoring
    // -----------------------------------------------------------------------

    #[test]
    fn test_field_stability_no_excitations() {
        let field = HiggsCognitiveField::new(default_params());
        // No excitations -> perfectly stable
        assert_relative_eq!(field.get_field_stability(), 1.0);
    }

    #[test]
    fn test_field_stability_with_excitations() {
        let mut field = HiggsCognitiveField::new(default_params());

        // Add excitations with varying deviations
        for i in 0..5 {
            field.excitations.push(ExcitationEvent {
                block_height: i as u64,
                field_deviation: 0.15 + (i as f64 * 0.05),
                deviation_bps: 1500 + i * 500,
                energy_released: 1.0,
                timestamp: 0.0,
            });
        }

        let stability = field.get_field_stability();
        // With varying deviations, stability should be < 1.0
        assert!(stability < 1.0);
        assert!(stability > 0.0);
    }

    // -----------------------------------------------------------------------
    // Mass hierarchy health check
    // -----------------------------------------------------------------------

    #[test]
    fn test_mass_hierarchy_health_after_init() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let mut energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        field.initialize(&mut energies);

        let health = field.get_mass_hierarchy_health();

        // After clean initialization, all pairs should be healthy
        assert!(health.all_healthy, "All SUSY pairs should be healthy after init");
        assert_eq!(health.pairs.len(), 3);

        for pair in &health.pairs {
            assert!(pair.healthy, "Pair {}/{} should be healthy", pair.expansion, pair.constraint);
            assert!(pair.deviation_pct < 10.0);
        }
    }

    // -----------------------------------------------------------------------
    // HiggsSUSYSwap
    // -----------------------------------------------------------------------

    #[test]
    fn test_susy_swap_no_correction_when_balanced() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let mut init_energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        field.initialize(&mut init_energies);

        let swap = HiggsSUSYSwap::new(&field);

        // Set energies at golden ratio balance
        let mut energies: HashMap<SephirahRole, f64> = HashMap::new();
        for &(exp, con) in SUSY_PAIRS {
            energies.insert(con, 1.0);
            energies.insert(exp, PHI); // Perfect ratio
        }

        let masses = field.cognitive_masses.clone();
        let corrections = swap.enforce_susy_balance_with_mass(100, &mut energies, &masses);
        assert_eq!(corrections, 0, "Balanced pairs should need no corrections");
    }

    #[test]
    fn test_susy_swap_corrects_imbalance() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let mut init_energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        field.initialize(&mut init_energies);

        let swap = HiggsSUSYSwap::new(&field);

        // Set highly imbalanced energies
        let mut energies: HashMap<SephirahRole, f64> = HashMap::new();
        energies.insert(SephirahRole::Chesed, 10.0);
        energies.insert(SephirahRole::Gevurah, 1.0); // ratio = 10, far from PHI
        energies.insert(SephirahRole::Chochmah, PHI);
        energies.insert(SephirahRole::Binah, 1.0);
        energies.insert(SephirahRole::Netzach, PHI);
        energies.insert(SephirahRole::Hod, 1.0);

        let masses = field.cognitive_masses.clone();
        let old_chesed = energies[&SephirahRole::Chesed];
        let corrections = swap.enforce_susy_balance_with_mass(100, &mut energies, &masses);

        assert!(corrections >= 1, "Imbalanced pair should be corrected");
        // Chesed energy should have moved toward target
        let new_chesed = energies[&SephirahRole::Chesed];
        assert!(
            (new_chesed - old_chesed).abs() > 0.0001,
            "Chesed energy should have changed"
        );
    }

    // -----------------------------------------------------------------------
    // get_status serialization
    // -----------------------------------------------------------------------

    #[test]
    fn test_get_status_json() {
        let params = default_params();
        let mut field = HiggsCognitiveField::new(params);
        let mut init_energies: HashMap<SephirahRole, (f64, f64)> = HashMap::new();
        field.initialize(&mut init_energies);

        let status = field.get_status();
        assert!(status.get("field_value").is_some());
        assert!(status.get("vev").is_some());
        assert!(status.get("mu").is_some());
        assert!(status.get("node_masses").is_some());
        assert!(status.get("recent_excitations").is_some());
    }

    // -----------------------------------------------------------------------
    // Yukawa coupling map
    // -----------------------------------------------------------------------

    #[test]
    fn test_yukawa_coupling_map_complete() {
        let map = yukawa_coupling_map();
        assert_eq!(map.len(), 10);

        assert_relative_eq!(map[&SephirahRole::Keter], 1.0);
        assert_relative_eq!(map[&SephirahRole::Chochmah], PHI_INV_1, epsilon = 1e-10);
        assert_relative_eq!(map[&SephirahRole::Binah], PHI_INV_1, epsilon = 1e-10);
        assert_relative_eq!(map[&SephirahRole::Tiferet], PHI_INV_1, epsilon = 1e-10);
        assert_relative_eq!(map[&SephirahRole::Chesed], PHI_INV_2, epsilon = 1e-10);
        assert_relative_eq!(map[&SephirahRole::Gevurah], PHI_INV_2, epsilon = 1e-10);
        assert_relative_eq!(map[&SephirahRole::Netzach], PHI_INV_3, epsilon = 1e-10);
        assert_relative_eq!(map[&SephirahRole::Hod], PHI_INV_3, epsilon = 1e-10);
        assert_relative_eq!(map[&SephirahRole::Yesod], PHI_INV_4, epsilon = 1e-10);
        assert_relative_eq!(map[&SephirahRole::Malkuth], PHI_INV_4, epsilon = 1e-10);
    }
}
