//! 4-qubit statevector quantum simulator.
//!
//! Operates on a `Vec<Complex64>` of length 2^n (16 for 4 qubits).
//! Supports RY and CZ gates, plus Pauli expectation value computation.

use num_complex::Complex64;

/// Number of qubits in the simulation.
pub const N_QUBITS: usize = 4;
/// Dimension of the statevector (2^N_QUBITS).
pub const DIM: usize = 1 << N_QUBITS;

/// A statevector quantum simulator.
pub struct Statevector {
    /// Amplitudes: `state[i]` is the amplitude of basis state `|i⟩`.
    pub state: Vec<Complex64>,
}

impl Statevector {
    /// Create a new simulator initialized to |0...0⟩.
    pub fn new(n_qubits: usize) -> Self {
        let dim = 1 << n_qubits;
        let mut state = vec![Complex64::new(0.0, 0.0); dim];
        state[0] = Complex64::new(1.0, 0.0);
        Self { state }
    }

    /// Apply RY(theta) gate to the target qubit.
    ///
    /// RY(θ) = [[cos(θ/2), -sin(θ/2)],
    ///          [sin(θ/2),  cos(θ/2)]]
    pub fn ry(&mut self, target: usize, theta: f64) {
        let cos = (theta / 2.0).cos();
        let sin = (theta / 2.0).sin();
        let n = self.state.len();
        let bit = 1 << target;

        let mut i = 0;
        while i < n {
            // Process pairs where bit `target` differs
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
    /// CZ flips the sign of amplitudes where both qubits are |1⟩.
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
    /// Each character in `pauli` must be 'I', 'X', 'Y', or 'Z'.
    /// Computes ⟨ψ|P₀⊗P₁⊗...⊗Pₙ|ψ⟩ efficiently using bit-manipulation.
    pub fn expectation_value(&self, pauli: &[u8]) -> f64 {
        let n = self.state.len();
        let mut result = 0.0;

        for i in 0..n {
            // Apply the Pauli string to basis state |i⟩ to get coeff * |j⟩
            let mut j = i;
            let mut coeff = Complex64::new(1.0, 0.0);

            for (q, &p) in pauli.iter().enumerate() {
                let bit = (i >> q) & 1;
                match p {
                    b'I' => {}
                    b'X' => {
                        // X|0⟩ = |1⟩, X|1⟩ = |0⟩
                        j ^= 1 << q;
                    }
                    b'Y' => {
                        // Y|0⟩ = i|1⟩, Y|1⟩ = -i|0⟩
                        j ^= 1 << q;
                        if bit == 0 {
                            coeff *= Complex64::new(0.0, 1.0);
                        } else {
                            coeff *= Complex64::new(0.0, -1.0);
                        }
                    }
                    b'Z' => {
                        // Z|0⟩ = |0⟩, Z|1⟩ = -|1⟩
                        if bit == 1 {
                            coeff *= Complex64::new(-1.0, 0.0);
                        }
                    }
                    _ => {}
                }
            }

            // ⟨ψ|P|ψ⟩ contribution: conj(ψ[i]) * coeff * ψ[j]
            result += (self.state[i].conj() * coeff * self.state[j]).re;
        }

        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::f64::consts::PI;

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
        // RY(π)|0⟩ = |1⟩
        let mut sv = Statevector::new(1);
        sv.ry(0, PI);
        assert!(sv.state[0].norm() < 1e-10);
        assert!((sv.state[1].re - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_ry_halfpi_creates_superposition() {
        // RY(π/2)|0⟩ = (|0⟩ + |1⟩)/√2
        let mut sv = Statevector::new(1);
        sv.ry(0, PI / 2.0);
        let expected = 1.0 / 2.0_f64.sqrt();
        assert!((sv.state[0].re - expected).abs() < 1e-10);
        assert!((sv.state[1].re - expected).abs() < 1e-10);
    }

    #[test]
    fn test_cz_sign_flip() {
        // Put both qubits in |1⟩, then CZ should flip the sign of |11⟩
        let mut sv = Statevector::new(2);
        sv.ry(0, PI); // |0⟩ → |1⟩ on qubit 0
        sv.ry(1, PI); // |0⟩ → |1⟩ on qubit 1
        // State is |11⟩ = state[3]
        assert!((sv.state[3].re - 1.0).abs() < 1e-10);
        sv.cz(0, 1);
        // After CZ, |11⟩ should become -|11⟩
        assert!((sv.state[3].re + 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_z_expectation_ground() {
        // ⟨0|Z|0⟩ = +1
        let sv = Statevector::new(1);
        let exp = sv.expectation_value(b"Z");
        assert!((exp - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_z_expectation_excited() {
        // ⟨1|Z|1⟩ = -1
        let mut sv = Statevector::new(1);
        sv.ry(0, PI);
        let exp = sv.expectation_value(b"Z");
        assert!((exp + 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_x_expectation_superposition() {
        // ⟨+|X|+⟩ = 1 where |+⟩ = RY(π/2)|0⟩
        let mut sv = Statevector::new(1);
        sv.ry(0, PI / 2.0);
        let exp = sv.expectation_value(b"X");
        assert!((exp - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_identity_expectation() {
        // ⟨ψ|I⊗I⊗I⊗I|ψ⟩ = 1 for any normalized state
        let sv = Statevector::new(4);
        let exp = sv.expectation_value(b"IIII");
        assert!((exp - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_multi_qubit_pauli() {
        // ⟨00|ZZ|00⟩ = (+1)(+1) = 1
        let sv = Statevector::new(2);
        let exp = sv.expectation_value(b"ZZ");
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
