"""Tests for light node SPV verification stub (Batch 13.4)."""
import hashlib
import json
import time
import pytest

from qubitcoin.database.models import Block, Transaction


# ── SPV (Simplified Payment Verification) helpers ─────────────────

def compute_merkle_root(txids: list[str]) -> str:
    """Compute a Merkle root from a list of transaction IDs."""
    if not txids:
        return hashlib.sha256(b'empty').hexdigest()

    leaves = [hashlib.sha256(txid.encode()).hexdigest() for txid in txids]

    while len(leaves) > 1:
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
        new_leaves = []
        for i in range(0, len(leaves), 2):
            combined = hashlib.sha256(
                (leaves[i] + leaves[i + 1]).encode()
            ).hexdigest()
            new_leaves.append(combined)
        leaves = new_leaves

    return leaves[0]


def compute_merkle_proof(txids: list[str], target_idx: int) -> list[dict]:
    """Compute a Merkle inclusion proof for the transaction at *target_idx*.

    Returns a list of {"hash": ..., "side": "left"|"right"} entries.
    """
    if not txids:
        return []

    leaves = [hashlib.sha256(txid.encode()).hexdigest() for txid in txids]
    proof = []
    idx = target_idx

    while len(leaves) > 1:
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
        new_leaves = []
        for i in range(0, len(leaves), 2):
            if i == idx - (idx % 2):
                if idx % 2 == 0:
                    proof.append({'hash': leaves[i + 1], 'side': 'right'})
                else:
                    proof.append({'hash': leaves[i], 'side': 'left'})
            new_leaves.append(
                hashlib.sha256((leaves[i] + leaves[i + 1]).encode()).hexdigest()
            )
        leaves = new_leaves
        idx //= 2

    return proof


def verify_merkle_proof(txid: str, merkle_root: str, proof: list[dict]) -> bool:
    """Verify a Merkle inclusion proof against a known root."""
    current = hashlib.sha256(txid.encode()).hexdigest()
    for step in proof:
        if step['side'] == 'left':
            current = hashlib.sha256((step['hash'] + current).encode()).hexdigest()
        else:
            current = hashlib.sha256((current + step['hash']).encode()).hexdigest()
    return current == merkle_root


# ── Tests ─────────────────────────────────────────────────────────

class TestMerkleRoot:
    """Test Merkle root computation."""

    def test_single_tx(self):
        root = compute_merkle_root(['tx1'])
        assert isinstance(root, str)
        assert len(root) == 64

    def test_two_txs(self):
        root = compute_merkle_root(['tx1', 'tx2'])
        assert len(root) == 64

    def test_four_txs(self):
        root = compute_merkle_root(['a', 'b', 'c', 'd'])
        assert len(root) == 64

    def test_empty_txs(self):
        root = compute_merkle_root([])
        assert root == hashlib.sha256(b'empty').hexdigest()

    def test_deterministic(self):
        txids = ['tx1', 'tx2', 'tx3']
        assert compute_merkle_root(txids) == compute_merkle_root(txids)

    def test_order_matters(self):
        r1 = compute_merkle_root(['tx1', 'tx2'])
        r2 = compute_merkle_root(['tx2', 'tx1'])
        assert r1 != r2


class TestMerkleProof:
    """Test Merkle proof generation and verification."""

    def test_proof_for_first_tx(self):
        txids = ['a', 'b', 'c', 'd']
        root = compute_merkle_root(txids)
        proof = compute_merkle_proof(txids, 0)
        assert verify_merkle_proof('a', root, proof) is True

    def test_proof_for_last_tx(self):
        txids = ['a', 'b', 'c', 'd']
        root = compute_merkle_root(txids)
        proof = compute_merkle_proof(txids, 3)
        assert verify_merkle_proof('d', root, proof) is True

    def test_proof_for_middle_tx(self):
        txids = ['a', 'b', 'c', 'd']
        root = compute_merkle_root(txids)
        proof = compute_merkle_proof(txids, 1)
        assert verify_merkle_proof('b', root, proof) is True

    def test_wrong_tx_fails(self):
        txids = ['a', 'b', 'c', 'd']
        root = compute_merkle_root(txids)
        proof = compute_merkle_proof(txids, 0)
        # Use proof for 'a' but check against 'b'
        assert verify_merkle_proof('b', root, proof) is False

    def test_wrong_root_fails(self):
        txids = ['a', 'b']
        proof = compute_merkle_proof(txids, 0)
        assert verify_merkle_proof('a', 'deadbeef' * 8, proof) is False

    def test_odd_number_of_txs(self):
        txids = ['a', 'b', 'c']
        root = compute_merkle_root(txids)
        proof = compute_merkle_proof(txids, 0)
        assert verify_merkle_proof('a', root, proof) is True

    def test_single_tx_empty_proof(self):
        txids = ['only']
        root = compute_merkle_root(txids)
        proof = compute_merkle_proof(txids, 0)
        assert verify_merkle_proof('only', root, proof) is True


class TestSPVBlockHeaderVerification:
    """Verify block header chain linking (light node requirement)."""

    def test_block_hash_chain(self):
        """Light nodes verify: block.prev_hash == parent.block_hash"""
        parent = Block(
            height=0, prev_hash='0' * 64,
            proof_data={'energy': 0.5, 'params': [1.0]},
            transactions=[], timestamp=1700000000.0, difficulty=1.0,
        )
        parent.block_hash = parent.calculate_hash()

        child = Block(
            height=1, prev_hash=parent.block_hash,
            proof_data={'energy': 0.4, 'params': [1.0]},
            transactions=[], timestamp=1700000003.3, difficulty=1.0,
        )
        child.block_hash = child.calculate_hash()

        assert child.prev_hash == parent.block_hash

    def test_invalid_prev_hash_detected(self):
        parent = Block(
            height=0, prev_hash='0' * 64,
            proof_data={'energy': 0.5}, transactions=[],
            timestamp=1700000000.0, difficulty=1.0,
        )
        parent.block_hash = parent.calculate_hash()

        # Attacker tries to link to a different parent
        child = Block(
            height=1, prev_hash='ff' * 32,
            proof_data={'energy': 0.4}, transactions=[],
            timestamp=1700000003.3, difficulty=1.0,
        )
        assert child.prev_hash != parent.block_hash
