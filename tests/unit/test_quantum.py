"""Unit tests for quantum engine"""
import pytest
import numpy as np
from qubitcoin.quantum.engine import QuantumEngine


def test_hamiltonian_generation():
    """Test Hamiltonian generation"""
    qe = QuantumEngine()
    hamiltonian = qe.generate_hamiltonian(num_qubits=4)
    
    assert len(hamiltonian) == 5  # num_qubits + 1
    assert all(isinstance(coeff, float) for coeff, _ in hamiltonian)
    assert all(len(pauli) == 4 for _, pauli in hamiltonian)


def test_vqe_optimization():
    """Test VQE optimization"""
    qe = QuantumEngine()
    hamiltonian = qe.generate_hamiltonian(num_qubits=4)
    
    params, energy = qe.optimize_vqe(hamiltonian)
    
    assert isinstance(params, np.ndarray)
    assert isinstance(energy, float)
    assert len(params) > 0
