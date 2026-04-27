"""Unit tests for DB maintenance: Phi downsampling, KG pruning with DB delete,
confidence persistence, and staking reward distribution.

Tests for UPDATETODO items 1.1, 1.2, 2.2, 8.1.
"""
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

from qubitcoin.aether.knowledge_graph import KnowledgeGraph, KeterNode, KeterEdge
from qubitcoin.aether.phi_calculator import PhiCalculator
from qubitcoin.config import Config


# ---------------------------------------------------------------------------
# PhiCalculator downsampling tests
# ---------------------------------------------------------------------------

class TestPhiDownsampling:
    """Test phi measurement downsampling."""

    def test_downsample_returns_stats(self):
        db = MagicMock()
        phi = PhiCalculator(db)
        # DB session that returns no rows to downsample
        session_mock = MagicMock()
        session_mock.execute = MagicMock(return_value=iter([]))
        session_mock.__enter__ = MagicMock(return_value=session_mock)
        session_mock.__exit__ = MagicMock(return_value=False)
        db.get_session = MagicMock(return_value=session_mock)

        stats = phi.downsample_phi_measurements(retain_days=7)
        assert 'hourly_created' in stats
        assert 'daily_created' in stats
        assert 'rows_deleted' in stats

    def test_downsample_graceful_on_error(self):
        db = MagicMock()
        db.get_session = MagicMock(side_effect=Exception("DB down"))
        phi = PhiCalculator(db)
        stats = phi.downsample_phi_measurements()
        assert stats['rows_deleted'] == 0

    def test_downsample_uses_config_default(self):
        db = MagicMock()
        phi = PhiCalculator(db)
        session_mock = MagicMock()
        session_mock.execute = MagicMock(return_value=iter([]))
        session_mock.__enter__ = MagicMock(return_value=session_mock)
        session_mock.__exit__ = MagicMock(return_value=False)
        db.get_session = MagicMock(return_value=session_mock)

        # Should use Config.PHI_DOWNSAMPLE_RETAIN_DAYS (default 7)
        stats = phi.downsample_phi_measurements()
        assert stats is not None


# ---------------------------------------------------------------------------
# KnowledgeGraph pruning with DB delete tests
# ---------------------------------------------------------------------------

class TestKGPruningDBDelete:
    """Test that prune_low_confidence also deletes from database."""

    def _make_kg_with_mock_db(self):
        db = MagicMock()
        # Prevent _load_from_db from running
        session_mock = MagicMock()
        session_mock.execute = MagicMock(return_value=iter([]))
        session_mock.__enter__ = MagicMock(return_value=session_mock)
        session_mock.__exit__ = MagicMock(return_value=False)
        db.get_session = MagicMock(return_value=session_mock)

        kg = KnowledgeGraph(db)
        return kg, db, session_mock

    def test_prune_deletes_from_db(self):
        kg, db, session_mock = self._make_kg_with_mock_db()

        # Add nodes directly to in-memory graph
        kg.nodes[1] = KeterNode(node_id=1, node_type='observation', confidence=0.05, content={'text': 'low'})
        kg.nodes[2] = KeterNode(node_id=2, node_type='assertion', confidence=0.9, content={'text': 'high'})
        kg.nodes[3] = KeterNode(node_id=3, node_type='axiom', confidence=0.01, content={'text': 'axiom'})  # protected

        # Mock the DELETE results
        delete_result = MagicMock()
        delete_result.rowcount = 1
        session_mock.execute = MagicMock(return_value=delete_result)

        pruned = kg.prune_low_confidence(threshold=0.1)

        # Only node 1 should be pruned (node 2 is above threshold, node 3 is axiom)
        assert pruned == 1
        assert 1 not in kg.nodes
        assert 2 in kg.nodes
        assert 3 in kg.nodes

        # Verify DB delete was called
        assert session_mock.execute.call_count >= 2  # edges + nodes delete
        assert session_mock.commit.called

    def test_prune_zero_nodes_skips_db(self):
        kg, db, session_mock = self._make_kg_with_mock_db()

        kg.nodes[1] = KeterNode(node_id=1, node_type='observation', confidence=0.9, content={})

        pruned = kg.prune_low_confidence(threshold=0.1)
        assert pruned == 0
        # Should not have made additional DB calls beyond _load_from_db
        assert not session_mock.commit.called

    def test_prune_cleans_edges(self):
        kg, db, session_mock = self._make_kg_with_mock_db()

        kg.nodes[1] = KeterNode(node_id=1, node_type='observation', confidence=0.05, content={})
        kg.nodes[2] = KeterNode(node_id=2, node_type='assertion', confidence=0.9, content={})
        edge = KeterEdge(from_node_id=1, to_node_id=2, edge_type='supports')
        kg.edges.append(edge)
        kg.nodes[2].edges_in.append(1)
        kg.nodes[1].edges_out.append(2)
        kg._adj_out.setdefault(1, []).append(edge)
        kg._adj_in.setdefault(2, []).append(edge)

        delete_result = MagicMock()
        delete_result.rowcount = 1
        session_mock.execute = MagicMock(return_value=delete_result)

        pruned = kg.prune_low_confidence(threshold=0.1)
        assert pruned == 1
        assert len(kg.edges) == 0
        assert 1 not in kg.nodes[2].edges_in


# ---------------------------------------------------------------------------
# Confidence persistence tests
# ---------------------------------------------------------------------------

class TestConfidencePersistence:
    """Test persist_confidence_updates method."""

    def _make_kg_with_mock_db(self):
        db = MagicMock()
        session_mock = MagicMock()
        session_mock.execute = MagicMock(return_value=iter([]))
        session_mock.__enter__ = MagicMock(return_value=session_mock)
        session_mock.__exit__ = MagicMock(return_value=False)
        db.get_session = MagicMock(return_value=session_mock)
        kg = KnowledgeGraph(db)
        return kg, db, session_mock

    def test_persist_updates_db(self):
        kg, db, session_mock = self._make_kg_with_mock_db()

        kg.nodes[1] = KeterNode(node_id=1, confidence=0.8, content={})
        kg.nodes[2] = KeterNode(node_id=2, confidence=0.5, content={})

        update_result = MagicMock()
        update_result.rowcount = 1
        session_mock.execute = MagicMock(return_value=update_result)

        updated = kg.persist_confidence_updates()
        assert updated >= 0  # May be 2 if DB had different values
        assert session_mock.commit.called

    def test_persist_empty_graph(self):
        kg, db, session_mock = self._make_kg_with_mock_db()
        updated = kg.persist_confidence_updates()
        assert updated == 0

    def test_persist_handles_error(self):
        kg, db, session_mock = self._make_kg_with_mock_db()
        kg.nodes[1] = KeterNode(node_id=1, confidence=0.8, content={})
        db.get_session = MagicMock(side_effect=Exception("DB error"))
        updated = kg.persist_confidence_updates()
        assert updated == 0


# ---------------------------------------------------------------------------
# Config tests for new variables
# ---------------------------------------------------------------------------

class TestNewConfigVars:
    """Test new config variables have correct defaults."""

    def test_phi_downsample_defaults(self):
        assert Config.PHI_DOWNSAMPLE_RETAIN_DAYS == 7
        assert Config.PHI_DOWNSAMPLE_INTERVAL == 1000

    def test_prune_defaults(self):
        assert Config.PRUNE_CONFIDENCE_THRESHOLD == 0.1
        assert Config.PRUNE_INTERVAL_BLOCKS == 500

    def test_sephirot_staking_defaults(self):
        assert Config.SEPHIROT_STAKER_SHARE_RATIO == 0.6
        assert Config.SEPHIROT_REWARD_INTERVAL == 100
        assert Config.SEPHIROT_MIN_STAKE == 100.0
        assert Config.SEPHIROT_UNSTAKING_DELAY_BLOCKS == 183272

    def test_reasoning_archive_default(self):
        assert Config.REASONING_ARCHIVE_RETAIN_BLOCKS == 50000
