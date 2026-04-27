use rand::Rng;
use rand_chacha::ChaCha8Rng;
use rand::SeedableRng;
use sha2::{Digest, Sha256};

pub const N_TERMS: usize = 5;
pub const N_QUBITS: usize = 4;

#[derive(Debug, Clone)]
pub struct PauliTerm {
    pub pauli: [u8; N_QUBITS],
    pub coefficient: f64,
}

#[derive(Debug, Clone)]
pub struct Hamiltonian {
    pub terms: Vec<PauliTerm>,
}

/// Derive seed from parent hash + block height.
/// Format: SHA256("{hex_parent_hash}:{decimal_height}")
pub fn derive_seed(parent_hash: &[u8; 32], block_height: u64) -> [u8; 32] {
    let mut hasher = Sha256::new();
    let hex_str = hex::encode(parent_hash);
    hasher.update(hex_str.as_bytes());
    hasher.update(b":");
    hasher.update(block_height.to_string().as_bytes());
    let result = hasher.finalize();
    let mut seed = [0u8; 32];
    seed.copy_from_slice(&result);
    seed
}

pub fn generate_hamiltonian(seed: &[u8; 32]) -> Hamiltonian {
    let mut rng = ChaCha8Rng::from_seed(*seed);
    let paulis = [b'I', b'X', b'Y', b'Z'];

    let terms = (0..N_TERMS)
        .map(|_| {
            let mut pauli = [0u8; N_QUBITS];
            for p in pauli.iter_mut() {
                let idx: usize = rng.gen_range(0..4);
                *p = paulis[idx];
            }
            let coefficient: f64 = rng.gen_range(-1.0..1.0);
            let is_all_identity = pauli.iter().all(|&p| p == b'I');
            PauliTerm {
                pauli,
                coefficient: if is_all_identity { 0.0 } else { coefficient },
            }
        })
        .collect();

    Hamiltonian { terms }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deterministic() {
        let seed = [42u8; 32];
        let h1 = generate_hamiltonian(&seed);
        let h2 = generate_hamiltonian(&seed);
        for (t1, t2) in h1.terms.iter().zip(h2.terms.iter()) {
            assert_eq!(t1.pauli, t2.pauli);
            assert!((t1.coefficient - t2.coefficient).abs() < 1e-15);
        }
    }

    #[test]
    fn test_term_count() {
        let h = generate_hamiltonian(&[1u8; 32]);
        assert_eq!(h.terms.len(), N_TERMS);
    }
}
