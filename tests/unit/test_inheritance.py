"""Tests for the Inheritance Protocol."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.reversibility.inheritance import (
    InheritanceManager, InheritancePlan, InheritanceClaim, ClaimStatus
)


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db in unit tests")
    return db


@pytest.fixture()
def manager(mock_db, monkeypatch):
    monkeypatch.setenv('INHERITANCE_ENABLED', 'true')
    monkeypatch.setenv('INHERITANCE_DEFAULT_INACTIVITY', '2618200')
    monkeypatch.setenv('INHERITANCE_MIN_INACTIVITY', '26182')
    monkeypatch.setenv('INHERITANCE_MAX_INACTIVITY', '95636360')
    monkeypatch.setenv('INHERITANCE_GRACE_PERIOD', '78546')
    # Reload config
    from qubitcoin.config import Config
    Config.INHERITANCE_ENABLED = True
    Config.INHERITANCE_DEFAULT_INACTIVITY = 2618200
    Config.INHERITANCE_MIN_INACTIVITY = 26182
    Config.INHERITANCE_MAX_INACTIVITY = 95636360
    Config.INHERITANCE_GRACE_PERIOD = 78546
    return InheritanceManager(mock_db)


OWNER = "qbc1owner_address_0000000000000000000000000000000"
BENEFICIARY = "qbc1beneficiary_address_00000000000000000000000"
OTHER = "qbc1other_address_0000000000000000000000000000000"


# ── Initialization ──────────────────────────────────────────────────────

class TestInit:
    def test_defaults(self, manager):
        assert manager._min_inactivity == 26182
        assert manager._max_inactivity == 95636360
        assert manager._default_inactivity == 2618200
        assert manager._grace_period == 78546
        assert manager._plans == {}
        assert manager._claims == {}


# ── Beneficiary Management ──────────────────────────────────────────────

class TestSetBeneficiary:
    def test_set_basic(self, manager):
        plan = manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        assert plan.owner_address == OWNER
        assert plan.beneficiary_address == BENEFICIARY
        assert plan.inactivity_blocks == 2618200
        assert plan.last_heartbeat_block == 1000
        assert plan.active is True

    def test_set_overwrites_existing(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        plan = manager.set_beneficiary(OWNER, OTHER, 100000, 2000)
        assert plan.beneficiary_address == OTHER
        assert plan.inactivity_blocks == 100000
        assert plan.last_heartbeat_block == 2000

    def test_reject_same_address(self, manager):
        with pytest.raises(ValueError, match="same address"):
            manager.set_beneficiary(OWNER, OWNER, 2618200, 1000)

    def test_reject_below_minimum(self, manager):
        with pytest.raises(ValueError, match="below minimum"):
            manager.set_beneficiary(OWNER, BENEFICIARY, 100, 1000)

    def test_reject_above_maximum(self, manager):
        with pytest.raises(ValueError, match="exceeds maximum"):
            manager.set_beneficiary(OWNER, BENEFICIARY, 999999999, 1000)

    def test_minimum_boundary(self, manager):
        plan = manager.set_beneficiary(OWNER, BENEFICIARY, 26182, 1000)
        assert plan.inactivity_blocks == 26182

    def test_maximum_boundary(self, manager):
        plan = manager.set_beneficiary(OWNER, BENEFICIARY, 95636360, 1000)
        assert plan.inactivity_blocks == 95636360


class TestRemoveBeneficiary:
    def test_remove_existing(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        assert manager.remove_beneficiary(OWNER) is True

    def test_remove_nonexistent(self, manager):
        assert manager.remove_beneficiary(OWNER) is False

    def test_remove_already_inactive(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        manager.remove_beneficiary(OWNER)
        assert manager.remove_beneficiary(OWNER) is False

    def test_plan_inactive_after_removal(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        manager.remove_beneficiary(OWNER)
        assert manager.get_plan(OWNER) is None


# ── Heartbeat ───────────────────────────────────────────────────────────

class TestHeartbeat:
    def test_manual_heartbeat(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        assert manager.heartbeat(OWNER, 5000) is True
        plan = manager.get_plan(OWNER)
        assert plan.last_heartbeat_block == 5000

    def test_heartbeat_no_plan(self, manager):
        assert manager.heartbeat(OWNER, 5000) is False

    def test_heartbeat_from_tx(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        manager.update_heartbeat_from_tx(OWNER, 7000)
        plan = manager.get_plan(OWNER)
        assert plan.last_heartbeat_block == 7000

    def test_heartbeat_from_tx_no_plan(self, manager):
        # Should not raise
        manager.update_heartbeat_from_tx(OWNER, 7000)


# ── Inactivity Check ────────────────────────────────────────────────────

class TestInactivityCheck:
    def test_check_inactivity(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        assert manager.check_inactivity(OWNER, 5000) == 4000

    def test_check_inactivity_no_plan(self, manager):
        assert manager.check_inactivity(OWNER, 5000) is None

    def test_is_claimable_not_yet(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        assert manager.is_claimable(OWNER, 100000) is False

    def test_is_claimable_threshold_reached(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        assert manager.is_claimable(OWNER, 1000 + 2618200) is True

    def test_is_claimable_beyond_threshold(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 2618200, 1000)
        assert manager.is_claimable(OWNER, 1000 + 2618200 + 1000) is True

    def test_is_claimable_no_plan(self, manager):
        assert manager.is_claimable(OWNER, 5000) is False


# ── Claims ──────────────────────────────────────────────────────────────

class TestClaimInheritance:
    def test_claim_success(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        assert claim.owner_address == OWNER
        assert claim.beneficiary_address == BENEFICIARY
        assert claim.status == ClaimStatus.PENDING
        assert claim.grace_expires_block == 1000 + 100000 + 78546

    def test_claim_wrong_beneficiary(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        with pytest.raises(ValueError, match="not the designated beneficiary"):
            manager.claim_inheritance(OWNER, OTHER, 1000 + 100000)

    def test_claim_not_yet_claimable(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        with pytest.raises(ValueError, match="not yet inactive"):
            manager.claim_inheritance(OWNER, BENEFICIARY, 50000)

    def test_claim_no_plan(self, manager):
        with pytest.raises(ValueError, match="No active inheritance plan"):
            manager.claim_inheritance(OWNER, BENEFICIARY, 100000)

    def test_duplicate_claim_rejected(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        with pytest.raises(ValueError, match="Pending claim already exists"):
            manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100001)


class TestCancelClaim:
    def test_cancel_by_owner(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        assert manager.cancel_claim(claim.claim_id, OWNER) is True
        updated = manager.get_claim(claim.claim_id)
        assert updated.status == ClaimStatus.CANCELLED

    def test_cancel_by_non_owner(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        with pytest.raises(ValueError, match="Only the owner"):
            manager.cancel_claim(claim.claim_id, BENEFICIARY)

    def test_cancel_not_found(self, manager):
        with pytest.raises(ValueError, match="not found"):
            manager.cancel_claim("nonexistent", OWNER)

    def test_cancel_already_executed(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        # Manually set to executed
        claim.status = ClaimStatus.EXECUTED
        with pytest.raises(ValueError, match="not pending"):
            manager.cancel_claim(claim.claim_id, OWNER)


# ── Execute Matured Claims ──────────────────────────────────────────────

class TestExecuteMaturedClaims:
    def test_execute_after_grace(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        grace_end = claim.grace_expires_block
        executed = manager.execute_matured_claims(grace_end)
        assert len(executed) == 1
        assert executed[0].status == ClaimStatus.EXECUTED
        assert executed[0].execution_txid is not None

    def test_no_execute_before_grace(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        executed = manager.execute_matured_claims(claim.grace_expires_block - 1)
        assert len(executed) == 0

    def test_auto_cancel_if_owner_active(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        # Owner heartbeats during grace period
        manager.heartbeat(OWNER, 1000 + 100000 + 100)
        executed = manager.execute_matured_claims(claim.grace_expires_block)
        assert len(executed) == 0
        updated = manager.get_claim(claim.claim_id)
        assert updated.status == ClaimStatus.CANCELLED

    def test_plan_deactivated_after_execution(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)
        manager.execute_matured_claims(claim.grace_expires_block)
        assert manager.get_plan(OWNER) is None


# ── Status ──────────────────────────────────────────────────────────────

class TestGetStatus:
    def test_owner_status(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        status = manager.get_status(OWNER, 5000)
        assert status is not None
        assert status["role"] == "owner"
        assert status["blocks_since_heartbeat"] == 4000
        assert status["claimable"] is False
        assert status["blocks_until_claimable"] == 96000

    def test_beneficiary_status(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        status = manager.get_status(BENEFICIARY, 5000)
        assert status is not None
        assert status["role"] == "beneficiary"
        assert status["owner_address"] == OWNER

    def test_no_status(self, manager):
        status = manager.get_status(OTHER, 5000)
        assert status is None

    def test_claimable_status(self, manager):
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        status = manager.get_status(OWNER, 1000 + 100000)
        assert status["claimable"] is True
        assert status["blocks_until_claimable"] == 0


# ── End-to-End Flows ────────────────────────────────────────────────────

class TestEndToEnd:
    def test_full_inheritance_flow(self, manager):
        """Full flow: set plan → go inactive → claim → grace → execute."""
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)

        # Owner is active
        assert not manager.is_claimable(OWNER, 50000)

        # Owner becomes inactive
        inactive_height = 1000 + 100000
        assert manager.is_claimable(OWNER, inactive_height)

        # Beneficiary claims
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, inactive_height)
        assert claim.status == ClaimStatus.PENDING

        # Grace period passes
        executed = manager.execute_matured_claims(claim.grace_expires_block)
        assert len(executed) == 1
        assert executed[0].execution_txid is not None

        # Plan is now inactive
        assert manager.get_plan(OWNER) is None

    def test_owner_cancels_during_grace(self, manager):
        """Owner cancels claim during grace period."""
        manager.set_beneficiary(OWNER, BENEFICIARY, 100000, 1000)
        claim = manager.claim_inheritance(OWNER, BENEFICIARY, 1000 + 100000)

        # Owner comes back during grace
        manager.cancel_claim(claim.claim_id, OWNER)
        manager.heartbeat(OWNER, 1000 + 100000 + 10)

        # Grace expires but claim is cancelled
        executed = manager.execute_matured_claims(claim.grace_expires_block)
        assert len(executed) == 0

        # Plan still active
        assert manager.get_plan(OWNER) is not None
