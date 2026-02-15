"""
Batch 27 tests:
  - CapabilityAdvertiser (P2P capability advertisement)
  - SnapshotScheduler (blockchain snapshot to IPFS)
  - SolutionArchiver (IPFS archival of SUSY solution datasets)
"""
import time
import unittest
from unittest.mock import MagicMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from qubitcoin.network.capability_advertisement import (
    CapabilityAdvertiser, PeerCapability,
)
from qubitcoin.storage.snapshot_scheduler import SnapshotScheduler, SnapshotRecord
from qubitcoin.storage.solution_archiver import SolutionArchiver, ArchiveRecord


# ===========================================================================
# CapabilityAdvertiser tests
# ===========================================================================

class TestCapabilityAdvertiser(unittest.TestCase):
    """Test P2P capability advertisement."""

    def setUp(self):
        self.advertiser = CapabilityAdvertiser(node_peer_id='node_abc')

    def test_set_local_capability(self):
        ad = {'backend_type': 'local_estimator', 'max_qubits': 20}
        self.advertiser.set_local_capability(ad)
        local = self.advertiser.get_local_advertisement()
        assert local is not None
        assert local['backend_type'] == 'local_estimator'
        assert local['peer_id'] == 'node_abc'

    def test_get_local_none(self):
        assert self.advertiser.get_local_advertisement() is None

    def test_receive_advertisement(self):
        ad = {
            'backend_type': 'aer_simulator',
            'max_qubits': 30,
            'is_simulator': True,
            'is_available': True,
            'estimated_vqe_time_s': 2.0,
            'features': {'noise_model': True},
            'timestamp': time.time(),
        }
        cap = self.advertiser.receive_advertisement('peer_1', ad)
        assert cap.peer_id == 'peer_1'
        assert cap.backend_type == 'aer_simulator'
        assert cap.max_qubits == 30

    def test_get_peer(self):
        self.advertiser.receive_advertisement('peer_1', {
            'backend_type': 'local_estimator', 'max_qubits': 20,
            'is_simulator': True, 'is_available': True,
            'estimated_vqe_time_s': 1.0,
        })
        peer = self.advertiser.get_peer('peer_1')
        assert peer is not None
        assert peer.backend_type == 'local_estimator'

    def test_get_peer_missing(self):
        assert self.advertiser.get_peer('nonexistent') is None

    def test_remove_peer(self):
        self.advertiser.receive_advertisement('peer_1', {
            'backend_type': 'local_estimator', 'max_qubits': 20,
            'is_simulator': True, 'is_available': True,
            'estimated_vqe_time_s': 1.0,
        })
        self.advertiser.remove_peer('peer_1')
        assert self.advertiser.get_peer('peer_1') is None

    def test_get_all_peers(self):
        for i in range(3):
            self.advertiser.receive_advertisement(f'peer_{i}', {
                'backend_type': 'local_estimator', 'max_qubits': 20,
                'is_simulator': True, 'is_available': True,
                'estimated_vqe_time_s': 1.0,
            })
        peers = self.advertiser.get_all_peers()
        assert len(peers) == 3

    def test_get_peers_by_power(self):
        # Faster node should rank higher
        self.advertiser.receive_advertisement('slow', {
            'backend_type': 'local_estimator', 'max_qubits': 4,
            'is_simulator': True, 'is_available': True,
            'estimated_vqe_time_s': 10.0,
        })
        self.advertiser.receive_advertisement('fast', {
            'backend_type': 'aer_simulator', 'max_qubits': 30,
            'is_simulator': True, 'is_available': True,
            'estimated_vqe_time_s': 0.5,
        })
        ranked = self.advertiser.get_peers_by_power()
        assert len(ranked) == 2
        assert ranked[0].peer_id == 'fast'

    def test_get_peers_by_backend(self):
        self.advertiser.receive_advertisement('p1', {
            'backend_type': 'local_estimator', 'max_qubits': 20,
            'is_simulator': True, 'is_available': True,
            'estimated_vqe_time_s': 1.0,
        })
        self.advertiser.receive_advertisement('p2', {
            'backend_type': 'ibm_quantum', 'max_qubits': 127,
            'is_simulator': False, 'is_available': True,
            'estimated_vqe_time_s': 30.0,
        })
        ibm = self.advertiser.get_peers_by_backend('ibm_quantum')
        assert len(ibm) == 1
        assert ibm[0].peer_id == 'p2'

    def test_network_summary(self):
        self.advertiser.receive_advertisement('p1', {
            'backend_type': 'local_estimator', 'max_qubits': 20,
            'is_simulator': True, 'is_available': True,
            'estimated_vqe_time_s': 1.0,
        })
        self.advertiser.receive_advertisement('p2', {
            'backend_type': 'ibm_quantum', 'max_qubits': 127,
            'is_simulator': False, 'is_available': True,
            'estimated_vqe_time_s': 30.0,
        })
        summary = self.advertiser.get_network_summary()
        assert summary['total_peers'] == 2
        assert summary['hardware_nodes'] == 1
        assert summary['simulator_nodes'] == 1
        assert summary['max_qubit_capacity'] == 127

    def test_peer_capability_mining_power(self):
        cap = PeerCapability(
            peer_id='p1', backend_type='local_estimator',
            max_qubits=20, is_simulator=True,
            is_available=True, estimated_vqe_time_s=1.0,
        )
        assert cap.mining_power_score > 0
        # Unavailable node has zero power
        cap2 = PeerCapability(
            peer_id='p2', backend_type='local_estimator',
            max_qubits=20, is_simulator=True,
            is_available=False, estimated_vqe_time_s=1.0,
        )
        assert cap2.mining_power_score == 0.0

    def test_peer_capability_to_dict(self):
        cap = PeerCapability(
            peer_id='p1', backend_type='aer_simulator',
            max_qubits=30, is_simulator=True,
            is_available=True, estimated_vqe_time_s=2.0,
            features={'noise_model': True},
        )
        d = cap.to_dict()
        assert d['peer_id'] == 'p1'
        assert d['mining_power_score'] > 0
        assert 'is_stale' in d

    def test_capacity_eviction(self):
        adv = CapabilityAdvertiser(node_peer_id='test', max_peers=3)
        for i in range(5):
            adv.receive_advertisement(f'peer_{i}', {
                'backend_type': 'local_estimator', 'max_qubits': 20,
                'is_simulator': True, 'is_available': True,
                'estimated_vqe_time_s': 1.0,
            })
        peers = adv.get_all_peers()
        assert len(peers) == 3

    def test_cleanup_stale(self):
        cap = PeerCapability(
            peer_id='old', backend_type='local_estimator',
            max_qubits=20, is_simulator=True,
            is_available=True, estimated_vqe_time_s=1.0,
            received_at=time.time() - 700,  # 11+ minutes ago
        )
        self.advertiser._peers['old'] = cap
        removed = self.advertiser.cleanup_stale()
        assert removed == 1
        assert self.advertiser.get_peer('old') is None

    def test_get_stats(self):
        self.advertiser.receive_advertisement('p1', {
            'backend_type': 'local_estimator', 'max_qubits': 20,
            'is_simulator': True, 'is_available': True,
            'estimated_vqe_time_s': 1.0,
        })
        stats = self.advertiser.get_stats()
        assert stats['registered_peers'] == 1
        assert stats['node_peer_id'] == 'node_abc'
        assert stats['has_local_capability'] is False

    def test_hardware_bonus_in_power(self):
        """Hardware nodes should get a 1.5x bonus over simulators."""
        sim = PeerCapability(
            peer_id='sim', backend_type='aer_simulator',
            max_qubits=20, is_simulator=True,
            is_available=True, estimated_vqe_time_s=1.0,
        )
        hw = PeerCapability(
            peer_id='hw', backend_type='ibm_quantum',
            max_qubits=20, is_simulator=False,
            is_available=True, estimated_vqe_time_s=1.0,
        )
        assert hw.mining_power_score > sim.mining_power_score


# ===========================================================================
# SnapshotScheduler tests
# ===========================================================================

class TestSnapshotScheduler(unittest.TestCase):
    """Test blockchain snapshot scheduling."""

    def setUp(self):
        self.scheduler = SnapshotScheduler(interval_blocks=100, max_history=50)

    def test_should_snapshot(self):
        assert self.scheduler.should_snapshot(0) is False
        assert self.scheduler.should_snapshot(50) is False
        assert self.scheduler.should_snapshot(100) is True
        assert self.scheduler.should_snapshot(200) is True

    def test_should_not_double_snapshot(self):
        # Simulate taking a snapshot at 100
        self.scheduler._last_snapshot_height = 100
        assert self.scheduler.should_snapshot(100) is False
        assert self.scheduler.should_snapshot(200) is True

    def test_take_snapshot_no_db(self):
        """Snapshot with mock DB that has no real data."""
        db = MagicMock()
        session_cm = MagicMock()
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        session_cm.__enter__ = MagicMock(return_value=session)
        session_cm.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = session_cm
        db.get_block.return_value = None

        record = self.scheduler.take_snapshot(100, db_manager=db)
        assert record.success is True
        assert record.block_height == 100
        assert record.block_count == 0
        assert record.cid is None  # No IPFS

    def test_take_snapshot_updates_state(self):
        db = MagicMock()
        session_cm = MagicMock()
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        session_cm.__enter__ = MagicMock(return_value=session)
        session_cm.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = session_cm
        db.get_block.return_value = None

        self.scheduler.take_snapshot(100, db)
        assert self.scheduler._last_snapshot_height == 100
        assert self.scheduler._total_snapshots == 1

    def test_on_new_block_triggers(self):
        db = MagicMock()
        session_cm = MagicMock()
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        session_cm.__enter__ = MagicMock(return_value=session)
        session_cm.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = session_cm
        db.get_block.return_value = None

        result = self.scheduler.on_new_block(50, db)
        assert result is None  # Not at interval

        result = self.scheduler.on_new_block(100, db)
        assert result is not None
        assert result.success is True

    def test_snapshot_history(self):
        db = MagicMock()
        session_cm = MagicMock()
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        session_cm.__enter__ = MagicMock(return_value=session)
        session_cm.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = session_cm
        db.get_block.return_value = None

        self.scheduler.take_snapshot(100, db)
        self.scheduler.take_snapshot(200, db)
        history = self.scheduler.get_history()
        assert len(history) == 2

    def test_get_latest(self):
        assert self.scheduler.get_latest() is None

        db = MagicMock()
        session_cm = MagicMock()
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        session_cm.__enter__ = MagicMock(return_value=session)
        session_cm.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = session_cm
        db.get_block.return_value = None

        self.scheduler.take_snapshot(100, db)
        latest = self.scheduler.get_latest()
        assert latest is not None
        assert latest.block_height == 100

    def test_snapshot_failure(self):
        db = MagicMock()
        db.get_session.side_effect = RuntimeError("DB down")

        record = self.scheduler.take_snapshot(100, db)
        assert record.success is False
        assert record.error is not None

    def test_get_stats(self):
        stats = self.scheduler.get_stats()
        assert stats['total_snapshots'] == 0
        assert stats['interval_blocks'] == 100

    def test_snapshot_record_to_dict(self):
        record = SnapshotRecord(
            snapshot_id='abc', block_height=100, cid='Qm123',
            chain_hash='0xabc', block_count=100, utxo_count=50,
            tx_count=200, size_estimate_bytes=5000,
            duration_s=1.5, success=True,
        )
        d = record.to_dict()
        assert d['snapshot_id'] == 'abc'
        assert d['cid'] == 'Qm123'
        assert d['success'] is True

    def test_history_eviction(self):
        scheduler = SnapshotScheduler(interval_blocks=1, max_history=3)
        db = MagicMock()
        session_cm = MagicMock()
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        session_cm.__enter__ = MagicMock(return_value=session)
        session_cm.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = session_cm
        db.get_block.return_value = None

        for h in [1, 2, 3, 4, 5]:
            scheduler.take_snapshot(h, db)
        history = scheduler.get_history(limit=100)
        assert len(history) == 3

    def test_interval_property(self):
        assert self.scheduler.interval_blocks == 100


# ===========================================================================
# SolutionArchiver tests
# ===========================================================================

class TestSolutionArchiver(unittest.TestCase):
    """Test IPFS archival of SUSY solution datasets."""

    def _mock_db(self, solutions=None):
        """Create a mock DB that returns given solutions."""
        db = MagicMock()
        session_cm = MagicMock()
        session = MagicMock()
        rows = solutions or []
        session.execute.return_value.fetchall.return_value = rows
        session_cm.__enter__ = MagicMock(return_value=session)
        session_cm.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = session_cm
        return db

    def setUp(self):
        self.archiver = SolutionArchiver(interval_blocks=500, max_history=50)

    def test_should_archive(self):
        assert self.archiver.should_archive(0) is False
        assert self.archiver.should_archive(250) is False
        assert self.archiver.should_archive(500) is True
        assert self.archiver.should_archive(1000) is True

    def test_should_not_double_archive(self):
        self.archiver._last_archive_height = 500
        assert self.archiver.should_archive(500) is False
        assert self.archiver.should_archive(1000) is True

    def test_archive_empty_range(self):
        db = self._mock_db([])
        record = self.archiver.archive_range(0, 100, db)
        assert record.success is True
        assert record.solution_count == 0
        assert record.cid is None  # No IPFS, no solutions

    def test_archive_with_solutions(self):
        solutions = [
            (1, '{"H": "XX"}', '[0.1, 0.2]', -1.5, 'qbc1miner', 50),
            (2, '{"H": "YY"}', '[0.3, 0.4]', -1.8, 'qbc1miner', 80),
        ]
        db = self._mock_db(solutions)
        record = self.archiver.archive_range(0, 100, db)
        assert record.success is True
        assert record.solution_count == 2
        assert record.size_bytes > 0

    def test_archive_updates_state(self):
        db = self._mock_db([])
        self.archiver.archive_range(0, 500, db)
        assert self.archiver._last_archive_height == 500
        assert self.archiver._total_archives == 1

    def test_on_new_block_triggers(self):
        db = self._mock_db([])
        result = self.archiver.on_new_block(250, db)
        assert result is None

        result = self.archiver.on_new_block(500, db)
        assert result is not None
        assert result.success is True

    def test_archive_failure(self):
        """DB errors in query are handled gracefully (returns 0 solutions)."""
        db = MagicMock()
        db.get_session.side_effect = RuntimeError("DB error")
        record = self.archiver.archive_range(0, 100, db)
        # Query failure is handled gracefully — archive succeeds with 0 solutions
        assert record.success is True
        assert record.solution_count == 0

    def test_archive_catastrophic_failure(self):
        """A non-DB error causes actual failure."""
        archiver = SolutionArchiver()
        # Patch _build_snapshot-equivalent logic — make _query_solutions raise
        # outside the try/except by patching _estimate_size to blow up
        db = self._mock_db([])
        with patch.object(archiver, '_estimate_size', side_effect=RuntimeError("fatal")):
            record = archiver.archive_range(0, 100, db)
        assert record.success is False
        assert 'fatal' in record.error

    def test_get_history(self):
        db = self._mock_db([])
        self.archiver.archive_range(0, 100, db)
        self.archiver.archive_range(100, 200, db)
        history = self.archiver.get_history()
        assert len(history) == 2

    def test_get_latest(self):
        assert self.archiver.get_latest() is None
        db = self._mock_db([])
        self.archiver.archive_range(0, 100, db)
        latest = self.archiver.get_latest()
        assert latest is not None
        assert latest.to_height == 100

    def test_get_all_cids_no_ipfs(self):
        db = self._mock_db([])
        self.archiver.archive_range(0, 100, db)
        assert self.archiver.get_all_cids() == []

    def test_get_all_cids_with_ipfs(self):
        db = self._mock_db([(1, '{}', '[]', -1.0, 'm', 50)])
        ipfs = MagicMock()
        ipfs.client = MagicMock()
        ipfs.client.add_json.return_value = 'QmTestCid123'

        self.archiver.archive_range(0, 100, db, ipfs_manager=ipfs)
        cids = self.archiver.get_all_cids()
        assert len(cids) == 1
        assert cids[0] == 'QmTestCid123'

    def test_get_stats(self):
        db = self._mock_db([(1, '{}', '[]', -1.0, 'm', 50)])
        self.archiver.archive_range(0, 100, db)
        stats = self.archiver.get_stats()
        assert stats['total_archives'] == 1
        assert stats['total_solutions_archived'] == 1
        assert stats['last_archive_height'] == 100

    def test_archive_record_to_dict(self):
        record = ArchiveRecord(
            archive_id='abc', from_height=0, to_height=100,
            solution_count=5, cid='QmTest', size_bytes=1000,
            duration_s=0.5, success=True,
        )
        d = record.to_dict()
        assert d['archive_id'] == 'abc'
        assert d['solution_count'] == 5
        assert d['cid'] == 'QmTest'

    def test_history_eviction(self):
        archiver = SolutionArchiver(interval_blocks=1, max_history=3)
        db = self._mock_db([])
        for i in range(5):
            archiver.archive_range(i * 10, (i + 1) * 10, db)
        history = archiver.get_history(limit=100)
        assert len(history) == 3


# ===========================================================================
# Integration tests
# ===========================================================================

class TestBatch27Integration(unittest.TestCase):
    """Integration tests across Batch 27 modules."""

    def test_capability_advertisement_full_flow(self):
        """Full flow: set local, receive peers, rank, summarize."""
        adv = CapabilityAdvertiser(node_peer_id='main')
        adv.set_local_capability({
            'backend_type': 'local_estimator', 'max_qubits': 20,
        })
        for i in range(5):
            adv.receive_advertisement(f'peer_{i}', {
                'backend_type': 'local_estimator',
                'max_qubits': 4 + i * 5,
                'is_simulator': True,
                'is_available': True,
                'estimated_vqe_time_s': 5.0 - i * 0.5,
            })
        summary = adv.get_network_summary()
        assert summary['total_peers'] == 5
        assert summary['available_miners'] == 5
        ranked = adv.get_peers_by_power()
        # peer_4 should be fastest (lowest VQE time, highest qubits)
        assert ranked[0].peer_id == 'peer_4'

    def test_snapshot_and_archive_together(self):
        """Both scheduler and archiver can run on the same block."""
        db = MagicMock()
        session_cm = MagicMock()
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        session_cm.__enter__ = MagicMock(return_value=session)
        session_cm.__exit__ = MagicMock(return_value=False)
        db.get_session.return_value = session_cm
        db.get_block.return_value = None

        scheduler = SnapshotScheduler(interval_blocks=100)
        archiver = SolutionArchiver(interval_blocks=100)

        snap = scheduler.on_new_block(100, db)
        arch = archiver.on_new_block(100, db)

        assert snap is not None and snap.success
        assert arch is not None and arch.success


if __name__ == '__main__':
    unittest.main()
