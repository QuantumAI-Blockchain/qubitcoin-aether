"""
Batch 41 tests:
  - SPVVerifier (Merkle proof verification)
  - LightNodeSync (header sync protocol)
  - LightNode (combined SPV + sync)
  - OrchestrationStakingPool (QBC staking for phase influence)
"""
import time
import hashlib
import unittest
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from qubitcoin.network.light_node import (
    BlockHeader, MerkleProof, SPVVerifier, LightNodeSync, LightNode,
    SPV_CONFIRMATION_DEPTH, HEADERS_PER_BATCH, MAX_HEADER_STORE,
)
from qubitcoin.aether.pineal import (
    OrchestrationStakingPool, CircadianPhase,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def sha3(data: str) -> str:
    return hashlib.sha3_256(data.encode()).hexdigest()


def make_header(height: int, prev_hash: str = "", merkle_root: str = "") -> BlockHeader:
    bh = sha3(f"block:{height}")
    return BlockHeader(
        height=height,
        block_hash=bh,
        prev_hash=prev_hash or sha3(f"block:{height - 1}") if height > 0 else "0" * 64,
        merkle_root=merkle_root or sha3(f"merkle:{height}"),
        timestamp=time.time(),
        difficulty=0.5,
    )


def make_valid_proof(tx_hash: str, sibling: str, merkle_root: str,
                     block_height: int, index: int = 0) -> MerkleProof:
    """Create a valid single-level Merkle proof."""
    return MerkleProof(
        tx_hash=tx_hash,
        block_height=block_height,
        proof_hashes=[sibling],
        proof_indices=[index],
        merkle_root=merkle_root,
    )


def build_merkle_root(tx_a: str, tx_b: str) -> str:
    """Compute Merkle root from two leaves: H(a || b)."""
    return sha3(tx_a + tx_b)


# ===========================================================================
# SPVVerifier tests
# ===========================================================================

class TestSPVVerifier(unittest.TestCase):
    """Test Merkle proof verification."""

    def setUp(self):
        self.spv = SPVVerifier()

    def test_single_tx_block(self):
        """Single-tx block: tx_hash equals merkle_root."""
        root = sha3("single_tx")
        proof = MerkleProof(
            tx_hash=root, block_height=1,
            proof_hashes=[], proof_indices=[], merkle_root=root,
        )
        assert self.spv.verify_merkle_proof(proof)

    def test_two_tx_block_left(self):
        """Two-tx block: verify left leaf."""
        tx_a = sha3("tx_a")
        tx_b = sha3("tx_b")
        root = build_merkle_root(tx_a, tx_b)
        proof = MerkleProof(
            tx_hash=tx_a, block_height=1,
            proof_hashes=[tx_b], proof_indices=[0], merkle_root=root,
        )
        assert self.spv.verify_merkle_proof(proof)

    def test_two_tx_block_right(self):
        """Two-tx block: verify right leaf."""
        tx_a = sha3("tx_a")
        tx_b = sha3("tx_b")
        root = build_merkle_root(tx_a, tx_b)
        proof = MerkleProof(
            tx_hash=tx_b, block_height=1,
            proof_hashes=[tx_a], proof_indices=[1], merkle_root=root,
        )
        assert self.spv.verify_merkle_proof(proof)

    def test_invalid_proof_wrong_root(self):
        """Proof against wrong merkle root should fail."""
        proof = MerkleProof(
            tx_hash=sha3("tx"), block_height=1,
            proof_hashes=[sha3("sibling")], proof_indices=[0],
            merkle_root="wrong_root",
        )
        assert not self.spv.verify_merkle_proof(proof)

    def test_mismatched_lengths(self):
        """Proof with mismatched hash/index counts should fail."""
        proof = MerkleProof(
            tx_hash=sha3("tx"), block_height=1,
            proof_hashes=[sha3("a"), sha3("b")], proof_indices=[0],
            merkle_root=sha3("root"),
        )
        assert not self.spv.verify_merkle_proof(proof)

    def test_stats(self):
        root = sha3("tx")
        proof = MerkleProof(
            tx_hash=root, block_height=1,
            proof_hashes=[], proof_indices=[], merkle_root=root,
        )
        self.spv.verify_merkle_proof(proof)
        stats = self.spv.get_stats()
        assert stats["total_verifications"] == 1
        assert stats["failures"] == 0

    def test_verify_tx_in_chain(self):
        """Full SPV verification with header store."""
        tx_a = sha3("tx_a")
        tx_b = sha3("tx_b")
        root = build_merkle_root(tx_a, tx_b)

        header = make_header(10, merkle_root=root)
        headers = {10: header}

        proof = MerkleProof(
            tx_hash=tx_a, block_height=10,
            proof_hashes=[tx_b], proof_indices=[0], merkle_root=root,
        )

        # Tip is at 20, so 10 confirmations (> 6 required)
        result = self.spv.verify_tx_in_chain(proof, headers, chain_tip=20)
        assert result["verified"]
        assert result["confirmed"]
        assert result["confirmations"] == 10

    def test_verify_insufficient_confirmations(self):
        """Transaction with too few confirmations."""
        root = sha3("tx")
        header = make_header(10, merkle_root=root)
        headers = {10: header}

        proof = MerkleProof(
            tx_hash=root, block_height=10,
            proof_hashes=[], proof_indices=[], merkle_root=root,
        )
        result = self.spv.verify_tx_in_chain(proof, headers, chain_tip=12)
        assert result["verified"]
        assert not result["confirmed"]
        assert result["confirmations"] == 2

    def test_verify_missing_header(self):
        result = self.spv.verify_tx_in_chain(
            MerkleProof("tx", 999, [], [], "root"),
            headers={},
            chain_tip=1000,
        )
        assert not result["verified"]
        assert "not found" in result["reason"]


# ===========================================================================
# LightNodeSync tests
# ===========================================================================

class TestLightNodeSync(unittest.TestCase):
    """Test header sync protocol."""

    def setUp(self):
        self.sync = LightNodeSync()

    def test_initial_state(self):
        assert self.sync.tip_height == -1
        assert not self.sync.is_synced
        assert self.sync.header_count == 0

    def test_process_single_header(self):
        h = make_header(0)
        result = self.sync.process_header_batch([h])
        assert result["accepted"] == 1
        assert result["rejected"] == 0
        assert self.sync.tip_height == 0
        assert self.sync.header_count == 1

    def test_process_chain_of_headers(self):
        headers = []
        for i in range(10):
            h = make_header(i)
            if i > 0:
                h.prev_hash = headers[i - 1].block_hash
            headers.append(h)

        result = self.sync.process_header_batch(headers)
        assert result["accepted"] == 10
        assert self.sync.tip_height == 9

    def test_reject_broken_chain(self):
        """Header with wrong prev_hash should be rejected."""
        h0 = make_header(0)
        self.sync.process_header_batch([h0])

        h1 = make_header(1)
        h1.prev_hash = "wrong_hash"
        result = self.sync.process_header_batch([h1])
        assert result["rejected"] == 1
        assert len(result["errors"]) == 1

    def test_checkpoint_validation(self):
        """Header at checkpoint height must match checkpoint hash."""
        self.sync.add_checkpoint(5, "expected_hash")
        headers = [make_header(i) for i in range(10)]
        # Header at height 5 won't match "expected_hash"
        result = self.sync.process_header_batch(headers)
        # Height 5 should be rejected
        assert result["rejected"] >= 1

    def test_checkpoint_pass(self):
        """Header matching checkpoint should be accepted."""
        h = make_header(5)
        self.sync.add_checkpoint(5, h.block_hash)
        result = self.sync.process_header_batch([h])
        assert result["accepted"] == 1

    def test_invalid_difficulty(self):
        h = make_header(0)
        h.difficulty = -1.0
        result = self.sync.process_header_batch([h])
        assert result["rejected"] == 1

    def test_get_header(self):
        h = make_header(42)
        self.sync.process_header_batch([h])
        stored = self.sync.get_header(42)
        assert stored is not None
        assert stored.height == 42

    def test_get_header_not_found(self):
        assert self.sync.get_header(999) is None

    def test_get_headers_range(self):
        headers = [make_header(i) for i in range(5)]
        self.sync.process_header_batch(headers)
        rng = self.sync.get_headers_range(1, 4)
        assert len(rng) == 3

    def test_mark_sync_complete(self):
        self.sync.process_header_batch([make_header(0)])
        self.sync.mark_sync_complete()
        assert self.sync.is_synced

    def test_get_status(self):
        self.sync.process_header_batch([make_header(0)])
        status = self.sync.get_status()
        assert status["tip_height"] == 0
        assert status["headers_stored"] == 1
        assert not status["synced"]


# ===========================================================================
# LightNode (combined) tests
# ===========================================================================

class TestLightNode(unittest.TestCase):
    """Test combined light node."""

    def setUp(self):
        self.node = LightNode()

    def test_has_spv_and_sync(self):
        assert hasattr(self.node, 'spv')
        assert hasattr(self.node, 'sync')

    def test_verify_transaction_end_to_end(self):
        """Full end-to-end: sync headers → verify tx."""
        tx_a = sha3("my_tx")
        tx_b = sha3("other_tx")
        root = build_merkle_root(tx_a, tx_b)

        # Sync headers
        headers = []
        for i in range(20):
            h = make_header(i)
            if i == 10:
                h.merkle_root = root
            if i > 0:
                h.prev_hash = headers[i - 1].block_hash
            headers.append(h)
        self.node.sync.process_header_batch(headers)

        # Verify transaction at block 10
        proof = MerkleProof(
            tx_hash=tx_a, block_height=10,
            proof_hashes=[tx_b], proof_indices=[0], merkle_root=root,
        )
        result = self.node.verify_transaction(proof)
        assert result["verified"]
        assert result["confirmed"]

    def test_get_status(self):
        status = self.node.get_status()
        assert status["type"] == "light"
        assert "sync" in status
        assert "spv" in status
        assert "chain_id" in status


# ===========================================================================
# OrchestrationStakingPool tests
# ===========================================================================

class TestOrchestrationStakingPool(unittest.TestCase):
    """Test QBC staking pool for orchestration influence."""

    def setUp(self):
        self.pool = OrchestrationStakingPool()

    def test_initial_state(self):
        status = self.pool.get_status()
        assert status["total_staked"] == 0
        assert status["stakers"] == 0

    def test_stake_success(self):
        result = self.pool.stake("qbc1alice", "active_learning", 100.0, block_height=1)
        assert result["success"]
        assert result["amount"] == 100.0
        assert self.pool.get_status()["total_staked"] == 100.0

    def test_stake_below_minimum(self):
        result = self.pool.stake("qbc1alice", "waking", 5.0, block_height=1)
        assert not result["success"]
        assert "Minimum" in result["error"]

    def test_stake_invalid_phase(self):
        result = self.pool.stake("qbc1alice", "nonexistent_phase", 100.0, block_height=1)
        assert not result["success"]
        assert "Invalid phase" in result["error"]

    def test_multiple_stakes_same_phase(self):
        self.pool.stake("qbc1alice", "waking", 50.0, block_height=1)
        self.pool.stake("qbc1alice", "waking", 30.0, block_height=2)
        info = self.pool.get_staker_info("qbc1alice")
        assert info["stakes"]["waking"] == 80.0

    def test_multiple_stakers_different_phases(self):
        self.pool.stake("qbc1alice", "waking", 100.0, block_height=1)
        self.pool.stake("qbc1bob", "sleep", 200.0, block_height=2)
        status = self.pool.get_status()
        assert status["stakers"] == 2
        assert status["total_staked"] == 300.0

    def test_phase_extension_no_stakes(self):
        """No stakes should mean no extension (1.0)."""
        assert self.pool.get_phase_extension("waking") == 1.0

    def test_phase_extension_proportional(self):
        """Phase with all stakes gets max extension."""
        self.pool.stake("qbc1alice", "active_learning", 1000.0, block_height=1)
        ext = self.pool.get_phase_extension("active_learning")
        assert ext == 2.0  # MAX_PHASE_EXTENSION

    def test_phase_extension_partial(self):
        """Phase with partial stake gets proportional extension."""
        self.pool.stake("qbc1alice", "waking", 500.0, block_height=1)
        self.pool.stake("qbc1bob", "sleep", 500.0, block_height=2)
        ext = self.pool.get_phase_extension("waking")
        # 50% of total stake → extension = 1.0 + 0.5 * 1.0 = 1.5
        assert abs(ext - 1.5) < 0.01

    def test_request_unstake(self):
        self.pool.stake("qbc1alice", "waking", 100.0, block_height=1)
        result = self.pool.request_unstake("qbc1alice", "waking", 50.0, block_height=10)
        assert result["success"]
        assert result["release_block"] == 10 + self.pool.UNSTAKE_DELAY_BLOCKS

    def test_request_unstake_insufficient(self):
        self.pool.stake("qbc1alice", "waking", 30.0, block_height=1)
        result = self.pool.request_unstake("qbc1alice", "waking", 50.0, block_height=10)
        assert not result["success"]

    def test_process_unstakes_before_maturity(self):
        self.pool.stake("qbc1alice", "waking", 100.0, block_height=1)
        self.pool.request_unstake("qbc1alice", "waking", 50.0, block_height=10)
        processed = self.pool.process_unstakes(block_height=100)
        assert processed == 0  # Not matured yet
        assert self.pool.get_status()["total_staked"] == 100.0

    def test_process_unstakes_after_maturity(self):
        self.pool.stake("qbc1alice", "waking", 100.0, block_height=1)
        self.pool.request_unstake("qbc1alice", "waking", 50.0, block_height=10)
        release = 10 + self.pool.UNSTAKE_DELAY_BLOCKS
        processed = self.pool.process_unstakes(block_height=release)
        assert processed == 1
        assert self.pool.get_status()["total_staked"] == 50.0

    def test_get_staker_info(self):
        self.pool.stake("qbc1alice", "waking", 100.0, block_height=1)
        self.pool.stake("qbc1alice", "sleep", 50.0, block_height=2)
        info = self.pool.get_staker_info("qbc1alice")
        assert info["total_staked"] == 150.0
        assert "waking" in info["stakes"]
        assert "sleep" in info["stakes"]

    def test_get_staker_info_unknown(self):
        info = self.pool.get_staker_info("qbc1unknown")
        assert info["total_staked"] == 0

    def test_get_status_has_extensions(self):
        self.pool.stake("qbc1alice", "waking", 100.0, block_height=1)
        status = self.pool.get_status()
        assert "phase_extensions" in status
        assert "waking" in status["phase_extensions"]


# ===========================================================================
# BlockHeader tests
# ===========================================================================

class TestBlockHeader(unittest.TestCase):
    """Test BlockHeader dataclass."""

    def test_compute_hash_deterministic(self):
        h = BlockHeader(
            height=1, block_hash="bh1", prev_hash="ph0",
            merkle_root="mr1", timestamp=1000.0, difficulty=0.5,
        )
        hash1 = h.compute_hash()
        hash2 = h.compute_hash()
        assert hash1 == hash2

    def test_to_dict(self):
        h = make_header(5)
        d = h.to_dict()
        assert d["height"] == 5
        assert "block_hash" in d
        assert "merkle_root" in d

    def test_merkle_proof_to_dict(self):
        proof = MerkleProof("tx", 1, ["s1"], [0], "root")
        d = proof.to_dict()
        assert d["tx_hash"] == "tx"
        assert d["block_height"] == 1


if __name__ == '__main__':
    unittest.main()
