"""Tests for QUSD Reserve Attestation Engine (Chainlink-style Proof of Reserve)."""

import hashlib
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from qubitcoin.stablecoin.reserve_attestation import (
    ReserveAttestation,
    ReserveAttestationEngine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> ReserveAttestationEngine:
    return ReserveAttestationEngine()


@pytest.fixture
def mock_stablecoin_engine() -> MagicMock:
    """Mock StablecoinEngine returning health data."""
    mock = MagicMock()
    mock.get_system_health.return_value = {
        'total_qusd': 1000000,
        'reserve_backing': 1050000,
    }
    return mock


@pytest.fixture
def engine_with_stablecoin(mock_stablecoin_engine: MagicMock) -> ReserveAttestationEngine:
    return ReserveAttestationEngine(stablecoin_engine=mock_stablecoin_engine)


# ---------------------------------------------------------------------------
# TestGenerateAttestation
# ---------------------------------------------------------------------------

class TestGenerateAttestation:
    """Tests for generate_attestation()."""

    def test_basic_attestation(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(
            block_height=100,
            total_supply=Decimal('1000'),
            reserve_value=Decimal('1200'),
        )
        assert att.block_height == 100
        assert att.total_qusd_supply == Decimal('1000')
        assert att.total_reserve_value == Decimal('1200')
        assert att.reserve_ratio == pytest.approx(1.2, abs=0.001)
        assert att.is_healthy is True
        assert att.deviations == []
        assert att.attester == "system"
        assert att.attestation_id.startswith("attest-100-")
        assert len(att.attestation_hash) == 64  # SHA-256 hex

    def test_under_collateralized(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(
            block_height=50,
            total_supply=Decimal('1000'),
            reserve_value=Decimal('950'),
        )
        assert att.reserve_ratio == pytest.approx(0.95, abs=0.001)
        assert att.is_healthy is False
        assert any("Under-collateralized" in d for d in att.deviations)

    def test_critical_deviation(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(
            block_height=50,
            total_supply=Decimal('1000'),
            reserve_value=Decimal('800'),
        )
        assert att.reserve_ratio == pytest.approx(0.8, abs=0.001)
        assert len(att.deviations) == 2
        assert any("Critical" in d for d in att.deviations)

    def test_custom_attester(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(
            block_height=10,
            total_supply=Decimal('500'),
            reserve_value=Decimal('600'),
            attester="validator_42",
        )
        assert att.attester == "validator_42"

    def test_custom_breakdown(self, engine: ReserveAttestationEngine) -> None:
        breakdown = {"qbc": Decimal('800'), "eth": Decimal('200')}
        att = engine.generate_attestation(
            block_height=10,
            total_supply=Decimal('500'),
            reserve_value=Decimal('1000'),
            reserve_breakdown=breakdown,
        )
        assert att.reserve_breakdown == breakdown

    def test_default_breakdown(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(
            block_height=10,
            total_supply=Decimal('500'),
            reserve_value=Decimal('700'),
        )
        assert att.reserve_breakdown == {"qbc": Decimal('700')}

    def test_zero_supply(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(
            block_height=1,
            total_supply=Decimal('0'),
            reserve_value=Decimal('100'),
        )
        assert att.reserve_ratio == 0.0

    def test_attestation_stored(self, engine: ReserveAttestationEngine) -> None:
        engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        engine.generate_attestation(200, Decimal('2000'), Decimal('2400'))
        assert len(engine._attestations) == 2

    def test_last_attestation_block_updated(self, engine: ReserveAttestationEngine) -> None:
        engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        assert engine._last_attestation_block == 100
        engine.generate_attestation(200, Decimal('2000'), Decimal('2400'))
        assert engine._last_attestation_block == 200

    def test_memory_cap(self, engine: ReserveAttestationEngine) -> None:
        """Only last 1000 attestations kept in memory."""
        for i in range(1050):
            engine.generate_attestation(i, Decimal('1000'), Decimal('1200'))
        assert len(engine._attestations) == 1000
        # Oldest should be trimmed
        assert engine._attestations[0].block_height == 50


# ---------------------------------------------------------------------------
# TestVerifyAttestation
# ---------------------------------------------------------------------------

class TestVerifyAttestation:
    """Tests for verify_attestation()."""

    def test_valid_attestation(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        assert engine.verify_attestation(att) is True

    def test_tampered_supply(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        att.total_qusd_supply = Decimal('999')  # tamper
        assert engine.verify_attestation(att) is False

    def test_tampered_reserve(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        att.total_reserve_value = Decimal('5000')  # tamper
        assert engine.verify_attestation(att) is False

    def test_tampered_hash(self, engine: ReserveAttestationEngine) -> None:
        att = engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        att.attestation_hash = "0" * 64  # tamper
        assert engine.verify_attestation(att) is False


# ---------------------------------------------------------------------------
# TestShouldAttest
# ---------------------------------------------------------------------------

class TestShouldAttest:
    """Tests for should_attest()."""

    def test_first_attestation(self, engine: ReserveAttestationEngine) -> None:
        """First attestation always fires (last_block=0, current >= interval)."""
        assert engine.should_attest(1000) is True

    def test_before_interval(self, engine: ReserveAttestationEngine) -> None:
        engine._last_attestation_block = 500
        assert engine.should_attest(1000) is False

    def test_at_interval(self, engine: ReserveAttestationEngine) -> None:
        engine._last_attestation_block = 0
        assert engine.should_attest(1000) is True

    def test_past_interval(self, engine: ReserveAttestationEngine) -> None:
        engine._last_attestation_block = 100
        assert engine.should_attest(1200) is True

    def test_custom_interval(self) -> None:
        engine = ReserveAttestationEngine()
        engine._attestation_interval = 500
        engine._last_attestation_block = 0
        assert engine.should_attest(499) is False
        assert engine.should_attest(500) is True


# ---------------------------------------------------------------------------
# TestAutoAttest
# ---------------------------------------------------------------------------

class TestAutoAttest:
    """Tests for auto_attest()."""

    def test_auto_attest_success(
        self,
        engine_with_stablecoin: ReserveAttestationEngine,
    ) -> None:
        att = engine_with_stablecoin.auto_attest(1000)
        assert att is not None
        assert att.block_height == 1000
        assert att.total_qusd_supply == Decimal('1000000')
        assert att.total_reserve_value == Decimal('1050000')
        assert att.attester == "auto"

    def test_auto_attest_skips_before_interval(
        self,
        engine_with_stablecoin: ReserveAttestationEngine,
    ) -> None:
        engine_with_stablecoin._last_attestation_block = 500
        att = engine_with_stablecoin.auto_attest(600)
        assert att is None

    def test_auto_attest_no_engine(self, engine: ReserveAttestationEngine) -> None:
        att = engine.auto_attest(1000)
        assert att is None

    def test_auto_attest_zero_supply(
        self,
        mock_stablecoin_engine: MagicMock,
    ) -> None:
        mock_stablecoin_engine.get_system_health.return_value = {
            'total_qusd': 0,
            'reserve_backing': 0,
        }
        engine = ReserveAttestationEngine(stablecoin_engine=mock_stablecoin_engine)
        att = engine.auto_attest(1000)
        assert att is None

    def test_auto_attest_engine_exception(
        self,
        mock_stablecoin_engine: MagicMock,
    ) -> None:
        mock_stablecoin_engine.get_system_health.side_effect = RuntimeError("db down")
        engine = ReserveAttestationEngine(stablecoin_engine=mock_stablecoin_engine)
        att = engine.auto_attest(1000)
        assert att is None


# ---------------------------------------------------------------------------
# TestQueryMethods
# ---------------------------------------------------------------------------

class TestQueryMethods:
    """Tests for get_latest_attestation, get_attestation_by_block, get_attestation_history."""

    def test_get_latest_empty(self, engine: ReserveAttestationEngine) -> None:
        assert engine.get_latest_attestation() is None

    def test_get_latest(self, engine: ReserveAttestationEngine) -> None:
        engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        engine.generate_attestation(200, Decimal('2000'), Decimal('2400'))
        latest = engine.get_latest_attestation()
        assert latest is not None
        assert latest.block_height == 200

    def test_get_by_block_empty(self, engine: ReserveAttestationEngine) -> None:
        assert engine.get_attestation_by_block(100) is None

    def test_get_by_block_exact(self, engine: ReserveAttestationEngine) -> None:
        engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        engine.generate_attestation(200, Decimal('2000'), Decimal('2400'))
        att = engine.get_attestation_by_block(100)
        assert att is not None
        assert att.block_height == 100

    def test_get_by_block_closest(self, engine: ReserveAttestationEngine) -> None:
        engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        engine.generate_attestation(200, Decimal('2000'), Decimal('2400'))
        att = engine.get_attestation_by_block(160)
        assert att is not None
        # Closest to 160 is 200 (distance 40) vs 100 (distance 60)
        assert att.block_height == 200

    def test_history_empty(self, engine: ReserveAttestationEngine) -> None:
        assert engine.get_attestation_history() == []

    def test_history_ordered(self, engine: ReserveAttestationEngine) -> None:
        engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))
        engine.generate_attestation(200, Decimal('2000'), Decimal('2400'))
        engine.generate_attestation(300, Decimal('3000'), Decimal('3600'))
        history = engine.get_attestation_history()
        assert len(history) == 3
        # Most recent first
        assert history[0]['block_height'] == 300
        assert history[2]['block_height'] == 100

    def test_history_limit(self, engine: ReserveAttestationEngine) -> None:
        for i in range(10):
            engine.generate_attestation(i * 100, Decimal('1000'), Decimal('1200'))
        history = engine.get_attestation_history(limit=3)
        assert len(history) == 3
        assert history[0]['block_height'] == 900

    def test_history_fields(self, engine: ReserveAttestationEngine) -> None:
        engine.generate_attestation(100, Decimal('1000'), Decimal('800'))
        history = engine.get_attestation_history()
        entry = history[0]
        assert 'attestation_id' in entry
        assert 'block_height' in entry
        assert 'timestamp' in entry
        assert 'reserve_ratio' in entry
        assert 'is_healthy' in entry
        assert 'attestation_hash' in entry
        assert 'deviations' in entry


# ---------------------------------------------------------------------------
# TestGetStats
# ---------------------------------------------------------------------------

class TestGetStats:
    """Tests for get_stats()."""

    def test_empty_stats(self, engine: ReserveAttestationEngine) -> None:
        stats = engine.get_stats()
        assert stats['total_attestations'] == 0
        assert stats['healthy_attestations'] == 0
        assert stats['unhealthy_attestations'] == 0
        assert stats['average_reserve_ratio'] == 0.0
        assert stats['latest_ratio'] is None
        assert stats['latest_hash'] is None

    def test_stats_with_attestations(self, engine: ReserveAttestationEngine) -> None:
        engine.generate_attestation(100, Decimal('1000'), Decimal('1200'))  # healthy
        engine.generate_attestation(200, Decimal('1000'), Decimal('800'))   # unhealthy
        engine.generate_attestation(300, Decimal('1000'), Decimal('1100'))  # healthy
        stats = engine.get_stats()
        assert stats['total_attestations'] == 3
        assert stats['healthy_attestations'] == 2
        assert stats['unhealthy_attestations'] == 1
        assert stats['average_reserve_ratio'] == pytest.approx(1.0333, abs=0.01)
        assert stats['latest_ratio'] == pytest.approx(1.1, abs=0.01)
        assert stats['latest_hash'] is not None
        assert stats['last_attestation_block'] == 300
