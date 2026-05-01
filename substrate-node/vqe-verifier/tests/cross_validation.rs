//! Cross-validation: mining engine and on-chain verifier must produce
//! identical Hamiltonians for consensus to work.

use sp_core::H256;

/// Verify that the mining engine's v2 Hamiltonian matches the verifier's v2
/// Hamiltonian term-for-term. If these diverge, miners will produce proofs
/// that the on-chain verifier rejects (or vice versa).
#[test]
fn test_v2_hamiltonian_mining_matches_verifier() {
    let seeds = [
        H256::from([42u8; 32]),
        H256::from([0u8; 32]),
        H256::from([0xFF; 32]),
        H256::from([7u8; 32]),
    ];
    let thetas = [0.0, 0.789, std::f64::consts::PI, -1.5, 3.0];

    for seed in &seeds {
        for &theta in &thetas {
            let mining_ham = qbc_mining::hamiltonian::generate_hamiltonian_v2(seed, theta);
            let verifier_ham = vqe_verifier::hamiltonian::generate_hamiltonian_v2(seed, theta);

            assert_eq!(
                mining_ham.terms.len(),
                verifier_ham.terms.len(),
                "Term count mismatch for seed={:?}, theta={}",
                seed, theta,
            );

            for (i, (mt, vt)) in mining_ham.terms.iter().zip(verifier_ham.terms.iter()).enumerate() {
                assert_eq!(
                    mt.pauli, vt.pauli,
                    "Pauli mismatch at term {} for seed={:?}, theta={}",
                    i, seed, theta,
                );
                assert!(
                    (mt.coefficient - vt.coefficient).abs() < 1e-14,
                    "Coefficient mismatch at term {}: mining={}, verifier={} for seed={:?}, theta={}",
                    i, mt.coefficient, vt.coefficient, seed, theta,
                );
            }
        }
    }
}

/// End-to-end: mining engine produces a proof, verifier accepts it.
#[test]
fn test_mining_proof_accepted_by_verifier() {
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let seed = H256::from([42u8; 32]);
    let theta = 0.789;

    let ham = qbc_mining::hamiltonian::generate_hamiltonian_v2(&seed, theta);
    let mut rng = ChaCha8Rng::from_seed([99u8; 32]);
    let result = qbc_mining::vqe::optimize(&ham, &mut rng);

    // Scale to on-chain format
    let scale = 1e12;
    let params_scaled: Vec<i64> = result.params.iter().map(|&p| (p * scale) as i64).collect();
    let energy_scaled = (result.energy * scale) as i128;
    let theta_scaled = (theta * scale) as i64;

    assert!(
        vqe_verifier::verify_energy_versioned(&seed, &params_scaled, energy_scaled, theta_scaled, 2),
        "Mining engine proof must be accepted by on-chain verifier (energy={})",
        result.energy,
    );
}
