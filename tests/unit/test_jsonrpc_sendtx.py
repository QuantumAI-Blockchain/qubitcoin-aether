"""Tests for eth_sendTransaction JSON-RPC method (Batch 11.2).

Updated to reflect security fixes:
- eth_sendTransaction requires localhost access (L1-C3)
- Transactions stored in mempool only, not executed immediately (L1-C3)
"""
import asyncio
import time
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from qubitcoin.network.jsonrpc import JsonRpcHandler, JsonRpcRequest


def _mock_localhost_request() -> MagicMock:
    """Create a mock HTTP request that simulates localhost access."""
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = '127.0.0.1'
    return req


def _handler(qvm: MagicMock | None = None) -> JsonRpcHandler:
    db = MagicMock()
    db.get_current_height.return_value = 100
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    db.get_session.return_value = session
    h = JsonRpcHandler(db=db, qvm=qvm)
    # Simulate localhost access for tests (eth_sendTransaction is localhost-only)
    h._http_request = _mock_localhost_request()
    return h


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


class TestEthSendTransactionSecurity:
    """Verify localhost-only restriction (L1-C3)."""

    def test_rejects_non_localhost(self):
        """Remote callers should be rejected."""
        h = _handler()
        # Simulate a remote request
        remote_req = MagicMock()
        remote_req.client = MagicMock()
        remote_req.client.host = '192.168.1.100'
        h._http_request = remote_req

        with pytest.raises(ValueError, match="only allowed from localhost"):
            _run(h.eth_sendTransaction([{
                'from': '0x' + 'aa' * 20,
                'data': '0x6080604052',
            }]))

    def test_rejects_no_request_info(self):
        """When no request info is available, deny by default."""
        h = _handler()
        h._http_request = None

        with pytest.raises(ValueError, match="only allowed from localhost"):
            _run(h.eth_sendTransaction([{
                'from': '0x' + 'aa' * 20,
                'data': '0x6080604052',
            }]))

    def test_allows_ipv6_localhost(self):
        """IPv6 localhost (::1) should be allowed."""
        h = _handler()
        req = MagicMock()
        req.client = MagicMock()
        req.client.host = '::1'
        h._http_request = req

        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x6080604052',
        }]))
        assert result.startswith('0x')


class TestEthSendTransactionMempoolOnly:
    """Verify transactions are stored in mempool, not executed immediately (L1-C3).

    After the security fix, eth_sendTransaction MUST NOT directly invoke QVM.
    Transactions are stored as pending and executed when mined into a block.
    """

    def test_stores_to_mempool_not_qvm(self):
        """QVM should NOT be called directly; tx goes to mempool."""
        mock_qvm = MagicMock()
        h = _handler(qvm=mock_qvm)

        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x6080604052',
        }]))
        assert result.startswith('0x')
        # QVM must NOT be invoked — execution deferred to block inclusion
        mock_qvm.process_transaction.assert_not_called()
        # DB session should have been used for mempool insert
        h.db.get_session.assert_called()

    def test_deploy_stored_as_pending(self):
        """Contract deploy should be stored as pending, not executed."""
        h = _handler()
        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x6080604052',
        }]))
        assert result.startswith('0x')
        h.db.get_session.assert_called()

    def test_call_stored_as_pending(self):
        """Contract call should be stored as pending, not executed."""
        h = _handler()
        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'to': '0x' + 'cc' * 20,
            'data': '0xabcdef00',
        }]))
        assert result.startswith('0x')
        h.db.get_session.assert_called()


class TestEthSendTransactionParams:
    """Verify parameter parsing."""

    def test_gas_hex_parsing(self):
        h = _handler()
        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x00',
            'gas': '0x7a120',  # 500000
        }]))
        assert result.startswith('0x')
        # Tx stored in mempool — verify DB session was used
        h.db.get_session.assert_called()

    def test_value_hex_parsing(self):
        h = _handler()
        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'to': '0x' + 'bb' * 20,
            'data': '0x',
            'value': '0x64',  # 100
        }]))
        assert result.startswith('0x')

    def test_nonce_hex_parsing(self):
        h = _handler()
        result = _run(h.eth_sendTransaction([{
            'from': '0x' + 'aa' * 20,
            'data': '0x00',
            'nonce': '0x5',
        }]))
        assert result.startswith('0x')


class TestJsonRpcIntegration:
    """Test via the full handle() dispatch."""

    def test_dispatch_eth_sendTransaction(self):
        h = _handler()
        # Must pass localhost request through the dispatch path
        localhost_req = _mock_localhost_request()
        req = JsonRpcRequest(
            method='eth_sendTransaction',
            params=[{'from': '0x' + 'aa' * 20, 'data': '0x6080604052'}],
            id=42,
        )
        resp = _run(h.handle(req, http_request=localhost_req))
        assert resp.error is None
        assert resp.result.startswith('0x')
        assert resp.id == 42
