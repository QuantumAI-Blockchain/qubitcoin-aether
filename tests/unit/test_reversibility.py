"""Unit tests for ReversibilityManager — transaction reversal windows, guardians, approvals."""
import pytest
from unittest.mock import MagicMock

from qubitcoin.reversibility.manager import (
    ReversibilityManager,
    ReversalRequest,
    ReversalStatus,
    SecurityGuardian,
    TransactionWindow,
)


@pytest.fixture()
def mock_db():
    """Create a mock DatabaseManager that silently ignores persistence."""
    db = MagicMock()
    db.get_session.side_effect = Exception("no db")
    return db


@pytest.fixture()
def manager(mock_db):
    """Create a ReversibilityManager with defaults."""
    return ReversibilityManager(mock_db, default_window=0)


class TestManagerInit:
    """Test ReversibilityManager initialization."""

    def test_default_window(self, manager):
        assert manager._default_window == 0

    def test_max_window(self, manager):
        assert manager._max_window == 26182

    def test_guardian_threshold(self, manager):
        assert manager._guardian_threshold == 2

    def test_empty_caches(self, manager):
        assert manager._windows == {}
        assert manager._guardians == {}
        assert manager._requests == {}


class TestTransactionWindows:
    """Test setting and querying reversal windows."""

    def test_set_window(self, manager):
        w = manager.set_transaction_window("tx1", 100, "sender_addr", 500)
        assert isinstance(w, TransactionWindow)
        assert w.txid == "tx1"
        assert w.window_blocks == 100
        assert w.set_by == "sender_addr"
        assert w.set_at_block == 500

    def test_get_window(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        w = manager.get_transaction_window("tx1")
        assert w is not None
        assert w.window_blocks == 100

    def test_get_window_nonexistent(self, manager):
        assert manager.get_transaction_window("nonexistent") is None

    def test_set_window_zero_irreversible(self, manager):
        manager.set_transaction_window("tx1", 0, "sender", 500)
        assert not manager.check_reversal_eligible("tx1", 500)

    def test_negative_window_raises(self, manager):
        with pytest.raises(ValueError, match="cannot be negative"):
            manager.set_transaction_window("tx1", -1, "sender", 500)

    def test_exceeds_max_window_raises(self, manager):
        with pytest.raises(ValueError, match="exceeds maximum"):
            manager.set_transaction_window("tx1", 30000, "sender", 500)

    def test_max_window_exact_allowed(self, manager):
        w = manager.set_transaction_window("tx1", 26182, "sender", 500)
        assert w.window_blocks == 26182


class TestReversalEligibility:
    """Test checking whether transactions are eligible for reversal."""

    def test_eligible_within_window(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        assert manager.check_reversal_eligible("tx1", 550) is True

    def test_eligible_at_start(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        assert manager.check_reversal_eligible("tx1", 500) is True

    def test_not_eligible_at_expiry(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        assert manager.check_reversal_eligible("tx1", 600) is False

    def test_not_eligible_after_expiry(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        assert manager.check_reversal_eligible("tx1", 700) is False

    def test_not_eligible_no_window(self, manager):
        assert manager.check_reversal_eligible("unknown_tx", 500) is False

    def test_not_eligible_zero_window(self, manager):
        manager.set_transaction_window("tx1", 0, "sender", 500)
        assert manager.check_reversal_eligible("tx1", 500) is False


class TestGuardianManagement:
    """Test adding, removing, and listing guardians."""

    def test_add_guardian(self, manager):
        g = manager.add_guardian("guardian1", "Cold Wallet", "admin", 100)
        assert isinstance(g, SecurityGuardian)
        assert g.address == "guardian1"
        assert g.label == "Cold Wallet"
        assert g.active is True

    def test_list_guardians(self, manager):
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        manager.add_guardian("g2", "Guard 2", "admin", 100)
        guardians = manager.list_guardians()
        assert len(guardians) == 2

    def test_remove_guardian(self, manager):
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        assert manager.remove_guardian("g1", "admin") is True
        assert len(manager.list_guardians()) == 0

    def test_remove_nonexistent_guardian(self, manager):
        assert manager.remove_guardian("unknown", "admin") is False

    def test_remove_already_inactive(self, manager):
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        manager.remove_guardian("g1", "admin")
        assert manager.remove_guardian("g1", "admin") is False

    def test_is_guardian(self, manager):
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        assert manager.is_guardian("g1") is True
        assert manager.is_guardian("unknown") is False

    def test_is_guardian_after_removal(self, manager):
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        manager.remove_guardian("g1", "admin")
        assert manager.is_guardian("g1") is False


class TestReversalRequests:
    """Test requesting reversals."""

    def test_request_reversal(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "someone", "stolen funds", 550)
        assert isinstance(req, ReversalRequest)
        assert req.txid == "tx1"
        assert req.requester == "someone"
        assert req.reason == "stolen funds"
        assert req.status == ReversalStatus.PENDING

    def test_self_reversal_auto_approves(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "sender", "accidental tx", 550)
        assert req.status == ReversalStatus.APPROVED
        assert "sender" in req.guardian_approvals

    def test_request_reversal_outside_window_raises(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        with pytest.raises(ValueError, match="not eligible"):
            manager.request_reversal("tx1", "someone", "too late", 700)

    def test_request_reversal_no_window_raises(self, manager):
        with pytest.raises(ValueError, match="not eligible"):
            manager.request_reversal("unknown_tx", "someone", "reason", 500)

    def test_request_sets_expiry(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        assert req.window_expires_block == 600  # 500 + 100


class TestGuardianApprovals:
    """Test guardian approval flow."""

    def test_single_approval(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        assert manager.approve_reversal(req.request_id, "g1", 560) is True
        assert "g1" in req.guardian_approvals

    def test_threshold_met_approves(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        manager.add_guardian("g2", "Guard 2", "admin", 100)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        manager.approve_reversal(req.request_id, "g1", 560)
        manager.approve_reversal(req.request_id, "g2", 560)
        assert req.status == ReversalStatus.APPROVED

    def test_below_threshold_stays_pending(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        manager.approve_reversal(req.request_id, "g1", 560)
        # Only 1 approval, threshold is 2
        assert req.status == ReversalStatus.PENDING

    def test_duplicate_approval_raises(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        manager.approve_reversal(req.request_id, "g1", 560)
        with pytest.raises(ValueError, match="already approved"):
            manager.approve_reversal(req.request_id, "g1", 561)

    def test_non_guardian_approval_raises(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        with pytest.raises(ValueError, match="not an active guardian"):
            manager.approve_reversal(req.request_id, "random_addr", 560)

    def test_expired_approval_raises(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.add_guardian("g1", "Guard 1", "admin", 100)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        with pytest.raises(ValueError, match="window expired"):
            manager.approve_reversal(req.request_id, "g1", 700)

    def test_nonexistent_request_raises(self, manager):
        with pytest.raises(ValueError, match="not found"):
            manager.approve_reversal("nonexistent_id", "g1", 560)


class TestExecuteReversal:
    """Test reversal execution."""

    def test_execute_approved(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "sender", "self reverse", 550)
        # Self-reversal auto-approves
        reversal_txid = manager.execute_reversal(req.request_id, 560)
        assert reversal_txid is not None
        assert len(reversal_txid) == 64  # SHA256 hex
        assert req.status == ReversalStatus.EXECUTED
        assert req.executed_at is not None
        assert req.reversal_txid == reversal_txid

    def test_execute_pending_raises(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        with pytest.raises(ValueError, match="not approved"):
            manager.execute_reversal(req.request_id, 560)

    def test_execute_expired_raises(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "sender", "reason", 550)
        with pytest.raises(ValueError, match="window expired"):
            manager.execute_reversal(req.request_id, 700)

    def test_double_execute_raises(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "sender", "reason", 550)
        manager.execute_reversal(req.request_id, 560)
        with pytest.raises(ValueError, match="already executed"):
            manager.execute_reversal(req.request_id, 561)


class TestPendingReversals:
    """Test listing and querying pending reversals."""

    def test_pending_empty(self, manager):
        assert manager.get_pending_reversals() == []

    def test_pending_shows_pending(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.request_reversal("tx1", "someone", "reason", 550)
        pending = manager.get_pending_reversals()
        assert len(pending) == 1

    def test_pending_shows_approved(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.request_reversal("tx1", "sender", "self", 550)  # auto-approved
        pending = manager.get_pending_reversals()
        assert len(pending) == 1
        assert pending[0].status == ReversalStatus.APPROVED

    def test_executed_not_in_pending(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "sender", "self", 550)
        manager.execute_reversal(req.request_id, 560)
        assert len(manager.get_pending_reversals()) == 0


class TestReversalStatus:
    """Test getting reversal status."""

    def test_get_status(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "someone", "reason", 550)
        status = manager.get_reversal_status(req.request_id)
        assert status is not None
        assert status.txid == "tx1"

    def test_get_status_nonexistent(self, manager):
        assert manager.get_reversal_status("nonexistent") is None


class TestExpireStale:
    """Test expiration of stale requests."""

    def test_expire_stale(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.request_reversal("tx1", "someone", "reason", 550)
        count = manager.expire_stale_requests(700)
        assert count == 1

    def test_expire_stale_none(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        manager.request_reversal("tx1", "someone", "reason", 550)
        count = manager.expire_stale_requests(550)
        assert count == 0

    def test_expire_stale_already_executed(self, manager):
        manager.set_transaction_window("tx1", 100, "sender", 500)
        req = manager.request_reversal("tx1", "sender", "self", 550)
        manager.execute_reversal(req.request_id, 560)
        count = manager.expire_stale_requests(700)
        assert count == 0  # Already executed, not expired


class TestEndToEndFlow:
    """Test complete reversal flows."""

    def test_full_self_reversal_flow(self, manager):
        """Sender sets window, requests self-reversal, executes."""
        manager.set_transaction_window("tx_abc", 200, "alice", 1000)
        req = manager.request_reversal("tx_abc", "alice", "sent to wrong addr", 1050)
        assert req.status == ReversalStatus.APPROVED
        txid = manager.execute_reversal(req.request_id, 1060)
        assert txid is not None
        assert req.status == ReversalStatus.EXECUTED

    def test_full_guardian_reversal_flow(self, manager):
        """Third party requests, two guardians approve, execute."""
        manager.set_transaction_window("tx_xyz", 500, "sender", 1000)
        manager.add_guardian("guard_a", "Exchange A", "admin", 100)
        manager.add_guardian("guard_b", "Exchange B", "admin", 100)

        req = manager.request_reversal("tx_xyz", "victim", "hacked", 1100)
        assert req.status == ReversalStatus.PENDING

        manager.approve_reversal(req.request_id, "guard_a", 1110)
        assert req.status == ReversalStatus.PENDING  # Only 1/2

        manager.approve_reversal(req.request_id, "guard_b", 1120)
        assert req.status == ReversalStatus.APPROVED  # 2/2

        txid = manager.execute_reversal(req.request_id, 1130)
        assert txid is not None
        assert req.status == ReversalStatus.EXECUTED
