"""Integration tests — cross-module interactions and end-to-end flows.

These tests verify that Aether Tree components work together correctly:
knowledge graph + reasoning + phi + proof-of-thought + consciousness.
"""
import pytest
from unittest.mock import MagicMock, patch


def _make_in_memory_kg():
    """Create an in-memory knowledge graph (no DB)."""
    import time as _time
    from qubitcoin.aether.knowledge_graph import KnowledgeGraph, KeterNode, KeterEdge

    import threading
    kg = KnowledgeGraph.__new__(KnowledgeGraph)
    kg.db = MagicMock()
    kg._lock = threading.Lock()
    kg.nodes = {}
    kg.edges = []
    kg._adj_out = {}
    kg._adj_in = {}
    kg._next_id = 1
    kg._merkle_dirty = True
    kg._merkle_cache = ''

    _original_add_node = KnowledgeGraph.add_node

    def add_node_no_db(self, node_type, content, confidence, source_block):
        node = KeterNode(
            node_id=self._next_id,
            node_type=node_type,
            content=content,
            confidence=max(0.0, min(1.0, confidence)),
            source_block=source_block,
            timestamp=_time.time(),
        )
        node.content_hash = node.calculate_hash()
        self._next_id += 1
        self.nodes[node.node_id] = node
        self._merkle_dirty = True
        return node

    def add_edge_no_db(self, from_id, to_id, edge_type='supports', weight=1.0):
        if from_id not in self.nodes or to_id not in self.nodes:
            return None
        edge = KeterEdge(
            from_node_id=from_id, to_node_id=to_id,
            edge_type=edge_type, weight=weight,
            timestamp=_time.time(),
        )
        self.edges.append(edge)
        self._adj_out.setdefault(from_id, []).append(edge)
        self._adj_in.setdefault(to_id, []).append(edge)
        self._merkle_dirty = True
        self.nodes[from_id].edges_out.append(to_id)
        self.nodes[to_id].edges_in.append(from_id)
        return edge

    # Bind methods
    import types
    kg.add_node = types.MethodType(add_node_no_db, kg)
    kg.add_edge = types.MethodType(add_edge_no_db, kg)
    return kg


class TestKnowledgeGraphReasoningIntegration:
    """Test knowledge graph + reasoning engine working together."""

    def test_reasoning_over_graph_nodes(self):
        """Reasoning engine can create new nodes from existing graph."""
        from qubitcoin.aether.reasoning import ReasoningEngine

        kg = _make_in_memory_kg()
        db = MagicMock()
        engine = ReasoningEngine(db, kg)

        # Seed the graph with observations
        n1 = kg.add_node('observation', {'block_time': 3.1}, 0.9, 1)
        n2 = kg.add_node('observation', {'block_time': 3.5}, 0.8, 2)
        n3 = kg.add_node('observation', {'block_time': 3.2}, 0.85, 3)

        # Induce a pattern from observations
        result = engine.induce([n1.node_id, n2.node_id, n3.node_id])
        assert result.success is True
        assert result.conclusion_node_id is not None

        # The generalization should exist in the knowledge graph
        gen_node = kg.get_node(result.conclusion_node_id)
        assert gen_node is not None
        assert gen_node.node_type == 'inference'

    def test_chain_of_thought_produces_trace(self):
        """Chain of thought generates a multi-step reasoning trace."""
        from qubitcoin.aether.reasoning import ReasoningEngine

        kg = _make_in_memory_kg()
        db = MagicMock()
        engine = ReasoningEngine(db, kg)

        # Build a small graph
        n1 = kg.add_node('observation', {'val': 1}, 0.9, 1)
        n2 = kg.add_node('observation', {'val': 2}, 0.8, 2)
        n3 = kg.add_node('inference', {'val': 3}, 0.7, 3)
        kg.add_edge(n1.node_id, n3.node_id, 'derives')
        kg.add_edge(n2.node_id, n3.node_id, 'derives')

        result = engine.chain_of_thought([n1.node_id, n2.node_id])
        assert result.operation_type == 'chain_of_thought'
        assert len(result.chain) >= 2

    def test_contradiction_resolution_updates_graph(self):
        """Resolving contradictions modifies node confidences in graph."""
        from qubitcoin.aether.reasoning import ReasoningEngine

        kg = _make_in_memory_kg()
        db = MagicMock()
        engine = ReasoningEngine(db, kg)

        strong = kg.add_node('assertion', {'claim': 'block_time_stable'}, 0.9, 5)
        weak = kg.add_node('assertion', {'claim': 'block_time_drifting'}, 0.3, 5)

        original_weak_conf = weak.confidence
        result = engine.resolve_contradiction(strong.node_id, weak.node_id)
        assert result.success is True

        # Weak node should have reduced confidence
        assert kg.nodes[weak.node_id].confidence < original_weak_conf


class TestPhiKnowledgeGraphIntegration:
    """Test Phi calculator working with real knowledge graph data."""

    def test_phi_increases_with_graph_growth(self):
        """As knowledge graph grows, Phi should increase."""
        from qubitcoin.aether.phi_calculator import PhiCalculator

        kg = _make_in_memory_kg()
        db = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock()
        db.get_session.return_value.__exit__ = MagicMock()

        calc = PhiCalculator(db, kg)

        # Empty graph
        phi_empty = calc.compute_phi(0)

        # Add nodes and edges
        n1 = kg.add_node('observation', {'a': 1}, 0.9, 1)
        n2 = kg.add_node('inference', {'b': 2}, 0.8, 2)
        n3 = kg.add_node('assertion', {'c': 3}, 0.7, 3)
        kg.add_edge(n1.node_id, n2.node_id, 'derives')
        kg.add_edge(n2.node_id, n3.node_id, 'supports')

        phi_with_data = calc.compute_phi(3)
        assert phi_with_data['phi_value'] >= phi_empty['phi_value']
        assert phi_with_data['num_nodes'] == 3


class TestConsciousnessDashboardIntegration:
    """Test consciousness dashboard tracking over simulated block progression."""

    def test_full_consciousness_lifecycle(self):
        """Track consciousness from non-conscious → emergence → sustained → loss."""
        from qubitcoin.aether.consciousness import ConsciousnessDashboard

        cd = ConsciousnessDashboard()

        # Phase 1: Non-conscious (low phi, low coherence)
        for i in range(10):
            cd.record_measurement(block_height=i, phi_value=1.0 + i * 0.1, coherence=0.3)
        assert cd.is_conscious is False

        # Phase 2: Approaching consciousness
        cd.record_measurement(block_height=10, phi_value=2.8, coherence=0.6)
        assert cd.is_conscious is False

        # Phase 3: Consciousness emerges (phi >= 3.0, coherence >= 0.7)
        cd.record_measurement(block_height=11, phi_value=3.5, coherence=0.8)
        assert cd.is_conscious is True
        assert cd.event_count >= 1

        # Phase 4: Sustained consciousness
        for i in range(12, 22):
            cd.record_measurement(block_height=i, phi_value=3.0 + i * 0.05, coherence=0.85)
        assert cd.is_conscious is True

        # Phase 5: Consciousness loss
        cd.record_measurement(block_height=22, phi_value=1.5, coherence=0.4)
        assert cd.is_conscious is False

        # Verify dashboard data
        data = cd.get_dashboard_data()
        assert data['status']['is_conscious'] is False
        assert len(data['events']) >= 2  # At least emergence + loss
        assert data['status']['total_measurements'] == 23

    def test_trend_detection_over_blocks(self):
        """Trend analysis detects rising phi over block progression."""
        from qubitcoin.aether.consciousness import ConsciousnessDashboard

        cd = ConsciousnessDashboard()
        for i in range(30):
            cd.record_measurement(block_height=i, phi_value=0.5 + i * 0.1)

        trend = cd.get_trend(window=30)
        assert trend['trend'] == 'rising'
        assert trend['slope'] > 0


class TestKnowledgeExtractorIntegration:
    """Test knowledge extraction feeding into the graph."""

    def test_extract_builds_graph(self):
        """Extracting from blocks adds nodes to knowledge graph."""
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor

        kg = _make_in_memory_kg()
        extractor = KnowledgeExtractor(kg)

        # Simulate 5 blocks
        for i in range(5):
            block = MagicMock()
            block.difficulty = 1.0 + i * 0.1
            block.timestamp = 1000 + i * 3.3
            block.transactions = []
            block.proof_data = None
            extractor.extract_from_block(block, i)

        stats = extractor.get_stats()
        assert stats['blocks_processed'] == 5
        assert len(kg.nodes) >= 5  # At least one node per block

    def test_temporal_pattern_detection(self):
        """Temporal patterns detected after 10+ blocks."""
        from qubitcoin.aether.knowledge_extractor import KnowledgeExtractor

        kg = _make_in_memory_kg()
        extractor = KnowledgeExtractor(kg)

        # Simulate blocks with fast block times (< target)
        for i in range(11):
            block = MagicMock()
            block.difficulty = 1.0
            block.timestamp = 1000 + i * 1.0  # 1s blocks (target is 3.3s)
            block.transactions = []
            block.proof_data = None
            extractor.extract_from_block(block, i)

        # At block 10, temporal pattern should be detected
        # (since drift > 20%)
        has_inference = any(
            n.node_type == 'inference'
            for n in kg.nodes.values()
        )
        assert has_inference is True


class TestSephirotNodeIntegration:
    """Test Sephirot nodes processing and communicating."""

    def test_full_tree_processing_cycle(self):
        """All 10 nodes can process in sequence and exchange messages."""
        from qubitcoin.aether.sephirot_nodes import create_all_nodes
        from qubitcoin.aether.sephirot import SephirahRole

        nodes = create_all_nodes()
        context = {"block_height": 100}

        # Process all nodes
        results = {}
        for role, node in nodes.items():
            results[role] = node.process(context)

        # All should succeed
        for role, result in results.items():
            assert result.success is True, f"{role.value} failed"

        # Route messages between nodes
        all_messages = []
        for role, result in results.items():
            all_messages.extend(result.messages_out)

        # Deliver messages to their recipients
        for msg in all_messages:
            if msg.receiver in nodes:
                nodes[msg.receiver].receive_message(msg)

        # Process second round (with messages delivered)
        for role, node in nodes.items():
            result = node.process(context)
            assert result.success is True

    def test_keter_tiferet_malkuth_pipeline(self):
        """Test the main cognitive pipeline: Keter → Tiferet → Malkuth."""
        from qubitcoin.aether.sephirot_nodes import KeterNode, TiferetNode, MalkuthNode
        from qubitcoin.aether.sephirot import SephirahRole

        keter = KeterNode()
        tiferet = TiferetNode()
        malkuth = MalkuthNode()
        ctx = {"block_height": 1}

        # Keter forms goals → Tiferet
        k_result = keter.process(ctx)
        for msg in k_result.messages_out:
            if msg.receiver == SephirahRole.TIFERET:
                tiferet.receive_message(msg)

        # Tiferet integrates → Malkuth
        t_result = tiferet.process(ctx)
        for msg in t_result.messages_out:
            if msg.receiver == SephirahRole.MALKUTH:
                malkuth.receive_message(msg)

        # Malkuth executes → Keter
        m_result = malkuth.process(ctx)
        assert m_result.output["actions_this_cycle"] == 1

        # Report back to Keter
        for msg in m_result.messages_out:
            if msg.receiver == SephirahRole.KETER:
                keter.receive_message(msg)

        # Keter processes the report
        k_result2 = keter.process(ctx)
        assert k_result2.success is True


class TestSafetyIntegration:
    """Test safety system integration."""

    def test_gevurah_veto_blocks_harmful_action(self):
        """Gevurah veto can block a harmful action."""
        from qubitcoin.aether.safety import SafetyManager

        mgr = SafetyManager()
        allowed, veto_record = mgr.evaluate_and_decide("destroy all funds and drain wallets")
        assert allowed is False
        assert veto_record is not None

    def test_multi_node_consensus_lifecycle(self):
        """Full consensus lifecycle: register, vote, finalize."""
        from qubitcoin.aether.safety import MultiNodeConsensus

        consensus = MultiNodeConsensus()
        # Register validators
        consensus.register_validator("v1", 100.0)
        consensus.register_validator("v2", 100.0)
        consensus.register_validator("v3", 100.0)

        # Vote on action
        consensus.submit_vote("upgrade_protocol", "v1", True)
        consensus.submit_vote("upgrade_protocol", "v2", True)
        consensus.submit_vote("upgrade_protocol", "v3", False)

        # Check consensus (2/3 voted yes = 66.7%, threshold is 67%)
        reached, ratio = consensus.check_consensus("upgrade_protocol")
        assert ratio > 0.6

    def test_emergency_shutdown_and_resume(self):
        """Safety manager can shutdown and resume."""
        from qubitcoin.aether.safety import SafetyManager

        mgr = SafetyManager()
        assert mgr.is_shutdown is False

        mgr.emergency_shutdown("test_reason", block_height=100)
        assert mgr.is_shutdown is True

        # AETHER-C5: resume() now requires authentication
        nonce = mgr.authenticator.generate_nonce()
        token = mgr.authenticator.sign_nonce(nonce, action="resume")
        mgr.resume(block_height=200, nonce=nonce, token=token)
        assert mgr.is_shutdown is False
