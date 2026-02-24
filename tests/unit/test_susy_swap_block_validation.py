"""Unit tests for Susy Swap (confidential tx) validation in block context.

Tests the _validate_block_susy_swaps method wired into ConsensusEngine.validate_block.
"""
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


def _make_consensus():
    """Create a ConsensusEngine with mocked dependencies."""
    from qubitcoin.consensus.engine import ConsensusEngine

    quantum_engine = MagicMock()
    db_manager = MagicMock()
    db_manager.get_current_height.return_value = 100
    p2p = MagicMock()

    engine = ConsensusEngine(quantum_engine, db_manager, p2p)
    return engine, db_manager


def _make_block(transactions=None, height: int = 10):
    """Create a minimal Block mock."""
    from qubitcoin.database.models import Block
    block = Block(
        height=height,
        prev_hash='0' * 64,
        timestamp=time.time(),
        difficulty=1.0,
        transactions=transactions or [],
        proof_data={},
    )
    return block


def _make_private_tx(
    txid: str = "priv_tx_01",
    inputs=None,
    outputs=None,
    is_private: bool = True,
):
    """Create a private Transaction mock."""
    from qubitcoin.database.models import Transaction

    if inputs is None:
        inputs = [{"txid": "prev_tx", "vout": 0, "key_image": "ki_" + "a" * 60}]
    if outputs is None:
        outputs = [{"address": "stealth_addr", "amount": "99.99"}]

    tx = Transaction(
        txid=txid,
        inputs=inputs,
        outputs=outputs,
        fee=Decimal("0.01"),
        signature="aa" * 1312,
        public_key="bb" * 656,
        timestamp=time.time(),
        is_private=is_private,
    )
    return tx


class TestBlockLevelKeyImageUniqueness:
    """Test that duplicate key images across different transactions in the same
    block are rejected."""

    def test_no_private_txs_passes(self):
        """Block with only public transactions passes susy validation."""
        engine, db = _make_consensus()
        # Public tx (not private, no confidential markers)
        from qubitcoin.database.models import Transaction
        tx = Transaction(
            txid="pub_tx",
            inputs=[{"txid": "prev", "vout": 0}],
            outputs=[{"address": "dest", "amount": "10"}],
            fee=Decimal("0.01"),
            signature="aa" * 1312,
            public_key="bb" * 656,
            timestamp=time.time(),
            is_private=False,
        )
        block = _make_block(transactions=[tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is True

    def test_unique_key_images_across_txs_passes(self):
        """Two private txs with different key images should pass."""
        engine, db = _make_consensus()
        tx1 = _make_private_tx(
            txid="tx1",
            inputs=[{"txid": "prev1", "vout": 0, "key_image": "ki_" + "a" * 60}],
        )
        tx2 = _make_private_tx(
            txid="tx2",
            inputs=[{"txid": "prev2", "vout": 0, "key_image": "ki_" + "b" * 60}],
        )
        block = _make_block(transactions=[tx1, tx2])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is True

    def test_duplicate_key_image_across_txs_rejected(self):
        """Two private txs reusing the same key image in one block = rejected."""
        engine, db = _make_consensus()
        shared_ki = "ki_" + "d" * 60
        tx1 = _make_private_tx(
            txid="tx1",
            inputs=[{"txid": "prev1", "vout": 0, "key_image": shared_ki}],
        )
        tx2 = _make_private_tx(
            txid="tx2",
            inputs=[{"txid": "prev2", "vout": 0, "key_image": shared_ki}],
        )
        block = _make_block(transactions=[tx1, tx2])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is False
        assert "Duplicate key image" in reason

    def test_coinbase_tx_skipped(self):
        """Coinbase transactions (no inputs) are skipped."""
        engine, db = _make_consensus()
        from qubitcoin.database.models import Transaction
        coinbase = Transaction(
            txid="coinbase",
            inputs=[],
            outputs=[{"address": "miner", "amount": "15.27"}],
            fee=Decimal("0"),
            signature="",
            public_key="",
            timestamp=time.time(),
        )
        block = _make_block(transactions=[coinbase])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is True


class TestCommitmentConsistency:
    """Test commitment format validation at block level."""

    def test_valid_commitment_hex_passes(self):
        """A well-formed 33-byte compressed point passes."""
        engine, db = _make_consensus()
        # 02 prefix + 32 bytes x-coord = 33 bytes = 66 hex chars
        valid_commitment = "02" + "ab" * 32
        tx = _make_private_tx(
            outputs=[{"address": "stealth", "amount": "10", "commitment": valid_commitment}],
        )
        block = _make_block(transactions=[tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is True

    def test_invalid_commitment_length_rejected(self):
        """Commitment with wrong byte length is rejected."""
        engine, db = _make_consensus()
        # Only 10 bytes instead of 33
        bad_commitment = "02" + "ab" * 9  # 20 hex chars = 10 bytes
        tx = _make_private_tx(
            outputs=[{"address": "stealth", "amount": "10", "commitment": bad_commitment}],
        )
        block = _make_block(transactions=[tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is False
        assert "Invalid commitment size" in reason

    def test_invalid_commitment_prefix_rejected(self):
        """Commitment with bad prefix byte (not 02 or 03) is rejected."""
        engine, db = _make_consensus()
        # 04 prefix is not a valid compressed point prefix
        bad_commitment = "04" + "ab" * 32
        tx = _make_private_tx(
            outputs=[{"address": "stealth", "amount": "10", "commitment": bad_commitment}],
        )
        block = _make_block(transactions=[tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is False
        assert "Invalid commitment prefix" in reason

    def test_malformed_hex_commitment_rejected(self):
        """Non-hex commitment string is rejected."""
        engine, db = _make_consensus()
        tx = _make_private_tx(
            outputs=[{"address": "stealth", "amount": "10", "commitment": "not_valid_hex!!"}],
        )
        block = _make_block(transactions=[tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is False
        assert "Malformed commitment" in reason


class TestRangeProofBlockValidation:
    """Test range proof verification within block validation."""

    def test_valid_range_proof_passes(self):
        """Output with a valid range proof passes block validation."""
        engine, db = _make_consensus()
        # Generate a real range proof using the privacy module
        from qubitcoin.privacy.commitments import PedersenCommitment
        from qubitcoin.privacy.range_proofs import RangeProofGenerator

        value = 1000
        blinding = PedersenCommitment.generate_blinding()
        commitment = PedersenCommitment.commit(value, blinding)
        proof = RangeProofGenerator.generate(value, blinding, commitment)

        tx = _make_private_tx(
            outputs=[{
                "address": "stealth",
                "amount": "0",
                "range_proof": {
                    "commitment": proof.commitment,
                    "A": proof.A,
                    "S": proof.S,
                    "T1": proof.T1,
                    "T2": proof.T2,
                    "tau_x": proof.tau_x,
                    "mu": proof.mu,
                    "t_hat": proof.t_hat,
                    "l_vec": proof.l_vec,
                    "r_vec": proof.r_vec,
                },
            }],
        )
        block = _make_block(transactions=[tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is True

    def test_invalid_range_proof_rejected(self):
        """Output with a tampered range proof is rejected."""
        engine, db = _make_consensus()
        tx = _make_private_tx(
            outputs=[{
                "address": "stealth",
                "amount": "0",
                "range_proof": {
                    "commitment": b'\x02' + b'\xab' * 32,
                    "A": b'\x02' + b'\xcd' * 32,
                    "S": b'\x02' + b'\xef' * 32,
                    "T1": b'\x02' + b'\x11' * 32,
                    "T2": b'\x02' + b'\x22' * 32,
                    "tau_x": 12345,
                    "mu": 67890,
                    "t_hat": 99999,
                    "l_vec": [1, 2, 3],
                    "r_vec": [4, 5, 6],  # Inner product won't match t_hat
                },
            }],
        )
        block = _make_block(transactions=[tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is False
        assert "Range proof" in reason


class TestGracefulDegradation:
    """Test that privacy module failures don't crash block validation."""

    def test_output_without_range_proof_passes(self):
        """Private tx outputs without range_proof field are allowed."""
        engine, db = _make_consensus()
        tx = _make_private_tx(
            outputs=[{"address": "stealth", "amount": "10"}],
        )
        block = _make_block(transactions=[tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is True

    def test_mixed_public_and_private_txs(self):
        """Block with both public and private transactions validates correctly."""
        engine, db = _make_consensus()
        from qubitcoin.database.models import Transaction
        pub_tx = Transaction(
            txid="pub_tx",
            inputs=[{"txid": "prev", "vout": 0}],
            outputs=[{"address": "dest", "amount": "10"}],
            fee=Decimal("0.01"),
            signature="aa" * 1312,
            public_key="bb" * 656,
            timestamp=time.time(),
            is_private=False,
        )
        priv_tx = _make_private_tx(
            txid="priv_tx",
            inputs=[{"txid": "prev2", "vout": 0, "key_image": "ki_" + "f" * 60}],
        )
        block = _make_block(transactions=[pub_tx, priv_tx])
        valid, reason = engine._validate_block_susy_swaps(block, db)
        assert valid is True
