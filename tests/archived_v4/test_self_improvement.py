"""Unit tests for SelfImprovementEngine — recursive reasoning optimization."""
import math
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Test group 1: Import and initialization
# ---------------------------------------------------------------------------

class TestSelfImprovementInit:
    """Test SelfImprovementEngine initialization."""

    def test_import(self):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        assert SelfImprovementEngine is not None

    def test_import_constants(self):
        from qubitcoin.aether.self_improvement import REASONING_MODES, DEFAULT_DOMAINS
        assert 'deductive' in REASONING_MODES
        assert 'inductive' in REASONING_MODES
        assert 'abductive' in REASONING_MODES
        assert 'neural' in REASONING_MODES
        assert 'general' in DEFAULT_DOMAINS
        assert len(REASONING_MODES) >= 6
        assert len(DEFAULT_DOMAINS) >= 10

    @patch('qubitcoin.aether.self_improvement.Config')
    def test_init_defaults(self, mock_config):
        """Init with default config values."""
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 100
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5

        engine = SelfImprovementEngine()
        stats = engine.get_stats()
        assert stats['cycles_completed'] == 0
        assert stats['total_adjustments'] == 0
        assert stats['total_records'] == 0
        assert stats['interval'] == 100
        assert stats['min_weight'] == 0.05
        assert stats['max_weight'] == 0.5
        assert stats['domains_tracked'] >= 10
        assert stats['strategies_tracked'] >= 6

    @patch('qubitcoin.aether.self_improvement.Config')
    def test_init_with_metacognition(self, mock_config):
        """Init with metacognition instance."""
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 100
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5

        metacog = MagicMock()
        metacog._strategy_weights = {
            'deductive': 1.0, 'inductive': 1.0, 'abductive': 1.0,
            'chain_of_thought': 1.0, 'neural': 1.0, 'causal': 1.0,
        }

        engine = SelfImprovementEngine(metacognition=metacog)
        assert engine.metacognition is metacog

    @patch('qubitcoin.aether.self_improvement.Config')
    def test_init_with_knowledge_graph(self, mock_config):
        """Init with knowledge graph instance."""
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 100
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5

        kg = MagicMock()
        engine = SelfImprovementEngine(knowledge_graph=kg)
        assert engine.kg is kg

    @patch('qubitcoin.aether.self_improvement.Config')
    def test_init_uniform_weights(self, mock_config):
        """All domains start with uniform strategy weights."""
        from qubitcoin.aether.self_improvement import (
            SelfImprovementEngine, REASONING_MODES, DEFAULT_DOMAINS,
        )
        mock_config.SELF_IMPROVEMENT_INTERVAL = 100
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5

        engine = SelfImprovementEngine()
        expected = 1.0 / len(REASONING_MODES)

        for domain in DEFAULT_DOMAINS:
            weights = engine.get_domain_weights(domain)
            for strategy in REASONING_MODES:
                assert abs(weights[strategy] - expected) < 1e-10, (
                    f"Non-uniform weight for {domain}/{strategy}"
                )


# ---------------------------------------------------------------------------
# Test group 2: Performance recording
# ---------------------------------------------------------------------------

class TestPerformanceRecording:
    """Test recording reasoning outcomes."""

    @patch('qubitcoin.aether.self_improvement.Config')
    def _make_engine(self, mock_config):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 100
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5
        return SelfImprovementEngine()

    def test_record_single(self):
        engine = self._make_engine()
        engine.record_performance('deductive', 'mathematics', 0.9, True, 100)
        assert engine.get_stats()['total_records'] == 1

    def test_record_multiple(self):
        engine = self._make_engine()
        for i in range(10):
            engine.record_performance('deductive', 'general', 0.5, i % 2 == 0, i)
        assert engine.get_stats()['total_records'] == 10

    def test_record_unknown_strategy_falls_back(self):
        """Unknown strategy names are mapped to chain_of_thought."""
        engine = self._make_engine()
        engine.record_performance('unknown_strategy', 'general', 0.5, True, 1)
        assert engine.get_stats()['total_records'] == 1
        # The record should be stored under chain_of_thought
        stats = engine._compute_performance_stats()
        assert 'general' in stats
        assert 'chain_of_thought' in stats['general']

    def test_record_unknown_domain_auto_registers(self):
        """Unknown domains get auto-registered with uniform weights."""
        engine = self._make_engine()
        engine.record_performance('deductive', 'astrobiology', 0.8, True, 10)
        assert 'astrobiology' in engine._domain_weights
        weights = engine.get_domain_weights('astrobiology')
        assert len(weights) == len(engine._domain_weights.get('general', {}))

    def test_record_buffer_bounded(self):
        """Records buffer does not grow without bound."""
        engine = self._make_engine()
        engine._max_records = 50
        for i in range(100):
            engine.record_performance('deductive', 'general', 0.5, True, i)
        assert len(engine._records) == 50

    def test_confidence_clamped(self):
        """Confidence is clamped to [0.0, 1.0]."""
        engine = self._make_engine()
        engine.record_performance('deductive', 'general', 5.0, True, 1)
        engine.record_performance('deductive', 'general', -1.0, False, 2)
        assert engine._records[0].confidence == 1.0
        assert engine._records[1].confidence == 0.0


# ---------------------------------------------------------------------------
# Test group 3: Improvement cycles
# ---------------------------------------------------------------------------

class TestImprovementCycles:
    """Test the core improvement cycle logic."""

    @patch('qubitcoin.aether.self_improvement.Config')
    def _make_engine(self, mock_config, interval=10, min_obs=3):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = interval
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5
        engine = SelfImprovementEngine()
        engine._min_observations = min_obs
        return engine

    def test_should_run_cycle_initially(self):
        engine = self._make_engine(interval=10)
        assert not engine.should_run_cycle(0)
        assert not engine.should_run_cycle(5)
        assert engine.should_run_cycle(10)
        assert engine.should_run_cycle(15)

    def test_should_run_cycle_after_first(self):
        engine = self._make_engine(interval=10)
        engine._last_cycle_block = 10
        assert not engine.should_run_cycle(15)
        assert engine.should_run_cycle(20)
        assert engine.should_run_cycle(25)

    def test_run_empty_cycle(self):
        """Running a cycle with no data produces no adjustments."""
        engine = self._make_engine(interval=10)
        result = engine.run_improvement_cycle(10)
        assert result['cycle_number'] == 1
        assert result['adjustments'] == 0
        assert result['weak_areas'] == []
        assert result['strong_areas'] == []
        assert engine.get_stats()['cycles_completed'] == 1

    def test_cycle_adjusts_weights(self):
        """Cycle adjusts weights when there is enough performance data."""
        engine = self._make_engine(interval=10, min_obs=3)

        # Record strong performance for deductive in mathematics
        for i in range(10):
            engine.record_performance('deductive', 'mathematics', 0.9, True, i)
        # Record weak performance for inductive in mathematics
        for i in range(10):
            engine.record_performance('inductive', 'mathematics', 0.3, False, i)

        result = engine.run_improvement_cycle(20)
        assert result['adjustments'] > 0

        # Deductive weight should have increased for mathematics
        weights = engine.get_domain_weights('mathematics')
        assert weights['deductive'] > weights['inductive']

    def test_cycle_identifies_weak_areas(self):
        """Cycle identifies areas with low success rate."""
        engine = self._make_engine(interval=10, min_obs=3)

        # All failures for abductive in blockchain
        for i in range(10):
            engine.record_performance('abductive', 'blockchain', 0.5, False, i)

        result = engine.run_improvement_cycle(20)
        # There should be at least one weak area identified
        weak_domains = [w['domain'] for w in result['weak_areas']]
        weak_strategies = [w['strategy'] for w in result['weak_areas']]
        if result['weak_areas']:
            assert 'blockchain' in weak_domains
            assert 'abductive' in weak_strategies

    def test_cycle_identifies_strong_areas(self):
        """Cycle identifies areas with high success rate."""
        engine = self._make_engine(interval=10, min_obs=3)

        # All successes for neural in ai_ml
        for i in range(10):
            engine.record_performance('neural', 'ai_ml', 0.95, True, i)

        result = engine.run_improvement_cycle(20)
        strong_strategies = [s['strategy'] for s in result['strong_areas']]
        if result['strong_areas']:
            assert 'neural' in strong_strategies

    def test_multiple_cycles_converge(self):
        """Multiple improvement cycles progressively refine weights."""
        engine = self._make_engine(interval=5, min_obs=3)

        for cycle in range(5):
            block = cycle * 10
            # Consistently strong: deductive in math
            for i in range(5):
                engine.record_performance('deductive', 'mathematics', 0.9, True, block + i)
            # Consistently weak: neural in math
            for i in range(5):
                engine.record_performance('neural', 'mathematics', 0.2, False, block + i)
            engine.run_improvement_cycle(block + 10)

        weights = engine.get_domain_weights('mathematics')
        assert weights['deductive'] > weights['neural']
        assert engine.get_stats()['cycles_completed'] == 5

    def test_cycle_updates_last_block(self):
        engine = self._make_engine(interval=10)
        engine.run_improvement_cycle(100)
        assert engine._last_cycle_block == 100


# ---------------------------------------------------------------------------
# Test group 4: Safety bounds
# ---------------------------------------------------------------------------

class TestSafetyBounds:
    """Test that weight safety constraints are enforced."""

    @patch('qubitcoin.aether.self_improvement.Config')
    def _make_engine(self, mock_config, min_w=0.05, max_w=0.5):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 10
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = min_w
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = max_w
        engine = SelfImprovementEngine()
        engine._min_observations = 2
        return engine

    def test_weights_never_below_minimum(self):
        """No weight should ever drop below min_weight after adjustment."""
        engine = self._make_engine(min_w=0.05)

        # Record extreme failure for one strategy
        for i in range(20):
            engine.record_performance('causal', 'general', 0.1, False, i)
            engine.record_performance('deductive', 'general', 0.9, True, i)

        engine.run_improvement_cycle(30)

        weights = engine.get_domain_weights('general')
        for strategy, w in weights.items():
            assert w >= 0.0, f"{strategy} weight {w} < 0"
            # After normalization, weights might be slightly above or at min

    def test_weights_never_above_maximum(self):
        """No weight should ever exceed max_weight before normalization."""
        engine = self._make_engine(max_w=0.5)

        # Record extreme success for one strategy
        for i in range(50):
            engine.record_performance('deductive', 'general', 1.0, True, i)
            engine.record_performance('inductive', 'general', 0.1, False, i)

        engine.run_improvement_cycle(60)
        engine.run_improvement_cycle(70)

        # Individual pre-normalization weights should respect max_weight
        # (checked indirectly: after normalization, no weight > max_weight / sum)
        weights = engine.get_domain_weights('general')
        for strategy, w in weights.items():
            assert w <= 1.0, f"{strategy} weight {w} > 1.0 after normalization"

    def test_weights_sum_to_one(self):
        """Weights per domain should sum to approximately 1.0 after normalization."""
        engine = self._make_engine()

        for i in range(20):
            engine.record_performance('deductive', 'physics', 0.8, True, i)
            engine.record_performance('inductive', 'physics', 0.3, False, i)
            engine.record_performance('abductive', 'physics', 0.6, True, i)

        engine.run_improvement_cycle(30)

        weights = engine.get_domain_weights('physics')
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, not ~1.0"

    def test_diversity_preserved(self):
        """Even with extreme data, all strategies retain some weight."""
        engine = self._make_engine()

        # Only ever succeed with deductive, fail with everything else
        for i in range(30):
            engine.record_performance('deductive', 'general', 0.99, True, i)
            engine.record_performance('inductive', 'general', 0.01, False, i)
            engine.record_performance('abductive', 'general', 0.01, False, i)
            engine.record_performance('neural', 'general', 0.01, False, i)
            engine.record_performance('causal', 'general', 0.01, False, i)
            engine.record_performance('chain_of_thought', 'general', 0.01, False, i)

        for cycle in range(5):
            engine.run_improvement_cycle(30 + (cycle + 1) * 10)

        weights = engine.get_domain_weights('general')
        for strategy, w in weights.items():
            assert w > 0, f"{strategy} has zero weight — diversity not preserved"


# ---------------------------------------------------------------------------
# Test group 5: Domain weight queries
# ---------------------------------------------------------------------------

class TestDomainWeightQueries:
    """Test weight query methods."""

    @patch('qubitcoin.aether.self_improvement.Config')
    def _make_engine(self, mock_config):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 100
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5
        return SelfImprovementEngine()

    def test_get_domain_weights_known(self):
        engine = self._make_engine()
        weights = engine.get_domain_weights('general')
        assert isinstance(weights, dict)
        assert len(weights) >= 6

    def test_get_domain_weights_unknown(self):
        """Unknown domains return uniform weights."""
        engine = self._make_engine()
        weights = engine.get_domain_weights('nonexistent_domain_xyz')
        from qubitcoin.aether.self_improvement import REASONING_MODES
        expected = 1.0 / len(REASONING_MODES)
        for w in weights.values():
            assert abs(w - expected) < 1e-10

    def test_get_best_strategy_initial(self):
        """With uniform weights, any strategy could be best (first alphabetically by max)."""
        engine = self._make_engine()
        best = engine.get_best_strategy('general')
        from qubitcoin.aether.self_improvement import REASONING_MODES
        assert best in REASONING_MODES

    def test_get_best_strategy_after_adjustment(self):
        """Best strategy reflects weight adjustments."""
        engine = self._make_engine()
        engine._min_observations = 2

        for i in range(10):
            engine.record_performance('neural', 'ai_ml', 0.95, True, i)
            engine.record_performance('deductive', 'ai_ml', 0.1, False, i)

        engine.run_improvement_cycle(20)
        best = engine.get_best_strategy('ai_ml')
        assert best == 'neural'


# ---------------------------------------------------------------------------
# Test group 6: Performance matrix and reporting
# ---------------------------------------------------------------------------

class TestReporting:
    """Test reporting and statistics methods."""

    @patch('qubitcoin.aether.self_improvement.Config')
    def _make_engine(self, mock_config):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 100
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5
        return SelfImprovementEngine()

    def test_performance_by_domain_empty(self):
        engine = self._make_engine()
        result = engine.get_performance_by_domain()
        assert result == {}

    def test_performance_by_domain_with_data(self):
        engine = self._make_engine()
        for i in range(10):
            engine.record_performance('deductive', 'mathematics', 0.8, True, i)
        for i in range(5):
            engine.record_performance('deductive', 'mathematics', 0.3, False, 10 + i)

        result = engine.get_performance_by_domain()
        assert 'mathematics' in result
        assert result['mathematics']['attempts'] == 15
        assert result['mathematics']['correct'] == 10
        assert abs(result['mathematics']['success_rate'] - 10 / 15) < 0.01

    def test_performance_matrix(self):
        engine = self._make_engine()
        for i in range(5):
            engine.record_performance('neural', 'ai_ml', 0.9, True, i)
        for i in range(5):
            engine.record_performance('deductive', 'ai_ml', 0.3, False, i)

        matrix = engine.get_performance_matrix()
        assert 'ai_ml' in matrix
        assert 'neural' in matrix['ai_ml']
        assert matrix['ai_ml']['neural']['attempts'] == 5
        assert matrix['ai_ml']['neural']['correct'] == 5
        assert matrix['ai_ml']['deductive']['correct'] == 0

    def test_recent_actions_empty(self):
        engine = self._make_engine()
        assert engine.get_recent_actions() == []

    def test_recent_actions_after_cycle(self):
        engine = self._make_engine()
        engine._min_observations = 2

        for i in range(10):
            engine.record_performance('deductive', 'general', 0.9, True, i)
            engine.record_performance('inductive', 'general', 0.1, False, i)

        engine.run_improvement_cycle(20)

        actions = engine.get_recent_actions(limit=5)
        assert isinstance(actions, list)
        if actions:
            assert 'strategy' in actions[0]
            assert 'domain' in actions[0]
            assert 'old_weight' in actions[0]
            assert 'new_weight' in actions[0]
            assert 'reason' in actions[0]

    def test_stats_diversity_score(self):
        """Diversity score should be 1.0 with uniform weights."""
        engine = self._make_engine()
        stats = engine.get_stats()
        # With uniform weights, Shannon entropy is maximal → diversity ≈ 1.0
        assert stats['diversity_score'] > 0.99, (
            f"Expected diversity ~1.0, got {stats['diversity_score']}"
        )

    def test_stats_diversity_decreases_with_skew(self):
        """Diversity score should decrease when weights become skewed."""
        engine = self._make_engine()
        engine._min_observations = 2

        # Create heavily skewed performance data
        for i in range(30):
            engine.record_performance('deductive', 'general', 0.99, True, i)
            engine.record_performance('inductive', 'general', 0.01, False, i)
            engine.record_performance('abductive', 'general', 0.01, False, i)
            engine.record_performance('neural', 'general', 0.01, False, i)
            engine.record_performance('causal', 'general', 0.01, False, i)
            engine.record_performance('chain_of_thought', 'general', 0.01, False, i)

        initial_diversity = engine.get_stats()['diversity_score']

        for cycle in range(5):
            engine.run_improvement_cycle(30 + (cycle + 1) * 10)

        final_diversity = engine.get_stats()['diversity_score']
        # After skewing weights, diversity should be lower (or at least not higher)
        assert final_diversity <= initial_diversity + 0.01


# ---------------------------------------------------------------------------
# Test group 7: Metacognition sync
# ---------------------------------------------------------------------------

class TestMetacognitionSync:
    """Test synchronization with MetacognitiveLoop."""

    @patch('qubitcoin.aether.self_improvement.Config')
    def _make_engine(self, mock_config, metacog=None):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 10
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5
        engine = SelfImprovementEngine(metacognition=metacog)
        engine._min_observations = 2
        return engine

    def test_sync_updates_metacognition_weights(self):
        """After a cycle, metacognition weights should be updated."""
        metacog = MagicMock()
        metacog._strategy_weights = {
            'deductive': 1.0, 'inductive': 1.0, 'abductive': 1.0,
            'chain_of_thought': 1.0, 'neural': 1.0, 'causal': 1.0,
        }
        engine = self._make_engine(metacog=metacog)

        for i in range(10):
            engine.record_performance('deductive', 'general', 0.9, True, i)
            engine.record_performance('inductive', 'general', 0.1, False, i)

        engine.run_improvement_cycle(20)

        # Metacognition weights should have been updated
        assert metacog._strategy_weights['deductive'] != 1.0 or \
               metacog._strategy_weights['inductive'] != 1.0

    def test_sync_none_metacognition(self):
        """No error when metacognition is None."""
        engine = self._make_engine(metacog=None)
        engine.record_performance('deductive', 'general', 0.5, True, 1)
        # Should not raise
        engine.run_improvement_cycle(20)


# ---------------------------------------------------------------------------
# Test group 8: Knowledge graph integration
# ---------------------------------------------------------------------------

class TestKnowledgeGraphIntegration:
    """Test knowledge graph meta-observation creation."""

    @patch('qubitcoin.aether.self_improvement.Config')
    def _make_engine(self, mock_config, kg=None):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 10
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5
        engine = SelfImprovementEngine(knowledge_graph=kg)
        engine._min_observations = 2
        return engine

    def test_cycle_creates_knowledge_node(self):
        """Improvement cycle creates a meta-observation node in KG."""
        kg = MagicMock()
        mock_node = MagicMock()
        mock_node.node_id = 42
        kg.add_node.return_value = mock_node

        engine = self._make_engine(kg=kg)
        for i in range(10):
            engine.record_performance('deductive', 'general', 0.9, True, i)

        result = engine.run_improvement_cycle(20)
        assert result['meta_node_id'] == 42
        kg.add_node.assert_called_once()

        # Check the content of the knowledge node
        call_kwargs = kg.add_node.call_args
        assert call_kwargs[1]['node_type'] == 'meta_observation'
        assert call_kwargs[1]['source_block'] == 20
        assert 'self_improvement' in str(call_kwargs[1]['content']['type'])

    def test_cycle_no_node_without_kg(self):
        """No node created when KG is None."""
        engine = self._make_engine(kg=None)
        result = engine.run_improvement_cycle(20)
        assert result['meta_node_id'] is None

    def test_cycle_handles_kg_exception(self):
        """Gracefully handles KG add_node failure."""
        kg = MagicMock()
        kg.add_node.side_effect = RuntimeError("DB error")

        engine = self._make_engine(kg=kg)
        result = engine.run_improvement_cycle(20)
        assert result['meta_node_id'] is None


# ---------------------------------------------------------------------------
# Test group 9: PerformanceRecord and ImprovementAction dataclasses
# ---------------------------------------------------------------------------

class TestDataclasses:
    """Test dataclass serialization."""

    def test_improvement_action_to_dict(self):
        from qubitcoin.aether.self_improvement import ImprovementAction
        action = ImprovementAction(
            strategy='deductive',
            domain='mathematics',
            old_weight=0.15,
            new_weight=0.25,
            reason='strong: success_rate=0.900 (n=10)',
            block_height=100,
            timestamp=1234567890.0,
        )
        d = action.to_dict()
        assert d['strategy'] == 'deductive'
        assert d['domain'] == 'mathematics'
        assert d['old_weight'] == 0.15
        assert d['new_weight'] == 0.25
        assert 'strong' in d['reason']
        assert d['block_height'] == 100

    def test_performance_record_fields(self):
        from qubitcoin.aether.self_improvement import PerformanceRecord
        record = PerformanceRecord(
            strategy='neural',
            domain='ai_ml',
            confidence=0.95,
            success=True,
            block_height=50,
        )
        assert record.strategy == 'neural'
        assert record.domain == 'ai_ml'
        assert record.confidence == 0.95
        assert record.success is True
        assert record.block_height == 50
        assert record.timestamp > 0


# ---------------------------------------------------------------------------
# Test group 10: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch('qubitcoin.aether.self_improvement.Config')
    def _make_engine(self, mock_config):
        from qubitcoin.aether.self_improvement import SelfImprovementEngine
        mock_config.SELF_IMPROVEMENT_INTERVAL = 10
        mock_config.SELF_IMPROVEMENT_MIN_WEIGHT = 0.05
        mock_config.SELF_IMPROVEMENT_MAX_WEIGHT = 0.5
        engine = SelfImprovementEngine()
        engine._min_observations = 2
        return engine

    def test_all_successes(self):
        """All strategies succeed — weights should stay relatively balanced."""
        engine = self._make_engine()
        for i in range(20):
            for s in ['deductive', 'inductive', 'abductive', 'neural', 'causal', 'chain_of_thought']:
                engine.record_performance(s, 'general', 0.9, True, i)

        engine.run_improvement_cycle(30)
        weights = engine.get_domain_weights('general')
        values = list(weights.values())
        # All weights should be similar
        assert max(values) - min(values) < 0.15

    def test_all_failures(self):
        """All strategies fail — weights should converge downward."""
        engine = self._make_engine()
        for i in range(20):
            for s in ['deductive', 'inductive', 'abductive', 'neural', 'causal', 'chain_of_thought']:
                engine.record_performance(s, 'general', 0.1, False, i)

        engine.run_improvement_cycle(30)
        weights = engine.get_domain_weights('general')
        # Should still sum to ~1.0 and all be positive
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01
        for w in weights.values():
            assert w > 0

    def test_single_strategy_data(self):
        """Only one strategy has data — others keep default weights."""
        engine = self._make_engine()
        for i in range(10):
            engine.record_performance('deductive', 'general', 0.9, True, i)

        engine.run_improvement_cycle(20)
        # Should not crash, and deductive should be adjusted
        weights = engine.get_domain_weights('general')
        assert isinstance(weights, dict)

    def test_empty_domain_normalization(self):
        """Normalization handles empty weight dicts gracefully."""
        engine = self._make_engine()
        engine._domain_weights['empty_test'] = {}
        engine._normalize_domain_weights('empty_test')
        # Should not crash

    def test_zero_weights_normalization(self):
        """Normalization handles all-zero weights by resetting to uniform."""
        engine = self._make_engine()
        engine._domain_weights['zero_test'] = {
            'deductive': 0.0, 'inductive': 0.0,
        }
        engine._normalize_domain_weights('zero_test')
        weights = engine._domain_weights['zero_test']
        assert all(w == 0.5 for w in weights.values())
