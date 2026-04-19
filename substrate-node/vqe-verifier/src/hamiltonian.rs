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
}
