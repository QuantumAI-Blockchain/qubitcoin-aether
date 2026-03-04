//! TwoLocal ansatz circuit for VQE mining.
//!
//! Implements TwoLocal(4, 'ry', 'cz', 'linear', reps=2) matching
//! the Python implementation's circuit structure.
//!
//! Layout (reps=2, 4 qubits):
//! ```text
//! RY(θ₀..θ₃) → CZ(0,1) CZ(1,2) CZ(2,3) →
//! RY(θ₄..θ₇) → CZ(0,1) CZ(1,2) CZ(2,3) →
//! RY(θ₈..θ₁₁)
//! ```
//! Total: 12 parameters (3 rotation layers × 4 qubits).

use crate::simulator::Statevector;

/// Number of repetitions in the TwoLocal ansatz.
pub const REPS: usize = 2;
/// Number of qubits.
pub const N_QUBITS: usize = 4;
/// Total number of variational parameters: (reps + 1) * n_qubits.
pub const N_PARAMS: usize = (REPS + 1) * N_QUBITS;

/// Apply the TwoLocal ansatz circuit to a statevector.
///
/// # Arguments
/// * `sv` - The statevector to apply the circuit to (modified in place).
/// * `params` - Exactly `N_PARAMS` (12) rotation angles.
///
/// # Panics
/// Panics if `params.len() != N_PARAMS`.
pub fn apply_ansatz(sv: &mut Statevector, params: &[f64]) {
    assert_eq!(
        params.len(),
        N_PARAMS,
        "Expected {} params, got {}",
        N_PARAMS,
        params.len()
    );

    let mut idx = 0;

    for rep in 0..=REPS {
        // Rotation layer: RY on each qubit
        for q in 0..N_QUBITS {
            sv.ry(q, params[idx]);
            idx += 1;
        }

        // Entanglement layer (not after the last rotation layer)
        if rep < REPS {
            for q in 0..(N_QUBITS - 1) {
                sv.cz(q, q + 1);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_param_count() {
        assert_eq!(N_PARAMS, 12);
    }

    #[test]
    fn test_zero_params_identity() {
        // All-zero params: RY(0) = identity, so state stays |0000⟩
        let mut sv = Statevector::new(N_QUBITS);
        let params = vec![0.0; N_PARAMS];
        apply_ansatz(&mut sv, &params);
        assert!((sv.state[0].re - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_normalization_preserved() {
        let mut sv = Statevector::new(N_QUBITS);
        let params: Vec<f64> = (0..N_PARAMS)
            .map(|i| (i as f64) * 0.5 + 0.1)
            .collect();
        apply_ansatz(&mut sv, &params);

        let norm: f64 = sv.state.iter().map(|a| a.norm_sqr()).sum();
        assert!((norm - 1.0).abs() < 1e-10, "Norm = {}, expected 1.0", norm);
    }

    #[test]
    #[should_panic(expected = "Expected 12 params")]
    fn test_wrong_param_count() {
        let mut sv = Statevector::new(N_QUBITS);
        apply_ansatz(&mut sv, &[0.0; 8]);
    }

    #[test]
    fn test_different_params_different_states() {
        let params1 = vec![0.1; N_PARAMS];
        let params2 = vec![0.5; N_PARAMS];

        let mut sv1 = Statevector::new(N_QUBITS);
        apply_ansatz(&mut sv1, &params1);

        let mut sv2 = Statevector::new(N_QUBITS);
        apply_ansatz(&mut sv2, &params2);

        // States should differ
        let diff: f64 = sv1
            .state
            .iter()
            .zip(sv2.state.iter())
            .map(|(a, b)| (a - b).norm_sqr())
            .sum();
        assert!(diff > 1e-6, "Different params should produce different states");
    }
}
