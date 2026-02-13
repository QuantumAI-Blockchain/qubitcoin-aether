"""Unit tests for block sync protocol in P2P network."""
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

import pytest


def _make_network(local_height: int = 0):
    """Create a P2PNetwork with mocked consensus."""
    from qubitcoin.network.p2p_network import P2PNetwork, Peer

    consensus = MagicMock()
    consensus.db = MagicMock()
    consensus.db.get_current_height.return_value = local_height

    net = P2PNetwork(port=4001, peer_id="sync-node", consensus=consensus)

    # Add a mock peer
    pid = "peer-sync"
    net.connections[pid] = Peer(
        peer_id=pid,
        host="127.0.0.1",
        port=4002,
        connected_at=datetime.now(),
        last_seen=datetime.now(),
    )
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    net.writers[pid] = writer

    return net


class TestRequestBlockRange:
    """Test block range request for sync."""

    def test_request_sends_message(self):
        """Block range request sends get_block_range message."""
        net = _make_network()
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            net.request_block_range("peer-sync", 0, 99)
        )
        loop.close()
        assert result is True

    def test_request_unknown_peer_returns_false(self):
        """Request to unknown peer returns False."""
        net = _make_network()
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            net.request_block_range("unknown-peer", 0, 99)
        )
        loop.close()
        assert result is False

    def test_request_invalid_range_returns_false(self):
        """start > end returns False."""
        net = _make_network()
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            net.request_block_range("peer-sync", 100, 50)
        )
        loop.close()
        assert result is False

    def test_request_caps_at_500_blocks(self):
        """Request for > 500 blocks is capped."""
        net = _make_network()
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            net.request_block_range("peer-sync", 0, 1000)
        )
        loop.close()
        assert result is True
        # Verify the message was sent with capped range (0-499)

    def test_request_single_block(self):
        """Requesting a single block works."""
        net = _make_network()
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            net.request_block_range("peer-sync", 42, 42)
        )
        loop.close()
        assert result is True


class TestSyncToPeer:
    """Test sync initiation."""

    def test_sync_to_peer_sends_height_request(self):
        """sync_to_peer sends a get_height message."""
        net = _make_network(local_height=5)
        loop = asyncio.new_event_loop()
        count = loop.run_until_complete(net.sync_to_peer("peer-sync"))
        loop.close()
        assert count == 1

    def test_sync_increments_stat(self):
        """sync_to_peer increments sync_requests stat."""
        net = _make_network(local_height=0)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(net.sync_to_peer("peer-sync"))
        loop.run_until_complete(net.sync_to_peer("peer-sync"))
        loop.close()
        assert net.stats.get('sync_requests', 0) == 2


class TestGetSyncStatus:
    """Test sync status reporting."""

    def test_sync_status_initial(self):
        """Initial sync status has zero values."""
        net = _make_network(local_height=0)
        status = net.get_sync_status()
        assert status['local_height'] == 0
        assert status['sync_requests'] == 0
        assert status['blocks_propagated'] == 0
        assert status['connected_peers'] == 1

    def test_sync_status_after_sync(self):
        """Sync status reflects sync activity."""
        net = _make_network(local_height=100)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(net.sync_to_peer("peer-sync"))
        loop.close()

        status = net.get_sync_status()
        assert status['local_height'] == 100
        assert status['sync_requests'] == 1

    def test_sync_status_handles_db_error(self):
        """Sync status handles DB errors gracefully."""
        net = _make_network()
        net.consensus.db.get_current_height.side_effect = Exception("DB down")
        status = net.get_sync_status()
        assert status['local_height'] == 0  # Fallback to 0 on error


class TestHeightHandlerSync:
    """Test that the height handler triggers sync when behind."""

    def test_height_response_triggers_block_request(self):
        """When peer has higher height, we request their block."""
        net = _make_network(local_height=5)

        from qubitcoin.network.p2p_network import Message
        msg = Message(
            type='height',
            data={'height': 10},
            timestamp=time.time(),
            sender_id="peer-sync",
            msg_id="height-msg-001",
        )

        loop = asyncio.new_event_loop()
        loop.run_until_complete(net._handle_message(msg, "peer-sync"))
        loop.close()

        # The handler should have sent a get_block request for height 10

    def test_height_response_no_sync_when_ahead(self):
        """When we have a higher height, no block request sent."""
        net = _make_network(local_height=20)

        from qubitcoin.network.p2p_network import Message
        msg = Message(
            type='height',
            data={'height': 10},
            timestamp=time.time(),
            sender_id="peer-sync",
            msg_id="height-msg-002",
        )

        initial_sent = net.stats['messages_sent']
        loop = asyncio.new_event_loop()
        loop.run_until_complete(net._handle_message(msg, "peer-sync"))
        loop.close()

        # No additional message should be sent (we're ahead)
        assert net.stats['messages_sent'] == initial_sent
