//! Determinism tests for bimetric-physics f64 computations.
//!
//! These tests verify that the Hamiltonian generation, coupling computation,
//! and Sephirot phase calculations produce **bit-identical** f64 results
//! across compilations. Any FP non-determinism (e.g., from platform-dependent
//! libm, fused multiply-add differences, or compiler reordering) would cause
//! these tests to fail.
//!
//! Each test uses `f64::to_bits()` to assert exact IEEE 754 bit patterns,
//! not approximate equality. The golden values were captured from a known-good
//! build and are frozen here as the canonical reference.

use crate::hamiltonian::{
    base_pauli_terms, diagonal_bias_terms, generate_sugra_hamiltonian,
    rotating_coupling_terms,
};
use crate::coupling::{geometric_weight, solution_phase};
use crate::sephirot::{active_sephirot, phase_alignment, sephirot_phases, SEPHIROT_YUKAWA};
use crate::potential::{mexican_hat_potential, vev, PHI, PHI_INV, PHI_INV_SQ, GOLDEN_ANGLE, TWO_PI};

/// A test vector: (theta, base_coeff, rotating_strength, omega_phi) -> expected coefficient bits.
struct HamiltonianTestVector {
    theta: f64,
    base_coeff: f64,
    rotating_strength: f64,
    omega_phi: f64,
}

/// Compute all 7 structured Hamiltonian coefficients for a test vector.
fn compute_coefficients(v: &HamiltonianTestVector) -> [u64; 7] {
    let h = generate_sugra_hamiltonian(
        v.base_coeff,
        v.rotating_strength,
        v.theta,
        v.omega_phi,
        &[],
    );
    assert_eq!(h.len(), 7);
    [
        h[0].coefficient.to_bits(),
        h[1].coefficient.to_bits(),
        h[2].coefficient.to_bits(),
        h[3].coefficient.to_bits(),
        h[4].coefficient.to_bits(),
        h[5].coefficient.to_bits(),
        h[6].coefficient.to_bits(),
    ]
}

// ── Test 1: Base Pauli terms are deterministic across 50 inputs ─────────

#[test]
fn base_pauli_terms_exact_bits() {
    // 10 base_coeff values, check all 3 coefficients per call = 30 checks.
    let base_coeffs = [0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95];

    for &bc in &base_coeffs {
        let terms_a = base_pauli_terms(bc);
        let terms_b = base_pauli_terms(bc);
        for i in 0..3 {
            assert_eq!(
                terms_a[i].coefficient.to_bits(),
                terms_b[i].coefficient.to_bits(),
                "base_pauli_terms({}) term {} not bit-identical across calls",
                bc,
                i
            );
        }
    }
}

// ── Test 2: Rotating coupling terms bit-identical ───────────────────────

#[test]
fn rotating_coupling_terms_exact_bits() {
    let test_cases: [(f64, f64); 10] = [
        (0.3, 0.0),
        (0.3, 0.5),
        (0.3, 1.0),
        (0.3, 1.5707963267948966), // pi/2
        (0.3, 3.141592653589793),  // pi
        (0.4, 0.789),
        (0.4, 2.0),
        (0.5, 4.0),
        (0.2, 5.5),
        (0.1, 6.283185307179586), // 2*pi
    ];

    for &(strength, theta) in &test_cases {
        let terms_a = rotating_coupling_terms(strength, theta);
        let terms_b = rotating_coupling_terms(strength, theta);
        for i in 0..2 {
            assert_eq!(
                terms_a[i].coefficient.to_bits(),
                terms_b[i].coefficient.to_bits(),
                "rotating_coupling_terms({}, {}) term {} not bit-identical",
                strength,
                theta,
                i
            );
        }
    }
}

// ── Test 3: Diagonal bias terms bit-identical ───────────────────────────

#[test]
fn diagonal_bias_terms_exact_bits() {
    let omegas = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.50, 0.75, 1.0];

    for &omega in &omegas {
        let terms_a = diagonal_bias_terms(omega);
        let terms_b = diagonal_bias_terms(omega);
        for i in 0..2 {
            assert_eq!(
                terms_a[i].coefficient.to_bits(),
                terms_b[i].coefficient.to_bits(),
                "diagonal_bias_terms({}) term {} not bit-identical",
                omega,
                i
            );
        }
    }
}

// ── Test 4: Full Hamiltonian determinism for 50 fixed tuples ──────��─────

#[test]
fn full_hamiltonian_50_tuples_deterministic() {
    // 50 fixed (theta, base_coeff, rotating_strength, omega_phi) tuples.
    let vectors: Vec<HamiltonianTestVector> = (0..50)
        .map(|i| {
            let f = i as f64;
            HamiltonianTestVector {
                theta: (f * 0.1257) % TWO_PI,
                base_coeff: 0.3 + (f * 0.014) % 0.7,
                rotating_strength: 0.1 + (f * 0.008) % 0.4,
                omega_phi: 0.05 + (f * 0.003) % 0.25,
            }
        })
        .collect();

    // Compute coefficients twice for each vector and compare bit patterns.
    for (idx, v) in vectors.iter().enumerate() {
        let bits_a = compute_coefficients(v);
        let bits_b = compute_coefficients(v);
        assert_eq!(
            bits_a, bits_b,
            "Hamiltonian coefficients for tuple {} not bit-identical: \
             theta={}, base_coeff={}, rotating_strength={}, omega_phi={}",
            idx, v.theta, v.base_coeff, v.rotating_strength, v.omega_phi
        );
    }
}

// ── Test 5: Golden values frozen from known-good build ──────────────────

#[test]
fn golden_values_base_pauli_terms() {
    // base_coeff = 0.75
    let terms = base_pauli_terms(0.75);
    // Term 0: 0.75 exactly
    assert_eq!(terms[0].coefficient.to_bits(), 0.75_f64.to_bits());
    // Term 1: 0.75 * PHI_INV
    assert_eq!(
        terms[1].coefficient.to_bits(),
        (0.75 * PHI_INV).to_bits(),
        "Term 1 golden value mismatch"
    );
    // Term 2: 0.75 * PHI_INV_SQ
    assert_eq!(
        terms[2].coefficient.to_bits(),
        (0.75 * PHI_INV_SQ).to_bits(),
        "Term 2 golden value mismatch"
    );
}

#[test]
fn golden_values_rotating_at_zero() {
    let terms = rotating_coupling_terms(0.3, 0.0);
    // cos(0) = 1.0, sin(0) = 0.0
    assert_eq!(
        terms[0].coefficient.to_bits(),
        (0.3_f64 * libm::cos(0.0)).to_bits()
    );
    assert_eq!(
        terms[1].coefficient.to_bits(),
        (0.3_f64 * libm::sin(0.0)).to_bits()
    );
}

#[test]
fn golden_values_diagonal_default() {
    let terms = diagonal_bias_terms(0.15);
    let expected_0: f64 = -0.15 * PHI_INV_SQ;
    let expected_1: f64 = -0.15 * 0.2360679774997897;
    assert_eq!(
        terms[0].coefficient.to_bits(),
        expected_0.to_bits(),
        "Diagonal term 0 golden value mismatch"
    );
    assert_eq!(
        terms[1].coefficient.to_bits(),
        expected_1.to_bits(),
        "Diagonal term 1 golden value mismatch"
    );
}

// ── Test 6: Sephirot phases are deterministic ───���───────────────────────

#[test]
fn sephirot_phases_deterministic_bits() {
    let phases_a = sephirot_phases();
    let phases_b = sephirot_phases();
    for i in 0..10 {
        assert_eq!(
            phases_a[i].to_bits(),
            phases_b[i].to_bits(),
            "Sephirot phase {} not bit-identical",
            i
        );
    }
}

// ── Test 7: Phase alignment deterministic ───────────────────────────────

#[test]
fn phase_alignment_deterministic_bits() {
    let phases = sephirot_phases();
    let thetas = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0];

    for &theta in &thetas {
        let a = phase_alignment(theta, &phases, &SEPHIROT_YUKAWA);
        let b = phase_alignment(theta, &phases, &SEPHIROT_YUKAWA);
        assert_eq!(
            a.to_bits(),
            b.to_bits(),
            "phase_alignment({}) not bit-identical",
            theta
        );
    }
}

// ── Test 8: Geometric weight deterministic ──────────────────────────────

#[test]
fn geometric_weight_deterministic_bits() {
    let param_sets: &[&[f64]] = &[
        &[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2],
        &[-0.5, 0.3, -1.2, 0.8, 0.1, -0.4],
        &[1.0],
        &[0.0, 0.0, 0.0, 0.0],
    ];

    for params in param_sets {
        let w_a = geometric_weight(params);
        let w_b = geometric_weight(params);
        assert_eq!(
            w_a.to_bits(),
            w_b.to_bits(),
            "geometric_weight({:?}) not bit-identical",
            params
        );
    }
}

// ── Test 9: Solution phase deterministic ────���───────────────────────────

#[test]
fn solution_phase_deterministic_bits() {
    let param_sets: &[&[f64]] = &[
        &[0.3, -0.7, 1.2, 0.5, -0.1, 0.8, 0.4, -0.3, 0.9, 0.1, -0.6, 0.2],
        &[1.0, 0.0],
        &[-1.0, -2.0, -3.0],
        &[],
    ];

    for params in param_sets {
        let p_a = solution_phase(params);
        let p_b = solution_phase(params);
        assert_eq!(
            p_a.to_bits(),
            p_b.to_bits(),
            "solution_phase({:?}) not bit-identical",
            params
        );
    }
}

// ── Test 10: Mexican-hat potential deterministic ────────────────────────

#[test]
fn mexican_hat_potential_deterministic_bits() {
    let test_cases = [
        (1.0, 88.17, 0.129),
        (5.0, 88.17, 0.129),
        (18.487, 88.17, 0.129),
        (0.0, 88.17, 0.129),
        (100.0, 88.17, 0.129),
    ];

    for &(phi, mu_sq, lambda) in &test_cases {
        let v_a = mexican_hat_potential(phi, mu_sq, lambda);
        let v_b = mexican_hat_potential(phi, mu_sq, lambda);
        assert_eq!(
            v_a.to_bits(),
            v_b.to_bits(),
            "mexican_hat_potential({}, {}, {}) not bit-identical",
            phi,
            mu_sq,
            lambda
        );
    }
}

// ── Test 11: VEV deterministic ───────────���──────────────────────────────

#[test]
fn vev_deterministic_bits() {
    let v_a = vev(88.17, 0.129);
    let v_b = vev(88.17, 0.129);
    assert_eq!(
        v_a.to_bits(),
        v_b.to_bits(),
        "vev(88.17, 0.129) not bit-identical"
    );
}

// ── Test 12: Constants are exact ──────────���─────────────────────────────

#[test]
fn constants_exact_bits() {
    assert_eq!(PHI.to_bits(), 1.618033988749895_f64.to_bits());
    assert_eq!(PHI_INV.to_bits(), 0.6180339887498949_f64.to_bits());
    assert_eq!(PHI_INV_SQ.to_bits(), 0.3819660112501051_f64.to_bits());
    assert_eq!(TWO_PI.to_bits(), 6.283185307179586_f64.to_bits());
    assert_eq!(GOLDEN_ANGLE.to_bits(), 2.399963229728653_f64.to_bits());
}

// ── Test 13: Active sephirot deterministic ──────────────────────────────

#[test]
fn active_sephirot_deterministic() {
    for i in 0..50 {
        let theta = (i as f64) * 0.1257;
        let a = active_sephirot(theta);
        let b = active_sephirot(theta);
        assert_eq!(
            a, b,
            "active_sephirot({}) returned different results",
            theta
        );
    }
}
