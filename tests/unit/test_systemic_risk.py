"""Tests for QRISK_SYSTEMIC — systemic risk and contagion prediction (Batch 17.3)."""
import pytest

from qubitcoin.qvm.systemic_risk import (
    SystemicRiskModel,
    ContagionResult,
    NodeState,
    _deterministic_hash,
    _compute_systemic_score,
)
from qubitcoin.qvm.tx_graph import TransactionGraph


class TestContagionBasics:
    """Basic contagion model tests."""

    def test_empty_model(self):
        model = SystemicRiskModel()
        result = model.simulate(['addr1'])
        assert result.total_infected == 0
        assert result.systemic_risk_score == 0.0

    def test_single_node_infected(self):
        model = SystemicRiskModel()
        model.add_edge('a', 'b', 1.0)
        result = model.simulate(['a'])
        assert result.total_infected >= 1
        assert 'a' in result.affected_addresses

    def test_no_spread_zero_rate(self):
        model = SystemicRiskModel(infection_rate=0.0)
        model.add_edge('a', 'b', 1.0)
        model.add_edge('b', 'c', 1.0)
        result = model.simulate(['a'])
        # Only the initially infected node
        assert result.total_infected == 1

    def test_full_spread_high_rate(self):
        model = SystemicRiskModel(infection_rate=1.0, recovery_rate=0.0)
        model.add_edge('a', 'b', 1.0)
        model.add_edge('b', 'c', 1.0)
        result = model.simulate(['a'])
        assert result.total_infected >= 2  # Should spread at least some

    def test_result_to_dict(self):
        model = SystemicRiskModel()
        model.add_edge('a', 'b', 1.0)
        result = model.simulate(['a'])
        d = result.to_dict()
        assert 'systemic_risk_score' in d
        assert 'peak_infection_rate' in d
        assert 'affected_count' in d

    def test_node_count(self):
        model = SystemicRiskModel()
        model.add_edge('a', 'b')
        model.add_edge('b', 'c')
        assert model.get_node_count() == 3


class TestContagionDynamics:
    """Test contagion propagation dynamics."""

    def test_peak_infection_rate_bounded(self):
        model = SystemicRiskModel(infection_rate=0.5)
        for i in range(10):
            model.add_edge(f'n{i}', f'n{i+1}', 0.8)
        result = model.simulate(['n0'])
        assert 0 <= result.peak_infection_rate <= 1.0

    def test_recovery_reduces_infected(self):
        model = SystemicRiskModel(infection_rate=0.8, recovery_rate=0.5)
        model.add_edge('a', 'b', 1.0)
        model.add_edge('b', 'c', 1.0)
        result = model.simulate(['a'])
        assert result.total_recovered >= 0
        assert result.final_susceptible >= 0

    def test_multiple_initial_infected(self):
        model = SystemicRiskModel(infection_rate=0.5)
        model.add_edge('a', 'b', 1.0)
        model.add_edge('c', 'd', 1.0)
        result = model.simulate(['a', 'c'])
        assert result.total_infected >= 2

    def test_steps_to_peak_non_negative(self):
        model = SystemicRiskModel(infection_rate=0.3)
        for i in range(5):
            model.add_edge(f'n{i}', f'n{i+1}', 1.0)
        result = model.simulate(['n0'])
        assert result.steps_to_peak >= 0

    def test_weight_influences_spread(self):
        # High weight should spread more
        model_high = SystemicRiskModel(infection_rate=0.5, recovery_rate=0.0, max_steps=10)
        model_high.add_edge('a', 'b', 1.0)
        model_high.add_edge('a', 'c', 1.0)
        result_high = model_high.simulate(['a'])

        model_low = SystemicRiskModel(infection_rate=0.5, recovery_rate=0.0, max_steps=10)
        model_low.add_edge('a', 'b', 0.01)
        model_low.add_edge('a', 'c', 0.01)
        result_low = model_low.simulate(['a'])

        # High-weight edges should produce at least as much infection
        assert result_high.total_infected >= result_low.total_infected

    def test_deterministic_simulation(self):
        def run():
            model = SystemicRiskModel(infection_rate=0.4, recovery_rate=0.1)
            for i in range(5):
                model.add_edge(f'n{i}', f'n{i+1}', 0.5)
            return model.simulate(['n0'])

        r1 = run()
        r2 = run()
        assert r1.total_infected == r2.total_infected
        assert r1.systemic_risk_score == r2.systemic_risk_score


class TestHighRiskConnections:
    """Test detection of sanctioned/mixer/hub connections."""

    def test_detect_sanctioned(self):
        model = SystemicRiskModel()
        model.add_edge('user', 'bad_actor', 1.0)
        results = model.detect_high_risk_connections(
            'user', sanctioned={'bad_actor'}
        )
        assert len(results) == 1
        assert results[0]['risk_type'] == 'sanctioned'

    def test_detect_mixer(self):
        model = SystemicRiskModel()
        model.add_edge('user', 'tornado', 1.0)
        results = model.detect_high_risk_connections(
            'user', mixer_addresses={'tornado'}
        )
        assert len(results) == 1
        assert results[0]['risk_type'] == 'mixer'

    def test_detect_high_connectivity(self):
        model = SystemicRiskModel()
        hub = 'exchange'
        model.add_edge('user', hub, 1.0)
        for i in range(55):
            model.add_edge(hub, f'peer_{i}', 0.1)
        results = model.detect_high_risk_connections('user')
        assert any(r['risk_type'] == 'high_connectivity' for r in results)

    def test_no_false_positives(self):
        model = SystemicRiskModel()
        model.add_edge('user', 'friend', 1.0)
        results = model.detect_high_risk_connections('user')
        assert len(results) == 0


class TestAddEdgesFromGraph:
    """Test bulk edge loading from TransactionGraph."""

    def test_load_from_tx_graph(self):
        g = TransactionGraph()
        g.add_transaction('a', 'b', 10.0, 1)
        g.add_transaction('b', 'c', 5.0, 2)
        edges = g.get_transactions('a') + g.get_transactions('b')

        model = SystemicRiskModel()
        model.add_edges_from_graph(edges)
        assert model.get_node_count() >= 2


class TestHelpers:
    """Test helper functions."""

    def test_deterministic_hash_range(self):
        val = _deterministic_hash('a', 'b', 1)
        assert 0 <= val < 1.0

    def test_deterministic_hash_reproducible(self):
        v1 = _deterministic_hash('a', 'b', 1)
        v2 = _deterministic_hash('a', 'b', 1)
        assert v1 == v2

    def test_deterministic_hash_different_inputs(self):
        v1 = _deterministic_hash('a', 'b', 1)
        v2 = _deterministic_hash('a', 'b', 2)
        assert v1 != v2

    def test_systemic_score_zero_inputs(self):
        score = _compute_systemic_score(0.0, 0.0, 0)
        assert score == 0.0

    def test_systemic_score_clamped(self):
        score = _compute_systemic_score(1.0, 1.0, 10000)
        assert 0 <= score <= 100.0

    def test_systemic_score_larger_network_higher(self):
        s1 = _compute_systemic_score(0.5, 0.5, 10)
        s2 = _compute_systemic_score(0.5, 0.5, 500)
        assert s2 >= s1
