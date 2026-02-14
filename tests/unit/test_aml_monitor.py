"""Tests for AML monitoring module — transaction pattern detection (Batch 15.3)."""
import pytest

from qubitcoin.qvm.aml import AMLMonitor, AMLAlert, AlertType


class TestRecordTransaction:
    """Basic recording and retrieval."""

    def test_record_does_not_crash(self):
        mon = AMLMonitor()
        alerts = mon.record_transaction('alice', 'bob', 50.0, 1000.0)
        assert isinstance(alerts, list)

    def test_no_alerts_for_normal_tx(self):
        mon = AMLMonitor()
        alerts = mon.record_transaction('alice', 'bob', 50.0, 1000.0)
        assert len(alerts) == 0


class TestStructuringDetection:
    """Detect rapid small transactions."""

    def test_structuring_flagged(self):
        mon = AMLMonitor()
        now = 10000.0
        for i in range(6):
            alerts = mon.record_transaction(
                'smurf', f'dest{i}', 500.0, now + i
            )
        # Last call should trigger structuring alert
        assert any(a.alert_type == AlertType.STRUCTURING for a in alerts)

    def test_structuring_not_flagged_below_count(self):
        mon = AMLMonitor()
        alerts = []
        for i in range(3):  # Below STRUCTURING_MIN_COUNT=5
            alerts = mon.record_transaction(
                'normal', f'dest{i}', 500.0, 1000.0 + i
            )
        assert not any(a.alert_type == AlertType.STRUCTURING for a in alerts)

    def test_structuring_not_flagged_large_amounts(self):
        mon = AMLMonitor()
        now = 10000.0
        alerts = []
        for i in range(6):
            alerts = mon.record_transaction(
                'whale', f'dest{i}', 5000.0, now + i  # Above 1000 threshold
            )
        assert not any(a.alert_type == AlertType.STRUCTURING for a in alerts)


class TestVolumeSpikeDetection:
    """Detect sudden volume increases."""

    def test_spike_detected(self):
        mon = AMLMonitor()
        # Baseline: small transactions
        for i in range(5):
            mon.record_transaction('spiker', 'dest', 10.0, 1000.0 + i, block_height=i)
        # Spike: large transaction
        alerts = mon.record_transaction('spiker', 'dest', 500.0, 2000.0, block_height=6)
        assert any(a.alert_type == AlertType.VOLUME_SPIKE for a in alerts)

    def test_no_spike_for_consistent_amounts(self):
        mon = AMLMonitor()
        alerts = []
        for i in range(5):
            alerts = mon.record_transaction('steady', 'dest', 100.0, 1000.0 + i, block_height=i)
        assert not any(a.alert_type == AlertType.VOLUME_SPIKE for a in alerts)


class TestRoundAmountDetection:
    """Detect round-number transaction clustering."""

    def test_round_amounts_flagged(self):
        mon = AMLMonitor()
        alerts = []
        for i in range(4):
            alerts = mon.record_transaction(
                'launderer', f'dest{i}', 1000.0, 10000.0 + i  # All round
            )
        assert any(a.alert_type == AlertType.ROUND_AMOUNTS for a in alerts)

    def test_non_round_amounts_ok(self):
        mon = AMLMonitor()
        alerts = []
        for i in range(4):
            alerts = mon.record_transaction(
                'normal', f'dest{i}', 123.45, 10000.0 + i
            )
        assert not any(a.alert_type == AlertType.ROUND_AMOUNTS for a in alerts)


class TestFanOutDetection:
    """Detect 1→many fan-out pattern."""

    def test_fan_out_flagged(self):
        mon = AMLMonitor()
        now = 10000.0
        alerts = []
        for i in range(6):
            alerts = mon.record_transaction(
                'distributor', f'unique_dest_{i}', 100.0, now + i
            )
        assert any(a.alert_type == AlertType.FAN_OUT for a in alerts)

    def test_fan_out_not_flagged_same_recipient(self):
        mon = AMLMonitor()
        now = 10000.0
        alerts = []
        for i in range(6):
            alerts = mon.record_transaction(
                'sender', 'same_dest', 100.0, now + i  # Same recipient
            )
        assert not any(a.alert_type == AlertType.FAN_OUT for a in alerts)


class TestRiskScore:
    """Test aggregate risk scoring."""

    def test_no_alerts_zero_risk(self):
        mon = AMLMonitor()
        assert mon.get_risk_score('nobody') == 0.0

    def test_risk_score_accumulates(self):
        mon = AMLMonitor()
        # Trigger structuring (30 points) + fan_out (20 points)
        now = 10000.0
        for i in range(6):
            mon.record_transaction('risky', f'dest_{i}', 500.0, now + i)
        score = mon.get_risk_score('risky')
        assert score > 0.0

    def test_risk_score_capped_at_100(self):
        mon = AMLMonitor()
        # Manually inject many alerts
        for _ in range(10):
            mon._alerts.append(AMLAlert(
                alert_type='test', address='over', score=20.0, details='test'
            ))
        assert mon.get_risk_score('over') == 100.0


class TestAlertManagement:
    """Test alert retrieval and clearing."""

    def test_get_alerts_by_address(self):
        mon = AMLMonitor()
        mon._alerts.append(AMLAlert(
            alert_type='x', address='a', score=10.0, details='test'
        ))
        mon._alerts.append(AMLAlert(
            alert_type='y', address='b', score=20.0, details='test'
        ))
        assert len(mon.get_alerts('a')) == 1
        assert len(mon.get_alerts('b')) == 1

    def test_get_all_alerts(self):
        mon = AMLMonitor()
        mon._alerts.append(AMLAlert(
            alert_type='x', address='a', score=10.0, details='test'
        ))
        assert len(mon.get_alerts()) == 1

    def test_clear_alerts_by_address(self):
        mon = AMLMonitor()
        mon._alerts.append(AMLAlert(
            alert_type='x', address='a', score=10.0, details='test'
        ))
        mon._alerts.append(AMLAlert(
            alert_type='y', address='b', score=20.0, details='test'
        ))
        removed = mon.clear_alerts('a')
        assert removed == 1
        assert len(mon.get_alerts()) == 1

    def test_clear_all_alerts(self):
        mon = AMLMonitor()
        mon._alerts.append(AMLAlert(
            alert_type='x', address='a', score=10.0, details='test'
        ))
        removed = mon.clear_alerts()
        assert removed == 1
        assert len(mon.get_alerts()) == 0

    def test_alert_to_dict(self):
        alert = AMLAlert(
            alert_type=AlertType.STRUCTURING,
            address='test_addr',
            score=30.0,
            details='5 small txs',
            block_height=42,
        )
        d = alert.to_dict()
        assert d['alert_type'] == 'structuring'
        assert d['score'] == 30.0
        assert d['block_height'] == 42
