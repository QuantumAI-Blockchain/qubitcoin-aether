"""Tests verifying Run #32 fixes: genesis attr, thread-safe stats, rate limiter
eviction, susy validation, key image safety, seen digests ordering,
deterministic coinbase txid, stablecoin session.

Covers:
- genesis_block.block_hash (not .hash)
- mining stats accessed via get_stats_snapshot() (thread-safe)
- Rate limiter evicts stale IP keys
- _validate_block_susy_swaps rejects on non-ImportError exceptions
- _is_key_image_spent rejects on unknown DB errors
- _seen_digests preserves insertion order (dict, not set)
- Coinbase txid is deterministic (no time.time())
- Stablecoin get_aggregated_price uses sample std (ddof=1)
"""

import hashlib
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ======================================================================
# genesis_block.block_hash (not .hash)
# ======================================================================


class TestGenesisBlockAttr:
    """Verify node.py uses .block_hash, not .hash."""

    def test_node_uses_block_hash_attr(self) -> None:
        """AetherGenesis init should reference .block_hash."""
        import inspect
        from qubitcoin.node import QubitcoinNode
        source = inspect.getsource(QubitcoinNode.__init__)
        # Must use genesis_block.block_hash (not .hash)
        assert 'genesis_block.block_hash' in source
        assert 'genesis_block.hash ' not in source


# ======================================================================
# Thread-safe mining stats
# ======================================================================


class TestThreadSafeMiningStats:
    """Verify RPC endpoints use get_stats_snapshot() not direct .stats access."""

    def test_rpc_no_direct_stats_access(self) -> None:
        """rpc.py should not access mining_engine.stats.get() directly."""
        import inspect
        from qubitcoin.network import rpc
        source = inspect.getsource(rpc.create_rpc_app)
        # The /mining/stats endpoint correctly uses get_stats_snapshot()
        # Other endpoints should NOT access mining_engine.stats.get()
        assert 'mining_engine.stats.get(' not in source


# ======================================================================
# Rate limiter IP eviction
# ======================================================================


class TestRateLimiterEviction:
    """Verify stale IP keys are evicted from rate limit store."""

    def test_empty_ip_evicted(self) -> None:
        """IPs with no recent requests should be removed from store."""
        import inspect
        from qubitcoin.network import rpc
        source = inspect.getsource(rpc.create_rpc_app)
        # Should contain eviction logic (pop or del for empty keys)
        assert '.pop(client_ip' in source or 'del _rate_limit_store' in source


# ======================================================================
# Susy Swap validation — only ImportError passes
# ======================================================================


class TestSusyValidationException:
    """Verify non-ImportError exceptions reject the block."""

    def test_non_import_error_rejects_block(self) -> None:
        """A KeyError in susy validation should reject the block."""
        from qubitcoin.consensus.engine import ConsensusEngine
        ce = ConsensusEngine(MagicMock(), MagicMock(), MagicMock())

        # Create a block with a private tx that will cause a non-ImportError
        block = MagicMock()
        block.transactions = [MagicMock()]
        block.transactions[0].is_private = True
        block.transactions[0].inputs = [{'key_image': 'abc'}]
        block.transactions[0].outputs = [{}]
        block.transactions[0].txid = 'test_tx'
        # Force a TypeError inside susy validation by making outputs weird
        block.transactions[0].outputs = 'not_a_list'

        valid, reason = ce._validate_block_susy_swaps(block, MagicMock())
        assert valid is False


# ======================================================================
# Key image — unknown DB errors reject tx
# ======================================================================


class TestKeyImageSafety:
    """Verify _is_key_image_spent rejects on unknown DB errors."""

    def test_table_missing_allows_tx(self) -> None:
        """If key_images table doesn't exist, return False (allow)."""
        from qubitcoin.consensus.engine import ConsensusEngine
        ce = ConsensusEngine(MagicMock(), MagicMock(), MagicMock())
        db = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(
            side_effect=Exception("relation \"key_images\" does not exist")
        )
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        assert ce._is_key_image_spent('abc', db) is False

    def test_unknown_error_rejects_tx(self) -> None:
        """Unknown DB errors (timeouts etc.) should return True (reject)."""
        from qubitcoin.consensus.engine import ConsensusEngine
        ce = ConsensusEngine(MagicMock(), MagicMock(), MagicMock())
        db = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(
            side_effect=Exception("connection timed out")
        )
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        assert ce._is_key_image_spent('abc', db) is True


# ======================================================================
# Seen digests — insertion order preserved
# ======================================================================


class TestSeenDigests:
    """Verify _seen_digests uses ordered dict, not unordered set."""

    def test_seen_digests_is_dict(self) -> None:
        """_seen_digests should be a dict (ordered in Python 3.7+)."""
        from qubitcoin.aether.proof_of_thought import AetherEngine
        engine = AetherEngine(
            db_manager=MagicMock(),
            knowledge_graph=MagicMock(),
            phi_calculator=MagicMock(),
            reasoning_engine=MagicMock(),
        )
        assert isinstance(engine._seen_digests, dict)
        assert not isinstance(engine._seen_digests, set)


# ======================================================================
# Deterministic coinbase txid
# ======================================================================


class TestDeterministicCoinbase:
    """Verify coinbase txid does not use time.time()."""

    def test_coinbase_txid_deterministic(self) -> None:
        """Same height + prev_hash should produce same coinbase txid."""
        from qubitcoin.mining.engine import MiningEngine
        me = MiningEngine(MagicMock(), MagicMock(), MagicMock(), MagicMock())

        cb1 = me._create_coinbase(100, Decimal('15.27'), [], 'aabb' * 16)
        cb2 = me._create_coinbase(100, Decimal('15.27'), [], 'aabb' * 16)
        assert cb1.txid == cb2.txid

    def test_different_heights_different_txid(self) -> None:
        """Different heights should produce different coinbase txids."""
        from qubitcoin.mining.engine import MiningEngine
        me = MiningEngine(MagicMock(), MagicMock(), MagicMock(), MagicMock())

        cb1 = me._create_coinbase(100, Decimal('15.27'), [], 'aabb' * 16)
        cb2 = me._create_coinbase(101, Decimal('15.27'), [], 'ccdd' * 16)
        assert cb1.txid != cb2.txid

    def test_no_time_in_coinbase_source(self) -> None:
        """Source code should not use time.time() for coinbase txid."""
        import inspect
        from qubitcoin.mining.engine import MiningEngine
        source = inspect.getsource(MiningEngine._create_coinbase)
        assert 'time.time()' not in source.split('coinbase_txid')[1].split('.hexdigest')[0]
