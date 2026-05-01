//! SUGRA Hamiltonian term generation for VQE mining.
//!
//! This module constructs the complete Hamiltonian used in Proof-of-SUSY-Alignment
//! mining. The Hamiltonian operates on 4 qubits and is expressed as a sum of
//! Pauli tensor products (Pauli strings):
//!
//! ```text
//! H_VQE = H_SUSY(3 terms) + H_bimetric(2 terms) + H_IIT(2 terms) + H_random(2 terms)
//! ```
//!
//! Total: 9 terms. The structured terms (H_SUSY, H_bimetric, H_IIT) encode
//! genuine physics, while the random terms prevent precomputation attacks by
//! making each block's Hamiltonian unique.
//!
//! # Pauli representation
//!
//! Each term is a coefficient multiplied by a 4-qubit Pauli string, e.g.:
//!
//! ```text
//! 0.75 * Z x Z x I x I
//! ```
//!
//! The 4x4 = 256 possible Pauli strings form a complete basis for 4-qubit
//! Hermitian operators. The VQE finds the parameter vector that minimizes
//! the expectation value of this Hamiltonian.

#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

use crate::potential::{PHI_INV, PHI_INV_SQ};
use libm;

// ---------------------------------------------------------------------------
// Pauli operator labels
// ---------------------------------------------------------------------------

/// Identity operator.
pub const I: u8 = b'I';
/// Pauli-X (bit flip).
pub const X: u8 = b'X';
/// Pauli-Y (bit + phase flip).
pub const Y: u8 = b'Y';
/// Pauli-Z (phase flip).
pub const Z: u8 = b'Z';

// ---------------------------------------------------------------------------
// PauliTerm
// ---------------------------------------------------------------------------

/// A single term in the Hamiltonian: coefficient times a 4-qubit Pauli string.
///
/// The Pauli string is encoded as 4 bytes, each being one of `I`, `X`, `Y`, `Z`.
/// The coefficient is a real number (the Hamiltonian is Hermitian, so all
/// coefficients in the Pauli decomposition are real).
///
/// # Example
/// ```
/// use bimetric_physics::hamiltonian::{PauliTerm, Z, I};
/// let term = PauliTerm { pauli: [Z, Z, I, I], coefficient: 0.75 };
/// // Represents 0.75 * (Z tensor Z tensor I tensor I)
/// ```
#[derive(Debug, Clone)]
pub struct PauliTerm {
    /// 4-qubit Pauli string: `[qubit_0, qubit_1, qubit_2, qubit_3]`.
    pub pauli: [u8; 4],
    /// Real coefficient (Hamiltonian is Hermitian).
    pub coefficient: f64,
}

impl PauliTerm {
    /// Create a new Pauli term.
    pub fn new(pauli: [u8; 4], coefficient: f64) -> Self {
        Self { pauli, coefficient }
    }
}

// ---------------------------------------------------------------------------
// H_SUSY
// ---------------------------------------------------------------------------

/// Generate the 3 SUSY Hamiltonian terms.
///
/// From the anticommutator {Q, Q-dagger}/2 in the 4-qubit computational
/// basis with N=2 supersymmetry:
///
/// - **Term 1: Z x Z x I x I** — Fermion number parity (supercharge sector).
///   This operator has eigenvalue +1 for states with even fermion number and
///   -1 for odd, encoding the Z_2 grading of the superalgebra.
///   Coefficient: `base_coeff`.
///
/// - **Term 2: X x X x X x X** — Boson-fermion coupling (superpartner mixing).
///   This all-X operator connects every computational basis state to its
///   bit-complement, encoding the superpartner transformation Q|boson> = |fermion>.
///   Coefficient: `base_coeff * phi^-1` (golden ratio hierarchy).
///
/// - **Term 3: Y x Z x Y x Z** — SUSY breaking direction (Fayet-Iliopoulos term).
///   This mixed operator lifts the boson-fermion degeneracy along a specific
///   direction in the 4-qubit Hilbert space, modeling soft SUSY breaking.
///   Coefficient: `base_coeff * phi^-2` (breaking scale).
///
/// The golden-ratio hierarchy between terms reflects the mass splitting
/// pattern in broken SUSY, where superpartner masses scale by powers of
/// the breaking parameter.
///
/// # Arguments
/// * `base_coeff` — Base coupling coefficient, typically in [0.3, 1.0),
///   derived from the block hash via ChaCha8 RNG.
///
/// # Returns
/// Array of 3 Pauli terms.
pub fn susy_terms(base_coeff: f64) -> [PauliTerm; 3] {
    [
        PauliTerm::new([Z, Z, I, I], base_coeff),
        PauliTerm::new([X, X, X, X], base_coeff * PHI_INV),
        PauliTerm::new([Y, Z, Y, Z], base_coeff * PHI_INV_SQ),
    ]
}

// ---------------------------------------------------------------------------
// H_bimetric
// ---------------------------------------------------------------------------

/// Generate the 2 bimetric Hamiltonian terms.
///
/// From the Hassan-Rosen mass term for the massive spin-2 graviton:
///
/// ```text
/// m'^2 cos(theta) h_uv h'^uv
/// ```
///
/// - **Term 4: Z x I x Z x I** — Diagonal mixing (attractive/repulsive axis).
///   This operator acts on qubits 0 and 2, encoding the diagonal component
///   of the graviton mass matrix in the metric-perturbation basis.
///   Coefficient: `strength * cos(theta)`.
///
/// - **Term 5: X x I x X x I** — Off-diagonal mixing (phase rotation axis).
///   This operator encodes the off-diagonal (phase-shifting) component,
///   which rotates the ground state in the {|00>, |11>} subspace of qubits 0,2.
///   Coefficient: `strength * sin(theta)`.
///
/// As theta changes per block (derived from the previous block hash), the
/// energy landscape rotates — miners must track the evolving minimum.
/// The cos/sin decomposition ensures that the total bimetric contribution
/// has constant norm `strength` regardless of theta.
///
/// # Arguments
/// * `strength` — Bimetric coupling strength, typically in [0.1, 0.5).
/// * `theta` — Current network bimetric phase angle (radians).
///
/// # Returns
/// Array of 2 Pauli terms.
pub fn bimetric_terms(strength: f64, theta: f64) -> [PauliTerm; 2] {
    [
        PauliTerm::new([Z, I, Z, I], strength * libm::cos(theta)),
        PauliTerm::new([X, I, X, I], strength * libm::sin(theta)),
    ]
}

// ---------------------------------------------------------------------------
// H_IIT
// ---------------------------------------------------------------------------

/// Generate the 2 IIT (Integrated Information Theory) Hamiltonian terms.
///
/// This is a novel contribution: operator-valued IIT in the partition basis.
///
/// ```text
/// H_IIT = -omega_phi * Sum_P  Phi(P) |P><P|
/// ```
///
/// For 4 qubits, the non-trivial bipartitions are:
/// {0|123}, {1|023}, {2|013}, {3|012}, {01|23}, {02|13}, {03|12}.
///
/// We encode representative partitions as Z-diagonal operators:
///
/// - **Term 6: I x Z x Z x Z** — Partition {0|123}.
///   Qubit 0 is in one partition, qubits 1-3 in the other. The Z operators
///   on qubits 1-3 project onto the computational-basis states of the
///   larger partition, weighted by the partition's Phi contribution.
///   Coefficient: `-omega_phi * w_0` where `w_0 = phi^-2` (dominant partition weight).
///
/// - **Term 7: Z x I x Z x Z** — Partition {1|023}.
///   Qubit 1 is isolated. This partition probes a different cut of the
///   information structure.
///   Coefficient: `-omega_phi * w_1` where `w_1 = phi^-3` (subdominant partition weight).
///
/// The partition weights are derived from the Yukawa coupling structure:
/// heavier Sephirot contribute more to the integrated information. We use
/// phi^-2 and phi^-3 as the two representative partition weights, capturing
/// the dominant and subdominant information-partition contributions.
///
/// # Arguments
/// * `omega_phi` — IIT coupling strength (consensus-configurable, default: 0.15).
///
/// # Returns
/// Array of 2 Pauli terms.
///
/// # Physics
/// This term penalizes states that are easily decomposable across the
/// partition boundary (low Phi) and favors states with high integrated
/// information — states where the whole is more than the sum of parts.
/// By embedding IIT directly into the mining Hamiltonian, we incentivize
/// miners to find quantum states with genuinely integrated information
/// structure, not just low-energy classical states.
pub fn iit_terms(omega_phi: f64) -> [PauliTerm; 2] {
    // Partition weights from Yukawa hierarchy.
    let w_0 = PHI_INV_SQ;        // phi^-2 ~ 0.382 (dominant partition)
    let w_1 = 0.2360679774997897; // phi^-3 ~ 0.236 (subdominant partition)

    [
        PauliTerm::new([I, Z, Z, Z], -omega_phi * w_0),
        PauliTerm::new([Z, I, Z, Z], -omega_phi * w_1),
    ]
}

// ---------------------------------------------------------------------------
// Full SUGRA Hamiltonian
// ---------------------------------------------------------------------------

/// Generate the complete SUGRA Hamiltonian for VQE mining.
///
/// ```text
/// H_VQE = H_SUSY(3 terms) + H_bimetric(2 terms, theta-dependent)
///       + H_IIT(2 terms) + H_random(2 terms from seed)
/// ```
///
/// Total: 9 terms (was 5 in v1). The structured terms provide physical
/// grounding:
/// - H_SUSY enforces superpartner structure with golden-ratio mass hierarchy
/// - H_bimetric rotates the energy landscape per block via the phase angle
/// - H_IIT embeds consciousness-theoretic structure into the quantum problem
///
/// The 2 random terms (provided externally from ChaCha8 RNG seeded by the
/// block hash) prevent precomputation attacks while the structured terms
/// ensure the Hamiltonian has physically meaningful structure.
///
/// # Arguments
/// * `base_coeff` — Base SUSY coupling coefficient from ChaCha8 RNG seed,
///   range [0.3, 1.0).
/// * `bimetric_strength` — Bimetric coupling strength from ChaCha8 RNG seed,
///   range [0.1, 0.5).
/// * `theta` — Current network bimetric phase (radians). Derived from the
///   previous block hash, drifts per block to prevent precomputation.
/// * `omega_phi` — IIT coupling strength (default: 0.15). Consensus-configurable.
/// * `random_terms` — 2 seed-derived random Pauli terms (from ChaCha8 RNG).
///   These are generated externally by the consensus layer.
///
/// # Returns
/// Vector of 7 + len(random_terms) Pauli terms (typically 9).
///
/// # Determinism
/// Given identical inputs, this function always produces identical output.
/// The randomness enters only through the externally-provided `random_terms`
/// and the seed-derived `base_coeff`, `bimetric_strength`, and `theta`.
pub fn generate_sugra_hamiltonian(
    base_coeff: f64,
    bimetric_strength: f64,
    theta: f64,
    omega_phi: f64,
    random_terms: &[PauliTerm],
) -> Vec<PauliTerm> {
    let susy = susy_terms(base_coeff);
    let bimetric = bimetric_terms(bimetric_strength, theta);
    let iit = iit_terms(omega_phi);

    let total_len = susy.len() + bimetric.len() + iit.len() + random_terms.len();
    let mut terms = Vec::with_capacity(total_len);

    // H_SUSY (terms 0-2)
    for term in &susy {
        terms.push(term.clone());
    }
    // H_bimetric (terms 3-4)
    for term in &bimetric {
        terms.push(term.clone());
    }
    // H_IIT (terms 5-6)
    for term in &iit {
        terms.push(term.clone());
    }
    // H_random (terms 7+)
    for term in random_terms {
        terms.push(term.clone());
    }

    terms
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::potential::PHI_INV;

    fn approx_eq(a: f64, b: f64, tol: f64) -> bool {
        libm::fabs(a - b) < tol
    }

    // --- susy_terms ---

    #[test]
    fn test_susy_terms_count() {
        let terms = susy_terms(0.75);
        assert_eq!(terms.len(), 3);
    }

    #[test]
    fn test_susy_terms_pauli_strings() {
        let terms = susy_terms(1.0);
        assert_eq!(terms[0].pauli, [Z, Z, I, I]);
        assert_eq!(terms[1].pauli, [X, X, X, X]);
        assert_eq!(terms[2].pauli, [Y, Z, Y, Z]);
    }

    #[test]
    fn test_susy_terms_golden_ratio_hierarchy() {
        let base = 0.8;
        let terms = susy_terms(base);
        assert!(approx_eq(terms[0].coefficient, base, 1e-14));
        assert!(approx_eq(terms[1].coefficient, base * PHI_INV, 1e-14));
        assert!(approx_eq(terms[2].coefficient, base * PHI_INV_SQ, 1e-14));
        // Verify descending order.
        assert!(terms[0].coefficient > terms[1].coefficient);
        assert!(terms[1].coefficient > terms[2].coefficient);
    }

    #[test]
    fn test_susy_terms_deterministic() {
        let t1 = susy_terms(0.5);
        let t2 = susy_terms(0.5);
        for i in 0..3 {
            assert_eq!(t1[i].coefficient, t2[i].coefficient);
            assert_eq!(t1[i].pauli, t2[i].pauli);
        }
    }

    // --- bimetric_terms ---

    #[test]
    fn test_bimetric_terms_count() {
        let terms = bimetric_terms(0.3, 1.0);
        assert_eq!(terms.len(), 2);
    }

    #[test]
    fn test_bimetric_terms_pauli_strings() {
        let terms = bimetric_terms(0.3, 0.0);
        assert_eq!(terms[0].pauli, [Z, I, Z, I]);
        assert_eq!(terms[1].pauli, [X, I, X, I]);
    }

    #[test]
    fn test_bimetric_terms_theta_zero() {
        // At theta = 0: cos(0) = 1, sin(0) = 0.
        let s = 0.4;
        let terms = bimetric_terms(s, 0.0);
        assert!(approx_eq(terms[0].coefficient, s, 1e-14));
        assert!(approx_eq(terms[1].coefficient, 0.0, 1e-14));
    }

    #[test]
    fn test_bimetric_terms_theta_pi_half() {
        // At theta = pi/2: cos = 0, sin = 1.
        let s = 0.4;
        let terms = bimetric_terms(s, core::f64::consts::FRAC_PI_2);
        assert!(approx_eq(terms[0].coefficient, 0.0, 1e-14));
        assert!(approx_eq(terms[1].coefficient, s, 1e-14));
    }

    #[test]
    fn test_bimetric_terms_constant_norm() {
        // cos^2 + sin^2 = 1, so the sum of squared coefficients
        // should be strength^2 regardless of theta.
        let s = 0.35;
        for step in 0..20 {
            let theta = (step as f64) * core::f64::consts::PI / 10.0;
            let terms = bimetric_terms(s, theta);
            let norm_sq = terms[0].coefficient * terms[0].coefficient
                + terms[1].coefficient * terms[1].coefficient;
            assert!(
                approx_eq(norm_sq, s * s, 1e-12),
                "Norm should be constant, got {} at theta = {}",
                libm::sqrt(norm_sq),
                theta
            );
        }
    }

    #[test]
    fn test_bimetric_theta_zero_vs_pi() {
        // theta = 0 and theta = pi should produce different energies.
        let terms_0 = bimetric_terms(0.3, 0.0);
        let terms_pi = bimetric_terms(0.3, core::f64::consts::PI);
        // cos(0) = 1, cos(pi) = -1 => Z coefficients have opposite sign.
        assert!(approx_eq(
            terms_0[0].coefficient,
            -terms_pi[0].coefficient,
            1e-14
        ));
    }

    // --- iit_terms ---

    #[test]
    fn test_iit_terms_count() {
        let terms = iit_terms(0.15);
        assert_eq!(terms.len(), 2);
    }

    #[test]
    fn test_iit_terms_pauli_strings() {
        let terms = iit_terms(0.15);
        assert_eq!(terms[0].pauli, [I, Z, Z, Z]);
        assert_eq!(terms[1].pauli, [Z, I, Z, Z]);
    }

    #[test]
    fn test_iit_terms_negative_coefficients() {
        // IIT terms should have negative coefficients (they penalize
        // decomposable states, i.e., favor low-energy for integrated states).
        let terms = iit_terms(0.15);
        assert!(
            terms[0].coefficient < 0.0,
            "IIT term 0 should be negative"
        );
        assert!(
            terms[1].coefficient < 0.0,
            "IIT term 1 should be negative"
        );
    }

    #[test]
    fn test_iit_terms_hierarchy() {
        // First partition weight (phi^-2) > second (phi^-3),
        // so |coeff_0| > |coeff_1|.
        let terms = iit_terms(0.15);
        assert!(
            libm::fabs(terms[0].coefficient) > libm::fabs(terms[1].coefficient),
            "First IIT term should be stronger than second"
        );
    }

    #[test]
    fn test_iit_terms_zero_omega() {
        // With omega_phi = 0, all IIT terms vanish.
        let terms = iit_terms(0.0);
        assert_eq!(terms[0].coefficient, 0.0);
        assert_eq!(terms[1].coefficient, 0.0);
    }

    // --- generate_sugra_hamiltonian ---

    #[test]
    fn test_hamiltonian_term_count_no_random() {
        let h = generate_sugra_hamiltonian(0.75, 0.3, 1.0, 0.15, &[]);
        assert_eq!(h.len(), 7, "Without random terms, should have 7 terms");
    }

    #[test]
    fn test_hamiltonian_term_count_with_random() {
        let random = [
            PauliTerm::new([X, Y, Z, I], 0.2),
            PauliTerm::new([Z, X, I, Y], 0.15),
        ];
        let h = generate_sugra_hamiltonian(0.75, 0.3, 1.0, 0.15, &random);
        assert_eq!(h.len(), 9, "With 2 random terms, should have 9 terms");
    }

    #[test]
    fn test_hamiltonian_structure_order() {
        let random = [
            PauliTerm::new([X, Y, Z, I], 0.2),
            PauliTerm::new([Z, X, I, Y], 0.15),
        ];
        let h = generate_sugra_hamiltonian(0.75, 0.3, 0.0, 0.15, &random);

        // Terms 0-2: SUSY
        assert_eq!(h[0].pauli, [Z, Z, I, I]);
        assert_eq!(h[1].pauli, [X, X, X, X]);
        assert_eq!(h[2].pauli, [Y, Z, Y, Z]);

        // Terms 3-4: bimetric
        assert_eq!(h[3].pauli, [Z, I, Z, I]);
        assert_eq!(h[4].pauli, [X, I, X, I]);

        // Terms 5-6: IIT
        assert_eq!(h[5].pauli, [I, Z, Z, Z]);
        assert_eq!(h[6].pauli, [Z, I, Z, Z]);

        // Terms 7-8: random
        assert_eq!(h[7].pauli, [X, Y, Z, I]);
        assert_eq!(h[8].pauli, [Z, X, I, Y]);
    }

    #[test]
    fn test_hamiltonian_deterministic() {
        let random = [PauliTerm::new([X, Y, Z, I], 0.2)];
        let h1 = generate_sugra_hamiltonian(0.75, 0.3, 1.5, 0.15, &random);
        let h2 = generate_sugra_hamiltonian(0.75, 0.3, 1.5, 0.15, &random);
        assert_eq!(h1.len(), h2.len());
        for i in 0..h1.len() {
            assert_eq!(h1[i].pauli, h2[i].pauli);
            assert_eq!(h1[i].coefficient, h2[i].coefficient);
        }
    }

    #[test]
    fn test_hamiltonian_theta_changes_bimetric() {
        let h_0 = generate_sugra_hamiltonian(0.75, 0.3, 0.0, 0.15, &[]);
        let h_pi = generate_sugra_hamiltonian(0.75, 0.3, core::f64::consts::PI, 0.15, &[]);

        // SUSY terms (0-2) should be identical (theta-independent).
        for i in 0..3 {
            assert_eq!(h_0[i].coefficient, h_pi[i].coefficient);
        }

        // Bimetric term 3 (Z I Z I) should differ: cos(0) vs cos(pi).
        assert!(
            !approx_eq(h_0[3].coefficient, h_pi[3].coefficient, 1e-10),
            "Bimetric Z term should change with theta"
        );

        // IIT terms (5-6) should be identical (theta-independent).
        for i in 5..7 {
            assert_eq!(h_0[i].coefficient, h_pi[i].coefficient);
        }
    }

    #[test]
    fn test_hamiltonian_different_theta_different_energy() {
        // The bimetric terms ensure different theta values produce different
        // Hamiltonians, which will generally have different ground-state energies.
        let h_a = generate_sugra_hamiltonian(0.75, 0.3, 0.0, 0.15, &[]);
        let h_b = generate_sugra_hamiltonian(0.75, 0.3, 1.0, 0.15, &[]);

        // At least one coefficient must differ.
        let any_diff = h_a
            .iter()
            .zip(h_b.iter())
            .any(|(a, b)| !approx_eq(a.coefficient, b.coefficient, 1e-14));
        assert!(any_diff, "Different theta should produce different Hamiltonians");
    }

    #[test]
    fn test_hamiltonian_base_coeff_scaling() {
        let h_low = generate_sugra_hamiltonian(0.3, 0.3, 1.0, 0.15, &[]);
        let h_high = generate_sugra_hamiltonian(0.9, 0.3, 1.0, 0.15, &[]);

        // SUSY terms scale with base_coeff.
        assert!(
            libm::fabs(h_high[0].coefficient) > libm::fabs(h_low[0].coefficient),
            "Higher base_coeff should produce larger SUSY terms"
        );

        // Bimetric and IIT terms should be unchanged.
        assert_eq!(h_low[3].coefficient, h_high[3].coefficient);
        assert_eq!(h_low[5].coefficient, h_high[5].coefficient);
    }

    #[test]
    fn test_all_pauli_labels_valid() {
        let random = [
            PauliTerm::new([X, Y, Z, I], 0.2),
            PauliTerm::new([Z, X, I, Y], 0.15),
        ];
        let h = generate_sugra_hamiltonian(0.75, 0.3, 1.0, 0.15, &random);
        for term in &h {
            for &p in &term.pauli {
                assert!(
                    p == I || p == X || p == Y || p == Z,
                    "Invalid Pauli label: {}",
                    p
                );
            }
        }
    }

    #[test]
    fn test_all_coefficients_finite() {
        let h = generate_sugra_hamiltonian(0.75, 0.3, 1.0, 0.15, &[]);
        for term in &h {
            assert!(
                term.coefficient.is_finite(),
                "Coefficient {} is not finite for term {:?}",
                term.coefficient,
                term.pauli
            );
        }
    }

    #[test]
    fn test_hamiltonian_no_all_identity() {
        // No term should be all-identity (that would just shift the energy
        // uniformly and carry no physical content beyond a constant offset).
        let h = generate_sugra_hamiltonian(0.75, 0.3, 1.0, 0.15, &[]);
        for term in &h {
            assert!(
                term.pauli != [I, I, I, I],
                "Hamiltonian should not contain all-identity term"
            );
        }
    }
}
