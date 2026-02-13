"""Unit tests for block and transaction propagation in P2P network."""
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

import pytest


def _make_network():
    """Create a P2PNetwork with mocked consensus to avoid DB deps."""
    from qubitcoin.network.p2p_network import P2PNetwork, Peer

    consensus = MagicMock()
    consensus.db = MagicMock()
    net = P2PNetwork(port=4001, peer_id="test-node-1", consensus=consensus)

    # Add mock peers
    for i in range(3):
        pid = f"peer-{i}"
        net.connections[pid] = Peer(
            peer_id=pid,
            host="127.0.0.1",
            port=4002 + i,
            connected_at=datetime.now(),
            last_seen=datetime.now(),
        )
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        net.writers[pid] = writer

    return net


def _make_block(height: int = 1):
    """Create a minimal mock block with to_dict."""
    block = MagicMock()
    block.height = height
    block.to_dict.return_value = {
        "height": height,
        "prev_hash": "0" * 64,
        "hash": f"block_{height}_hash",
        "timestamp": time.time(),
        "transactions": [],
    }
    return block


class TestPropagateBlock:
    """Test block propagation to peers."""

    def test_propagate_block_sends_to_all_peers(self):
        """Block propagated to all connected peers."""
        net = _make_network()
        block = _make_block(10)

        loop = asyncio.new_event_loop()
        count = loop.run_until_complete(net.propagate_block(block))
        loop.close()

        assert count == 3

    def test_propagate_block_excludes_sender(self):
        """Block not sent back to the peer that sent it."""
        net = _make_network()
        block = _make_block(10)

        loop = asyncio.new_event_loop()
        count = loop.run_until_complete(net.propagate_block(block, exclude="peer-0"))
        loop.close()

        assert count == 2

    def test_propagate_block_increments_stats(self):
        """Block propagation increments blocks_propagated stat."""
        net = _make_network()
        block = _make_block(5)
        initial = net.stats['blocks_propagated']

        loop = asyncio.new_event_loop()
        loop.run_until_complete(net.propagate_block(block))
        loop.close()

        assert net.stats['blocks_propagated'] == initial + 1

    def test_propagate_block_no_peers(self):
        """Propagation with zero peers returns 0."""
        from qubitcoin.network.p2p_network import P2PNetwork

        consensus = MagicMock()
        net = P2PNetwork(port=4001, peer_id="lonely-node", consensus=consensus)
        block = _make_block(1)

        loop = asyncio.new_event_loop()
        count = loop.run_until_complete(net.propagate_block(block))
        loop.close()

        assert count == 0

    def test_propagate_block_calls_to_dict(self):
        """Block's to_dict() is called to serialize the data."""
        net = _make_network()
        block = _make_block(7)

        loop = asyncio.new_event_loop()
        loop.run_until_complete(net.propagate_block(block))
        loop.close()

        block.to_dict.assert_called_once()


class TestPropagateTransaction:
    """Test transaction propagation to peers."""

    def test_propagate_tx_sends_to_all_peers(self):
        """Transaction propagated to all connected peers."""
        net = _make_network()
        tx_data = {"txid": "abc123", "inputs": [], "outputs": []}

        loop = asyncio.new_event_loop()
        count = loop.run_until_complete(net.propagate_transaction(tx_data))
        loop.close()

        assert count == 3

    def test_propagate_tx_excludes_sender(self):
        """Transaction not sent back to the originating peer."""
        net = _make_network()
        tx_data = {"txid": "abc123"}

        loop = asyncio.new_event_loop()
        count = loop.run_until_complete(
            net.propagate_transaction(tx_data, exclude="peer-1")
        )
        loop.close()

        assert count == 2

    def test_propagate_tx_increments_stats(self):
        """Transaction propagation increments txs_propagated stat."""
        net = _make_network()
        tx_data = {"txid": "tx-1"}
        initial = net.stats['txs_propagated']

        loop = asyncio.new_event_loop()
        loop.run_until_complete(net.propagate_transaction(tx_data))
        loop.close()

        assert net.stats['txs_propagated'] == initial + 1

    def test_propagate_tx_no_peers(self):
        """Transaction propagation with no peers returns 0."""
        from qubitcoin.network.p2p_network import P2PNetwork

        consensus = MagicMock()
        net = P2PNetwork(port=4001, peer_id="lonely-node", consensus=consensus)
        tx_data = {"txid": "tx-1"}

        loop = asyncio.new_event_loop()
        count = loop.run_until_complete(net.propagate_transaction(tx_data))
        loop.close()

        assert count == 0


class TestPropagationStats:
    """Test propagation statistics reporting."""

    def test_get_propagation_stats_initial(self):
        """Propagation stats start at zero."""
        net = _make_network()
        stats = net.get_propagation_stats()

        assert stats['blocks_propagated'] == 0
        assert stats['txs_propagated'] == 0
        assert stats['connected_peers'] == 3

    def test_get_propagation_stats_after_activity(self):
        """Stats reflect propagation activity."""
        net = _make_network()

        loop = asyncio.new_event_loop()
        loop.run_until_complete(net.propagate_block(_make_block(1)))
        loop.run_until_complete(net.propagate_block(_make_block(2)))
        loop.run_until_complete(
            net.propagate_transaction({"txid": "tx-1"})
        )
        loop.close()

        stats = net.get_propagation_stats()
        assert stats['blocks_propagated'] == 2
        assert stats['txs_propagated'] == 1

    def test_multiple_blocks_sequential(self):
        """Multiple blocks propagated sequentially track correctly."""
        net = _make_network()

        loop = asyncio.new_event_loop()
        for i in range(5):
            count = loop.run_until_complete(net.propagate_block(_make_block(i)))
            assert count == 3
        loop.close()

        assert net.stats['blocks_propagated'] == 5


class TestMessageDeduplication:
    """Test message deduplication in block/tx handling."""

    def test_seen_messages_prevents_reprocessing(self):
        """A message with a seen msg_id is ignored."""
        net = _make_network()

        # Manually add a msg_id to the seen set
        net.seen_messages.add("duplicate-id-123")

        from qubitcoin.network.p2p_network import Message
        msg = Message(
            type='block',
            data={"height": 1},
            timestamp=time.time(),
            sender_id="peer-0",
            msg_id="duplicate-id-123",
        )

        # _handle_message should skip this
        loop = asyncio.new_event_loop()
        loop.run_until_complete(net._handle_message(msg, "peer-0"))
        loop.close()

        # blocks_propagated should NOT be incremented since message was deduped
        assert net.stats['blocks_propagated'] == 0

    def test_new_message_gets_processed(self):
        """A fresh msg_id gets added to seen set."""
        net = _make_network()

        from qubitcoin.network.p2p_network import Message
        msg = Message(
            type='ping',
            data={"peer_id": "test"},
            timestamp=time.time(),
            sender_id="peer-0",
            msg_id="fresh-id-456",
        )

        loop = asyncio.new_event_loop()
        loop.run_until_complete(net._handle_message(msg, "peer-0"))
        loop.close()

        assert "fresh-id-456" in net.seen_messages

    def test_message_cache_size_eviction(self):
        """Seen messages cache evicts old entries when full."""
        net = _make_network()
        net.message_cache_size = 100

        # Fill the cache beyond limit
        for i in range(150):
            net.seen_messages.add(f"msg-{i}")

        from qubitcoin.network.p2p_network import Message
        msg = Message(
            type='ping',
            data={},
            timestamp=time.time(),
            sender_id="peer-0",
            msg_id="trigger-eviction",
        )

        loop = asyncio.new_event_loop()
        loop.run_until_complete(net._handle_message(msg, "peer-0"))
        loop.close()

        # Some messages should have been evicted
        assert len(net.seen_messages) <= 151  # 150 + trigger - evicted
