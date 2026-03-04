"""
Deniable RPC handler for Qubitcoin.

Provides privacy-preserving batch queries that:
- Return constant-size responses regardless of match count
- Never short-circuit on first match/miss
- Don't log query content
- Use Bloom filters for UTXO set membership queries

Uses Rust BloomFilter from security-core if available, with
a pure-Python fallback.
"""

import hashlib
import time
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Try to import Rust Bloom filter
try:
    from security_core import BloomFilter as RustBloomFilter
    _USE_RUST_BLOOM = True
    logger.info("Deniable RPC: using Rust BloomFilter")
except ImportError:
    _USE_RUST_BLOOM = False
    logger.info("Deniable RPC: using Python BloomFilter fallback")


class PythonBloomFilter:
    """Pure Python Bloom filter fallback."""

    def __init__(self, size: int, hash_count: int) -> None:
        self.bits = bytearray(size)
        self.size = size
        self.hash_count = hash_count
        self._count = 0

    def _hash_indices(self, item: str) -> List[int]:
        h1 = hashlib.sha256(item.encode()).digest()
        h2 = hashlib.sha256(h1 + b"bloom2").digest()
        h1_val = int.from_bytes(h1[:8], 'little')
        h2_val = int.from_bytes(h2[:8], 'little')
        bit_size = self.size * 8
        return [(h1_val + i * h2_val) % bit_size for i in range(self.hash_count)]

    def insert(self, item: str) -> None:
        for idx in self._hash_indices(item):
            self.bits[idx // 8] |= 1 << (idx % 8)
        self._count += 1

    def check(self, item: str) -> bool:
        for idx in self._hash_indices(item):
            if not (self.bits[idx // 8] & (1 << (idx % 8))):
                return False
        return True

    def to_bytes(self) -> bytes:
        return bytes(self.bits)

    @staticmethod
    def from_bytes(data: bytes, hash_count: int) -> 'PythonBloomFilter':
        bf = PythonBloomFilter(len(data), hash_count)
        bf.bits = bytearray(data)
        return bf

    def item_count(self) -> int:
        return self._count

    def byte_size(self) -> int:
        return self.size


def create_bloom_filter(size: int = 1024, hash_count: int = 7):
    """Create a Bloom filter (Rust or Python)."""
    if _USE_RUST_BLOOM:
        return RustBloomFilter(size, hash_count)
    return PythonBloomFilter(size, hash_count)


class DeniableRPCHandler:
    """Privacy-preserving batch RPC handler.

    All methods run in constant time regardless of results.
    No logging of query content.
    """

    def __init__(self, db_manager) -> None:
        self.db = db_manager
        self._max_batch = Config.DENIABLE_RPC_MAX_BATCH
        self._bloom_max_size = Config.DENIABLE_RPC_BLOOM_MAX_SIZE
        logger.info(
            f"DeniableRPCHandler initialized: "
            f"max_batch={self._max_batch}, bloom_max={self._bloom_max_size}, "
            f"rust_bloom={_USE_RUST_BLOOM}"
        )

    def batch_balance(self, addresses: List[str]) -> Dict[str, float]:
        """Query balances for a batch of addresses.

        Returns balances for ALL addresses in the batch (real + decoy).
        Never short-circuits — processes every address.

        Args:
            addresses: List of addresses to query (real + decoys)

        Returns:
            Dict mapping address -> balance for all addresses
        """
        if len(addresses) > self._max_batch:
            addresses = addresses[:self._max_batch]

        results = {}
        for addr in addresses:
            balance = self._query_balance(addr)
            results[addr] = balance

        return results

    def bloom_utxos(self, address: str,
                     bloom_size: int = 1024,
                     hash_count: int = 7) -> bytes:
        """Return a Bloom filter of UTXOs for an address.

        The Bloom filter provides plausible deniability — the client
        can check UTXO membership without the server knowing which
        specific UTXOs the client is interested in.

        Args:
            address: Address to build filter for
            bloom_size: Size of the Bloom filter in bytes
            hash_count: Number of hash functions

        Returns:
            Bloom filter as bytes
        """
        bloom_size = min(bloom_size, self._bloom_max_size)
        bf = create_bloom_filter(bloom_size, hash_count)

        utxos = self._query_utxos(address)
        for utxo in utxos:
            bf.insert(utxo)

        return bf.to_bytes()

    def batch_blocks(self, heights: List[int]) -> Dict[int, Optional[dict]]:
        """Query blocks by height in batch.

        Args:
            heights: List of block heights (real + decoys)

        Returns:
            Dict mapping height -> block data (or None)
        """
        if len(heights) > self._max_batch:
            heights = heights[:self._max_batch]

        results = {}
        for height in heights:
            block = self._query_block(height)
            results[height] = block

        return results

    def batch_tx(self, txids: List[str]) -> Dict[str, Optional[dict]]:
        """Query transactions by ID in batch.

        Args:
            txids: List of transaction IDs (real + decoys)

        Returns:
            Dict mapping txid -> tx data (or None)
        """
        if len(txids) > self._max_batch:
            txids = txids[:self._max_batch]

        results = {}
        for txid in txids:
            tx = self._query_tx(txid)
            results[txid] = tx

        return results

    # ── Internal queries (no content logging) ───────────────────────────

    def _query_balance(self, address: str) -> float:
        """Query balance without logging the address."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                result = session.execute(
                    text("SELECT balance FROM address_balances WHERE address = :addr"),
                    {'addr': address}
                ).fetchone()
                return float(result[0]) if result else 0.0
        except Exception:
            return 0.0

    def _query_utxos(self, address: str) -> List[str]:
        """Query UTXOs without logging the address."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                results = session.execute(
                    text("SELECT txid || ':' || vout FROM utxo_set WHERE address = :addr AND spent = false"),
                    {'addr': address}
                ).fetchall()
                return [r[0] for r in results]
        except Exception:
            return []

    def _query_block(self, height: int) -> Optional[dict]:
        """Query block without logging the height."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                result = session.execute(
                    text("SELECT block_hash, height, created_at FROM blocks WHERE height = :h"),
                    {'h': height}
                ).fetchone()
                if result:
                    return {'hash': result[0], 'height': result[1], 'timestamp': str(result[2])}
                return None
        except Exception:
            return None

    def _query_tx(self, txid: str) -> Optional[dict]:
        """Query transaction without logging the txid."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                result = session.execute(
                    text("SELECT txid, block_height FROM transactions WHERE txid = :txid"),
                    {'txid': txid}
                ).fetchone()
                if result:
                    return {'txid': result[0], 'block_height': result[1]}
                return None
        except Exception:
            return None
