"""Tests for deniable RPC endpoint-level logic."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.privacy.deniable_rpc import DeniableRPCHandler


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db")
    return db


@pytest.fixture()
def handler(mock_db):
    from qubitcoin.config import Config
    Config.DENIABLE_RPC_ENABLED = True
    Config.DENIABLE_RPC_MAX_BATCH = 50
    Config.DENIABLE_RPC_BLOOM_MAX_SIZE = 65536
    return DeniableRPCHandler(mock_db)


class TestBatchBalanceEndpoint:
    def test_returns_all(self, handler):
        result = handler.batch_balance(["a", "b", "c"])
        assert len(result) == 3

    def test_empty_input(self, handler):
        result = handler.batch_balance([])
        assert len(result) == 0


class TestBloomUtxosEndpoint:
    def test_returns_bytes(self, handler):
        data = handler.bloom_utxos("addr1", 512, 5)
        assert isinstance(data, (bytes, bytearray))
        assert len(data) == 512


class TestBatchBlocksEndpoint:
    def test_returns_all(self, handler):
        result = handler.batch_blocks([1, 2, 3])
        assert len(result) == 3


class TestBatchTxEndpoint:
    def test_returns_all(self, handler):
        result = handler.batch_tx(["tx1", "tx2"])
        assert len(result) == 2

    def test_batch_limit(self, handler):
        result = handler.batch_tx([f"tx{i}" for i in range(100)])
        assert len(result) == 50
