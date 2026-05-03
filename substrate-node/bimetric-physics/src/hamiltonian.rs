//! Parameterized Hamiltonian term generation for VQE mining.
//!
//! This module constructs the 4-qubit Hamiltonian used by the VQE mining
//! algorithm. The Hamiltonian is a sum of Pauli tensor products with
//! golden-ratio coefficient hierarchies and a rotating phase parameter:
//!
//! ```text
//! H_VQE = H_base(3 terms) + H_rotating(2 terms) + H_diagonal(2 terms) + H_random(2 terms)
//! ```
//!
//! Total: 9 terms. The structured terms provide a well-conditioned energy
//! landscape for VQE optimization, while the random terms (seeded from
//! the block hash) prevent precomputation attacks.
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
// Base Pauli terms (golden-ratio coefficient hierarchy)
// ---------------------------------------------------------------------------

/// Generate the 3 base Pauli terms with golden-ratio coefficient hierarchy.
///
/// These form the static (theta-independent) core of the Hamiltonian.
/// The three Pauli strings are chosen to span complementary subspaces
/// of the 4-qubit Hilbert space, ensuring a non-trivial energy landscape:
///
/// - **Term 1: Z x Z x I x I** — Diagonal parity operator on qubits 0-1.
///   Has eigenvalue +1 for even-parity states and -1 for odd-parity.
///   Coefficient: `base_coeff`.
///
/// - **Term 2: X x X x X x X** — Full bit-flip operator.
///   Connects every computational basis state to its complement, creating
///   off-diagonal mixing across the entire Hilbert space.
///   Coefficient: `base_coeff * phi^-1` (golden ratio hierarchy).
///
/// - **Term 3: Y x Z x Y x Z** — Mixed Pauli operator.
///   Creates asymmetric coupling in the Y-Z subspace, breaking degeneracies
///   that the first two terms leave intact.
///   Coefficient: `base_coeff * phi^-2`.
///
/// The golden-ratio (phi^-n) coefficient hierarchy ensures a well-separated
/// scale structure: each successive term contributes ~61.8% of the previous,
/// preventing near-degenerate energy levels.
///
/// # Arguments
/// * `base_coeff` — Base coupling coefficient, typically in [0.3, 1.0),
///   derived from the block hash via ChaCha8 RNG.
///
/// # Returns
/// Array of 3 Pauli terms.
pub fn base_pauli_terms(base_coeff: f64) -> [PauliTerm; 3] {
    [
        PauliTerm::new([Z, Z, I, I], base_coeff),
        PauliTerm::new([X, X, X, X], base_coeff * PHI_INV),
        PauliTerm::new([Y, Z, Y, Z], base_coeff * PHI_INV_SQ),
    ]
}

// ---------------------------------------------------------------------------
// Rotating coupling terms (theta-dependent, cos/sin parameterization)
// ---------------------------------------------------------------------------

/// Generate the 2 rotating-coefficient coupling terms parameterized by cos(theta)/sin(theta).
///
/// These terms rotate the energy landscape each block by varying theta.
/// The cos/sin decomposition ensures the total contribution has constant
/// norm `strength` regardless of theta (since cos^2 + sin^2 = 1):
///
/// - **Term 4: Z x I x Z x I** — Diagonal coupling on qubits 0 and 2.
///   Coefficient: `strength * cos(theta)`. At theta=0 this term dominates;
///   at theta=pi/2 it vanishes.
///
/// - **Term 5: X x I x X x I** — Off-diagonal coupling on qubits 0 and 2.
///   Coefficient: `strength * sin(theta)`. Orthogonal to term 4, creating
///   a smooth rotation of the ground-state direction as theta advances.
///
/// As theta advances per block, miners must track the evolving minimum.
/// This prevents miners from caching solutions across blocks.
///
/// # Arguments
/// * `strength` — Coupling strength, typically in [0.1, 0.5).
/// * `theta` — Current network phase angle (radians), advances each block.
///
/// # Returns
/// Array of 2 Pauli terms.
pub fn rotating_coupling_terms(strength: f64, theta: f64) -> [PauliTerm; 2] {
    [
        PauliTerm::new([Z, I, Z, I], strength * libm::cos(theta)),
        PauliTerm::new([X, I, X, I], strength * libm::sin(theta)),
    ]
}

// ---------------------------------------------------------------------------
// Diagonal bias terms (small negative coefficient, Z-only operators)
// ---------------------------------------------------------------------------

/// Generate the 2 diagonal bias terms with small negative coefficients.
///
/// These Z-only operators act on the diagonal of the Hamiltonian in the
/// computational basis, adding a bias that breaks remaining degeneracies
/// left by the base and rotating terms. The negative sign favors states
/// where the Z-eigenvalues align with the operator pattern.
///
/// - **Term 6: I x Z x Z x Z** — Diagonal bias on qubits 1-3.
///   Coefficient: `-omega_phi * phi^-2` (dominant weight ~ -0.057).
///
/// - **Term 7: Z x I x Z x Z** — Diagonal bias on qubits 0, 2-3.
///   Coefficient: `-omega_phi * phi^-3` (subdominant weight ~ -0.035).
///
/// The phi^-2 / phi^-3 weight hierarchy follows the same golden-ratio
/// descent used in the base terms, maintaining a consistent scale structure
/// across the entire Hamiltonian.
///
/// # Arguments
/// * `omega_phi` — Bias strength (consensus-configurable, default: 0.15).
///
/// # Returns
/// Array of 2 Pauli terms.
pub fn diagonal_bias_terms(omega_phi: f64) -> [PauliTerm; 2] {
    // Partition weights from Yukawa hierarchy.
    let w_0 = PHI_INV_SQ;        // phi^-2 ~ 0.382 (dominant partition)
    let w_1 = 0.2360679774997897; // phi^-3 ~ 0.236 (subdominant partition)

    [
        PauliTerm::new([I, Z, Z, Z], -omega_phi * w_0),
        PauliTerm::new([Z, I, Z, Z], -omega_phi * w_1),
    ]
}

// ---------------------------------------------------------------------------
// Full parameterized Hamiltonian
// ---------------------------------------------------------------------------

/// Generate the complete parameterized Hamiltonian for VQE mining.
///
/// ```text
/// H_VQE = H_base(3 terms, golden-ratio hierarchy)
///       + H_rotating(2 terms, theta-dependent cos/sin)
///       + H_diagonal(2 terms, small negative bias)
///       + H_random(2 terms from seed)
/// ```
///
/// Total: 9 terms (was 5 in v1). The structured terms provide a
/// well-conditioned VQE energy landscape:
/// - Base terms: 3 Pauli terms with golden-ratio coefficient hierarchy
/// - Rotating terms: 2 rotating-coefficient terms parameterized by cos(theta)/sin(theta)
/// - Diagonal terms: 2 diagonal bias terms with small negative coefficient
///
/// The 2 random terms (provided externally from ChaCha8 RNG seeded by the
/// block hash) prevent precomputation attacks while the structured terms
/// ensure the Hamiltonian has well-behaved optimization properties.
///
/// # Arguments
/// * `base_coeff` — Base coupling coefficient from ChaCha8 RNG seed,
///   range [0.3, 1.0).
/// * `rotating_strength` — Rotating-term coupling strength from ChaCha8 RNG seed,
///   range [0.1, 0.5).
/// * `theta` — Current network phase angle (radians). Advances per block
///   to prevent solution reuse.
/// * `omega_phi` — Diagonal bias strength (default: 0.15). Consensus-configurable.
/// * `random_terms` — 2 seed-derived random Pauli terms (from ChaCha8 RNG).
///   These are generated externally by the consensus layer.
///
/// # Returns
/// Vector of 7 + len(random_terms) Pauli terms (typically 9).
///
/// # Determinism
/// Given identical inputs, this function always produces identical output.
/// The randomness enters only through the externally-provided `random_terms`
/// and the seed-derived `base_coeff`, `rotating_strength`, and `theta`.
pub fn generate_sugra_hamiltonian(
    base_coeff: f64,
    rotating_strength: f64,
    theta: f64,
    omega_phi: f64,
    random_terms: &[PauliTerm],
) -> Vec<PauliTerm> {
    let base = base_pauli_terms(base_coeff);
    let rotating = rotating_coupling_terms(rotating_strength, theta);
    let diagonal = diagonal_bias_terms(omega_phi);

    let total_len = base.len() + rotating.len() + diagonal.len() + random_terms.len();
    let mut terms = Vec::with_capacity(total_len);

    // Base terms (0-2): golden-ratio coefficient hierarchy
    for term in &base {
        terms.push(term.clone());
    }
    // Rotating terms (3-4): theta-dependent cos/sin coupling
    for term in &rotating {
        terms.push(term.clone());
    }
    // Diagonal bias terms (5-6): small negative Z-only operators
    for term in &diagonal {
        terms.push(term.clone());
    }
    // Random terms (7+): block-hash-derived anti-precomputation
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

    // --- base_pauli_terms ---

    #[test]
    fn test_base_pauli_terms_count() {
        let terms = base_pauli_terms(0.75);
        assert_eq!(terms.len(), 3);
    }

    #[test]
    fn test_base_pauli_terms_pauli_strings() {
        let terms = base_pauli_terms(1.0);
        assert_eq!(terms[0].pauli, [Z, Z, I, I]);
        assert_eq!(terms[1].pauli, [X, X, X, X]);
        assert_eq!(terms[2].pauli, [Y, Z, Y, Z]);
    }

    #[test]
    fn test_base_pauli_terms_golden_ratio_hierarchy() {
        let base = 0.8;
        let terms = base_pauli_terms(base);
        assert!(approx_eq(terms[0].coefficient, base, 1e-14));
        assert!(approx_eq(terms[1].coefficient, base * PHI_INV, 1e-14));
        assert!(approx_eq(terms[2].coefficient, base * PHI_INV_SQ, 1e-14));
        // Verify descending order.
        assert!(terms[0].coefficient > terms[1].coefficient);
        assert!(terms[1].coefficient > terms[2].coefficient);
    }

    #[test]
    fn test_base_pauli_terms_deterministic() {
        let t1 = base_pauli_terms(0.5);
        let t2 = base_pauli_terms(0.5);
        for i in 0..3 {
            assert_eq!(t1[i].coefficient, t2[i].coefficient);
            assert_eq!(t1[i].pauli, t2[i].pauli);
        }
    }

    // --- rotating_coupling_terms ---

    #[test]
    fn test_rotating_coupling_terms_count() {
        let terms = rotating_coupling_terms(0.3, 1.0);
        assert_eq!(terms.len(), 2);
    }

    #[test]
    fn test_rotating_coupling_terms_pauli_strings() {
        let terms = rotating_coupling_terms(0.3, 0.0);
        assert_eq!(terms[0].pauli, [Z, I, Z, I]);
        assert_eq!(terms[1].pauli, [X, I, X, I]);
    }

    #[test]
    fn test_rotating_coupling_terms_theta_zero() {
        // At theta = 0: cos(0) = 1, sin(0) = 0.
        let s = 0.4;
        let terms = rotating_coupling_terms(s, 0.0);
        assert!(approx_eq(terms[0].coefficient, s, 1e-14));
        assert!(approx_eq(terms[1].coefficient, 0.0, 1e-14));
    }

    #[test]
    fn test_rotating_coupling_terms_theta_pi_half() {
        // At theta = pi/2: cos = 0, sin = 1.
        let s = 0.4;
        let terms = rotating_coupling_terms(s, core::f64::consts::FRAC_PI_2);
        assert!(approx_eq(terms[0].coefficient, 0.0, 1e-14));
        assert!(approx_eq(terms[1].coefficient, s, 1e-14));
    }

    #[test]
    fn test_rotating_coupling_terms_constant_norm() {
        // cos^2 + sin^2 = 1, so the sum of squared coefficients
        // should be strength^2 regardless of theta.
        let s = 0.35;
        for step in 0..20 {
            let theta = (step as f64) * core::f64::consts::PI / 10.0;
            let terms = rotating_coupling_terms(s, theta);
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
        let terms_0 = rotating_coupling_terms(0.3, 0.0);
        let terms_pi = rotating_coupling_terms(0.3, core::f64::consts::PI);
        // cos(0) = 1, cos(pi) = -1 => Z coefficients have opposite sign.
        assert!(approx_eq(
            terms_0[0].coefficient,
            -terms_pi[0].coefficient,
            1e-14
        ));
    }

    // --- diagonal_bias_terms ---

    #[test]
    fn test_diagonal_bias_terms_count() {
        let terms = diagonal_bias_terms(0.15);
        assert_eq!(terms.len(), 2);
    }

    #[test]
    fn test_diagonal_bias_terms_pauli_strings() {
        let terms = diagonal_bias_terms(0.15);
        assert_eq!(terms[0].pauli, [I, Z, Z, Z]);
        assert_eq!(terms[1].pauli, [Z, I, Z, Z]);
    }

    #[test]
    fn test_diagonal_bias_terms_negative_coefficients() {
        // IIT terms should have negative coefficients (they penalize
        // decomposable states, i.e., favor low-energy for integrated states).
        let terms = diagonal_bias_terms(0.15);
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
    fn test_diagonal_bias_terms_hierarchy() {
        // First partition weight (phi^-2) > second (phi^-3),
        // so |coeff_0| > |coeff_1|.
        let terms = diagonal_bias_terms(0.15);
        assert!(
            libm::fabs(terms[0].coefficient) > libm::fabs(terms[1].coefficient),
            "First IIT term should be stronger than second"
        );
    }

    #[test]
    fn test_diagonal_bias_terms_zero_omega() {
        // With omega_phi = 0, all IIT terms vanish.
        let terms = diagonal_bias_terms(0.0);
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
