"""
Batch 26 tests:
  - PoolHealthMonitor (connection pool health monitoring)
  - SolutionVerificationTracker (SUSY solution verification counts)
  - VQECapabilityDetector (mining node capability detection)
"""
import time
import unittest
from unittest.mock import MagicMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from qubitcoin.database.pool_monitor import PoolHealthMonitor, PoolSnapshot
from qubitcoin.mining.solution_tracker import (
    SolutionVerificationTracker, SolutionRecord, SolutionVerification,
)
from qubitcoin.mining.capability_detector import VQECapabilityDetector, VQECapability


# ===========================================================================
# PoolHealthMonitor tests
# ===========================================================================

class TestPoolHealthMonitor(unittest.TestCase):
    """Test connection pool health monitoring."""

    def setUp(self):
        self.monitor = PoolHealthMonitor(engine=None, max_history=50)

    def test_initial_stats(self):
        stats = self.monitor.get_stats()
        assert stats['total_checkouts'] == 0
        assert stats['total_errors'] == 0
        assert stats['total_timeouts'] == 0

    def test_record_checkout(self):
        self.monitor.record_checkout()
        self.monitor.record_checkout()
        stats = self.monitor.get_stats()
        assert stats['total_checkouts'] == 2

    def test_record_checkin_with_latency(self):
        self.monitor.record_checkin(latency_ms=15.0)
        self.monitor.record_checkin(latency_ms=25.0)
        stats = self.monitor.get_stats()
        assert stats['total_checkins'] == 2
        assert stats['avg_checkout_latency_ms'] == 20.0
        assert stats['latency_samples'] == 2

    def test_record_error(self):
        self.monitor.record_error()
        self.monitor.record_error()
        self.monitor.record_error()
        stats = self.monitor.get_stats()
        assert stats['total_errors'] == 3

    def test_record_timeout(self):
        self.monitor.record_timeout()
        stats = self.monitor.get_stats()
        assert stats['total_timeouts'] == 1

    def test_get_snapshot_defaults(self):
        snap = self.monitor.get_snapshot()
        assert isinstance(snap, PoolSnapshot)
        assert snap.status == 'healthy'
        assert snap.pool_size == 0
        assert snap.checked_out == 0

    def test_snapshot_stored_in_history(self):
        self.monitor.get_snapshot()
        self.monitor.get_snapshot()
        history = self.monitor.get_history(limit=10)
        assert len(history) == 2

    def test_history_limit(self):
        for _ in range(5):
            self.monitor.get_snapshot()
        history = self.monitor.get_history(limit=3)
        assert len(history) == 3

    def test_snapshot_to_dict(self):
        snap = self.monitor.get_snapshot()
        d = snap.to_dict()
        assert 'timestamp' in d
        assert 'status' in d
        assert 'avg_checkout_ms' in d
        assert 'checkedout_pct' in d

    def test_health_status_degraded(self):
        status = self.monitor._compute_status(0.80, 50.0)
        assert status == 'degraded'

    def test_health_status_critical_utilization(self):
        status = self.monitor._compute_status(0.95, 10.0)
        assert status == 'critical'

    def test_health_status_critical_latency(self):
        status = self.monitor._compute_status(0.10, 600.0)
        assert status == 'critical'

    def test_health_status_healthy(self):
        status = self.monitor._compute_status(0.50, 20.0)
        assert status == 'healthy'

    def test_is_healthy(self):
        assert self.monitor.is_healthy() is True

    def test_max_latency(self):
        self.monitor.record_checkin(latency_ms=10.0)
        self.monitor.record_checkin(latency_ms=50.0)
        self.monitor.record_checkin(latency_ms=30.0)
        stats = self.monitor.get_stats()
        assert stats['max_checkout_latency_ms'] == 50.0

    def test_history_eviction(self):
        monitor = PoolHealthMonitor(engine=None, max_history=5)
        for _ in range(10):
            monitor.get_snapshot()
        history = monitor.get_history(limit=100)
        assert len(history) == 5

    def test_latency_samples_capped(self):
        monitor = PoolHealthMonitor(engine=None)
        for i in range(250):
            monitor.record_checkin(latency_ms=float(i))
        stats = monitor.get_stats()
        assert stats['latency_samples'] == 200  # max_latency_samples


# ===========================================================================
# SolutionVerificationTracker tests
# ===========================================================================

class TestSolutionVerificationTracker(unittest.TestCase):
    """Test SUSY solution verification tracking."""

    def setUp(self):
        self.tracker = SolutionVerificationTracker(max_solutions=100)

    def test_register_solution(self):
        record = self.tracker.register_solution(
            solution_id=1, block_height=100,
            miner_address='qbc1miner', original_energy=-1.5,
        )
        assert record.solution_id == 1
        assert record.verification_count == 0

    def test_register_duplicate(self):
        r1 = self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        r2 = self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        assert r1 is r2

    def test_record_verification(self):
        self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        v = self.tracker.record_verification(
            solution_id=1, verifier_address='qbc1v1',
            verified_energy=-1.49, energy_tolerance=0.05,
        )
        assert v is not None
        assert v.matches_original is True
        record = self.tracker.get_solution(1)
        assert record.verification_count == 1
        assert record.confirmed_count == 1

    def test_verification_mismatch(self):
        self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        v = self.tracker.record_verification(
            solution_id=1, verifier_address='qbc1v1',
            verified_energy=-0.5, energy_tolerance=0.01,
        )
        assert v.matches_original is False

    def test_verification_nonexistent_solution(self):
        v = self.tracker.record_verification(
            solution_id=999, verifier_address='qbc1v', verified_energy=0,
        )
        assert v is None

    def test_duplicate_verifier(self):
        self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        v1 = self.tracker.record_verification(1, 'qbc1v1', -1.49)
        v2 = self.tracker.record_verification(1, 'qbc1v1', -1.50)
        assert v1 is v2  # Same verification returned
        record = self.tracker.get_solution(1)
        assert record.verification_count == 1  # Not double-counted

    def test_confidence_score(self):
        self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        self.tracker.record_verification(1, 'v1', -1.50)   # match
        self.tracker.record_verification(1, 'v2', -1.505)  # match (within 0.01)
        self.tracker.record_verification(1, 'v3', -0.10)   # no match
        record = self.tracker.get_solution(1)
        assert record.verification_count == 3
        assert record.confirmed_count == 2
        assert abs(record.confidence - 2 / 3) < 0.001

    def test_get_by_block(self):
        self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        record = self.tracker.get_by_block(100)
        assert record is not None
        assert record.solution_id == 1

    def test_get_by_block_missing(self):
        assert self.tracker.get_by_block(999) is None

    def test_get_by_miner(self):
        self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        self.tracker.register_solution(2, 101, 'qbc1m', -1.6)
        self.tracker.register_solution(3, 102, 'qbc1other', -1.7)
        records = self.tracker.get_by_miner('qbc1m')
        assert len(records) == 2

    def test_get_top_verified(self):
        self.tracker.register_solution(1, 100, 'm1', -1.5)
        self.tracker.register_solution(2, 101, 'm2', -1.6)
        self.tracker.record_verification(1, 'v1', -1.5)
        self.tracker.record_verification(1, 'v2', -1.5)
        self.tracker.record_verification(2, 'v3', -1.6)
        top = self.tracker.get_top_verified(limit=2)
        assert len(top) == 2
        assert top[0].solution_id == 1  # More verifications

    def test_get_unverified(self):
        self.tracker.register_solution(1, 100, 'm1', -1.5)
        self.tracker.register_solution(2, 101, 'm2', -1.6)
        self.tracker.record_verification(1, 'v1', -1.5)
        unv = self.tracker.get_unverified()
        assert len(unv) == 1
        assert unv[0].solution_id == 2

    def test_capacity_eviction(self):
        tracker = SolutionVerificationTracker(max_solutions=3)
        tracker.register_solution(1, 100, 'm', -1.0)
        tracker.register_solution(2, 101, 'm', -1.1)
        tracker.register_solution(3, 102, 'm', -1.2)
        tracker.register_solution(4, 103, 'm', -1.3)  # Evicts #1
        assert tracker.get_solution(1) is None
        assert tracker.get_solution(4) is not None

    def test_solution_to_dict(self):
        self.tracker.register_solution(1, 100, 'qbc1m', -1.5)
        self.tracker.record_verification(1, 'v1', -1.5)
        record = self.tracker.get_solution(1)
        d = record.to_dict()
        assert d['solution_id'] == 1
        assert d['verification_count'] == 1
        assert d['confidence'] == 1.0
        assert len(d['verifications']) == 1

    def test_verification_to_dict(self):
        v = SolutionVerification(
            verifier_address='qbc1v', block_height=100,
            verified_energy=-1.5, matches_original=True,
        )
        d = v.to_dict()
        assert 'verification_id' in d
        assert d['verifier_address'] == 'qbc1v'
        assert d['matches_original'] is True

    def test_get_stats(self):
        self.tracker.register_solution(1, 100, 'm1', -1.5)
        self.tracker.register_solution(2, 101, 'm2', -1.6)
        self.tracker.record_verification(1, 'v1', -1.5)
        stats = self.tracker.get_stats()
        assert stats['total_solutions'] == 2
        assert stats['verified_solutions'] == 1
        assert stats['unverified_solutions'] == 1
        assert stats['total_verifications'] == 1
        assert stats['unique_miners'] == 2


# ===========================================================================
# VQECapabilityDetector tests
# ===========================================================================

class TestVQECapabilityDetector(unittest.TestCase):
    """Test VQE mining capability detection."""

    def setUp(self):
        self.detector = VQECapabilityDetector()

    def test_detect_local_estimator(self):
        engine = MagicMock()
        engine.estimator = MagicMock()
        engine.backend = None
        engine.service = None
        cap = self.detector.detect(engine)
        assert cap.backend_type == 'local_estimator'
        assert cap.is_simulator is True
        assert cap.is_available is True
        assert cap.max_qubits == 20

    def test_detect_aer_simulator(self):
        engine = MagicMock()
        engine.estimator = MagicMock()
        engine.backend = MagicMock()
        engine.backend.name = 'aer_simulator'
        engine.service = None
        cap = self.detector.detect(engine)
        assert cap.backend_type == 'aer_simulator'
        assert cap.is_simulator is True
        assert cap.max_qubits == 30

    def test_detect_ibm_quantum(self):
        engine = MagicMock()
        engine.estimator = MagicMock()
        engine.backend = MagicMock()
        engine.backend.name = 'ibm_brisbane'
        engine.backend.num_qubits = 127
        engine.backend.configuration = None
        engine.service = MagicMock()
        cap = self.detector.detect(engine)
        assert cap.backend_type == 'ibm_quantum'
        assert cap.is_simulator is False
        assert cap.max_qubits == 127
        assert cap.features.get('real_hardware') is True

    def test_detect_no_estimator(self):
        engine = MagicMock()
        engine.estimator = None
        engine.backend = None
        engine.service = None
        cap = self.detector.detect(engine)
        assert cap.backend_type == 'unknown'
        assert cap.is_available is False

    def test_detect_from_config_local(self):
        with patch('qubitcoin.config.Config') as MockConfig:
            MockConfig.USE_LOCAL_ESTIMATOR = True
            MockConfig.USE_SIMULATOR = False
            cap = self.detector.detect_from_config()
            assert cap.backend_type == 'local_estimator'
            assert cap.is_simulator is True

    def test_detect_from_config_aer(self):
        with patch('qubitcoin.config.Config') as MockConfig:
            MockConfig.USE_LOCAL_ESTIMATOR = False
            MockConfig.USE_SIMULATOR = True
            cap = self.detector.detect_from_config()
            assert cap.backend_type == 'aer_simulator'

    def test_detect_from_config_ibm(self):
        with patch('qubitcoin.config.Config') as MockConfig:
            MockConfig.USE_LOCAL_ESTIMATOR = False
            MockConfig.USE_SIMULATOR = False
            MockConfig.IBM_TOKEN = 'test_token'
            cap = self.detector.detect_from_config()
            assert cap.backend_type == 'ibm_quantum'
            assert cap.is_available is True

    def test_get_cached_none(self):
        assert self.detector.get_cached() is None

    def test_get_cached_after_detect(self):
        engine = MagicMock()
        engine.estimator = MagicMock()
        engine.backend = None
        engine.service = None
        self.detector.detect(engine)
        cached = self.detector.get_cached()
        assert cached is not None
        assert cached.backend_type == 'local_estimator'

    def test_capability_to_dict(self):
        cap = VQECapability(
            backend_type='local_estimator',
            backend_name='test',
            max_qubits=20,
            is_simulator=True,
            is_available=True,
            estimated_vqe_time_s=1.5,
            features={'exact': True},
        )
        d = cap.to_dict()
        assert d['backend_type'] == 'local_estimator'
        assert d['max_qubits'] == 20
        assert d['features'] == {'exact': True}

    def test_p2p_advertisement(self):
        engine = MagicMock()
        engine.estimator = MagicMock()
        engine.backend = None
        engine.service = None
        self.detector.detect(engine)
        ad = self.detector.get_p2p_advertisement()
        assert ad['type'] == 'vqe_capability'
        assert ad['backend_type'] == 'local_estimator'
        assert 'timestamp' in ad

    def test_p2p_advertisement_no_detect(self):
        """Should fall back to config-based detection."""
        with patch('qubitcoin.config.Config') as MockConfig:
            MockConfig.USE_LOCAL_ESTIMATOR = True
            MockConfig.USE_SIMULATOR = False
            ad = self.detector.get_p2p_advertisement()
            assert ad['type'] == 'vqe_capability'

    def test_detect_error_handling(self):
        """Should handle errors gracefully."""
        engine = MagicMock()
        engine.estimator = property(lambda self: (_ for _ in ()).throw(RuntimeError("fail")))
        # Make it raise on attribute access
        type(engine).estimator = property(lambda self: (_ for _ in ()).throw(RuntimeError("fail")))
        cap = self.detector.detect(engine)
        assert cap.is_available is False

    def test_ibm_qubits_from_num_qubits(self):
        backend = MagicMock()
        backend.configuration = None
        backend.num_qubits = 65
        qubits = VQECapabilityDetector._get_ibm_qubits(backend)
        assert qubits == 65


# ===========================================================================
# Integration tests
# ===========================================================================

class TestBatch26Integration(unittest.TestCase):
    """Integration tests across Batch 26 modules."""

    def test_pool_monitor_snapshot_sequence(self):
        """Simulate a sequence of pool activity and check status transitions."""
        monitor = PoolHealthMonitor(engine=None, max_history=100)
        # Normal activity
        for _ in range(10):
            monitor.record_checkout()
            monitor.record_checkin(latency_ms=5.0)
        snap = monitor.get_snapshot()
        assert snap.status == 'healthy'

    def test_solution_tracker_full_workflow(self):
        """Register solution, add verifications, check confidence."""
        tracker = SolutionVerificationTracker()
        tracker.register_solution(1, 100, 'miner1', -2.5)
        tracker.record_verification(1, 'v1', -2.50)
        tracker.record_verification(1, 'v2', -2.49)
        tracker.record_verification(1, 'v3', -2.51)
        tracker.record_verification(1, 'v4', -1.00)  # mismatch
        record = tracker.get_solution(1)
        assert record.verification_count == 4
        assert record.confirmed_count == 3
        assert record.confidence == 0.75


if __name__ == '__main__':
    unittest.main()
