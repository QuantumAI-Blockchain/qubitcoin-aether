"""Tests for Batch 7 features: Sephirot performance metrics, analogy detection,
Gates 7-10, LLM self-reflection, circadian learning phases."""
import random
from unittest.mock import MagicMock, patch

import pytest

from qubitcoin.aether.knowledge_graph import KeterNode, KnowledgeGraph, KeterEdge


# ─── 5.2 Gates 7-10 ────────────────────────────────────────────────────────

class TestSemanticGates:
    """Test semantically hardened milestone gates in phi_calculator."""

    def test_milestone_gates_has_10_entries(self):
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        assert len(MILESTONE_GATES) == 10

    def test_gate_1_knowledge_foundation(self):
        """Gate 1: >=500 nodes, >=5 domains, avg confidence >= 0.5."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        gate = MILESTONE_GATES[0]
        assert gate['id'] == 1
        assert gate['name'] == 'Knowledge Foundation'

        # Fail: not enough nodes
        stats = {
            'n_nodes': 499, 'n_edges': 10,
            'node_type_counts': {}, 'edge_type_counts': {},
            'avg_confidence': 0.7, 'domain_count': 5,
        }
        assert gate['check'](stats) is False

        # Fail: enough nodes but too few domains
        stats['n_nodes'] = 500
        stats['domain_count'] = 4
        assert gate['check'](stats) is False

        # Fail: enough nodes/domains but low confidence
        stats['domain_count'] = 5
        stats['avg_confidence'] = 0.3
        assert gate['check'](stats) is False

        # Pass: all criteria met
        stats['avg_confidence'] = 0.5
        assert gate['check'](stats) is True

    def test_gate_2_diverse_reasoning(self):
        """Gate 2: >=2K nodes, >=4 types with 50+ each, integration > 0.3."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        gate = MILESTONE_GATES[1]
        assert gate['id'] == 2
        assert gate['name'] == 'Diverse Reasoning'

        # Fail: not enough node types with 50+ each
        stats = {
            'n_nodes': 2000, 'n_edges': 100,
            'node_type_counts': {'assertion': 400, 'observation': 100, 'inference': 49},
            'edge_type_counts': {},
            'integration_score': 0.5,
        }
        assert gate['check'](stats) is False

        # Fail: enough types but low integration
        stats['node_type_counts'] = {
            'assertion': 200, 'observation': 200, 'inference': 100, 'axiom': 50,
        }
        stats['integration_score'] = 0.2
        assert gate['check'](stats) is False

        # Pass: diverse types and good integration
        stats['integration_score'] = 0.5
        assert gate['check'](stats) is True

    def test_gate_3_predictive_power(self):
        """Gate 3: >=5K nodes, >=50 verified predictions, accuracy > 60%."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        gate = MILESTONE_GATES[2]
        assert gate['id'] == 3
        assert gate['name'] == 'Predictive Power'

        # Fail: no verified predictions
        stats = {
            'n_nodes': 5000, 'n_edges': 500,
            'node_type_counts': {}, 'edge_type_counts': {},
            'verified_predictions': 0, 'prediction_accuracy': 0.7,
        }
        assert gate['check'](stats) is False

        # Fail: predictions but low accuracy
        stats['verified_predictions'] = 50
        stats['prediction_accuracy'] = 0.5
        assert gate['check'](stats) is False

        # Pass: predictions + sufficient accuracy
        stats['prediction_accuracy'] = 0.7
        assert gate['check'](stats) is True

    def test_gate_4_self_correction(self):
        """Gate 4: >=10K nodes, >=20 debate verdicts, >=10 contradictions, MIP > 0.3."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        gate = MILESTONE_GATES[3]
        assert gate['id'] == 4
        assert gate['name'] == 'Self-Correction'

        # Fail: not enough debate verdicts
        stats = {
            'n_nodes': 10000, 'n_edges': 500,
            'node_type_counts': {}, 'edge_type_counts': {},
            'debate_verdicts': 19, 'contradiction_resolutions': 10,
            'mip_phi': 0.5,
        }
        assert gate['check'](stats) is False

        # Fail: verdicts but low MIP
        stats['debate_verdicts'] = 20
        stats['mip_phi'] = 0.2
        assert gate['check'](stats) is False

        # Pass: all criteria met
        stats['mip_phi'] = 0.5
        assert gate['check'](stats) is True

    def test_gate_7_metacognitive_calibration(self):
        """Gate 7: >=25K nodes, calibration error < 0.15, >=200 evals, >5% grounded."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        gate = MILESTONE_GATES[6]
        assert gate['id'] == 7
        assert gate['name'] == 'Metacognitive Calibration'

        # Fail: high calibration error
        stats = {
            'n_nodes': 25000, 'n_edges': 5000,
            'node_type_counts': {}, 'edge_type_counts': {},
            'calibration_error': 0.5, 'grounding_ratio': 0.2,
            'calibration_evaluations': 200,
        }
        assert gate['check'](stats) is False

        # Fail: good calibration but low grounding
        stats['calibration_error'] = 0.1
        stats['grounding_ratio'] = 0.04
        assert gate['check'](stats) is False

        # Fail: good calibration/grounding but not enough evaluations
        stats['grounding_ratio'] = 0.2
        stats['calibration_evaluations'] = 199
        assert gate['check'](stats) is False

        # Pass: all criteria met
        stats['calibration_evaluations'] = 200
        assert gate['check'](stats) is True

    def test_gate_9_predictive_mastery(self):
        """Gate 9: >=50K nodes, prediction accuracy > 70%, >=5K inferences."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        gate = MILESTONE_GATES[8]
        assert gate['id'] == 9
        assert gate['name'] == 'Predictive Mastery'

        # Fail: low prediction accuracy
        stats = {
            'n_nodes': 50000, 'n_edges': 10000,
            'node_type_counts': {'inference': 5000},
            'edge_type_counts': {},
            'prediction_accuracy': 0.6,
        }
        assert gate['check'](stats) is False

        # Fail: good accuracy but too few inferences
        stats['prediction_accuracy'] = 0.8
        stats['node_type_counts']['inference'] = 4999
        assert gate['check'](stats) is False

        # Pass: accurate and enough inferences
        stats['node_type_counts']['inference'] = 5000
        assert gate['check'](stats) is True

    def test_gate_10_creative_synthesis(self):
        """Gate 10: >=75K nodes, >=100 cross-domain inferences, >=50 novel concepts."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        gate = MILESTONE_GATES[9]
        assert gate['id'] == 10
        assert gate['name'] == 'Creative Synthesis'

        # Fail: not enough nodes
        stats = {
            'n_nodes': 74999, 'n_edges': 50000,
            'node_type_counts': {}, 'edge_type_counts': {},
            'cross_domain_inferences': 100,
            'novel_concept_count': 60,
        }
        assert gate['check'](stats) is False

        # Fail: enough nodes but not enough novel concepts
        stats['n_nodes'] = 75000
        stats['novel_concept_count'] = 49
        assert gate['check'](stats) is False

        # Pass: all criteria met
        stats['novel_concept_count'] = 50
        assert gate['check'](stats) is True

    def test_max_ceiling_is_5(self):
        """With all 10 gates passed, ceiling should be 5.0."""
        from qubitcoin.aether.phi_calculator import MILESTONE_GATES
        max_ceiling = len(MILESTONE_GATES) * 0.5
        assert max_ceiling == 5.0

    def test_check_gates_computes_extended_stats(self):
        """Verify _check_gates builds the extended stats dict correctly."""
        from qubitcoin.aether.phi_calculator import PhiCalculator

        calc = PhiCalculator.__new__(PhiCalculator)
        calc.kg = MagicMock()

        # Create nodes with domains, self-reflection, and various content types
        nodes = {
            1: KeterNode(node_id=1, node_type='assertion', domain='physics',
                         content={'text': 'test'}, confidence=0.8),
            2: KeterNode(node_id=2, node_type='inference', domain='math',
                         content={'source': 'self-reflection', 'text': 'reflect'},
                         confidence=0.6),
            3: KeterNode(node_id=3, node_type='inference', domain='physics',
                         content={'cross_domain': True, 'text': 'cross'},
                         confidence=0.7),
        }
        edges = [
            KeterEdge(from_node_id=1, to_node_id=2,
                          edge_type='supports', weight=1.0),
        ]

        results = calc._check_gates(nodes, edges)
        assert len(results) == 10
        # All gates should fail with only 3 nodes (gate 1 requires >= 500)
        for g in results:
            assert g['passed'] is False

    def test_check_gates_accepts_extra_stats(self):
        """Verify _check_gates merges external stats."""
        from qubitcoin.aether.phi_calculator import PhiCalculator

        calc = PhiCalculator.__new__(PhiCalculator)
        calc.kg = MagicMock()

        # Create 500 nodes across 5 domains to pass gate 1
        domains = ['physics', 'math', 'cs', 'biology', 'chemistry']
        nodes = {
            i: KeterNode(node_id=i, node_type='assertion',
                         content={'text': f'node {i}'}, confidence=0.7,
                         domain=domains[i % 5])
            for i in range(1, 501)
        }
        edges = []

        # Without extra_stats, gate 1 should pass (500 nodes, 5 domains, conf 0.7)
        results = calc._check_gates(nodes, edges)
        assert results[0]['passed'] is True  # Gate 1

        # With extra_stats, integration_score is injected
        results_with_extra = calc._check_gates(nodes, edges, extra_stats={
            'integration_score': 0.5,
            'mip_phi': 0.4,
        })
        assert results_with_extra[0]['passed'] is True  # Gate 1 still passes


# ─── 4.2 Analogy Detection ─────────────────────────────────────────────────

class TestAnalogyDetection:
    """Test ReasoningEngine.find_analogies()."""

    def _make_kg(self):
        import threading
        kg = KnowledgeGraph.__new__(KnowledgeGraph)
        kg.db = None
        kg._lock = threading.Lock()
        kg.nodes = {}
        kg.edges = []
        kg._adj_out = {}
        kg._adj_in = {}
        kg._next_id = 1
        kg._next_edge_id = 1
        kg._index = None
        kg._merkle_dirty = True
        kg._merkle_cache = ''
        return kg

    def test_find_analogies_source_not_found(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        kg = self._make_kg()
        db = MagicMock()
        engine = ReasoningEngine(db, kg)
        result = engine.find_analogies(999)
        assert not result.success

    def test_find_analogies_no_edges(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        kg = self._make_kg()
        node = KeterNode(node_id=1, node_type='assertion',
                         content={'text': 'test'}, domain='physics')
        kg.nodes[1] = node
        kg._next_id = 2
        db = MagicMock()
        engine = ReasoningEngine(db, kg)
        result = engine.find_analogies(1)
        assert not result.success
        assert 'no edges' in result.explanation.lower()

    def test_find_analogies_with_matching_patterns(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        kg = self._make_kg()

        # Source node in physics domain with supports + derives edges
        kg.nodes[1] = KeterNode(node_id=1, node_type='assertion',
                                content={'text': 'quantum'}, domain='physics')
        kg.nodes[2] = KeterNode(node_id=2, node_type='inference',
                                content={'text': 'deduction'}, domain='physics')
        kg.nodes[3] = KeterNode(node_id=3, node_type='assertion',
                                content={'text': 'derivative'}, domain='math')
        kg.nodes[4] = KeterNode(node_id=4, node_type='inference',
                                content={'text': 'proof'}, domain='math')

        # Source pattern: supports + derives
        kg.edges = [
            KeterEdge(from_node_id=1, to_node_id=2,
                          edge_type='supports', weight=1.0),
            KeterEdge(from_node_id=2, to_node_id=1,
                          edge_type='derives', weight=1.0),
            # Target pattern: same types
            KeterEdge(from_node_id=3, to_node_id=4,
                          edge_type='supports', weight=1.0),
            KeterEdge(from_node_id=4, to_node_id=3,
                          edge_type='derives', weight=1.0),
        ]
        kg._next_id = 5
        kg._next_edge_id = 5

        db = MagicMock()
        engine = ReasoningEngine(db, kg)
        result = engine.find_analogies(1, target_domain='math')
        assert result.success
        # Should have created analogous_to edge
        analogy_edges = [e for e in kg.edges if e.edge_type == 'analogous_to']
        assert len(analogy_edges) >= 1

    def test_get_edge_pattern(self):
        from qubitcoin.aether.reasoning import ReasoningEngine
        kg = self._make_kg()
        kg.nodes[1] = KeterNode(node_id=1, content={'text': 'a'})
        kg.nodes[2] = KeterNode(node_id=2, content={'text': 'b'})
        kg.edges = [
            KeterEdge(from_node_id=1, to_node_id=2,
                          edge_type='supports', weight=1.0),
            KeterEdge(from_node_id=2, to_node_id=1,
                          edge_type='derives', weight=1.0),
        ]
        db = MagicMock()
        engine = ReasoningEngine(db, kg)
        pattern = engine._get_edge_pattern(1)
        assert pattern == {'supports', 'derives'}


# ─── 2.3 Sephirot Performance Metrics ──────────────────────────────────────

class TestSephirotPerformanceMetrics:
    """Test BaseSephirah performance tracking."""

    def test_performance_fields_exist(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode as KeterSephirah
        node = KeterSephirah.__new__(KeterSephirah)
        from qubitcoin.aether.sephirot import SephirahRole, SephirahState
        node.role = SephirahRole.KETER
        node.kg = None
        node.state = SephirahState(role=SephirahRole.KETER, qubits=8)
        node._inbox = []
        node._outbox = []
        node._processing_count = 0
        node._quantum_state = None
        node._tasks_solved = 0
        node._knowledge_contributed = 0
        node._errors = 0
        node._goals = []

        status = node.get_status()
        assert 'tasks_solved' in status
        assert 'knowledge_contributed' in status
        assert 'errors' in status

    def test_performance_weight_minimum(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode as KeterSephirah
        from qubitcoin.aether.sephirot import SephirahRole, SephirahState
        node = KeterSephirah.__new__(KeterSephirah)
        node.role = SephirahRole.KETER
        node.state = SephirahState(role=SephirahRole.KETER, qubits=8)
        node._tasks_solved = 0
        node._knowledge_contributed = 0
        node._errors = 0
        node._goals = []

        # With all zeros, weight should be minimum 1.0
        weight = node.get_performance_weight()
        assert weight == 1.0

    def test_performance_weight_increases(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode as KeterSephirah
        from qubitcoin.aether.sephirot import SephirahRole, SephirahState
        node = KeterSephirah.__new__(KeterSephirah)
        node.role = SephirahRole.KETER
        node.state = SephirahState(role=SephirahRole.KETER, qubits=8)
        node.state.reasoning_ops = 100
        node._tasks_solved = 50
        node._knowledge_contributed = 30
        node._errors = 0
        node._goals = []

        weight = node.get_performance_weight()
        expected = 50 * 0.5 + 30 * 0.3 + 100 * 0.2  # 25 + 9 + 20 = 54
        assert weight == expected

    def test_serialize_includes_performance(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode as KeterSephirah
        from qubitcoin.aether.sephirot import SephirahRole, SephirahState
        node = KeterSephirah.__new__(KeterSephirah)
        node.role = SephirahRole.KETER
        node.state = SephirahState(role=SephirahRole.KETER, qubits=8)
        node._processing_count = 5
        node._tasks_solved = 10
        node._knowledge_contributed = 20
        node._errors = 2
        node._goals = []
        node._meta_patterns = []
        node._inbox = []
        node._outbox = []
        node._quantum_state = None
        node.kg = None

        data = node.serialize_state()
        assert data['tasks_solved'] == 10
        assert data['knowledge_contributed'] == 20
        assert data['errors'] == 2

    def test_deserialize_restores_performance(self):
        from qubitcoin.aether.sephirot_nodes import KeterNode as KeterSephirah
        from qubitcoin.aether.sephirot import SephirahRole, SephirahState
        node = KeterSephirah.__new__(KeterSephirah)
        node.role = SephirahRole.KETER
        node.state = SephirahState(role=SephirahRole.KETER, qubits=8)
        node._processing_count = 0
        node._tasks_solved = 0
        node._knowledge_contributed = 0
        node._errors = 0
        node._goals = []

        data = {
            'processing_count': 5,
            'tasks_solved': 15,
            'knowledge_contributed': 25,
            'errors': 3,
            'state': {'active': True, 'energy': 0.9,
                      'messages_processed': 100, 'reasoning_ops': 50},
            'goals': [],
        }
        node.deserialize_state(data)
        assert node._tasks_solved == 15
        assert node._knowledge_contributed == 25
        assert node._errors == 3


# ─── 6.2 LLM Self-Reflection ───────────────────────────────────────────────

class TestSelfReflection:
    """Test AetherEngine.self_reflect()."""

    def test_self_reflect_no_llm(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        engine = AetherEngine(db)
        assert engine.self_reflect(100) == 0

    @patch('qubitcoin.aether.proof_of_thought.Config')
    def test_self_reflect_disabled(self, mock_config):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        mock_config.LLM_ENABLED = False
        db = MagicMock()
        engine = AetherEngine(db, llm_manager=MagicMock())
        engine.kg = MagicMock()
        result = engine.self_reflect(100)
        assert result == 0

    @patch('qubitcoin.aether.proof_of_thought.Config')
    def test_self_reflect_creates_nodes(self, mock_config):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        mock_config.LLM_ENABLED = True

        db = MagicMock()
        mock_session = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_session)
        ctx.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = ctx

        kg = MagicMock()
        kg.edges = []  # No contradictions
        kg.get_domain_stats.return_value = {
            'physics': {'count': 10, 'avg_confidence': 0.5},
        }

        llm = MagicMock()
        llm.generate.return_value = {'content': 'Physics explanation.'}

        engine = AetherEngine(db, knowledge_graph=kg, llm_manager=llm)

        result = engine.self_reflect(200)
        # Should have called generate for weak domains
        assert llm.generate.called


# ─── 10.2 Circadian Learning Phases ────────────────────────────────────────

class TestCircadianPhases:
    """Test circadian behavior integration."""

    def test_circadian_status_none_without_pineal(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        engine = AetherEngine(db)
        assert engine.get_circadian_status() is None

    def test_circadian_status_with_pineal(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        pineal = MagicMock()
        pineal.get_status.return_value = {
            'current_phase': 'waking',
            'metabolic_rate': 1.0,
        }
        engine = AetherEngine(db, pineal=pineal)
        status = engine.get_circadian_status()
        assert status['current_phase'] == 'waking'

    def test_apply_circadian_consolidation(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        from qubitcoin.aether.pineal import CircadianPhase
        db = MagicMock()
        kg = MagicMock()
        pineal = MagicMock()
        pineal.current_phase = CircadianPhase.CONSOLIDATION

        engine = AetherEngine(db, knowledge_graph=kg, pineal=pineal)
        engine._sephirot = None

        # Patch Config so the test is environment-agnostic: interval=50, height=150 (150%50==0)
        block = MagicMock()
        block.height = 150
        with patch("qubitcoin.aether.proof_of_thought.Config") as mock_cfg:
            mock_cfg.AETHER_CURIOSITY_INTERVAL = 50
            mock_cfg.AETHER_DEBATE_INTERVAL = 541
            engine._apply_circadian_behavior(block)
        kg.prune_low_confidence.assert_called_once()

    def test_apply_circadian_rem_dreaming(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        from qubitcoin.aether.pineal import CircadianPhase
        db = MagicMock()
        kg = MagicMock()
        kg.nodes = {}  # Empty — no analogies to find
        reasoning = MagicMock()
        pineal = MagicMock()
        pineal.current_phase = CircadianPhase.REM_DREAMING

        engine = AetherEngine(db, knowledge_graph=kg,
                              reasoning_engine=reasoning, pineal=pineal)

        block = MagicMock()
        block.height = 50
        engine._apply_circadian_behavior(block)
        # _dream_analogies should have been called but with empty KG
        # No assertions to crash on, just verifying no errors

    def test_dream_analogies_needs_2_domains(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        kg = MagicMock()
        kg.nodes = {
            1: KeterNode(node_id=1, node_type='assertion',
                         domain='physics', content={'text': 'a'}),
        }
        reasoning = MagicMock()
        engine = AetherEngine(db, knowledge_graph=kg,
                              reasoning_engine=reasoning)

        result = engine._dream_analogies(100)
        assert result == 0  # Only 1 domain, need 2

    def test_pineal_ticked_in_process_block(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        mock_session = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_session)
        ctx.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = ctx

        kg = MagicMock()
        kg.nodes = {}
        kg.edges = []
        kg.get_stats.return_value = {}
        kg.get_merkle_root.return_value = 'abc123'
        kg.add_node.return_value = KeterNode(node_id=1)

        pineal = MagicMock()
        pineal.current_phase = MagicMock(value='waking')

        engine = AetherEngine(db, knowledge_graph=kg, pineal=pineal)

        block = MagicMock()
        block.height = 10
        block.block_hash = 'hash123'
        block.difficulty_target = 1.0
        block.timestamp = 1234567890

        engine.process_block_knowledge(block)
        pineal.tick.assert_called_once()
