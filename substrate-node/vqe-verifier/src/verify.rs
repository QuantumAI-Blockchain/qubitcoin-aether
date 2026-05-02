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
/// Both the mining engine and the runtime pallet use vqe-verifier's
/// simulator/ansatz/hamiltonian code, so floating-point results should
/// be bit-identical. The tolerance is kept tight to prevent fraud.
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

/// Compute the VQE energy from params and seed, returning the scaled energy.
///
/// This is the authoritative energy computation used by the runtime pallet.
/// The miner submits only parameters; the runtime computes the energy itself
/// and checks if it's below difficulty. This eliminates FP divergence between
/// native (mining engine) and WASM (runtime pallet) execution environments.
///
/// # Returns
/// `Some(energy_scaled)` on success, `None` if params are invalid.
pub fn compute_energy_versioned(
    seed: &H256,
    params_scaled: &[i64],
    theta_scaled: i64,
    version: u8,
) -> Option<i128> {
    if params_scaled.len() != ansatz::N_PARAMS {
        return None;
    }
    let params: Vec<f64> = params_scaled
        .iter()
        .map(|&p| p as f64 / SCALE_FACTOR)
        .collect();
    let ham = match version {
        1 => hamiltonian::generate_hamiltonian(seed),
        _ => {
            let theta = theta_scaled as f64 / SCALE_FACTOR;
            hamiltonian::generate_hamiltonian_v2(seed, theta)
        }
    };
    let mut sv = Statevector::new(ansatz::N_QUBITS);
    if !ansatz::apply_ansatz(&mut sv, &params) {
        return None;
    }
    let computed_energy = hamiltonian::compute_energy(&ham, &sv);
    Some((computed_energy * SCALE_FACTOR) as i128)
}

/// Debug helper: compute the energy that the verifier would produce for the given
/// seed, params, theta, and version. Returns the energy as i128 scaled by 10^12.
pub fn debug_compute_energy(
    seed: &H256,
    params_scaled: &[i64],
    theta_scaled: i64,
    version: u8,
) -> i128 {
    if params_scaled.len() != ansatz::N_PARAMS {
        return 0;
    }
    let params: Vec<f64> = params_scaled
        .iter()
        .map(|&p| p as f64 / SCALE_FACTOR)
        .collect();
    let ham = match version {
        1 => hamiltonian::generate_hamiltonian(seed),
        _ => {
            let theta = theta_scaled as f64 / SCALE_FACTOR;
            hamiltonian::generate_hamiltonian_v2(seed, theta)
        }
    };
    let mut sv = Statevector::new(ansatz::N_QUBITS);
    if !ansatz::apply_ansatz(&mut sv, &params) {
        return 0;
    }
    let computed_energy = hamiltonian::compute_energy(&ham, &sv);
    (computed_energy * SCALE_FACTOR) as i128
}

/// Verify VQE energy with version awareness.
///
/// - version 1: Uses v1 Hamiltonian (5 random Pauli terms)
/// - version 2: Uses v2 SUGRA Hamiltonian (9 structured + random terms)
///
/// The `theta_scaled` parameter is only used for version 2 (ignored for v1).
///
/// # Arguments
/// * `seed` - The Hamiltonian seed (H256, derived from parent block hash)
/// * `params_scaled` - VQE parameters scaled by 10^12 (from `VqeProof.params`)
/// * `claimed_energy_scaled` - Claimed energy scaled by 10^12 (from `VqeProof.energy`)
/// * `theta_scaled` - Network bimetric theta in radians, scaled by 10^12
/// * `version` - Hamiltonian version (1 = legacy, 2+ = SUGRA bimetric)
///
/// # Returns
/// `true` if `|claimed_energy_scaled - computed_energy_scaled| <= TOLERANCE_SCALED`
pub fn verify_energy_versioned(
    seed: &H256,
    params_scaled: &[i64],
    claimed_energy_scaled: i128,
    theta_scaled: i64,
    version: u8,
) -> bool {
    // Validate parameter count
    if params_scaled.len() != ansatz::N_PARAMS {
        return false;
    }

    // Unscale parameters
    let params: Vec<f64> = params_scaled
        .iter()
        .map(|&p| p as f64 / SCALE_FACTOR)
        .collect();

    // Generate appropriate Hamiltonian
    let ham = match version {
        1 => hamiltonian::generate_hamiltonian(seed),
        _ => {
            let theta = theta_scaled as f64 / SCALE_FACTOR;
            hamiltonian::generate_hamiltonian_v2(seed, theta)
        }
    };

    // Initialize statevector and apply ansatz
    let mut sv = Statevector::new(ansatz::N_QUBITS);
    if !ansatz::apply_ansatz(&mut sv, &params) {
        return false;
    }

    // Compute and compare energy
    let computed_energy = hamiltonian::compute_energy(&ham, &sv);
    let computed_scaled = (computed_energy * SCALE_FACTOR) as i128;

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

    // ── verify_energy_versioned tests ───────────────────────────

    /// Helper: compute the correct scaled energy for v2 Hamiltonian.
    fn compute_v2_energy_scaled(seed: &H256, theta: f64, params_f64: &[f64; 12]) -> (Vec<i64>, i128, i64) {
        let ham = hamiltonian::generate_hamiltonian_v2(seed, theta);
        let mut sv = Statevector::new(ansatz::N_QUBITS);
        ansatz::apply_ansatz(&mut sv, params_f64);
        let energy = hamiltonian::compute_energy(&ham, &sv);

        let params_scaled: Vec<i64> = params_f64.iter().map(|&p| (p * SCALE_FACTOR) as i64).collect();
        let energy_scaled = (energy * SCALE_FACTOR) as i128;
        let theta_scaled = (theta * SCALE_FACTOR) as i64;

        (params_scaled, energy_scaled, theta_scaled)
    }

    /// Test that verify_energy_versioned accepts a correctly computed v2 proof.
    #[test]
    fn test_v2_valid_proof_accepted() {
        let seed = H256::from([42u8; 32]);
        let params_f64 = [0.5, -0.3, 1.2, 0.8, -0.1, 0.4, -0.9, 0.6, 0.2, -0.7, 1.0, -0.5];
        let theta = 0.789;

        let (params_scaled, energy_scaled, theta_scaled) =
            compute_v2_energy_scaled(&seed, theta, &params_f64);

        assert!(
            verify_energy_versioned(&seed, &params_scaled, energy_scaled, theta_scaled, 2),
            "Valid v2 proof should be accepted",
        );
    }

    /// Test that different theta values produce different energy landscapes.
    #[test]
    fn test_v2_different_theta_different_energy() {
        let seed = H256::from([42u8; 32]);
        let params_f64 = [0.5, -0.3, 1.2, 0.8, -0.1, 0.4, -0.9, 0.6, 0.2, -0.7, 1.0, -0.5];

        let (_, energy_a, _) = compute_v2_energy_scaled(&seed, 0.0, &params_f64);
        let (_, energy_b, _) = compute_v2_energy_scaled(&seed, core::f64::consts::FRAC_PI_2, &params_f64);

        assert_ne!(
            energy_a, energy_b,
            "Different theta should produce different energy landscapes",
        );
    }

    /// Test that v1 path still works through the versioned function.
    #[test]
    fn test_v1_still_works() {
        let seed = H256::from([42u8; 32]);
        let params_f64 = [0.5, -0.3, 1.2, 0.8, -0.1, 0.4, -0.9, 0.6, 0.2, -0.7, 1.0, -0.5];

        let ham = hamiltonian::generate_hamiltonian(&seed);
        let mut sv = Statevector::new(ansatz::N_QUBITS);
        ansatz::apply_ansatz(&mut sv, &params_f64);
        let energy = hamiltonian::compute_energy(&ham, &sv);

        let params_scaled: Vec<i64> = params_f64.iter().map(|&p| (p * SCALE_FACTOR) as i64).collect();
        let energy_scaled = (energy * SCALE_FACTOR) as i128;

        // Version 1 through versioned function should match direct verify_energy
        assert!(
            verify_energy_versioned(&seed, &params_scaled, energy_scaled, 0, 1),
            "v1 path through versioned function should accept valid v1 proof",
        );
        assert!(
            verify_energy(&seed, &params_scaled, energy_scaled),
            "Direct v1 should still work",
        );
    }

    /// Test that fabricated energy is rejected by v2 path.
    #[test]
    fn test_v2_fake_energy_rejected() {
        let seed = H256::from([42u8; 32]);
        let params_f64 = [0.5, -0.3, 1.2, 0.8, -0.1, 0.4, -0.9, 0.6, 0.2, -0.7, 1.0, -0.5];
        let theta = 0.789;

        let (params_scaled, _, theta_scaled) =
            compute_v2_energy_scaled(&seed, theta, &params_f64);

        let fake_energy: i128 = -999_000_000_000_000; // -999.0

        assert!(
            !verify_energy_versioned(&seed, &params_scaled, fake_energy, theta_scaled, 2),
            "Fabricated energy should be rejected by v2 path",
        );
    }

    /// Test that v1 energy does not verify against v2 Hamiltonian.
    #[test]
    fn test_version_mismatch_rejected() {
        let seed = H256::from([42u8; 32]);
        let params_f64 = [0.5, -0.3, 1.2, 0.8, -0.1, 0.4, -0.9, 0.6, 0.2, -0.7, 1.0, -0.5];
        let theta = 0.789;

        // Compute correct energy for v1
        let ham_v1 = hamiltonian::generate_hamiltonian(&seed);
        let mut sv = Statevector::new(ansatz::N_QUBITS);
        ansatz::apply_ansatz(&mut sv, &params_f64);
        let energy_v1 = hamiltonian::compute_energy(&ham_v1, &sv);
        let energy_v1_scaled = (energy_v1 * SCALE_FACTOR) as i128;

        let params_scaled: Vec<i64> = params_f64.iter().map(|&p| (p * SCALE_FACTOR) as i64).collect();
        let theta_scaled = (theta * SCALE_FACTOR) as i64;

        // v1 energy should NOT verify against v2 Hamiltonian
        // (they produce different Hamiltonians, so energy will differ)
        // Note: there is a tiny theoretical chance they match — use assertion message
        assert!(
            !verify_energy_versioned(&seed, &params_scaled, energy_v1_scaled, theta_scaled, 2),
            "v1 energy should not pass v2 verification (different Hamiltonian)",
        );
    }
}
