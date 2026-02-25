"""Tests verifying Run #29 fixes: debugger methods, decoherence stats, risk serialization.

Covers:
- QVMDebugger.load_bytecode() (not .load())
- QVMDebugger.get_stats() (not .get_state())
- DecoherenceManager.get_stats() new method
- RiskNormalizer.normalize() returns RiskBreakdown with .to_dict()
"""

import pytest
from unittest.mock import MagicMock


class TestQVMDebuggerMethods:
    """Verify QVMDebugger has load_bytecode(), not load()."""

    def test_load_bytecode_exists(self) -> None:
        from qubitcoin.qvm.debugger import QVMDebugger
        d = QVMDebugger()
        assert hasattr(d, 'load_bytecode')

    def test_load_not_exists(self) -> None:
        from qubitcoin.qvm.debugger import QVMDebugger
        d = QVMDebugger()
        assert not hasattr(d, 'load')

    def test_get_stats_exists(self) -> None:
        from qubitcoin.qvm.debugger import QVMDebugger
        d = QVMDebugger()
        assert hasattr(d, 'get_stats')

    def test_get_state_not_exists(self) -> None:
        from qubitcoin.qvm.debugger import QVMDebugger
        d = QVMDebugger()
        assert not hasattr(d, 'get_state')

    def test_get_stats_returns_dict(self) -> None:
        from qubitcoin.qvm.debugger import QVMDebugger
        d = QVMDebugger()
        stats = d.get_stats()
        assert isinstance(stats, dict)

    def test_load_bytecode_works(self) -> None:
        from qubitcoin.qvm.debugger import QVMDebugger
        d = QVMDebugger()
        d.load_bytecode(b'\x60\x00')  # PUSH1 0x00
        stats = d.get_stats()
        assert stats.get('bytecode_size', 0) > 0 or 'pc' in stats


class TestDecoherenceManagerGetStats:
    """Verify DecoherenceManager.get_stats() exists and returns correct shape."""

    def test_get_stats_exists(self) -> None:
        from qubitcoin.qvm.decoherence import DecoherenceManager
        dm = DecoherenceManager()
        assert hasattr(dm, 'get_stats')

    def test_get_stats_empty(self) -> None:
        from qubitcoin.qvm.decoherence import DecoherenceManager
        dm = DecoherenceManager()
        stats = dm.get_stats()
        assert isinstance(stats, dict)
        assert stats['total_states'] == 0
        assert stats['active'] == 0
        assert stats['decohered'] == 0
        assert isinstance(stats['states'], list)

    def test_get_stats_with_states(self) -> None:
        from qubitcoin.qvm.decoherence import DecoherenceManager
        dm = DecoherenceManager()
        dm.register(1, block_height=0, budget=10)
        dm.register(2, block_height=0, budget=5)
        stats = dm.get_stats()
        assert stats['total_states'] == 2
        assert stats['active'] == 2
        assert stats['decohered'] == 0
        assert len(stats['states']) == 2

    def test_get_stats_after_decoherence(self) -> None:
        from qubitcoin.qvm.decoherence import DecoherenceManager
        dm = DecoherenceManager()
        dm.register(1, block_height=0, budget=2)
        dm.tick(1)
        dm.tick(2)  # budget=0 -> decohered
        stats = dm.get_stats()
        assert stats['active'] == 0
        assert stats['decohered'] == 1

    def test_get_stats_frozen_count(self) -> None:
        from qubitcoin.qvm.decoherence import DecoherenceManager
        dm = DecoherenceManager()
        dm.register(1, block_height=0, budget=100)
        dm.freeze(1)
        stats = dm.get_stats()
        assert stats['frozen'] == 1


class TestRiskNormalizerSerialization:
    """Verify RiskNormalizer.normalize() returns RiskBreakdown with to_dict()."""

    def test_normalize_returns_risk_breakdown(self) -> None:
        from qubitcoin.qvm.risk import RiskNormalizer, RiskBreakdown
        rn = RiskNormalizer()
        result = rn.normalize('qbc1test')
        assert isinstance(result, RiskBreakdown)

    def test_risk_breakdown_has_to_dict(self) -> None:
        from qubitcoin.qvm.risk import RiskNormalizer
        rn = RiskNormalizer()
        result = rn.normalize('qbc1test')
        assert hasattr(result, 'to_dict')
        d = result.to_dict()
        assert isinstance(d, dict)
        assert 'total_score' in d
        assert 'risk_level' in d
        assert 'address' in d

    def test_risk_breakdown_serializable(self) -> None:
        """RiskBreakdown.to_dict() must be JSON-serializable."""
        import json
        from qubitcoin.qvm.risk import RiskNormalizer
        rn = RiskNormalizer()
        result = rn.normalize('qbc1test')
        d = result.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
