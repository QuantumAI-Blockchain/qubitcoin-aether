"""Tests for Batch 4 features: Knowledge decay, domain clustering,
KG load verification, /aether/mind endpoint."""
import json
from unittest.mock import MagicMock, patch

import pytest


class TestKnowledgeDecay:
    """Test effective_confidence with time-decay."""

    def _make_node(self, **kwargs):
        from qubitcoin.aether.knowledge_graph import KeterNode
        defaults = {
            'node_id': 1,
            'node_type': 'observation',
            'content': {'text': 'test'},
            'confidence': 0.9,
            'source_block': 100,
            'last_referenced_block': 100,
        }
        defaults.update(kwargs)
        return KeterNode(**defaults)

    def test_no_decay_at_creation_block(self):
        node = self._make_node(source_block=100, last_referenced_block=100)
        eff = node.effective_confidence(current_block=100)
        assert eff == pytest.approx(0.9, abs=0.01)

    def test_decay_after_halflife(self):
        node = self._make_node(source_block=100, last_referenced_block=100, confidence=1.0)
        # At exactly halflife blocks later, exponential decay = 2^(-1) = 0.5
        with patch('qubitcoin.config.Config') as mock_config:
            mock_config.CONFIDENCE_DECAY_HALFLIFE = 100000
            mock_config.CONFIDENCE_DECAY_FLOOR = 0.3
            eff = node.effective_confidence(current_block=100100)
            # age=100000, decay = max(0.3, 2^(-1)) = max(0.3, 0.5) = 0.5
            assert eff == pytest.approx(0.5, abs=0.01)

    def test_decay_partial(self):
        node = self._make_node(source_block=100, last_referenced_block=100, confidence=1.0)
        with patch('qubitcoin.config.Config') as mock_config:
            mock_config.CONFIDENCE_DECAY_HALFLIFE = 100000
            mock_config.CONFIDENCE_DECAY_FLOOR = 0.3
            eff = node.effective_confidence(current_block=50100)
            # age=50000, decay = max(0.3, 2^(-0.5)) = max(0.3, 0.707) = 0.707
            assert eff == pytest.approx(0.707, abs=0.01)

    def test_axioms_never_decay(self):
        node = self._make_node(node_type='axiom', confidence=0.95, source_block=0)
        eff = node.effective_confidence(current_block=999999)
        assert eff == 0.95  # No decay for axioms

    def test_no_decay_when_current_block_zero(self):
        node = self._make_node(confidence=0.8)
        eff = node.effective_confidence(current_block=0)
        assert eff == 0.8

    def test_touch_resets_decay_clock(self):
        from qubitcoin.aether.knowledge_graph import KeterNode
        node = KeterNode(
            node_id=1, confidence=1.0, source_block=100,
            last_referenced_block=100,
        )
        # Touch at a later block
        node.last_referenced_block = 50000
        with patch('qubitcoin.config.Config') as mock_config:
            mock_config.CONFIDENCE_DECAY_HALFLIFE = 100000
            mock_config.CONFIDENCE_DECAY_FLOOR = 0.3
            # Age from touched block = 50100 - 50000 = 100, nearly no decay
            eff = node.effective_confidence(current_block=50100)
            assert eff > 0.99


class TestDomainClassification:
    """Test auto-domain classification of knowledge nodes."""

    def test_classify_quantum(self):
        from qubitcoin.aether.knowledge_graph import classify_domain
        content = {'text': 'Quantum entanglement between two qubits'}
        assert classify_domain(content) == 'quantum_physics'

    def test_classify_blockchain(self):
        from qubitcoin.aether.knowledge_graph import classify_domain
        content = {'text': 'Block transaction merkle tree consensus'}
        assert classify_domain(content) == 'blockchain'

    def test_classify_mathematics(self):
        from qubitcoin.aether.knowledge_graph import classify_domain
        content = {'text': 'Theorem proof algebra topology'}
        assert classify_domain(content) == 'mathematics'

    def test_classify_general_for_unknown(self):
        from qubitcoin.aether.knowledge_graph import classify_domain
        content = {'text': 'hello world random stuff'}
        assert classify_domain(content) == 'general'

    def test_classify_empty_content(self):
        from qubitcoin.aether.knowledge_graph import classify_domain
        assert classify_domain({}) == 'general'

    def test_classify_philosophy(self):
        from qubitcoin.aether.knowledge_graph import classify_domain
        content = {'text': 'consciousness qualia epistemology mind'}
        assert classify_domain(content) == 'philosophy'

    def test_classify_biology(self):
        from qubitcoin.aether.knowledge_graph import classify_domain
        content = {'text': 'neuron brain synapse neural dna'}
        assert classify_domain(content) == 'biology'

    def test_classify_physics(self):
        from qubitcoin.aether.knowledge_graph import classify_domain
        content = {'text': 'relativity gravity thermodynamics entropy'}
        assert classify_domain(content) == 'physics'


class TestDomainStats:
    """Test domain statistics and reclassification."""

    def _make_graph(self):
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph
        db = MagicMock()
        db.get_session = MagicMock(side_effect=Exception("skip DB"))
        # Patch _load_from_db to avoid DB access
        with patch.object(KnowledgeGraph, '_load_from_db'):
            kg = KnowledgeGraph(db)
        return kg

    def test_get_domain_stats(self):
        kg = self._make_graph()
        kg.add_node('observation', {'text': 'quantum entanglement qubit'}, 0.9, 1)
        kg.add_node('observation', {'text': 'quantum superposition wave'}, 0.8, 2)
        kg.add_node('observation', {'text': 'blockchain transaction merkle'}, 0.7, 3)

        stats = kg.get_domain_stats()
        assert 'quantum_physics' in stats
        assert stats['quantum_physics']['count'] == 2
        assert 'blockchain' in stats
        assert stats['blockchain']['count'] == 1

    def test_domains_in_get_stats(self):
        kg = self._make_graph()
        kg.add_node('observation', {'text': 'quantum entanglement'}, 0.9, 1)
        stats = kg.get_stats()
        assert 'domains' in stats

    def test_reclassify_domains(self):
        kg = self._make_graph()
        node = kg.add_node('observation', {'text': 'theorem proof algebra'}, 0.9, 1)
        # Manually clear domain
        node.domain = ''
        count = kg.reclassify_domains()
        assert count == 1
        assert node.domain == 'mathematics'


class TestTouchNode:
    """Test touch_node for decay clock reset."""

    def _make_graph(self):
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph
        db = MagicMock()
        db.get_session = MagicMock(side_effect=Exception("skip DB"))
        with patch.object(KnowledgeGraph, '_load_from_db'):
            kg = KnowledgeGraph(db)
        return kg

    def test_touch_updates_last_referenced(self):
        kg = self._make_graph()
        node = kg.add_node('observation', {'text': 'test'}, 0.9, 100)
        assert node.last_referenced_block == 100
        kg.touch_node(node.node_id, 500)
        assert node.last_referenced_block == 500

    def test_touch_nonexistent_node(self):
        kg = self._make_graph()
        # Should not crash
        kg.touch_node(9999, 500)


class TestKGLoadVerification:
    """Verify _load_from_db loads both nodes and edges correctly."""

    def test_load_rebuilds_edge_backpointers(self):
        """Confirm edges_in and edges_out are rebuilt from loaded edges."""
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph

        db = MagicMock()
        mock_session = MagicMock()
        ctx_manager = MagicMock()
        ctx_manager.__enter__ = MagicMock(return_value=mock_session)
        ctx_manager.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = ctx_manager

        # Simulate DB returning 2 nodes and 1 edge
        node_rows = [
            (1, 'observation', 'hash1', '{"text": "node 1"}', 0.9, 10),
            (2, 'inference', 'hash2', '{"text": "node 2"}', 0.8, 20),
        ]
        edge_rows = [
            (1, 2, 'supports', 1.0),
        ]

        call_count = [0]
        def mock_execute(query, *args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:
                result.__iter__ = MagicMock(return_value=iter(node_rows))
                call_count[0] += 1
            else:
                result.__iter__ = MagicMock(return_value=iter(edge_rows))
            return result

        mock_session.execute = mock_execute

        kg = KnowledgeGraph(db)

        assert 1 in kg.nodes
        assert 2 in kg.nodes
        assert 2 in kg.nodes[1].edges_out
        assert 1 in kg.nodes[2].edges_in
        assert len(kg.edges) == 1


class TestMindEndpoint:
    """Test AetherEngine.get_mind_state()."""

    def _make_engine(self, with_kg=True, with_phi=True, with_sephirot=True):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        kg = MagicMock() if with_kg else None
        phi = MagicMock() if with_phi else None
        reasoning = MagicMock()

        engine = AetherEngine(db, kg, phi, reasoning)

        if with_phi:
            phi.compute_phi.return_value = {
                'phi_value': 2.5,
                'gates_passed': 4,
            }

        if with_kg:
            kg.edges = []
            kg.get_domain_stats.return_value = {
                'quantum_physics': {'count': 100, 'avg_confidence': 0.85},
                'economics': {'count': 10, 'avg_confidence': 0.6},
            }

        if with_sephirot:
            from qubitcoin.aether.sephirot_nodes import KeterNode as KeterSephirah
            keter = KeterSephirah()
            keter._goals = [{'type': 'learn', 'domain': 'economics'}]
            from qubitcoin.aether.sephirot import SephirahRole
            engine._sephirot = {SephirahRole.KETER: keter}

        return engine

    def test_mind_state_returns_phi(self):
        engine = self._make_engine()
        state = engine.get_mind_state(1000)
        assert state['phi'] == 2.5
        assert state['gates_passed'] == 4

    def test_mind_state_returns_goals(self):
        engine = self._make_engine()
        state = engine.get_mind_state(1000)
        assert len(state['active_goals']) == 1
        assert state['active_goals'][0]['domain'] == 'economics'

    def test_mind_state_returns_knowledge_gaps(self):
        engine = self._make_engine()
        state = engine.get_mind_state(1000)
        assert len(state['knowledge_gaps']) == 2
        # Smallest domain first
        assert state['knowledge_gaps'][0]['domain'] == 'economics'

    def test_mind_state_returns_domain_balance(self):
        engine = self._make_engine()
        state = engine.get_mind_state(1000)
        assert 'quantum_physics' in state['domain_balance']
        assert state['domain_balance']['quantum_physics']['count'] == 100

    def test_mind_state_returns_sephirot_summary(self):
        engine = self._make_engine()
        state = engine.get_mind_state(1000)
        assert 'keter' in state['sephirot_summary']

    def test_mind_state_no_phi(self):
        engine = self._make_engine(with_phi=False)
        state = engine.get_mind_state(1000)
        assert state['phi'] == 0.0

    def test_mind_state_no_kg(self):
        engine = self._make_engine(with_kg=False)
        state = engine.get_mind_state(1000)
        assert state['domain_balance'] == {}
        assert state['knowledge_gaps'] == []

    def test_mind_state_contradictions(self):
        engine = self._make_engine()
        from qubitcoin.aether.knowledge_graph import KeterEdge, KeterNode
        edge = KeterEdge(from_node_id=1, to_node_id=2, edge_type='contradicts')
        engine.kg.edges = [edge]
        node1 = KeterNode(node_id=1, content={'text': 'A is true'})
        node2 = KeterNode(node_id=2, content={'text': 'A is false'})
        engine.kg.nodes = {1: node1, 2: node2}

        state = engine.get_mind_state(1000)
        assert len(state['recent_contradictions']) == 1
        assert state['recent_contradictions'][0]['node_a_id'] == 1
