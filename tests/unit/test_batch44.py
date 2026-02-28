"""
Batch 44 Tests: QUSD Reserve Building & Safety
  - ReserveFeeRouter (reserve_manager.py)
  - ReserveMilestoneEnforcer (reserve_manager.py)
  - CrossChainQUSDAggregator (reserve_manager.py)
  - ReserveVerifier (reserve_verification.py)
"""

import pytest
from decimal import Decimal


def _dec(val: str) -> Decimal:
    """Helper: parse str/Decimal-like values for comparison."""
    return Decimal(val)


# ═══════════════════════════════════════════════════════════════════════
#  ReserveFeeRouter Tests
# ═══════════════════════════════════════════════════════════════════════

class TestReserveFeeRouter:
    """Tests for protocol fee routing to QUSD reserves."""

    def _make_router(self, **kwargs):
        from qubitcoin.stablecoin.reserve_manager import ReserveFeeRouter
        return ReserveFeeRouter(**kwargs)

    def test_route_bridge_fee(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        result = r.route_fee(
            source=FeeSource.BRIDGE_FEE,
            total_fee_qbc=100.0,
            block_height=1000,
            tx_hash="0xabc",
        )
        assert result["success"] is True
        # Bridge fees: 100% to reserves (Decimal values returned as strings)
        assert _dec(result["reserve_amount"]) == Decimal('100')
        assert _dec(result["treasury_amount"]) == Decimal('0')

    def test_route_aether_chat_fee(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        result = r.route_fee(
            source=FeeSource.AETHER_CHAT_FEE,
            total_fee_qbc=10.0,
            block_height=1000,
            tx_hash="0xdef",
        )
        assert result["success"] is True
        # Aether fees: 10% to reserves
        assert _dec(result["reserve_amount"]) == Decimal('1')
        assert _dec(result["treasury_amount"]) == Decimal('9')

    def test_route_contract_deploy_fee(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        result = r.route_fee(
            source=FeeSource.CONTRACT_DEPLOY_FEE,
            total_fee_qbc=50.0,
            block_height=2000,
            tx_hash="0x123",
        )
        # Deploy fees: 10% to reserves
        assert _dec(result["reserve_amount"]) == Decimal('5')
        assert _dec(result["treasury_amount"]) == Decimal('45')

    def test_route_lp_fee(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        result = r.route_fee(
            source=FeeSource.LP_FEE,
            total_fee_qbc=200.0,
            block_height=3000,
            tx_hash="0x456",
        )
        # LP fees: 50% to reserves
        assert _dec(result["reserve_amount"]) == Decimal('100')
        assert _dec(result["treasury_amount"]) == Decimal('100')

    def test_route_zero_fee_rejected(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        result = r.route_fee(FeeSource.BRIDGE_FEE, 0.0, 1000, "0x0")
        assert result["success"] is False

    def test_route_negative_fee_rejected(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        result = r.route_fee(FeeSource.BRIDGE_FEE, -10.0, 1000, "0x0")
        assert result["success"] is False

    def test_usd_value_tracked(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router(qbc_usd_price=2.0)
        r.route_fee(FeeSource.BRIDGE_FEE, 100.0, 1000, "0xabc")
        stats = r.get_stats()
        assert _dec(stats["total_inflow_usd"]) == Decimal('200')  # 100 QBC * $2

    def test_set_qbc_price(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router(qbc_usd_price=1.0)
        r.set_qbc_price(5.0)
        r.route_fee(FeeSource.BRIDGE_FEE, 10.0, 1000, "0x1")
        stats = r.get_stats()
        assert _dec(stats["total_inflow_usd"]) == Decimal('50')  # 10 * $5

    def test_custom_allocation(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        r.set_allocation(FeeSource.AETHER_CHAT_FEE, 0.50)
        result = r.route_fee(FeeSource.AETHER_CHAT_FEE, 100.0, 1000, "0x1")
        assert _dec(result["reserve_amount"]) == Decimal('50')

    def test_set_allocation_invalid(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        result = r.set_allocation(FeeSource.BRIDGE_FEE, 1.5)
        assert result["success"] is False

    def test_get_inflows(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        r.route_fee(FeeSource.BRIDGE_FEE, 100.0, 1000, "0xa")
        r.route_fee(FeeSource.LP_FEE, 200.0, 2000, "0xb")
        inflows = r.get_inflows()
        assert len(inflows) == 2

    def test_get_inflows_filtered(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        r.route_fee(FeeSource.BRIDGE_FEE, 100.0, 1000, "0xa")
        r.route_fee(FeeSource.LP_FEE, 200.0, 2000, "0xb")
        inflows = r.get_inflows(source=FeeSource.BRIDGE_FEE)
        assert len(inflows) == 1

    def test_reserve_balance(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        r.route_fee(FeeSource.BRIDGE_FEE, 100.0, 1000, "0xa")
        r.route_fee(FeeSource.BRIDGE_FEE, 50.0, 2000, "0xb")
        assert r.get_reserve_balance() == Decimal('150.0')

    def test_by_source_tracking(self):
        from qubitcoin.stablecoin.reserve_manager import FeeSource
        r = self._make_router()
        r.route_fee(FeeSource.BRIDGE_FEE, 100.0, 1000, "0xa")
        r.route_fee(FeeSource.LP_FEE, 200.0, 2000, "0xb")  # 50% = 100
        stats = r.get_stats()
        assert _dec(stats["by_source"]["bridge_fee"]) == Decimal('100')
        assert _dec(stats["by_source"]["lp_fee"]) == Decimal('100')

    def test_stats(self):
        r = self._make_router()
        stats = r.get_stats()
        assert stats["total_inflows"] == 0
        assert _dec(stats["reserve_balance_qbc"]) == Decimal('0')


# ═══════════════════════════════════════════════════════════════════════
#  ReserveMilestoneEnforcer Tests
# ═══════════════════════════════════════════════════════════════════════

class TestReserveMilestoneEnforcer:
    """Tests for year-based reserve backing enforcement."""

    def _make_enforcer(self, **kwargs):
        from qubitcoin.stablecoin.reserve_manager import ReserveMilestoneEnforcer
        return ReserveMilestoneEnforcer(**kwargs)

    def test_chain_year_calculation(self):
        e = self._make_enforcer()
        assert e.get_chain_year(0) == 1
        assert e.get_chain_year(9_565_090) == 2
        assert e.get_chain_year(19_130_180) == 3

    def test_required_backing_year_1(self):
        e = self._make_enforcer()
        assert e.get_required_backing(1000) == 5.0

    def test_required_backing_year_3(self):
        e = self._make_enforcer()
        # Year 3 starts at block ~19M
        block = 9_565_090 * 2 + 100
        assert e.get_required_backing(block) == 15.0

    def test_required_backing_year_10(self):
        e = self._make_enforcer()
        block = 9_565_090 * 9 + 100  # Year 10
        assert e.get_required_backing(block) == 100.0

    def test_compliant_when_above_minimum(self):
        e = self._make_enforcer(total_minted_qusd=1_000_000.0)
        e.set_reserve_value(60_000.0)  # 6% > 5% (Year 1 minimum)
        result = e.check_compliance(current_block=1000)
        assert result["compliant"] is True
        assert result["actual_backing_pct"] == 6.0

    def test_violation_below_minimum(self):
        e = self._make_enforcer(total_minted_qusd=1_000_000.0)
        e.set_reserve_value(30_000.0)  # 3% < 5% (Year 1 minimum)
        result = e.check_compliance(current_block=1000)
        assert result["compliant"] is False
        assert result["deficit_pct"] == 2.0

    def test_emergency_halt_minting(self):
        e = self._make_enforcer(total_minted_qusd=1_000_000.0)
        e.set_reserve_value(0.0)  # 0% backing, deficit >= 10%
        result = e.check_compliance(current_block=1000)
        assert "HALT_MINTING" in result["emergency_actions"]
        assert e.can_mint() is False

    def test_emergency_increase_fees(self):
        e = self._make_enforcer(total_minted_qusd=1_000_000.0)
        e.set_reserve_value(0.0)  # deficit >= 5%
        result = e.check_compliance(current_block=1000)
        assert "INCREASE_FEES" in result["emergency_actions"]

    def test_clear_emergency(self):
        e = self._make_enforcer(total_minted_qusd=1_000_000.0)
        e.set_reserve_value(0.0)
        e.check_compliance(current_block=1000)
        assert e.can_mint() is False
        e.clear_emergency()
        assert e.can_mint() is True

    def test_milestone_event_5pct(self):
        e = self._make_enforcer()
        result = e.record_milestone_event(5.0, block=100_000)
        assert result is not None
        assert 5.0 in result["milestones_crossed"]

    def test_milestone_not_re_recorded(self):
        e = self._make_enforcer()
        e.record_milestone_event(5.0, block=100_000)
        result = e.record_milestone_event(5.0, block=200_000)
        assert result is None  # already crossed

    def test_multiple_milestones_at_once(self):
        e = self._make_enforcer()
        result = e.record_milestone_event(50.0, block=100_000)
        assert result is not None
        # Should cross 5, 15, 30, and 50
        assert 5.0 in result["milestones_crossed"]
        assert 15.0 in result["milestones_crossed"]
        assert 30.0 in result["milestones_crossed"]
        assert 50.0 in result["milestones_crossed"]

    def test_violation_history(self):
        e = self._make_enforcer(total_minted_qusd=1_000_000.0)
        e.set_reserve_value(30_000.0)
        e.check_compliance(1000)
        e.check_compliance(2000)
        stats = e.get_stats()
        assert stats["violation_count"] == 2

    def test_backing_100_when_no_minted(self):
        e = self._make_enforcer(total_minted_qusd=0.0)
        assert e.get_current_backing() == 100.0

    def test_stats(self):
        e = self._make_enforcer()
        stats = e.get_stats()
        assert _dec(stats["total_minted_qusd"]) == Decimal('3300000000')
        assert stats["minting_halted"] is False


# ═══════════════════════════════════════════════════════════════════════
#  CrossChainQUSDAggregator Tests
# ═══════════════════════════════════════════════════════════════════════

class TestCrossChainQUSDAggregator:
    """Tests for cross-chain QUSD supply aggregation."""

    def _make_aggregator(self):
        from qubitcoin.stablecoin.reserve_manager import CrossChainQUSDAggregator
        return CrossChainQUSDAggregator()

    def test_update_chain_supply(self):
        a = self._make_aggregator()
        result = a.update_chain_supply("ethereum", 1_000_000.0)
        assert result["success"] is True
        assert a.get_total_supply() == Decimal('1000000.0')

    def test_multi_chain_total(self):
        a = self._make_aggregator()
        a.update_chain_supply("ethereum", 1_000_000.0)
        a.update_chain_supply("polygon", 500_000.0)
        a.update_chain_supply("solana", 300_000.0)
        assert a.get_total_supply() == Decimal('1800000.0')

    def test_bridge_transfer_fee(self):
        a = self._make_aggregator()
        result = a.record_bridge_transfer(10_000.0)
        assert result["success"] is True
        assert _dec(result["fee"]) == Decimal('5')
        assert _dec(result["net_amount"]) == Decimal('9995')

    def test_bridge_fees_accumulate(self):
        a = self._make_aggregator()
        a.record_bridge_transfer(10_000.0)
        a.record_bridge_transfer(20_000.0)
        stats = a.get_stats()
        assert stats["bridge_transfers"] == 2

    def test_get_chain_supply(self):
        a = self._make_aggregator()
        a.update_chain_supply("ethereum", 1_000_000.0)
        assert a.get_chain_supply("ethereum") == Decimal('1000000.0')
        assert a.get_chain_supply("nonexistent") == Decimal('0')

    def test_get_all_chains(self):
        a = self._make_aggregator()
        a.update_chain_supply("ethereum", 1_000.0)
        a.update_chain_supply("solana", 500.0)
        chains = a.get_all_chain_supplies()
        assert len(chains) == 2

    def test_negative_supply_clamped(self):
        a = self._make_aggregator()
        a.update_chain_supply("ethereum", -100.0)
        assert a.get_chain_supply("ethereum") == Decimal('0')

    def test_stats(self):
        a = self._make_aggregator()
        stats = a.get_stats()
        assert stats["bridge_fee_bps"] == 5
        assert stats["chain_count"] == 0


# ═══════════════════════════════════════════════════════════════════════
#  ReserveVerifier Tests
# ═══════════════════════════════════════════════════════════════════════

class TestReserveVerifier:
    """Tests for public reserve verification and snapshots."""

    def _make_verifier(self, **kwargs):
        from qubitcoin.stablecoin.reserve_verification import ReserveVerifier
        return ReserveVerifier(**kwargs)

    def test_should_snapshot(self):
        v = self._make_verifier(snapshot_interval_blocks=100)
        assert v.should_snapshot(100) is True
        v.create_snapshot(100, 3_300_000_000.0, 165_000_000.0, 1, 5.0)
        assert v.should_snapshot(150) is False
        assert v.should_snapshot(200) is True

    def test_create_snapshot(self):
        v = self._make_verifier()
        snap = v.create_snapshot(
            block_height=1000,
            total_minted=3_300_000_000.0,
            reserve_usd=165_000_000.0,
            chain_year=1,
            required_backing=5.0,
        )
        assert snap.backing_pct == 5.0
        assert snap.compliant is True

    def test_snapshot_non_compliant(self):
        v = self._make_verifier()
        snap = v.create_snapshot(
            block_height=1000,
            total_minted=3_300_000_000.0,
            reserve_usd=100_000_000.0,  # ~3%, below 5%
            chain_year=1,
            required_backing=5.0,
        )
        assert snap.compliant is False

    def test_snapshot_with_chain_supplies(self):
        v = self._make_verifier()
        supplies = {"ethereum": 1_000_000.0, "polygon": 500_000.0}
        snap = v.create_snapshot(1000, 3_300_000_000.0, 165_000_000.0, 1, 5.0, supplies)
        assert snap.chain_supplies["ethereum"] == 1_000_000.0

    def test_set_snapshot_ipfs_cid(self):
        v = self._make_verifier()
        snap = v.create_snapshot(1000, 3_300_000_000.0, 165_000_000.0, 1, 5.0)
        assert v.set_snapshot_ipfs_cid(snap.snapshot_id, "QmABC123") is True
        assert snap.ipfs_cid == "QmABC123"

    def test_set_snapshot_ipfs_not_found(self):
        v = self._make_verifier()
        assert v.set_snapshot_ipfs_cid("nonexistent", "QmXYZ") is False

    def test_record_inflow_hash(self):
        v = self._make_verifier()
        v.record_inflow_hash("inflow_001")
        v.record_inflow_hash("inflow_002")
        stats = v.get_stats()
        assert stats["inflow_hash_count"] == 2

    def test_get_reserve_status(self):
        v = self._make_verifier()
        v.record_inflow_hash("inf1")
        status = v.get_reserve_status(
            total_minted=1_000_000.0,
            reserve_usd=60_000.0,
            chain_year=1,
            required_backing=5.0,
        )
        assert status["backing_pct"] == 6.0
        assert status["compliant"] is True
        assert status["total_verified_inflows"] == 1

    def test_get_proof_of_reserves(self):
        v = self._make_verifier()
        v.record_inflow_hash("inf1")
        v.record_inflow_hash("inf2")
        proof = v.get_proof_of_reserves()
        assert len(proof["merkle_root"]) == 64  # SHA-256 hex
        assert proof["inflow_count"] == 2
        assert "verification_instructions" in proof

    def test_generate_audit_report(self):
        v = self._make_verifier()
        v.create_snapshot(1000, 3_300_000_000.0, 165_000_000.0, 1, 5.0)
        report = v.generate_audit_report(
            quarter="2026-Q1",
            start_block=0,
            end_block=2_000_000,
            total_inflows_qbc=5_000_000.0,
            total_inflows_usd=25_000_000.0,
            inflow_count=5000,
            violations=2,
            milestones_crossed=[5.0],
        )
        assert report.quarter == "2026-Q1"
        assert report.inflow_count == 5000
        assert report.violations == 2

    def test_get_snapshots(self):
        v = self._make_verifier(snapshot_interval_blocks=10)
        v.create_snapshot(100, 1_000_000.0, 50_000.0, 1, 5.0)
        v.create_snapshot(200, 1_000_000.0, 60_000.0, 1, 5.0)
        snaps = v.get_snapshots()
        assert len(snaps) == 2

    def test_get_audit_reports(self):
        v = self._make_verifier()
        v.generate_audit_report("2026-Q1", 0, 2_000_000, 1_000.0, 5_000.0, 100, 0)
        reports = v.get_audit_reports()
        assert len(reports) == 1

    def test_stats(self):
        v = self._make_verifier()
        stats = v.get_stats()
        assert stats["snapshot_count"] == 0
        assert stats["audit_report_count"] == 0


class TestComputeMerkleRoot:
    """Tests for Merkle root computation."""

    def test_empty(self):
        from qubitcoin.stablecoin.reserve_verification import compute_merkle_root
        root = compute_merkle_root([])
        assert len(root) == 64

    def test_single(self):
        from qubitcoin.stablecoin.reserve_verification import compute_merkle_root
        root = compute_merkle_root(["abc123"])
        assert root == "abc123"

    def test_two_elements(self):
        from qubitcoin.stablecoin.reserve_verification import compute_merkle_root
        root = compute_merkle_root(["aaa", "bbb"])
        assert len(root) == 64

    def test_deterministic(self):
        from qubitcoin.stablecoin.reserve_verification import compute_merkle_root
        r1 = compute_merkle_root(["a", "b", "c", "d"])
        r2 = compute_merkle_root(["a", "b", "c", "d"])
        assert r1 == r2

    def test_order_matters(self):
        from qubitcoin.stablecoin.reserve_verification import compute_merkle_root
        r1 = compute_merkle_root(["a", "b"])
        r2 = compute_merkle_root(["b", "a"])
        # Canonical ordering means same pair → same root regardless of order
        assert r1 == r2

    def test_odd_count(self):
        from qubitcoin.stablecoin.reserve_verification import compute_merkle_root
        root = compute_merkle_root(["a", "b", "c"])
        assert len(root) == 64
