"""Tests for Graph-to-SUSY-Hamiltonian conversion (Batch 17.1/17.2)."""
import pytest
from dataclasses import dataclass

from qubitcoin.qvm.hamiltonian_risk import (
    GraphToHamiltonianConverter,
    HamiltonianTerm,
    RiskHamiltonian,
    energy_to_risk_score,
    _zz_label,
    _z_label,
    _x_label,
)
from qubitcoin.qvm.tx_graph import TransactionGraph, TxEdge, GraphNode


def _build_simple_graph():
    """Build a small 4-node transaction graph."""
    g = TransactionGraph()
    g.add_transaction('alice', 'bob', 10.0, 1)
    g.add_transaction('bob', 'charlie', 5.0, 2)
    g.add_transaction('charlie', 'dave', 2.0, 3)
    g.add_transaction('alice', 'dave', 1.0, 4)
    return g


class TestPauliLabels:
    """Test Pauli label construction."""

    def test_zz_label(self):
        assert _zz_label(4, 0, 1) == 'ZZII'

    def test_zz_label_non_adjacent(self):
        assert _zz_label(4, 0, 3) == 'ZIIZ'

    def test_z_label(self):
        assert _z_label(4, 2) == 'IIZI'

    def test_x_label(self):
        assert _x_label(3, 0) == 'XII'

    def test_z_label_last(self):
        assert _z_label(3, 2) == 'IIZ'


class TestGraphToHamiltonian:
    """Test conversion of transaction graph to Hamiltonian."""

    def test_empty_graph(self):
        conv = GraphToHamiltonianConverter()
        h = conv.convert({}, [], seed='addr')
        assert h.n_qubits == 0
        assert len(h.terms) == 0

    def test_simple_graph_produces_terms(self):
        g = _build_simple_graph()
        nodes = g.build_subgraph('alice')
        edges = g.get_transactions('alice') + g.get_transactions('bob') + g.get_transactions('charlie')
        conv = GraphToHamiltonianConverter()
        h = conv.convert(nodes, edges, seed='alice')
        assert h.n_qubits == 4
        assert len(h.terms) > 0
        assert h.seed_address == 'alice'

    def test_has_coupling_and_field_terms(self):
        g = _build_simple_graph()
        nodes = g.build_subgraph('alice')
        edges = []
        for addr in nodes:
            edges.extend(g.get_transactions(addr))
        conv = GraphToHamiltonianConverter()
        h = conv.convert(nodes, edges, seed='alice')

        pauli_types = set()
        for t in h.terms:
            chars = set(t.pauli_label) - {'I'}
            pauli_types.update(chars)
        # Should have Z (self-energy + coupling) and X (transverse field)
        assert 'Z' in pauli_types
        assert 'X' in pauli_types

    def test_flagged_address_higher_self_energy(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 1.0, 1)
        nodes = g.build_subgraph('a')
        edges = g.get_transactions('a')
        conv = GraphToHamiltonianConverter()

        h_clean = conv.convert(nodes, edges, seed='a')
        h_flagged = conv.convert(nodes, edges, seed='a', flagged_addresses={'b'})

        # Find Z-only terms for 'b' qubit
        def z_coeff_for_b(h):
            idx = h.address_map.get('b')
            if idx is None:
                return 0.0
            label = _z_label(h.n_qubits, idx)
            for t in h.terms:
                if t.pauli_label == label:
                    return t.coefficient
            return 0.0

        assert z_coeff_for_b(h_flagged) > z_coeff_for_b(h_clean)

    def test_max_qubits_limit(self):
        g = TransactionGraph()
        for i in range(20):
            g.add_transaction(f'addr_{i}', f'addr_{i+1}', 1.0, i)
        nodes = g.build_subgraph('addr_0')
        edges = []
        for addr in list(nodes.keys())[:10]:
            edges.extend(g.get_transactions(addr))
        conv = GraphToHamiltonianConverter(max_qubits=8)
        h = conv.convert(nodes, edges, seed='addr_0')
        assert h.n_qubits <= 8

    def test_address_map_consistent(self):
        g = _build_simple_graph()
        nodes = g.build_subgraph('alice')
        conv = GraphToHamiltonianConverter()
        h = conv.convert(nodes, [])
        assert len(h.address_map) == h.n_qubits
        for addr, idx in h.address_map.items():
            assert 0 <= idx < h.n_qubits

    def test_hamiltonian_to_dict(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 1.0, 1)
        nodes = g.build_subgraph('a')
        conv = GraphToHamiltonianConverter()
        h = conv.convert(nodes, g.get_transactions('a'))
        d = h.to_dict()
        assert 'n_qubits' in d
        assert 'terms' in d
        assert 'num_terms' in d

    def test_total_flow_tracked(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 10.0, 1)
        g.add_transaction('b', 'a', 5.0, 2)
        nodes = g.build_subgraph('a')
        edges = g.get_transactions('a') + g.get_transactions('b')
        conv = GraphToHamiltonianConverter()
        h = conv.convert(nodes, edges, seed='a')
        assert h.total_flow > 0


class TestGroundStateEnergy:
    """Test ground-state energy computation."""

    def test_empty_hamiltonian(self):
        conv = GraphToHamiltonianConverter()
        h = RiskHamiltonian(n_qubits=0)
        assert conv.estimate_ground_energy(h) == 0.0

    def test_single_z_term(self):
        conv = GraphToHamiltonianConverter()
        h = RiskHamiltonian(
            n_qubits=1,
            terms=[HamiltonianTerm(pauli_label='Z', coefficient=1.0)],
        )
        energy = conv.estimate_ground_energy(h)
        # Ground state of Z is -1
        assert energy == pytest.approx(-1.0, abs=0.01)

    def test_two_qubit_zz(self):
        conv = GraphToHamiltonianConverter()
        h = RiskHamiltonian(
            n_qubits=2,
            terms=[HamiltonianTerm(pauli_label='ZZ', coefficient=1.0)],
        )
        energy = conv.estimate_ground_energy(h)
        # Ground state of ZZ is -1 (|00> or |11>)
        assert energy == pytest.approx(-1.0, abs=0.01)

    def test_exact_for_small_systems(self):
        conv = GraphToHamiltonianConverter()
        # H = Z + X (single qubit)
        h = RiskHamiltonian(
            n_qubits=1,
            terms=[
                HamiltonianTerm(pauli_label='Z', coefficient=1.0),
                HamiltonianTerm(pauli_label='X', coefficient=1.0),
            ],
        )
        energy = conv.estimate_ground_energy(h)
        # Eigenvalues of Z+X are ±√2
        import math
        assert energy == pytest.approx(-math.sqrt(2), abs=0.01)

    def test_mean_field_for_large_systems(self):
        conv = GraphToHamiltonianConverter()
        terms = [HamiltonianTerm(pauli_label='Z' + 'I' * 9, coefficient=0.5)]
        h = RiskHamiltonian(n_qubits=10, terms=terms)
        energy = conv.estimate_ground_energy(h)
        # Mean-field should return a negative value
        assert energy < 0

    def test_energy_deterministic(self):
        conv = GraphToHamiltonianConverter()
        h = RiskHamiltonian(
            n_qubits=2,
            terms=[
                HamiltonianTerm(pauli_label='ZZ', coefficient=1.0),
                HamiltonianTerm(pauli_label='XI', coefficient=0.3),
            ],
        )
        e1 = conv.estimate_ground_energy(h)
        e2 = conv.estimate_ground_energy(h)
        assert e1 == e2


class TestEnergyToRiskScore:
    """Test energy-to-risk conversion."""

    def test_zero_qubits(self):
        assert energy_to_risk_score(0.0, 0) == 0.0

    def test_low_energy_low_risk(self):
        score = energy_to_risk_score(-4.0, 4)
        assert score < 50

    def test_high_energy_high_risk(self):
        score = energy_to_risk_score(4.0, 4)
        assert score > 50

    def test_clamped_to_0_100(self):
        score = energy_to_risk_score(-1000.0, 2)
        assert 0 <= score <= 100
        score = energy_to_risk_score(1000.0, 2)
        assert 0 <= score <= 100

    def test_monotonic(self):
        s1 = energy_to_risk_score(-2.0, 4)
        s2 = energy_to_risk_score(0.0, 4)
        s3 = energy_to_risk_score(2.0, 4)
        assert s1 < s2 < s3
