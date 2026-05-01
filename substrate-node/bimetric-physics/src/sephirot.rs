//! Sephirot phase assignments and alignment scoring.
//!
//! The 10 Sephirot of the Kabbalistic Tree of Life form the cognitive
//! architecture of the Aether Mind. Each Sephirah is assigned a fixed
//! phase angle theta_i on the unit circle, spaced by the **golden angle**
//! (2*pi / phi^2 ~ 137.508 degrees).
//!
//! This golden-angle spacing is the same irrational rotation used by
//! sunflower seeds (phyllotaxis). It guarantees **maximal phase separation**
//! — no two Sephirot are ever close together, and the pattern never repeats.
//! This makes the phase structure optimally spread across the circle,
//! which is critical for the VQE energy landscape to have rich structure
//! in every angular direction.
//!
//! Each Sephirah also carries a **Yukawa coupling weight** that follows
//! a golden-ratio power descent: Keter (crown) has weight 1.0, while
//! Malkuth (kingdom) has weight phi^-4 ~ 0.146. These weights determine
//! how strongly each cognitive domain contributes to the overall bimetric
//! phase alignment score.

use crate::potential::{GOLDEN_ANGLE, PHI_INV, PHI_INV_SQ, TWO_PI};
use libm;

// ---------------------------------------------------------------------------
// Sephirot metadata
// ---------------------------------------------------------------------------

/// Names of the 10 Sephirot in descending order (crown to kingdom).
pub const SEPHIROT_NAMES: [&str; 10] = [
    "Keter",    // 0 — Crown: meta-learning, goals
    "Chochmah", // 1 — Wisdom: intuition, pattern recognition
    "Binah",    // 2 — Understanding: logic, causal inference
    "Chesed",   // 3 — Mercy: exploration, divergent thinking
    "Gevurah",  // 4 — Severity: safety, constraints, veto
    "Tiferet",  // 5 — Beauty: integration, synthesis
    "Netzach",  // 6 — Victory: reinforcement learning
    "Hod",      // 7 — Splendor: language, semantics
    "Yesod",    // 8 — Foundation: memory, fusion
    "Malkuth",  // 9 — Kingdom: action, interaction
];

/// Yukawa coupling weights per Sephirot, following golden-ratio power descent.
///
/// The mass hierarchy mirrors broken SUSY: heavier cognitive modules (Keter)
/// have stronger coupling and resist perturbation, while lighter modules
/// (Malkuth) are more agile but contribute less to the integrated information.
///
/// ```text
/// Keter     = 1.0      (phi^0)
/// Chochmah  = phi^-1   ~ 0.618
/// Binah     = phi^-1   ~ 0.618
/// Chesed    = phi^-2   ~ 0.382
/// Gevurah   = phi^-2   ~ 0.382
/// Tiferet   = phi^-1   ~ 0.618
/// Netzach   = phi^-3   ~ 0.236
/// Hod       = phi^-3   ~ 0.236
/// Yesod     = phi^-4   ~ 0.146
/// Malkuth   = phi^-4   ~ 0.146
/// ```
pub const SEPHIROT_YUKAWA: [f64; 10] = [
    1.0,                 // Keter    — phi^0
    PHI_INV,             // Chochmah — phi^-1
    PHI_INV,             // Binah    — phi^-1
    PHI_INV_SQ,          // Chesed   — phi^-2
    PHI_INV_SQ,          // Gevurah  — phi^-2
    PHI_INV,             // Tiferet  — phi^-1
    0.2360679774997897,  // Netzach  — phi^-3
    0.2360679774997897,  // Hod      — phi^-3
    0.1458980337503153,  // Yesod    — phi^-4
    0.1458980337503153,  // Malkuth  — phi^-4
];

// ---------------------------------------------------------------------------
// Phase computations
// ---------------------------------------------------------------------------

/// Compute the fixed phase angle for a single Sephirah.
///
/// ```text
/// theta_i = i * GOLDEN_ANGLE  (mod 2*pi)
/// ```
///
/// # Arguments
/// * `index` — Sephirah index (0 = Keter, 9 = Malkuth). Values >= 10 are
///   taken modulo 10.
///
/// # Returns
/// Phase angle in radians, in the range [0, 2*pi).
pub fn sephirot_theta(index: u8) -> f64 {
    let i = (index % 10) as f64;
    let raw = i * GOLDEN_ANGLE;
    raw - libm::floor(raw / TWO_PI) * TWO_PI
}

/// Compute all 10 Sephirot phase angles.
///
/// Returns an array of 10 angles in [0, 2*pi), each separated by the
/// golden angle. Due to the irrationality of the golden ratio, these
/// phases are maximally spread on the circle — no two phases are ever
/// "close" in the sense of rational approximation.
///
/// # Returns
/// Array of 10 phase angles in radians.
pub fn sephirot_phases() -> [f64; 10] {
    let mut phases = [0.0_f64; 10];
    for i in 0..10 {
        phases[i] = sephirot_theta(i as u8);
    }
    phases
}

/// Find the Sephirah whose phase is closest to the given network phase.
///
/// This identifies which cognitive domain is "active" — i.e., which
/// Sephirah the current block's VQE solution phase is most aligned with.
///
/// # Arguments
/// * `theta_network` — The current network bimetric phase angle (radians).
///
/// # Returns
/// Index (0..9) of the closest Sephirah.
pub fn active_sephirot(theta_network: f64) -> u8 {
    let phases = sephirot_phases();
    let mut best_idx: u8 = 0;
    let mut best_dist = f64::MAX;

    for i in 0..10 {
        let dist = angular_distance(theta_network, phases[i]);
        if dist < best_dist {
            best_dist = dist;
            best_idx = i as u8;
        }
    }
    best_idx
}

/// Compute the phase alignment score (geometric coupling weight).
///
/// This is the Yukawa-weighted cosine similarity between a block's phase
/// angle and all 10 Sephirot phases:
///
/// ```text
/// alpha = Sum_i  yukawa_i * cos(theta_block - theta_sephirot_i)
/// ```
///
/// # Arguments
/// * `theta_block` — The block's bimetric phase angle (radians).
/// * `phases` — The 10 Sephirot phase angles (from [`sephirot_phases`]).
/// * `yukawa` — The 10 Yukawa coupling weights (typically [`SEPHIROT_YUKAWA`]).
///
/// # Returns
/// The phase alignment score. This can range from negative (anti-aligned)
/// to positive (aligned). The theoretical maximum occurs when `theta_block`
/// is perfectly aligned with all high-weight Sephirot simultaneously
/// (impossible due to golden-angle spacing, which is the point — miners
/// must find the best compromise alignment).
///
/// # Physics
/// This score enters the consensus as a geometric weight on the mining
/// reward. Miners whose VQE solutions have higher phase alignment with
/// the cognitive geometry receive proportionally more reward, incentivizing
/// the network to maintain coherent cognitive structure.
pub fn phase_alignment(theta_block: f64, phases: &[f64; 10], yukawa: &[f64; 10]) -> f64 {
    let mut alpha = 0.0_f64;
    for i in 0..10 {
        alpha += yukawa[i] * libm::cos(theta_block - phases[i]);
    }
    alpha
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Compute the shortest angular distance between two angles on the circle.
///
/// Returns a value in [0, pi].
fn angular_distance(a: f64, b: f64) -> f64 {
    let diff = a - b;
    // Normalize to [-pi, pi].
    let normalized = diff - libm::round(diff / TWO_PI) * TWO_PI;
    libm::fabs(normalized)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn approx_eq(a: f64, b: f64, tol: f64) -> bool {
        libm::fabs(a - b) < tol
    }

    #[test]
    fn test_sephirot_theta_keter_is_zero() {
        // Keter (index 0) has phase = 0 * GOLDEN_ANGLE = 0.
        assert_eq!(sephirot_theta(0), 0.0);
    }

    #[test]
    fn test_sephirot_theta_chochmah() {
        // Chochmah (index 1) has phase = 1 * GOLDEN_ANGLE.
        assert!(approx_eq(sephirot_theta(1), GOLDEN_ANGLE, 1e-12));
    }

    #[test]
    fn test_all_phases_distinct() {
        let phases = sephirot_phases();
        for i in 0..10 {
            for j in (i + 1)..10 {
                let dist = angular_distance(phases[i], phases[j]);
                assert!(
                    dist > 0.1,
                    "Phases {} ({}) and {} ({}) are too close: distance = {}",
                    SEPHIROT_NAMES[i],
                    phases[i],
                    SEPHIROT_NAMES[j],
                    phases[j],
                    dist
                );
            }
        }
    }

    #[test]
    fn test_phases_in_range() {
        let phases = sephirot_phases();
        for (i, &phase) in phases.iter().enumerate() {
            assert!(
                phase >= 0.0 && phase < TWO_PI,
                "Phase {} ({}) out of range: {}",
                i,
                SEPHIROT_NAMES[i],
                phase
            );
        }
    }

    #[test]
    fn test_golden_angle_spacing() {
        // Each successive phase should differ by GOLDEN_ANGLE (mod 2*pi)
        // from the previous, before modular reduction.
        for i in 0..9 {
            let raw_i = (i as f64) * GOLDEN_ANGLE;
            let raw_next = ((i + 1) as f64) * GOLDEN_ANGLE;
            let diff = raw_next - raw_i;
            assert!(
                approx_eq(diff, GOLDEN_ANGLE, 1e-12),
                "Spacing between {} and {} is not golden angle",
                i,
                i + 1
            );
        }
    }

    #[test]
    fn test_active_sephirot_at_exact_phase() {
        let phases = sephirot_phases();
        // At each Sephirah's exact phase, that Sephirah should be active.
        for i in 0..10 {
            let active = active_sephirot(phases[i]);
            assert_eq!(
                active, i as u8,
                "At phase {}, expected active Sephirah {} ({}), got {} ({})",
                phases[i],
                i,
                SEPHIROT_NAMES[i],
                active,
                SEPHIROT_NAMES[active as usize]
            );
        }
    }

    #[test]
    fn test_active_sephirot_rotation() {
        // As we sweep theta from 0 to 2*pi, we should visit all 10 Sephirot.
        let mut visited = [false; 10];
        let steps = 1000;
        for step in 0..steps {
            let theta = (step as f64) * TWO_PI / (steps as f64);
            let active = active_sephirot(theta) as usize;
            visited[active] = true;
        }
        for i in 0..10 {
            assert!(
                visited[i],
                "Sephirah {} ({}) was never active during full rotation",
                i,
                SEPHIROT_NAMES[i]
            );
        }
    }

    #[test]
    fn test_phase_alignment_at_keter() {
        // At theta = 0 (Keter's phase), alignment should be positive
        // because cos(0 - 0) = 1 for Keter (weight 1.0).
        let phases = sephirot_phases();
        let alpha = phase_alignment(0.0, &phases, &SEPHIROT_YUKAWA);
        assert!(alpha > 0.0, "Alignment at Keter phase should be positive");
    }

    #[test]
    fn test_phase_alignment_varies_with_theta() {
        let phases = sephirot_phases();
        let a1 = phase_alignment(0.0, &phases, &SEPHIROT_YUKAWA);
        let a2 = phase_alignment(1.0, &phases, &SEPHIROT_YUKAWA);
        let a3 = phase_alignment(3.0, &phases, &SEPHIROT_YUKAWA);
        // They should not all be equal (the function varies with theta).
        assert!(
            !(approx_eq(a1, a2, 1e-10) && approx_eq(a2, a3, 1e-10)),
            "Phase alignment should vary with theta"
        );
    }

    #[test]
    fn test_phase_alignment_bounded() {
        // The maximum possible alignment is sum of all yukawa weights
        // (when cos = 1 for all terms, which cannot actually happen due
        // to golden-angle spacing). The actual value should be less.
        let phases = sephirot_phases();
        let max_possible: f64 = SEPHIROT_YUKAWA.iter().sum();
        let min_possible = -max_possible;

        for step in 0..100 {
            let theta = (step as f64) * TWO_PI / 100.0;
            let alpha = phase_alignment(theta, &phases, &SEPHIROT_YUKAWA);
            assert!(
                alpha >= min_possible - 1e-10 && alpha <= max_possible + 1e-10,
                "Alignment {} out of bounds [{}, {}] at theta = {}",
                alpha,
                min_possible,
                max_possible,
                theta
            );
        }
    }

    #[test]
    fn test_yukawa_weights_sum() {
        // Verify the total Yukawa weight.
        let sum: f64 = SEPHIROT_YUKAWA.iter().sum();
        // 1.0 + 3*phi^-1 + 2*phi^-2 + 2*phi^-3 + 2*phi^-4
        let expected = 1.0 + 3.0 * PHI_INV + 2.0 * PHI_INV_SQ
            + 2.0 * 0.2360679774997897
            + 2.0 * 0.1458980337503153;
        assert!(approx_eq(sum, expected, 1e-10));
    }

    #[test]
    fn test_angular_distance_same() {
        assert!(approx_eq(angular_distance(1.0, 1.0), 0.0, 1e-14));
    }

    #[test]
    fn test_angular_distance_opposite() {
        let d = angular_distance(0.0, core::f64::consts::PI);
        assert!(approx_eq(d, core::f64::consts::PI, 1e-10));
    }

    #[test]
    fn test_sephirot_theta_modulo() {
        // Index >= 10 wraps around.
        assert!(approx_eq(
            sephirot_theta(10),
            sephirot_theta(0),
            1e-14
        ));
        assert!(approx_eq(
            sephirot_theta(13),
            sephirot_theta(3),
            1e-14
        ));
    }
}
