//! Deterministic Hamiltonian generation from a SHA2-256 seed.
//!
//! Generates a SUSY Hamiltonian as a weighted sum of Pauli strings.
//! Must match the pallet's `derive_hamiltonian_seed()` exactly.

use rand::Rng;
use rand_chacha::ChaCha8Rng;
use rand::SeedableRng;
use sha2::{Digest, Sha256};
use sp_core::H256;

/// Number of Pauli terms in the generated Hamiltonian.
pub const N_TERMS: usize = 5;
/// Number of qubits.
pub const N_QUBITS: usize = 4;

/// A single term in the Hamiltonian: coefficient * Pauli string.
#[derive(Debug, Clone)]
pub struct PauliTerm {
    /// The Pauli string (e.g., b"XYZZ"), one char per qubit.
    pub pauli: [u8; N_QUBITS],
    /// The coefficient (real-valued, in [-1, 1)).
    pub coefficient: f64,
}

/// A Hamiltonian represented as a sum of weighted Pauli strings.
#[derive(Debug, Clone)]
pub struct Hamiltonian {
    pub terms: Vec<PauliTerm>,
}

/// Derive the Hamiltonian seed from parent block hash and block height.
///
/// Must match `pallet-qbc-consensus::derive_hamiltonian_seed()` exactly:
///   `seed = SHA2-256("{hex_of_parent_hash}:{block_height_decimal}")`
/// where hex is lowercase and height is a decimal ASCII string.
///
/// This also matches the Python node's derivation:
///   `hashlib.sha256(f"{prev_hash}:{height}".encode()).digest()`
pub fn derive_seed(parent_hash: &H256, block_height: u64) -> H256 {
    let mut hasher = Sha256::new();
    // Format: "{hex_of_parent_hash}:{block_height_decimal}"
    let hex_str = hex::encode(parent_hash.as_bytes());
    hasher.update(hex_str.as_bytes());
    hasher.update(b":");
    hasher.update(block_height.to_string().as_bytes());
    H256::from_slice(&hasher.finalize())
}

/// Generate a deterministic Hamiltonian from a seed.
///
/// Uses ChaCha8Rng seeded from the 32-byte seed to produce exactly
/// `N_TERMS` Pauli terms, each with a random 4-qubit Pauli string
/// and coefficient in [-1, 1).
pub fn generate_hamiltonian(seed: &H256) -> Hamiltonian {
    let mut rng = ChaCha8Rng::from_seed(seed.0);
    let paulis = [b'I', b'X', b'Y', b'Z'];

    let terms = (0..N_TERMS)
        .map(|_| {
            let mut pauli = [0u8; N_QUBITS];
            for p in pauli.iter_mut() {
                let idx: usize = rng.gen_range(0..4);
                *p = paulis[idx];
            }
            // Coefficient in [-1, 1)
            let coefficient: f64 = rng.gen_range(-1.0..1.0);
            PauliTerm { pauli, coefficient }
        })
        .collect();

    Hamiltonian { terms }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deterministic_seed() {
        let parent = H256::from([0xABu8; 32]);
        let seed1 = derive_seed(&parent, 100);
        let seed2 = derive_seed(&parent, 100);
        assert_eq!(seed1, seed2, "Same inputs must produce same seed");
    }

    #[test]
    fn test_different_heights_different_seeds() {
        let parent = H256::from([0xABu8; 32]);
        let seed1 = derive_seed(&parent, 100);
        let seed2 = derive_seed(&parent, 101);
        assert_ne!(seed1, seed2);
    }

    #[test]
    fn test_different_parents_different_seeds() {
        let parent1 = H256::from([0xAAu8; 32]);
        let parent2 = H256::from([0xBBu8; 32]);
        let seed1 = derive_seed(&parent1, 100);
        let seed2 = derive_seed(&parent2, 100);
        assert_ne!(seed1, seed2);
    }

    /// Verify mining engine seed derivation matches pallet's format exactly.
    /// The pallet computes: SHA256("{hex_parent_hash}:{decimal_height}")
    /// This test manually constructs the same string to ensure agreement.
    #[test]
    fn test_seed_matches_pallet_format() {
        let parent = H256::from([0x42u8; 32]);
        let height: u64 = 100;

        let seed = derive_seed(&parent, height);

        // Manual computation matching the pallet's derive_hamiltonian_seed()
        let mut hasher = Sha256::new();
        let hex_str = hex::encode(parent.as_bytes());
        hasher.update(hex_str.as_bytes());
        hasher.update(b":");
        hasher.update(b"100"); // decimal string of height
        let expected = H256::from_slice(&hasher.finalize());

        assert_eq!(seed, expected, "Mining seed must match pallet derivation");
    }

    /// Verify the seed format matches what Python produces:
    ///   hashlib.sha256(f"{prev_hash}:{height}".encode()).digest()
    #[test]
    fn test_seed_format_is_hex_colon_decimal() {
        let parent = H256::from([0x00u8; 32]);
        let height: u64 = 0;

        let seed = derive_seed(&parent, height);

        // The input string should be:
        // "0000000000000000000000000000000000000000000000000000000000000000:0"
        let mut hasher = Sha256::new();
        hasher.update(b"0000000000000000000000000000000000000000000000000000000000000000:0");
        let expected = H256::from_slice(&hasher.finalize());

        assert_eq!(seed, expected, "Seed format must be hex:decimal");
    }

    #[test]
    fn test_hamiltonian_deterministic() {
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
    fn test_hamiltonian_term_count() {
        let seed = H256::from([1u8; 32]);
        let h = generate_hamiltonian(&seed);
        assert_eq!(h.terms.len(), N_TERMS);
    }

    #[test]
    fn test_hamiltonian_valid_paulis() {
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
    fn test_hamiltonian_coefficients_bounded() {
        let seed = H256::from([7u8; 32]);
        let h = generate_hamiltonian(&seed);
        for term in &h.terms {
            assert!(term.coefficient >= -1.0 && term.coefficient < 1.0);
        }
    }
}
