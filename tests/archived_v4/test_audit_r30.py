"""Tests verifying Run #30 fixes: consciousness double-count, keccak256,
batcher timeout, oracle falsy checks, LP dead code removal.

Covers:
- ConsciousnessDashboard._total_conscious_blocks correct counting
- token_indexer TRANSFER_TOPIC uses keccak256 (not SHA3-256)
- proxy IMPLEMENTATION_SLOT uses keccak256 (not SHA3-256)
- abi._keccak256 uses real keccak256 (not SHA-256)
- TransactionBatcher._start_block lazy init
- QUSDOracle Decimal(0) truthiness
- BridgeLiquidityPool dead code removal
"""

import hashlib
import time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest


# ======================================================================
# Consciousness Dashboard — no double-counting
# ======================================================================


class TestConsciousnessDoubleCount:
    """Verify _total_conscious_blocks is not double-counted."""

    def test_sustained_consciousness_counted_once(self) -> None:
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        dash = ConsciousnessDashboard()
        # 10 blocks of consciousness (phi=4.0, coherence=0.8 => conscious)
        for h in range(10):
            dash.record_measurement(h, phi_value=4.0, coherence=0.8)
        # Then lose consciousness
        dash.record_measurement(10, phi_value=1.0, coherence=0.2)
        status = dash.get_consciousness_status()
        # Blocks 0-9 were conscious = 10 blocks, NOT 20 (old double-count)
        assert status['total_conscious_blocks'] == 10

    def test_no_double_count_multiple_spans(self) -> None:
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        dash = ConsciousnessDashboard()
        # Span 1: blocks 0-4 conscious (5 blocks)
        for h in range(5):
            dash.record_measurement(h, phi_value=4.0, coherence=0.8)
        dash.record_measurement(5, phi_value=1.0, coherence=0.2)  # loss
        # Span 2: blocks 10-14 conscious (5 blocks)
        for h in range(6, 10):
            dash.record_measurement(h, phi_value=1.0, coherence=0.2)
        for h in range(10, 15):
            dash.record_measurement(h, phi_value=4.0, coherence=0.8)
        dash.record_measurement(15, phi_value=1.0, coherence=0.2)  # loss
        status = dash.get_consciousness_status()
        assert status['total_conscious_blocks'] == 10  # 5 + 5

    def test_in_progress_consciousness_included_in_status(self) -> None:
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        dash = ConsciousnessDashboard()
        # Conscious from block 0
        for h in range(5):
            dash.record_measurement(h, phi_value=4.0, coherence=0.8)
        # Still conscious (no loss event)
        status = dash.get_consciousness_status()
        assert status['is_conscious'] is True
        # Should include in-progress blocks: block 4 - block 0 = 4
        assert status['total_conscious_blocks'] == 4

    def test_unconscious_zero_blocks(self) -> None:
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        dash = ConsciousnessDashboard()
        for h in range(10):
            dash.record_measurement(h, phi_value=1.0, coherence=0.2)
        status = dash.get_consciousness_status()
        assert status['total_conscious_blocks'] == 0
        assert status['consciousness_ratio'] == 0.0


# ======================================================================
# Keccak-256 vs SHA3-256 — correct hash function
# ======================================================================


class TestKeccakUsage:
    """Verify EVM-critical code uses keccak256, not SHA3-256 or SHA-256."""

    def test_transfer_topic_not_sha3(self) -> None:
        """TRANSFER_TOPIC must NOT equal SHA3-256 output."""
        from qubitcoin.qvm.token_indexer import TRANSFER_TOPIC
        sha3_result = hashlib.sha3_256(
            b'Transfer(address,address,uint256)'
        ).hexdigest()
        # After fix, these should differ (keccak != SHA3)
        from qubitcoin.qvm.vm import keccak256
        keccak_result = keccak256(
            b'Transfer(address,address,uint256)'
        ).hex()
        assert TRANSFER_TOPIC == keccak_result

    def test_approval_topic_uses_keccak(self) -> None:
        from qubitcoin.qvm.token_indexer import APPROVAL_TOPIC
        from qubitcoin.qvm.vm import keccak256
        expected = keccak256(b'Approval(address,address,uint256)').hex()
        assert APPROVAL_TOPIC == expected

    def test_proxy_slots_use_keccak(self) -> None:
        from qubitcoin.contracts.proxy import IMPLEMENTATION_SLOT, ADMIN_SLOT
        from qubitcoin.qvm.vm import keccak256
        expected_impl = int.from_bytes(
            keccak256(b"eip1967.proxy.implementation"), "big"
        ) - 1
        expected_admin = int.from_bytes(
            keccak256(b"eip1967.proxy.admin"), "big"
        ) - 1
        assert IMPLEMENTATION_SLOT == expected_impl
        assert ADMIN_SLOT == expected_admin

    def test_abi_function_selector_uses_keccak(self) -> None:
        from qubitcoin.qvm.abi import function_selector
        from qubitcoin.qvm.vm import keccak256
        sig = "transfer(address,uint256)"
        expected = keccak256(sig.encode())[:4]
        assert function_selector(sig) == expected


# ======================================================================
# TransactionBatcher — _start_block lazy init
# ======================================================================


class TestBatcherStartBlock:
    """Verify _start_block is not stuck at 0."""

    def test_no_premature_timeout(self) -> None:
        """A batch with 1 tx should NOT auto-submit at block 15."""
        from qubitcoin.qvm.transaction_batcher import (
            TransactionBatcher, BatchTransaction,
        )
        batcher = TransactionBatcher()
        tx = BatchTransaction(
            tx_id="tx1", sender="a", to="b", value=1.0
        )
        batcher.add_transaction(tx)
        # First should_submit call at block 15 sets _start_block = 15
        assert batcher.should_submit(15) is False
        # Block 20: only 5 blocks since start (15), timeout is 10
        assert batcher.should_submit(20) is False
        # Block 25: 10 blocks since start (15), timeout triggers
        assert batcher.should_submit(25) is True

    def test_empty_batch_no_submit(self) -> None:
        from qubitcoin.qvm.transaction_batcher import TransactionBatcher
        batcher = TransactionBatcher()
        assert batcher.should_submit(100) is False

    def test_full_batch_submits_immediately(self) -> None:
        from qubitcoin.qvm.transaction_batcher import (
            TransactionBatcher, BatchTransaction,
        )
        batcher = TransactionBatcher(max_batch_size=2)
        batcher.add_transaction(BatchTransaction(
            tx_id="t1", sender="a", to="b", value=1.0
        ))
        batcher.add_transaction(BatchTransaction(
            tx_id="t2", sender="a", to="b", value=2.0
        ))
        assert batcher.should_submit(0) is True

    def test_start_block_resets_after_execute(self) -> None:
        from qubitcoin.qvm.transaction_batcher import (
            TransactionBatcher, BatchTransaction,
        )
        batcher = TransactionBatcher()
        batcher.add_transaction(BatchTransaction(
            tx_id="t1", sender="a", to="b", value=1.0
        ))
        batcher.should_submit(100)  # sets _start_block = 100
        batcher.execute_batch(100)
        # After execute, should reset
        assert batcher._start_block is None


# ======================================================================
# QUSDOracle — Decimal(0) truthiness
# ======================================================================


class TestOracleDecimalZero:
    """Verify oracle handles Decimal('0') correctly."""

    def test_cached_price_none_vs_zero(self) -> None:
        from qubitcoin.utils.qusd_oracle import QUSDOracle
        oracle = QUSDOracle()
        assert oracle.is_price_stale() is True  # None -> stale
        # Set price to 0 would be rejected by set_external_price,
        # but simulate internal caching of a zero price
        oracle._cached_price = Decimal('0')
        oracle._cache_ts = time.time()
        # With the fix, Decimal('0') is not None, so is_price_stale() checks age
        assert oracle.is_price_stale() is False

    def test_none_cache_returns_none(self) -> None:
        from qubitcoin.utils.qusd_oracle import QUSDOracle
        oracle = QUSDOracle()
        assert oracle.get_qbc_usd_price() is None

    def test_external_price_set_and_read(self) -> None:
        from qubitcoin.utils.qusd_oracle import QUSDOracle
        oracle = QUSDOracle()
        oracle.set_external_price(Decimal('0.50'))
        price = oracle.get_qbc_usd_price()
        assert price == Decimal('0.50')


# ======================================================================
# BridgeLiquidityPool — dead code removal
# ======================================================================


class TestLPDeadCodeRemoved:
    """Verify dead code was removed and existing behavior still works."""

    def test_add_to_existing_position(self) -> None:
        from qubitcoin.bridge.liquidity_pool import BridgeLiquidityPool
        pool = BridgeLiquidityPool(min_deposit=10.0)
        pool.add_liquidity("provider1", "ethereum", 50.0)
        pos = pool.add_liquidity("provider1", "ethereum", 5.0)
        assert pos.amount == 55.0

    def test_negative_deposit_rejected(self) -> None:
        from qubitcoin.bridge.liquidity_pool import BridgeLiquidityPool
        pool = BridgeLiquidityPool(min_deposit=10.0)
        with pytest.raises(ValueError, match="positive"):
            pool.add_liquidity("provider1", "ethereum", -5.0)

    def test_zero_deposit_rejected(self) -> None:
        from qubitcoin.bridge.liquidity_pool import BridgeLiquidityPool
        pool = BridgeLiquidityPool(min_deposit=10.0)
        with pytest.raises(ValueError, match="positive"):
            pool.add_liquidity("provider1", "ethereum", 0.0)

    def test_below_minimum_new_position_rejected(self) -> None:
        from qubitcoin.bridge.liquidity_pool import BridgeLiquidityPool
        pool = BridgeLiquidityPool(min_deposit=10.0)
        with pytest.raises(ValueError, match="below minimum"):
            pool.add_liquidity("provider1", "ethereum", 5.0)
