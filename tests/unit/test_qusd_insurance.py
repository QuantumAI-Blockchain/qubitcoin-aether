"""Unit tests for QUSD insurance fund (S18).

Tests the insurance collection, payout, threshold trigger, and stats
methods added to StablecoinEngine.
"""

from decimal import Decimal
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_engine(
    params: Optional[Dict] = None,
    health_row: Optional[tuple] = None,
    insurance_pct: float = 0.05,
    payout_threshold: float = 0.90,
) -> "StablecoinEngine":
    """Create a StablecoinEngine with mocked DB and configurable insurance
    settings.

    Returns:
        (engine, mock_session)
    """
    from qubitcoin.stablecoin.engine import StablecoinEngine

    db = MagicMock()
    session = MagicMock()
    db.get_session.return_value.__enter__ = MagicMock(return_value=session)
    db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    db.get_current_height.return_value = 100

    if health_row is not None:
        session.execute.return_value.fetchone.return_value = health_row

    with patch.object(StablecoinEngine, '_load_params', return_value=params or {}):
        with patch.object(StablecoinEngine, '_ensure_qusd_token'):
            with patch('qubitcoin.stablecoin.engine.Config') as mock_cfg:
                # Propagate all Config attributes we need
                mock_cfg.QUSD_TOKEN_ADDRESS = ''
                mock_cfg.QUSD_RESERVE_ADDRESS = ''
                mock_cfg.QUSD_INSURANCE_FUND_PERCENTAGE = insurance_pct
                mock_cfg.QUSD_INSURANCE_PAYOUT_THRESHOLD = payout_threshold
                mock_cfg.QUSD_INSURANCE_FUND_ADDRESS = 'insurance_treasury_addr'
                eng = StablecoinEngine(
                    db_manager=db, quantum_engine=MagicMock(),
                )
    # Patch Config on the instance for methods that re-read it
    eng._config_patcher = patch('qubitcoin.stablecoin.engine.Config')
    mock_cfg_ctx = eng._config_patcher.start()
    mock_cfg_ctx.QUSD_INSURANCE_FUND_PERCENTAGE = insurance_pct
    mock_cfg_ctx.QUSD_INSURANCE_PAYOUT_THRESHOLD = payout_threshold
    mock_cfg_ctx.QUSD_INSURANCE_FUND_ADDRESS = 'insurance_treasury_addr'
    mock_cfg_ctx.QUSD_TOKEN_ADDRESS = ''
    mock_cfg_ctx.QUSD_RESERVE_ADDRESS = ''
    return eng, session


def _cleanup(eng: "StablecoinEngine") -> None:
    """Stop any patchers attached to the engine."""
    if hasattr(eng, '_config_patcher'):
        eng._config_patcher.stop()


# ===========================================================================
# S18: Insurance Fund Tests
# ===========================================================================


class TestCollectInsurance:
    """Test collect_insurance method."""

    def test_basic_collection(self):
        """5% of a 100 QBC fee => 5 QBC to insurance."""
        eng, _ = _make_engine(insurance_pct=0.05)
        try:
            collected = eng.collect_insurance(100.0)
            assert collected == pytest.approx(5.0)
            assert eng.insurance_fund_balance == pytest.approx(5.0)
        finally:
            _cleanup(eng)

    def test_zero_fee_returns_zero(self):
        """Zero fee collects nothing."""
        eng, _ = _make_engine()
        try:
            assert eng.collect_insurance(0.0) == 0.0
            assert eng.insurance_fund_balance == 0.0
        finally:
            _cleanup(eng)

    def test_negative_fee_returns_zero(self):
        """Negative fee collects nothing."""
        eng, _ = _make_engine()
        try:
            assert eng.collect_insurance(-50.0) == 0.0
        finally:
            _cleanup(eng)

    def test_accumulation_over_multiple_fees(self):
        """Multiple fee collections accumulate in the fund."""
        eng, _ = _make_engine(insurance_pct=0.10)
        try:
            eng.collect_insurance(100.0)  # +10
            eng.collect_insurance(200.0)  # +20
            eng.collect_insurance(50.0)   # +5
            assert eng.insurance_fund_balance == pytest.approx(35.0)
        finally:
            _cleanup(eng)

    def test_collection_history_recorded(self):
        """Each collection is recorded in history."""
        eng, _ = _make_engine(insurance_pct=0.05)
        try:
            eng.collect_insurance(100.0)
            eng.collect_insurance(200.0)
            assert len(eng._insurance_collection_history) == 2
            assert eng._insurance_collection_history[0]['source_fee'] == 100.0
            assert eng._insurance_collection_history[1]['source_fee'] == 200.0
        finally:
            _cleanup(eng)

    def test_zero_percentage_collects_nothing(self):
        """When insurance percentage is 0, nothing is collected."""
        eng, _ = _make_engine(insurance_pct=0.0)
        try:
            collected = eng.collect_insurance(1000.0)
            assert collected == 0.0
            assert eng.insurance_fund_balance == 0.0
        finally:
            _cleanup(eng)

    def test_invalid_percentage_over_one(self):
        """When insurance percentage > 1.0, nothing is collected (guard)."""
        eng, _ = _make_engine(insurance_pct=1.5)
        try:
            collected = eng.collect_insurance(100.0)
            assert collected == 0.0
        finally:
            _cleanup(eng)


class TestPayoutInsurance:
    """Test payout_insurance method."""

    def test_basic_payout(self):
        """Payout deducts from fund balance."""
        eng, _ = _make_engine()
        try:
            eng.insurance_fund_balance = 100.0
            success = eng.payout_insurance(60.0)
            assert success is True
            assert eng.insurance_fund_balance == pytest.approx(40.0)
        finally:
            _cleanup(eng)

    def test_payout_exceeding_balance_fails(self):
        """Payout greater than balance is rejected."""
        eng, _ = _make_engine()
        try:
            eng.insurance_fund_balance = 50.0
            success = eng.payout_insurance(100.0)
            assert success is False
            assert eng.insurance_fund_balance == pytest.approx(50.0)
        finally:
            _cleanup(eng)

    def test_payout_zero_fails(self):
        """Payout of zero amount is rejected."""
        eng, _ = _make_engine()
        try:
            eng.insurance_fund_balance = 100.0
            assert eng.payout_insurance(0.0) is False
        finally:
            _cleanup(eng)

    def test_payout_negative_fails(self):
        """Negative payout is rejected."""
        eng, _ = _make_engine()
        try:
            eng.insurance_fund_balance = 100.0
            assert eng.payout_insurance(-10.0) is False
        finally:
            _cleanup(eng)

    def test_full_payout_drains_fund(self):
        """Paying out entire balance leaves fund at zero."""
        eng, _ = _make_engine()
        try:
            eng.insurance_fund_balance = 75.0
            success = eng.payout_insurance(75.0)
            assert success is True
            assert eng.insurance_fund_balance == pytest.approx(0.0)
        finally:
            _cleanup(eng)

    def test_payout_history_recorded(self):
        """Payouts are recorded in payout history."""
        eng, _ = _make_engine()
        try:
            eng.insurance_fund_balance = 200.0
            eng.payout_insurance(50.0)
            eng.payout_insurance(30.0)
            assert len(eng._insurance_payout_history) == 2
            assert eng._insurance_payout_history[0]['amount'] == 50.0
            assert eng._insurance_payout_history[1]['amount'] == 30.0
        finally:
            _cleanup(eng)


class TestCheckInsurancePayout:
    """Test check_insurance_payout automatic trigger."""

    def test_payout_triggered_below_threshold(self):
        """When reserve ratio < threshold, payout is triggered."""
        eng, session = _make_engine(
            payout_threshold=0.90,
            health_row=('1000000', '0.80', '500000', 10, 3),
        )
        try:
            eng.insurance_fund_balance = 50.0
            triggered = eng.check_insurance_payout()
            assert triggered is True
            assert eng.insurance_fund_balance == pytest.approx(0.0)
        finally:
            _cleanup(eng)

    def test_no_payout_above_threshold(self):
        """When reserve ratio >= threshold, no payout is triggered."""
        eng, session = _make_engine(
            payout_threshold=0.90,
            health_row=('1000000', '0.95', '500000', 10, 0),
        )
        try:
            eng.insurance_fund_balance = 50.0
            triggered = eng.check_insurance_payout()
            assert triggered is False
            assert eng.insurance_fund_balance == pytest.approx(50.0)
        finally:
            _cleanup(eng)

    def test_no_payout_when_fund_empty(self):
        """When fund is empty, check returns False even below threshold."""
        eng, session = _make_engine(
            payout_threshold=0.90,
            health_row=('1000000', '0.50', '500000', 10, 5),
        )
        try:
            eng.insurance_fund_balance = 0.0
            triggered = eng.check_insurance_payout()
            assert triggered is False
        finally:
            _cleanup(eng)

    def test_exact_threshold_no_payout(self):
        """When reserve ratio exactly equals threshold, no payout."""
        eng, session = _make_engine(
            payout_threshold=0.90,
            health_row=('1000000', '0.90', '500000', 10, 0),
        )
        try:
            eng.insurance_fund_balance = 100.0
            triggered = eng.check_insurance_payout()
            assert triggered is False
        finally:
            _cleanup(eng)


class TestGetInsuranceStats:
    """Test get_insurance_stats method."""

    def test_stats_after_collections_and_payouts(self):
        """Stats reflect collection and payout history."""
        eng, _ = _make_engine(insurance_pct=0.10, payout_threshold=0.90)
        try:
            eng.collect_insurance(100.0)   # +10
            eng.collect_insurance(200.0)   # +20
            eng.payout_insurance(15.0)     # -15
            stats = eng.get_insurance_stats()

            assert stats['balance'] == pytest.approx(15.0)
            assert stats['total_collected'] == pytest.approx(30.0)
            assert stats['total_paid_out'] == pytest.approx(15.0)
            assert stats['collection_events'] == 2
            assert stats['payout_events'] == 1
            assert stats['payout_threshold'] == 0.90
            assert stats['collection_percentage'] == 0.10
            assert stats['fund_address'] == 'insurance_treasury_addr'
            assert len(stats['recent_collections']) == 2
            assert len(stats['recent_payouts']) == 1
        finally:
            _cleanup(eng)

    def test_stats_empty_fund(self):
        """Stats for a fresh engine with no activity."""
        eng, _ = _make_engine()
        try:
            stats = eng.get_insurance_stats()
            assert stats['balance'] == 0.0
            assert stats['total_collected'] == 0.0
            assert stats['total_paid_out'] == 0.0
            assert stats['collection_events'] == 0
            assert stats['payout_events'] == 0
        finally:
            _cleanup(eng)


class TestInsuranceConfigIntegration:
    """Test that Config parameters are correctly picked up."""

    def test_config_has_insurance_params(self):
        """Config class exposes insurance fund parameters."""
        from qubitcoin.config import Config
        assert hasattr(Config, 'QUSD_INSURANCE_FUND_PERCENTAGE')
        assert hasattr(Config, 'QUSD_INSURANCE_FUND_ADDRESS')
        assert hasattr(Config, 'QUSD_INSURANCE_PAYOUT_THRESHOLD')

    def test_default_values(self):
        """Default config values match the specification."""
        from qubitcoin.config import Config
        assert Config.QUSD_INSURANCE_FUND_PERCENTAGE == 0.05
        assert Config.QUSD_INSURANCE_PAYOUT_THRESHOLD == 0.90
        assert isinstance(Config.QUSD_INSURANCE_FUND_ADDRESS, str)
