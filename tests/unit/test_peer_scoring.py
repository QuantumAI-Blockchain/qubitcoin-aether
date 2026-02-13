"""Unit tests for P2P peer scoring and eviction."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock


def _make_p2p():
    """Create a P2PNetwork with mock consensus (no actual network)."""
    from qubitcoin.network.p2p_network import P2PNetwork, Peer
    consensus = MagicMock()
    p2p = P2PNetwork(port=4001, peer_id='test_node', consensus=consensus)
    return p2p


def _add_peer(p2p, peer_id: str, score: int = 100):
    """Add a mock peer to the network."""
    from qubitcoin.network.p2p_network import Peer
    peer = Peer(
        peer_id=peer_id,
        host='127.0.0.1',
        port=4001,
        connected_at=datetime.now(),
        last_seen=datetime.now(),
        score=score,
    )
    p2p.connections[peer_id] = peer
    return peer


class TestPeerScoring:
    """Test peer reputation scoring."""

    def test_initial_score(self):
        from qubitcoin.network.p2p_network import Peer
        peer = Peer(peer_id='p1', host='127.0.0.1', port=4001,
                     connected_at=datetime.now(), last_seen=datetime.now())
        assert peer.score == 100

    def test_adjust_score_positive(self):
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=50)
        new_score = p2p.adjust_peer_score('p1', 10, 'valid block')
        assert new_score == 60

    def test_adjust_score_negative(self):
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=50)
        new_score = p2p.adjust_peer_score('p1', -20, 'invalid block')
        assert new_score == 30

    def test_score_clamped_at_zero(self):
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=5)
        new_score = p2p.adjust_peer_score('p1', -100)
        assert new_score == 0

    def test_score_clamped_at_100(self):
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=95)
        new_score = p2p.adjust_peer_score('p1', 50)
        assert new_score == 100

    def test_adjust_unknown_peer(self):
        p2p = _make_p2p()
        result = p2p.adjust_peer_score('nonexistent', 10)
        assert result == -1

    def test_penalize_peer(self):
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=80)
        new_score = p2p.penalize_peer('p1', severity=25, reason='spam')
        assert new_score == 55

    def test_penalize_with_positive_severity(self):
        """Penalty should always subtract (abs of severity)."""
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=80)
        new_score = p2p.penalize_peer('p1', severity=10)
        assert new_score == 70

    def test_reward_peer(self):
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=50)
        new_score = p2p.reward_peer('p1', amount=15, reason='valid tx')
        assert new_score == 65

    def test_reward_with_negative_amount(self):
        """Reward should always add (abs of amount)."""
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=50)
        new_score = p2p.reward_peer('p1', amount=-5)
        assert new_score == 55


class TestPeerEviction:
    """Test peer eviction based on score."""

    def test_evict_low_score_peer(self):
        import asyncio
        p2p = _make_p2p()
        _add_peer(p2p, 'good_peer', score=80)
        _add_peer(p2p, 'bad_peer', score=10)
        p2p._disconnect_peer = AsyncMock()
        evicted = asyncio.get_event_loop().run_until_complete(
            p2p.evict_low_score_peers(min_score=20)
        )
        assert 'bad_peer' in evicted
        assert 'good_peer' not in evicted

    def test_evict_no_one_above_threshold(self):
        import asyncio
        p2p = _make_p2p()
        _add_peer(p2p, 'p1', score=80)
        _add_peer(p2p, 'p2', score=50)
        p2p._disconnect_peer = AsyncMock()
        evicted = asyncio.get_event_loop().run_until_complete(
            p2p.evict_low_score_peers(min_score=20)
        )
        assert len(evicted) == 0

    def test_evict_multiple_bad_peers(self):
        import asyncio
        p2p = _make_p2p()
        _add_peer(p2p, 'bad1', score=5)
        _add_peer(p2p, 'bad2', score=10)
        _add_peer(p2p, 'good', score=90)
        p2p._disconnect_peer = AsyncMock()
        evicted = asyncio.get_event_loop().run_until_complete(
            p2p.evict_low_score_peers(min_score=15)
        )
        assert len(evicted) == 2
        assert 'good' not in evicted


class TestPeerSorting:
    """Test peer sorting by score."""

    def test_sort_descending(self):
        p2p = _make_p2p()
        _add_peer(p2p, 'low', score=10)
        _add_peer(p2p, 'mid', score=50)
        _add_peer(p2p, 'high', score=90)
        sorted_peers = p2p.get_peers_by_score(ascending=False)
        scores = [p['score'] for p in sorted_peers]
        assert scores == [90, 50, 10]

    def test_sort_ascending(self):
        p2p = _make_p2p()
        _add_peer(p2p, 'low', score=10)
        _add_peer(p2p, 'mid', score=50)
        _add_peer(p2p, 'high', score=90)
        sorted_peers = p2p.get_peers_by_score(ascending=True)
        scores = [p['score'] for p in sorted_peers]
        assert scores == [10, 50, 90]

    def test_empty_network(self):
        p2p = _make_p2p()
        sorted_peers = p2p.get_peers_by_score()
        assert sorted_peers == []
