"""Unit tests for knowledge graph, Phi calculator, and Aether Tree reasoning."""
import pytest
import math
from unittest.mock import MagicMock, patch


class TestKeterNode:
    """Test KeterNode data structures."""

    def test_import(self):
        from qubitcoin.aether.knowledge_graph import KeterNode
        assert KeterNode is not None

    def test_default_values(self):
        from qubitcoin.aether.knowledge_graph import KeterNode
        node = KeterNode()
        assert node.node_type == 'assertion'
        assert node.confidence == 0.5
        assert node.source_block == 0

    def test_calculate_hash(self):
        from qubitcoin.aether.knowledge_graph import KeterNode
        node = KeterNode(node_type='observation', content={'key': 'val'}, source_block=1)
        h = node.calculate_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_same_content_same_hash(self):
        from qubitcoin.aether.knowledge_graph import KeterNode
        n1 = KeterNode(node_type='axiom', content={'x': 1}, source_block=5)
        n2 = KeterNode(node_type='axiom', content={'x': 1}, source_block=5)
        assert n1.calculate_hash() == n2.calculate_hash()

    def test_different_content_different_hash(self):
        from qubitcoin.aether.knowledge_graph import KeterNode
        n1 = KeterNode(node_type='axiom', content={'x': 1}, source_block=5)
        n2 = KeterNode(node_type='axiom', content={'x': 2}, source_block=5)
        assert n1.calculate_hash() != n2.calculate_hash()

    def test_to_dict(self):
        from qubitcoin.aether.knowledge_graph import KeterNode
        node = KeterNode(node_id=1, node_type='inference', content={'data': True})
        d = node.to_dict()
        assert d['node_id'] == 1
        assert d['node_type'] == 'inference'
        assert 'edges_out' not in d
        assert 'edges_in' not in d


class TestKeterEdge:
    """Test KeterEdge data structure."""

    def test_import(self):
        from qubitcoin.aether.knowledge_graph import KeterEdge
        assert KeterEdge is not None

    def test_default_edge_type(self):
        from qubitcoin.aether.knowledge_graph import KeterEdge
        edge = KeterEdge(from_node_id=1, to_node_id=2)
        assert edge.edge_type == 'supports'
        assert edge.weight == 1.0

    def test_edge_types(self):
        from qubitcoin.aether.knowledge_graph import KeterEdge
        for et in ['supports', 'contradicts', 'derives', 'requires', 'refines']:
            edge = KeterEdge(from_node_id=1, to_node_id=2, edge_type=et)
            assert edge.edge_type == et


class TestPhiCalculator:
    """Test Phi (consciousness metric) calculator."""

    def test_import(self):
        from qubitcoin.aether.phi_calculator import PhiCalculator, PHI_THRESHOLD
        assert PhiCalculator is not None
        assert PHI_THRESHOLD == 3.0

    def test_empty_graph_zero_phi(self):
        """Empty knowledge graph yields Phi = 0."""
        from qubitcoin.aether.phi_calculator import PhiCalculator
        db = MagicMock()
        kg = MagicMock()
        kg.nodes = {}
        kg.edges = []
        calc = PhiCalculator(db, kg)
        result = calc.compute_phi(block_height=0)
        assert result['phi_value'] == 0.0
        assert result['above_threshold'] is False

    def test_single_node_zero_integration(self):
        """Single node can't have integration."""
        from qubitcoin.aether.phi_calculator import PhiCalculator
        from qubitcoin.aether.knowledge_graph import KeterNode
        db = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock()
        db.get_session.return_value.__exit__ = MagicMock()
        kg = MagicMock()
        node = KeterNode(node_id=1, confidence=0.8)
        kg.nodes = {1: node}
        kg.edges = []
        calc = PhiCalculator(db, kg)
        result = calc.compute_phi(block_height=1)
        assert result['integration_score'] == 0.0
        assert result['num_nodes'] == 1

    def test_phi_result_structure(self):
        """Phi result has all expected keys (empty graph returns zeros)."""
        from qubitcoin.aether.phi_calculator import PhiCalculator
        db = MagicMock()
        kg = MagicMock()
        kg.nodes = {}
        kg.edges = []
        calc = PhiCalculator(db, kg)
        result = calc.compute_phi()
        # Empty graph returns _empty_result which has these keys
        expected_keys = {
            'phi_value', 'phi_raw', 'phi_threshold', 'above_threshold',
            'integration_score', 'differentiation_score',
            'mip_score', 'redundancy_factor',
            'num_nodes', 'num_edges',
            'block_height', 'timestamp', 'phi_version',
            'convergence_stddev', 'convergence_status',
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_connected_graph_returns_result(self):
        """With MagicMock KG (no Rust KG), phi returns zeros gracefully."""
        from qubitcoin.aether.phi_calculator import PhiCalculator
        from qubitcoin.aether.knowledge_graph import KeterNode, KeterEdge

        db = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock()
        db.get_session.return_value.__exit__ = MagicMock()

        kg = MagicMock()
        nodes = {
            1: KeterNode(node_id=1, node_type='assertion', confidence=0.9),
            2: KeterNode(node_id=2, node_type='observation', confidence=0.7),
            3: KeterNode(node_id=3, node_type='inference', confidence=0.8),
        }
        edges = [
            KeterEdge(from_node_id=1, to_node_id=2, weight=1.0),
            KeterEdge(from_node_id=2, to_node_id=3, weight=1.0),
        ]
        kg.nodes = nodes
        kg.edges = edges

        calc = PhiCalculator(db, kg)
        result = calc.compute_phi(block_height=10)
        # Rust can't process MagicMock KG — returns zeros gracefully
        assert 'phi_value' in result
        assert result['phi_value'] == 0.0

    def test_rust_sole_compute_path(self):
        """Verify Python has no fallback compute methods (Rust only)."""
        from qubitcoin.aether.phi_calculator import PhiCalculator
        # These methods were removed — Rust handles all computation
        assert not hasattr(PhiCalculator, '_compute_integration')
        assert not hasattr(PhiCalculator, '_compute_differentiation')
        assert not hasattr(PhiCalculator, '_compute_mip')
        assert not hasattr(PhiCalculator, '_compute_iit_micro')

    def test_diverse_types_tracked_by_gates(self):
        """Gate system tracks node type diversity via MILESTONE_GATES."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        # Gate 2 requires >=4 node types with 50+ each
        gate2 = MILESTONE_GATES[1]
        assert gate2['name'] == 'Structural Diversity'
        stats_diverse = {
            'n_nodes': 2000,
            'node_type_counts': {
                'assertion': 100, 'observation': 100,
                'inference': 100, 'axiom': 100,
            },
            'integration_score': 0.5,
        }
        assert gate2['check'](stats_diverse) is True
        stats_homogeneous = {
            'n_nodes': 2000,
            'node_type_counts': {'assertion': 2000},
            'integration_score': 0.5,
        }
        assert gate2['check'](stats_homogeneous) is False



class TestReasoningEngine:
    """Test reasoning engine import and basic methods."""

    def test_import(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        assert ReasoningEngine is not None


class TestAetherProofOfThought:
    """Test Proof-of-Thought engine."""

    def test_import(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        assert AetherEngine is not None
