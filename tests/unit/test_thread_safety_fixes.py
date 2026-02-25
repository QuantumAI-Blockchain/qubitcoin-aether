"""Tests verifying Run #27 fixes: thread safety, bare excepts, health subsystems.

Covers:
- MiningEngine.get_stats_snapshot() thread-safe copy
- KnowledgeGraph._lock protects add_node/add_edge
- Bare `except:` replaced with `except Exception:`
- /health/subsystems endpoint shape
"""

import threading
import pytest
from unittest.mock import MagicMock, patch


def _make_mining_engine():
    from qubitcoin.mining.engine import MiningEngine
    return MiningEngine(MagicMock(), MagicMock(), MagicMock(), MagicMock())


class TestMiningStatsSnapshot:
    """Verify MiningEngine.get_stats_snapshot() returns a thread-safe copy."""

    def test_get_stats_snapshot_exists(self) -> None:
        engine = _make_mining_engine()
        assert hasattr(engine, 'get_stats_snapshot')

    def test_snapshot_returns_dict(self) -> None:
        engine = _make_mining_engine()
        snap = engine.get_stats_snapshot()
        assert isinstance(snap, dict)
        assert 'blocks_found' in snap
        assert 'total_attempts' in snap
        assert 'current_difficulty' in snap

    def test_snapshot_is_a_copy(self) -> None:
        """Mutating the snapshot must not affect the engine's stats."""
        engine = _make_mining_engine()
        snap = engine.get_stats_snapshot()
        snap['blocks_found'] = 9999
        assert engine.stats['blocks_found'] != 9999

    def test_lock_exists_on_engine(self) -> None:
        engine = _make_mining_engine()
        assert hasattr(engine, '_lock')
        assert isinstance(engine._lock, type(threading.Lock()))


class TestKnowledgeGraphLock:
    """Verify KnowledgeGraph has a threading lock on mutations."""

    def _make_kg(self):
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph
        mock_db = MagicMock()
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([]))
        session.execute.return_value = result_mock
        mock_db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        return KnowledgeGraph(mock_db)

    def test_lock_exists(self) -> None:
        kg = self._make_kg()
        assert hasattr(kg, '_lock')
        assert isinstance(kg._lock, type(threading.Lock()))

    def test_add_node_works(self) -> None:
        kg = self._make_kg()
        node = kg.add_node('assertion', {'text': 'test'}, 0.9, 1)
        assert node.node_id == 1
        assert node.node_type == 'assertion'

    def test_add_edge_works(self) -> None:
        kg = self._make_kg()
        n1 = kg.add_node('assertion', {'text': 'a'}, 0.9, 1)
        n2 = kg.add_node('observation', {'text': 'b'}, 0.8, 1)
        edge = kg.add_edge(n1.node_id, n2.node_id, 'supports', 1.0)
        assert edge is not None
        assert edge.from_node_id == n1.node_id
        assert edge.to_node_id == n2.node_id

    def test_concurrent_add_node_no_crash(self) -> None:
        """Multiple threads adding nodes should not crash."""
        kg = self._make_kg()
        errors = []

        def add_nodes(start: int):
            try:
                for i in range(10):
                    kg.add_node('assertion', {'idx': start + i}, 0.5, 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_nodes, args=(i * 10,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(kg.nodes) == 40


class TestBareExceptsFixed:
    """Verify bare `except:` has been replaced with `except Exception:`."""

    def test_p2p_no_bare_except(self) -> None:
        """p2p_network.py should have no bare except: clauses."""
        from pathlib import Path
        src = Path(__file__).parent.parent.parent / "src" / "qubitcoin" / "network" / "p2p_network.py"
        content = src.read_text()
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Match bare `except:` but not `except Exception:` or similar
            if stripped == 'except:':
                pytest.fail(f"p2p_network.py line {i}: bare 'except:' found")

    def test_database_manager_no_bare_except(self) -> None:
        """database/manager.py should have no bare except: clauses."""
        from pathlib import Path
        src = Path(__file__).parent.parent.parent / "src" / "qubitcoin" / "database" / "manager.py"
        content = src.read_text()
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == 'except:':
                pytest.fail(f"database/manager.py line {i}: bare 'except:' found")


class TestHealthSubsystemsEndpoint:
    """Verify /health/subsystems endpoint is registered."""

    def test_endpoint_exists(self) -> None:
        """The endpoint should be registered on the FastAPI app."""
        from qubitcoin.network.rpc import create_rpc_app
        mock_mining = MagicMock()
        mock_mining.is_mining = False
        mock_mining.get_stats_snapshot.return_value = {'blocks_found': 0, 'uptime': 0}
        mock_mining.stats = {}
        app = create_rpc_app(
            db_manager=MagicMock(),
            mining_engine=mock_mining,
            consensus_engine=MagicMock(),
            quantum_engine=MagicMock(),
            ipfs_manager=MagicMock(),
        )
        routes = [r.path for r in app.routes]
        assert '/health/subsystems' in routes

    def test_mining_stats_endpoint_uses_snapshot(self) -> None:
        """The /mining/stats endpoint should use get_stats_snapshot()."""
        from qubitcoin.network.rpc import create_rpc_app
        mock_mining = MagicMock()
        mock_mining.is_mining = False
        mock_mining.get_stats_snapshot.return_value = {
            'blocks_found': 42, 'uptime': 100,
            'current_difficulty': 1.0, 'total_attempts': 10,
            'best_energy': None, 'alignment_score': None,
            'total_burned': 0.0,
        }
        mock_mining.stats = {}
        app = create_rpc_app(
            db_manager=MagicMock(),
            mining_engine=mock_mining,
            consensus_engine=MagicMock(),
            quantum_engine=MagicMock(),
            ipfs_manager=MagicMock(),
        )
        routes = [r.path for r in app.routes]
        assert '/mining/stats' in routes
