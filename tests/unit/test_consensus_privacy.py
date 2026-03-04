"""Tests for privacy transaction verification in the consensus engine."""
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


def _make_private_tx(
    *,
    txid: str = "abc123",
    fee: Decimal = Decimal("0.01"),
    inputs: list = None,
    outputs: list = None,
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
        fee=fee,
        signature="aa" * 1312,
        public_key="bb" * 656,
        timestamp=time.time(),
        is_private=True,
    )
    return tx


class TestPrivateTxRouting:
    """Verify that is_private routes to the privacy validation path."""

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=True)
    def test_private_tx_routes_to_privacy_validator(self, mock_verify):
        engine, db = _make_consensus()
        engine._is_key_image_spent = MagicMock(return_value=False)
        tx = _make_private_tx()
        result = engine.validate_transaction(tx, db, current_height=100)
        assert result is True

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=False)
    def test_private_tx_invalid_signature(self, mock_verify):
        engine, db = _make_consensus()
        tx = _make_private_tx()
        result = engine.validate_transaction(tx, db, current_height=100)
        assert result is False


class TestKeyImageValidation:
    """Test key image double-spend prevention."""

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=True)
    def test_missing_key_image_fails(self, mock_verify):
        engine, db = _make_consensus()
        tx = _make_private_tx(inputs=[{"txid": "prev_tx", "vout": 0}])
        result = engine.validate_transaction(tx, db, current_height=100)
        assert result is False

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=True)
    def test_duplicate_key_image_in_same_tx_fails(self, mock_verify):
        engine, db = _make_consensus()
        ki = "ki_" + "b" * 60
        tx = _make_private_tx(
            inputs=[
                {"txid": "tx1", "vout": 0, "key_image": ki},
                {"txid": "tx2", "vout": 0, "key_image": ki},
            ]
        )
        result = engine.validate_transaction(tx, db, current_height=100)
        assert result is False

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=True)
    def test_already_spent_key_image_fails(self, mock_verify):
        engine, db = _make_consensus()
        engine._is_key_image_spent = MagicMock(return_value=True)
        tx = _make_private_tx()
        result = engine.validate_transaction(tx, db, current_height=100)
        assert result is False

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=True)
    def test_unique_key_images_pass(self, mock_verify):
        engine, db = _make_consensus()
        engine._is_key_image_spent = MagicMock(return_value=False)
        tx = _make_private_tx(
            inputs=[
                {"txid": "tx1", "vout": 0, "key_image": "ki_" + "a" * 60},
                {"txid": "tx2", "vout": 0, "key_image": "ki_" + "b" * 60},
            ]
        )
        result = engine.validate_transaction(tx, db, current_height=100)
        assert result is True


class TestPrivateTxFee:
    """Test fee validation for private transactions."""

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=True)
    def test_negative_fee_rejected(self, mock_verify):
        engine, db = _make_consensus()
        engine._is_key_image_spent = MagicMock(return_value=False)
        tx = _make_private_tx(fee=Decimal("-1"))
        result = engine.validate_transaction(tx, db, current_height=100)
        assert result is False

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=True)
    def test_zero_fee_allowed(self, mock_verify):
        engine, db = _make_consensus()
        engine._is_key_image_spent = MagicMock(return_value=False)
        tx = _make_private_tx(fee=Decimal("0"))
        result = engine.validate_transaction(tx, db, current_height=100)
        assert result is True


class TestKeyImageDBLookup:
    """Test key image database lookup."""

    def test_key_image_not_in_db(self):
        engine, db = _make_consensus()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.fetchone.return_value = None
        db.get_session.return_value = mock_session
        assert engine._is_key_image_spent("ki_test", db) is False

    def test_key_image_in_db(self):
        engine, db = _make_consensus()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.fetchone.return_value = (1,)
        db.get_session.return_value = mock_session
        assert engine._is_key_image_spent("ki_test", db) is True

    def test_key_image_db_error_rejects_tx(self):
        """Unknown DB errors should reject tx for safety (return True)."""
        engine, db = _make_consensus()
        db.get_session.side_effect = Exception("DB down")
        assert engine._is_key_image_spent("ki_test", db) is True

    def test_key_image_table_missing_allows_tx(self):
        """If key_images table doesn't exist, allow tx (return False)."""
        engine, db = _make_consensus()
        db.get_session.side_effect = Exception(
            'relation "key_images" does not exist'
        )
        assert engine._is_key_image_spent("ki_test", db) is False


class TestPublicTxUnchanged:
    """Verify public transactions are not affected by privacy changes."""

    @patch("qubitcoin.consensus.engine.DilithiumSigner.verify", return_value=True)
    def test_public_tx_uses_standard_path(self, mock_verify):
        engine, db = _make_consensus()
        from qubitcoin.database.models import Transaction, UTXO

        utxo = UTXO(
            txid="prev_tx", vout=0, amount=Decimal("100"),
            address="addr", proof={}, block_height=0,
        )
        db.get_utxo.return_value = utxo
        db.get_current_height.return_value = 200

        tx = Transaction(
            txid="test_tx",
            inputs=[{"txid": "prev_tx", "vout": 0}],
            outputs=[{"address": "dest", "amount": "99"}],
            fee=Decimal("1"),
            signature="aa" * 1312,
            public_key="bb" * 656,
            timestamp=time.time(),
            is_private=False,
        )

        result = engine.validate_transaction(tx, db, current_height=200)
        assert result is True
        db.get_utxo.assert_called_once()
