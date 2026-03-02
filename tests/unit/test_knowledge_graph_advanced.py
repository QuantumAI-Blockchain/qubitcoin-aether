"""Unit tests for knowledge graph pruning, query API, and advanced operations."""
import pytest
from unittest.mock import MagicMock


def _make_test_kg():
    """Create a knowledge graph with test data (no DB)."""
    from qubitcoin.aether.knowledge_graph import KnowledgeGraph
    db = MagicMock()
    db.get_session.side_effect = Exception("No DB in test")
    import threading
    kg = KnowledgeGraph.__new__(KnowledgeGraph)
    kg.db = db
    kg._lock = threading.Lock()
    kg.nodes = {}
    kg.edges = []
    kg._adj_out = {}
    kg._adj_in = {}
    kg._next_id = 1
    kg._merkle_dirty = True
    kg._merkle_cache = ''
    return kg


class TestPruneLowConfidence:
    """Test knowledge graph node pruning."""

    def test_prune_removes_low_confidence(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        kg.add_node('observation', {'a': 1}, 0.05, 1)
        kg.add_node('observation', {'b': 2}, 0.5, 2)
        kg.add_node('observation', {'c': 3}, 0.9, 3)

        removed = kg.prune_low_confidence(threshold=0.1)
        assert removed == 1
        assert len(kg.nodes) == 2

    def test_prune_protects_axioms(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        kg.add_node('axiom', {'principle': True}, 0.01, 0)
        kg.add_node('observation', {'data': 1}, 0.01, 1)

        removed = kg.prune_low_confidence(threshold=0.1)
        assert removed == 1  # Only observation removed
        remaining_types = [n.node_type for n in kg.nodes.values()]
        assert 'axiom' in remaining_types

    def test_prune_custom_protected_types(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        kg.add_node('assertion', {'x': 1}, 0.05, 0)
        kg.add_node('observation', {'y': 2}, 0.05, 1)

        removed = kg.prune_low_confidence(threshold=0.1, protect_types={'assertion', 'axiom'})
        assert removed == 1
        remaining_types = [n.node_type for n in kg.nodes.values()]
        assert 'assertion' in remaining_types

    def test_prune_removes_edges(self):
        from qubitcoin.aether.knowledge_graph import KeterEdge
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        n1 = kg.add_node('observation', {}, 0.05, 0)
        n2 = kg.add_node('observation', {}, 0.9, 1)
        # Add edge manually (including adjacency indices used by prune)
        edge = KeterEdge(from_node_id=n1.node_id, to_node_id=n2.node_id)
        kg.edges.append(edge)
        kg.nodes[n1.node_id].edges_out.append(n2.node_id)
        kg.nodes[n2.node_id].edges_in.append(n1.node_id)
        kg._adj_out.setdefault(n1.node_id, []).append(edge)
        kg._adj_in.setdefault(n2.node_id, []).append(edge)

        kg.prune_low_confidence(threshold=0.1)
        assert len(kg.edges) == 0
        assert n1.node_id not in kg.nodes[n2.node_id].edges_in

    def test_prune_nothing_above_threshold(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        kg.add_node('observation', {}, 0.5, 0)
        kg.add_node('observation', {}, 0.8, 1)

        removed = kg.prune_low_confidence(threshold=0.1)
        assert removed == 0
        assert len(kg.nodes) == 2


class TestFindByType:
    """Test node lookup by type."""

    def test_find_matching_type(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        kg.add_node('observation', {}, 0.5, 0)
        kg.add_node('inference', {}, 0.7, 1)
        kg.add_node('observation', {}, 0.9, 2)

        results = kg.find_by_type('observation')
        assert len(results) == 2
        # Should be sorted by confidence descending
        assert results[0].confidence >= results[1].confidence

    def test_find_no_match(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        kg.add_node('observation', {}, 0.5, 0)

        results = kg.find_by_type('axiom')
        assert len(results) == 0

    def test_find_with_limit(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        for i in range(10):
            kg.add_node('observation', {}, 0.5, i)

        results = kg.find_by_type('observation', limit=3)
        assert len(results) == 3


class TestFindByContent:
    """Test node lookup by content field."""

    def test_find_matching_content(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        kg.add_node('observation', {'type': 'block_observation', 'height': 10}, 0.9, 10)
        kg.add_node('observation', {'type': 'quantum_observation', 'energy': 1.5}, 0.8, 11)
        kg.add_node('observation', {'type': 'block_observation', 'height': 12}, 0.7, 12)

        results = kg.find_by_content('type', 'block_observation')
        assert len(results) == 2

    def test_find_no_match(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        kg.add_node('observation', {'type': 'foo'}, 0.5, 0)

        results = kg.find_by_content('type', 'bar')
        assert len(results) == 0


class TestFindRecent:
    """Test recent node retrieval."""

    def test_find_recent_ordered(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        for i in range(5):
            kg.add_node('observation', {'i': i}, 0.5, i)

        recent = kg.find_recent(3)
        assert len(recent) == 3
        assert recent[0].source_block == 4
        assert recent[1].source_block == 3
        assert recent[2].source_block == 2

    def test_find_recent_empty(self):
        kg = _make_test_kg()
        recent = kg.find_recent(10)
        assert len(recent) == 0


class TestGetEdgeTypesForNode:
    """Test edge type grouping."""

    def test_edge_types(self):
        from qubitcoin.aether.knowledge_graph import KeterEdge
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        n1 = kg.add_node('observation', {}, 0.5, 0)
        n2 = kg.add_node('inference', {}, 0.7, 1)
        n3 = kg.add_node('observation', {}, 0.6, 2)

        e1 = KeterEdge(from_node_id=n1.node_id, to_node_id=n2.node_id, edge_type='derives')
        e2 = KeterEdge(from_node_id=n3.node_id, to_node_id=n1.node_id, edge_type='supports')
        kg.edges = [e1, e2]
        kg._adj_out.setdefault(n1.node_id, []).append(e1)
        kg._adj_in.setdefault(n2.node_id, []).append(e1)
        kg._adj_out.setdefault(n3.node_id, []).append(e2)
        kg._adj_in.setdefault(n1.node_id, []).append(e2)

        result = kg.get_edge_types_for_node(n1.node_id)
        assert 'out_derives' in result
        assert n2.node_id in result['out_derives']
        assert 'in_supports' in result
        assert n3.node_id in result['in_supports']

    def test_no_edges(self):
        kg = _make_test_kg()
        kg.add_node = KnowledgeGraph_add_node_no_db(kg)
        n1 = kg.add_node('observation', {}, 0.5, 0)
        result = kg.get_edge_types_for_node(n1.node_id)
        assert result == {}


# Helper: add_node without DB persistence
def KnowledgeGraph_add_node_no_db(kg):
    """Create a closure that adds nodes without DB."""
    import time as _time
    from qubitcoin.aether.knowledge_graph import KeterNode

    def add_node(node_type, content, confidence, source_block):
        node = KeterNode(
            node_id=kg._next_id,
            node_type=node_type,
            content=content,
            confidence=max(0.0, min(1.0, confidence)),
            source_block=source_block,
            timestamp=_time.time(),
        )
        node.content_hash = node.calculate_hash()
        kg._next_id += 1
        kg.nodes[node.node_id] = node
        return node

    return add_node
