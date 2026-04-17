//! TwoLocal ansatz circuit for VQE verification (no_std).
//!
//! Implements TwoLocal(4, 'ry', 'cz', 'linear', reps=2) — identical
//! to `qbc-mining::ansatz`.
//!
//! Layout (reps=2, 4 qubits):
//! ```text
//! RY(t0..t3) -> CZ(0,1) CZ(1,2) CZ(2,3) ->
//! RY(t4..t7) -> CZ(0,1) CZ(1,2) CZ(2,3) ->
//! RY(t8..t11)
//! ```
//! Total: 12 parameters (3 rotation layers x 4 qubits).

use crate::simulator::Statevector;

/// Number of repetitions in the TwoLocal ansatz.
pub const REPS: usize = 2;
/// Number of qubits.
pub const N_QUBITS: usize = 4;
/// Total number of variational parameters: (reps + 1) * n_qubits.
pub const N_PARAMS: usize = (REPS + 1) * N_QUBITS;

/// Apply the TwoLocal ansatz circuit to a statevector.
///
/// Returns `false` if `params.len() != N_PARAMS`.
pub fn apply_ansatz(sv: &mut Statevector, params: &[f64]) -> bool {
    if params.len() != N_PARAMS {
        return false;
    }

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

    true
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
        let mut sv = Statevector::new(N_QUBITS);
        let params = [0.0; N_PARAMS];
        assert!(apply_ansatz(&mut sv, &params));
        assert!((sv.state[0].re - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_wrong_param_count() {
        let mut sv = Statevector::new(N_QUBITS);
        assert!(!apply_ansatz(&mut sv, &[0.0; 8]));
    }

    #[test]
    fn test_normalization_preserved() {
        let mut sv = Statevector::new(N_QUBITS);
        let params: [f64; N_PARAMS] = [
            0.1, 0.6, 1.1, 1.6, 2.1, 2.6, 3.1, 3.6, 4.1, 4.6, 5.1, 5.6,
        ];
        assert!(apply_ansatz(&mut sv, &params));

        let norm: f64 = sv.state.iter().map(|a| a.norm_sqr()).sum();
        assert!((norm - 1.0).abs() < 1e-10, "Norm = {}, expected 1.0", norm);
    }
}
