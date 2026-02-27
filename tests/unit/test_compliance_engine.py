"""Tests for the Programmable Compliance Policies (PCP) framework (Batch 14.1)."""
import time
import pytest

from qubitcoin.qvm.compliance import (
    ComplianceEngine, CompliancePolicy, ComplianceTier,
    KYCLevel, AMLStatus, CircuitBreaker, TIER_DAILY_LIMITS,
)


class TestPolicyCRUD:
    """Create / read / update / delete compliance policies."""

    def test_create_policy(self):
        engine = ComplianceEngine()
        policy = engine.create_policy('abc123', kyc_level=KYCLevel.ENHANCED)
        assert policy.address == 'abc123'
        assert policy.kyc_level == KYCLevel.ENHANCED
        assert policy.policy_id

    def test_get_policy_by_id(self):
        engine = ComplianceEngine()
        p = engine.create_policy('addr1')
        assert engine.get_policy(p.policy_id) is p

    def test_get_policy_for_address(self):
        engine = ComplianceEngine()
        engine.create_policy('addr2', kyc_level=KYCLevel.FULL)
        result = engine.get_policy_for_address('addr2')
        assert result is not None
        assert result.kyc_level == KYCLevel.FULL

    def test_get_policy_missing_returns_none(self):
        engine = ComplianceEngine()
        assert engine.get_policy_for_address('nonexistent') is None

    def test_global_fallback(self):
        engine = ComplianceEngine()
        engine.create_policy('*', kyc_level=KYCLevel.BASIC)
        result = engine.get_policy_for_address('any_addr')
        assert result is not None
        assert result.kyc_level == KYCLevel.BASIC

    def test_update_policy(self):
        engine = ComplianceEngine()
        p = engine.create_policy('addr3')
        updated = engine.update_policy(p.policy_id, kyc_level=KYCLevel.FULL, is_blocked=True)
        assert updated is not None
        assert updated.kyc_level == KYCLevel.FULL
        assert updated.is_blocked is True

    def test_update_nonexistent_returns_none(self):
        engine = ComplianceEngine()
        assert engine.update_policy('bad_id', kyc_level=3) is None

    def test_delete_policy(self):
        engine = ComplianceEngine()
        p = engine.create_policy('addr4')
        assert engine.delete_policy(p.policy_id) is True
        assert engine.get_policy(p.policy_id) is None

    def test_delete_nonexistent_returns_false(self):
        engine = ComplianceEngine()
        assert engine.delete_policy('nope') is False

    def test_list_policies(self):
        engine = ComplianceEngine()
        engine.create_policy('a')
        engine.create_policy('b')
        engine.create_policy('c')
        assert len(engine.list_policies()) == 3

    def test_policy_to_dict(self):
        engine = ComplianceEngine()
        p = engine.create_policy('addr5', jurisdiction='US')
        d = p.to_dict()
        assert d['address'] == 'addr5'
        assert d['jurisdiction'] == 'US'
        assert 'policy_id' in d


class TestComplianceCheck:
    """Test the check_compliance() method used by QCOMPLIANCE opcode."""

    def test_default_compliance_level(self):
        engine = ComplianceEngine()
        assert engine.check_compliance('unknown') == KYCLevel.BASIC

    def test_enhanced_level(self):
        engine = ComplianceEngine()
        engine.create_policy('addr6', kyc_level=KYCLevel.ENHANCED)
        assert engine.check_compliance('addr6') == KYCLevel.ENHANCED

    def test_blocked_returns_none_level(self):
        engine = ComplianceEngine()
        engine.create_policy('badguy', kyc_level=KYCLevel.FULL, is_blocked=True)
        assert engine.check_compliance('badguy') == KYCLevel.NONE

    def test_is_address_blocked(self):
        engine = ComplianceEngine()
        engine.create_policy('flagged', aml_status=AMLStatus.BLOCKED)
        assert engine.is_address_blocked('flagged') is True

    def test_is_address_not_blocked(self):
        engine = ComplianceEngine()
        engine.create_policy('good', aml_status=AMLStatus.CLEAR)
        assert engine.is_address_blocked('good') is False

    def test_unregistered_not_blocked(self):
        engine = ComplianceEngine()
        assert engine.is_address_blocked('nobody') is False


class TestRiskCache:
    """Test risk score caching with block-based TTL."""

    def test_cache_and_retrieve(self):
        engine = ComplianceEngine()
        engine.set_block_height(100)
        engine.cache_risk('addr7', 42.5)
        assert engine.get_cached_risk('addr7') == 42.5

    def test_cache_miss(self):
        engine = ComplianceEngine()
        assert engine.get_cached_risk('none') is None

    def test_cache_expires_after_ttl(self):
        engine = ComplianceEngine()
        engine.set_block_height(100)
        engine.cache_risk('addr8', 30.0)
        engine.set_block_height(111)  # 11 blocks later > 10 TTL
        assert engine.get_cached_risk('addr8') is None

    def test_cache_valid_within_ttl(self):
        engine = ComplianceEngine()
        engine.set_block_height(100)
        engine.cache_risk('addr9', 20.0)
        engine.set_block_height(109)  # 9 blocks later <= 10 TTL
        assert engine.get_cached_risk('addr9') == 20.0

    def test_invalidate_single(self):
        engine = ComplianceEngine()
        engine.set_block_height(50)
        engine.cache_risk('a', 10.0)
        engine.cache_risk('b', 20.0)
        removed = engine.invalidate_risk_cache('a')
        assert removed == 1
        assert engine.get_cached_risk('a') is None
        assert engine.get_cached_risk('b') == 20.0

    def test_invalidate_all(self):
        engine = ComplianceEngine()
        engine.set_block_height(50)
        engine.cache_risk('x', 1.0)
        engine.cache_risk('y', 2.0)
        removed = engine.invalidate_risk_cache()
        assert removed == 2
        assert engine.get_cached_risk('x') is None


class TestCircuitBreaker:
    """Test auto-circuit breakers for systemic risk."""

    def test_not_tripped_below_threshold(self):
        cb = CircuitBreaker(threshold=80.0)
        assert cb.check(50.0) is False
        assert cb.is_tripped is False

    def test_tripped_at_threshold(self):
        cb = CircuitBreaker(threshold=80.0)
        assert cb.check(80.0) is True
        assert cb.is_tripped is True

    def test_tripped_above_threshold(self):
        cb = CircuitBreaker(threshold=80.0)
        assert cb.check(95.0) is True

    def test_stays_tripped_until_cooldown(self):
        cb = CircuitBreaker(threshold=80.0, cooldown_seconds=1.0)
        cb.check(90.0)
        assert cb.is_tripped is True
        # Before cooldown — should still be tripped (cooldown=1.0s, we check immediately)
        assert cb.check(10.0) is True
        # Manually reset for quick test (avoids 1s sleep)
        cb.reset()
        assert cb.check(10.0) is False

    def test_manual_reset(self):
        cb = CircuitBreaker(threshold=80.0)
        cb.check(90.0)
        assert cb.is_tripped is True
        cb.reset()
        assert cb.is_tripped is False

    def test_engine_circuit_breaker(self):
        engine = ComplianceEngine()
        assert engine.check_circuit_breaker(50.0) is False
        assert engine.check_circuit_breaker(90.0) is True
        engine.reset_circuit_breaker()
        assert engine.circuit_breaker.is_tripped is False

    def test_circuit_breaker_to_dict(self):
        cb = CircuitBreaker(threshold=75.0)
        d = cb.to_dict()
        assert d['threshold'] == 75.0
        assert d['is_tripped'] is False


class TestComplianceTiers:
    """Verify tier daily limits."""

    def test_retail_limit(self):
        assert TIER_DAILY_LIMITS[ComplianceTier.RETAIL] == 10_000.0

    def test_professional_limit(self):
        assert TIER_DAILY_LIMITS[ComplianceTier.PROFESSIONAL] == 1_000_000.0

    def test_institutional_unlimited(self):
        assert TIER_DAILY_LIMITS[ComplianceTier.INSTITUTIONAL] == float('inf')

    def test_tier_enum_values(self):
        assert int(ComplianceTier.RETAIL) == 0
        assert int(ComplianceTier.SOVEREIGN) == 3
