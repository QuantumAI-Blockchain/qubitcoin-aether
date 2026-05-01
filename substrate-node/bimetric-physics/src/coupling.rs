//! Geometric weight computation from VQE solution parameters.
//!
//! The VQE (Variational Quantum Eigensolver) produces a parameter vector
//! that encodes the rotation angles applied to qubits in the ansatz circuit.
//! This module extracts a single **bimetric phase angle** from that vector
//! and computes the **geometric coupling weight** — a measure of how well
//! the miner's solution aligns with the network's cognitive phase geometry.
//!
//! # Phase extraction
//!
//! The VQE parameter vector lives in a high-dimensional space (typically 12
//! parameters for a 4-qubit hardware-efficient ansatz with 3 layers). We
//! project this vector onto a 2D plane by treating even-indexed parameters
//! as the "real" component and odd-indexed as the "imaginary" component:
//!
//! ```text
//! Re = Sum params[0], params[2], params[4], ...
//! Im = Sum params[1], params[3], params[5], ...
//! theta_block = atan2(Im, Re)
//! ```
//!
//! This is equivalent to computing the phase of the discrete Fourier
//! transform of the parameter vector at the Nyquist frequency — it
//! captures the dominant alternating pattern in the solution.
//!
//! # Geometric weight
//!
//! The geometric weight is the Yukawa-weighted phase alignment between
//! the block's solution phase and all 10 Sephirot cognitive phases:
//!
//! ```text
//! alpha_block = Sum_i  yukawa_i * cos(theta_block - theta_sephirot_i)
//! ```
//!
//! This value enters the consensus as a quality multiplier on the mining
//! reward, incentivizing miners to find VQE solutions that are not just
//! low-energy but also geometrically coherent with the cognitive architecture.

#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

use crate::sephirot::{phase_alignment, sephirot_phases, SEPHIROT_YUKAWA};
use libm;

/// Compute the bimetric phase angle of a VQE solution.
///
/// The VQE parameter vector encodes rotation angles applied to qubits.
/// We extract a single "phase" by treating even-indexed params as the
/// real component and odd-indexed as the imaginary component, then
/// taking atan2. This is mathematically equivalent to projecting the
/// solution onto the bimetric mixing direction.
///
/// # Arguments
/// * `params` — VQE solution parameter vector. Typically 12 elements for
///   a 4-qubit, 3-layer hardware-efficient ansatz. Can be any length >= 1.
///
/// # Returns
/// Phase angle in radians, in the range (-pi, pi].
/// Returns 0.0 if `params` is empty.
///
/// # Determinism
/// This function is fully deterministic: same params always produce the
/// same phase angle. No randomness, no floating-point non-determinism
/// beyond IEEE 754 guarantees.
pub fn solution_phase(params: &[f64]) -> f64 {
    if params.is_empty() {
        return 0.0;
    }

    let mut real_sum = 0.0_f64;
    let mut imag_sum = 0.0_f64;

    for (i, &p) in params.iter().enumerate() {
        if i % 2 == 0 {
            real_sum += p;
        } else {
            imag_sum += p;
        }
    }

    // atan2(0, 0) returns 0.0 in libm, which is a valid degenerate case
    // (all-zero params have no preferred phase direction).
    libm::atan2(imag_sum, real_sum)
}

/// Compute the full geometric weight for a mining proof.
///
/// This is the primary function used by the consensus layer. Given a
/// miner's VQE solution parameters, it computes how well the solution
/// aligns with the network's Sephirot phase geometry:
///
/// ```text
/// alpha_block = phase_alignment(solution_phase(params), sephirot_phases, yukawa)
/// ```
///
/// # Arguments
/// * `params` — VQE solution parameter vector.
///
/// # Returns
/// The geometric coupling weight. Higher values indicate better alignment
/// with the cognitive architecture. The value is bounded by the sum of
/// Yukawa weights (positive and negative).
///
/// # Usage in consensus
/// The geometric weight multiplies the base mining reward:
/// ```text
/// reward = base_reward * (1 + beta * alpha_block)
/// ```
/// where `beta` is a consensus-configurable scaling factor.
pub fn geometric_weight(params: &[f64]) -> f64 {
    let theta = solution_phase(params);
    let phases = sephirot_phases();
    phase_alignment(theta, &phases, &SEPHIROT_YUKAWA)
}

/// Compute geometric weight from scaled i64 parameters (on-chain format).
///
/// Parameters are stored on-chain as i64 scaled by 10^12. This function
/// unscales them to f64 and delegates to `geometric_weight`.
///
/// # Arguments
/// * `params_scaled` — VQE parameters as i64 × 10^12 (on-chain representation).
///
/// # Returns
/// The geometric coupling weight (same as `geometric_weight`).
pub fn geometric_weight_from_scaled(params_scaled: &[i64]) -> f64 {
    const SCALE: f64 = 1_000_000_000_000.0;
    let params: Vec<f64> = params_scaled
        .iter()
        .map(|&p| p as f64 / SCALE)
        .collect();
    geometric_weight(&params)
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
    fn test_solution_phase_empty() {
        assert_eq!(solution_phase(&[]), 0.0);
    }

    #[test]
    fn test_solution_phase_single_element() {
        // Single element (index 0 = even = real). Phase = atan2(0, p).
        assert!(approx_eq(solution_phase(&[1.0]), 0.0, 1e-14));
        assert!(approx_eq(
            solution_phase(&[-1.0]),
            core::f64::consts::PI,
            1e-14
        ));
    }

    #[test]
    fn test_solution_phase_two_elements() {
        // params[0] = real, params[1] = imag.
        // atan2(1, 1) = pi/4
        assert!(approx_eq(
            solution_phase(&[1.0, 1.0]),
            core::f64::consts::FRAC_PI_4,
            1e-14
        ));
        // atan2(1, 0) = pi/2
        assert!(approx_eq(
            solution_phase(&[0.0, 1.0]),
            core::f64::consts::FRAC_PI_2,
            1e-14
        ));
    }

    #[test]
    fn test_solution_phase_deterministic() {
        let params = [0.3, -0.7, 1.2, 0.5, -0.1, 0.8, 0.4, -0.3, 0.9, 0.1, -0.6, 0.2];
        let phase1 = solution_phase(&params);
        let phase2 = solution_phase(&params);
        assert_eq!(phase1, phase2, "solution_phase must be deterministic");
    }

    #[test]
    fn test_solution_phase_range() {
        // Phase should be in (-pi, pi].
        let test_cases: &[&[f64]] = &[
            &[1.0, 0.0],
            &[0.0, 1.0],
            &[-1.0, 0.0],
            &[0.0, -1.0],
            &[1.0, 1.0, 1.0, 1.0],
            &[-3.0, 2.0, -1.0, 4.0, -5.0, 6.0],
        ];
        for params in test_cases {
            let phase = solution_phase(params);
            assert!(
                phase >= -core::f64::consts::PI && phase <= core::f64::consts::PI,
                "Phase {} out of range for params {:?}",
                phase,
                params
            );
        }
    }

    #[test]
    fn test_solution_phase_zero_params() {
        // All zeros => atan2(0, 0) = 0.
        assert_eq!(solution_phase(&[0.0, 0.0, 0.0, 0.0]), 0.0);
    }

    #[test]
    fn test_geometric_weight_deterministic() {
        let params = [0.3, -0.7, 1.2, 0.5, -0.1, 0.8, 0.4, -0.3, 0.9, 0.1, -0.6, 0.2];
        let w1 = geometric_weight(&params);
        let w2 = geometric_weight(&params);
        assert_eq!(w1, w2, "geometric_weight must be deterministic");
    }

    #[test]
    fn test_geometric_weight_bounded() {
        // The geometric weight is a sum of yukawa_i * cos(...), so it's
        // bounded by [-sum(yukawa), +sum(yukawa)].
        let max_bound: f64 = SEPHIROT_YUKAWA.iter().sum();

        let test_params: &[&[f64]] = &[
            &[0.0],
            &[1.0, 2.0, 3.0, 4.0],
            &[-1.0, -2.0, -3.0, -4.0, -5.0, -6.0],
            &[100.0, -100.0, 50.0, -50.0],
            &[0.3, -0.7, 1.2, 0.5, -0.1, 0.8, 0.4, -0.3, 0.9, 0.1, -0.6, 0.2],
        ];

        for params in test_params {
            let w = geometric_weight(params);
            assert!(
                w >= -max_bound - 1e-10 && w <= max_bound + 1e-10,
                "Weight {} out of bounds [{}, {}] for params {:?}",
                w,
                -max_bound,
                max_bound,
                params
            );
        }
    }

    #[test]
    fn test_geometric_weight_varies() {
        // Different params should (generally) produce different weights.
        let w1 = geometric_weight(&[1.0, 0.0, 0.0, 0.0]);
        let w2 = geometric_weight(&[0.0, 1.0, 0.0, 0.0]);
        let w3 = geometric_weight(&[0.0, 0.0, 1.0, 0.0]);
        // At least some should differ.
        assert!(
            !approx_eq(w1, w2, 1e-10) || !approx_eq(w2, w3, 1e-10),
            "Geometric weight should vary with different params"
        );
    }

    #[test]
    fn test_geometric_weight_opposite_params() {
        // Negating all params flips the phase by pi, so the weight
        // should generally differ (unless the alignment is symmetric).
        let params_pos = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0];
        let params_neg: [f64; 6] = [-1.0, -2.0, -3.0, -4.0, -5.0, -6.0];
        let w_pos = geometric_weight(&params_pos);
        let w_neg = geometric_weight(&params_neg);
        // Negating all params adds pi to the phase, so cos changes.
        // They should not be equal (in general).
        // Actually, atan2(-Im, -Re) = atan2(Im, Re) + pi (or - pi),
        // so the alignment will differ.
        assert!(
            !approx_eq(w_pos, w_neg, 1e-10),
            "Opposite params should produce different geometric weights"
        );
    }

    #[test]
    fn test_geometric_weight_typical_vqe() {
        // A typical 12-parameter VQE solution.
        let params = [
            0.5236, -0.3142, 1.0472, 0.7854, -0.2618, 0.9425,
            0.1745, -0.6981, 0.4363, 0.8727, -0.5236, 0.3491,
        ];
        let w = geometric_weight(&params);
        // Should be a finite number in the valid range.
        assert!(w.is_finite(), "Weight should be finite, got {}", w);
        let max_bound: f64 = SEPHIROT_YUKAWA.iter().sum();
        assert!(w >= -max_bound && w <= max_bound);
    }

    #[test]
    fn test_phase_alignment_consistency() {
        // Verify that geometric_weight matches manual computation.
        let params = [1.0, 0.5];
        let theta = solution_phase(&params);
        let phases = sephirot_phases();
        let alpha_manual = phase_alignment(theta, &phases, &SEPHIROT_YUKAWA);
        let alpha_fn = geometric_weight(&params);
        assert!(
            approx_eq(alpha_manual, alpha_fn, 1e-14),
            "geometric_weight should equal manual phase_alignment computation"
        );
    }

    #[test]
    fn test_solution_phase_even_odd_split() {
        // Verify the even/odd split manually.
        // params = [1, 2, 3, 4, 5, 6]
        // even indices (0,2,4): 1 + 3 + 5 = 9 (real)
        // odd indices (1,3,5):  2 + 4 + 6 = 12 (imag)
        // phase = atan2(12, 9)
        let params = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0];
        let expected = libm::atan2(12.0, 9.0);
        assert!(approx_eq(solution_phase(&params), expected, 1e-14));
    }
}
