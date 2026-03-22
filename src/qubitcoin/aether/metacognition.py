"""
Metacognitive Self-Evaluation Loop — Reasoning About Reasoning

Tracks the accuracy and effectiveness of all reasoning strategies,
evaluates which approaches produce the best results, and adjusts
the system's reasoning parameters accordingly.

Improvement #9: Without metacognition, the system has no way to know
whether its reasoning is actually working.  This module closes the
feedback loop — every prediction, deduction, and causal inference
is evaluated for accuracy, and the system adapts its strategy mix.
"""
import math
import time
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MetacognitiveLoop:
    """
    Self-evaluation system that monitors reasoning quality.

    Tracks:
    1. Reasoning strategy effectiveness (deductive vs inductive vs abductive)
    2. Prediction accuracy over time
    3. Neural reasoner vs rule-based accuracy comparison
    4. Per-domain reasoning success rates
    5. Overall cognitive health metrics

    Adjusts:
    - Strategy weights (which reasoning type to prefer)
    - Confidence calibration (are we over/under confident?)
    - Domain focus (which domains need more attention?)
    """

    def __init__(self, knowledge_graph=None) -> None:
        self.kg = knowledge_graph
        # Strategy effectiveness tracking
        self._strategy_stats: Dict[str, dict] = {}
        # Per-domain tracking
        self._domain_stats: Dict[str, dict] = {}
        # Confidence calibration
        self._confidence_bins: Dict[int, dict] = {}  # bin -> {count, correct}
        # Overall metrics
        self._total_evaluations: int = 0
        self._total_correct: int = 0
        self._evaluation_history: List[dict] = []
        self._max_history: int = 500
        # Adaptive temperature scaling for confidence calibration
        # T > 1 softens overconfident predictions, T < 1 sharpens underconfident
        # Updated via EMA from observed accuracy vs predicted confidence
        self._temperature: float = 1.0
        self._temperature_ema_alpha: float = 0.15  # EMA smoothing factor
        self._min_evals_for_temperature: int = 30  # Need this many before adapting T
        # Strategy weights (adapted over time)
        self._strategy_weights: Dict[str, float] = {
            'deductive': 1.0,
            'inductive': 1.0,
            'abductive': 1.0,
            'chain_of_thought': 1.0,
            'neural': 1.0,
            'causal': 1.0,
        }

    def evaluate_reasoning(self, strategy: str, confidence: float,
                           outcome_correct: bool, domain: str = 'general',
                           block_height: int = 0) -> dict:
        """
        Record the outcome of a reasoning operation.

        Args:
            strategy: Which reasoning strategy was used.
            confidence: The system's stated confidence in the result.
            outcome_correct: Whether the result turned out to be correct.
            domain: Knowledge domain of the reasoning.
            block_height: Current block height.

        Returns:
            Updated strategy stats.
        """
        self._total_evaluations += 1
        if outcome_correct:
            self._total_correct += 1

        # Store raw confidence in bins so calibration tracking is honest.
        # Temperature scaling is applied in calibrate_confidence() instead,
        # which is called BEFORE confidence is used for decisions.

        # Update strategy stats
        if strategy not in self._strategy_stats:
            self._strategy_stats[strategy] = {
                'attempts': 0, 'correct': 0,
                'total_confidence': 0.0, 'total_actual': 0.0,
            }
        stats = self._strategy_stats[strategy]
        stats['attempts'] += 1
        if outcome_correct:
            stats['correct'] += 1
        stats['total_confidence'] += confidence
        stats['total_actual'] += (1.0 if outcome_correct else 0.0)

        # Update domain stats
        if domain not in self._domain_stats:
            self._domain_stats[domain] = {'attempts': 0, 'correct': 0}
        self._domain_stats[domain]['attempts'] += 1
        if outcome_correct:
            self._domain_stats[domain]['correct'] += 1

        # Update confidence calibration bins (10 bins from 0.0-1.0)
        bin_idx = min(9, int(confidence * 10))
        if bin_idx not in self._confidence_bins:
            self._confidence_bins[bin_idx] = {'count': 0, 'correct': 0}
        self._confidence_bins[bin_idx]['count'] += 1
        if outcome_correct:
            self._confidence_bins[bin_idx]['correct'] += 1

        # Record in history
        entry = {
            'strategy': strategy,
            'confidence': round(confidence, 4),
            'correct': outcome_correct,
            'domain': domain,
            'block_height': block_height,
            'timestamp': time.time(),
        }
        self._evaluation_history.append(entry)
        if len(self._evaluation_history) > self._max_history:
            self._evaluation_history = self._evaluation_history[-self._max_history:]

        return self._strategy_stats[strategy]

    def _update_temperature(self) -> None:
        """Learn the optimal temperature from calibration bin data.

        Computes the ratio of mean actual accuracy to mean stated confidence
        across all populated bins. If the system is overconfident
        (stated > actual), T increases to soften predictions. If
        underconfident, T decreases to sharpen them.

        Updates via EMA so the temperature changes smoothly over time.
        """
        if self._total_evaluations < self._min_evals_for_temperature:
            return

        # Compute mean stated confidence and mean actual accuracy across bins
        sum_stated = 0.0
        sum_actual = 0.0
        total_count = 0

        for bin_idx in range(10):
            data = self._confidence_bins.get(bin_idx, {'count': 0, 'correct': 0})
            if data['count'] < 3:
                continue
            stated = (bin_idx + 0.5) / 10.0
            actual = data['correct'] / data['count']
            sum_stated += stated * data['count']
            sum_actual += actual * data['count']
            total_count += data['count']

        if total_count == 0 or sum_stated < 0.01:
            return

        mean_stated = sum_stated / total_count
        mean_actual = sum_actual / total_count

        # Target temperature from per-bin calibration error.
        # We use conf^T to calibrate, so T > 1 lowers confidence (for [0,1]).
        # Instead of solving T analytically, use a linear regression approach:
        # Overconfident (stated > actual) → T > 1; underconfident → T < 1.
        # Simple robust estimate: T = 1 + alpha * (mean_stated - mean_actual)
        # where alpha scales the correction proportionally.
        gap = mean_stated - mean_actual  # positive = overconfident
        # Scale factor: a gap of 0.2 should produce T ≈ 1.5
        t_target = 1.0 + gap * 2.5

        # Clamp to reasonable range
        t_target = max(0.5, min(3.0, t_target))

        # EMA update
        old_t = self._temperature
        self._temperature = (
            old_t * (1.0 - self._temperature_ema_alpha)
            + t_target * self._temperature_ema_alpha
        )

        logger.debug(
            "Temperature updated: %.3f -> %.3f (target=%.3f, "
            "mean_stated=%.3f, mean_actual=%.3f)",
            old_t, self._temperature, t_target, mean_stated, mean_actual,
        )

    def adapt_strategy_weights(self) -> Dict[str, float]:
        """
        Adjust strategy weights based on accumulated performance data.

        Strategies that are more accurate get higher weights.
        Uses exponential moving average with temporal weighting to avoid
        overreacting to noise while favoring recent evidence.

        Also updates the adaptive temperature for confidence calibration.
        """
        # Update temperature for confidence calibration
        self._update_temperature()

        # Compute temporally-weighted accuracy from recent history (Improvement: temporal weighting)
        recent_strategy_stats: Dict[str, Dict[str, float]] = {}
        now = time.time()
        decay_half_life = 3600.0  # 1 hour half-life for temporal weighting

        for entry in self._evaluation_history:
            strategy = entry['strategy']
            if strategy not in recent_strategy_stats:
                recent_strategy_stats[strategy] = {'weighted_correct': 0.0, 'weighted_total': 0.0}

            # Temporal weight: recent evaluations weighted more
            age = now - entry.get('timestamp', now)
            temporal_weight = 0.5 ** (age / decay_half_life)

            recent_strategy_stats[strategy]['weighted_total'] += temporal_weight
            if entry['correct']:
                recent_strategy_stats[strategy]['weighted_correct'] += temporal_weight

        for strategy, stats in self._strategy_stats.items():
            if stats['attempts'] < 10:
                continue  # Not enough data

            # Use temporally-weighted accuracy if available, otherwise raw
            recent = recent_strategy_stats.get(strategy)
            if recent and recent['weighted_total'] > 3.0:
                accuracy = recent['weighted_correct'] / recent['weighted_total']
            else:
                accuracy = stats['correct'] / stats['attempts']

            # EMA update: 70% old weight, 30% new evidence
            old_weight = self._strategy_weights.get(strategy, 1.0)
            new_evidence = accuracy * 2.0  # Scale: 0.0-2.0
            self._strategy_weights[strategy] = old_weight * 0.7 + new_evidence * 0.3

        return dict(self._strategy_weights)

    def get_recommended_strategy(self, domain: str = 'general',
                                   question_type: str = 'general') -> str:
        """
        Recommend the best reasoning strategy for a given domain and question type.

        Uses both global strategy weights and domain-specific performance
        history to recommend the most effective strategy.

        Args:
            domain: Knowledge domain (e.g., 'quantum_physics', 'blockchain').
            question_type: Type of question ('factual', 'causal', 'predictive', 'general').

        Returns:
            Strategy name with the highest combined weight.
        """
        if not self._strategy_weights:
            return 'deductive'

        # Question type heuristic bonus
        question_bonus: Dict[str, float] = {}
        if question_type == 'causal':
            question_bonus = {'causal': 0.15, 'abductive': 0.1, 'deductive': 0.05}
        elif question_type == 'predictive':
            question_bonus = {'inductive': 0.15, 'neural': 0.1, 'chain_of_thought': 0.05}
        elif question_type == 'factual':
            question_bonus = {'deductive': 0.15, 'chain_of_thought': 0.05}

        # Domain-specific performance bonus from history
        domain_bonus: Dict[str, float] = {}
        for entry in self._evaluation_history[-100:]:
            if entry['domain'] == domain and entry['correct']:
                s = entry['strategy']
                domain_bonus[s] = domain_bonus.get(s, 0) + 0.05

        # Hard vs easy distinction: if domain has high success rate, prefer fast strategies
        domain_data = self._domain_stats.get(domain, {'attempts': 0, 'correct': 0})
        if domain_data['attempts'] > 20:
            domain_accuracy = domain_data['correct'] / domain_data['attempts']
            if domain_accuracy > 0.8:
                # Easy domain: prefer fast deductive
                question_bonus['deductive'] = question_bonus.get('deductive', 0) + 0.1
            elif domain_accuracy < 0.4:
                # Hard domain: prefer exploratory strategies
                question_bonus['chain_of_thought'] = question_bonus.get('chain_of_thought', 0) + 0.1
                question_bonus['abductive'] = question_bonus.get('abductive', 0) + 0.1

        weighted = {
            s: w + domain_bonus.get(s, 0.0) + question_bonus.get(s, 0.0)
            for s, w in self._strategy_weights.items()
        }
        return max(weighted, key=weighted.get)

    def get_confidence_calibration(self) -> Dict[str, float]:
        """
        Compute confidence calibration — how well-calibrated are our
        confidence scores?

        Returns a dict mapping confidence bins to actual accuracy.
        A well-calibrated system has stated confidence ≈ actual accuracy.
        """
        calibration = {}
        for bin_idx in range(10):
            data = self._confidence_bins.get(bin_idx, {'count': 0, 'correct': 0})
            if data['count'] > 0:
                stated = (bin_idx + 0.5) / 10.0
                actual = data['correct'] / data['count']
                calibration[f"{bin_idx * 10}-{(bin_idx + 1) * 10}%"] = {
                    'stated_confidence': round(stated, 2),
                    'actual_accuracy': round(actual, 4),
                    'calibration_error': round(abs(stated - actual), 4),
                    'count': data['count'],
                }
        return calibration

    def calibrate_confidence(self, stated_confidence: float) -> float:
        """Apply temperature-scaled calibration to a stated confidence value.

        Uses an adaptive temperature parameter learned from the ratio of
        actual accuracy to predicted confidence across all bins.
        T > 1 softens overconfident predictions; T < 1 sharpens underconfident.

        The calibrated value is: conf^T, clamped to [0.01, 1.0].

        If insufficient calibration data exists (< _min_evals_for_temperature),
        returns the stated confidence unchanged.

        Args:
            stated_confidence: The raw confidence value (0.0-1.0)

        Returns:
            Calibrated confidence value (0.0-1.0)
        """
        if self._total_evaluations < self._min_evals_for_temperature:
            return stated_confidence

        # Apply temperature scaling: conf^T
        # For confidence in [0, 1], raising to power T > 1 lowers the value
        # (fixes overconfidence), while T < 1 raises it (fixes underconfidence).
        t = max(0.5, min(3.0, self._temperature))
        if stated_confidence <= 0.0:
            return 0.01
        calibrated = stated_confidence ** t
        return max(0.01, min(1.0, calibrated))

    def get_overall_calibration_error(self) -> float:
        """Compute Expected Calibration Error (ECE).

        Standard ECE: weighted average of |stated_confidence - actual_accuracy|
        across bins, weighted by bin sample count.

        The adaptive temperature in calibrate_confidence() reduces ECE by
        adjusting predictions before they are used. This method measures the
        *current* calibration quality honestly so the temperature can adapt.

        Bins with fewer than 3 samples are skipped to avoid noise.
        """
        total_samples = 0
        weighted_error = 0.0

        for bin_idx in range(10):
            data = self._confidence_bins.get(bin_idx, {'count': 0, 'correct': 0})
            if data['count'] < 3:
                continue

            stated = (bin_idx + 0.5) / 10.0
            actual = data['correct'] / data['count']
            # Standard ECE weighting: proportional to bin count
            weighted_error += data['count'] * abs(stated - actual)
            total_samples += data['count']

        if total_samples == 0:
            return 0.0
        return weighted_error / total_samples

    def create_meta_observation(self, block_height: int) -> Optional[int]:
        """
        Create a meta-observation node in the knowledge graph
        summarizing current cognitive health.

        This feeds back into the knowledge graph for recursive
        self-improvement.

        Returns:
            Node ID of the created meta-observation, or None.
        """
        if not self.kg or self._total_evaluations < 10:
            return None

        calibration_error = self.get_overall_calibration_error()
        overall_accuracy = (
            self._total_correct / self._total_evaluations
            if self._total_evaluations > 0 else 0.0
        )

        best_strategy = max(
            self._strategy_stats.items(),
            key=lambda x: x[1]['correct'] / max(1, x[1]['attempts']),
            default=('none', {'attempts': 0, 'correct': 0})
        )
        worst_strategy = min(
            self._strategy_stats.items(),
            key=lambda x: x[1]['correct'] / max(1, x[1]['attempts']),
            default=('none', {'attempts': 0, 'correct': 0})
        )

        content = {
            'type': 'meta_observation',
            'text': (f"Cognitive health: accuracy={overall_accuracy:.1%}, "
                     f"calibration_error={calibration_error:.3f}, "
                     f"best_strategy={best_strategy[0]}, "
                     f"worst_strategy={worst_strategy[0]}"),
            'source': 'self-reflection',
            'overall_accuracy': round(overall_accuracy, 4),
            'calibration_error': round(calibration_error, 4),
            'total_evaluations': self._total_evaluations,
            'best_strategy': best_strategy[0],
            'worst_strategy': worst_strategy[0],
            'strategy_weights': dict(self._strategy_weights),
        }

        node = self.kg.add_node(
            node_type='meta_observation',
            content=content,
            confidence=0.9,
            source_block=block_height,
        )

        if node:
            logger.info(
                f"Meta-observation at block {block_height}: "
                f"accuracy={overall_accuracy:.1%}, "
                f"ECE={calibration_error:.3f}"
            )
            return node.node_id
        return None

    def process_block(self, block_height: int) -> dict:
        """
        Per-block metacognitive processing.

        Every 100 blocks: adapt strategy weights.
        Every 500 blocks: create meta-observation node.
        """
        results = {
            'weights_adapted': False,
            'meta_node_created': False,
        }

        if block_height > 0 and block_height % 100 == 0:
            self.adapt_strategy_weights()
            results['weights_adapted'] = True

        if block_height > 0 and block_height % 500 == 0:
            node_id = self.create_meta_observation(block_height)
            results['meta_node_created'] = node_id is not None

        return results

    def get_calibration_trend(self, window: int = 50) -> List[float]:
        """Track calibration error over time to see if it is improving.

        Computes ECE for sliding windows of the evaluation history.

        Args:
            window: Size of each evaluation window.

        Returns:
            List of ECE values over time (oldest first).
        """
        if len(self._evaluation_history) < window:
            return [self.get_overall_calibration_error()]

        trend: List[float] = []
        for start in range(0, len(self._evaluation_history) - window + 1, window // 2):
            end = start + window
            window_entries = self._evaluation_history[start:end]

            # Compute ECE for this window
            bins: Dict[int, Dict[str, int]] = {}
            for entry in window_entries:
                bin_idx = min(9, int(entry['confidence'] * 10))
                if bin_idx not in bins:
                    bins[bin_idx] = {'count': 0, 'correct': 0}
                bins[bin_idx]['count'] += 1
                if entry['correct']:
                    bins[bin_idx]['correct'] += 1

            total_weight = 0.0
            weighted_error = 0.0
            for bin_idx, data in bins.items():
                if data['count'] == 0:
                    continue
                stated = (bin_idx + 0.5) / 10.0
                actual = data['correct'] / data['count']
                bin_weight = math.sqrt(data['count'])
                weighted_error += bin_weight * abs(stated - actual)
                total_weight += bin_weight

            ece = weighted_error / total_weight if total_weight > 0 else 0.0
            trend.append(round(ece, 4))

        return trend

    def export_metacognitive_state(self) -> dict:
        """Export the full metacognitive state for chat responses and monitoring.

        Returns a comprehensive snapshot of the system's self-knowledge
        about its own reasoning capabilities.

        Returns:
            Dict with all metacognitive state information.
        """
        calibration = self.get_confidence_calibration()
        trend = self.get_calibration_trend()

        # Determine if calibration is improving
        improving = False
        if len(trend) >= 2:
            recent = trend[-min(3, len(trend)):]
            older = trend[:min(3, len(trend))]
            improving = sum(recent) / len(recent) < sum(older) / len(older)

        # Identify strongest and weakest domains
        strongest_domain = ''
        weakest_domain = ''
        best_acc = -1.0
        worst_acc = 2.0
        for d, data in self._domain_stats.items():
            if data['attempts'] >= 5:
                acc = data['correct'] / data['attempts']
                if acc > best_acc:
                    best_acc = acc
                    strongest_domain = d
                if acc < worst_acc:
                    worst_acc = acc
                    weakest_domain = d

        return {
            'overall_accuracy': round(
                self._total_correct / max(1, self._total_evaluations), 4
            ),
            'total_evaluations': self._total_evaluations,
            'calibration_error': round(self.get_overall_calibration_error(), 4),
            'calibration_temperature': round(self._temperature, 4),
            'calibration_improving': improving,
            'calibration_trend': trend[-10:],  # Last 10 windows
            'recommended_strategy': self.get_recommended_strategy(),
            'strategy_weights': {
                k: round(v, 4) for k, v in self._strategy_weights.items()
            },
            'strongest_domain': strongest_domain,
            'weakest_domain': weakest_domain,
            'confidence_calibration': calibration,
        }

    def save_to_db(self, persistence: 'AGIPersistence', block_height: int = 0) -> bool:
        """Persist metacognition state to CockroachDB."""
        try:
            return persistence.save_metacognition(self, block_height)
        except Exception as e:
            logger.warning("Failed to save metacognition state: %s", e)
            return False

    def load_from_db(self, persistence: 'AGIPersistence') -> bool:
        """Load metacognition state from CockroachDB."""
        try:
            return persistence.load_metacognition(self)
        except Exception as e:
            logger.warning("Failed to load metacognition state: %s", e)
            return False

    def get_stats(self) -> dict:
        strategy_accuracies = {}
        for s, data in self._strategy_stats.items():
            if data['attempts'] > 0:
                strategy_accuracies[s] = round(
                    data['correct'] / data['attempts'], 4
                )

        domain_accuracies = {}
        for d, data in self._domain_stats.items():
            if data['attempts'] > 0:
                domain_accuracies[d] = round(
                    data['correct'] / data['attempts'], 4
                )

        return {
            'total_evaluations': self._total_evaluations,
            'total_correct': self._total_correct,
            'overall_accuracy': round(
                self._total_correct / max(1, self._total_evaluations), 4
            ),
            'calibration_error': round(self.get_overall_calibration_error(), 4),
            'calibration_temperature': round(self._temperature, 4),
            'calibration_improving': len(self.get_calibration_trend()) >= 2 and (
                self.get_calibration_trend()[-1] < self.get_calibration_trend()[0]
                if self.get_calibration_trend() else False
            ),
            'strategy_accuracies': strategy_accuracies,
            'strategy_weights': {
                k: round(v, 4) for k, v in self._strategy_weights.items()
            },
            'domain_accuracies': domain_accuracies,
        }
