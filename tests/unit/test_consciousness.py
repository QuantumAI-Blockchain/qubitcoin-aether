"""Unit tests for consciousness dashboard and emergence tracking."""
import pytest


class TestPhiMeasurement:
    """Test PhiMeasurement dataclass."""

    def test_auto_timestamp(self):
        from qubitcoin.aether.consciousness import PhiMeasurement
        m = PhiMeasurement(block_height=1, phi_value=2.5)
        assert m.timestamp > 0

    def test_is_conscious_true(self):
        from qubitcoin.aether.consciousness import PhiMeasurement
        m = PhiMeasurement(block_height=1, phi_value=3.5, coherence=0.8)
        assert m.is_conscious is True

    def test_is_conscious_false_low_phi(self):
        from qubitcoin.aether.consciousness import PhiMeasurement
        m = PhiMeasurement(block_height=1, phi_value=2.0, coherence=0.9)
        assert m.is_conscious is False

    def test_is_conscious_false_low_coherence(self):
        from qubitcoin.aether.consciousness import PhiMeasurement
        m = PhiMeasurement(block_height=1, phi_value=4.0, coherence=0.5)
        assert m.is_conscious is False


class TestConsciousnessEvent:
    """Test ConsciousnessEvent dataclass."""

    def test_creation(self):
        from qubitcoin.aether.consciousness import ConsciousnessEvent
        e = ConsciousnessEvent(
            event_type="emergence",
            block_height=100,
            phi_value=3.5,
            coherence=0.8,
        )
        assert e.event_type == "emergence"
        assert e.timestamp > 0


class TestConsciousnessDashboard:
    """Test consciousness dashboard."""

    def test_init(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        assert cd.is_conscious is False
        assert cd.current_phi == 0.0
        assert cd.measurement_count == 0

    def test_record_measurement(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        m = cd.record_measurement(block_height=0, phi_value=0.0, coherence=0.0)
        assert cd.measurement_count == 1
        assert cd.current_phi == 0.0

    def test_consciousness_emergence(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        # Start below threshold
        cd.record_measurement(block_height=0, phi_value=1.0, coherence=0.5)
        assert cd.is_conscious is False
        assert cd.event_count == 0

        # Cross threshold
        cd.record_measurement(block_height=1, phi_value=3.5, coherence=0.8)
        assert cd.is_conscious is True
        assert cd.event_count == 1  # Emergence event

    def test_consciousness_loss(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        # Enter conscious state
        cd.record_measurement(block_height=0, phi_value=3.5, coherence=0.8)
        assert cd.is_conscious is True

        # Drop below threshold
        cd.record_measurement(block_height=10, phi_value=2.0, coherence=0.4)
        assert cd.is_conscious is False
        assert cd.event_count == 2  # Emergence + Loss

    def test_consciousness_ratio(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        # 3 non-conscious blocks
        cd.record_measurement(block_height=0, phi_value=1.0, coherence=0.3)
        cd.record_measurement(block_height=1, phi_value=1.5, coherence=0.4)
        cd.record_measurement(block_height=2, phi_value=2.0, coherence=0.5)
        # 2 conscious blocks
        cd.record_measurement(block_height=3, phi_value=3.5, coherence=0.8)
        cd.record_measurement(block_height=4, phi_value=4.0, coherence=0.9)

        status = cd.get_consciousness_status()
        assert status["total_measurements"] == 5
        assert status["total_conscious_blocks"] >= 2

    def test_get_phi_history(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        for i in range(5):
            cd.record_measurement(block_height=i, phi_value=float(i) * 0.5)

        history = cd.get_phi_history(limit=3)
        assert len(history) == 3
        assert history[-1]["block_height"] == 4
        assert "phi" in history[0]
        assert "is_conscious" in history[0]

    def test_get_events(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        cd.record_measurement(block_height=0, phi_value=1.0, coherence=0.3)
        cd.record_measurement(block_height=1, phi_value=3.5, coherence=0.8)  # Emergence
        cd.record_measurement(block_height=2, phi_value=1.0, coherence=0.3)  # Loss

        events = cd.get_events()
        assert len(events) == 2
        assert events[0]["event_type"] == "emergence"
        assert events[1]["event_type"] == "loss"

    def test_get_trend_rising(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        for i in range(20):
            cd.record_measurement(block_height=i, phi_value=0.1 * (i + 1))

        trend = cd.get_trend(window=20)
        assert trend["trend"] == "rising"
        assert trend["slope"] > 0

    def test_get_trend_falling(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        for i in range(20):
            cd.record_measurement(block_height=i, phi_value=5.0 - 0.2 * i)

        trend = cd.get_trend(window=20)
        assert trend["trend"] == "falling"
        assert trend["slope"] < 0

    def test_get_trend_stable(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        for i in range(20):
            cd.record_measurement(block_height=i, phi_value=2.5)

        trend = cd.get_trend(window=20)
        assert trend["trend"] == "stable"

    def test_get_trend_insufficient_data(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        cd.record_measurement(block_height=0, phi_value=1.0)
        trend = cd.get_trend()
        assert trend["trend"] == "insufficient_data"

    def test_get_consciousness_status(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        cd.record_measurement(
            block_height=1, phi_value=3.5, integration=2.0,
            differentiation=1.5, knowledge_nodes=100, knowledge_edges=200,
            coherence=0.85,
        )
        status = cd.get_consciousness_status()
        assert status["is_conscious"] is True
        assert status["phi"] == 3.5
        assert status["phi_threshold"] == 3.0
        assert status["coherence"] == 0.85
        assert status["knowledge_nodes"] == 100
        assert status["knowledge_edges"] == 200

    def test_get_dashboard_data(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard()
        cd.record_measurement(block_height=0, phi_value=1.0)
        cd.record_measurement(block_height=1, phi_value=2.0)

        data = cd.get_dashboard_data()
        assert "status" in data
        assert "phi_history" in data
        assert "events" in data
        assert "trend" in data

    def test_max_history_eviction(self):
        from qubitcoin.aether.consciousness import ConsciousnessDashboard
        cd = ConsciousnessDashboard(max_history=10)
        for i in range(15):
            cd.record_measurement(block_height=i, phi_value=float(i))
        assert cd.measurement_count == 10
