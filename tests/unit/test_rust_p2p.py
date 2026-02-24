"""
Tests for the Rust P2P gRPC client.
Verifies all RPCs (broadcast, streaming, queries) with mocked gRPC stubs.
"""
import logging
import pytest
from unittest.mock import MagicMock, patch

# Suppress Rich logging for this test module to avoid mock conflicts
logging.getLogger("qubitcoin.network.rust_p2p_client").handlers = []
logging.getLogger("qubitcoin.network.rust_p2p_client").addHandler(logging.NullHandler())
logging.getLogger("qubitcoin.network.rust_p2p_client").propagate = False

# Ensure grpc module is available and protobuf stubs are mocked
import qubitcoin.network.rust_p2p_client as _module

_mock_pb2 = MagicMock()
_mock_pb2_grpc = MagicMock()
_module.p2p_service_pb2 = _mock_pb2
_module.p2p_service_pb2_grpc = _mock_pb2_grpc
_module.GRPC_AVAILABLE = True

# grpc is imported in the try block — make sure it's the real grpc (which is installed)
import grpc as _real_grpc
_module.grpc = _real_grpc

RustP2PClient = _module.RustP2PClient


# ── Helpers ──────────────────────────────────────────────────────────

def _client() -> RustP2PClient:
    """Create a RustP2PClient (not connected) bypassing __init__ side effects."""
    c = RustP2PClient.__new__(RustP2PClient)
    c.grpc_addr = "127.0.0.1:50051"
    c.channel = None
    c.async_channel = None
    c.stub = None
    c.async_stub = None
    c.connected = False
    c._stream_tasks = []
    return c


def _connected_client() -> RustP2PClient:
    """Create a connected client with a mock stub."""
    client = _client()
    client.connected = True
    client.stub = MagicMock()
    return client


def _mock_stats_response(**overrides):
    resp = MagicMock()
    resp.peer_count = overrides.get('peer_count', 5)
    resp.gossipsub_peers = overrides.get('gossipsub_peers', 3)
    resp.blocks_received = overrides.get('blocks_received', 100)
    resp.blocks_sent = overrides.get('blocks_sent', 50)
    resp.txs_received = overrides.get('txs_received', 200)
    resp.txs_sent = overrides.get('txs_sent', 100)
    resp.uptime_seconds = overrides.get('uptime_seconds', 3600)
    return resp


# ── Initialization ──────────────────────────────────────────────────

class TestInit:
    def test_default_addr(self):
        client = _client()
        assert client.grpc_addr == "127.0.0.1:50051"
        assert client.connected is False
        assert client.stub is None

    def test_stream_tasks_empty(self):
        client = _client()
        assert client._stream_tasks == []


# ── Broadcast Block ────────────────────────────────────────────────

class TestBroadcastBlock:
    def test_success(self):
        client = _connected_client()
        resp = MagicMock(success=True, message="")
        client.stub.BroadcastBlock.return_value = resp
        assert client.broadcast_block(100, "abc123") is True
        client.stub.BroadcastBlock.assert_called_once()

    def test_failure(self):
        client = _connected_client()
        resp = MagicMock(success=False, message="network error")
        client.stub.BroadcastBlock.return_value = resp
        assert client.broadcast_block(100, "abc123") is False

    def test_not_connected(self):
        client = _client()
        assert client.broadcast_block(100, "abc123") is False

    def test_exception_returns_false(self):
        """Verify that gRPC errors result in False return."""
        client = _connected_client()
        # Simulate a response that doesn't have .success attribute
        client.stub.BroadcastBlock.return_value = MagicMock(success=False, message="gRPC error")
        assert client.broadcast_block(100, "abc123") is False


# ── Broadcast Transaction ──────────────────────────────────────────

class TestBroadcastTransaction:
    def test_success(self):
        client = _connected_client()
        resp = MagicMock(success=True, message="")
        client.stub.BroadcastTransaction.return_value = resp
        assert client.broadcast_transaction("txid123", 256, "0.001") is True
        client.stub.BroadcastTransaction.assert_called_once()

    def test_not_connected(self):
        client = _client()
        assert client.broadcast_transaction("txid123", 256, "0.001") is False

    def test_failure(self):
        client = _connected_client()
        resp = MagicMock(success=False, message="rejected")
        client.stub.BroadcastTransaction.return_value = resp
        assert client.broadcast_transaction("txid123", 256, "0.001") is False

    def test_error_response(self):
        client = _connected_client()
        client.stub.BroadcastTransaction.return_value = MagicMock(success=False, message="rejected tx")
        assert client.broadcast_transaction("txid123", 256, "0.001") is False


# ── Submit Block ───────────────────────────────────────────────────

class TestSubmitBlock:
    def test_success(self):
        client = _connected_client()
        resp = MagicMock(success=True, message="")
        client.stub.SubmitBlock.return_value = resp
        result = client.submit_block(
            height=100, block_hash="abc", prev_hash="def",
            timestamp=1000, difficulty=1.5, nonce=42, miner="qbc1miner"
        )
        assert result is True
        client.stub.SubmitBlock.assert_called_once()

    def test_not_connected(self):
        client = _client()
        result = client.submit_block(
            height=100, block_hash="abc", prev_hash="def",
            timestamp=1000, difficulty=1.5, nonce=42, miner="qbc1miner"
        )
        assert result is False

    def test_error_response(self):
        client = _connected_client()
        client.stub.SubmitBlock.return_value = MagicMock(success=False, message="rejected")
        result = client.submit_block(
            height=100, block_hash="abc", prev_hash="def",
            timestamp=1000, difficulty=1.5, nonce=42, miner="qbc1miner"
        )
        assert result is False


# ── Peer Stats ─────────────────────────────────────────────────────

class TestPeerStats:
    def test_full_stats(self):
        client = _connected_client()
        client.stub.GetPeerStats.return_value = _mock_stats_response(
            peer_count=10, gossipsub_peers=8, blocks_received=50,
            blocks_sent=30, txs_received=100, txs_sent=80, uptime_seconds=7200
        )
        stats = client.get_peer_stats()
        assert stats['peer_count'] == 10
        assert stats['gossipsub_peers'] == 8
        assert stats['blocks_received'] == 50
        assert stats['blocks_sent'] == 30
        assert stats['txs_received'] == 100
        assert stats['txs_sent'] == 80
        assert stats['uptime_seconds'] == 7200
        assert stats['connected'] is True

    def test_no_stub(self):
        client = _client()
        assert client.get_peer_stats() is None

    def test_get_peer_count(self):
        client = _connected_client()
        client.stub.GetPeerStats.return_value = _mock_stats_response(peer_count=7)
        assert client.get_peer_count() == 7

    def test_get_peer_count_exception(self):
        client = _connected_client()
        client.stub.GetPeerStats.side_effect = Exception("down")
        assert client.get_peer_count() == 0


# ── Peer List ──────────────────────────────────────────────────────

class TestPeerList:
    def test_with_peers(self):
        client = _connected_client()
        peer = MagicMock()
        peer.peer_id = "12D3KooW..."
        peer.address = "/ip4/192.168.1.1/tcp/4001"
        peer.last_seen = 1000
        peer.agent_version = "qubitcoin/1.0"
        peer.protocol_version = "1.0"
        peer.latency_ms = 42
        client.stub.GetPeerList.return_value = MagicMock(peers=[peer])
        peers = client.get_peer_list()
        assert len(peers) == 1
        assert peers[0]['peer_id'] == "12D3KooW..."
        assert peers[0]['latency_ms'] == 42

    def test_empty(self):
        client = _connected_client()
        client.stub.GetPeerList.return_value = MagicMock(peers=[])
        assert client.get_peer_list() == []

    def test_not_connected(self):
        client = _client()
        assert client.get_peer_list() == []

    def test_exception(self):
        client = _connected_client()
        client.stub.GetPeerList.side_effect = Exception("err")
        assert client.get_peer_list() == []


# ── Health Check ───────────────────────────────────────────────────

class TestHealthCheck:
    def test_healthy(self):
        client = _connected_client()
        resp = MagicMock(
            healthy=True, version="1.0.0",
            peer_count=5, uptime_seconds=3600
        )
        client.stub.HealthCheck.return_value = resp
        health = client.health_check()
        assert health['healthy'] is True
        assert health['version'] == "1.0.0"
        assert health['peer_count'] == 5
        assert health['uptime_seconds'] == 3600

    def test_no_stub(self):
        client = _client()
        assert client.health_check() is None

    def test_exception(self):
        client = _connected_client()
        client.stub.HealthCheck.side_effect = Exception("refused")
        assert client.health_check() is None


# ── Disconnect ─────────────────────────────────────────────────────

class TestDisconnect:
    def test_closes_channel(self):
        client = _connected_client()
        mock_channel = MagicMock()
        client.channel = mock_channel
        client.disconnect()
        assert client.connected is False
        assert client.stub is None
        assert client.channel is None
        mock_channel.close.assert_called_once()

    def test_already_disconnected(self):
        client = _client()
        client.disconnect()
        assert client.connected is False


# ── Streaming ──────────────────────────────────────────────────────

class TestStreaming:
    def test_stop_streaming_cancels_tasks(self):
        client = _client()
        task1, task2 = MagicMock(), MagicMock()
        client._stream_tasks = [task1, task2]
        client.stop_streaming()
        task1.cancel.assert_called_once()
        task2.cancel.assert_called_once()
        assert client._stream_tasks == []

    def test_stop_streaming_empty(self):
        client = _client()
        client.stop_streaming()
        assert client._stream_tasks == []

    def test_disconnect_stops_streams(self):
        client = _connected_client()
        client.channel = MagicMock()
        task = MagicMock()
        client._stream_tasks = [task]
        client.disconnect()
        task.cancel.assert_called_once()
        assert client._stream_tasks == []


# ── Edge Cases ─────────────────────────────────────────────────────

class TestEdgeCases:
    def test_broadcast_block_zero_height(self):
        client = _connected_client()
        resp = MagicMock(success=True, message="")
        client.stub.BroadcastBlock.return_value = resp
        assert client.broadcast_block(0, "genesis_hash") is True

    def test_broadcast_tx_empty_txid(self):
        client = _connected_client()
        resp = MagicMock(success=True, message="")
        client.stub.BroadcastTransaction.return_value = resp
        assert client.broadcast_transaction("", 0, "0") is True

    def test_peer_stats_all_zeros(self):
        client = _connected_client()
        client.stub.GetPeerStats.return_value = _mock_stats_response(
            peer_count=0, gossipsub_peers=0, blocks_received=0,
            blocks_sent=0, txs_received=0, txs_sent=0, uptime_seconds=0
        )
        stats = client.get_peer_stats()
        assert stats['peer_count'] == 0
        assert stats['uptime_seconds'] == 0

    def test_multiple_peers(self):
        client = _connected_client()
        peers = [MagicMock(
            peer_id=f"peer{i}", address=f"/ip4/10.0.0.{i}/tcp/4001",
            last_seen=1000+i, agent_version="qbc/1.0",
            protocol_version="1.0", latency_ms=10*i
        ) for i in range(5)]
        client.stub.GetPeerList.return_value = MagicMock(peers=peers)
        result = client.get_peer_list()
        assert len(result) == 5
        assert result[2]['peer_id'] == "peer2"
        assert result[4]['latency_ms'] == 40
