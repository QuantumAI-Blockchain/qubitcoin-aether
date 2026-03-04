"""Tests for Deniable RPC handler."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.privacy.deniable_rpc import (
    DeniableRPCHandler, PythonBloomFilter, create_bloom_filter
)


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db in unit tests")
    return db


@pytest.fixture()
def handler(mock_db, monkeypatch):
    from qubitcoin.config import Config
    Config.DENIABLE_RPC_ENABLED = True
    Config.DENIABLE_RPC_MAX_BATCH = 100
    Config.DENIABLE_RPC_BLOOM_MAX_SIZE = 65536
    return DeniableRPCHandler(mock_db)


# ── Bloom Filter Tests ──────────────────────────────────────────────────

class TestPythonBloomFilter:
    def test_insert_and_check(self):
        bf = PythonBloomFilter(1024, 5)
        bf.insert("hello")
        bf.insert("world")
        assert bf.check("hello")
        assert bf.check("world")
        assert not bf.check("missing")

    def test_empty_filter(self):
        bf = PythonBloomFilter(1024, 5)
        assert not bf.check("anything")

    def test_serialization(self):
        bf = PythonBloomFilter(256, 3)
        bf.insert("test1")
        bf.insert("test2")
        data = bf.to_bytes()
        bf2 = PythonBloomFilter.from_bytes(data, 3)
        assert bf2.check("test1")
        assert bf2.check("test2")
        assert not bf2.check("test3")

    def test_no_false_negatives(self):
        bf = PythonBloomFilter(4096, 7)
        items = [f"item_{i}" for i in range(100)]
        for item in items:
            bf.insert(item)
        for item in items:
            assert bf.check(item), f"False negative for {item}"

    def test_item_count(self):
        bf = PythonBloomFilter(1024, 5)
        assert bf.item_count() == 0
        bf.insert("x")
        assert bf.item_count() == 1

    def test_byte_size(self):
        bf = PythonBloomFilter(2048, 5)
        assert bf.byte_size() == 2048


class TestCreateBloomFilter:
    def test_creates_filter(self):
        bf = create_bloom_filter(512, 5)
        bf.insert("test")
        assert bf.check("test")
        assert not bf.check("missing")


# ── Batch Balance ───────────────────────────────────────────────────────

class TestBatchBalance:
    def test_returns_all_addresses(self, handler):
        addresses = ["addr1", "addr2", "addr3"]
        result = handler.batch_balance(addresses)
        # All addresses get a result (0.0 since DB fails)
        assert len(result) == 3
        for addr in addresses:
            assert addr in result

    def test_max_batch_enforced(self, handler):
        addresses = [f"addr_{i}" for i in range(200)]
        result = handler.batch_balance(addresses)
        assert len(result) == 100  # Capped at max_batch


# ── Bloom UTXOs ─────────────────────────────────────────────────────────

class TestBloomUtxos:
    def test_returns_bytes(self, handler):
        result = handler.bloom_utxos("addr1", bloom_size=256, hash_count=5)
        assert isinstance(result, (bytes, bytearray))
        assert len(result) == 256

    def test_max_size_enforced(self, handler):
        result = handler.bloom_utxos("addr1", bloom_size=999999, hash_count=5)
        assert len(result) <= handler._bloom_max_size


# ── Batch Blocks ────────────────────────────────────────────────────────

class TestBatchBlocks:
    def test_returns_all_heights(self, handler):
        heights = [1, 2, 3, 4, 5]
        result = handler.batch_blocks(heights)
        assert len(result) == 5
        for h in heights:
            assert h in result

    def test_max_batch_enforced(self, handler):
        heights = list(range(200))
        result = handler.batch_blocks(heights)
        assert len(result) == 100


# ── Batch TX ────────────────────────────────────────────────────────────

class TestBatchTx:
    def test_returns_all_txids(self, handler):
        txids = ["tx1", "tx2", "tx3"]
        result = handler.batch_tx(txids)
        assert len(result) == 3
        for txid in txids:
            assert txid in result

    def test_max_batch_enforced(self, handler):
        txids = [f"tx_{i}" for i in range(200)]
        result = handler.batch_tx(txids)
        assert len(result) == 100
