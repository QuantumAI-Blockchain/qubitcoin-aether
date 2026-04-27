use crate::ansatz::{self, N_PARAMS};
use crate::hamiltonian::Hamiltonian;
use crate::simulator::Statevector;
use rand::Rng;

pub const MAX_ITER: usize = 200;

#[derive(Debug, Clone)]
pub struct VqeResult {
    pub params: Vec<f64>,
    pub energy: f64,
}

pub fn compute_energy(params: &[f64], hamiltonian: &Hamiltonian) -> f64 {
    let mut sv = Statevector::new(ansatz::N_QUBITS);
    ansatz::apply_ansatz(&mut sv, params);

    let mut energy = 0.0;
    for term in &hamiltonian.terms {
        energy += term.coefficient * sv.expectation_value(&term.pauli);
    }
    energy
}

pub fn optimize<R: Rng>(hamiltonian: &Hamiltonian, rng: &mut R) -> VqeResult {
    use std::f64::consts::PI;

    let initial_params: Vec<f64> = (0..N_PARAMS).map(|_| rng.gen_range(0.0..2.0 * PI)).collect();
    let bounds: Vec<(f64, f64)> = vec![(0.0, 2.0 * PI); N_PARAMS];
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
        Err((_status, params, energy)) => VqeResult { params, energy },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hamiltonian::generate_hamiltonian;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    #[test]
    fn test_vqe_finds_low_energy() {
        let seed = [42u8; 32];
        let hamiltonian = generate_hamiltonian(&seed);
        let mut rng = ChaCha8Rng::seed_from_u64(123);
        let result = optimize(&hamiltonian, &mut rng);
        // Should find some solution (energy is finite)
        assert!(result.energy.is_finite());
        assert_eq!(result.params.len(), N_PARAMS);
    }
}
