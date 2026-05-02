use libm;
use rand::Rng;
use rand_chacha::ChaCha8Rng;
use rand::SeedableRng;
use sha2::{Digest, Sha256};

pub const N_TERMS: usize = 5;
pub const N_TERMS_V2: usize = 9;
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

/// Generate a SUGRA v2 Hamiltonian: H_SUSY + H_bimetric(theta) + H_IIT + H_random.
///
/// CONSENSUS-CRITICAL: Must produce identical output to the Substrate pallet's
/// `vqe_verifier::hamiltonian::generate_hamiltonian_v2()` and
/// `qbc_mining::hamiltonian::generate_hamiltonian_v2()`.
pub fn generate_hamiltonian_v2(seed: &[u8; 32], theta: f64) -> Hamiltonian {
    let mut rng = ChaCha8Rng::from_seed(*seed);
    let mut terms = Vec::with_capacity(N_TERMS_V2);

    // H_SUSY: 3 structured terms from {Q, Q-dagger}/2
    let base_coeff: f64 = rng.gen_range(0.3..1.0);

    terms.push(PauliTerm { pauli: [b'Z', b'Z', b'I', b'I'], coefficient: base_coeff });
    terms.push(PauliTerm { pauli: [b'X', b'X', b'X', b'X'], coefficient: base_coeff * 0.6180339887498949 });
    terms.push(PauliTerm { pauli: [b'Y', b'Z', b'Y', b'Z'], coefficient: base_coeff * 0.3819660112501051 });

    // H_bimetric: 2 phase-coupled terms
    let bimetric_strength: f64 = rng.gen_range(0.1..0.5);

    terms.push(PauliTerm { pauli: [b'Z', b'I', b'Z', b'I'], coefficient: bimetric_strength * libm::cos(theta) });
    terms.push(PauliTerm { pauli: [b'X', b'I', b'X', b'I'], coefficient: bimetric_strength * libm::sin(theta) });

    // H_IIT: 2 operator-valued IIT terms
    let omega_phi: f64 = 0.15;

    terms.push(PauliTerm { pauli: [b'I', b'Z', b'Z', b'Z'], coefficient: -omega_phi * 1.0 });
    terms.push(PauliTerm { pauli: [b'Z', b'I', b'Z', b'Z'], coefficient: -omega_phi * 0.6180339887498949 });

    // H_random: 2 seed-specific anti-precomputation terms
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

    #[test]
    fn test_v2_deterministic() {
        let seed = [42u8; 32];
        let theta = 0.789;
        let h1 = generate_hamiltonian_v2(&seed, theta);
        let h2 = generate_hamiltonian_v2(&seed, theta);
        assert_eq!(h1.terms.len(), N_TERMS_V2);
        for (t1, t2) in h1.terms.iter().zip(h2.terms.iter()) {
            assert_eq!(t1.pauli, t2.pauli);
            assert!((t1.coefficient - t2.coefficient).abs() < 1e-15);
        }
    }

    #[test]
    fn test_v2_susy_structure() {
        let seed = [42u8; 32];
        let h = generate_hamiltonian_v2(&seed, 0.0);
        assert_eq!(h.terms[0].pauli, [b'Z', b'Z', b'I', b'I']);
        assert_eq!(h.terms[1].pauli, [b'X', b'X', b'X', b'X']);
        assert_eq!(h.terms[2].pauli, [b'Y', b'Z', b'Y', b'Z']);
        let ratio = h.terms[1].coefficient / h.terms[0].coefficient;
        assert!((ratio - 0.6180339887498949).abs() < 1e-10);
    }

    #[test]
    fn test_v2_theta_changes_bimetric() {
        let seed = [42u8; 32];
        let h0 = generate_hamiltonian_v2(&seed, 0.0);
        let h1 = generate_hamiltonian_v2(&seed, std::f64::consts::FRAC_PI_2);
        assert!((h0.terms[3].coefficient - h1.terms[3].coefficient).abs() > 1e-6);
    }
}
