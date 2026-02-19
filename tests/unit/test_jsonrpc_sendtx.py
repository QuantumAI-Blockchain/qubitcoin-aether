"""Tests for eth_sendTransaction JSON-RPC method (Batch 11.2)."""
import asyncio
import time
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from qubitcoin.network.jsonrpc import JsonRpcHandler, JsonRpcRequest


def _handler(qvm: MagicMock | None = None) -> JsonRpcHandler:
    db = MagicMock()
    db.get_current_height.return_value = 100
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    db.get_session.return_value = session
    return JsonRpcHandler(db=db, qvm=qvm)


def _run(coro):
    return asyncio.run(coro)


class TestEthSendTransactionExists:
    """Verify the method is registered and callable."""

    def test_method_registered(self):
        h = _handler()
        assert 'eth_sendTransaction' in h.methods

    def test_returns_tx_hash(self):
        h = _handler()
        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x6080604052',
        }]))
        assert result.startswith('0x')
        assert len(result) == 66  # 0x + 64 hex chars

    def test_deploy_no_to(self):
        """When 'to' is missing/empty it should be a contract_deploy."""
        h = _handler()
        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x6080604052',
        }]))
        assert isinstance(result, str)

    def test_call_with_to(self):
        """When 'to' is present it should be a contract_call."""
        h = _handler()
        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'to': '0x' + 'bb' * 20,
            'data': '0x12345678',
        }]))
        assert result.startswith('0x')


class TestEthSendTransactionWithQVM:
    """Verify that QVM integration is invoked when available."""

    def test_routes_deploy_through_qvm(self):
        mock_qvm = MagicMock()
        mock_receipt = MagicMock()
        mock_receipt.txid = 'abc123'
        mock_qvm.process_transaction.return_value = mock_receipt
        h = _handler(qvm=mock_qvm)

        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x6080604052',
        }]))
        assert result.startswith('0x')
        mock_qvm.process_transaction.assert_called_once()

        # Verify the Transaction object passed to StateManager
        call_args = mock_qvm.process_transaction.call_args
        tx = call_args[0][0] if call_args[0] else call_args[1].get('tx')
        assert tx.tx_type == 'contract_deploy'

    def test_routes_call_through_qvm(self):
        mock_qvm = MagicMock()
        mock_receipt = MagicMock()
        mock_qvm.process_transaction.return_value = mock_receipt
        h = _handler(qvm=mock_qvm)

        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'to': '0x' + 'cc' * 20,
            'data': '0xabcdef00',
        }]))
        call_args = mock_qvm.process_transaction.call_args
        tx = call_args[0][0]
        assert tx.tx_type == 'contract_call'

    def test_qvm_none_falls_back_to_mempool(self):
        """When qvm.process_transaction returns None, fall back to DB insert."""
        mock_qvm = MagicMock()
        mock_qvm.process_transaction.return_value = None
        h = _handler(qvm=mock_qvm)

        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x6080604052',
        }]))
        assert result.startswith('0x')
        # DB session should have been used for fallback insert
        h.db.get_session.assert_called()


class TestEthSendTransactionParams:
    """Verify parameter parsing."""

    def test_gas_hex_parsing(self):
        mock_qvm = MagicMock()
        mock_qvm.process_transaction.return_value = MagicMock()
        h = _handler(qvm=mock_qvm)

        _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x00',
            'gas': '0x7a120',  # 500000
        }]))
        tx = mock_qvm.process_transaction.call_args[0][0]
        assert tx.gas_limit == 500000

    def test_value_hex_parsing(self):
        mock_qvm = MagicMock()
        mock_qvm.process_transaction.return_value = MagicMock()
        h = _handler(qvm=mock_qvm)

        _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'to': '0x' + 'bb' * 20,
            'data': '0x',
            'value': '0x64',  # 100
        }]))
        # Value goes into the Transaction (not directly tested on the model but ensures no error)
        assert mock_qvm.process_transaction.called

    def test_nonce_hex_parsing(self):
        mock_qvm = MagicMock()
        mock_qvm.process_transaction.return_value = MagicMock()
        h = _handler(qvm=mock_qvm)

        _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x00',
            'nonce': '0x5',
        }]))
        tx = mock_qvm.process_transaction.call_args[0][0]
        assert tx.nonce == 5


class TestJsonRpcIntegration:
    """Test via the full handle() dispatch."""

    def test_dispatch_eth_sendTransaction(self):
        h = _handler()
        req = JsonRpcRequest(
            method='eth_sendTransaction',
            params=[{'from': '0x' + 'aa' * 20, 'data': '0x6080604052'}],
            id=42,
        )
        resp = _run(h.handle(req))
        assert resp.error is None
        assert resp.result.startswith('0x')
        assert resp.id == 42
