//! VQE (Variational Quantum Eigensolver) optimization loop.
//!
//! Uses the COBYLA derivative-free optimizer to minimize the energy
//! of a parameterized quantum circuit with respect to a given Hamiltonian.
//!
//! CRITICAL: Uses `vqe_verifier`'s simulator/ansatz/hamiltonian for energy
//! computation so that the mining engine and runtime pallet produce
//! bit-identical floating-point results. The mining crate's own simulator,
//! ansatz, and hamiltonian modules exist for unit tests / standalone use,
//! but COBYLA calls the verifier's code to ensure consensus.

use crate::hamiltonian::Hamiltonian;
use rand::Rng;

/// Maximum optimizer iterations.
pub const MAX_ITER: usize = 200;

/// Number of variational parameters (must match verifier).
pub const N_PARAMS: usize = vqe_verifier::ansatz::N_PARAMS;

/// Result of a VQE optimization run.
#[derive(Debug, Clone)]
pub struct VqeResult {
    /// Optimized parameters.
    pub params: Vec<f64>,
    /// Achieved ground state energy.
    pub energy: f64,
}

/// Compute the energy ⟨ψ(θ)|H|ψ(θ)⟩ for given parameters and Hamiltonian.
///
/// Uses vqe_verifier's simulator and ansatz to guarantee bit-identical
/// results with the runtime's verification path.
pub fn compute_energy(params: &[f64], hamiltonian: &Hamiltonian) -> f64 {
    let mut sv = vqe_verifier::simulator::Statevector::new(vqe_verifier::ansatz::N_QUBITS);
    vqe_verifier::ansatz::apply_ansatz(&mut sv, params);

    let mut energy = 0.0;
    for term in &hamiltonian.terms {
        energy += term.coefficient * sv.expectation_value(&term.pauli);
    }
    energy
}

/// Run VQE optimization to find the minimum energy parameters.
///
/// Uses COBYLA (Constrained Optimization BY Linear Approximation) which
/// is a derivative-free optimizer — ideal for noisy quantum objectives.
///
/// # Arguments
/// * `hamiltonian` - The Hamiltonian to minimize.
/// * `rng` - Random number generator for initial parameter sampling.
///
/// # Returns
/// `VqeResult` with optimized parameters and achieved energy.
pub fn optimize<R: Rng>(hamiltonian: &Hamiltonian, rng: &mut R) -> VqeResult {
    use std::f64::consts::PI;

    // Random initial parameters in [0, 2π)
    let initial_params: Vec<f64> = (0..N_PARAMS).map(|_| rng.gen_range(0.0..2.0 * PI)).collect();

    // Bounds: each parameter in [0, 2π]
    let bounds: Vec<(f64, f64)> = vec![(0.0, 2.0 * PI); N_PARAMS];

    // No constraints for VQE
    let no_cons: &[fn(&[f64], &mut Hamiltonian) -> f64] = &[];

    let ham = hamiltonian.clone();

    let result = cobyla::minimize(
        |x: &[f64], ham: &mut Hamiltonian| compute_energy(x, ham),
        &initial_params,
        &bounds,
        no_cons,
        ham,
        MAX_ITER,
        cobyla::RhoBeg::All(0.5),
        None,
    );

    match result {
        Ok((_status, params, energy)) => VqeResult { params, energy },
        Err((_status, params, energy)) => {
            // Even on "failure" (e.g., max evals reached), we still get the best result
            VqeResult { params, energy }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hamiltonian::{generate_hamiltonian, PauliTerm};
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;
    use sp_core::H256;

    #[test]
    fn test_compute_energy_identity() {
        // H = I⊗I⊗I⊗I with coefficient 1.0 → ⟨ψ|I|ψ⟩ = 1.0
        let hamiltonian = Hamiltonian {
            terms: vec![PauliTerm {
                pauli: *b"IIII",
                coefficient: 1.0,
            }],
        };
        let params = vec![0.0; N_PARAMS];
        let energy = compute_energy(&params, &hamiltonian);
        assert!((energy - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_vqe_finds_negative_energy() {
        // Generate a random Hamiltonian and verify VQE finds a lower energy
        // than the initial random parameters would give
        let seed = H256::from([42u8; 32]);
        let hamiltonian = generate_hamiltonian(&seed);

        let mut rng = ChaCha8Rng::seed_from_u64(123);
        let result = optimize(&hamiltonian, &mut rng);

        // The optimized energy should be less than or equal to a random energy
        let random_params: Vec<f64> = (0..N_PARAMS).map(|i| (i as f64) * 0.5).collect();
        let random_energy = compute_energy(&random_params, &hamiltonian);

        assert!(
            result.energy <= random_energy + 0.1,
            "VQE energy {} should be <= random energy {} (with tolerance)",
            result.energy,
            random_energy
        );
    }

    #[test]
    fn test_vqe_simple_hamiltonian() {
        // H = -Z⊗I⊗I⊗I: ground state is |0000⟩ with energy -1.0
        let hamiltonian = Hamiltonian {
            terms: vec![PauliTerm {
                pauli: *b"ZIII",
                coefficient: -1.0,
            }],
        };

        let mut rng = ChaCha8Rng::seed_from_u64(42);
        let result = optimize(&hamiltonian, &mut rng);

        // Should find energy close to -1.0
        assert!(
            result.energy < -0.8,
            "VQE should find energy near -1.0, got {}",
            result.energy
        );
    }

    #[test]
    fn test_vqe_result_has_correct_param_count() {
        let seed = H256::from([1u8; 32]);
        let hamiltonian = generate_hamiltonian(&seed);
        let mut rng = ChaCha8Rng::seed_from_u64(0);
        let result = optimize(&hamiltonian, &mut rng);
        assert_eq!(result.params.len(), N_PARAMS);
    }
}
