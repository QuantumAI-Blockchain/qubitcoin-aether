"""Tests for inheritance protocol endpoint-level logic."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.reversibility.inheritance import (
    InheritanceManager, ClaimStatus
)


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db")
    db.get_current_height.return_value = 100000
    return db


@pytest.fixture()
def manager(mock_db, monkeypatch):
    from qubitcoin.config import Config
    Config.INHERITANCE_ENABLED = True
    Config.INHERITANCE_DEFAULT_INACTIVITY = 2618200
    Config.INHERITANCE_MIN_INACTIVITY = 26182
    Config.INHERITANCE_MAX_INACTIVITY = 95636360
    Config.INHERITANCE_GRACE_PERIOD = 78546
    return InheritanceManager(mock_db)


OWNER = "qbc1owner_ep_000000000000000000000000000000000000"
BENEFICIARY = "qbc1benef_ep_000000000000000000000000000000000000"


class TestSetBeneficiaryEndpoint:
    def test_set_returns_plan_dict(self, manager):
        plan = manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        assert plan.owner_address == OWNER
        assert plan.beneficiary_address == BENEFICIARY
        assert plan.inactivity_blocks == 100000
        assert plan.active is True

    def test_set_validation_error(self, manager):
        with pytest.raises(ValueError):
            manager.set_beneficiary(OWNER, OWNER, 100000, 5000)


class TestHeartbeatEndpoint:
    def test_heartbeat_success(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        assert manager.heartbeat(OWNER, 10000) is True

    def test_heartbeat_no_plan(self, manager):
        assert manager.heartbeat(OWNER, 10000) is False


class TestClaimEndpoint:
    def test_claim_success(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 5000 + 100000)
        assert claim.status == ClaimStatus.PENDING
        assert claim.claim_id is not None

    def test_claim_not_yet_eligible(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        with pytest.raises(ValueError, match="not yet inactive"):
            manager.claim_inheritance(OWNER, BENEFICIARY, 50000)

    def test_claim_wrong_beneficiary(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        with pytest.raises(ValueError, match="not the designated"):
            manager.claim_inheritance(OWNER, "qbc1wrong", 5000 + 100000)


class TestStatusEndpoint:
    def test_owner_status(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        status = manager.get_status(OWNER, 10000)
        assert status["role"] == "owner"
        assert status["blocks_since_heartbeat"] == 5000

    def test_beneficiary_status(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        status = manager.get_status(BENEFICIARY, 10000)
        assert status["role"] == "beneficiary"

    def test_no_status(self, manager):
        assert manager.get_status("qbc1unknown", 10000) is None


class TestClaimCancelFlow:
    def test_cancel_and_recheck_status(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 5000 + 100000)
        manager.cancel_claim(claim.claim_id, OWNER)
        updated = manager.get_claim(claim.claim_id)
        assert updated.status == ClaimStatus.CANCELLED

    def test_execute_matured(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 5000 + 100000)
        executed = manager.execute_matured_claims(claim.grace_expires_block)
        assert len(executed) == 1
        assert executed[0].execution_txid is not None


class TestRemoveBeneficiaryEndpoint:
    def test_remove_existing(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 5000)
        assert manager.remove_beneficiary(OWNER) is True
        assert manager.get_plan(OWNER) is None

    def test_remove_nonexistent(self, manager):
        assert manager.remove_beneficiary(OWNER) is False
