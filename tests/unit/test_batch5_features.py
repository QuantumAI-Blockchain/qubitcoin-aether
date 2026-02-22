"""Tests for Batch 5 features: Reasoning archive, evidence accumulation,
Phi caching, KeterNode auto goal generation."""
import math
from unittest.mock import MagicMock, patch

import pytest


class TestReasoningArchive:
    """Test reasoning operation archival."""

    def test_archive_returns_zero_when_no_old_ops(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg = MagicMock()
        engine = ReasoningEngine(db, kg)
        # cutoff_block <= 0, should return 0
        result = engine.archive_old_reasoning(current_block=100, retain_blocks=50000)
        assert result == 0

    def test_archive_calls_db(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        db = MagicMock()
        kg = MagicMock()
        engine = ReasoningEngine(db, kg)

        mock_session = MagicMock()
        ctx_manager = MagicMock()
        ctx_manager.__enter__ = MagicMock(return_value=mock_session)
        ctx_manager.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = ctx_manager

        # No old ops found
        mock_session.execute.return_value.fetchall.return_value = []
        mock_session.execute.return_value.rowcount = 0

        result = engine.archive_old_reasoning(current_block=100000, retain_blocks=50000)
        assert result == 0
        assert db.get_session.called


class TestEvidenceAccumulation:
    """Test reference counting and confidence boost."""

    def _make_graph(self):
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph
        db = MagicMock()
        db.get_session = MagicMock(side_effect=Exception("skip DB"))
        with patch.object(KnowledgeGraph, '_load_from_db'):
            kg = KnowledgeGraph(db)
        return kg

    def test_touch_increments_reference_count(self):
        kg = self._make_graph()
        node = kg.add_node('observation', {'text': 'test'}, 0.9, 100)
        assert node.reference_count == 0
        kg.touch_node(node.node_id, 200)
        assert node.reference_count == 1
        kg.touch_node(node.node_id, 300)
        assert node.reference_count == 2

    def test_boost_referenced_nodes_no_references(self):
        kg = self._make_graph()
        kg.add_node('observation', {'text': 'test'}, 0.5, 100)
        boosted = kg.boost_referenced_nodes(min_references=5)
        assert boosted == 0

    def test_boost_referenced_nodes_with_references(self):
        kg = self._make_graph()
        node = kg.add_node('observation', {'text': 'test'}, 0.5, 100)
        # Simulate many references
        node.reference_count = 100
        boosted = kg.boost_referenced_nodes(min_references=5)
        assert boosted == 1
        assert node.confidence > 0.5

    def test_boost_capped_at_max(self):
        kg = self._make_graph()
        node = kg.add_node('observation', {'text': 'test'}, 0.99, 100)
        node.reference_count = 10000
        kg.boost_referenced_nodes(min_references=1)
        assert node.confidence <= 1.0

    def test_boost_formula(self):
        kg = self._make_graph()
        node = kg.add_node('observation', {'text': 'test'}, 0.5, 100)
        node.reference_count = 10
        # Expected boost: min(0.15, 0.01 * log(10)) ≈ min(0.15, 0.023) ≈ 0.023
        kg.boost_referenced_nodes(min_references=5)
        expected_boost = min(0.15, 0.01 * math.log(10))
        assert node.confidence == pytest.approx(0.5 + expected_boost, abs=0.001)


class TestPhiCaching:
    """Test Phi computation caching."""

    def _make_calculator(self, interval=10):
        from qubitcoin.aether.phi_calculator import PhiCalculator
        db = MagicMock()
        kg = MagicMock()
        kg.nodes = {1: MagicMock(node_type='observation', confidence=0.9,
                                  edges_out=[], edges_in=[])}
        kg.edges = []

        with patch.dict('os.environ', {'PHI_COMPUTE_INTERVAL': str(interval)}):
            calc = PhiCalculator(db, kg)
        return calc

    def test_no_caching_when_interval_1(self):
        calc = self._make_calculator(interval=1)
        assert calc._compute_interval == 1

    def test_cache_returns_result_within_interval(self):
        calc = self._make_calculator(interval=10)
        # Set up a cached result
        calc._last_full_result = {
            'phi_value': 1.5,
            'block_height': 100,
        }
        calc._last_computed_block = 100

        # Request for block 105 (within interval of 10)
        result = calc.compute_phi(105)
        assert result['phi_value'] == 1.5
        assert result['block_height'] == 105
        assert result.get('cached') is True

    def test_cache_invalidates_after_interval(self):
        calc = self._make_calculator(interval=10)
        calc._last_full_result = {
            'phi_value': 1.5,
            'block_height': 100,
        }
        calc._last_computed_block = 100

        # Request for block 110 (at interval boundary)
        # This should trigger a full recompute (v3 computes inline)
        result = calc.compute_phi(110)
        # Should have recomputed and updated the cached block
        assert calc._last_computed_block == 110

    def test_no_cache_on_first_call(self):
        calc = self._make_calculator(interval=10)
        assert calc._last_full_result is None
        # First call should do full computation (v3 computes inline)
        result = calc.compute_phi(50)
        assert 'phi_value' in result
        assert calc._last_computed_block == 50


class TestAutoGoalGeneration:
    """Test KeterNode auto goal generation."""

    def test_generates_learn_domain_goals(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        keter = KeterNode()
        domain_stats = {
            'quantum_physics': {'count': 500, 'avg_confidence': 0.8},
            'economics': {'count': 10, 'avg_confidence': 0.6},
            'biology': {'count': 50, 'avg_confidence': 0.7},
        }
        goals = keter.auto_generate_goals(domain_stats, contradiction_count=0)
        learn_goals = [g for g in goals if g['type'] == 'learn_domain']
        assert len(learn_goals) >= 2  # economics and biology both < 100
        domains = [g['domain'] for g in learn_goals]
        assert 'economics' in domains
        assert 'biology' in domains

    def test_generates_resolve_contradictions_goal(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        keter = KeterNode()
        goals = keter.auto_generate_goals({}, contradiction_count=8)
        resolve_goals = [g for g in goals if g['type'] == 'resolve_contradictions']
        assert len(resolve_goals) == 1
        assert resolve_goals[0]['priority'] == 'high'

    def test_generates_improve_confidence_goals(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        keter = KeterNode()
        domain_stats = {
            'quantum_physics': {'count': 200, 'avg_confidence': 0.3},
        }
        goals = keter.auto_generate_goals(domain_stats, contradiction_count=0)
        improve_goals = [g for g in goals if g['type'] == 'improve_confidence']
        assert len(improve_goals) == 1
        assert improve_goals[0]['domain'] == 'quantum_physics'

    def test_caps_at_10_auto_goals(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        keter = KeterNode()
        # Create many low-count domains
        domain_stats = {f'domain_{i}': {'count': 5, 'avg_confidence': 0.3}
                        for i in range(20)}
        goals = keter.auto_generate_goals(domain_stats, contradiction_count=3)
        assert len(goals) <= 10

    def test_preserves_external_goals(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        keter = KeterNode()
        keter._goals = [
            {'type': 'goal', 'priority': 'high', 'source': 'external'},
            {'type': 'goal', 'priority': 'low', 'source': 'external'},
        ]
        keter.auto_generate_goals({'x': {'count': 5, 'avg_confidence': 0.5}}, 0)
        external = [g for g in keter._goals if g.get('source') == 'external']
        assert len(external) == 2  # External goals preserved

    def test_replaces_old_auto_goals(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        keter = KeterNode()
        keter._goals = [
            {'type': 'learn_domain', 'domain': 'old', 'source': 'auto'},
        ]
        keter.auto_generate_goals({'new': {'count': 5, 'avg_confidence': 0.5}}, 0)
        old_goals = [g for g in keter._goals if g.get('domain') == 'old']
        assert len(old_goals) == 0  # Old auto-goals removed

    def test_no_goals_when_all_domains_large(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode
        keter = KeterNode()
        domain_stats = {
            'quantum_physics': {'count': 500, 'avg_confidence': 0.8},
            'mathematics': {'count': 300, 'avg_confidence': 0.7},
        }
        goals = keter.auto_generate_goals(domain_stats, contradiction_count=0)
        assert len(goals) == 0  # All domains above threshold


class TestAutoGenerateKeterGoalsWiring:
    """Test the AetherEngine._auto_generate_keter_goals wiring."""

    def test_auto_generate_called_from_engine(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        kg = MagicMock()
        kg.edges = []
        kg.get_domain_stats.return_value = {'test': {'count': 5, 'avg_confidence': 0.5}}
        engine = AetherEngine(db, kg, MagicMock(), MagicMock())

        from qubitcoin.aether.sephirot_nodes import KeterNode as KeterSephirah
        from qubitcoin.aether.sephirot import SephirahRole
        keter = KeterSephirah()
        engine._sephirot = {SephirahRole.KETER: keter}

        count = engine._auto_generate_keter_goals(1000)
        assert count > 0
        assert len(keter._goals) > 0
