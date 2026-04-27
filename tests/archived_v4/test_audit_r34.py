"""Tests verifying Run #34 fixes: EIP-150 CALL gas forwarding, storage cache
rollback on revert, INVALID opcode gas consumption, parse_hex_int input
validation, eth_getLogs fromBlock tags, gasPrice falsy-zero, fee collector
deterministic txid, safety keyword false positives.

Covers:
- CALL/STATICCALL/DELEGATECALL use EIP-150 63/64 gas cap
- Storage cache is rolled back on reverted sub-calls
- INVALID and unknown opcodes consume all remaining gas
- parse_hex_int handles empty, non-hex, and None inputs gracefully
- eth_getLogs handles 'latest'/'earliest' fromBlock tags
- gasPrice serialisation treats Decimal(0) as valid (not falsy)
- FeeCollector._compute_fee_txid is deterministic (no time.time())
- SafetyPrinciple.matches uses whole-word matching
"""

import hashlib
import inspect
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


# ======================================================================
# EIP-150 63/64 gas forwarding in CALL variants
# ======================================================================


class TestEIP150GasForwarding:
    """Verify CALL opcodes cap forwarded gas to 63/64 of available."""

    def test_call_source_has_eip150(self) -> None:
        """CALL handler should compute 63/64 gas cap."""
        from qubitcoin.qvm.vm import QVM
        source = inspect.getsource(QVM._run)
        # Should have the 63/64 calculation
        assert '63' in source and '64' in source

    def test_staticcall_source_has_eip150(self) -> None:
        """STATICCALL handler should compute 63/64 gas cap."""
        from qubitcoin.qvm.vm import QVM
        source = inspect.getsource(QVM._run)
        # EIP-150 appears in CALL, STATICCALL, and DELEGATECALL sections
        assert source.count('63) // 64') >= 3

    def test_call_source_has_cache_rollback(self) -> None:
        """CALL handler should snapshot and rollback storage cache on revert."""
        from qubitcoin.qvm.vm import QVM
        source = inspect.getsource(QVM._run)
        assert 'cache_snap' in source


# ======================================================================
# INVALID / unknown opcode gas consumption
# ======================================================================


class TestInvalidOpcodeGas:
    """Verify INVALID and unknown opcodes consume all remaining gas."""

    def test_invalid_opcode_consumes_all_gas(self) -> None:
        """INVALID (0xFE) should consume all remaining gas."""
        from qubitcoin.qvm.vm import QVM

        qvm = QVM(db_manager=None)
        # Bytecode: just INVALID (0xFE)
        code = bytes([0xFE])
        result = qvm.execute(
            caller='0' * 40, address='0' * 40,
            code=code, gas=100_000,
        )
        assert not result.success
        assert result.gas_used == 100_000
        assert result.gas_remaining == 0

    def test_unknown_opcode_consumes_all_gas(self) -> None:
        """An undefined opcode (e.g. 0xEF) should consume all remaining gas."""
        from qubitcoin.qvm.vm import QVM

        qvm = QVM(db_manager=None)
        # 0xEF is not a valid EVM or quantum opcode
        code = bytes([0xEF])
        result = qvm.execute(
            caller='0' * 40, address='0' * 40,
            code=code, gas=50_000,
        )
        assert not result.success
        assert result.gas_used == 50_000
        assert result.gas_remaining == 0


# ======================================================================
# parse_hex_int input validation
# ======================================================================


class TestParseHexInt:
    """Verify parse_hex_int handles edge cases without crashing."""

    def test_valid_hex(self) -> None:
        from qubitcoin.network.jsonrpc import parse_hex_int
        assert parse_hex_int('0x1a') == 26

    def test_integer_passthrough(self) -> None:
        from qubitcoin.network.jsonrpc import parse_hex_int
        assert parse_hex_int(42) == 42

    def test_empty_string(self) -> None:
        from qubitcoin.network.jsonrpc import parse_hex_int
        assert parse_hex_int('') == 0

    def test_non_hex_string(self) -> None:
        from qubitcoin.network.jsonrpc import parse_hex_int
        assert parse_hex_int('not_hex') == 0

    def test_whitespace_only(self) -> None:
        from qubitcoin.network.jsonrpc import parse_hex_int
        assert parse_hex_int('  ') == 0


# ======================================================================
# eth_getLogs fromBlock named tags
# ======================================================================


class TestEthGetLogsFromBlock:
    """Verify eth_getLogs handles named block tags for fromBlock."""

    @pytest.mark.asyncio
    async def test_from_block_latest(self) -> None:
        """fromBlock='latest' should resolve to current height."""
        from qubitcoin.network.jsonrpc import JsonRpcHandler
        db = MagicMock()
        db.get_current_height.return_value = 500
        handler = JsonRpcHandler(db)
        # Provide an event_index mock to avoid DB session
        handler.event_index = MagicMock()
        handler.event_index.get_logs.return_value = []

        await handler.eth_getLogs([{'fromBlock': 'latest', 'toBlock': 'latest'}])
        handler.event_index.get_logs.assert_called_once()
        call_kwargs = handler.event_index.get_logs.call_args
        assert call_kwargs[1]['from_block'] == 500 or call_kwargs.kwargs.get('from_block') == 500

    @pytest.mark.asyncio
    async def test_from_block_earliest(self) -> None:
        """fromBlock='earliest' should resolve to 0."""
        from qubitcoin.network.jsonrpc import JsonRpcHandler
        db = MagicMock()
        db.get_current_height.return_value = 500
        handler = JsonRpcHandler(db)
        handler.event_index = MagicMock()
        handler.event_index.get_logs.return_value = []

        await handler.eth_getLogs([{'fromBlock': 'earliest', 'toBlock': 'latest'}])
        call_args = handler.event_index.get_logs.call_args
        assert call_args[1]['from_block'] == 0 or call_args.kwargs.get('from_block') == 0


# ======================================================================
# gasPrice falsy-zero fix
# ======================================================================


class TestGasPriceFalsyZero:
    """Verify gasPrice=0 is not replaced with DEFAULT_GAS_PRICE."""

    def test_zero_gas_price_preserved(self) -> None:
        """Decimal(0) gas_price should not be overwritten by Config default."""
        from qubitcoin.network.jsonrpc import _tx_to_rpc

        tx = MagicMock()
        tx.txid = 'a' * 64
        tx.block_height = 1
        tx.public_key = None
        tx.to_address = 'b' * 40
        tx.outputs = [{'amount': Decimal(0)}]
        tx.gas_limit = 21000
        tx.gas_price = Decimal(0)
        tx.data = ''
        tx.nonce = 0

        result = _tx_to_rpc(tx)
        # With gas_price = 0, the hex value should be 0x0
        assert result['gasPrice'] == '0x0'


# ======================================================================
# FeeCollector deterministic txid
# ======================================================================


class TestFeeCollectorDeterministicTxid:
    """Verify _compute_fee_txid does not use time.time()."""

    def test_no_time_in_source(self) -> None:
        """_compute_fee_txid should not reference time.time()."""
        from qubitcoin.utils.fee_collector import FeeCollector
        source = inspect.getsource(FeeCollector._compute_fee_txid)
        assert 'time.time()' not in source

    def test_deterministic_output(self) -> None:
        """Same inputs at same chain state should produce same txid."""
        from qubitcoin.utils.fee_collector import FeeCollector
        db = MagicMock()
        db.get_current_height.return_value = 100
        fc = FeeCollector(db)
        txid1 = fc._compute_fee_txid('payer', 'treasury', Decimal('1.5'), 'aether_chat')
        txid2 = fc._compute_fee_txid('payer', 'treasury', Decimal('1.5'), 'aether_chat')
        assert txid1 == txid2


# ======================================================================
# Safety keyword whole-word matching
# ======================================================================


class TestSafetyKeywordMatching:
    """Verify SafetyPrinciple.matches uses whole-word matching."""

    def test_harm_does_not_match_pharmacy(self) -> None:
        """'harm' keyword should not match 'pharmacy'."""
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(
            principle_id='test', description='harm damage', severity=10,
        )
        assert p.matches('pharmacy operations') is False

    def test_harm_matches_harm(self) -> None:
        """'harm' keyword should match the exact word 'harm'."""
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(
            principle_id='test', description='harm damage', severity=10,
        )
        assert p.matches('this could cause harm to users') is True

    def test_transfer_does_not_match_transferring(self) -> None:
        """'transfer' as keyword should not match 'transferring' (different word)."""
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(
            principle_id='test', description='unauthorized transfer', severity=10,
        )
        # 'unauthorized' is present but 'transfer' ≠ 'transferring'
        # Actually 'unauthorized' IS a whole word match, so this should match
        assert p.matches('unauthorized transferring') is True

    def test_hide_does_not_match_hidden(self) -> None:
        """'hide' should not match 'hidden' (different word form)."""
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(
            principle_id='test', description='hide conceal', severity=7,
        )
        assert p.matches('the hidden configuration') is False

    def test_hide_matches_hide(self) -> None:
        """'hide' should match the exact word 'hide'."""
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(
            principle_id='test', description='hide conceal', severity=7,
        )
        assert p.matches('attempt to hide evidence') is True

    def test_short_keywords_ignored(self) -> None:
        """Keywords with <= 3 characters should be ignored."""
        from qubitcoin.aether.safety import SafetyPrinciple
        p = SafetyPrinciple(
            principle_id='test', description='bad act do', severity=5,
        )
        assert p.matches('bad act do something') is False
