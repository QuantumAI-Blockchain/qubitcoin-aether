"""Tests for the Stratum bridge service (Python gRPC side)."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.mining.stratum_bridge import StratumBridgeService


@pytest.fixture()
def bridge():
    mining = MagicMock()
    consensus = MagicMock()
    consensus._current_height = 100
    consensus._current_difficulty = 1.5
    db = MagicMock()
    db.get_latest_block.return_value = {'hash': 'abc123' * 10 + 'abcd', 'height': 99}
    return StratumBridgeService(
        mining_engine=mining,
        consensus_engine=consensus,
        db_manager=db,
    )


class TestGetWorkUnit:
    def test_returns_work(self, bridge):
        work = bridge.get_work_unit()
        assert 'job_id' in work
        assert 'prev_block_hash' in work
        assert 'height' in work
        assert 'difficulty' in work
        assert work['difficulty'] == 1.5

    def test_increments_job_counter(self, bridge):
        bridge.get_work_unit()
        bridge.get_work_unit()
        assert bridge._job_counter == 2

    def test_job_id_changes(self, bridge):
        w1 = bridge.get_work_unit()
        w2 = bridge.get_work_unit()
        assert w1['job_id'] != w2['job_id']

    def test_uses_db_tip(self, bridge):
        work = bridge.get_work_unit()
        assert work['height'] == 100  # tip.height + 1


class TestSubmitSolution:
    def test_accept_valid(self, bridge):
        work = bridge.get_work_unit()
        result = bridge.submit_solution(
            job_id=work['job_id'],
            worker_id='w1',
            worker_address='qbc1addr',
            vqe_params=[0.1, 0.2],
            energy=0.5,  # below difficulty 1.5
            nonce=42,
        )
        assert result['accepted'] is True
        assert result['block_found'] is True

    def test_reject_stale_job(self, bridge):
        bridge.get_work_unit()
        result = bridge.submit_solution(
            job_id='old_job',
            worker_id='w1',
            worker_address='qbc1addr',
            vqe_params=[0.1],
            energy=0.5,
            nonce=1,
        )
        assert result['accepted'] is False
        assert 'Stale' in result['reason']

    def test_reject_high_energy(self, bridge):
        work = bridge.get_work_unit()
        result = bridge.submit_solution(
            job_id=work['job_id'],
            worker_id='w1',
            worker_address='qbc1addr',
            vqe_params=[0.1],
            energy=2.0,  # above difficulty 1.5
            nonce=1,
        )
        assert result['accepted'] is False
        assert 'Energy' in result['reason']


class TestGetDifficulty:
    def test_returns_difficulty(self, bridge):
        result = bridge.get_difficulty(100)
        assert result['difficulty'] == 1.5
        assert result['height'] == 100


class TestGetStats:
    def test_initial_stats(self, bridge):
        stats = bridge.get_stats()
        assert stats['job_counter'] == 0
        assert stats['current_job_id'] == ''

    def test_stats_after_work(self, bridge):
        bridge.get_work_unit()
        stats = bridge.get_stats()
        assert stats['job_counter'] == 1
        assert stats['current_job_id'] != ''


class TestNoEngines:
    def test_works_without_engines(self):
        bridge = StratumBridgeService()
        work = bridge.get_work_unit()
        assert work['height'] == 0
        assert work['difficulty'] == 1.0

    def test_submit_without_consensus(self):
        bridge = StratumBridgeService()
        work = bridge.get_work_unit()
        result = bridge.submit_solution(
            job_id=work['job_id'],
            worker_id='w1',
            worker_address='qbc1addr',
            vqe_params=[0.1],
            energy=0.5,
            nonce=1,
        )
        assert result['accepted'] is True
