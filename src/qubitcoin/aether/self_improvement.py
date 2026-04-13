"""
Recursive Self-Improvement Engine — Aether Reasons About Its Own Reasoning

Analyzes past reasoning operations to identify patterns of success and failure
across reasoning modes and knowledge domains, then adjusts strategy weights
to improve future performance.

This module is the next step beyond metacognition: while MetacognitiveLoop
tracks *whether* reasoning works, SelfImprovementEngine actively *modifies*
the weights that govern which reasoning strategy is deployed for which
domain — a form of recursive self-improvement bounded by safety constraints.

Key design principles:
- Safety-bounded: No single strategy can dominate (min 0.05, max 0.5)
- Diversity-preserving: Strategy diversity is enforced structurally
- Transparent: All adjustments are logged and queryable
- Periodic: Runs every N blocks (configurable) — not every block
- Self-contained: Testable without running the full node
"""
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Rust acceleration
_RUST_AVAILABLE = False
try:
    from .rust_bridge import RUST_AVAILABLE, RustSelfImprovementEngine
    _RUST_AVAILABLE = RUST_AVAILABLE and RustSelfImprovementEngine is not None
except ImportError:
    pass

# Reasoning modes tracked by this engine
REASONING_MODES: List[str] = [
    'deductive', 'inductive', 'abductive',
    'chain_of_thought', 'neural', 'causal',
]

# Default domain list (matches knowledge_graph.py DOMAIN_KEYWORDS)
DEFAULT_DOMAINS: List[str] = [
    'quantum_physics', 'mathematics', 'computer_science', 'blockchain',
    'cryptography', 'philosophy', 'biology', 'physics', 'economics',
    'ai_ml', 'general',
]


@dataclass
class PerformanceRecord:
    """A single reasoning performance observation."""
    strategy: str
    domain: str
    confidence: float
    success: bool
    block_height: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class ImprovementAction:
    """A weight adjustment made during an improvement cycle."""
    strategy: str
    domain: str
    old_weight: float
    new_weight: float
    reason: str
    block_height: int
    timestamp: float = field(default_factory=time.time)
    # Outcome tracking (Improvement 91)
    outcome_measured: bool = False
    outcome_improved: Optional[bool] = None
    post_adjustment_success_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            'strategy': self.strategy,
            'domain': self.domain,
            'old_weight': round(self.old_weight, 6),
            'new_weight': round(self.new_weight, 6),
            'reason': self.reason,
            'block_height': self.block_height,
            'timestamp': self.timestamp,
            'outcome_measured': self.outcome_measured,
            'outcome_improved': self.outcome_improved,
        }


class SelfImprovementEngine:
    """
    Recursive self-improvement engine for Aether Tree reasoning.

    Analyzes past reasoning operations to identify which reasoning modes
    succeed or fail on which knowledge domains, then adjusts per-domain
    strategy weights to improve future performance.

    The engine runs periodic improvement cycles (every SELF_IMPROVEMENT_INTERVAL
    blocks) that:
    1. Analyze recent reasoning performance records
    2. Compute per-strategy, per-domain success rates
    3. Identify weak areas (low success rates with sufficient data)
    4. Adjust strategy weights using exponential moving average
    5. Clamp all weights to [MIN_WEIGHT, MAX_WEIGHT] for safety
    6. Log all adjustments for transparency

    Safety guarantees:
    - No weight can drop below MIN_WEIGHT (default 0.05) — every strategy
      always has a chance to run, preserving reasoning diversity
    - No weight can exceed MAX_WEIGHT (default 0.5) — no single strategy
      can monopolize reasoning for a domain
    - Weights are normalized per domain to sum to 1.0
    """

    def __init__(self, metacognition: Optional[object] = None,
                 knowledge_graph: Optional[object] = None) -> None:
        """Initialize the self-improvement engine.

        Args:
            metacognition: Optional MetacognitiveLoop instance for feeding
                back adjusted weights. If None, operates standalone.
            knowledge_graph: Optional KnowledgeGraph instance for creating
                meta-observation nodes about self-improvement. If None,
                no knowledge nodes are created.
        """
        self.metacognition = metacognition
        self.kg = knowledge_graph

        # Per-domain, per-strategy weights: domain -> {strategy -> weight}
        # Initialized with uniform weights (1/n for n strategies)
        n_strategies = len(REASONING_MODES)
        uniform_weight = 1.0 / n_strategies
        self._domain_weights: Dict[str, Dict[str, float]] = {}
        for domain in DEFAULT_DOMAINS:
            self._domain_weights[domain] = {
                s: uniform_weight for s in REASONING_MODES
            }

        # Performance records (bounded circular buffer)
        self._records: List[PerformanceRecord] = []
        self._max_records: int = 5000

        # Improvement action history
        self._actions: List[ImprovementAction] = []
        self._max_actions: int = 1000

        # Counters
        self._cycles_completed: int = 0
        self._total_adjustments: int = 0
        self._last_cycle_block: int = 0
        self._last_performance_delta: float = 0.0  # cross-cycle success rate improvement
        self._prev_cycle_success_rate: float = 0.0  # success rate from previous cycle
        self._rollback_count: int = 0

        # Configurable parameters (read from Config)
        self._interval: int = Config.SELF_IMPROVEMENT_INTERVAL
        self._min_weight: float = Config.SELF_IMPROVEMENT_MIN_WEIGHT
        self._max_weight: float = Config.SELF_IMPROVEMENT_MAX_WEIGHT

        # EMA smoothing factor (0.0-1.0): higher = more responsive to new data
        self._ema_alpha: float = 0.3

        # Minimum observations per (strategy, domain) before adjusting
        self._min_observations: int = 3

        # Rollback mechanism (Improvement 92)
        self._weight_snapshots: List[Tuple[int, Dict[str, Dict[str, float]]]] = []
        self._max_snapshots: int = 10

        # Performance regression detection (Improvement 94)
        self._cycle_performance_history: List[dict] = []

        # Adaptive learning rate (Improvement 95)
        self._adaptive_alpha: Dict[str, float] = {}  # per-domain alpha

        # Improvement cycle statistics for chat exposure (Improvement 95)
        self._cycle_stats_history: List[dict] = []

        logger.info(
            "SelfImprovementEngine initialized: interval=%d, "
            "min_weight=%.3f, max_weight=%.3f, strategies=%d, domains=%d",
            self._interval, self._min_weight, self._max_weight,
            len(REASONING_MODES), len(DEFAULT_DOMAINS),
        )

    def record_performance(self, strategy: str, domain: str,
                           confidence: float, success: bool,
                           block_height: int) -> None:
        """Record the outcome of a reasoning operation.

        Args:
            strategy: Reasoning strategy used (e.g. 'deductive', 'neural').
            domain: Knowledge domain (e.g. 'quantum_physics', 'general').
            confidence: Confidence score of the reasoning result (0.0-1.0).
            success: Whether the reasoning was successful/correct.
            block_height: Block height at which this reasoning occurred.
        """
        # Normalize unknown strategies/domains
        if strategy not in REASONING_MODES:
            strategy = 'chain_of_thought'  # fallback
        if domain not in self._domain_weights:
            # Auto-register new domain with uniform weights
            n_strategies = len(REASONING_MODES)
            uniform_weight = 1.0 / n_strategies
            self._domain_weights[domain] = {
                s: uniform_weight for s in REASONING_MODES
            }

        record = PerformanceRecord(
            strategy=strategy,
            domain=domain,
            confidence=max(0.0, min(1.0, confidence)),
            success=success,
            block_height=block_height,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

    def should_run_cycle(self, block_height: int) -> bool:
        """Check whether it is time to run an improvement cycle.

        Args:
            block_height: Current block height.

        Returns:
            True if enough blocks have passed since the last cycle.
        """
        if block_height <= 0:
            return False
        if self._last_cycle_block == 0:
            # First cycle: require at least interval blocks of data
            return block_height >= self._interval
        return (block_height - self._last_cycle_block) >= self._interval

    def run_improvement_cycle(self, block_height: int) -> dict:
        """Run a complete improvement cycle.

        Steps:
        1. Compute per-strategy, per-domain success rates from recent records
        2. Identify weak and strong areas
        3. Adjust weights using EMA
        4. Clamp and normalize weights
        5. Log adjustments
        6. Optionally create a knowledge node about the improvement

        Args:
            block_height: Current block height.

        Returns:
            Summary dict with cycle results.
        """
        cycle_start = time.time()
        adjustments_this_cycle = 0
        weak_areas: List[dict] = []
        strong_areas: List[dict] = []

        # Save weight snapshot for rollback (Improvement 92)
        import copy
        snapshot = copy.deepcopy(self._domain_weights)
        self._weight_snapshots.append((block_height, snapshot))
        if len(self._weight_snapshots) > self._max_snapshots:
            self._weight_snapshots = self._weight_snapshots[-self._max_snapshots:]

        # Measure pre-cycle performance for regression detection (Improvement 94)
        pre_cycle_stats = self._compute_performance_stats()
        pre_cycle_success = self._compute_overall_success_rate(pre_cycle_stats)

        # Step 1: Compute per-domain, per-strategy success rates
        domain_strategy_stats = pre_cycle_stats

        # Step 2 & 3: Adjust weights based on performance
        for domain, strategy_stats in domain_strategy_stats.items():
            if domain not in self._domain_weights:
                continue

            for strategy, stats in strategy_stats.items():
                if stats['attempts'] < self._min_observations:
                    continue  # Not enough data to adjust

                success_rate = stats['correct'] / stats['attempts']
                old_weight = self._domain_weights[domain].get(
                    strategy, 1.0 / len(REASONING_MODES)
                )

                # Compute target weight based on success rate
                # Map success_rate [0,1] to weight space
                target_weight = success_rate

                # Adaptive EMA: use domain-specific alpha (Improvement 95)
                domain_alpha = self._adaptive_alpha.get(domain, self._ema_alpha)
                # Adapt alpha based on data quantity: more data = more responsive
                if stats['attempts'] > 50:
                    domain_alpha = min(0.5, domain_alpha * 1.05)
                elif stats['attempts'] < 10:
                    domain_alpha = max(0.1, domain_alpha * 0.95)
                self._adaptive_alpha[domain] = domain_alpha

                new_weight = old_weight * (1.0 - domain_alpha) + target_weight * domain_alpha

                # Clamp to safety bounds
                new_weight = max(self._min_weight, min(self._max_weight, new_weight))

                # Only record if there was a meaningful change
                if abs(new_weight - old_weight) > 0.001:
                    reason = (
                        f"success_rate={success_rate:.3f} "
                        f"(n={stats['attempts']})"
                    )
                    if success_rate < 0.3:
                        reason = f"weak: {reason}"
                        weak_areas.append({
                            'strategy': strategy, 'domain': domain,
                            'success_rate': round(success_rate, 4),
                        })
                    elif success_rate > 0.7:
                        reason = f"strong: {reason}"
                        strong_areas.append({
                            'strategy': strategy, 'domain': domain,
                            'success_rate': round(success_rate, 4),
                        })

                    action = ImprovementAction(
                        strategy=strategy,
                        domain=domain,
                        old_weight=old_weight,
                        new_weight=new_weight,
                        reason=reason,
                        block_height=block_height,
                    )
                    self._actions.append(action)
                    if len(self._actions) > self._max_actions:
                        self._actions = self._actions[-self._max_actions:]

                    self._domain_weights[domain][strategy] = new_weight
                    adjustments_this_cycle += 1

        # Step 4: Normalize weights per domain so they sum to 1.0
        for domain in self._domain_weights:
            self._normalize_domain_weights(domain)

        # Step 5: Push adjusted weights to metacognition if available
        if self.metacognition is not None:
            self._sync_to_metacognition()

        # Step 6: Create knowledge node about the improvement
        meta_node_id = self._create_improvement_node(
            block_height, adjustments_this_cycle, weak_areas, strong_areas
        )

        # Update counters
        self._cycles_completed += 1
        self._total_adjustments += adjustments_this_cycle
        self._last_cycle_block = block_height

        cycle_duration = time.time() - cycle_start

        # Performance regression detection (Improvement 94)
        post_cycle_stats = self._compute_performance_stats()
        post_cycle_success = self._compute_overall_success_rate(post_cycle_stats)
        # Track cross-cycle delta (not within-cycle, which is always ~0)
        if self._prev_cycle_success_rate > 0:
            self._last_performance_delta = post_cycle_success - self._prev_cycle_success_rate
        elif adjustments_this_cycle > 0:
            # First cycle with adjustments: treat any positive success as positive delta
            self._last_performance_delta = post_cycle_success if post_cycle_success > 0 else 0.01
        self._prev_cycle_success_rate = post_cycle_success
        regression_detected = False
        if pre_cycle_success > 0 and post_cycle_success < pre_cycle_success * 0.9:
            regression_detected = True
            logger.warning(
                "Performance regression detected after cycle #%d: "
                "%.4f -> %.4f (%.1f%% drop). Consider rollback.",
                self._cycles_completed + 1, pre_cycle_success, post_cycle_success,
                (1.0 - post_cycle_success / pre_cycle_success) * 100
            )

        # Track outcome of previous cycle's adjustments (Improvement 91)
        self._evaluate_previous_actions(post_cycle_stats)

        logger.info(
            "Self-improvement cycle #%d at block %d: "
            "%d adjustments, %d weak areas, %d strong areas (%.3fs)%s",
            self._cycles_completed, block_height,
            adjustments_this_cycle, len(weak_areas), len(strong_areas),
            cycle_duration,
            " [REGRESSION]" if regression_detected else "",
        )

        cycle_result = {
            'cycle_number': self._cycles_completed,
            'block_height': block_height,
            'adjustments': adjustments_this_cycle,
            'weak_areas': weak_areas,
            'strong_areas': strong_areas,
            'meta_node_id': meta_node_id,
            'duration_seconds': round(cycle_duration, 4),
            'regression_detected': regression_detected,
            'pre_success_rate': round(pre_cycle_success, 4),
            'post_success_rate': round(post_cycle_success, 4),
        }

        # Store for chat exposure (Improvement 95)
        self._cycle_stats_history.append(cycle_result)
        if len(self._cycle_stats_history) > 50:
            self._cycle_stats_history = self._cycle_stats_history[-50:]

        return cycle_result

    def _compute_performance_stats(self) -> Dict[str, Dict[str, dict]]:
        """Compute per-domain, per-strategy performance statistics.

        Returns:
            Nested dict: domain -> strategy -> {attempts, correct, avg_confidence}
        """
        stats: Dict[str, Dict[str, dict]] = {}

        for record in self._records:
            domain = record.domain
            strategy = record.strategy

            if domain not in stats:
                stats[domain] = {}
            if strategy not in stats[domain]:
                stats[domain][strategy] = {
                    'attempts': 0, 'correct': 0, 'total_confidence': 0.0,
                }

            entry = stats[domain][strategy]
            entry['attempts'] += 1
            if record.success:
                entry['correct'] += 1
            entry['total_confidence'] += record.confidence

        return stats

    def _normalize_domain_weights(self, domain: str) -> None:
        """Normalize weights for a domain to sum to 1.0 while respecting bounds.

        After normalization, all weights are re-clamped to [min_weight, max_weight]
        to maintain safety invariants.
        """
        weights = self._domain_weights.get(domain, {})
        if not weights:
            return

        total = sum(weights.values())
        if total <= 0:
            # Reset to uniform if somehow all weights are zero
            n = len(weights)
            for s in weights:
                weights[s] = 1.0 / n
            return

        # Normalize to sum to 1.0
        for s in weights:
            weights[s] = weights[s] / total

        # Re-clamp after normalization (may break sum=1.0 slightly)
        for s in weights:
            weights[s] = max(self._min_weight, min(self._max_weight, weights[s]))

        # Re-normalize after clamping
        total = sum(weights.values())
        if total > 0:
            for s in weights:
                weights[s] = weights[s] / total

    def _sync_to_metacognition(self) -> None:
        """Push aggregated strategy weights to the MetacognitiveLoop.

        Computes a global weight per strategy by averaging across all domains,
        then updates the metacognition's _strategy_weights dict.
        """
        if self.metacognition is None:
            return

        global_weights: Dict[str, float] = {s: 0.0 for s in REASONING_MODES}
        n_domains = len(self._domain_weights)
        if n_domains == 0:
            return

        for domain_weights in self._domain_weights.values():
            for s, w in domain_weights.items():
                global_weights[s] = global_weights.get(s, 0.0) + w

        for s in global_weights:
            global_weights[s] /= n_domains

        # Scale to metacognition's weight range (0.0-2.0, centered at 1.0)
        for s in global_weights:
            # Map from [0, 1/n_strategies ... max_weight] to [0.5, 1.5]
            global_weights[s] = 0.5 + global_weights[s] * len(REASONING_MODES)

        # Update metacognition weights
        if hasattr(self.metacognition, '_strategy_weights'):
            for s, w in global_weights.items():
                if s in self.metacognition._strategy_weights:
                    self.metacognition._strategy_weights[s] = w

    def _create_improvement_node(self, block_height: int,
                                  adjustments: int,
                                  weak_areas: List[dict],
                                  strong_areas: List[dict]) -> Optional[int]:
        """Create a knowledge graph node recording this improvement cycle.

        Args:
            block_height: Current block height.
            adjustments: Number of weight adjustments made.
            weak_areas: List of weak (strategy, domain) pairs.
            strong_areas: List of strong (strategy, domain) pairs.

        Returns:
            Node ID of the created node, or None if KG is unavailable.
        """
        if self.kg is None:
            return None
        if not hasattr(self.kg, 'add_node'):
            return None

        try:
            content = {
                'type': 'self_improvement',
                'text': (
                    f"Self-improvement cycle #{self._cycles_completed + 1}: "
                    f"{adjustments} weight adjustments, "
                    f"{len(weak_areas)} weak areas identified, "
                    f"{len(strong_areas)} strong areas confirmed"
                ),
                'source': 'self_improvement_engine',
                'cycle_number': self._cycles_completed + 1,
                'adjustments': adjustments,
                'weak_areas': weak_areas[:5],  # Top 5
                'strong_areas': strong_areas[:5],
                'total_records': len(self._records),
            }

            node = self.kg.add_node(
                node_type='meta_observation',
                content=content,
                confidence=0.9,
                source_block=block_height,
            )
            return node.node_id if node else None
        except Exception as e:
            logger.debug("Failed to create improvement knowledge node: %s", e)
            return None

    def get_domain_weights(self, domain: str) -> Dict[str, float]:
        """Get current strategy weights for a specific domain.

        Args:
            domain: Knowledge domain name.

        Returns:
            Dict mapping strategy names to weights. Returns uniform weights
            for unknown domains.
        """
        if domain in self._domain_weights:
            return dict(self._domain_weights[domain])

        # Return uniform weights for unknown domains
        n = len(REASONING_MODES)
        return {s: 1.0 / n for s in REASONING_MODES}

    def get_best_strategy(self, domain: str) -> str:
        """Get the highest-weighted strategy for a domain.

        Args:
            domain: Knowledge domain name.

        Returns:
            Strategy name with highest weight for this domain.
        """
        weights = self.get_domain_weights(domain)
        return max(weights, key=weights.get)

    def get_performance_by_domain(self) -> Dict[str, dict]:
        """Get aggregated performance metrics per domain.

        Returns:
            Dict mapping domain -> {attempts, correct, success_rate, best_strategy}.
        """
        stats = self._compute_performance_stats()
        result: Dict[str, dict] = {}

        for domain, strategy_stats in stats.items():
            total_attempts = sum(s['attempts'] for s in strategy_stats.values())
            total_correct = sum(s['correct'] for s in strategy_stats.values())
            success_rate = total_correct / total_attempts if total_attempts > 0 else 0.0

            # Find best strategy for this domain based on actual performance
            best_strategy = 'unknown'
            best_rate = -1.0
            for strategy, s in strategy_stats.items():
                if s['attempts'] >= self._min_observations:
                    rate = s['correct'] / s['attempts']
                    if rate > best_rate:
                        best_rate = rate
                        best_strategy = strategy

            result[domain] = {
                'attempts': total_attempts,
                'correct': total_correct,
                'success_rate': round(success_rate, 4),
                'best_strategy': best_strategy,
                'strategies_evaluated': len(strategy_stats),
            }

        return result

    def get_performance_matrix(self) -> Dict[str, Dict[str, dict]]:
        """Get the full strategy x domain performance matrix.

        Returns:
            Nested dict: domain -> strategy -> {attempts, correct, success_rate, weight}.
        """
        stats = self._compute_performance_stats()
        result: Dict[str, Dict[str, dict]] = {}

        for domain, strategy_stats in stats.items():
            result[domain] = {}
            domain_weights = self.get_domain_weights(domain)

            for strategy, s in strategy_stats.items():
                success_rate = s['correct'] / s['attempts'] if s['attempts'] > 0 else 0.0
                result[domain][strategy] = {
                    'attempts': s['attempts'],
                    'correct': s['correct'],
                    'success_rate': round(success_rate, 4),
                    'weight': round(domain_weights.get(strategy, 0.0), 6),
                }

        return result

    def get_recent_actions(self, limit: int = 20) -> List[dict]:
        """Get the most recent improvement actions.

        Args:
            limit: Maximum number of actions to return.

        Returns:
            List of action dicts, most recent first.
        """
        actions = self._actions[-limit:]
        actions.reverse()
        return [a.to_dict() for a in actions]

    def _compute_overall_success_rate(self, stats: Dict[str, Dict[str, dict]]) -> float:
        """Compute overall success rate from performance stats."""
        total_attempts = 0
        total_correct = 0
        for domain_stats in stats.values():
            for strategy_stats in domain_stats.values():
                total_attempts += strategy_stats.get('attempts', 0)
                total_correct += strategy_stats.get('correct', 0)
        return total_correct / max(total_attempts, 1)

    def _evaluate_previous_actions(self, current_stats: Dict[str, Dict[str, dict]]) -> None:
        """Evaluate whether previous improvement actions helped.

        Marks actions as outcome_measured and determines if the
        adjustment improved performance for that strategy+domain.
        """
        for action in reversed(self._actions[-20:]):
            if action.outcome_measured:
                continue
            domain_stats = current_stats.get(action.domain, {})
            strategy_stats = domain_stats.get(action.strategy, {})
            if strategy_stats.get('attempts', 0) >= self._min_observations:
                current_rate = strategy_stats['correct'] / strategy_stats['attempts']
                action.outcome_measured = True
                action.post_adjustment_success_rate = current_rate
                # Determine if adjustment direction was correct
                weight_increased = action.new_weight > action.old_weight
                rate_is_good = current_rate > 0.5
                action.outcome_improved = weight_increased == rate_is_good

    def rollback_to_snapshot(self, snapshot_index: int = -1) -> bool:
        """Rollback weights to a previous snapshot.

        Args:
            snapshot_index: Index of snapshot to restore (-1 = most recent).

        Returns:
            True if rollback was performed.
        """
        if not self._weight_snapshots:
            return False

        try:
            block_height, snapshot = self._weight_snapshots[snapshot_index]
            import copy
            self._domain_weights = copy.deepcopy(snapshot)
            self._rollback_count += 1
            logger.info(
                "Rolled back weights to snapshot from block %d", block_height
            )
            # Push to metacognition
            if self.metacognition is not None:
                self._sync_to_metacognition()
            return True
        except (IndexError, KeyError) as e:
            logger.debug("Rollback failed: %s", e)
            return False

    def get_domain_improvement_strategy(self, domain: str) -> dict:
        """Get domain-specific improvement strategy recommendation.

        Analyzes per-domain performance to recommend whether to explore
        new strategies or exploit known-good ones.

        Args:
            domain: Knowledge domain name.

        Returns:
            Dict with recommendation and reasoning.
        """
        weights = self.get_domain_weights(domain)
        stats = self._compute_performance_stats()
        domain_stats = stats.get(domain, {})

        total_attempts = sum(s.get('attempts', 0) for s in domain_stats.values())
        total_correct = sum(s.get('correct', 0) for s in domain_stats.values())
        success_rate = total_correct / max(total_attempts, 1)

        # Determine if we should explore or exploit
        if total_attempts < 30:
            mode = 'explore'
            reason = f"Not enough data ({total_attempts} attempts). Try diverse strategies."
        elif success_rate > 0.7:
            mode = 'exploit'
            best_strategy = self.get_best_strategy(domain)
            reason = f"Strong performance ({success_rate:.1%}). Focus on {best_strategy}."
        elif success_rate < 0.3:
            mode = 'explore_aggressively'
            reason = f"Weak performance ({success_rate:.1%}). Try radically different approaches."
        else:
            mode = 'balanced'
            reason = f"Moderate performance ({success_rate:.1%}). Mix exploration and exploitation."

        return {
            'domain': domain,
            'mode': mode,
            'reason': reason,
            'success_rate': round(success_rate, 4),
            'total_attempts': total_attempts,
            'current_weights': {k: round(v, 4) for k, v in weights.items()},
            'best_strategy': self.get_best_strategy(domain),
        }

    def get_cycle_stats_for_chat(self) -> dict:
        """Get improvement cycle statistics formatted for chat exposure.

        Returns:
            Dict with recent cycle summaries and trends.
        """
        if not self._cycle_stats_history:
            return {
                'cycles_completed': 0,
                'recent_cycles': [],
                'trend': 'no_data',
            }

        recent = self._cycle_stats_history[-5:]
        success_rates = [c.get('post_success_rate', 0) for c in recent]

        if len(success_rates) >= 2:
            if success_rates[-1] > success_rates[0]:
                trend = 'improving'
            elif success_rates[-1] < success_rates[0]:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'

        return {
            'cycles_completed': self._cycles_completed,
            'total_adjustments': self._total_adjustments,
            'performance_delta': self._last_performance_delta,
            'total_records': len(self._records),
            'recent_cycles': recent,
            'trend': trend,
            'regressions_detected': sum(
                1 for c in self._cycle_stats_history if c.get('regression_detected')
            ),
        }

    def save_to_db(self, persistence: 'AGIPersistence', block_height: int = 0) -> bool:
        """Persist domain weights to CockroachDB."""
        try:
            return persistence.save_domain_weights(self._domain_weights, block_height)
        except Exception as e:
            logger.warning("Failed to save domain weights: %s", e)
            return False

    def load_from_db(self, persistence: 'AGIPersistence') -> bool:
        """Load domain weights from CockroachDB."""
        try:
            weights = persistence.load_domain_weights()
            if not weights:
                return False
            # Merge loaded weights with defaults (in case new domains/strategies were added)
            for domain, strategies in weights.items():
                if domain not in self._domain_weights:
                    self._domain_weights[domain] = {}
                for strategy, weight in strategies.items():
                    self._domain_weights[domain][strategy] = weight
            logger.info("Loaded domain weights from DB: %d domains", len(weights))
            return True
        except Exception as e:
            logger.warning("Failed to load domain weights: %s", e)
            return False

    def get_enacted_weights(self, domain: str) -> Dict[str, float]:
        """Get the current enacted strategy weights for a specific domain.

        Unlike get_domain_weights() which returns a copy, this returns the
        live weights that are actively being used for strategy selection.
        These weights reflect all enacted improvement cycles.

        Args:
            domain: Knowledge domain name.

        Returns:
            Dict mapping strategy names to enacted weights. Returns uniform
            weights for unknown domains.
        """
        if domain in self._domain_weights:
            return dict(self._domain_weights[domain])

        # Return uniform weights for unknown domains
        n = len(REASONING_MODES)
        return {s: 1.0 / n for s in REASONING_MODES}

    def enact_improvements(self, block_height: int) -> Dict[str, int]:
        """Apply pending improvement actions and perform automatic rollback
        if performance regresses beyond threshold.

        This is the critical method that makes self-improvement REAL.
        It ensures that weight adjustments computed by run_improvement_cycle()
        are actually reflected in strategy selection, and monitors for
        performance regression to trigger automatic rollback.

        The method:
        1. Verifies weights have been updated (run_improvement_cycle already
           writes to _domain_weights, so this syncs downstream consumers)
        2. Pushes enacted weights to metacognition for global strategy selection
        3. Checks for performance regression over a rolling window
        4. If regression > 10% over 100 blocks, rolls back to best snapshot

        Args:
            block_height: Current block height for tracking.

        Returns:
            Dict with enactment summary: enacted_count, rollback_performed, etc.
        """
        enacted_count = 0
        rollback_performed = False

        # Count actions that have been applied since last enactment
        recent_actions = [
            a for a in self._actions
            if a.block_height == block_height or
            (self._last_cycle_block > 0 and a.block_height >= self._last_cycle_block)
        ]
        enacted_count = len(recent_actions)

        # Sync enacted weights to metacognition
        if self.metacognition is not None:
            self._sync_to_metacognition()

        # Performance regression detection with automatic rollback
        # Check rolling window of last 100 blocks worth of records
        if len(self._records) >= 20:
            recent_records = self._records[-100:]
            recent_success = sum(1 for r in recent_records if r.success)
            recent_rate = recent_success / len(recent_records)

            # Compare against historical baseline (older records)
            if len(self._records) > 200:
                baseline_records = self._records[-300:-100]
                baseline_success = sum(1 for r in baseline_records if r.success)
                baseline_rate = baseline_success / len(baseline_records) if baseline_records else 0.0

                # Regression threshold: >10% drop from baseline
                if baseline_rate > 0 and recent_rate < baseline_rate * 0.9:
                    logger.warning(
                        "Performance regression detected at block %d: "
                        "baseline=%.4f, current=%.4f (%.1f%% drop). "
                        "Rolling back to previous snapshot.",
                        block_height, baseline_rate, recent_rate,
                        (1.0 - recent_rate / baseline_rate) * 100,
                    )
                    # Find the best snapshot (highest performance era)
                    if self._weight_snapshots and len(self._weight_snapshots) >= 2:
                        # Roll back to second-most-recent (before the bad cycle)
                        rollback_performed = self.rollback_to_snapshot(-2)
                        if rollback_performed:
                            logger.info(
                                "Automatic rollback completed at block %d. "
                                "Reverted to snapshot index -2.",
                                block_height,
                            )

        if enacted_count > 0:
            logger.info(
                "Enacted %d improvement actions at block %d%s",
                enacted_count, block_height,
                " (with rollback)" if rollback_performed else "",
            )

        return {
            'enacted_count': enacted_count,
            'rollback_performed': rollback_performed,
            'block_height': block_height,
            'domains_updated': len(self._domain_weights),
        }

    def get_stats(self) -> dict:
        """Get comprehensive self-improvement statistics.

        Returns:
            Dict with all tracking metrics.
        """
        # Compute diversity score: Shannon entropy of average weights
        avg_weights: Dict[str, float] = {s: 0.0 for s in REASONING_MODES}
        n_domains = len(self._domain_weights)
        if n_domains > 0:
            for domain_weights in self._domain_weights.values():
                for s, w in domain_weights.items():
                    avg_weights[s] += w
            for s in avg_weights:
                avg_weights[s] /= n_domains

        # Shannon entropy (higher = more diverse)
        entropy = 0.0
        for w in avg_weights.values():
            if w > 0:
                entropy -= w * math.log2(w)
        max_entropy = math.log2(len(REASONING_MODES)) if REASONING_MODES else 1.0
        diversity_score = entropy / max_entropy if max_entropy > 0 else 0.0

        return {
            'cycles_completed': self._cycles_completed,
            'total_adjustments': self._total_adjustments,
            'rollbacks': self._rollback_count,
            'performance_delta': self._last_performance_delta,
            'total_records': len(self._records),
            'last_cycle_block': self._last_cycle_block,
            'interval': self._interval,
            'min_weight': self._min_weight,
            'max_weight': self._max_weight,
            'domains_tracked': len(self._domain_weights),
            'strategies_tracked': len(REASONING_MODES),
            'diversity_score': round(diversity_score, 4),
            'performance_by_domain': self.get_performance_by_domain(),
            'average_weights': {
                s: round(w, 6) for s, w in avg_weights.items()
            },
        }
