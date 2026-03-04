"""
Batch 40 tests:
  - MelatoninModulator (pineal.py inhibitory signals)
  - PressureMonitor (csf_transport.py load balancing)
  - QuantumEntangledChannel (csf_transport.py SUSY pair instant delivery)
  - CSFTransport integration with pressure/entanglement
  - SnapshotScheduler.restore_from_snapshot
  - Config.IPFS_GATEWAY_PORT
"""
import json
import time
import unittest
from unittest.mock import MagicMock, patch


def _using_rust_csf() -> bool:
    """Return True if the Rust-accelerated CSFTransport is active."""
    try:
        import aether_core  # noqa: F401
        return True
    except ImportError:
        return False

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from qubitcoin.aether.sephirot import SephirahRole, SUSY_PAIRS, SephirotManager
from qubitcoin.aether.pineal import (
    MelatoninModulator, PinealOrchestrator, CircadianPhase,
    MELATONIN_LEVELS, METABOLIC_RATES,
)
from qubitcoin.aether.csf_transport import (
    CSFTransport, CSFMessage, PressureMonitor, QuantumEntangledChannel,
    TOPOLOGY, MAX_NODE_PRESSURE,
)
from qubitcoin.storage.snapshot_scheduler import SnapshotScheduler


# ===========================================================================
# MelatoninModulator tests
# ===========================================================================

class TestMelatoninModulator(unittest.TestCase):
    """Test melatonin inhibitory signal modulator."""

    def setUp(self):
        self.mod = MelatoninModulator()

    def test_initial_level_zero(self):
        assert self.mod.level == 0.0

    def test_inhibition_factor_at_zero(self):
        """No melatonin means no inhibition (factor = 1.0)."""
        assert self.mod.inhibition_factor == 1.0

    def test_melatonin_rises_during_sleep(self):
        """Melatonin should increase during DEEP_SLEEP phase."""
        for _ in range(20):
            self.mod.update(CircadianPhase.DEEP_SLEEP)
        assert self.mod.level > 0.5

    def test_melatonin_decays_during_waking(self):
        """Melatonin should decay during WAKING phase."""
        # First build up melatonin
        for _ in range(20):
            self.mod.update(CircadianPhase.DEEP_SLEEP)
        high_level = self.mod.level

        # Now decay it
        for _ in range(30):
            self.mod.update(CircadianPhase.WAKING)
        assert self.mod.level < high_level

    def test_inhibition_factor_dampens_during_sleep(self):
        """Inhibition factor should decrease (dampen) when melatonin is high."""
        for _ in range(20):
            self.mod.update(CircadianPhase.DEEP_SLEEP)
        assert self.mod.inhibition_factor < 1.0

    def test_inhibition_factor_floor(self):
        """Inhibition factor should never go below 0.1."""
        self.mod._level = 1.0
        assert self.mod.inhibition_factor >= 0.1

    def test_melatonin_levels_dict(self):
        """All circadian phases should have melatonin level entries."""
        for phase in CircadianPhase:
            assert phase.value in MELATONIN_LEVELS

    def test_waking_no_melatonin(self):
        assert MELATONIN_LEVELS["waking"] == 0.0
        assert MELATONIN_LEVELS["active_learning"] == 0.0

    def test_deep_sleep_high_melatonin(self):
        assert MELATONIN_LEVELS["deep_sleep"] == 0.9

    def test_get_status(self):
        status = self.mod.get_status()
        assert "level" in status
        assert "inhibition_factor" in status
        assert "accumulated" in status

    def test_reset_cycle(self):
        for _ in range(10):
            self.mod.update(CircadianPhase.SLEEP)
        assert self.mod._accumulated > 0.0
        self.mod.reset_cycle()
        assert self.mod._accumulated == 0.0

    def test_level_clamped_zero_to_one(self):
        """Level should always be in [0.0, 1.0]."""
        self.mod._level = -5.0
        self.mod.update(CircadianPhase.WAKING)
        assert self.mod.level >= 0.0

        self.mod._level = 5.0
        self.mod.update(CircadianPhase.DEEP_SLEEP)
        assert self.mod.level <= 1.0


# ===========================================================================
# PinealOrchestrator melatonin integration tests
# ===========================================================================

class TestPinealMelatonin(unittest.TestCase):
    """Test PinealOrchestrator's melatonin integration."""

    def setUp(self):
        db = MagicMock()
        self.seph = SephirotManager(db_manager=db)
        self.pineal = PinealOrchestrator(self.seph)

    def test_pineal_has_melatonin(self):
        assert hasattr(self.pineal, 'melatonin')
        assert isinstance(self.pineal.melatonin, MelatoninModulator)

    def test_tick_returns_melatonin_status(self):
        result = self.pineal.tick(block_height=1, phi_value=0.5)
        assert "melatonin" in result
        assert "level" in result["melatonin"]

    def test_tick_includes_base_metabolic_rate(self):
        result = self.pineal.tick(block_height=1, phi_value=0.5)
        assert "metabolic_rate_base" in result
        assert result["metabolic_rate_base"] == METABOLIC_RATES[CircadianPhase.WAKING]

    def test_melatonin_dampens_metabolic_rate(self):
        """During sleep phases, effective metabolic rate should be lower than base."""
        # Force into deep sleep
        self.pineal._current_phase = CircadianPhase.DEEP_SLEEP
        self.pineal._phase_index = 5
        # Pump melatonin up
        for _ in range(20):
            self.pineal.melatonin.update(CircadianPhase.DEEP_SLEEP)
        result = self.pineal.tick(block_height=100, phi_value=0.5)
        assert result["metabolic_rate"] < result["metabolic_rate_base"]

    def test_get_status_includes_melatonin(self):
        status = self.pineal.get_status()
        assert "melatonin" in status


# ===========================================================================
# PressureMonitor tests
# ===========================================================================

class TestPressureMonitor(unittest.TestCase):
    """Test CSF pressure monitoring / load balancing."""

    def setUp(self):
        self.pm = PressureMonitor(max_pressure=10)

    def test_initial_pressure_zero(self):
        for role in SephirahRole:
            assert self.pm.get_pressure(role) == 0.0

    def test_enqueue_increases_pressure(self):
        self.pm.record_enqueue(SephirahRole.KETER)
        self.pm.record_enqueue(SephirahRole.KETER)
        assert self.pm.get_pressure(SephirahRole.KETER) == 0.2  # 2/10

    def test_dequeue_decreases_pressure(self):
        self.pm.record_enqueue(SephirahRole.KETER)
        self.pm.record_enqueue(SephirahRole.KETER)
        self.pm.record_dequeue(SephirahRole.KETER)
        assert self.pm.get_pressure(SephirahRole.KETER) == 0.1  # 1/10

    def test_dequeue_floors_at_zero(self):
        self.pm.record_dequeue(SephirahRole.KETER)
        assert self.pm.get_pressure(SephirahRole.KETER) == 0.0

    def test_congested_detection(self):
        # Threshold is 0.8 * 10 = 8
        for _ in range(8):
            self.pm.record_enqueue(SephirahRole.TIFERET)
        assert self.pm.is_congested(SephirahRole.TIFERET)

    def test_not_congested_below_threshold(self):
        for _ in range(5):
            self.pm.record_enqueue(SephirahRole.TIFERET)
        assert not self.pm.is_congested(SephirahRole.TIFERET)

    def test_least_congested_neighbor(self):
        self.pm.record_enqueue(SephirahRole.CHOCHMAH)
        self.pm.record_enqueue(SephirahRole.CHOCHMAH)
        self.pm.record_enqueue(SephirahRole.BINAH)
        neighbors = [SephirahRole.CHOCHMAH, SephirahRole.BINAH]
        least = self.pm.get_least_congested_neighbor(neighbors)
        assert least == SephirahRole.BINAH

    def test_get_status(self):
        status = self.pm.get_status()
        assert "node_pressure" in status
        assert "congested_nodes" in status
        assert "total_backpressure_events" in status


# ===========================================================================
# QuantumEntangledChannel tests
# ===========================================================================

class TestQuantumEntangledChannel(unittest.TestCase):
    """Test quantum-entangled instant delivery between SUSY pairs."""

    def setUp(self):
        self.qec = QuantumEntangledChannel()

    def test_susy_pairs_entangled(self):
        """All SUSY pairs should be recognized as entangled."""
        for expansion, constraint in SUSY_PAIRS:
            assert self.qec.is_entangled(expansion, constraint)
            assert self.qec.is_entangled(constraint, expansion)

    def test_non_pairs_not_entangled(self):
        """Non-SUSY pairs should not be entangled."""
        assert not self.qec.is_entangled(SephirahRole.KETER, SephirahRole.MALKUTH)
        assert not self.qec.is_entangled(SephirahRole.TIFERET, SephirahRole.YESOD)

    def test_get_partner(self):
        assert self.qec.get_partner(SephirahRole.CHESED) == SephirahRole.GEVURAH
        assert self.qec.get_partner(SephirahRole.GEVURAH) == SephirahRole.CHESED
        assert self.qec.get_partner(SephirahRole.CHOCHMAH) == SephirahRole.BINAH
        assert self.qec.get_partner(SephirahRole.NETZACH) == SephirahRole.HOD

    def test_no_partner_for_unpaired(self):
        assert self.qec.get_partner(SephirahRole.KETER) is None
        assert self.qec.get_partner(SephirahRole.TIFERET) is None
        assert self.qec.get_partner(SephirahRole.MALKUTH) is None

    def test_deliver_entangled(self):
        msg = CSFMessage(
            source=SephirahRole.CHESED,
            destination=SephirahRole.GEVURAH,
            payload='{"test": true}',
        )
        result = self.qec.deliver_entangled(msg)
        assert result.delivered
        assert self.qec._entangled_deliveries == 1

    def test_get_status(self):
        status = self.qec.get_status()
        assert "pairs" in status
        assert len(status["pairs"]) == len(SUSY_PAIRS)
        assert "total_entangled_deliveries" in status


# ===========================================================================
# CSFTransport integration tests (pressure + entanglement)
# ===========================================================================

class TestCSFTransportIntegration(unittest.TestCase):
    """Test CSFTransport with pressure monitoring and entangled channels."""

    def setUp(self):
        self.transport = CSFTransport()

    def test_has_pressure_and_entangled(self):
        if _using_rust_csf():
            # Rust backend exposes pressure/entanglement via methods, not attributes
            assert callable(getattr(self.transport, 'get_pressure', None))
            assert callable(getattr(self.transport, 'is_entangled', None))
        else:
            assert hasattr(self.transport, 'pressure')
            assert hasattr(self.transport, 'entangled')

    def test_entangled_send_bypasses_queue(self):
        """Sending between SUSY pairs should deliver instantly."""
        payload = '{"data": "test"}' if _using_rust_csf() else {"data": "test"}
        msg = self.transport.send(
            SephirahRole.CHESED, SephirahRole.GEVURAH,
            payload=payload
        )
        assert msg.delivered
        if _using_rust_csf():
            # Rust backend: verify queue is empty via method
            assert self.transport.queue_size() == 0
            assert self.transport.total_entangled_deliveries() >= 1
        else:
            # Should NOT be in the queue
            assert len(self.transport._queue) == 0
            # Should be in delivered
            assert msg in self.transport._delivered

    def test_normal_send_uses_queue(self):
        """Non-entangled sends go through normal routing."""
        payload = '{"data": "test"}' if _using_rust_csf() else {"data": "test"}
        msg = self.transport.send(
            SephirahRole.KETER, SephirahRole.MALKUTH,
            payload=payload
        )
        assert not msg.delivered
        if _using_rust_csf():
            assert self.transport.queue_size() == 1
        else:
            assert len(self.transport._queue) == 1

    def test_backpressure_deprioritizes(self):
        """Congested destination should halve message priority."""
        if _using_rust_csf():
            # Rust backend does not expose pressure attribute directly.
            # Instead, flood the destination via normal sends to trigger
            # internal backpressure, then verify priority is halved.
            payload = '{"x": 1}'
            for _ in range(50):
                self.transport.send(
                    SephirahRole.YESOD, SephirahRole.MALKUTH,
                    payload=payload, priority_qbc=0.01
                )
            msg = self.transport.send(
                SephirahRole.KETER, SephirahRole.MALKUTH,
                payload=payload, priority_qbc=10.0
            )
            # Priority should be halved due to backpressure
            assert msg.priority_qbc == 5.0
        else:
            # Flood Malkuth queue
            for _ in range(50):
                self.transport.pressure.record_enqueue(SephirahRole.MALKUTH)

            msg = self.transport.send(
                SephirahRole.KETER, SephirahRole.MALKUTH,
                payload={"x": 1}, priority_qbc=10.0
            )
            # Priority should be halved due to backpressure
            assert msg.priority_qbc == 5.0

    def test_stats_include_pressure_and_entangled(self):
        stats = self.transport.get_stats()
        assert "pressure" in stats
        assert "entangled_channels" in stats

    def test_process_queue_updates_pressure(self):
        """Processing messages should dequeue pressure counts."""
        # Send a direct neighbor message
        payload = '{"test": true}' if _using_rust_csf() else {"test": True}
        self.transport.send(
            SephirahRole.KETER, SephirahRole.CHOCHMAH,
            payload=payload
        )
        # Chochmah is a neighbor of Keter -- should be delivered
        # But only if not entangled. Keter/Chochmah are NOT a SUSY pair.
        if _using_rust_csf():
            assert self.transport.queue_size() == 1
        else:
            assert len(self.transport._queue) == 1
        delivered = self.transport.process_queue()
        assert len(delivered) == 1
        assert delivered[0].delivered


# ===========================================================================
# SnapshotScheduler restore_from_snapshot tests
# ===========================================================================

class TestSnapshotRestore(unittest.TestCase):
    """Test snapshot restoration from IPFS."""

    def setUp(self):
        self.scheduler = SnapshotScheduler(interval_blocks=100)

    def _make_mock_ipfs(self, snapshot_data):
        """Create a mock IPFS manager that returns given snapshot data."""
        ipfs = MagicMock()
        ipfs.retrieve_snapshot.return_value = snapshot_data
        return ipfs

    def _make_mock_db(self):
        """Create a mock DB manager with a session context manager."""
        db = MagicMock()
        session = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        return db, session

    def test_restore_valid_snapshot(self):
        snapshot = {
            'version': '2.0',
            'height': 500,
            'blocks': [
                {'height': 1, 'prev_hash': '0x00', 'difficulty': 0.5,
                 'block_hash': '0xabc', 'created_at': '2025-01-01'},
            ],
            'utxos': [
                {'txid': 'tx1', 'vout': 0, 'amount': '100', 'address': 'qbc1abc',
                 'block_height': 1},
            ],
            'transactions': [
                {'txid': 'tx1', 'block_height': 1, 'fee': '0.001'},
            ],
        }
        db, session = self._make_mock_db()
        ipfs = self._make_mock_ipfs(snapshot)

        result = self.scheduler.restore_from_snapshot('QmTest', db, ipfs)
        assert result['success']
        assert result['height'] == 500
        assert result['blocks_restored'] == 1
        assert result['utxos_restored'] == 1
        assert result['txs_restored'] == 1

    def test_restore_missing_keys_raises(self):
        bad_snapshot = {'version': '2.0'}  # Missing required keys
        db, session = self._make_mock_db()
        ipfs = self._make_mock_ipfs(bad_snapshot)

        with self.assertRaises(ValueError):
            self.scheduler.restore_from_snapshot('QmBad', db, ipfs)

    def test_restore_null_snapshot_raises(self):
        db, _ = self._make_mock_db()
        ipfs = self._make_mock_ipfs(None)  # IPFS returns None

        with self.assertRaises(ValueError):
            self.scheduler.restore_from_snapshot('QmNone', db, ipfs)

    def test_restore_no_retrieve_method_raises(self):
        db, _ = self._make_mock_db()
        ipfs = MagicMock(spec=[])  # No retrieve_snapshot method

        with self.assertRaises(RuntimeError):
            self.scheduler.restore_from_snapshot('QmNoMethod', db, ipfs)

    def test_restore_empty_snapshot(self):
        snapshot = {
            'version': '2.0',
            'height': 0,
            'blocks': [],
            'utxos': [],
            'transactions': [],
        }
        db, session = self._make_mock_db()
        ipfs = self._make_mock_ipfs(snapshot)

        result = self.scheduler.restore_from_snapshot('QmEmpty', db, ipfs)
        assert result['success']
        assert result['blocks_restored'] == 0


# ===========================================================================
# Config IPFS Gateway Port test
# ===========================================================================

class TestConfigIPFSGateway(unittest.TestCase):
    """Test IPFS gateway port configuration."""

    def test_gateway_port_default(self):
        from qubitcoin.config import Config
        assert hasattr(Config, 'IPFS_GATEWAY_PORT')
        assert Config.IPFS_GATEWAY_PORT == 8081

    def test_gateway_port_not_8080(self):
        """Gateway port must not conflict with CockroachDB admin UI (8080)."""
        from qubitcoin.config import Config
        assert Config.IPFS_GATEWAY_PORT != 8080


if __name__ == '__main__':
    unittest.main()
