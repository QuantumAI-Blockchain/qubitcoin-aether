//! no_std 4-qubit statevector quantum simulator.
//!
//! Identical logic to `qbc-mining::simulator` but uses `libm` for trig
//! functions and `alloc::vec::Vec` instead of `std::vec::Vec`.

#[cfg(not(feature = "std"))]
use alloc::vec;
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

use num_complex::Complex64;

/// Number of qubits in the simulation.
pub const N_QUBITS: usize = 4;
/// Dimension of the statevector (2^N_QUBITS).
pub const DIM: usize = 1 << N_QUBITS;

/// A statevector quantum simulator.
pub struct Statevector {
    /// Amplitudes: `state[i]` is the amplitude of basis state `|i>`.
    pub state: Vec<Complex64>,
}

impl Statevector {
    /// Create a new simulator initialized to |0...0>.
    pub fn new(n_qubits: usize) -> Self {
        let dim = 1 << n_qubits;
        let mut state = vec![Complex64::new(0.0, 0.0); dim];
        state[0] = Complex64::new(1.0, 0.0);
        Self { state }
    }

    /// Apply RY(theta) gate to the target qubit.
    ///
    /// RY(t) = [[cos(t/2), -sin(t/2)],
    ///          [sin(t/2),  cos(t/2)]]
    pub fn ry(&mut self, target: usize, theta: f64) {
        let half = theta / 2.0;
        let cos = libm::cos(half);
        let sin = libm::sin(half);
        let n = self.state.len();
        let bit = 1 << target;

        let mut i = 0;
        while i < n {
            if i & bit == 0 {
                let j = i | bit;
                let a0 = self.state[i];
                let a1 = self.state[j];
                self.state[i] = a0 * cos - a1 * sin;
                self.state[j] = a0 * sin + a1 * cos;
            }
            i += 1;
        }
    }

    /// Apply CZ gate between control and target qubits.
    ///
    /// CZ flips the sign of amplitudes where both qubits are |1>.
    pub fn cz(&mut self, control: usize, target: usize) {
        let ctrl_bit = 1 << control;
        let tgt_bit = 1 << target;

        for i in 0..self.state.len() {
            if (i & ctrl_bit != 0) && (i & tgt_bit != 0) {
                self.state[i] = -self.state[i];
            }
        }
    }

    /// Compute the expectation value of a Pauli string.
    ///
    /// Each character in `pauli` must be b'I', b'X', b'Y', or b'Z'.
    /// Computes <psi|P0 x P1 x ... x Pn|psi> efficiently.
    pub fn expectation_value(&self, pauli: &[u8]) -> f64 {
        let n = self.state.len();
        let mut result = 0.0;

        for i in 0..n {
            let mut j = i;
            let mut coeff = Complex64::new(1.0, 0.0);

            for (q, &p) in pauli.iter().enumerate() {
                let bit = (i >> q) & 1;
                match p {
                    b'I' => {}
                    b'X' => {
                        j ^= 1 << q;
                    }
                    b'Y' => {
                        j ^= 1 << q;
                        if bit == 0 {
                            coeff *= Complex64::new(0.0, 1.0);
                        } else {
                            coeff *= Complex64::new(0.0, -1.0);
                        }
                    }
                    b'Z' => {
                        if bit == 1 {
                            coeff *= Complex64::new(-1.0, 0.0);
                        }
                    }
                    _ => {}
                }
            }

            result += (self.state[i].conj() * coeff * self.state[j]).re;
        }

        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use core::f64::consts::PI;

    #[test]
    fn test_initial_state() {
        let sv = Statevector::new(4);
        assert_eq!(sv.state.len(), 16);
        assert!((sv.state[0].re - 1.0).abs() < 1e-12);
        for i in 1..16 {
            assert!(sv.state[i].norm() < 1e-12);
        }
    }

    #[test]
    fn test_ry_pi_creates_one() {
        let mut sv = Statevector::new(1);
        sv.ry(0, PI);
        assert!(sv.state[0].norm() < 1e-10);
        assert!((sv.state[1].re - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_z_expectation_ground() {
        let sv = Statevector::new(1);
        let exp = sv.expectation_value(b"Z");
        assert!((exp - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_z_expectation_excited() {
        let mut sv = Statevector::new(1);
        sv.ry(0, PI);
        let exp = sv.expectation_value(b"Z");
        assert!((exp + 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_identity_expectation() {
        let sv = Statevector::new(4);
        let exp = sv.expectation_value(b"IIII");
        assert!((exp - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_normalization_preserved_after_gates() {
        let mut sv = Statevector::new(4);
        sv.ry(0, 1.23);
        sv.ry(1, 0.45);
        sv.cz(0, 1);
        sv.ry(2, 2.34);
        sv.cz(1, 2);

        let norm: f64 = sv.state.iter().map(|a| a.norm_sqr()).sum();
        assert!((norm - 1.0).abs() < 1e-10);
    }
}
