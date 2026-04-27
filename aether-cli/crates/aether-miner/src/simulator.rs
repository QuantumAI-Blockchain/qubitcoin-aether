use num_complex::Complex64;

pub const N_QUBITS: usize = 4;
pub const DIM: usize = 1 << N_QUBITS;

pub struct Statevector {
    pub state: Vec<Complex64>,
}

impl Statevector {
    pub fn new(n_qubits: usize) -> Self {
        let dim = 1 << n_qubits;
        let mut state = vec![Complex64::new(0.0, 0.0); dim];
        state[0] = Complex64::new(1.0, 0.0);
        Self { state }
    }

    pub fn ry(&mut self, target: usize, theta: f64) {
        let cos = (theta / 2.0).cos();
        let sin = (theta / 2.0).sin();
        let n = self.state.len();
        let bit = 1 << target;

        for i in 0..n {
            if i & bit == 0 {
                let j = i | bit;
                let a0 = self.state[i];
                let a1 = self.state[j];
                self.state[i] = a0 * cos - a1 * sin;
                self.state[j] = a0 * sin + a1 * cos;
            }
        }
    }

    pub fn cz(&mut self, control: usize, target: usize) {
        let ctrl_bit = 1 << control;
        let tgt_bit = 1 << target;

        for i in 0..self.state.len() {
            if (i & ctrl_bit != 0) && (i & tgt_bit != 0) {
                self.state[i] = -self.state[i];
            }
        }
    }

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
    use std::f64::consts::PI;

    #[test]
    fn test_initial_state() {
        let sv = Statevector::new(4);
        assert_eq!(sv.state.len(), 16);
        assert!((sv.state[0].re - 1.0).abs() < 1e-12);
    }

    #[test]
    fn test_ry_pi() {
        let mut sv = Statevector::new(1);
        sv.ry(0, PI);
        assert!(sv.state[0].norm() < 1e-10);
        assert!((sv.state[1].re - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_z_expectation() {
        let sv = Statevector::new(1);
        assert!((sv.expectation_value(b"Z") - 1.0).abs() < 1e-10);
    }
}
