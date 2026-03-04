"""Tests for high-security account endpoint-level logic."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.reversibility.high_security import HighSecurityManager


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db")
    return db


@pytest.fixture()
def manager(mock_db):
    from qubitcoin.config import Config
    Config.SECURITY_POLICY_ENABLED = True
    Config.SECURITY_DAILY_LIMIT_WINDOW = 26182
    return HighSecurityManager(mock_db)


ADDR = "qbc1sec_ep_test_000000000000000000000000000000000"
RCPT = "qbc1recipient_ep_test_0000000000000000000000000000"


class TestSetPolicyEndpoint:
    def test_set_basic(self, manager):
        policy = manager.set_policy(ADDR, daily_limit_qbc=500.0)
        assert policy.address == ADDR
        assert policy.daily_limit_qbc == 500.0

    def test_set_with_whitelist(self, manager):
        policy = manager.set_policy(
            ADDR, require_whitelist=True, whitelist=[RCPT]
        )
        assert policy.require_whitelist is True
        assert RCPT in policy.whitelist

    def test_set_validation_error(self, manager):
        with pytest.raises(ValueError):
            manager.set_policy(ADDR, daily_limit_qbc=-1.0)


class TestGetPolicyEndpoint:
    def test_get_existing(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=500.0)
        p = manager.get_policy(ADDR)
        assert p is not None
        assert p.daily_limit_qbc == 500.0

    def test_get_nonexistent(self, manager):
        assert manager.get_policy(ADDR) is None


class TestRemovePolicyEndpoint:
    def test_remove(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=500.0)
        assert manager.remove_policy(ADDR) is True
        assert manager.get_policy(ADDR) is None

    def test_remove_nonexistent(self, manager):
        assert manager.remove_policy(ADDR) is False


class TestValidateTransaction:
    def test_validate_allowed(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=1000.0)
        result = manager.validate_outgoing_tx(ADDR, RCPT, 100.0, 1000)
        assert result['allowed'] is True

    def test_validate_blocked(self, manager):
        manager.set_policy(ADDR, daily_limit_qbc=100.0)
        manager.record_spending(ADDR, RCPT, 80.0, 1000)
        result = manager.validate_outgoing_tx(ADDR, RCPT, 30.0, 1000)
        assert result['allowed'] is False

    def test_validate_whitelist_blocked(self, manager):
        manager.set_policy(ADDR, require_whitelist=True, whitelist=["qbc1approved"])
        result = manager.validate_outgoing_tx(ADDR, RCPT, 10.0, 1000)
        assert result['allowed'] is False
