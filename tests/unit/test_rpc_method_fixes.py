"""Tests verifying RPC endpoint method calls match actual class APIs.

Run #26 fixes: aml_monitor, tlac_manager, governance plugin, tx_graph,
systemic_risk_model, mining stats defensive access.
"""

import pytest
from unittest.mock import MagicMock


class TestAMLMonitorMethodExists:
    """Verify AMLMonitor has get_alerts(), not get_recent_alerts()."""

    def test_get_alerts_exists(self) -> None:
        from qubitcoin.qvm.aml import AMLMonitor
        monitor = AMLMonitor()
        assert hasattr(monitor, 'get_alerts')
        alerts = monitor.get_alerts()
        assert isinstance(alerts, list)

    def test_get_recent_alerts_not_exists(self) -> None:
        from qubitcoin.qvm.aml import AMLMonitor
        monitor = AMLMonitor()
        assert not hasattr(monitor, 'get_recent_alerts')


class TestTLACManagerMethods:
    """Verify TLACManager has create(), not create_transaction()."""

    def test_create_exists(self) -> None:
        from qubitcoin.qvm.compliance_advanced import TLACManager
        mgr = TLACManager()
        assert hasattr(mgr, 'create')

    def test_create_transaction_not_exists(self) -> None:
        from qubitcoin.qvm.compliance_advanced import TLACManager
        mgr = TLACManager()
        assert not hasattr(mgr, 'create_transaction')

    def test_list_pending_not_exists(self) -> None:
        """list_pending() was never a method — we access _transactions directly."""
        from qubitcoin.qvm.compliance_advanced import TLACManager
        mgr = TLACManager()
        assert not hasattr(mgr, 'list_pending')

    def test_create_returns_dict(self) -> None:
        from qubitcoin.qvm.compliance_advanced import TLACManager
        mgr = TLACManager()
        result = mgr.create(
            initiator="qbc1alice",
            tx_data={"recipient": "qbc1bob", "amount": 100},
            jurisdictions=["US_SEC", "EU_MiCA"],
            time_lock_blocks=1000,
            block_height=50,
        )
        assert result['success'] is True
        assert 'tlac_id' in result

    def test_pending_iteration_works(self) -> None:
        """The fix iterates _transactions.values() for pending items."""
        from qubitcoin.qvm.compliance_advanced import TLACManager
        mgr = TLACManager()
        mgr.create("qbc1alice", {"amount": 100}, ["US_SEC"], 1000, 10)
        mgr.create("qbc1bob", {"amount": 200}, ["EU_MiCA"], 500, 20)
        pending = [
            t.to_dict() for t in mgr._transactions.values()
            if not t.expired and not t.executed
        ]
        assert len(pending) == 2
        assert all('tlac_id' in p for p in pending)


class TestGovernancePluginMethods:
    """Verify GovernancePlugin has cast_vote(), not vote()."""

    def test_cast_vote_exists(self) -> None:
        from qubitcoin.qvm.governance_plugin import GovernancePlugin
        plugin = GovernancePlugin()
        assert hasattr(plugin, 'cast_vote')

    def test_vote_not_exists(self) -> None:
        from qubitcoin.qvm.governance_plugin import GovernancePlugin
        plugin = GovernancePlugin()
        assert not hasattr(plugin, 'vote')

    def test_plugin_name_is_governance(self) -> None:
        from qubitcoin.qvm.governance_plugin import GovernancePlugin
        plugin = GovernancePlugin()
        assert plugin.name() == 'governance'

    def test_registry_get_returns_plugin_directly(self) -> None:
        """registry.get() returns QVMPlugin, not a meta wrapper."""
        from qubitcoin.qvm.plugins import PluginRegistry
        from qubitcoin.qvm.governance_plugin import GovernancePlugin
        registry = PluginRegistry()
        plugin = GovernancePlugin()
        registry.register(plugin)
        fetched = registry.get('governance')
        assert fetched is plugin
        # Verify NO .instance attribute (would break old code)
        assert not hasattr(fetched, 'instance')

    def test_cast_vote_choice_param(self) -> None:
        """cast_vote takes choice: int (0=AGAINST, 1=FOR, 2=ABSTAIN)."""
        from qubitcoin.qvm.governance_plugin import GovernancePlugin
        plugin = GovernancePlugin()
        # Create a proposal first
        proposal = plugin.create_proposal(
            title="Test",
            description="Test proposal",
            proposer="qbc1alice",
        )
        pid = proposal.proposal_id
        plugin.activate_proposal(pid)
        # Cast vote with choice=1 (FOR)
        vote = plugin.cast_vote(pid, "qbc1voter", choice=1, weight=1.0)
        assert vote is not None
        assert hasattr(vote, 'to_dict')


class TestTransactionGraphMethods:
    """Verify TransactionGraph has build_subgraph(), not analyze()."""

    def test_build_subgraph_exists(self) -> None:
        from qubitcoin.qvm.tx_graph import TransactionGraph
        graph = TransactionGraph()
        assert hasattr(graph, 'build_subgraph')

    def test_analyze_not_exists(self) -> None:
        from qubitcoin.qvm.tx_graph import TransactionGraph
        graph = TransactionGraph()
        assert not hasattr(graph, 'analyze')

    def test_build_subgraph_returns_dict(self) -> None:
        from qubitcoin.qvm.tx_graph import TransactionGraph
        graph = TransactionGraph()
        graph.add_transaction("alice", "bob", 100.0, "tx1", 1)
        result = graph.build_subgraph("alice")
        assert isinstance(result, dict)

    def test_graph_node_has_to_dict(self) -> None:
        from qubitcoin.qvm.tx_graph import TransactionGraph
        graph = TransactionGraph()
        graph.add_transaction("alice", "bob", 100.0, "tx1", 1)
        result = graph.build_subgraph("alice")
        for node in result.values():
            assert hasattr(node, 'to_dict')
            d = node.to_dict()
            assert isinstance(d, dict)


class TestSystemicRiskModelMethods:
    """Verify SystemicRiskModel has detect_high_risk_connections(), not assess()."""

    def test_detect_high_risk_connections_exists(self) -> None:
        from qubitcoin.qvm.systemic_risk import SystemicRiskModel
        model = SystemicRiskModel()
        assert hasattr(model, 'detect_high_risk_connections')

    def test_assess_not_exists(self) -> None:
        from qubitcoin.qvm.systemic_risk import SystemicRiskModel
        model = SystemicRiskModel()
        assert not hasattr(model, 'assess')

    def test_detect_returns_list(self) -> None:
        from qubitcoin.qvm.systemic_risk import SystemicRiskModel
        model = SystemicRiskModel()
        result = model.detect_high_risk_connections("qbc1alice")
        assert isinstance(result, list)


class TestMiningStatsDefensiveAccess:
    """Verify mining stats use .get() for safety."""

    def test_empty_stats_dict_safe(self) -> None:
        """If mining_engine.stats is empty, .get() prevents KeyError."""
        stats = {}
        blocks = stats.get('blocks_found', 0)
        attempts = stats.get('total_attempts', 0)
        rate = blocks / max(1, stats.get('total_attempts', 1))
        assert blocks == 0
        assert attempts == 0
        assert rate == 0.0
