"""Tests for Batch 6 features: Consciousness events cap, contradiction
detection, Solidity contract hardening, adaptive seeder."""
import random
from unittest.mock import MagicMock, patch

import pytest

from qubitcoin.aether.knowledge_graph import KeterNode, KnowledgeGraph


# ─── 9.1 Auto Contradiction Detection ──────────────────────────────────────

class TestContradictionDetection:
    """Test KnowledgeGraph.detect_contradictions()."""

    def _make_kg(self) -> KnowledgeGraph:
        kg = KnowledgeGraph.__new__(KnowledgeGraph)
        kg.db = None
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

    def test_returns_zero_for_missing_node(self):
        kg = self._make_kg()
        assert kg.detect_contradictions(999) == 0

    def test_skips_non_assertion_nodes(self):
        kg = self._make_kg()
        node = KeterNode(node_id=1, node_type='axiom',
                         content={'text': 'test'}, domain='physics')
        kg.nodes[1] = node
        assert kg.detect_contradictions(1) == 0

    def test_skips_empty_content(self):
        kg = self._make_kg()
        node = KeterNode(node_id=1, node_type='assertion',
                         content={'text': ''}, domain='physics')
        kg.nodes[1] = node
        assert kg.detect_contradictions(1) == 0

    def test_detects_numeric_contradiction(self):
        kg = self._make_kg()
        # Existing node
        existing = KeterNode(
            node_id=1, node_type='assertion',
            content={'text': 'the maximum supply of qubitcoin is 3300000000 coins total'},
            domain='blockchain', source_block=10, confidence=0.8
        )
        kg.nodes[1] = existing
        # New node with conflicting number
        new_node = KeterNode(
            node_id=2, node_type='assertion',
            content={'text': 'the maximum supply of qubitcoin is 21000000 coins total'},
            domain='blockchain', source_block=20, confidence=0.7
        )
        kg.nodes[2] = new_node
        kg._next_id = 3
        kg._next_edge_id = 1

        created = kg.detect_contradictions(2)
        assert created == 1
        # Check that a contradicts edge was created
        assert len(kg.edges) == 1
        assert kg.edges[0].edge_type == 'contradicts'

    def test_no_contradiction_when_same_numbers(self):
        kg = self._make_kg()
        existing = KeterNode(
            node_id=1, node_type='assertion',
            content={'text': 'the block time target is 3.3 seconds'},
            domain='blockchain', source_block=10
        )
        kg.nodes[1] = existing
        new_node = KeterNode(
            node_id=2, node_type='assertion',
            content={'text': 'the block time target is 3.3 seconds per block'},
            domain='blockchain', source_block=20
        )
        kg.nodes[2] = new_node
        kg._next_id = 3
        kg._next_edge_id = 1

        created = kg.detect_contradictions(2)
        assert created == 0

    def test_no_contradiction_low_word_overlap(self):
        kg = self._make_kg()
        existing = KeterNode(
            node_id=1, node_type='assertion',
            content={'text': 'quantum entanglement correlates particles at 100 percent fidelity'},
            domain='physics', source_block=10
        )
        kg.nodes[1] = existing
        new_node = KeterNode(
            node_id=2, node_type='assertion',
            content={'text': 'the blockchain network has 500 nodes'},
            domain='blockchain', source_block=20
        )
        kg.nodes[2] = new_node
        kg._next_id = 3
        kg._next_edge_id = 1

        created = kg.detect_contradictions(2)
        assert created == 0

    def test_caps_at_3_contradictions(self):
        kg = self._make_kg()
        # Create 5 existing nodes all with conflicting numbers
        for i in range(1, 6):
            node = KeterNode(
                node_id=i, node_type='assertion',
                content={'text': f'the total supply of the qubitcoin token is {i * 1000000} coins in this chain'},
                domain='blockchain', source_block=i
            )
            kg.nodes[i] = node

        new_node = KeterNode(
            node_id=10, node_type='assertion',
            content={'text': 'the total supply of the qubitcoin token is 99999999 coins in this chain'},
            domain='blockchain', source_block=100
        )
        kg.nodes[10] = new_node
        kg._next_id = 11
        kg._next_edge_id = 1

        created = kg.detect_contradictions(10)
        assert created <= 3


# ─── 1.4 Consciousness Events Cap ──────────────────────────────────────────

class TestConsciousnessEventsCap:
    """Test AetherEngine.archive_consciousness_events()."""

    def test_returns_zero_when_under_cap(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        engine = AetherEngine(db)

        mock_session = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_session)
        ctx.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = ctx

        # Total events under cap
        mock_session.execute.return_value.scalar.return_value = 500
        result = engine.archive_consciousness_events(max_keep=10000)
        assert result == 0

    def test_deletes_excess_events(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        engine = AetherEngine(db)

        mock_session = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_session)
        ctx.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = ctx

        # Simulate: first execute returns count, second returns delete result
        count_result = MagicMock()
        count_result.scalar.return_value = 15000

        delete_result = MagicMock()
        delete_result.rowcount = 5000

        mock_session.execute.side_effect = [count_result, delete_result]

        result = engine.archive_consciousness_events(max_keep=10000)
        assert result == 5000

    def test_handles_db_error(self):
        from qubitcoin.aether.proof_of_thought import AetherEngine
        db = MagicMock()
        engine = AetherEngine(db)

        db.get_session.side_effect = Exception("DB unavailable")
        # Should not raise, returns 0
        result = engine.archive_consciousness_events()
        assert result == 0


# ─── 6.1 Adaptive Seeder (Domain-Weighted Selection) ───────────────────────

class TestAdaptiveSeeder:
    """Test KnowledgeSeeder._pick_weighted_prompt()."""

    def test_weighted_prompt_favors_small_domains(self):
        from qubitcoin.aether.knowledge_seeder import KnowledgeSeeder, MASTER_PROMPTS
        seeder = KnowledgeSeeder.__new__(KnowledgeSeeder)
        seeder._prompt_index = 0
        seeder._kg = None

        # Domain stats: quantum_physics has 1000 nodes, economics has 0
        domain_stats = {
            'quantum_physics': {'count': 1000, 'avg_confidence': 0.7},
            'economics': {'count': 0, 'avg_confidence': 0.0},
        }

        # Run many picks and count domain distribution
        picks = {'quantum_physics': 0, 'economics': 0}
        random.seed(42)
        for _ in range(200):
            p = seeder._pick_weighted_prompt(domain_stats)
            if p['domain'] in picks:
                picks[p['domain']] += 1

        # Economics (0 nodes) should be picked more often than quantum_physics (1000 nodes)
        # Weight for economics: 1.0 / (1 + 0/100) = 1.0
        # Weight for quantum_physics: 1.0 / (1 + 1000/100) = 0.0909
        assert picks['economics'] > picks['quantum_physics']

    def test_weighted_prompt_returns_valid_prompt(self):
        from qubitcoin.aether.knowledge_seeder import KnowledgeSeeder, MASTER_PROMPTS
        seeder = KnowledgeSeeder.__new__(KnowledgeSeeder)
        seeder._prompt_index = 0
        seeder._kg = None

        domain_stats = {'quantum_physics': {'count': 50, 'avg_confidence': 0.5}}
        result = seeder._pick_weighted_prompt(domain_stats)
        assert 'domain' in result
        assert 'prompt' in result
        assert result in MASTER_PROMPTS

    def test_pick_prompt_uses_weighted_when_kg_available(self):
        from qubitcoin.aether.knowledge_seeder import KnowledgeSeeder
        seeder = KnowledgeSeeder.__new__(KnowledgeSeeder)
        seeder._prompt_index = 0
        mock_kg = MagicMock()
        mock_kg.get_domain_stats.return_value = {
            'quantum_physics': {'count': 500},
            'economics': {'count': 10},
        }
        seeder._kg = mock_kg

        result = seeder._pick_prompt()
        assert result is not None
        assert 'domain' in result

    def test_pick_prompt_falls_back_to_roundrobin(self):
        from qubitcoin.aether.knowledge_seeder import KnowledgeSeeder, MASTER_PROMPTS
        seeder = KnowledgeSeeder.__new__(KnowledgeSeeder)
        seeder._prompt_index = 0
        seeder._kg = None  # No KG available

        result = seeder._pick_prompt()
        assert result == MASTER_PROMPTS[0]

    def test_pick_prompt_roundrobin_on_kg_error(self):
        from qubitcoin.aether.knowledge_seeder import KnowledgeSeeder, MASTER_PROMPTS
        seeder = KnowledgeSeeder.__new__(KnowledgeSeeder)
        seeder._prompt_index = 3
        mock_kg = MagicMock()
        mock_kg.get_domain_stats.side_effect = Exception("KG error")
        seeder._kg = mock_kg

        result = seeder._pick_prompt()
        assert result == MASTER_PROMPTS[3]


# ─── 7.2 + 7.3 Solidity Contract Checks (structure only) ───────────────────

class TestSolidityContractHardening:
    """Verify Solidity contracts contain expected hardening patterns."""

    def test_consciousness_dashboard_has_archive(self):
        import os
        sol_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'src', 'qubitcoin',
            'contracts', 'solidity', 'aether', 'ConsciousnessDashboard.sol'
        )
        with open(sol_path, 'r') as f:
            content = f.read()
        assert 'MAX_MEASUREMENTS' in content
        assert 'archiveMeasurements' in content
        assert 'archivedUpTo' in content
        assert 'latestMeasurementIndex' in content

    def test_global_workspace_has_prune(self):
        import os
        sol_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'src', 'qubitcoin',
            'contracts', 'solidity', 'aether', 'GlobalWorkspace.sol'
        )
        with open(sol_path, 'r') as f:
            content = f.read()
        assert 'MAX_BROADCAST_HISTORY' in content
        assert 'pruneBroadcastHistory' in content
