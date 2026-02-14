"""Tests for Bridge Proof Storage & QVCSP (Batch 19.2)."""
import time

import pytest

from qubitcoin.bridge.proof_store import (
    BridgeProof,
    ProofStatus,
    ProofStore,
    ProofType,
    compute_entanglement_id,
    compute_proof_id,
    verify_merkle_proof,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_merkle_leaf_and_root(
    source_chain_id: int = 1,
    source_tx_hash: str = "0xabc",
    sender: str = "alice",
    receiver: str = "bob",
    amount: float = 10.0,
):
    """Build a trivial single-leaf Merkle tree (root == leaf hash)."""
    import hashlib
    leaf_data = f"{source_chain_id}:{source_tx_hash}:{sender}:{receiver}:{amount}"
    leaf_hash = hashlib.sha256(leaf_data.encode()).hexdigest()
    return leaf_hash, leaf_hash  # proof = [], root = leaf


# ---------------------------------------------------------------------------
# compute_proof_id
# ---------------------------------------------------------------------------

class TestComputeProofId:
    def test_deterministic(self):
        a = compute_proof_id(1, "0xabc", "alice", "bob", 10.0)
        b = compute_proof_id(1, "0xabc", "alice", "bob", 10.0)
        assert a == b

    def test_different_inputs_differ(self):
        a = compute_proof_id(1, "0xabc", "alice", "bob", 10.0)
        b = compute_proof_id(2, "0xabc", "alice", "bob", 10.0)
        assert a != b


# ---------------------------------------------------------------------------
# compute_entanglement_id
# ---------------------------------------------------------------------------

class TestComputeEntanglementId:
    def test_deterministic(self):
        a = compute_entanglement_id(1, 3301, "root_a", 100)
        b = compute_entanglement_id(1, 3301, "root_a", 100)
        assert a == b

    def test_different_chains_differ(self):
        a = compute_entanglement_id(1, 3301, "root", 0)
        b = compute_entanglement_id(56, 3301, "root", 0)
        assert a != b


# ---------------------------------------------------------------------------
# verify_merkle_proof
# ---------------------------------------------------------------------------

class TestVerifyMerkleProof:
    def test_single_leaf(self):
        leaf, root = _make_merkle_leaf_and_root()
        assert verify_merkle_proof(leaf, [], root) is True

    def test_invalid_root(self):
        leaf, _ = _make_merkle_leaf_and_root()
        assert verify_merkle_proof(leaf, [], "bad_root") is False

    def test_two_level_tree(self):
        import hashlib
        leaf = "aaa"
        sibling = "bbb"
        # canonical order: smaller first
        combined = leaf + sibling  # "aaa" < "bbb"
        root = hashlib.sha256(combined.encode()).hexdigest()
        assert verify_merkle_proof(leaf, [sibling], root) is True

    def test_two_level_reversed(self):
        import hashlib
        leaf = "zzz"
        sibling = "aaa"
        combined = sibling + leaf  # "aaa" < "zzz"
        root = hashlib.sha256(combined.encode()).hexdigest()
        assert verify_merkle_proof(leaf, [sibling], root) is True


# ---------------------------------------------------------------------------
# BridgeProof dataclass
# ---------------------------------------------------------------------------

class TestBridgeProof:
    def test_to_dict(self):
        p = BridgeProof(
            proof_id="abc",
            source_chain_id=1,
            dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0x123",
            source_block_height=100,
            sender="alice",
            receiver="bob",
            amount=5.0,
            merkle_proof=[],
            state_root="root",
        )
        d = p.to_dict()
        assert d["proof_id"] == "abc"
        assert d["proof_type"] == "deposit"
        assert d["status"] == "pending"


# ---------------------------------------------------------------------------
# ProofStore — submit
# ---------------------------------------------------------------------------

class TestProofStoreSubmit:
    def test_submit(self):
        store = ProofStore()
        leaf, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert proof is not None
        assert proof.status == ProofStatus.PENDING
        assert proof.entanglement_id is not None

    def test_replay_rejected(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        dup = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert dup is None

    def test_duplicate_source_tx_rejected(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        # Same source_tx_hash but different amount → still blocked
        dup = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=20.0,
            merkle_proof=[], state_root=root,
        )
        assert dup is None


# ---------------------------------------------------------------------------
# ProofStore — verify
# ---------------------------------------------------------------------------

class TestProofStoreVerify:
    def test_verify_valid(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert store.verify_proof(proof.proof_id) is True
        assert proof.status == ProofStatus.VERIFIED
        assert proof.verified_at is not None

    def test_verify_bad_merkle(self):
        store = ProofStore()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root="wrong_root",
        )
        assert store.verify_proof(proof.proof_id) is False
        assert proof.status == ProofStatus.REJECTED

    def test_verify_nonexistent(self):
        store = ProofStore()
        assert store.verify_proof("no_such_id") is False

    def test_verify_already_verified(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        store.verify_proof(proof.proof_id)
        # Second verify should fail (already verified)
        assert store.verify_proof(proof.proof_id) is False

    def test_verify_expired(self):
        store = ProofStore(proof_expiry_seconds=0.0)  # instant expiry
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        time.sleep(0.01)
        assert store.verify_proof(proof.proof_id) is False
        assert proof.status == ProofStatus.EXPIRED


# ---------------------------------------------------------------------------
# ProofStore — execute
# ---------------------------------------------------------------------------

class TestProofStoreExecute:
    def test_mark_executed(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        store.verify_proof(proof.proof_id)
        assert store.mark_executed(proof.proof_id) is True
        assert proof.status == ProofStatus.EXECUTED

    def test_cannot_execute_pending(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert store.mark_executed(proof.proof_id) is False

    def test_cannot_execute_nonexistent(self):
        store = ProofStore()
        assert store.mark_executed("missing") is False


# ---------------------------------------------------------------------------
# ProofStore — QVCSP
# ---------------------------------------------------------------------------

class TestQVCSP:
    def test_qvcsp_success(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert store.verify_qvcsp(
            proof.proof_id, proof.entanglement_id, 1
        ) is True
        assert proof.status == ProofStatus.VERIFIED

    def test_qvcsp_wrong_entanglement(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert store.verify_qvcsp(proof.proof_id, 999, 1) is False

    def test_qvcsp_wrong_chain(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert store.verify_qvcsp(
            proof.proof_id, proof.entanglement_id, 56
        ) is False

    def test_qvcsp_nonexistent(self):
        store = ProofStore()
        assert store.verify_qvcsp("missing", 0, 1) is False

    def test_qvcsp_on_already_executed(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        store.verify_proof(proof.proof_id)
        store.mark_executed(proof.proof_id)
        assert store.verify_qvcsp(
            proof.proof_id, proof.entanglement_id, 1
        ) is False


# ---------------------------------------------------------------------------
# ProofStore — queries
# ---------------------------------------------------------------------------

class TestProofStoreQueries:
    def test_get_proof(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert store.get_proof(proof.proof_id) is proof

    def test_get_proof_by_source_tx(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        proof = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        found = store.get_proof_by_source_tx("0xabc")
        assert found is proof

    def test_get_proof_by_source_tx_missing(self):
        store = ProofStore()
        assert store.get_proof_by_source_tx("missing") is None

    def test_list_proofs_filter_status(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        p = store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        store.verify_proof(p.proof_id)
        assert len(store.list_proofs(status=ProofStatus.VERIFIED)) == 1
        assert len(store.list_proofs(status=ProofStatus.PENDING)) == 0

    def test_list_proofs_filter_chain(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        assert len(store.list_proofs(source_chain_id=1)) == 1
        assert len(store.list_proofs(source_chain_id=56)) == 0

    def test_stats(self):
        store = ProofStore()
        _, root = _make_merkle_leaf_and_root()
        store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        stats = store.get_stats()
        assert stats["total_proofs"] == 1
        assert stats["total_amount"] == 10.0
        assert stats["by_status"]["pending"] == 1

    def test_expire_stale(self):
        store = ProofStore(proof_expiry_seconds=0.0)
        _, root = _make_merkle_leaf_and_root()
        store.submit_proof(
            source_chain_id=1, dest_chain_id=3301,
            proof_type=ProofType.DEPOSIT,
            source_tx_hash="0xabc",
            source_block_height=500,
            sender="alice", receiver="bob", amount=10.0,
            merkle_proof=[], state_root=root,
        )
        time.sleep(0.01)
        count = store.expire_stale()
        assert count == 1
