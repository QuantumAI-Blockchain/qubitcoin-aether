"""Tests for Bridge Liquidity Pool RPC endpoints and node wiring."""

import pytest
from unittest.mock import MagicMock, patch

from qubitcoin.bridge.liquidity_pool import BridgeLiquidityPool, LPPosition


class TestBridgeLPWiring:
    """Verify BridgeLiquidityPool is importable from bridge package."""

    def test_import_from_bridge_package(self) -> None:
        from qubitcoin.bridge import BridgeLiquidityPool
        assert BridgeLiquidityPool is not None

    def test_bridge_lp_in_all(self) -> None:
        import qubitcoin.bridge as bridge_mod
        assert 'BridgeLiquidityPool' in bridge_mod.__all__


class TestGATReasonerWiring:
    """Verify GATReasoner is importable from aether package."""

    def test_import_from_aether_package(self) -> None:
        from qubitcoin.aether import GATReasoner
        assert GATReasoner is not None

    def test_import_gat_layer_from_aether(self) -> None:
        from qubitcoin.aether import GATLayer
        assert GATLayer is not None

    def test_gat_reasoner_in_all(self) -> None:
        import qubitcoin.aether as aether_mod
        assert 'GATReasoner' in aether_mod.__all__
        assert 'GATLayer' in aether_mod.__all__


class TestBridgeLPEndpointLogic:
    """Test the LP pool operations used by RPC endpoints."""

    def setup_method(self) -> None:
        self.pool = BridgeLiquidityPool(reward_rate_bps=500, min_deposit=10.0)

    def test_add_liquidity_returns_position(self) -> None:
        pos = self.pool.add_liquidity("qbc1alice", "ethereum", 100.0)
        assert pos.provider == "qbc1alice"
        assert pos.chain == "ethereum"
        assert pos.amount == 100.0

    def test_remove_liquidity_returns_tuple(self) -> None:
        self.pool.add_liquidity("qbc1alice", "ethereum", 100.0)
        withdrawn, rewards = self.pool.remove_liquidity("qbc1alice", "ethereum", 50.0)
        assert withdrawn == 50.0
        assert isinstance(rewards, float)

    def test_get_pool_stats_shape(self) -> None:
        self.pool.add_liquidity("qbc1alice", "ethereum", 100.0)
        stats = self.pool.get_pool_stats()
        assert 'total_liquidity' in stats
        assert 'total_providers' in stats
        assert 'chains' in stats
        assert 'ethereum' in stats['chains']

    def test_calculate_rewards_returns_dict(self) -> None:
        self.pool.add_liquidity("qbc1alice", "ethereum", 100.0)
        rewards = self.pool.calculate_rewards("qbc1alice")
        assert isinstance(rewards, dict)

    def test_get_provider_positions_shape(self) -> None:
        self.pool.add_liquidity("qbc1alice", "ethereum", 100.0)
        self.pool.add_liquidity("qbc1alice", "polygon", 50.0)
        positions = self.pool.get_provider_positions("qbc1alice")
        assert len(positions) == 2
        chains = {p['chain'] for p in positions}
        assert chains == {'ethereum', 'polygon'}

    def test_distribute_rewards_returns_count(self) -> None:
        self.pool.add_liquidity("qbc1alice", "ethereum", 100.0)
        count = self.pool.distribute_rewards()
        assert isinstance(count, int)


def _make_stablecoin_engine():
    """Helper: create a StablecoinEngine with properly mocked DB."""
    from qubitcoin.stablecoin.engine import StablecoinEngine
    mock_db = MagicMock()
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.__iter__ = MagicMock(return_value=iter([]))
    result_mock.fetchone.return_value = ('qusd-token-id', True)
    session.execute.return_value = result_mock
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    return StablecoinEngine(mock_db, MagicMock())


class TestFlashLoanEndpointLogic:
    """Test flash loan operations used by RPC endpoints."""

    def setup_method(self) -> None:
        self.engine = _make_stablecoin_engine()

    def test_initiate_flash_loan_returns_loan(self) -> None:
        from decimal import Decimal
        loan = self.engine.initiate_flash_loan("qbc1bob", Decimal("1000"))
        assert loan.borrower == "qbc1bob"
        assert loan.amount == Decimal("1000")
        assert loan.fee > 0

    def test_complete_flash_loan_returns_bool(self) -> None:
        from decimal import Decimal
        loan = self.engine.initiate_flash_loan("qbc1bob", Decimal("1000"))
        result = self.engine.complete_flash_loan(loan.id, loan.amount + loan.fee)
        assert result is True

    def test_get_flash_loan_stats_shape(self) -> None:
        stats = self.engine.get_flash_loan_stats()
        assert 'enabled' in stats
        assert 'fee_bps' in stats
        assert 'total_loans' in stats
        assert 'active_loans' in stats

    def test_get_active_flash_loan(self) -> None:
        from decimal import Decimal
        loan = self.engine.initiate_flash_loan("qbc1carol", Decimal("500"))
        fetched = self.engine.get_active_flash_loan(loan.id)
        assert fetched is not None
        assert fetched.id == loan.id

    def test_get_active_flash_loan_returns_none_after_repay(self) -> None:
        from decimal import Decimal
        loan = self.engine.initiate_flash_loan("qbc1carol", Decimal("500"))
        self.engine.complete_flash_loan(loan.id, loan.amount + loan.fee)
        fetched = self.engine.get_active_flash_loan(loan.id)
        assert fetched is None


class TestNeuralReasonerEndpointLogic:
    """Test GATReasoner operations used by RPC endpoints."""

    def test_get_stats_shape(self) -> None:
        from qubitcoin.aether.neural_reasoner import GATReasoner
        reasoner = GATReasoner(hidden_dim=32, n_heads=2)
        stats = reasoner.get_stats()
        assert 'training_mode' in stats
        assert 'has_pytorch' in stats
        assert 'accuracy' in stats
        assert 'backprop_steps' in stats

    def test_get_accuracy_returns_float(self) -> None:
        from qubitcoin.aether.neural_reasoner import GATReasoner
        reasoner = GATReasoner()
        acc = reasoner.get_accuracy()
        assert isinstance(acc, float)
        assert 0.0 <= acc <= 1.0

    def test_training_mode_property(self) -> None:
        from qubitcoin.aether.neural_reasoner import GATReasoner
        reasoner = GATReasoner()
        mode = reasoner.training_mode
        assert mode in ('backprop', 'evolutionary', 'rust_backprop')


class TestContractValidationEndpointLogic:
    """Test contract validation used by RPC endpoint."""

    def test_validate_all_runs(self) -> None:
        from pathlib import Path
        import sys
        scripts_dir = Path(__file__).parent.parent.parent / "scripts" / "deploy"
        sys.path.insert(0, str(scripts_dir))
        from validate_contracts import validate_all
        contracts_root = Path(__file__).parent.parent.parent / "src" / "qubitcoin" / "contracts" / "solidity"
        if contracts_root.exists():
            results, summary = validate_all(contracts_root)
            assert summary['total_files'] > 0
            assert summary['passed'] >= 0

    def test_compute_deploy_order_runs(self) -> None:
        from pathlib import Path
        import sys
        scripts_dir = Path(__file__).parent.parent.parent / "scripts" / "deploy"
        sys.path.insert(0, str(scripts_dir))
        from validate_contracts import validate_all, compute_deploy_order
        contracts_root = Path(__file__).parent.parent.parent / "src" / "qubitcoin" / "contracts" / "solidity"
        if contracts_root.exists():
            results, _ = validate_all(contracts_root)
            order = compute_deploy_order(results)
            assert isinstance(order, list)
            assert len(order) > 0
