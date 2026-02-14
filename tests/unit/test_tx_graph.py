"""Tests for transaction graph builder (Batch 16.2)."""
import pytest

from qubitcoin.qvm.tx_graph import TransactionGraph, TxEdge, GraphNode, MAX_HOPS


def _linear_graph(n: int = 5) -> TransactionGraph:
    """Create a linear chain: A→B→C→D→E."""
    g = TransactionGraph()
    for i in range(n - 1):
        g.add_transaction(f'addr_{i}', f'addr_{i+1}', 100.0, block_height=i)
    return g


class TestAddTransaction:
    def test_add_creates_edge(self):
        g = TransactionGraph()
        e = g.add_transaction('alice', 'bob', 50.0, 10)
        assert e.sender == 'alice'
        assert e.recipient == 'bob'

    def test_addresses_tracked(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 10.0, 0)
        assert g.has_address('a')
        assert g.has_address('b')

    def test_edge_count(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 10.0, 0)
        g.add_transaction('b', 'c', 20.0, 1)
        assert g.get_edge_count() == 2

    def test_node_count(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 10.0, 0)
        g.add_transaction('b', 'c', 20.0, 1)
        assert g.get_node_count() == 3


class TestBuildSubgraph:
    def test_seed_only(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 10.0, 0)
        sub = g.build_subgraph('a', max_hops=0)
        assert len(sub) == 1
        assert 'a' in sub

    def test_1_hop(self):
        g = _linear_graph(3)  # A→B→C
        sub = g.build_subgraph('addr_0', max_hops=1)
        assert 'addr_0' in sub
        assert 'addr_1' in sub
        assert 'addr_2' not in sub

    def test_2_hops(self):
        g = _linear_graph(4)  # A→B→C→D
        sub = g.build_subgraph('addr_0', max_hops=2)
        assert 'addr_2' in sub
        assert 'addr_3' not in sub

    def test_full_6_hops(self):
        g = _linear_graph(8)  # 8 nodes, 7 edges
        sub = g.build_subgraph('addr_0', max_hops=6)
        # Should reach addr_0 through addr_6 (7 nodes)
        assert len(sub) == 7

    def test_missing_seed_returns_empty(self):
        g = TransactionGraph()
        sub = g.build_subgraph('nonexistent')
        assert len(sub) == 0

    def test_hop_distance_correct(self):
        g = _linear_graph(4)
        sub = g.build_subgraph('addr_0', max_hops=3)
        assert sub['addr_0'].hop_distance == 0
        assert sub['addr_1'].hop_distance == 1
        assert sub['addr_2'].hop_distance == 2
        assert sub['addr_3'].hop_distance == 3

    def test_aggregates_amount(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 100.0, 0)
        g.add_transaction('a', 'b', 200.0, 1)
        sub = g.build_subgraph('a', max_hops=1)
        assert sub['b'].total_received == 300.0
        assert sub['b'].tx_count == 2

    def test_bidirectional_discovery(self):
        g = TransactionGraph()
        g.add_transaction('a', 'center', 10.0, 0)
        g.add_transaction('center', 'b', 20.0, 1)
        sub = g.build_subgraph('center', max_hops=1)
        assert 'a' in sub
        assert 'b' in sub

    def test_default_max_hops(self):
        assert MAX_HOPS == 6


class TestGetNeighbors:
    def test_direct_neighbors(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 10.0, 0)
        g.add_transaction('c', 'a', 20.0, 1)
        neighbors = g.get_neighbors('a')
        assert 'b' in neighbors
        assert 'c' in neighbors

    def test_no_neighbors(self):
        g = TransactionGraph()
        assert g.get_neighbors('unknown') == set()


class TestGetTransactions:
    def test_all_txs(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 10.0, 0)
        g.add_transaction('c', 'a', 20.0, 1)
        txs = g.get_transactions('a')
        assert len(txs) == 2

    def test_empty(self):
        g = TransactionGraph()
        assert g.get_transactions('nope') == []


class TestSerialization:
    def test_edge_to_dict(self):
        e = TxEdge(sender='a', recipient='b', amount=10.0, block_height=5, txid='tx1')
        d = e.to_dict()
        assert d['sender'] == 'a'
        assert d['txid'] == 'tx1'

    def test_node_to_dict(self):
        n = GraphNode(address='x', hop_distance=2, total_sent=100.0)
        d = n.to_dict()
        assert d['address'] == 'x'
        assert d['hop_distance'] == 2
