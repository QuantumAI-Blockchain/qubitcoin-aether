"""Tests for quantum state root in block header (Batch 15.2)."""
import hashlib
import pytest

from qubitcoin.qvm.state import QuantumStateStore
from qubitcoin.database.models import Block


class TestQuantumStateRoot:
    """Verify QuantumStateStore.compute_state_root() Merkle root."""

    def test_empty_returns_deterministic(self):
        store = QuantumStateStore()
        root = store.compute_state_root()
        assert root == hashlib.sha256(b'empty_quantum').hexdigest()

    def test_single_state(self):
        store = QuantumStateStore()
        store.create(1, 4, 'alice', 10)
        root = store.compute_state_root()
        assert isinstance(root, str) and len(root) == 64

    def test_multiple_states(self):
        store = QuantumStateStore()
        store.create(1, 4, 'alice', 10)
        store.create(2, 8, 'bob', 20)
        root = store.compute_state_root()
        assert len(root) == 64

    def test_deterministic(self):
        store = QuantumStateStore()
        store.create(1, 4, 'c', 0)
        store.create(2, 4, 'c', 0)
        r1 = store.compute_state_root()
        r2 = store.compute_state_root()
        assert r1 == r2

    def test_different_states_different_root(self):
        s1 = QuantumStateStore()
        s1.create(1, 4, 'c', 0)
        s2 = QuantumStateStore()
        s2.create(99, 16, 'd', 100)
        assert s1.compute_state_root() != s2.compute_state_root()

    def test_measurement_changes_root(self):
        store = QuantumStateStore()
        store.create(1, 4, 'c', 0)
        root_before = store.compute_state_root()
        store.measure(1)
        root_after = store.compute_state_root()
        assert root_before != root_after

    def test_odd_number_of_states(self):
        store = QuantumStateStore()
        for i in range(1, 4):  # 3 states
            store.create(i, 2, 'addr', 0)
        root = store.compute_state_root()
        assert len(root) == 64


class TestBlockQuantumStateRoot:
    """Verify Block dataclass includes quantum_state_root."""

    def test_block_has_field(self):
        b = Block(
            height=0, prev_hash='0'*64,
            proof_data={'energy': 0.5}, transactions=[],
            timestamp=1700000000.0, difficulty=1.0,
        )
        assert hasattr(b, 'quantum_state_root')
        assert b.quantum_state_root == ''

    def test_block_hash_includes_quantum_root(self):
        b1 = Block(
            height=0, prev_hash='0'*64,
            proof_data={'energy': 0.5}, transactions=[],
            timestamp=1700000000.0, difficulty=1.0,
            quantum_state_root='',
        )
        b2 = Block(
            height=0, prev_hash='0'*64,
            proof_data={'energy': 0.5}, transactions=[],
            timestamp=1700000000.0, difficulty=1.0,
            quantum_state_root='abc123',
        )
        assert b1.calculate_hash() != b2.calculate_hash()

    def test_block_to_dict_includes_quantum_root(self):
        b = Block(
            height=0, prev_hash='0'*64,
            proof_data={}, transactions=[],
            timestamp=1700000000.0, difficulty=1.0,
            quantum_state_root='deadbeef',
        )
        d = b.to_dict()
        assert d['quantum_state_root'] == 'deadbeef'

    def test_block_from_dict_round_trip(self):
        b = Block(
            height=0, prev_hash='0'*64,
            proof_data={}, transactions=[],
            timestamp=1700000000.0, difficulty=1.0,
            quantum_state_root='abc',
        )
        d = b.to_dict()
        b2 = Block.from_dict(d)
        assert b2.quantum_state_root == 'abc'
