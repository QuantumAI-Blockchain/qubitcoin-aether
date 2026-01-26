"""Unit tests for database operations"""
import pytest
from decimal import Decimal
from qubitcoin.database.models import UTXO, Transaction, Block


def test_utxo_creation():
    """Test UTXO model"""
    utxo = UTXO(
        txid="test123",
        vout=0,
        amount=Decimal("50.0"),
        address="addr123",
        proof={}
    )
    
    assert utxo.txid == "test123"
    assert utxo.amount == Decimal("50.0")
    assert not utxo.spent


def test_transaction_txid():
    """Test transaction ID calculation"""
    tx = Transaction(
        txid="",
        inputs=[],
        outputs=[{"address": "addr1", "amount": Decimal("10.0")}],
        fee=Decimal("0.01"),
        signature="sig",
        public_key="pk",
        timestamp=12345.0
    )
    
    txid = tx.calculate_txid()
    assert len(txid) == 64  # SHA256 hex
