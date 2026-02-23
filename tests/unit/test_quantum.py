"""Unit tests for quantum engine — Hamiltonian generation, VQE, validation."""
import pytest
import numpy as np
from qubitcoin.quantum.engine import QuantumEngine


class TestHamiltonianGeneration:
    """Tests for Hamiltonian generation from chain state."""

    def test_basic_generation(self):
        """Hamiltonian has num_qubits+1 terms, correct structure."""
        qe = QuantumEngine()
        hamiltonian = qe.generate_hamiltonian(num_qubits=4)
        assert len(hamiltonian) == 5  # num_qubits + 1
        assert all(isinstance(coeff, float) for _, coeff in hamiltonian)
        assert all(len(pauli) == 4 for pauli, _ in hamiltonian)

    def test_deterministic_same_seed(self):
        """Same prev_hash + height produces identical Hamiltonian."""
        qe = QuantumEngine()
        h1 = qe.generate_hamiltonian(prev_hash='ab' * 32, height=100)
        h2 = qe.generate_hamiltonian(prev_hash='ab' * 32, height=100)
        assert h1 == h2

    def test_deterministic_different_height(self):
        """Different height produces different Hamiltonian."""
        qe = QuantumEngine()
        h1 = qe.generate_hamiltonian(prev_hash='ab' * 32, height=100)
        h2 = qe.generate_hamiltonian(prev_hash='ab' * 32, height=101)
        assert h1 != h2

    def test_deterministic_different_hash(self):
        """Different prev_hash produces different Hamiltonian."""
        qe = QuantumEngine()
        h1 = qe.generate_hamiltonian(prev_hash='ab' * 32, height=100)
        h2 = qe.generate_hamiltonian(prev_hash='cd' * 32, height=100)
        assert h1 != h2

    def test_pauli_characters_valid(self):
        """All Pauli strings use only I, X, Y, Z."""
        qe = QuantumEngine()
        hamiltonian = qe.generate_hamiltonian(num_qubits=4, seed=42)
        for pauli, _ in hamiltonian:
            assert all(c in 'IXYZ' for c in pauli)

    def test_coefficients_bounded(self):
        """Coefficients are in [-1, 1] range."""
        qe = QuantumEngine()
        hamiltonian = qe.generate_hamiltonian(num_qubits=4, seed=42)
        for _, coeff in hamiltonian:
            assert -1.0 <= coeff <= 1.0

    def test_seed_derivation(self):
        """derive_hamiltonian_seed is deterministic and returns uint32."""
        qe = QuantumEngine()
        seed = qe.derive_hamiltonian_seed('aa' * 32, 0)
        assert isinstance(seed, int)
        assert 0 <= seed < 2**32
        assert seed == qe.derive_hamiltonian_seed('aa' * 32, 0)

    def test_different_qubit_counts(self):
        """Hamiltonian term count scales with qubit count."""
        qe = QuantumEngine()
        h2 = qe.generate_hamiltonian(num_qubits=2, seed=1)
        h6 = qe.generate_hamiltonian(num_qubits=6, seed=1)
        assert len(h2) == 3  # 2 + 1
        assert len(h6) == 7  # 6 + 1

    def test_pauli_string_length_matches_qubits(self):
        """Pauli strings have length equal to num_qubits."""
        qe = QuantumEngine()
        for n in [2, 4, 6]:
            h = qe.generate_hamiltonian(num_qubits=n, seed=99)
            for pauli, _ in h:
                assert len(pauli) == n

    def test_random_without_seed(self):
        """Without seed, two calls produce different Hamiltonians (probabilistic)."""
        qe = QuantumEngine()
        h1 = qe.generate_hamiltonian(num_qubits=4)
        h2 = qe.generate_hamiltonian(num_qubits=4)
        # Very unlikely to be identical
        assert h1 != h2


class TestVQEOptimization:
    """Tests for VQE optimization (mining core)."""

    def test_basic_vqe(self):
        """VQE returns params array and float energy."""
        qe = QuantumEngine()
        hamiltonian = qe.generate_hamiltonian(num_qubits=4, seed=42)
        params, energy = qe.optimize_vqe(hamiltonian)
        assert isinstance(params, np.ndarray)
        assert isinstance(energy, float)
        assert len(params) > 0

    def test_energy_is_real(self):
        """Energy must be a real finite number."""
        qe = QuantumEngine()
        hamiltonian = qe.generate_hamiltonian(num_qubits=4, seed=42)
        _, energy = qe.optimize_vqe(hamiltonian)
        assert np.isfinite(energy)

    def test_vqe_with_initial_params(self):
        """VQE accepts explicit initial parameters."""
        qe = QuantumEngine()
        hamiltonian = qe.generate_hamiltonian(num_qubits=4, seed=42)
        ansatz = qe.create_ansatz(4)
        n_params = getattr(ansatz, 'num_parameters', 12)
        if not isinstance(n_params, int):
            n_params = 12  # Fallback for stub environments
        init = np.zeros(n_params)
        params, energy = qe.optimize_vqe(hamiltonian, initial_params=init)
        assert isinstance(energy, float)
