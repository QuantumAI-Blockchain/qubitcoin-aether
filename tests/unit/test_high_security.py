"""Tests for High-Security Account Manager."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.reversibility.high_security import (
    HighSecurityManager, SecurityPolicy
)


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db")
    return db


@pytest.fixture()
def manager(mock_db, monkeypatch):
    from qubitcoin.config import Config
    Config.SECURITY_POLICY_ENABLED = True
    Config.SECURITY_DAILY_LIMIT_WINDOW = 26182
    Config.SECURITY_MAX_WHITELIST_SIZE = 100
    Config.SECURITY_MAX_TIME_LOCK = 26182
    return HighSecurityManager(mock_db)


ADDR = "qbc1security_test_address_0000000000000000000000"
RECIPIENT_A = "qbc1recipient_a_000000000000000000000000000000"
RECIPIENT_B = "qbc1recipient_b_000000000000000000000000000000"
RECIPIENT_C = "qbc1recipient_c_000000000000000000000000000000"


# ── Policy Management ──────────────────────────────────────────────────

class TestSetPolicy:
    def test_basic_policy(self, manager):
        policy = manager.set_policy(ADDR, daily_limit_qbc=1000.0)
        assert policy.address == ADDR
        assert policy.daily_limit_qbc == 1000.0
        assert policy.active is True

    def test_full_policy(self, manager):
        policy = manager.set_policy(
            ADDR,
            daily_limit_qbc=500.0,
            require_whitelist=True,
            whitelist=[RECIPIENT_A, RECIPIENT_B],
            time_lock_blocks=100,
            time_lock_threshold_qbc=100.0,
        )
        assert policy.require_whitelist is True
        assert len(policy.whitelist) == 2
        assert policy.time_lock_blocks == 100

    def test_negative_limit_rejected(self, manager):
        with pytest.raises(ValueError, match="negative"):
            manager.set_policy(ADDR, daily_limit_qbc=-1.0)

    def test_negative_time_lock_rejected(self, manager):
        with pytest.raises(ValueError, match="negative"):
            manager.set_policy(ADDR, time_lock_blocks=-1)

    def test_time_lock_without_threshold(self, manager):
        with pytest.raises(ValueError, match="positive threshold"):
            manager.set_policy(ADDR, time_lock_blocks=100, time_lock_threshold_qbc=0.0)

    def test_overwrite_policy(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=1000.0)
        policy = manager.set_policy(ADDR, daily_limit_qbc=500.0)
        assert policy.daily_limit_qbc == 500.0


class TestGetPolicy:
    def test_get_existing(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=1000.0)
        policy = manager.get_policy(ADDR)
        assert policy is not None
        assert policy.daily_limit_qbc == 1000.0

    def test_get_nonexistent(self, manager):
        assert manager.get_policy(ADDR) is None


class TestRemovePolicy:
    def test_remove_existing(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=1000.0)
        assert manager.remove_policy(ADDR) is True
        assert manager.get_policy(ADDR) is None

    def test_remove_nonexistent(self, manager):
        assert manager.remove_policy(ADDR) is False


# ── Transaction Validation ──────────────────────────────────────────────

class TestValidateOutgoingTx:
    def test_no_policy_allows_all(self, manager):
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 9999.0, 1000)
        assert result['allowed'] is True

    def test_whitelist_allows_listed(self, manager):
        manager.set_policy(ADDR, require_whitelist=True, whitelist=[RECIPIENT_A])
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 100.0, 1000)
        assert result['allowed'] is True

    def test_whitelist_blocks_unlisted(self, manager):
        manager.set_policy(ADDR, require_whitelist=True, whitelist=[RECIPIENT_A])
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_B, 100.0, 1000)
        assert result['allowed'] is False
        assert "whitelist" in result['reason'].lower()

    def test_daily_limit_allows_within(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=1000.0)
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 500.0, 1000)
        assert result['allowed'] is True

    def test_daily_limit_blocks_over(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=1000.0)
        manager.record_spending(ADDR, RECIPIENT_A, 800.0, 1000)
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 300.0, 1000)
        assert result['allowed'] is False
        assert "limit exceeded" in result['reason'].lower()

    def test_daily_limit_resets_after_window(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=1000.0)
        manager.record_spending(ADDR, RECIPIENT_A, 900.0, 1000)
        # After window (26182 blocks)
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 500.0, 1000 + 26183)
        assert result['allowed'] is True

    def test_time_lock_triggered(self, manager):
        manager.set_policy(
            ADDR,
            time_lock_blocks=100,
            time_lock_threshold_qbc=500.0,
        )
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 600.0, 1000)
        assert result['allowed'] is True
        assert result.get('time_locked') is True
        assert result.get('time_lock_blocks') == 100

    def test_time_lock_not_triggered_under_threshold(self, manager):
        manager.set_policy(
            ADDR,
            time_lock_blocks=100,
            time_lock_threshold_qbc=500.0,
        )
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 400.0, 1000)
        assert result['allowed'] is True
        assert result.get('time_locked') is None


# ── Spending Tracking ───────────────────────────────────────────────────

class TestSpendingTracking:
    def test_record_and_query(self, manager):
        manager.record_spending(ADDR, RECIPIENT_A, 100.0, 1000)
        assert manager.get_daily_spent(ADDR, 1000) == 100.0

    def test_cumulative_spending(self, manager):
        manager.record_spending(ADDR, RECIPIENT_A, 100.0, 1000)
        manager.record_spending(ADDR, RECIPIENT_B, 200.0, 1001)
        assert manager.get_daily_spent(ADDR, 1001) == 300.0

    def test_spending_outside_window(self, manager):
        manager.record_spending(ADDR, RECIPIENT_A, 100.0, 1000)
        # Query well beyond the window
        assert manager.get_daily_spent(ADDR, 1000 + 26183) == 0.0

    def test_empty_spending(self, manager):
        assert manager.get_daily_spent(ADDR, 1000) == 0.0


# ── Combined Policies ──────────────────────────────────────────────────

class TestCombinedPolicies:
    def test_whitelist_and_limit(self, manager):
        manager.set_policy(
            ADDR,
            daily_limit_qbc=1000.0,
            require_whitelist=True,
            whitelist=[RECIPIENT_A],
        )
        # Whitelist check first — blocked
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_B, 100.0, 1000)
        assert result['allowed'] is False

        # Within whitelist, within limit — allowed
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 100.0, 1000)
        assert result['allowed'] is True

    def test_limit_and_time_lock(self, manager):
        manager.set_policy(
            ADDR,
            daily_limit_qbc=1000.0,
            time_lock_blocks=50,
            time_lock_threshold_qbc=500.0,
        )
        # Large amount: allowed but time-locked
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 600.0, 1000)
        assert result['allowed'] is True
        assert result.get('time_locked') is True

        # Over daily limit: blocked
        manager.record_spending(ADDR, RECIPIENT_A, 900.0, 1000)
        result = manager.validate_outgoing_tx(ADDR, RECIPIENT_A, 200.0, 1000)
        assert result['allowed'] is False
