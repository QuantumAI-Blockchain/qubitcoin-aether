"""
Tests for Aether Tree core AI modules.

Covers: EmotionalState, CuriosityEngine, MetacognitiveLoop.
All tests run without a database or running node.
"""

import sys
import os
import time
from unittest.mock import MagicMock, patch

import pytest

# Ensure the source is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


# ── EmotionalState Tests ──────────────────────────────────────────────────


class TestEmotionalState:
    """Tests for emotional_state.py — cognitive emotion tracking."""

    def _make_emotional_state(self):
        """Create an EmotionalState with Rust backend disabled."""
        with patch('qubitcoin.aether.emotional_state._USE_RUST', False):
            from qubitcoin.aether.emotional_state import EmotionalState
            return EmotionalState()

    def test_initial_state_at_baseline(self):
        es = self._make_emotional_state()
        states = es.states
        assert len(states) == 7
        for emotion, value in states.items():
            assert abs(value - 0.3) < 1e-6, f"{emotion} should start at baseline 0.3"

    def test_initial_mood_is_valid(self):
        es = self._make_emotional_state()
        valid_moods = {
            "curious", "awestruck", "determined", "content",
            "excited", "contemplative", "engaged", "neutral",
        }
        assert es.mood in valid_moods

    def test_update_curiosity_from_prediction_errors(self):
        es = self._make_emotional_state()
        es.update({"prediction_errors": 20.0})
        states = es.states
        # curiosity should increase: EMA toward min(1.0, 20/20) = 1.0
        assert states["curiosity"] > 0.3

    def test_update_satisfaction_from_accuracy(self):
        es = self._make_emotional_state()
        es.update({"prediction_accuracy": 0.95, "debate_verdicts_recent": 10})
        states = es.states
        assert states["satisfaction"] > 0.3

    def test_update_frustration_from_contradictions(self):
        es = self._make_emotional_state()
        es.update({"unresolved_contradictions": 15})
        states = es.states
        assert states["frustration"] > 0.3

    def test_update_contemplation_sleep_phase(self):
        es = self._make_emotional_state()
        es.update({"pineal_phase": "sleep"})
        states = es.states
        # contemplation EMA toward 0.9
        assert states["contemplation"] > 0.3

    def test_emotions_clamped_0_to_1(self):
        es = self._make_emotional_state()
        # Feed extreme metrics
        for _ in range(50):
            es.update({
                "prediction_errors": 100,
                "novel_concepts_recent": 100,
                "unresolved_contradictions": 100,
                "prediction_accuracy": 1.0,
                "debate_verdicts_recent": 100,
                "cross_domain_edges_recent": 100,
                "gates_passed": 100,
                "user_interactions_recent": 100,
                "pineal_phase": "sleep",
            })
        for emotion, val in es.states.items():
            assert 0.0 <= val <= 1.0, f"{emotion}={val} out of range"

    def test_describe_feeling_returns_string(self):
        es = self._make_emotional_state()
        es.update({"prediction_errors": 15})
        desc = es.describe_feeling()
        assert isinstance(desc, str)
        assert len(desc) > 10

    def test_get_response_modifier_structure(self):
        es = self._make_emotional_state()
        modifier = es.get_response_modifier()
        assert "tone" in modifier
        assert "topics_of_interest" in modifier
        assert "emotional_color" in modifier

    def test_set_interest_domains(self):
        es = self._make_emotional_state()
        es.set_interest_domains(["quantum_physics", "cryptography"])
        modifier = es.get_response_modifier()
        assert "quantum_physics" in modifier["topics_of_interest"]

    def test_to_dict_structure(self):
        es = self._make_emotional_state()
        d = es.to_dict()
        assert "emotions" in d
        assert "mood" in d
        assert len(d["emotions"]) == 7

    def test_update_from_fep(self):
        es = self._make_emotional_state()
        es.update_from_fep({"curiosity": 0.9, "wonder": 0.8})
        states = es.states
        # Should have moved toward 0.9 from 0.3
        assert states["curiosity"] > 0.3
        assert states["wonder"] > 0.3


# ── CuriosityEngine Tests ────────────────────────────────────────────────


class TestCuriosityEngine:
    """Tests for curiosity_engine.py — intrinsic motivation."""

    def _make_curiosity_engine(self):
        """Create a CuriosityEngine with mocked KG and no Rust."""
        with patch('qubitcoin.aether.curiosity_engine._RUST_AVAILABLE', False):
            from qubitcoin.aether.curiosity_engine import CuriosityEngine
            mock_kg = MagicMock()
            mock_kg.nodes = {}
            return CuriosityEngine(knowledge_graph=mock_kg)

    def test_empty_curiosity_scores(self):
        ce = self._make_curiosity_engine()
        scores = ce.compute_curiosity_scores()
        assert scores == {}

    def test_record_prediction_outcome(self):
        ce = self._make_curiosity_engine()
        ce.record_prediction_outcome("physics", 0.8, 0.3, "energy_level")
        scores = ce.compute_curiosity_scores()
        assert "physics" in scores
        assert abs(scores["physics"] - 0.5) < 1e-6  # |0.8 - 0.3| = 0.5

    def test_multiple_predictions_averaged(self):
        ce = self._make_curiosity_engine()
        ce.record_prediction_outcome("math", 0.5, 0.5, "t1")  # error = 0
        ce.record_prediction_outcome("math", 0.8, 0.2, "t2")  # error = 0.6
        scores = ce.compute_curiosity_scores()
        assert abs(scores["math"] - 0.3) < 1e-6  # (0 + 0.6) / 2

    def test_rolling_window_bounded(self):
        ce = self._make_curiosity_engine()
        # Add 150 predictions (window is 100)
        for i in range(150):
            ce.record_prediction_outcome("test", float(i), 0.0, f"t{i}")
        assert len(ce.prediction_errors["test"]) == 100

    def test_suggest_exploration_goal_empty(self):
        ce = self._make_curiosity_engine()
        assert ce.suggest_exploration_goal() is None

    def test_suggest_exploration_goal_picks_highest(self):
        ce = self._make_curiosity_engine()
        ce.record_prediction_outcome("easy", 0.5, 0.49, "t1")   # error = 0.01
        ce.record_prediction_outcome("hard", 0.9, 0.1, "t2")    # error = 0.8
        goal = ce.suggest_exploration_goal()
        assert goal is not None
        assert goal["domain"] == "hard"
        assert goal["curiosity_score"] > 0.5

    def test_record_discovery(self):
        ce = self._make_curiosity_engine()
        ce.record_discovery("physics", "dark_matter", 1000)
        assert ce.discoveries_count == 1

    def test_multiple_discoveries(self):
        ce = self._make_curiosity_engine()
        ce.record_discovery("physics", "topic1", 100)
        ce.record_discovery("math", "topic2", 200)
        ce.record_discovery("physics", "topic3", 300)
        assert ce.discoveries_count == 3

    def test_curiosity_stats_structure(self):
        ce = self._make_curiosity_engine()
        ce.record_prediction_outcome("physics", 0.5, 0.3, "t1")
        ce.record_discovery("physics", "d1", 100)
        stats = ce.get_curiosity_stats()
        assert "curiosity_scores" in stats
        assert "top_interests" in stats
        assert "discoveries_count" in stats
        assert stats["discoveries_count"] == 1


# ── MetacognitiveLoop Tests ──────────────────────────────────────────────


class TestMetacognitiveLoop:
    """Tests for metacognition.py — reasoning about reasoning."""

    def _make_metacognition(self):
        """Create a MetacognitiveLoop with no KG and no Rust."""
        with patch('qubitcoin.aether.metacognition._RUST_AVAILABLE', False):
            from qubitcoin.aether.metacognition import MetacognitiveLoop
            return MetacognitiveLoop(knowledge_graph=None)

    def test_initial_state(self):
        mc = self._make_metacognition()
        assert mc._total_evaluations == 0
        assert mc._total_correct == 0
        assert len(mc._strategy_weights) == 6

    def test_evaluate_reasoning_increments_counters(self):
        mc = self._make_metacognition()
        mc.evaluate_reasoning("deductive", 0.8, True, "physics", 100)
        assert mc._total_evaluations == 1
        assert mc._total_correct == 1

    def test_evaluate_reasoning_incorrect(self):
        mc = self._make_metacognition()
        mc.evaluate_reasoning("inductive", 0.6, False, "math", 100)
        assert mc._total_evaluations == 1
        assert mc._total_correct == 0

    def test_strategy_stats_accumulated(self):
        mc = self._make_metacognition()
        mc.evaluate_reasoning("deductive", 0.9, True, "physics", 100)
        mc.evaluate_reasoning("deductive", 0.7, False, "physics", 101)
        mc.evaluate_reasoning("deductive", 0.8, True, "physics", 102)
        stats = mc._strategy_stats["deductive"]
        assert stats["attempts"] == 3
        assert stats["correct"] == 2

    def test_domain_stats_accumulated(self):
        mc = self._make_metacognition()
        mc.evaluate_reasoning("deductive", 0.8, True, "physics", 100)
        mc.evaluate_reasoning("inductive", 0.6, False, "physics", 101)
        mc.evaluate_reasoning("deductive", 0.9, True, "math", 102)
        assert mc._domain_stats["physics"]["attempts"] == 2
        assert mc._domain_stats["physics"]["correct"] == 1
        assert mc._domain_stats["math"]["attempts"] == 1

    def test_confidence_binning(self):
        mc = self._make_metacognition()
        mc.evaluate_reasoning("deductive", 0.85, True, "general", 100)
        # 0.85 -> bin_idx = min(9, int(0.85 * 10)) = 8
        assert 8 in mc._confidence_bins
        assert mc._confidence_bins[8]["count"] == 1
        assert mc._confidence_bins[8]["correct"] == 1

    def test_calibrate_confidence_no_data(self):
        mc = self._make_metacognition()
        # With < 30 evaluations, should return unchanged
        result = mc.calibrate_confidence(0.8)
        assert result == 0.8

    def test_calibrate_confidence_with_data(self):
        mc = self._make_metacognition()
        # Feed enough evaluations to enable temperature scaling
        for i in range(40):
            mc.evaluate_reasoning("deductive", 0.7, i % 2 == 0, "general", i)
        mc._update_temperature()
        calibrated = mc.calibrate_confidence(0.8)
        assert 0.0 < calibrated <= 1.0
        # Should be different from raw value since temperature != 1.0
        # (but we can't predict the exact value)
        assert isinstance(calibrated, float)

    def test_calibrate_confidence_zero_handled(self):
        mc = self._make_metacognition()
        mc._total_evaluations = 100
        assert mc.calibrate_confidence(0.0) == 0.01

    def test_get_recommended_strategy_default(self):
        mc = self._make_metacognition()
        strategy = mc.get_recommended_strategy()
        assert strategy in mc._strategy_weights

    def test_get_recommended_strategy_causal_bonus(self):
        mc = self._make_metacognition()
        # Causal questions should boost causal/abductive strategies
        strategy = mc.get_recommended_strategy(question_type="causal")
        assert strategy in mc._strategy_weights

    def test_adapt_strategy_weights_needs_data(self):
        mc = self._make_metacognition()
        # Without enough data, weights shouldn't change much
        original = dict(mc._strategy_weights)
        mc.adapt_strategy_weights()
        # With <10 attempts per strategy, weights are unchanged
        assert mc._strategy_weights == original

    def test_adapt_strategy_weights_with_data(self):
        mc = self._make_metacognition()
        # Feed enough data for deductive to have high accuracy
        for i in range(20):
            mc.evaluate_reasoning("deductive", 0.8, True, "general", i)
        # Feed data for inductive with low accuracy
        for i in range(20):
            mc.evaluate_reasoning("inductive", 0.5, False, "general", i + 20)

        mc.adapt_strategy_weights()
        # Deductive should be weighted higher than inductive
        assert mc._strategy_weights["deductive"] > mc._strategy_weights["inductive"]

    def test_overall_calibration_error_empty(self):
        mc = self._make_metacognition()
        ece = mc.get_overall_calibration_error()
        assert ece == 0.0

    def test_overall_calibration_error_computes(self):
        mc = self._make_metacognition()
        # Feed data: high confidence always correct
        for i in range(20):
            mc.evaluate_reasoning("deductive", 0.9, True, "general", i)
        # Feed data: low confidence always wrong
        for i in range(20):
            mc.evaluate_reasoning("deductive", 0.2, False, "general", i + 20)

        ece = mc.get_overall_calibration_error()
        assert isinstance(ece, float)
        assert 0.0 <= ece <= 1.0

    def test_confidence_calibration_structure(self):
        mc = self._make_metacognition()
        for i in range(10):
            mc.evaluate_reasoning("deductive", 0.5, i % 2 == 0, "general", i)
        cal = mc.get_confidence_calibration()
        assert isinstance(cal, dict)

    def test_evaluation_history_bounded(self):
        mc = self._make_metacognition()
        for i in range(600):
            mc.evaluate_reasoning("deductive", 0.5, True, "general", i)
        assert len(mc._evaluation_history) == 500  # max_history

    def test_calibration_trend(self):
        mc = self._make_metacognition()
        for i in range(100):
            mc.evaluate_reasoning("deductive", 0.5, i % 2 == 0, "general", i)
        trend = mc.get_calibration_trend(window=20)
        assert isinstance(trend, list)
        assert len(trend) > 0
        for val in trend:
            assert 0.0 <= val <= 1.0

    def test_get_stats_structure(self):
        mc = self._make_metacognition()
        mc.evaluate_reasoning("deductive", 0.8, True, "general", 100)
        stats = mc.get_stats()
        assert "total_evaluations" in stats
        assert "overall_accuracy" in stats
        assert "calibration_error" in stats
        assert "strategy_weights" in stats
        assert stats["total_evaluations"] == 1

    def test_export_metacognitive_state(self):
        mc = self._make_metacognition()
        for i in range(15):
            mc.evaluate_reasoning("deductive", 0.7, True, "physics", i)
        state = mc.export_metacognitive_state()
        assert "overall_accuracy" in state
        assert "calibration_temperature" in state
        assert "recommended_strategy" in state
        assert "strategy_weights" in state

    def test_process_block_adapts_at_interval(self):
        mc = self._make_metacognition()
        for i in range(15):
            mc.evaluate_reasoning("deductive", 0.8, True, "general", i)
        result = mc.process_block(50)
        assert result["weights_adapted"] is True

    def test_process_block_no_adapt_off_interval(self):
        mc = self._make_metacognition()
        result = mc.process_block(33)
        assert result["weights_adapted"] is False

    def test_create_meta_observation_needs_data(self):
        mc = self._make_metacognition()
        # No KG, so should return None
        result = mc.create_meta_observation(100)
        assert result is None
