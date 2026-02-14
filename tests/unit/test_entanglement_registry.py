"""Tests for entanglement registry and lazy measurement (Batch 13.2)."""
import pytest

from qubitcoin.qvm.state import QuantumStateStore


class TestEntanglementRegistry:
    """Verify entanglement tracking between quantum states."""

    def test_entangle_creates_bidirectional_link(self):
        store = QuantumStateStore()
        store.create(100, 4, 'alice', 10)
        store.create(200, 4, 'bob', 10)
        assert store.entangle(100, 200) is True
        assert store.get(100)['entangled_with'] == 200
        assert store.get(200)['entangled_with'] == 100

    def test_entangle_requires_both_states(self):
        store = QuantumStateStore()
        store.create(1, 2, 'c', 0)
        assert store.entangle(1, 999) is False

    def test_entangle_returns_false_for_missing_first(self):
        store = QuantumStateStore()
        store.create(2, 2, 'c', 0)
        assert store.entangle(999, 2) is False

    def test_multiple_entanglements(self):
        store = QuantumStateStore()
        for i in range(1, 6):
            store.create(i, 2, 'lab', 0)
        # Pairwise entanglements
        store.entangle(1, 2)
        store.entangle(3, 4)
        assert store.get(1)['entangled_with'] == 2
        assert store.get(3)['entangled_with'] == 4
        assert store.get(5)['entangled_with'] is None


class TestLazyMeasurement:
    """Verify states persist until explicitly measured."""

    def test_state_starts_unmeasured(self):
        store = QuantumStateStore()
        store.create(42, 4, 'c', 0)
        assert store.get(42)['measured'] is False

    def test_measure_collapses_state(self):
        store = QuantumStateStore()
        store.create(42, 4, 'c', 0)
        assert store.measure(42) is True
        assert store.get(42)['measured'] is True

    def test_measure_twice_idempotent(self):
        store = QuantumStateStore()
        store.create(42, 4, 'c', 0)
        store.measure(42)
        store.measure(42)
        assert store.get(42)['measured'] is True

    def test_measured_state_still_readable(self):
        """Lazy measurement: state persists even after measurement."""
        store = QuantumStateStore()
        store.create(7, 8, 'addr', 100)
        store.measure(7)
        state = store.get(7)
        assert state is not None
        assert state['n_qubits'] == 8
        assert state['measured'] is True

    def test_entangled_state_measurement_independent(self):
        """Measuring one entangled state doesn't collapse its partner."""
        store = QuantumStateStore()
        store.create(1, 4, 'c', 0)
        store.create(2, 4, 'c', 0)
        store.entangle(1, 2)
        store.measure(1)
        assert store.get(1)['measured'] is True
        assert store.get(2)['measured'] is False


class TestEntanglementSQLSchema:
    """Verify the SQL schema was updated for entanglement_pairs table."""

    def test_sql_has_entanglement_pairs_table(self):
        import os
        sql_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sql')
        sql_path = os.path.join(sql_dir, '03_smart_contracts_qvm.sql')
        with open(sql_path) as f:
            content = f.read()
        assert 'entanglement_pairs' in content

    def test_sql_has_quantum_states_table(self):
        import os
        sql_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sql')
        sql_path = os.path.join(sql_dir, '03_smart_contracts_qvm.sql')
        with open(sql_path) as f:
            content = f.read()
        assert 'quantum_states' in content
