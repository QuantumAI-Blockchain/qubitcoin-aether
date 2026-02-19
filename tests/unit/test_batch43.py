"""
Batch 43 Tests: Bridge Infrastructure
  - FederatedValidatorSet (validators.py)
  - BridgeEventMonitor (monitoring.py)
  - TransferTracker (monitoring.py)
"""

import time
import pytest
from unittest.mock import patch


# ═══════════════════════════════════════════════════════════════════════
#  FederatedValidatorSet Tests
# ═══════════════════════════════════════════════════════════════════════

class TestFederatedValidatorSet:
    """Tests for federated bridge validator management."""

    def _make_set(self, quorum: int = 7, max_v: int = 11):
        from qubitcoin.bridge.validators import FederatedValidatorSet
        return FederatedValidatorSet(
            quorum_threshold=quorum,
            max_validators=max_v,
        )

    def test_register_validator(self):
        vs = self._make_set()
        result = vs.register_validator("addr_a", 10_000.0)
        assert result["success"] is True
        assert result["bond"] == 10_000.0

    def test_register_below_minimum(self):
        vs = self._make_set()
        result = vs.register_validator("addr_a", 5_000.0)
        assert result["success"] is False
        assert "minimum" in result["error"].lower() or "below" in result["error"].lower()

    def test_register_duplicate(self):
        vs = self._make_set()
        vs.register_validator("addr_a", 10_000.0)
        result = vs.register_validator("addr_a", 10_000.0)
        assert result["success"] is False

    def test_register_full_set(self):
        vs = self._make_set(quorum=2, max_v=3)
        vs.register_validator("a", 10_000.0)
        vs.register_validator("b", 10_000.0)
        vs.register_validator("c", 10_000.0)
        result = vs.register_validator("d", 10_000.0)
        assert result["success"] is False
        assert "full" in result["error"].lower()

    def test_increase_bond(self):
        vs = self._make_set()
        vs.register_validator("addr_a", 10_000.0)
        result = vs.increase_bond("addr_a", 5_000.0)
        assert result["success"] is True
        assert result["new_bond"] == 15_000.0

    def test_increase_bond_not_active(self):
        vs = self._make_set()
        result = vs.increase_bond("nonexistent", 1_000.0)
        assert result["success"] is False

    def test_get_active_validators(self):
        vs = self._make_set()
        vs.register_validator("a", 10_000.0)
        vs.register_validator("b", 20_000.0)
        active = vs.get_active_validators()
        assert len(active) == 2

    def test_get_validator(self):
        vs = self._make_set()
        vs.register_validator("addr_a", 15_000.0)
        info = vs.get_validator("addr_a")
        assert info is not None
        assert info["bond_amount"] == 15_000.0
        assert info["status"] == "active"

    def test_get_validator_not_found(self):
        vs = self._make_set()
        assert vs.get_validator("nonexistent") is None

    def test_stats(self):
        vs = self._make_set()
        vs.register_validator("a", 10_000.0)
        vs.register_validator("b", 20_000.0)
        stats = vs.get_stats()
        assert stats["active_validators"] == 2
        assert stats["total_bonded_qbc"] == 30_000.0
        assert stats["quorum_threshold"] == 7


class TestValidatorUnbonding:
    """Tests for validator unbonding lifecycle."""

    def _make_set(self):
        from qubitcoin.bridge.validators import FederatedValidatorSet
        return FederatedValidatorSet(quorum_threshold=2, max_validators=5)

    def test_request_unbond(self):
        vs = self._make_set()
        vs.register_validator("addr_a", 10_000.0)
        result = vs.request_unbond("addr_a", current_block=1000)
        assert result["success"] is True
        assert result["complete_block"] == 1000 + 181_818

    def test_request_unbond_not_active(self):
        vs = self._make_set()
        result = vs.request_unbond("nonexistent", 1000)
        assert result["success"] is False

    def test_finalize_too_early(self):
        vs = self._make_set()
        vs.register_validator("addr_a", 10_000.0)
        vs.request_unbond("addr_a", current_block=1000)
        result = vs.finalize_unbond("addr_a", current_block=2000)
        assert result["success"] is False

    def test_finalize_after_delay(self):
        vs = self._make_set()
        vs.register_validator("addr_a", 10_000.0)
        vs.request_unbond("addr_a", current_block=1000)
        result = vs.finalize_unbond("addr_a", current_block=200_000)
        assert result["success"] is True
        assert result["returned"] == 10_000.0

    def test_re_register_after_removal(self):
        vs = self._make_set()
        vs.register_validator("addr_a", 10_000.0)
        vs.request_unbond("addr_a", current_block=1000)
        vs.finalize_unbond("addr_a", current_block=200_000)
        result = vs.register_validator("addr_a", 15_000.0)
        assert result["success"] is True


class TestValidatorSlashing:
    """Tests for validator slashing mechanics."""

    def _make_set(self):
        from qubitcoin.bridge.validators import FederatedValidatorSet
        return FederatedValidatorSet(quorum_threshold=2, max_validators=5)

    def test_slash_double_sign(self):
        from qubitcoin.bridge.validators import SlashReason
        vs = self._make_set()
        vs.register_validator("addr_a", 10_000.0)
        result = vs.slash_validator("addr_a", SlashReason.DOUBLE_SIGN, evidence="block-42")
        assert result["success"] is True
        assert result["slashed_amount"] == 5_000.0  # 50%
        # 5000 remaining < 10000 MIN_BOND, should be removed
        assert result["status"] == "slashed"

    def test_slash_invalid_proof(self):
        from qubitcoin.bridge.validators import SlashReason
        vs = self._make_set()
        vs.register_validator("addr_a", 20_000.0)
        result = vs.slash_validator("addr_a", SlashReason.INVALID_PROOF)
        assert result["success"] is True
        assert result["slashed_amount"] == 5_000.0  # 25% of 20k
        assert result["remaining_bond"] == 15_000.0
        assert result["status"] == "active"  # still above minimum

    def test_slash_offline(self):
        from qubitcoin.bridge.validators import SlashReason
        vs = self._make_set()
        vs.register_validator("addr_a", 10_000.0)
        result = vs.slash_validator("addr_a", SlashReason.OFFLINE)
        assert result["success"] is True
        assert result["slashed_amount"] == 500.0  # 5%
        # 9500 < 10000, should be slashed out
        assert result["status"] == "slashed"

    def test_slash_not_active(self):
        from qubitcoin.bridge.validators import SlashReason
        vs = self._make_set()
        result = vs.slash_validator("nonexistent", SlashReason.DOUBLE_SIGN)
        assert result["success"] is False

    def test_slash_stats_tracked(self):
        from qubitcoin.bridge.validators import SlashReason
        vs = self._make_set()
        vs.register_validator("addr_a", 20_000.0)
        vs.slash_validator("addr_a", SlashReason.INVALID_PROOF)
        stats = vs.get_stats()
        assert stats["total_slashed_qbc"] == 5_000.0


class TestValidatorAttestations:
    """Tests for attestation and quorum mechanics."""

    def _make_set(self):
        from qubitcoin.bridge.validators import FederatedValidatorSet
        return FederatedValidatorSet(quorum_threshold=3, max_validators=5)

    def test_submit_attestation(self):
        vs = self._make_set()
        vs.register_validator("v1", 10_000.0)
        result = vs.submit_attestation("v1", "event_abc", "sig_1")
        assert result["success"] is True
        assert result["attestation_count"] == 1
        assert result["quorum_reached"] is False

    def test_quorum_reached(self):
        vs = self._make_set()
        for i in range(5):
            vs.register_validator(f"v{i}", 10_000.0)
        vs.submit_attestation("v0", "event_abc", "sig_0")
        vs.submit_attestation("v1", "event_abc", "sig_1")
        result = vs.submit_attestation("v2", "event_abc", "sig_2")
        assert result["quorum_reached"] is True

    def test_duplicate_attestation_rejected(self):
        vs = self._make_set()
        vs.register_validator("v1", 10_000.0)
        vs.submit_attestation("v1", "event_abc", "sig_1")
        result = vs.submit_attestation("v1", "event_abc", "sig_1_again")
        assert result["success"] is False

    def test_attestation_from_non_validator(self):
        vs = self._make_set()
        result = vs.submit_attestation("unknown", "event_abc", "sig")
        assert result["success"] is False

    def test_check_quorum(self):
        vs = self._make_set()
        for i in range(5):
            vs.register_validator(f"v{i}", 10_000.0)
        vs.submit_attestation("v0", "evt", "sig0")
        vs.submit_attestation("v1", "evt", "sig1")
        result = vs.check_quorum("evt")
        assert result["attestation_count"] == 2
        assert result["quorum_reached"] is False

    def test_missed_attestation_auto_slash(self):
        from qubitcoin.bridge.validators import MAX_MISSED_ATTESTATIONS
        vs = self._make_set()
        vs.register_validator("v1", 20_000.0)
        for _ in range(MAX_MISSED_ATTESTATIONS - 1):
            result = vs.record_missed_attestation("v1")
            assert result["auto_slashed"] is False
        result = vs.record_missed_attestation("v1")
        assert result["auto_slashed"] is True

    def test_quorum_reached_count_stat(self):
        vs = self._make_set()
        for i in range(5):
            vs.register_validator(f"v{i}", 10_000.0)
        for i in range(3):
            vs.submit_attestation(f"v{i}", "evt1", f"sig{i}")
        stats = vs.get_stats()
        assert stats["quorum_reached_count"] == 1


# ═══════════════════════════════════════════════════════════════════════
#  BridgeEventMonitor Tests
# ═══════════════════════════════════════════════════════════════════════

class TestBridgeEventMonitor:
    """Tests for multi-source event monitoring."""

    def _make_monitor(self):
        from qubitcoin.bridge.monitoring import BridgeEventMonitor
        return BridgeEventMonitor()

    def test_detect_event(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        result = m.detect_event(
            chain="ethereum",
            tx_hash="0xabc123",
            block_height=100,
            sender="alice",
            receiver="bob",
            amount=1000.0,
            direction=TransferDirection.DEPOSIT,
        )
        assert result["success"] is True
        assert result["duplicate"] is False
        assert result["required_confirmations"] == 20  # ethereum default

    def test_detect_duplicate(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        m.detect_event("ethereum", "0xabc", 100, "alice", "bob", 1000.0, TransferDirection.DEPOSIT)
        result = m.detect_event("ethereum", "0xabc", 100, "alice", "bob", 1000.0, TransferDirection.DEPOSIT)
        assert result["duplicate"] is True
        assert result["verified_sources"] == 2

    def test_confirmation_tracking(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        result = m.detect_event("ethereum", "0xtx1", 100, "a", "b", 500.0, TransferDirection.DEPOSIT)
        event_id = result["event_id"]

        # Not enough confirmations yet
        upd = m.update_confirmations(event_id, current_block_height=110)
        assert upd["confirmations"] == 10
        assert upd["confirmed"] is False

        # Enough confirmations
        upd = m.update_confirmations(event_id, current_block_height=125)
        assert upd["confirmations"] == 25
        assert upd["confirmed"] is True

    def test_is_confirmed(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        result = m.detect_event("qbc", "0xtx1", 50, "a", "b", 100.0, TransferDirection.WITHDRAWAL)
        event_id = result["event_id"]
        assert m.is_confirmed(event_id) is False
        m.update_confirmations(event_id, 60)  # 10 > 6 (qbc needs 6)
        assert m.is_confirmed(event_id) is True

    def test_get_pending_events(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        m.detect_event("ethereum", "0x1", 100, "a", "b", 100.0, TransferDirection.DEPOSIT)
        m.detect_event("polygon", "0x2", 200, "c", "d", 200.0, TransferDirection.DEPOSIT)
        pending = m.get_pending_events()
        assert len(pending) == 2

    def test_get_confirmed_events(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        r = m.detect_event("qbc", "0x1", 100, "a", "b", 100.0, TransferDirection.DEPOSIT)
        m.update_confirmations(r["event_id"], 110)  # 10 > 6 = confirmed
        confirmed = m.get_confirmed_events()
        assert len(confirmed) == 1

    def test_get_event(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        r = m.detect_event("ethereum", "0xabc", 42, "alice", "bob", 999.0, TransferDirection.DEPOSIT)
        event = m.get_event(r["event_id"])
        assert event is not None
        assert event["amount"] == 999.0
        assert event["chain"] == "ethereum"

    def test_get_event_not_found(self):
        m = self._make_monitor()
        assert m.get_event("nonexistent") is None

    def test_update_confirmations_not_found(self):
        m = self._make_monitor()
        result = m.update_confirmations("nonexistent", 100)
        assert result["success"] is False

    def test_stats(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        m.detect_event("ethereum", "0x1", 100, "a", "b", 100.0, TransferDirection.DEPOSIT)
        stats = m.get_stats()
        assert stats["total_events"] == 1
        assert stats["active_events"] == 1

    def test_solana_confirmation_depth(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        m = self._make_monitor()
        r = m.detect_event("solana", "sig1", 500, "a", "b", 50.0, TransferDirection.DEPOSIT)
        assert r["required_confirmations"] == 32


# ═══════════════════════════════════════════════════════════════════════
#  TransferTracker Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTransferTracker:
    """Tests for transfer lifecycle tracking."""

    def _make_tracker(self, **kwargs):
        from qubitcoin.bridge.monitoring import TransferTracker
        return TransferTracker(**kwargs)

    def test_calculate_fee(self):
        t = self._make_tracker(fee_bps=10)
        assert t.calculate_fee(10_000.0) == 10.0  # 0.1%

    def test_initiate_transfer(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker()
        result = t.initiate_transfer(
            event_id="evt1",
            chain="ethereum",
            direction=TransferDirection.DEPOSIT,
            sender="alice",
            receiver="bob",
            amount=1000.0,
        )
        assert result["success"] is True
        assert result["fee"] == 1.0  # 0.1% of 1000
        assert result["net_amount"] == 999.0

    def test_initiate_exceeds_single_limit(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker(single_tx_limit=500.0)
        result = t.initiate_transfer(
            event_id="evt1", chain="eth", direction=TransferDirection.DEPOSIT,
            sender="a", receiver="b", amount=1000.0,
        )
        assert result["success"] is False
        assert "limit" in result["error"].lower()

    def test_initiate_exceeds_daily_limit(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker(daily_limit=100.0, single_tx_limit=200.0)
        t.initiate_transfer("e1", "eth", TransferDirection.DEPOSIT, "a", "b", 80.0)
        result = t.initiate_transfer("e2", "eth", TransferDirection.DEPOSIT, "a", "b", 30.0)
        assert result["success"] is False
        assert "daily" in result["error"].lower()

    def test_initiate_when_paused(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker()
        t.pause("security incident")
        result = t.initiate_transfer("e1", "eth", TransferDirection.DEPOSIT, "a", "b", 100.0)
        assert result["success"] is False
        assert "paused" in result["error"].lower()

    def test_duplicate_event_rejected(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker()
        t.initiate_transfer("evt1", "eth", TransferDirection.DEPOSIT, "a", "b", 100.0)
        result = t.initiate_transfer("evt1", "eth", TransferDirection.DEPOSIT, "a", "b", 100.0)
        assert result["success"] is False

    def test_update_status_lifecycle(self):
        from qubitcoin.bridge.monitoring import TransferDirection, TransferStatus
        t = self._make_tracker()
        r = t.initiate_transfer("evt1", "eth", TransferDirection.DEPOSIT, "a", "b", 1000.0)
        tid = r["transfer_id"]

        t.update_status(tid, TransferStatus.CONFIRMING)
        t.update_status(tid, TransferStatus.CONFIRMED)
        t.update_status(tid, TransferStatus.VALIDATED)
        t.update_status(tid, TransferStatus.EXECUTING)
        result = t.update_status(tid, TransferStatus.COMPLETED, dest_tx_hash="0xdest")
        assert result["success"] is True

        transfer = t.get_transfer(tid)
        assert transfer["status"] == "completed"
        assert transfer["dest_tx_hash"] == "0xdest"
        assert transfer["completed_at"] is not None

    def test_update_status_failed(self):
        from qubitcoin.bridge.monitoring import TransferDirection, TransferStatus
        t = self._make_tracker()
        r = t.initiate_transfer("evt1", "eth", TransferDirection.DEPOSIT, "a", "b", 100.0)
        tid = r["transfer_id"]
        t.update_status(tid, TransferStatus.FAILED, error_message="Timeout")
        transfer = t.get_transfer(tid)
        assert transfer["status"] == "failed"
        assert transfer["error_message"] == "Timeout"

    def test_update_status_not_found(self):
        from qubitcoin.bridge.monitoring import TransferStatus
        t = self._make_tracker()
        result = t.update_status("nonexistent", TransferStatus.COMPLETED)
        assert result["success"] is False

    def test_pause_unpause(self):
        t = self._make_tracker()
        assert t.is_paused is False
        t.pause("maintenance")
        assert t.is_paused is True
        t.unpause()
        assert t.is_paused is False

    def test_get_transfer_by_event(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker()
        t.initiate_transfer("evt1", "eth", TransferDirection.DEPOSIT, "a", "b", 100.0)
        transfer = t.get_transfer_by_event("evt1")
        assert transfer is not None
        assert transfer["amount"] == 100.0

    def test_get_transfer_by_event_not_found(self):
        t = self._make_tracker()
        assert t.get_transfer_by_event("nonexistent") is None

    def test_get_transfers_by_status(self):
        from qubitcoin.bridge.monitoring import TransferDirection, TransferStatus
        t = self._make_tracker()
        t.initiate_transfer("e1", "eth", TransferDirection.DEPOSIT, "a", "b", 100.0)
        t.initiate_transfer("e2", "eth", TransferDirection.DEPOSIT, "a", "b", 200.0)
        initiated = t.get_transfers_by_status(TransferStatus.INITIATED)
        assert len(initiated) == 2

    def test_daily_volume_tracked(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker()
        t.initiate_transfer("e1", "ethereum", TransferDirection.DEPOSIT, "a", "b", 500.0)
        t.initiate_transfer("e2", "ethereum", TransferDirection.DEPOSIT, "a", "b", 300.0)
        vol = t.get_daily_volume("ethereum")
        assert vol == 800.0

    def test_fees_collected(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker(fee_bps=10)
        t.initiate_transfer("e1", "eth", TransferDirection.DEPOSIT, "a", "b", 10_000.0)
        stats = t.get_stats()
        assert stats["total_fees_collected"] == 10.0

    def test_insurance_fund(self):
        t = self._make_tracker()
        result = t.contribute_to_insurance(5_000.0)
        assert result["success"] is True
        assert result["insurance_fund"] == 5_000.0

    def test_insurance_fund_negative(self):
        t = self._make_tracker()
        result = t.contribute_to_insurance(-100.0)
        assert result["success"] is False

    def test_stats(self):
        from qubitcoin.bridge.monitoring import TransferDirection
        t = self._make_tracker()
        t.initiate_transfer("e1", "eth", TransferDirection.DEPOSIT, "a", "b", 100.0)
        stats = t.get_stats()
        assert stats["total_transfers"] == 1
        assert stats["fee_bps"] == 10
        assert stats["paused"] is False
