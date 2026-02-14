"""Tests for compliance policy CRUD API endpoints (Batch 14.2).

These tests verify the API contract by calling the ComplianceEngine
directly (same object the RPC endpoints delegate to), avoiding the
need for httpx/TestClient dependencies.
"""
import pytest
from unittest.mock import MagicMock

from qubitcoin.qvm.compliance import (
    ComplianceEngine, KYCLevel, AMLStatus, ComplianceTier,
)


def _engine() -> ComplianceEngine:
    return ComplianceEngine()


class TestAPICreateFlow:
    """Simulate POST /qvm/compliance/policies."""

    def test_create_returns_policy(self):
        engine = _engine()
        p = engine.create_policy('0x' + 'aa' * 20, kyc_level=KYCLevel.ENHANCED)
        assert p.address == '0x' + 'aa' * 20
        assert p.kyc_level == KYCLevel.ENHANCED

    def test_create_with_tier(self):
        engine = _engine()
        p = engine.create_policy('addr', tier=ComplianceTier.INSTITUTIONAL)
        assert p.tier == ComplianceTier.INSTITUTIONAL

    def test_create_with_jurisdiction(self):
        engine = _engine()
        p = engine.create_policy('addr', jurisdiction='EU')
        assert p.jurisdiction == 'EU'


class TestAPIGetFlow:
    """Simulate GET /qvm/compliance/policies/{id}."""

    def test_get_existing(self):
        engine = _engine()
        p = engine.create_policy('addr1')
        retrieved = engine.get_policy(p.policy_id)
        assert retrieved is p

    def test_get_nonexistent(self):
        engine = _engine()
        assert engine.get_policy('no_such_id') is None


class TestAPIUpdateFlow:
    """Simulate PUT /qvm/compliance/policies/{id}."""

    def test_update_kyc_level(self):
        engine = _engine()
        p = engine.create_policy('addr2')
        engine.update_policy(p.policy_id, kyc_level=KYCLevel.FULL)
        assert p.kyc_level == KYCLevel.FULL

    def test_update_aml_status(self):
        engine = _engine()
        p = engine.create_policy('addr3')
        engine.update_policy(p.policy_id, aml_status=AMLStatus.FLAGGED)
        assert p.aml_status == AMLStatus.FLAGGED

    def test_update_daily_limit(self):
        engine = _engine()
        p = engine.create_policy('addr4')
        engine.update_policy(p.policy_id, daily_limit=500_000.0)
        assert p.daily_limit == 500_000.0

    def test_update_sets_updated_at(self):
        engine = _engine()
        p = engine.create_policy('addr5')
        old_ts = p.updated_at
        import time; time.sleep(0.01)
        engine.update_policy(p.policy_id, kyc_level=KYCLevel.ENHANCED)
        assert p.updated_at >= old_ts


class TestAPIDeleteFlow:
    """Simulate DELETE /qvm/compliance/policies/{id}."""

    def test_delete_existing(self):
        engine = _engine()
        p = engine.create_policy('addr6')
        assert engine.delete_policy(p.policy_id) is True
        assert engine.get_policy(p.policy_id) is None

    def test_delete_removes_address_index(self):
        engine = _engine()
        p = engine.create_policy('addr7')
        engine.delete_policy(p.policy_id)
        assert engine.get_policy_for_address('addr7') is None


class TestAPICheckFlow:
    """Simulate GET /qvm/compliance/check/{address}."""

    def test_check_returns_level_and_blocked(self):
        engine = _engine()
        engine.create_policy('addr8', kyc_level=KYCLevel.FULL)
        level = engine.check_compliance('addr8')
        blocked = engine.is_address_blocked('addr8')
        assert level == KYCLevel.FULL
        assert blocked is False

    def test_check_blocked_address(self):
        engine = _engine()
        engine.create_policy('addr9', is_blocked=True)
        assert engine.check_compliance('addr9') == KYCLevel.NONE
        assert engine.is_address_blocked('addr9') is True


class TestAPICircuitBreakerFlow:
    """Simulate GET/POST /qvm/compliance/circuit-breaker."""

    def test_get_status(self):
        engine = _engine()
        d = engine.circuit_breaker.to_dict()
        assert 'threshold' in d
        assert 'is_tripped' in d

    def test_reset(self):
        engine = _engine()
        engine.check_circuit_breaker(90.0)
        assert engine.circuit_breaker.is_tripped is True
        engine.reset_circuit_breaker()
        assert engine.circuit_breaker.is_tripped is False
