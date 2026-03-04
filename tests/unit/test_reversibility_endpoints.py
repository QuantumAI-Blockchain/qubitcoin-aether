"""Unit tests for reversibility endpoint logic.

Tests the ReversibilityManager operations that back the 9 reversibility
REST endpoints in rpc.py. Uses mock db_manager since DB isn't available
in unit tests.
"""
import pytest
from unittest.mock import MagicMock

from qubitcoin.reversibility.manager import (
    ReversalRequest,
    ReversalStatus,
    ReversibilityManager,
    SecurityGuardian,
    TransactionWindow,
)


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db")
    return db


@pytest.fixture()
def mgr(mock_db):
    return ReversibilityManager(mock_db, default_window=0)


class TestSetWindowEndpoint:
    """POST /transaction/set-window logic."""

    def test_set_window_valid(self, mgr):
        w = mgr.set_transaction_window("tx_abc", 1000, "sender_addr", 500)
        assert w.window_blocks == 1000

    def test_set_window_zero(self, mgr):
        w = mgr.set_transaction_window("tx_abc", 0, "sender_addr", 500)
        assert w.window_blocks == 0

    def test_set_window_exceeds_max(self, mgr):
        with pytest.raises(ValueError, match="exceeds maximum"):
            mgr.set_transaction_window("tx_abc", 30000, "sender_addr", 500)


class TestTransactionWindowEndpoint:
    """GET /transaction/{txid}/window logic."""

    def test_window_found(self, mgr):
        mgr.set_transaction_window("tx1", 200, "sender", 500)
        w = mgr.get_transaction_window("tx1")
        assert w is not None
        assert w.window_blocks == 200

    def test_window_not_found(self, mgr):
        assert mgr.get_transaction_window("unknown") is None


class TestReversalRequestEndpoint:
    """POST /reversal/request logic."""

    def test_request_within_window(self, mgr):
        mgr.set_transaction_window("tx1", 100, "sender", 500)
        req = mgr.request_reversal("tx1", "requester", "stolen", 550)
        assert req.status == ReversalStatus.PENDING

    def test_request_self_reversal(self, mgr):
        mgr.set_transaction_window("tx1", 100, "sender", 500)
        req = mgr.request_reversal("tx1", "sender", "accident", 550)
        assert req.status == ReversalStatus.APPROVED

    def test_request_outside_window(self, mgr):
        mgr.set_transaction_window("tx1", 100, "sender", 500)
        with pytest.raises(ValueError, match="not eligible"):
            mgr.request_reversal("tx1", "requester", "too late", 700)


class TestApproveReversalEndpoint:
    """POST /reversal/approve/{id} logic."""

    def test_approve_by_guardian(self, mgr):
        mgr.set_transaction_window("tx1", 100, "sender", 500)
        mgr.add_guardian("g1", "Guard", "admin", 100)
        req = mgr.request_reversal("tx1", "victim", "hacked", 550)
        result = mgr.approve_reversal(req.request_id, "g1", 560)
        assert result is True

    def test_approve_non_guardian(self, mgr):
        mgr.set_transaction_window("tx1", 100, "sender", 500)
        req = mgr.request_reversal("tx1", "victim", "hacked", 550)
        with pytest.raises(ValueError, match="not an active guardian"):
            mgr.approve_reversal(req.request_id, "random", 560)


class TestReversalStatusEndpoint:
    """GET /reversal/status/{id} logic."""

    def test_status_found(self, mgr):
        mgr.set_transaction_window("tx1", 100, "sender", 500)
        req = mgr.request_reversal("tx1", "victim", "reason", 550)
        status = mgr.get_reversal_status(req.request_id)
        assert status is not None
        assert status.txid == "tx1"

    def test_status_not_found(self, mgr):
        assert mgr.get_reversal_status("nonexistent") is None


class TestPendingReversalsEndpoint:
    """GET /reversal/pending logic."""

    def test_pending_list(self, mgr):
        mgr.set_transaction_window("tx1", 100, "sender", 500)
        mgr.request_reversal("tx1", "victim", "reason", 550)
        pending = mgr.get_pending_reversals()
        assert len(pending) == 1


class TestGuardianAddEndpoint:
    """POST /guardian/add logic."""

    def test_add_guardian(self, mgr):
        g = mgr.add_guardian("g_addr", "Test Guardian", "admin", 100)
        assert g.address == "g_addr"
        assert g.active is True


class TestGuardianRemoveEndpoint:
    """DELETE /guardian/remove/{address} logic."""

    def test_remove_guardian(self, mgr):
        mgr.add_guardian("g_addr", "Test Guardian", "admin", 100)
        assert mgr.remove_guardian("g_addr", "admin") is True

    def test_remove_nonexistent(self, mgr):
        assert mgr.remove_guardian("unknown", "admin") is False


class TestGuardiansListEndpoint:
    """GET /guardians logic."""

    def test_list_guardians(self, mgr):
        mgr.add_guardian("g1", "G1", "admin", 100)
        mgr.add_guardian("g2", "G2", "admin", 100)
        assert len(mgr.list_guardians()) == 2

    def test_list_excludes_removed(self, mgr):
        mgr.add_guardian("g1", "G1", "admin", 100)
        mgr.remove_guardian("g1", "admin")
        assert len(mgr.list_guardians()) == 0
