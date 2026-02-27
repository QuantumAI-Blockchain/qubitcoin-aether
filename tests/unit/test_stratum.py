"""Tests for Stratum mining pool protocol."""
import time
import pytest
from unittest.mock import MagicMock, patch


class TestStratumPool:
    """Tests for the StratumPool class."""

    def _make_pool(self, **kwargs):
        from qubitcoin.mining.stratum import StratumPool
        return StratumPool(
            host="127.0.0.1",
            port=3333,
            reward_address="qbc1pool_reward_addr",
            **kwargs,
        )

    def test_init(self):
        pool = self._make_pool()
        assert pool.host == "127.0.0.1"
        assert pool.port == 3333
        assert pool.blocks_found == 0
        assert pool.total_shares == 0
        assert len(pool.workers) == 0

    def test_register_worker(self):
        pool = self._make_pool()
        worker = pool.register_worker("w1", "qbc1abc123")
        assert worker.worker_id == "w1"
        assert worker.address == "qbc1abc123"
        assert worker.session_id is not None
        assert len(worker.session_id) == 16
        assert "w1" in pool.workers

    def test_authorize_worker(self):
        pool = self._make_pool()
        pool.register_worker("w1", "")
        assert pool.authorize_worker("w1", "qbc1valid_address_here")
        assert pool.workers["w1"].authorized is True
        assert pool.workers["w1"].address == "qbc1valid_address_here"

    def test_authorize_invalid_address(self):
        pool = self._make_pool()
        pool.register_worker("w1", "")
        assert pool.authorize_worker("w1", "") is False
        assert pool.workers["w1"].authorized is False

    def test_authorize_unknown_worker(self):
        pool = self._make_pool()
        assert pool.authorize_worker("nonexistent", "qbc1addr") is False

    def test_disconnect_worker(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        assert "w1" in pool.workers
        pool.disconnect_worker("w1")
        assert "w1" not in pool.workers

    def test_create_work_unit(self):
        pool = self._make_pool()
        work = pool.create_work_unit(
            block_height=100,
            prev_hash="abcd1234",
            hamiltonian_seed="seed_hex",
            difficulty_target=1.5,
        )
        assert work.block_height == 100
        assert work.prev_hash == "abcd1234"
        assert work.difficulty_target == 1.5
        assert pool.current_work == work

    def test_get_work_notification(self):
        pool = self._make_pool()
        # No work yet
        assert pool.get_work_notification() is None

        pool.create_work_unit(100, "abcd", "seed", 1.5)
        notification = pool.get_work_notification()
        assert notification is not None
        assert notification["method"] == "mining.notify"
        assert len(notification["params"]) == 5

    def test_submit_share_valid(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1miner_address")
        pool.authorize_worker("w1", "qbc1miner_address")
        pool.create_work_unit(100, "abcd", "seed", 1.5)

        result = pool.submit_share(
            worker_id="w1",
            job_id=pool.current_work.job_id,
            vqe_params=[0.1, 0.2, 0.3, 0.4, 0.5],
            energy=0.05,  # Below worker difficulty (0.1)
            nonce=42,
        )
        assert result["accepted"] is True
        assert pool.workers["w1"].shares_accepted == 1
        assert pool.total_shares == 1

    def test_submit_share_unauthorized(self):
        pool = self._make_pool()
        pool.register_worker("w1", "")
        pool.create_work_unit(100, "abcd", "seed", 1.5)

        result = pool.submit_share("w1", "job", [0.1, 0.2, 0.3, 0.4], 0.05, 1)
        assert result["accepted"] is False
        assert result["reason"] == "unauthorized"

    def test_submit_share_stale_job(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")
        pool.create_work_unit(100, "abcd", "seed", 1.5)

        result = pool.submit_share("w1", "wrong_job_id", [0.1, 0.2, 0.3, 0.4], 0.05, 1)
        assert result["accepted"] is False
        assert result["reason"] == "stale_job"

    def test_submit_share_above_difficulty(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")
        pool.create_work_unit(100, "abcd", "seed", 1.5)

        # Energy (0.5) is above worker difficulty (0.1 default)
        result = pool.submit_share(
            "w1", pool.current_work.job_id, [0.1, 0.2, 0.3, 0.4], 0.5, 1
        )
        assert result["accepted"] is False
        assert result["reason"] == "above_difficulty"

    def test_submit_share_block_found(self):
        callback = MagicMock()
        pool = self._make_pool(on_block_found=callback)
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")
        pool.create_work_unit(100, "abcd", "seed", 1.5)

        # Energy below both worker difficulty AND block difficulty target
        result = pool.submit_share(
            "w1", pool.current_work.job_id, [0.1, 0.2, 0.3, 0.4, 0.5], 0.02, 1
        )
        assert result["accepted"] is True
        assert result["is_block"] is True
        assert pool.blocks_found == 1
        callback.assert_called_once()

    def test_submit_share_invalid_params(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")
        pool.create_work_unit(100, "abcd", "seed", 1.5)

        result = pool.submit_share("w1", pool.current_work.job_id, [0.1], 0.05, 1)
        assert result["accepted"] is False
        assert result["reason"] == "invalid_params"

    def test_calculate_rewards(self):
        pool = self._make_pool()
        pool.pool_fee_percent = 2.0

        # Register and authorize workers
        pool.register_worker("w1", "qbc1addr_a")
        pool.authorize_worker("w1", "qbc1addr_a")
        pool.register_worker("w2", "qbc1addr_b")
        pool.authorize_worker("w2", "qbc1addr_b")

        pool.create_work_unit(100, "abcd", "seed", 1.5)
        job = pool.current_work.job_id

        # w1 submits 3 shares, w2 submits 1 share
        for _ in range(3):
            pool.submit_share("w1", job, [0.1, 0.2, 0.3, 0.4], 0.05, 1)
        pool.submit_share("w2", job, [0.1, 0.2, 0.3, 0.4], 0.08, 2)

        rewards = pool.calculate_rewards(block_reward=15.27)
        assert "qbc1addr_a" in rewards
        assert "qbc1addr_b" in rewards

        # Pool fee = 2% of 15.27 = 0.3054
        # Distributable = 14.9646
        # w1 gets 3/4 = 11.2235
        # w2 gets 1/4 = 3.7412
        assert rewards["qbc1addr_a"] == pytest.approx(15.27 * 0.98 * 0.75, rel=0.01)
        assert rewards["qbc1addr_b"] == pytest.approx(15.27 * 0.98 * 0.25, rel=0.01)

    def test_calculate_rewards_empty(self):
        pool = self._make_pool()
        rewards = pool.calculate_rewards(15.27)
        assert rewards == {}

    def test_adjust_worker_difficulty(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")

        # Too soon — should not adjust (less than 60s)
        d = pool.adjust_worker_difficulty("w1", target_shares_per_minute=4.0)
        assert d == pool.min_difficulty

    def test_adjust_worker_difficulty_after_time(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")

        # Fake worker being connected for >60s with shares
        pool.workers["w1"].connected_at = time.time() - 120
        pool.workers["w1"].shares_accepted = 16  # 8 per minute

        d = pool.adjust_worker_difficulty("w1", target_shares_per_minute=4.0)
        # 8/min actual vs 4/min target → ratio 2.0 → difficulty doubles
        assert d > pool.min_difficulty

    def test_get_pool_stats(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")
        pool.create_work_unit(100, "abcd", "seed", 1.5)

        stats = pool.get_pool_stats()
        assert stats["active_workers"] == 1
        assert stats["total_shares"] == 0
        assert stats["blocks_found"] == 0
        assert stats["current_block_height"] == 100

    def test_get_worker_stats(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")

        stats = pool.get_worker_stats("w1")
        assert stats is not None
        assert stats["worker_id"] == "w1"
        assert stats["authorized"] is True
        assert stats["shares_accepted"] == 0

    def test_get_worker_stats_unknown(self):
        pool = self._make_pool()
        assert pool.get_worker_stats("unknown") is None

    # ─── JSON-RPC Protocol Tests ────────────────────────────────────────

    def test_handle_subscribe(self):
        pool = self._make_pool()
        response = pool.handle_message("w1", {
            "id": 1,
            "method": "mining.subscribe",
            "params": ["my_miner/1.0"],
        })
        assert response["id"] == 1
        assert response["error"] is None
        assert len(response["result"]) == 2
        assert "w1" in pool.workers

    def test_handle_authorize(self):
        pool = self._make_pool()
        pool.register_worker("w1", "")

        response = pool.handle_message("w1", {
            "id": 2,
            "method": "mining.authorize",
            "params": ["qbc1miner_wallet", "password"],
        })
        assert response["id"] == 2
        assert response["result"] is True

    def test_handle_submit(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")
        pool.create_work_unit(100, "abcd", "seed", 1.5)

        response = pool.handle_message("w1", {
            "id": 3,
            "method": "mining.submit",
            "params": [pool.current_work.job_id, "42", "0.05", [0.1, 0.2, 0.3, 0.4]],
        })
        assert response["id"] == 3
        assert response["result"] is True

    def test_handle_submit_insufficient_params(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")

        response = pool.handle_message("w1", {
            "id": 3,
            "method": "mining.submit",
            "params": ["job"],
        })
        assert response["result"] is False
        assert response["error"] == "insufficient_params"

    def test_handle_unknown_method(self):
        pool = self._make_pool()
        response = pool.handle_message("w1", {
            "id": 4,
            "method": "mining.unknown",
            "params": [],
        })
        assert response["error"] is not None
        assert "unknown_method" in response["error"]

    def test_unique_session_ids(self):
        pool = self._make_pool()
        w1 = pool.register_worker("w1", "qbc1a")
        w2 = pool.register_worker("w2", "qbc1b")
        assert w1.session_id != w2.session_id

    def test_multiple_blocks_found(self):
        pool = self._make_pool()
        pool.register_worker("w1", "qbc1addr")
        pool.authorize_worker("w1", "qbc1addr")

        # Find block 1
        pool.create_work_unit(100, "abcd", "seed1", 1.5)
        pool.submit_share("w1", pool.current_work.job_id, [0.1, 0.2, 0.3, 0.4], 0.01, 1)

        # Find block 2
        pool.create_work_unit(101, "efgh", "seed2", 1.5)
        pool.submit_share("w1", pool.current_work.job_id, [0.1, 0.2, 0.3, 0.4], 0.01, 2)

        assert pool.blocks_found == 2
        assert pool.total_shares == 2
