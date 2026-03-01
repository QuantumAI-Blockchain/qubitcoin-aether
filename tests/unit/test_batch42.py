"""
Batch 42 tests:
  - StateChannelManager (open, update, close, dispute, finalize)
  - TransactionBatcher (add, execute, batch Merkle root)
  - TLACManager (multi-jurisdiction time-locked compliance)
  - HDCKManager (hierarchical deterministic compliance keys)
  - VCRStore (verifiable computation receipts)
"""
import time
import unittest
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from qubitcoin.qvm.state_channels import (
    StateChannelManager, StateChannel, StateUpdate, ChannelState,
    CHALLENGE_WINDOW_BLOCKS, MIN_CHANNEL_DEPOSIT,
)
from qubitcoin.qvm.transaction_batcher import (
    TransactionBatcher, BatchTransaction, BatchReceipt,
    MAX_BATCH_SIZE, BATCH_TIMEOUT_BLOCKS,
)
from qubitcoin.qvm.compliance_advanced import (
    TLACManager, TLACTransaction, ApprovalStatus,
    HDCKManager, HDCKRole, ROLE_PERMISSIONS,
    VCRStore, ComputationReceipt,
)


# ===========================================================================
# StateChannelManager tests
# ===========================================================================

class TestStateChannelManager(unittest.TestCase):

    def setUp(self):
        self.mgr = StateChannelManager()

    def test_open_channel(self):
        result = self.mgr.open_channel("alice", "bob", 100.0, 50.0, block_height=1)
        assert result["success"]
        assert "channel_id" in result
        ch = result["channel"]
        assert ch["deposit_a"] == 100.0
        assert ch["deposit_b"] == 50.0
        assert ch["total_locked"] == 150.0

    def test_open_channel_below_min_deposit(self):
        result = self.mgr.open_channel("alice", "bob", 0.001, 50.0, block_height=1)
        assert not result["success"]
        assert "Minimum" in result["error"]

    def test_open_channel_with_self(self):
        result = self.mgr.open_channel("alice", "alice", 100.0, 100.0, block_height=1)
        assert not result["success"]

    def test_update_state(self):
        r = self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        cid = r["channel_id"]
        result = self.mgr.update_state(cid, 80.0, 120.0, "sig_a", "sig_b")
        assert result["success"]
        assert result["nonce"] == 1

    def test_update_conservation_violation(self):
        r = self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        cid = r["channel_id"]
        result = self.mgr.update_state(cid, 80.0, 80.0)  # 160 != 200
        assert not result["success"]
        assert "conservation" in result["error"].lower()

    def test_update_negative_balance(self):
        r = self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        cid = r["channel_id"]
        result = self.mgr.update_state(cid, -10.0, 210.0)
        assert not result["success"]

    def test_close_and_finalize(self):
        r = self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        cid = r["channel_id"]
        self.mgr.update_state(cid, 70.0, 130.0)

        close = self.mgr.initiate_close(cid, block_height=10)
        assert close["success"]
        assert close["challenge_deadline"] == 10 + CHALLENGE_WINDOW_BLOCKS

        # Before deadline — should fail
        result = self.mgr.finalize(cid, block_height=50)
        assert not result["success"]

        # After deadline — should succeed
        result = self.mgr.finalize(cid, block_height=10 + CHALLENGE_WINDOW_BLOCKS)
        assert result["success"]
        assert result["settlement"]["balance_a"] == 70.0

    def test_dispute(self):
        r = self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        cid = r["channel_id"]
        self.mgr.update_state(cid, 70.0, 130.0)
        self.mgr.initiate_close(cid, block_height=10)

        # Dispute with higher nonce
        update = StateUpdate(cid, nonce=5, balance_a=60.0, balance_b=140.0)
        result = self.mgr.dispute(cid, update, block_height=15)
        assert result["success"]
        assert result["new_nonce"] == 5

    def test_dispute_after_deadline(self):
        r = self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        cid = r["channel_id"]
        self.mgr.initiate_close(cid, block_height=10)
        update = StateUpdate(cid, nonce=5, balance_a=60.0, balance_b=140.0)
        result = self.mgr.dispute(cid, update, block_height=10 + CHALLENGE_WINDOW_BLOCKS + 1)
        assert not result["success"]

    def test_get_channel(self):
        r = self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        ch = self.mgr.get_channel(r["channel_id"])
        assert ch is not None
        assert ch["party_a"] == "alice"

    def test_get_address_channels(self):
        self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        self.mgr.open_channel("alice", "carol", 50.0, 50.0, block_height=2)
        channels = self.mgr.get_address_channels("alice")
        assert len(channels) == 2

    def test_stats(self):
        self.mgr.open_channel("alice", "bob", 100.0, 100.0, block_height=1)
        stats = self.mgr.get_stats()
        assert stats["total_channels"] == 1
        assert stats["open_channels"] == 1
        assert stats["total_locked_qbc"] == 200.0


# ===========================================================================
# TransactionBatcher tests
# ===========================================================================

class TestTransactionBatcher(unittest.TestCase):

    def setUp(self):
        self.batcher = TransactionBatcher(max_batch_size=10, max_batch_gas=500000)

    def _make_tx(self, tx_id: str = "tx1", gas: int = 21000) -> BatchTransaction:
        return BatchTransaction(tx_id=tx_id, sender="alice", to="bob",
                                value=1.0, gas_limit=gas)

    def test_add_transaction(self):
        result = self.batcher.add_transaction(self._make_tx())
        assert result["success"]
        assert self.batcher.pending_count == 1

    def test_batch_full(self):
        for i in range(10):
            self.batcher.add_transaction(self._make_tx(f"tx{i}"))
        result = self.batcher.add_transaction(self._make_tx("tx_overflow"))
        assert not result["success"]
        assert "full" in result["error"].lower()

    def test_batch_gas_limit(self):
        # Gas limit is 500000, each tx uses 21000 → can fit 23
        # But batch size is 10, so size limit hits first.
        # Use larger gas to trigger gas limit
        self.batcher = TransactionBatcher(max_batch_size=100, max_batch_gas=50000)
        self.batcher.add_transaction(self._make_tx("tx1", gas=40000))
        result = self.batcher.add_transaction(self._make_tx("tx2", gas=20000))
        assert not result["success"]
        assert "gas" in result["error"].lower()

    def test_execute_batch(self):
        for i in range(5):
            self.batcher.add_transaction(self._make_tx(f"tx{i}"))
        receipt = self.batcher.execute_batch(block_height=100, state_root_before="root0")
        assert receipt.success
        assert receipt.tx_count == 5
        assert receipt.total_gas_used == 5 * 21000
        assert receipt.batch_root != ""
        assert self.batcher.pending_count == 0

    def test_execute_empty_batch(self):
        receipt = self.batcher.execute_batch(block_height=1)
        assert receipt.tx_count == 0

    def test_should_submit_full(self):
        for i in range(10):
            self.batcher.add_transaction(self._make_tx(f"tx{i}"))
        assert self.batcher.should_submit(block_height=1)

    def test_should_not_submit_empty(self):
        assert not self.batcher.should_submit(block_height=100)

    def test_batch_receipt_to_dict(self):
        self.batcher.add_transaction(self._make_tx())
        receipt = self.batcher.execute_batch(block_height=1)
        d = receipt.to_dict()
        assert "batch_id" in d
        assert "batch_root" in d

    def test_get_receipt(self):
        self.batcher.add_transaction(self._make_tx())
        receipt = self.batcher.execute_batch(block_height=1)
        found = self.batcher.get_receipt(receipt.batch_id)
        assert found is not None
        assert found["tx_count"] == 1

    def test_stats(self):
        self.batcher.add_transaction(self._make_tx())
        self.batcher.execute_batch(block_height=1)
        stats = self.batcher.get_stats()
        assert stats["total_batches"] == 1
        assert stats["total_tx_batched"] == 1


# ===========================================================================
# TLACManager tests
# ===========================================================================

class TestTLACManager(unittest.TestCase):

    def setUp(self):
        self.tlac = TLACManager()

    def test_create(self):
        result = self.tlac.create(
            "alice", {"type": "transfer"}, ["US_SEC", "EU_MiCA"],
            time_lock_blocks=100, block_height=1
        )
        assert result["success"]
        tx = result["transaction"]
        assert tx["total_required"] == 2
        assert not tx["fully_approved"]

    def test_create_no_jurisdictions(self):
        result = self.tlac.create("alice", {}, [], time_lock_blocks=100, block_height=1)
        assert not result["success"]

    def test_approve_single(self):
        r = self.tlac.create("alice", {}, ["US_SEC"], time_lock_blocks=100, block_height=1)
        tid = r["tlac_id"]
        result = self.tlac.approve(tid, "US_SEC", "regulator_addr", block_height=5)
        assert result["success"]
        assert result["fully_approved"]

    def test_approve_multi_jurisdiction(self):
        r = self.tlac.create("alice", {}, ["US_SEC", "EU_MiCA"], time_lock_blocks=100, block_height=1)
        tid = r["tlac_id"]
        self.tlac.approve(tid, "US_SEC", "reg_us", block_height=5)
        result = self.tlac.approve(tid, "EU_MiCA", "reg_eu", block_height=6)
        assert result["fully_approved"]
        assert len(result["remaining"]) == 0

    def test_execute_after_approval(self):
        r = self.tlac.create("alice", {"amount": 1000}, ["US_SEC"], time_lock_blocks=100, block_height=1)
        tid = r["tlac_id"]
        self.tlac.approve(tid, "US_SEC", "reg", block_height=5)
        result = self.tlac.execute_if_ready(tid, block_height=10)
        assert result["success"]
        assert result["tx_data"]["amount"] == 1000

    def test_execute_without_approval(self):
        r = self.tlac.create("alice", {}, ["US_SEC"], time_lock_blocks=100, block_height=1)
        result = self.tlac.execute_if_ready(r["tlac_id"], block_height=10)
        assert not result["success"]

    def test_expired_deadline(self):
        r = self.tlac.create("alice", {}, ["US_SEC"], time_lock_blocks=50, block_height=1)
        tid = r["tlac_id"]
        result = self.tlac.approve(tid, "US_SEC", "reg", block_height=100)
        assert not result["success"]
        assert "deadline" in result["error"].lower() or "expired" in result["error"].lower()

    def test_expire_stale(self):
        self.tlac.create("alice", {}, ["US_SEC"], time_lock_blocks=50, block_height=1)
        count = self.tlac.expire_stale(block_height=100)
        assert count == 1

    def test_stats(self):
        self.tlac.create("alice", {}, ["US_SEC"], time_lock_blocks=100, block_height=1)
        stats = self.tlac.get_stats()
        assert stats["total_created"] == 1
        assert stats["active"] == 1


# ===========================================================================
# HDCKManager tests
# ===========================================================================

class TestHDCKManager(unittest.TestCase):

    def setUp(self):
        self.hdck = HDCKManager()

    def test_derive_key(self):
        result = self.hdck.derive_key(org_id=0, role=HDCKRole.TRADING, index=0)
        assert result["success"]
        assert result["path"] == "m/44'/689'/0'/0/0"
        assert "sign_tx" in result["key"]["permissions"]

    def test_derive_audit_key(self):
        result = self.hdck.derive_key(org_id=1, role=HDCKRole.AUDIT, index=0)
        assert result["success"]
        assert "view_all" in result["key"]["permissions"]
        assert "export_reports" in result["key"]["permissions"]

    def test_derive_emergency_key(self):
        result = self.hdck.derive_key(org_id=0, role=HDCKRole.EMERGENCY, index=0)
        assert result["success"]
        assert "freeze_all" in result["key"]["permissions"]
        assert "revoke_keys" in result["key"]["permissions"]

    def test_duplicate_path(self):
        self.hdck.derive_key(org_id=0, role=HDCKRole.TRADING, index=0)
        result = self.hdck.derive_key(org_id=0, role=HDCKRole.TRADING, index=0)
        assert not result["success"]

    def test_check_permission(self):
        self.hdck.derive_key(org_id=0, role=HDCKRole.COMPLIANCE, index=0)
        path = "m/44'/689'/0'/2/0"
        assert self.hdck.check_permission(path, "freeze_account")
        assert not self.hdck.check_permission(path, "nonexistent_perm")

    def test_revoke_key(self):
        self.hdck.derive_key(org_id=0, role=HDCKRole.TRADING, index=0)
        path = "m/44'/689'/0'/0/0"
        result = self.hdck.revoke_key(path)
        assert result["success"]
        assert not self.hdck.check_permission(path, "sign_tx")

    def test_get_org_keys(self):
        self.hdck.derive_key(org_id=5, role=HDCKRole.TRADING, index=0)
        self.hdck.derive_key(org_id=5, role=HDCKRole.AUDIT, index=0)
        keys = self.hdck.get_org_keys(5)
        assert len(keys) == 2

    def test_stats(self):
        self.hdck.derive_key(org_id=0, role=HDCKRole.TRADING, index=0)
        stats = self.hdck.get_stats()
        assert stats["total_keys"] == 1
        assert stats["organizations"] == 1


# ===========================================================================
# VCRStore tests
# ===========================================================================

class TestVCRStore(unittest.TestCase):

    def setUp(self):
        self.vcr = VCRStore(max_receipts=100)

    def test_create_receipt(self):
        receipt = self.vcr.create_receipt(
            "input_data", "output_data", ["step1", "step2"],
            gas_used=50000, block_height=10, executor="alice"
        )
        assert receipt.receipt_id != ""
        assert receipt.gas_used == 50000

    def test_verify_receipt_valid(self):
        receipt = self.vcr.create_receipt(
            "input", "output", ["s1"], 1000, 1, "alice"
        )
        result = self.vcr.verify_receipt(receipt.receipt_id, "auditor")
        assert result["verified"]
        assert result["verification_count"] == 1

    def test_verify_receipt_not_found(self):
        result = self.vcr.verify_receipt("nonexistent", "auditor")
        assert not result["verified"]

    def test_verify_with_expected_hashes(self):
        from qubitcoin.qvm.vm import keccak256
        inp = "test_input"
        out = "test_output"
        receipt = self.vcr.create_receipt(inp, out, ["s1"], 1000, 1, "alice")
        expected_comp = keccak256(inp.encode()).hex()
        expected_res = keccak256(out.encode()).hex()
        result = self.vcr.verify_receipt(
            receipt.receipt_id, "auditor",
            expected_computation_hash=expected_comp,
            expected_result_hash=expected_res,
        )
        assert result["verified"]

    def test_verify_wrong_computation_hash(self):
        receipt = self.vcr.create_receipt("input", "output", [], 1000, 1, "alice")
        result = self.vcr.verify_receipt(
            receipt.receipt_id, "auditor",
            expected_computation_hash="wrong_hash"
        )
        assert not result["verified"]
        assert "mismatch" in result["reason"].lower()

    def test_multi_verifier(self):
        receipt = self.vcr.create_receipt("i", "o", [], 100, 1, "alice")
        self.vcr.verify_receipt(receipt.receipt_id, "auditor_1")
        self.vcr.verify_receipt(receipt.receipt_id, "auditor_2")
        r = self.vcr.get_receipt(receipt.receipt_id)
        assert r["verification_count"] == 2

    def test_duplicate_verifier_no_double_count(self):
        receipt = self.vcr.create_receipt("i", "o", [], 100, 1, "alice")
        self.vcr.verify_receipt(receipt.receipt_id, "auditor_1")
        self.vcr.verify_receipt(receipt.receipt_id, "auditor_1")
        r = self.vcr.get_receipt(receipt.receipt_id)
        assert r["verification_count"] == 1

    def test_get_block_receipts(self):
        self.vcr.create_receipt("i1", "o1", [], 100, 5, "alice")
        self.vcr.create_receipt("i2", "o2", [], 200, 5, "bob")
        receipts = self.vcr.get_block_receipts(5)
        assert len(receipts) == 2

    def test_eviction(self):
        store = VCRStore(max_receipts=5)
        for i in range(10):
            store.create_receipt(f"i{i}", f"o{i}", [], 100, i, "alice")
        assert store.get_stats()["stored"] <= 5

    def test_integrity_hash(self):
        receipt = self.vcr.create_receipt("i", "o", ["s1"], 100, 1, "alice")
        h1 = receipt.integrity_hash
        h2 = receipt.integrity_hash
        assert h1 == h2  # Deterministic

    def test_stats(self):
        self.vcr.create_receipt("i", "o", [], 100, 1, "alice")
        self.vcr.verify_receipt(
            list(self.vcr._receipts.keys())[0], "aud"
        )
        stats = self.vcr.get_stats()
        assert stats["total_created"] == 1
        assert stats["total_verified"] == 1


if __name__ == '__main__':
    unittest.main()
