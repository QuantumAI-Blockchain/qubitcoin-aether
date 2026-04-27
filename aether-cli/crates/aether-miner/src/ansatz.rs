use crate::simulator::Statevector;

pub const REPS: usize = 2;
pub const N_QUBITS: usize = 4;
pub const N_PARAMS: usize = (REPS + 1) * N_QUBITS;

pub fn apply_ansatz(sv: &mut Statevector, params: &[f64]) {
    assert_eq!(params.len(), N_PARAMS, "Expected {N_PARAMS} params, got {}", params.len());

    let mut idx = 0;
    for rep in 0..=REPS {
        for q in 0..N_QUBITS {
            sv.ry(q, params[idx]);
            idx += 1;
        }
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
    fn test_zero_params() {
        let mut sv = Statevector::new(N_QUBITS);
        apply_ansatz(&mut sv, &[0.0; N_PARAMS]);
        assert!((sv.state[0].re - 1.0).abs() < 1e-10);
    }
}
