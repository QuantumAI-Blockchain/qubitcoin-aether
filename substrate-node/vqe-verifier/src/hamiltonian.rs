//! Deterministic Hamiltonian generation from a SHA2-256 seed (no_std).
//!
//! MUST produce identical output to `qbc-mining::hamiltonian::generate_hamiltonian`.
//! Uses the same ChaCha8Rng seeded from the 32-byte H256 seed.

#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use sp_core::H256;

/// Number of Pauli terms in the generated Hamiltonian.
pub const N_TERMS: usize = 5;
/// Number of qubits.
pub const N_QUBITS: usize = 4;

/// A single term in the Hamiltonian: coefficient * Pauli string.
#[derive(Debug, Clone)]
pub struct PauliTerm {
    /// The Pauli string (e.g., [b'X', b'Y', b'Z', b'Z']), one char per qubit.
    pub pauli: [u8; N_QUBITS],
    /// The coefficient (real-valued, in [-1, 1)).
    pub coefficient: f64,
}

/// A Hamiltonian represented as a sum of weighted Pauli strings.
#[derive(Debug, Clone)]
pub struct Hamiltonian {
    pub terms: Vec<PauliTerm>,
}

/// Generate a deterministic Hamiltonian from a seed.
///
/// Uses ChaCha8Rng seeded from the 32-byte seed to produce exactly
/// `N_TERMS` Pauli terms, each with a random 4-qubit Pauli string
/// and coefficient in [-1, 1).
///
/// MUST match `qbc-mining::hamiltonian::generate_hamiltonian` exactly:
/// - Same RNG: `ChaCha8Rng::from_seed(seed.0)`
/// - Same Pauli alphabet: `[b'I', b'X', b'Y', b'Z']`
/// - Same selection: `rng.gen_range(0..4)` for each qubit in each term
/// - Same coefficient: `rng.gen_range(-1.0..1.0)`
pub fn generate_hamiltonian(seed: &H256) -> Hamiltonian {
    let mut rng = ChaCha8Rng::from_seed(seed.0);
    let paulis = [b'I', b'X', b'Y', b'Z'];

    let mut terms = Vec::with_capacity(N_TERMS);
    for _ in 0..N_TERMS {
        let mut pauli = [0u8; N_QUBITS];
        for p in pauli.iter_mut() {
            let idx: usize = rng.gen_range(0..4);
            *p = paulis[idx];
        }
        let coefficient: f64 = rng.gen_range(-1.0..1.0);
        // Zero out all-Identity terms: IIII just shifts every eigenvalue
        // by a constant, which can make the Hamiltonian unsolvable when
        // the shift pushes the ground state above the difficulty floor.
        // Zeroing (instead of re-sampling) preserves RNG state consistency.
        let is_all_identity = pauli.iter().all(|&p| p == b'I');
        terms.push(PauliTerm {
            pauli,
            coefficient: if is_all_identity { 0.0 } else { coefficient },
        });
    }

    Hamiltonian { terms }
}

/// Number of Pauli terms in the v2 SUGRA Hamiltonian.
pub const N_TERMS_V2: usize = 9;

/// Generate a SUGRA-motivated Hamiltonian for post-fork VQE mining.
///
/// H_VQE = H_SUSY(3 terms) + H_bimetric(2 terms) + H_IIT(2 terms) + H_random(2 terms)
///
/// Total: 9 Pauli terms (was 5 in v1).
///
/// # Arguments
/// - `seed` — H256 from parent block hash (same derivation as v1)
/// - `theta` — Current network bimetric phase (f64, radians)
///
/// The seed determines:
/// - base_coeff for H_SUSY (range [0.3, 1.0) — never near-zero)
/// - bimetric_strength for H_bimetric (range [0.1, 0.5))
/// - The 2 random anti-precomputation terms
///
/// theta determines:
/// - The rotation of the bimetric energy landscape via cos(theta) and sin(theta)
pub fn generate_hamiltonian_v2(seed: &H256, theta: f64) -> Hamiltonian {
    let mut rng = ChaCha8Rng::from_seed(seed.0);

    let mut terms = Vec::with_capacity(N_TERMS_V2);

    // ── H_SUSY: 3 structured terms from {Q, Q†}/2 ──────────────
    // The N=2 superalgebra forces these operator structures.
    // Golden-ratio hierarchy reflects SUSY mass splitting.

    let base_coeff: f64 = rng.gen_range(0.3..1.0); // Never near-zero

    // Term 1: Z⊗Z⊗I⊗I — fermion number parity (supercharge sector)
    terms.push(PauliTerm {
        pauli: [b'Z', b'Z', b'I', b'I'],
        coefficient: base_coeff,
    });

    // Term 2: X⊗X⊗X⊗X — boson-fermion coupling (superpartner mixing)
    terms.push(PauliTerm {
        pauli: [b'X', b'X', b'X', b'X'],
        coefficient: base_coeff * 0.6180339887498949, // phi^-1
    });

    // Term 3: Y⊗Z⊗Y⊗Z — SUSY breaking direction (FI term analog)
    terms.push(PauliTerm {
        pauli: [b'Y', b'Z', b'Y', b'Z'],
        coefficient: base_coeff * 0.3819660112501051, // phi^-2
    });

    // ── H_bimetric: 2 phase-coupled terms ───────────────────────
    // From Hassan-Rosen mass term: m'^2 cos(theta) h_mu_nu h'^mu_nu
    // theta controls the energy landscape rotation per block.

    let bimetric_strength: f64 = rng.gen_range(0.1..0.5);

    // Term 4: Z⊗I⊗Z⊗I — diagonal coupling (attractive/repulsive axis)
    terms.push(PauliTerm {
        pauli: [b'Z', b'I', b'Z', b'I'],
        coefficient: bimetric_strength * libm::cos(theta),
    });

    // Term 5: X⊗I⊗X⊗I — off-diagonal coupling (phase rotation axis)
    terms.push(PauliTerm {
        pauli: [b'X', b'I', b'X', b'I'],
        coefficient: bimetric_strength * libm::sin(theta),
    });

    // ── H_IIT: 2 operator-valued IIT terms ──────────────────────
    // Novel: H_IIT = -omega_Phi Sum Phi(P)|P><P| in partition basis
    // Encodes integrated information as diagonal Z operators
    // over bipartitions of the 4-qubit system.

    let omega_phi: f64 = 0.15; // IIT coupling strength

    // Term 6: I⊗Z⊗Z⊗Z — partition {0|123}, weight from Keter Yukawa
    terms.push(PauliTerm {
        pauli: [b'I', b'Z', b'Z', b'Z'],
        coefficient: -omega_phi * 1.0, // Keter weight
    });

    // Term 7: Z⊗I⊗Z⊗Z — partition {1|023}, weight from integration
    terms.push(PauliTerm {
        pauli: [b'Z', b'I', b'Z', b'Z'],
        coefficient: -omega_phi * 0.6180339887498949, // Tiferet weight (phi^-1)
    });

    // ── H_random: 2 seed-specific anti-precomputation terms ─────
    // Prevents offline precomputation of solutions.
    // Same structure as v1 but only 2 terms (not 5).

    let paulis = [b'I', b'X', b'Y', b'Z'];
    for _ in 0..2 {
        let mut pauli = [0u8; N_QUBITS];
        for p in pauli.iter_mut() {
            let idx: usize = rng.gen_range(0..4);
            *p = paulis[idx];
        }
        let coefficient: f64 = rng.gen_range(-0.5..0.5);
        let is_all_identity = pauli.iter().all(|&p| p == b'I');
        terms.push(PauliTerm {
            pauli,
            coefficient: if is_all_identity { 0.0 } else { coefficient },
        });
    }

    Hamiltonian { terms }
}

/// Compute the VQE energy: E = sum_i coeff_i * <psi|P_i|psi>.
pub fn compute_energy(hamiltonian: &Hamiltonian, sv: &crate::simulator::Statevector) -> f64 {
    let mut energy = 0.0;
    for term in &hamiltonian.terms {
        energy += term.coefficient * sv.expectation_value(&term.pauli);
    }
    energy
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deterministic() {
        let seed = H256::from([42u8; 32]);
        let h1 = generate_hamiltonian(&seed);
        let h2 = generate_hamiltonian(&seed);
        assert_eq!(h1.terms.len(), h2.terms.len());
        for (t1, t2) in h1.terms.iter().zip(h2.terms.iter()) {
            assert_eq!(t1.pauli, t2.pauli);
            assert!((t1.coefficient - t2.coefficient).abs() < 1e-15);
        }
    }

    #[test]
    fn test_term_count() {
        let seed = H256::from([1u8; 32]);
        let h = generate_hamiltonian(&seed);
        assert_eq!(h.terms.len(), N_TERMS);
    }

    #[test]
    fn test_valid_paulis() {
        let seed = H256::from([99u8; 32]);
        let h = generate_hamiltonian(&seed);
        for term in &h.terms {
            for &p in &term.pauli {
                assert!(
                    p == b'I' || p == b'X' || p == b'Y' || p == b'Z',
                    "Invalid Pauli char: {}",
                    p as char
                );
            }
        }
    }

    #[test]
    fn test_coefficients_bounded() {
        let seed = H256::from([7u8; 32]);
        let h = generate_hamiltonian(&seed);
        for term in &h.terms {
            assert!(term.coefficient >= -1.0 && term.coefficient < 1.0);
        }
    }

    #[test]
    fn test_different_seeds_different_hamiltonians() {
        let h1 = generate_hamiltonian(&H256::from([1u8; 32]));
        let h2 = generate_hamiltonian(&H256::from([2u8; 32]));
        // Very unlikely to be the same
        let same = h1.terms.iter().zip(h2.terms.iter()).all(|(t1, t2)| {
            t1.pauli == t2.pauli && (t1.coefficient - t2.coefficient).abs() < 1e-15
        });
        assert!(!same, "Different seeds should produce different Hamiltonians");
    }

    // ── v2 Hamiltonian tests ────────────────────────────────────

    #[test]
    fn test_v2_deterministic() {
        let seed = H256::from([42u8; 32]);
        let theta = 1.234;
        let h1 = generate_hamiltonian_v2(&seed, theta);
        let h2 = generate_hamiltonian_v2(&seed, theta);
        assert_eq!(h1.terms.len(), h2.terms.len());
        for (t1, t2) in h1.terms.iter().zip(h2.terms.iter()) {
            assert_eq!(t1.pauli, t2.pauli);
            assert!(
                (t1.coefficient - t2.coefficient).abs() < 1e-15,
                "Coefficients differ: {} vs {}",
                t1.coefficient,
                t2.coefficient,
            );
        }
    }

    #[test]
    fn test_v2_term_count() {
        let seed = H256::from([1u8; 32]);
        let h = generate_hamiltonian_v2(&seed, 0.5);
        assert_eq!(h.terms.len(), N_TERMS_V2);
    }

    #[test]
    fn test_v2_theta_modulates_bimetric() {
        let seed = H256::from([99u8; 32]);
        let h_a = generate_hamiltonian_v2(&seed, 0.0);
        let h_b = generate_hamiltonian_v2(&seed, core::f64::consts::FRAC_PI_2);

        // Term 4 (index 3): Z I Z I — coefficient = strength * cos(theta)
        // At theta=0, cos=1; at theta=pi/2, cos=0
        assert!(
            h_a.terms[3].coefficient.abs() > 0.05,
            "Term 4 at theta=0 should be non-negligible",
        );
        assert!(
            h_b.terms[3].coefficient.abs() < 1e-10,
            "Term 4 at theta=pi/2 should be ~0 (cos(pi/2)=0)",
        );

        // Term 5 (index 4): X I X I — coefficient = strength * sin(theta)
        // At theta=0, sin=0; at theta=pi/2, sin=1
        assert!(
            h_a.terms[4].coefficient.abs() < 1e-10,
            "Term 5 at theta=0 should be ~0 (sin(0)=0)",
        );
        assert!(
            h_b.terms[4].coefficient.abs() > 0.05,
            "Term 5 at theta=pi/2 should be non-negligible",
        );
    }

    #[test]
    fn test_v2_susy_structure() {
        // First 3 terms always have fixed Pauli strings regardless of seed
        for seed_byte in [1u8, 42, 99, 200, 255] {
            let seed = H256::from([seed_byte; 32]);
            let h = generate_hamiltonian_v2(&seed, 0.0);

            assert_eq!(h.terms[0].pauli, [b'Z', b'Z', b'I', b'I'], "Term 1 must be ZZII");
            assert_eq!(h.terms[1].pauli, [b'X', b'X', b'X', b'X'], "Term 2 must be XXXX");
            assert_eq!(h.terms[2].pauli, [b'Y', b'Z', b'Y', b'Z'], "Term 3 must be YZYZ");
        }
    }

    #[test]
    fn test_v2_golden_ratio_hierarchy() {
        let seed = H256::from([77u8; 32]);
        let h = generate_hamiltonian_v2(&seed, 0.0);

        let c1 = h.terms[0].coefficient; // base_coeff
        let c2 = h.terms[1].coefficient; // base_coeff * phi^-1
        let c3 = h.terms[2].coefficient; // base_coeff * phi^-2

        let phi_inv = 0.6180339887498949;
        let phi_inv2 = 0.3819660112501051;

        assert!(
            (c2 - c1 * phi_inv).abs() < 1e-12,
            "Term 2 coeff ({}) should equal term 1 ({}) * phi^-1 ({})",
            c2, c1, c1 * phi_inv,
        );
        assert!(
            (c3 - c1 * phi_inv2).abs() < 1e-12,
            "Term 3 coeff ({}) should equal term 1 ({}) * phi^-2 ({})",
            c3, c1, c1 * phi_inv2,
        );
    }
}
