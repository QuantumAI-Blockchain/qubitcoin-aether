"""Unit tests for Aether Genesis initialization and validation.

Verifies that the AI layer is properly initialized from block 0:
- Knowledge graph seeded with genesis axioms
- First Phi measurement recorded (baseline Phi=0.0)
- Genesis consciousness event logged (system_birth)
"""
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_kg():
    """Create a mock knowledge graph that tracks add_node/add_edge calls."""
    from qubitcoin.aether.knowledge_graph import KeterNode
    import time

    kg = MagicMock()
    kg.nodes = {}
    kg._next_id = 1
    added_nodes = []
    added_edges = []

    def mock_add_node(node_type, content, confidence, source_block):
        node = KeterNode(
            node_id=kg._next_id,
            node_type=node_type,
            content=content,
            confidence=confidence,
            source_block=source_block,
            timestamp=time.time(),
        )
        kg._next_id += 1
        kg.nodes[node.node_id] = node
        added_nodes.append(node)
        return node

    def mock_add_edge(from_id, to_id, edge_type='supports'):
        added_edges.append((from_id, to_id, edge_type))

    kg.add_node = MagicMock(side_effect=mock_add_node)
    kg.add_edge = MagicMock(side_effect=mock_add_edge)
    kg._added_nodes = added_nodes
    kg._added_edges = added_edges
    return kg


class TestAetherGenesis:
    """Test Aether Genesis initialization."""

    def test_import(self):
        from qubitcoin.aether.genesis import AetherGenesis
        assert AetherGenesis is not None

    def test_genesis_creates_knowledge_nodes(self):
        """Genesis should seed 23 nodes: 1 genesis + 22 axioms (incl. premine + higgs)."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        result = genesis.initialize_genesis(genesis_block_hash='a' * 64)
        assert result['knowledge_nodes_created'] == 23  # 1 genesis + 22 axioms (incl. premine + higgs)
        assert kg.add_node.call_count == 23

    def test_genesis_nodes_are_axioms(self):
        """All genesis nodes should be of type 'axiom'."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        genesis.initialize_genesis()
        for node in kg._added_nodes:
            assert node.node_type == 'axiom'

    def test_genesis_nodes_full_confidence(self):
        """All genesis axioms should have confidence 1.0."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        genesis.initialize_genesis()
        for node in kg._added_nodes:
            assert node.confidence == 1.0

    def test_genesis_nodes_block_zero(self):
        """All genesis nodes should have source_block = 0."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        genesis.initialize_genesis()
        for node in kg._added_nodes:
            assert node.source_block == 0

    def test_genesis_has_edges(self):
        """Genesis node should derive into 22 axiom nodes (incl. premine + higgs)."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        genesis.initialize_genesis()
        assert kg.add_edge.call_count == 22
        for from_id, to_id, edge_type in kg._added_edges:
            assert edge_type == 'derives'

    def test_genesis_content_types(self):
        """Genesis should create genesis, economic, quantum, and consciousness axioms."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        genesis.initialize_genesis()
        content_types = {n.content.get('type') for n in kg._added_nodes}
        assert 'genesis' in content_types
        assert 'axiom_economic' in content_types
        assert 'axiom_quantum' in content_types
        assert 'axiom_consciousness' in content_types

    def test_genesis_phi_baseline(self):
        """Genesis result should record Phi=0.0 baseline."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        result = genesis.initialize_genesis()
        assert result['phi_baseline'] == 0.0

    def test_genesis_consciousness_event(self):
        """Genesis should record 'system_birth' consciousness event."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        result = genesis.initialize_genesis()
        assert result['consciousness_event'] == 'system_birth'

    def test_genesis_block_height_zero(self):
        """Genesis result should record block_height=0."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        result = genesis.initialize_genesis()
        assert result['block_height'] == 0

    def test_genesis_without_kg(self):
        """Genesis without knowledge graph should still succeed."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        genesis = AetherGenesis(db, knowledge_graph=None)
        result = genesis.initialize_genesis()
        assert result['knowledge_nodes_created'] == 0
        assert result['consciousness_event'] == 'system_birth'

    def test_genesis_custom_hash(self):
        """Genesis should use custom block hash when provided."""
        from qubitcoin.aether.genesis import AetherGenesis
        db = MagicMock()
        kg = _make_mock_kg()
        genesis = AetherGenesis(db, knowledge_graph=kg)
        genesis.initialize_genesis(genesis_block_hash='b' * 64)
        genesis_node = kg._added_nodes[0]
        assert genesis_node.content['block_hash'] == 'b' * 64
