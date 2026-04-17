//! Main VQE energy verification function.
//!
//! Takes the Hamiltonian seed, scaled VQE parameters, and claimed energy,
//! re-computes the energy, and checks it matches within tolerance.

#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

use sp_core::H256;

use crate::ansatz;
use crate::hamiltonian;
use crate::simulator::Statevector;

/// Energy scaling factor: parameters and energy are stored as integers
/// scaled by 10^12 for fixed-point on-chain representation.
const SCALE_FACTOR: f64 = 1_000_000_000_000.0; // 10^12

/// Verification tolerance in scaled units (10^12 scale).
///
/// The only source of drift is floating-point differences between the
/// mining engine (std math) and this verifier (libm math). This should
/// be very small (< 1e-6). We use a tolerance of 1e-2 to be safe.
///
/// 1e-2 * 10^12 = 10_000_000_000
const TOLERANCE_SCALED: i128 = 10_000_000_000;

/// Verify that the claimed VQE energy matches re-computation from the
/// given seed and parameters.
///
/// # Arguments
/// * `seed` - The Hamiltonian seed (H256, derived from parent block hash)
/// * `params_scaled` - VQE parameters scaled by 10^12 (from `VqeProof.params`)
/// * `claimed_energy_scaled` - Claimed energy scaled by 10^12 (from `VqeProof.energy`)
///
/// # Returns
/// `true` if `|claimed_energy_scaled - computed_energy_scaled| <= TOLERANCE_SCALED`
///
/// # Algorithm
/// 1. Unscale parameters: `param_f64 = param_i64 as f64 / 10^12`
/// 2. Generate Hamiltonian from seed (deterministic ChaCha8 RNG)
/// 3. Initialize |0000> statevector
/// 4. Apply TwoLocal ansatz with unscaled parameters
/// 5. Compute energy: E = sum_i coeff_i * <psi|P_i|psi>
/// 6. Scale computed energy: `computed_scaled = (energy * 10^12) as i128`
/// 7. Check: `|claimed - computed| <= tolerance`
pub fn verify_energy(
    seed: &H256,
    params_scaled: &[i64],
    claimed_energy_scaled: i128,
) -> bool {
    // Validate parameter count — must be exactly 12 for TwoLocal(4, ry, cz, reps=2)
    if params_scaled.len() != ansatz::N_PARAMS {
        return false;
    }

    // 1. Unscale parameters from fixed-point to f64
    let params: Vec<f64> = params_scaled
        .iter()
        .map(|&p| p as f64 / SCALE_FACTOR)
        .collect();

    // 2. Generate Hamiltonian from seed
    let ham = hamiltonian::generate_hamiltonian(seed);

    // 3. Initialize |0000> statevector
    let mut sv = Statevector::new(ansatz::N_QUBITS);

    // 4. Apply ansatz
    if !ansatz::apply_ansatz(&mut sv, &params) {
        return false;
    }

    // 5. Compute energy
    let computed_energy = hamiltonian::compute_energy(&ham, &sv);

    // 6. Scale computed energy to fixed-point
    let computed_scaled = (computed_energy * SCALE_FACTOR) as i128;

    // 7. Check tolerance
    let diff = if claimed_energy_scaled > computed_scaled {
        claimed_energy_scaled - computed_scaled
    } else {
        computed_scaled - claimed_energy_scaled
    };

    diff <= TOLERANCE_SCALED
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Test that verify_energy accepts a correctly computed proof.
    #[test]
    fn test_valid_proof_accepted() {
        let seed = H256::from([42u8; 32]);

        // Use known parameters
        let params_f64 = [0.5, -0.3, 1.2, 0.8, -0.1, 0.4, -0.9, 0.6, 0.2, -0.7, 1.0, -0.5];

        // Compute the correct energy
        let ham = hamiltonian::generate_hamiltonian(&seed);
        let mut sv = Statevector::new(ansatz::N_QUBITS);
        ansatz::apply_ansatz(&mut sv, &params_f64);
        let energy = hamiltonian::compute_energy(&ham, &sv);

        // Scale to on-chain representation
        let params_scaled: Vec<i64> = params_f64.iter().map(|&p| (p * SCALE_FACTOR) as i64).collect();
        let energy_scaled = (energy * SCALE_FACTOR) as i128;

        assert!(
            verify_energy(&seed, &params_scaled, energy_scaled),
            "Valid proof should be accepted"
        );
    }

    /// Test that verify_energy rejects a fabricated energy value.
    #[test]
    fn test_fake_energy_rejected() {
        let seed = H256::from([42u8; 32]);
        let params_scaled: Vec<i64> = vec![
            500_000_000_000, -300_000_000_000, 1_200_000_000_000, 800_000_000_000,
            -100_000_000_000, 400_000_000_000, -900_000_000_000, 600_000_000_000,
            200_000_000_000, -700_000_000_000, 1_000_000_000_000, -500_000_000_000,
        ];

        // Claim a ridiculously low energy that no VQE could achieve
        let fake_energy_scaled: i128 = -999_000_000_000_000; // -999.0

        assert!(
            !verify_energy(&seed, &params_scaled, fake_energy_scaled),
            "Fabricated energy should be rejected"
        );
    }

    /// Test that wrong parameter count is rejected.
    #[test]
    fn test_wrong_param_count_rejected() {
        let seed = H256::from([1u8; 32]);
        let params_scaled: Vec<i64> = vec![0; 8]; // Wrong: should be 12
        assert!(
            !verify_energy(&seed, &params_scaled, 0),
            "Wrong param count should be rejected"
        );
    }

    /// Test that a slightly perturbed energy within tolerance is accepted.
    #[test]
    fn test_within_tolerance_accepted() {
        let seed = H256::from([7u8; 32]);
        let params_f64 = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2];

        let ham = hamiltonian::generate_hamiltonian(&seed);
        let mut sv = Statevector::new(ansatz::N_QUBITS);
        ansatz::apply_ansatz(&mut sv, &params_f64);
        let energy = hamiltonian::compute_energy(&ham, &sv);

        let params_scaled: Vec<i64> = params_f64.iter().map(|&p| (p * SCALE_FACTOR) as i64).collect();
        let energy_scaled = (energy * SCALE_FACTOR) as i128;

        // Add a small perturbation within tolerance (1e-3 scaled = 1_000_000_000)
        let perturbed = energy_scaled + 1_000_000_000; // 1e-3 perturbation
        assert!(
            verify_energy(&seed, &params_scaled, perturbed),
            "Energy within tolerance should be accepted"
        );
    }

    /// Test that energy outside tolerance is rejected.
    #[test]
    fn test_outside_tolerance_rejected() {
        let seed = H256::from([7u8; 32]);
        let params_f64 = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2];

        let ham = hamiltonian::generate_hamiltonian(&seed);
        let mut sv = Statevector::new(ansatz::N_QUBITS);
        ansatz::apply_ansatz(&mut sv, &params_f64);
        let energy = hamiltonian::compute_energy(&ham, &sv);

        let params_scaled: Vec<i64> = params_f64.iter().map(|&p| (p * SCALE_FACTOR) as i64).collect();
        let energy_scaled = (energy * SCALE_FACTOR) as i128;

        // Add a large perturbation outside tolerance (0.1 scaled = 100_000_000_000)
        let perturbed = energy_scaled + 100_000_000_000; // 0.1 perturbation
        assert!(
            !verify_energy(&seed, &params_scaled, perturbed),
            "Energy outside tolerance should be rejected"
        );
    }

    /// Test determinism: same inputs always produce same result.
    #[test]
    fn test_deterministic_verification() {
        let seed = H256::from([55u8; 32]);
        let params_f64 = [1.0, -1.0, 0.5, -0.5, 0.3, -0.3, 0.8, -0.8, 0.1, -0.1, 0.6, -0.6];

        let ham = hamiltonian::generate_hamiltonian(&seed);
        let mut sv = Statevector::new(ansatz::N_QUBITS);
        ansatz::apply_ansatz(&mut sv, &params_f64);
        let energy = hamiltonian::compute_energy(&ham, &sv);

        let params_scaled: Vec<i64> = params_f64.iter().map(|&p| (p * SCALE_FACTOR) as i64).collect();
        let energy_scaled = (energy * SCALE_FACTOR) as i128;

        // Verify 10 times — must always be consistent
        for _ in 0..10 {
            assert!(verify_energy(&seed, &params_scaled, energy_scaled));
        }
    }
}
