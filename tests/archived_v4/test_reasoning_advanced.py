"""Unit tests for chain-of-thought reasoning and contradiction resolution."""
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_kg():
    """Create a mock knowledge graph with a few connected nodes."""
    from qubitcoin.aether.knowledge_graph import KeterNode, KeterEdge

    nodes = {}
    edges = []
    next_id = [100]

    def add_node(node_type='inference', content=None, confidence=0.5, source_block=0):
        nid = next_id[0]
        next_id[0] += 1
        node = KeterNode(
            node_id=nid,
            node_type=node_type,
            content=content or {},
            confidence=confidence,
            source_block=source_block,
        )
        nodes[nid] = node
        return node

    def add_edge(from_id, to_id, edge_type='supports', weight=1.0):
        edge = KeterEdge(from_node_id=from_id, to_node_id=to_id,
                         edge_type=edge_type, weight=weight)
        edges.append(edge)
        if from_id in nodes:
            nodes[from_id].edges_out.append(to_id)
        if to_id in nodes:
            nodes[to_id].edges_in.append(from_id)
        return edge

    def get_node(nid):
        return nodes.get(nid)

    def get_neighbors(nid, direction='out'):
        node = nodes.get(nid)
        if not node:
            return []
        ids = node.edges_out if direction == 'out' else node.edges_in
        return [nodes[i] for i in ids if i in nodes]

    kg = MagicMock()
    kg.nodes = nodes
    kg.edges = edges
    kg.add_node = MagicMock(side_effect=add_node)
    kg.add_edge = MagicMock(side_effect=add_edge)
    kg.get_node = MagicMock(side_effect=get_node)
    kg.get_neighbors = MagicMock(side_effect=get_neighbors)
    return kg, add_node, add_edge


class TestChainOfThought:
    """Test chain-of-thought multi-step reasoning."""

    def test_import(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        assert hasattr(ReasoningEngine, 'chain_of_thought')

    def test_empty_query(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, _, _ = _make_mock_kg()
        engine = ReasoningEngine(db, kg)
        result = engine.chain_of_thought([])
        assert result.success is False

    def test_invalid_node_ids(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, _, _ = _make_mock_kg()
        engine = ReasoningEngine(db, kg)
        result = engine.chain_of_thought([9999, 9998])
        assert result.success is False

    def test_single_node_chain(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, _ = _make_mock_kg()
        n1 = add_node('observation', {'val': 1}, 0.8, 1)
        engine = ReasoningEngine(db, kg)
        result = engine.chain_of_thought([n1.node_id])
        # Single node doesn't produce extra steps
        assert result.operation_type == 'chain_of_thought'
        assert len(result.chain) >= 1

    def test_multi_node_chain(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, add_edge = _make_mock_kg()
        n1 = add_node('observation', {'v': 1}, 0.8, 1)
        n2 = add_node('observation', {'v': 2}, 0.7, 2)
        n3 = add_node('inference', {'v': 3}, 0.6, 3)
        add_edge(n1.node_id, n3.node_id, 'derives')
        add_edge(n2.node_id, n3.node_id, 'derives')

        engine = ReasoningEngine(db, kg)
        result = engine.chain_of_thought([n1.node_id, n2.node_id], max_depth=3)
        assert result.operation_type == 'chain_of_thought'
        assert len(result.chain) >= 2

    def test_chain_follows_edges(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, add_edge = _make_mock_kg()
        n1 = add_node('observation', {'step': 0}, 0.9, 0)
        n2 = add_node('observation', {'step': 1}, 0.8, 1)
        n3 = add_node('inference', {'step': 2}, 0.7, 2)
        add_edge(n1.node_id, n2.node_id, 'derives')
        add_edge(n2.node_id, n3.node_id, 'derives')

        engine = ReasoningEngine(db, kg)
        result = engine.chain_of_thought([n1.node_id], max_depth=5)
        # Should explore n2 and n3 via edges
        visited_ids = {s.node_id for s in result.chain if s.node_id}
        assert n1.node_id in visited_ids

    def test_max_depth_limits(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, add_edge = _make_mock_kg()
        # Create a long chain
        nodes = []
        for i in range(10):
            n = add_node('observation', {'i': i}, 0.8, i)
            nodes.append(n)
            if i > 0:
                add_edge(nodes[i-1].node_id, n.node_id, 'derives')

        engine = ReasoningEngine(db, kg)
        result = engine.chain_of_thought([nodes[0].node_id], max_depth=2)
        assert result.operation_type == 'chain_of_thought'
        # With max_depth=2, shouldn't visit all 10 nodes
        visited = {s.node_id for s in result.chain if s.node_id}
        assert len(visited) < 10

    def test_recorded_in_operations(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, _ = _make_mock_kg()
        n1 = add_node('observation', {}, 0.8, 1)
        engine = ReasoningEngine(db, kg)
        engine.chain_of_thought([n1.node_id])
        stats = engine.get_stats()
        assert stats['total_operations'] >= 1


class TestContradictionResolution:
    """Test contradiction resolution between knowledge nodes."""

    def test_import(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        assert hasattr(ReasoningEngine, 'resolve_contradiction')

    def test_missing_nodes(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, _, _ = _make_mock_kg()
        engine = ReasoningEngine(db, kg)
        result = engine.resolve_contradiction(9999, 9998)
        assert result.success is False

    def test_higher_confidence_wins(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, _ = _make_mock_kg()
        strong = add_node('assertion', {'claim': 'A'}, 0.9, 1)
        weak = add_node('assertion', {'claim': 'not A'}, 0.3, 1)

        engine = ReasoningEngine(db, kg)
        result = engine.resolve_contradiction(strong.node_id, weak.node_id)
        assert result.success is True
        assert result.operation_type == 'contradiction_resolution'
        # Winner should be the higher confidence node
        resolution = result.chain[-1].content
        assert resolution['winner_id'] == strong.node_id
        assert resolution['loser_id'] == weak.node_id

    def test_loser_confidence_reduced(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, _ = _make_mock_kg()
        strong = add_node('assertion', {'claim': 'A'}, 0.9, 1)
        weak = add_node('assertion', {'claim': 'not A'}, 0.8, 1)
        original_conf = weak.confidence

        engine = ReasoningEngine(db, kg)
        engine.resolve_contradiction(strong.node_id, weak.node_id)
        # Loser's confidence should be reduced
        assert kg.nodes[weak.node_id].confidence < original_conf

    def test_supported_node_wins(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, add_edge = _make_mock_kg()
        # Node A has support, node B doesn't
        support1 = add_node('observation', {'data': 1}, 0.9, 1)
        support2 = add_node('observation', {'data': 2}, 0.8, 1)
        node_a = add_node('assertion', {'claim': 'A'}, 0.5, 2)
        node_b = add_node('assertion', {'claim': 'not A'}, 0.5, 2)
        add_edge(support1.node_id, node_a.node_id, 'supports')
        add_edge(support2.node_id, node_a.node_id, 'supports')

        engine = ReasoningEngine(db, kg)
        result = engine.resolve_contradiction(node_a.node_id, node_b.node_id)
        assert result.success is True
        resolution = result.chain[-1].content
        assert resolution['winner_id'] == node_a.node_id

    def test_contradiction_edge_created(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, _ = _make_mock_kg()
        n1 = add_node('assertion', {'c': 1}, 0.9, 1)
        n2 = add_node('assertion', {'c': 2}, 0.3, 1)

        engine = ReasoningEngine(db, kg)
        engine.resolve_contradiction(n1.node_id, n2.node_id)
        # add_edge should have been called with 'contradicts'
        kg.add_edge.assert_any_call(n1.node_id, n2.node_id, 'contradicts')

    def test_resolution_node_created(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, _ = _make_mock_kg()
        n1 = add_node('assertion', {'c': 1}, 0.7, 1)
        n2 = add_node('assertion', {'c': 2}, 0.6, 1)

        engine = ReasoningEngine(db, kg)
        result = engine.resolve_contradiction(n1.node_id, n2.node_id)
        assert result.conclusion_node_id is not None
        # Resolution node should exist
        assert result.conclusion_node_id in kg.nodes

    def test_recorded_in_stats(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg, add_node, _ = _make_mock_kg()
        n1 = add_node('assertion', {}, 0.9, 1)
        n2 = add_node('assertion', {}, 0.3, 1)

        engine = ReasoningEngine(db, kg)
        engine.resolve_contradiction(n1.node_id, n2.node_id)
        stats = engine.get_stats()
        assert 'contradiction_resolution' in stats['operation_types']
