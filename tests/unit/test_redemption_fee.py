"""
Tests for dynamic QUSD redemption fee (E18).

Covers: StablecoinEngine.calculate_redemption_fee() and
get_current_redemption_fee_bps() — base fee, proportional increase when
reserve ratio drops, edge cases, and configuration.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from qubitcoin.stablecoin.engine import StablecoinEngine


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_engine() -> StablecoinEngine:
    """Create a StablecoinEngine with mocked dependencies.

    We bypass __init__ since it requires a live DB, quantum engine, etc.
    We create the instance manually and set the attributes that the
    redemption fee methods depend on.
    """
    engine = object.__new__(StablecoinEngine)
    engine.db = MagicMock()
    engine.quantum = MagicMock()
    engine._qvm = None
    engine._qusd_token_addr = ""
    engine._qusd_reserve_addr = ""
    engine.params = {}
    engine.insurance_fund_balance = 0.0
    engine._insurance_collection_history = []
    engine._insurance_payout_history = []
    return engine


# ============================================================================
# calculate_redemption_fee TESTS
# ============================================================================

class TestCalculateRedemptionFee:
    @patch("qubitcoin.stablecoin.engine.Config")
    def test_fully_backed_base_fee(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Reserve ratio >= 1.0 should charge only the base fee."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        fee = mock_engine.calculate_redemption_fee(Decimal("1000"), reserve_ratio=1.0)
        # 1000 * 10 / 10000 = 1.0
        assert fee == Decimal("1.0")

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_over_backed_base_fee(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Reserve ratio > 1.0 should still charge only base fee."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        fee = mock_engine.calculate_redemption_fee(Decimal("1000"), reserve_ratio=1.5)
        assert fee == Decimal("1.0")

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_90_percent_backed(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Reserve ratio = 0.9 should increase fee proportionally."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        # fee_bps = 10 * (1 + (1 - 0.9) * 5) = 10 * 1.5 = 15
        fee = mock_engine.calculate_redemption_fee(Decimal("1000"), reserve_ratio=0.9)
        # 1000 * 15 / 10000 = 1.5
        assert fee == Decimal("1.5")

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_50_percent_backed(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Reserve ratio = 0.5 should significantly increase the fee."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        # fee_bps = 10 * (1 + (1 - 0.5) * 5) = 10 * 3.5 = 35
        fee = mock_engine.calculate_redemption_fee(Decimal("1000"), reserve_ratio=0.5)
        # 1000 * 35 / 10000 = 3.5
        assert fee == Decimal("3.5")

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_zero_reserve_maximum_penalty(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Reserve ratio = 0.0 should produce the maximum fee increase."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        # fee_bps = 10 * (1 + (1 - 0) * 5) = 10 * 6 = 60
        fee = mock_engine.calculate_redemption_fee(Decimal("1000"), reserve_ratio=0.0)
        # 1000 * 60 / 10000 = 6.0
        assert fee == Decimal("6.0")

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_zero_amount(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Zero redemption amount should return zero fee."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        fee = mock_engine.calculate_redemption_fee(Decimal("0"), reserve_ratio=0.5)
        assert fee == Decimal("0")

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_negative_amount(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Negative redemption amount should return zero fee."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        fee = mock_engine.calculate_redemption_fee(Decimal("-100"), reserve_ratio=0.5)
        assert fee == Decimal("0")


# ============================================================================
# get_current_redemption_fee_bps TESTS
# ============================================================================

class TestGetCurrentRedemptionFeeBps:
    @patch("qubitcoin.stablecoin.engine.Config")
    def test_fully_backed_returns_base(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        bps = mock_engine.get_current_redemption_fee_bps(reserve_ratio=1.0)
        assert bps == 10

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_80_percent_backed(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        # 10 * (1 + 0.2 * 5) = 10 * 2 = 20
        bps = mock_engine.get_current_redemption_fee_bps(reserve_ratio=0.8)
        assert bps == 20

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_capped_at_10000(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Fee should never exceed 10000 bps (100%)."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 5000
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 10.0

        # 5000 * (1 + 1.0 * 10) = 5000 * 11 = 55000 -> capped at 10000
        bps = mock_engine.get_current_redemption_fee_bps(reserve_ratio=0.0)
        assert bps == 10000

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_negative_ratio_clamped_to_zero(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Negative reserve ratio should be clamped to 0."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        # Clamped to 0 -> 10 * (1 + 1.0 * 5) = 60
        bps = mock_engine.get_current_redemption_fee_bps(reserve_ratio=-0.5)
        assert bps == 60

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_reads_from_system_health_when_none(
        self, mock_config: MagicMock, mock_engine: StablecoinEngine
    ) -> None:
        """When reserve_ratio is None, should read from get_system_health()."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        # Mock get_system_health to return reserve_backing=0.7
        mock_engine.get_system_health = MagicMock(return_value={
            'reserve_backing': Decimal('0.7'),
        })

        # 10 * (1 + 0.3 * 5) = 10 * 2.5 = 25
        bps = mock_engine.get_current_redemption_fee_bps(reserve_ratio=None)
        assert bps == 25
        mock_engine.get_system_health.assert_called_once()

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_multiplier_zero_no_increase(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Multiplier = 0 means no fee increase regardless of ratio."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 0.0

        bps = mock_engine.get_current_redemption_fee_bps(reserve_ratio=0.5)
        assert bps == 10

    @patch("qubitcoin.stablecoin.engine.Config")
    def test_fee_proportional_scaling(self, mock_config: MagicMock, mock_engine: StablecoinEngine) -> None:
        """Fee should scale linearly with the deficit."""
        mock_config.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        mock_config.QUSD_REDEMPTION_FEE_MULTIPLIER = 10.0

        bps_95 = mock_engine.get_current_redemption_fee_bps(reserve_ratio=0.95)
        bps_90 = mock_engine.get_current_redemption_fee_bps(reserve_ratio=0.90)
        bps_80 = mock_engine.get_current_redemption_fee_bps(reserve_ratio=0.80)

        # 10*(1+0.05*10)=15, 10*(1+0.1*10)=20, 10*(1+0.2*10)=30
        assert bps_95 == 15
        assert bps_90 == 20
        assert bps_80 == 30
        # Verify linearity: diff between 95 and 90 should equal diff 90 and 85
        assert bps_90 - bps_95 == 5  # 5 bps per 5% deficit
