"""Tests for risk score normalization (Batch 16.3)."""
import pytest

from qubitcoin.qvm.risk import RiskNormalizer, RiskBreakdown, _clamp


class TestClamp:
    def test_within_range(self):
        assert _clamp(50.0) == 50.0

    def test_below_zero(self):
        assert _clamp(-10.0) == 0.0

    def test_above_hundred(self):
        assert _clamp(150.0) == 100.0

    def test_exact_bounds(self):
        assert _clamp(0.0) == 0.0
        assert _clamp(100.0) == 100.0


class TestRiskNormalizer:
    def test_all_zero(self):
        norm = RiskNormalizer()
        result = norm.normalize('addr', 0, 0, 0, 0)
        assert result.total_score == 0.0

    def test_all_max(self):
        norm = RiskNormalizer()
        result = norm.normalize('addr', 100, 100, 100, 100)
        assert result.total_score == 100.0

    def test_weighted_combination(self):
        norm = RiskNormalizer()
        result = norm.normalize('addr', aml_score=100, graph_score=0,
                                compliance_score=0, raw_qrisk=0)
        assert result.total_score == pytest.approx(35.0)  # 0.35 * 100

    def test_custom_weights(self):
        norm = RiskNormalizer(weights={'aml': 1.0, 'graph': 0.0,
                                       'compliance': 0.0, 'qrisk': 0.0})
        result = norm.normalize('addr', aml_score=50)
        assert result.total_score == pytest.approx(50.0)

    def test_clamped_inputs(self):
        norm = RiskNormalizer()
        result = norm.normalize('addr', aml_score=200, raw_qrisk=-50)
        assert result.aml_score == 100.0
        assert result.raw_qrisk == 0.0

    def test_breakdown_fields(self):
        norm = RiskNormalizer()
        result = norm.normalize('addr', 10, 20, 30, 40)
        assert result.address == 'addr'
        assert result.aml_score == 10.0
        assert result.graph_score == 20.0
        assert result.compliance_score == 30.0
        assert result.raw_qrisk == 40.0


class TestRiskLevel:
    def test_low(self):
        bd = RiskBreakdown(address='a', total_score=10.0)
        assert bd.risk_level == 'low'

    def test_medium(self):
        bd = RiskBreakdown(address='a', total_score=30.0)
        assert bd.risk_level == 'medium'

    def test_high(self):
        bd = RiskBreakdown(address='a', total_score=60.0)
        assert bd.risk_level == 'high'

    def test_critical(self):
        bd = RiskBreakdown(address='a', total_score=90.0)
        assert bd.risk_level == 'critical'

    def test_boundary_20(self):
        bd = RiskBreakdown(address='a', total_score=20.0)
        assert bd.risk_level == 'medium'

    def test_boundary_50(self):
        bd = RiskBreakdown(address='a', total_score=50.0)
        assert bd.risk_level == 'high'


class TestNormalizeRawQrisk:
    def test_default_low(self):
        norm = RiskNormalizer()
        # Default QRISK opcode value: 10 * 10^16
        score = norm.normalize_raw_qrisk(10 * 10**16)
        assert score == pytest.approx(10.0)

    def test_zero(self):
        norm = RiskNormalizer()
        assert norm.normalize_raw_qrisk(0) == 0.0

    def test_max(self):
        norm = RiskNormalizer()
        score = norm.normalize_raw_qrisk(100 * 10**16)
        assert score == 100.0

    def test_over_max(self):
        norm = RiskNormalizer()
        score = norm.normalize_raw_qrisk(200 * 10**16)
        assert score == 100.0


class TestNormalizeGraphMetrics:
    def test_empty_graph(self):
        norm = RiskNormalizer()
        score = norm.normalize_graph_metrics(0, 0, 0)
        assert score == 0.0

    def test_small_graph(self):
        norm = RiskNormalizer()
        score = norm.normalize_graph_metrics(5, 10, 2)
        assert 0.0 < score < 50.0

    def test_large_graph(self):
        norm = RiskNormalizer()
        score = norm.normalize_graph_metrics(50, 100, 6, suspicious_ratio=0.5)
        assert score > 50.0

    def test_suspicious_ratio(self):
        norm = RiskNormalizer()
        clean = norm.normalize_graph_metrics(10, 10, 2, suspicious_ratio=0.0)
        suspicious = norm.normalize_graph_metrics(10, 10, 2, suspicious_ratio=1.0)
        assert suspicious > clean


class TestRiskBreakdownDict:
    def test_to_dict(self):
        bd = RiskBreakdown(
            address='test', total_score=42.5,
            aml_score=10.0, graph_score=20.0,
        )
        d = bd.to_dict()
        assert d['address'] == 'test'
        assert d['total_score'] == 42.5
        assert d['risk_level'] == 'medium'
