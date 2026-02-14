"""Tests for Proof-of-Thought hash embedding in block headers (Batch 11.1)."""
import hashlib
import json
import time

import pytest

from qubitcoin.database.models import Block, Transaction


FIXED_TS = 1700000000.0


def _coinbase(height: int = 0) -> Transaction:
    return Transaction(
        txid="cb_" + hex(height)[2:],
        inputs=[],
        outputs=[{"address": "miner", "amount": "15.27"}],
        fee=0,
        signature="aa" * 1312,
        public_key="bb" * 656,
        timestamp=FIXED_TS,
    )


def _block(thought_proof: dict | None = None, height: int = 1) -> Block:
    return Block(
        height=height,
        prev_hash="0" * 64,
        proof_data={"energy": 0.5, "params": [1.0]},
        transactions=[_coinbase(height)],
        timestamp=FIXED_TS,
        difficulty=1.0,
        thought_proof=thought_proof,
    )


class TestThoughtProofInHash:
    """Verify that thought_proof contributes to the block hash."""

    def test_hash_changes_with_thought_proof(self):
        """A block with a thought proof must hash differently from one without."""
        b_none = _block(thought_proof=None)
        b_pot = _block(thought_proof={"phi": 1.5, "reasoning_steps": ["a", "b"]})
        # Same block params except thought_proof — hashes must differ
        assert b_none.calculate_hash() != b_pot.calculate_hash()

    def test_hash_changes_with_different_thought_proofs(self):
        """Two different thought proofs must produce different hashes."""
        b1 = _block(thought_proof={"phi": 1.5, "hash": "abc"})
        b2 = _block(thought_proof={"phi": 2.0, "hash": "def"})
        assert b1.calculate_hash() != b2.calculate_hash()

    def test_hash_stable_for_same_thought_proof(self):
        """Same thought proof data must always produce the same hash."""
        tp = {"phi": 3.0, "steps": [1, 2, 3]}
        b1 = _block(thought_proof=tp)
        b2 = _block(thought_proof=tp)
        assert b1.calculate_hash() == b2.calculate_hash()

    def test_none_thought_proof_stable(self):
        """Blocks without a thought proof still hash deterministically."""
        b1 = _block(thought_proof=None)
        b2 = _block(thought_proof=None)
        assert b1.calculate_hash() == b2.calculate_hash()

    def test_thought_proof_hash_derivation(self):
        """Verify the intermediate thought_proof_hash value used inside calculate_hash."""
        tp = {"key": "value"}
        expected = hashlib.sha256(json.dumps(tp, sort_keys=True).encode()).hexdigest()
        # Build the canonical data dict manually to confirm the hash feeds in
        b = _block(thought_proof=tp)
        data = {
            'height': b.height,
            'prev_hash': b.prev_hash,
            'proof': b.proof_data,
            'transactions': [tx.txid for tx in b.transactions],
            'timestamp': b.timestamp,
            'difficulty': b.difficulty,
            'state_root': b.state_root,
            'receipts_root': b.receipts_root,
            'quantum_state_root': b.quantum_state_root,
            'thought_proof_hash': expected,
        }
        manual = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        assert b.calculate_hash() == manual


class TestThoughtProofInDict:
    """Verify thought_proof survives serialization round-trip."""

    def test_to_dict_includes_thought_proof(self):
        tp = {"phi": 2.5}
        b = _block(thought_proof=tp)
        d = b.to_dict()
        assert d['thought_proof'] == tp

    def test_to_dict_none_thought_proof(self):
        b = _block(thought_proof=None)
        d = b.to_dict()
        assert d['thought_proof'] is None

    def test_round_trip(self):
        tp = {"phi": 1.618, "hash": "abc123"}
        b = _block(thought_proof=tp)
        d = b.to_dict()
        b2 = Block.from_dict(d)
        assert b2.thought_proof == tp
        assert b2.calculate_hash() == b.calculate_hash()


class TestBlockHashIncludesPoTRoot:
    """Verify the block_hash stored on the block object includes the PoT."""

    def test_block_hash_set_after_calculate(self):
        tp = {"phi": 3.0, "threshold_crossed": True}
        b = _block(thought_proof=tp)
        b.block_hash = b.calculate_hash()
        # Mutate thought_proof and recalculate — must differ
        b2 = _block(thought_proof={"phi": 0.1})
        b2.block_hash = b2.calculate_hash()
        assert b.block_hash != b2.block_hash
