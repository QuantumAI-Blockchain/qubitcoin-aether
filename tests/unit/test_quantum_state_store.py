"""Tests for QuantumStateStore (density matrix persistence, Batch 12.3)."""
import pytest

from qubitcoin.qvm.state import QuantumStateStore


class TestQuantumStateStoreCRUD:
    """Test create / get / measure / delete lifecycle."""

    def test_create_and_get(self):
        store = QuantumStateStore()
        record = store.create(
            state_id=42, n_qubits=4,
            contract_address='aabb' * 10, block_height=100,
        )
        assert record['state_id'] == 42
        assert record['n_qubits'] == 4
        assert record['measured'] is False

        fetched = store.get(42)
        assert fetched is not None
        assert fetched['n_qubits'] == 4

    def test_get_missing_returns_none(self):
        store = QuantumStateStore()
        assert store.get(999) is None

    def test_measure_marks_collapsed(self):
        store = QuantumStateStore()
        store.create(1, 2, 'addr', 10)
        assert store.measure(1) is True
        assert store.get(1)['measured'] is True

    def test_measure_missing_returns_false(self):
        store = QuantumStateStore()
        assert store.measure(999) is False

    def test_delete_removes_state(self):
        store = QuantumStateStore()
        store.create(7, 3, 'addr', 20)
        assert store.delete(7) is True
        assert store.get(7) is None

    def test_delete_missing_returns_false(self):
        store = QuantumStateStore()
        assert store.delete(999) is False


class TestQuantumStateEntanglement:
    """Test entanglement tracking between states."""

    def test_entangle_two_states(self):
        store = QuantumStateStore()
        store.create(1, 4, 'c1', 10)
        store.create(2, 4, 'c2', 10)
        assert store.entangle(1, 2) is True
        assert store.get(1)['entangled_with'] == 2
        assert store.get(2)['entangled_with'] == 1

    def test_entangle_missing_state_fails(self):
        store = QuantumStateStore()
        store.create(1, 4, 'c1', 10)
        assert store.entangle(1, 999) is False

    def test_re_entangle_overwrites(self):
        store = QuantumStateStore()
        store.create(1, 2, 'c', 5)
        store.create(2, 2, 'c', 5)
        store.create(3, 2, 'c', 5)
        store.entangle(1, 2)
        store.entangle(1, 3)  # overwrite
        assert store.get(1)['entangled_with'] == 3


class TestQuantumStateListStates:
    """Test listing / filtering states."""

    def test_list_all(self):
        store = QuantumStateStore()
        store.create(1, 2, 'a', 0)
        store.create(2, 4, 'b', 0)
        store.create(3, 8, 'a', 0)
        assert len(store.list_states()) == 3

    def test_list_by_contract(self):
        store = QuantumStateStore()
        store.create(1, 2, 'alice', 0)
        store.create(2, 4, 'bob', 0)
        store.create(3, 8, 'alice', 0)
        results = store.list_states(contract_address='alice')
        assert len(results) == 2

    def test_list_empty_store(self):
        store = QuantumStateStore()
        assert store.list_states() == []


class TestQuantumStatePersistence:
    """Verify DB persistence hooks (no-op without real DB)."""

    def test_create_without_db_no_error(self):
        store = QuantumStateStore(db_manager=None)
        record = store.create(1, 4, 'addr', 100)
        assert record['state_id'] == 1

    def test_load_without_db_returns_none(self):
        store = QuantumStateStore(db_manager=None)
        assert store._load(42) is None
