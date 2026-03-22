"""
Active Learner — Select the most informative training examples.

Implements uncertainty sampling, margin sampling, entropy sampling,
and diversity sampling with combined strategies and meta-learning.

AGI Roadmap Item #60.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ActiveLearner:
    """Active learning for training data selection in Aether Tree."""

    def __init__(self, strategy: str = "combined", diversity_weight: float = 0.3) -> None:
        self._strategy: str = strategy
        self._diversity_weight: float = diversity_weight
        self._selections: int = 0
        self._total_samples_selected: int = 0
        # Meta-learning: track which strategies led to good outcomes
        self._strategy_outcomes: Dict[str, List[float]] = {
            "uncertainty": [],
            "margin": [],
            "entropy": [],
            "diversity": [],
            "combined": [],
        }
        self._max_outcomes: int = 500

    def select_samples(
        self,
        candidates: List[np.ndarray],
        model_confidence: List[float],
        n: int,
        strategy: Optional[str] = None,
    ) -> List[int]:
        """Select the n most informative samples.

        Args:
            candidates: List of feature vectors.
            model_confidence: Confidence for each candidate (0-1).
            n: Number of samples to select.
            strategy: Override default strategy.

        Returns:
            List of indices into candidates.
        """
        if not candidates or n <= 0:
            return []

        n = min(n, len(candidates))
        strat = strategy or self._strategy

        if strat == "uncertainty":
            indices = self._uncertainty_sampling(model_confidence, n)
        elif strat == "margin":
            indices = self._margin_sampling(model_confidence, n)
        elif strat == "entropy":
            indices = self._entropy_sampling(model_confidence, n)
        elif strat == "diversity":
            indices = self.diversity_sampling(candidates, n)
        elif strat == "combined":
            indices = self._combined_sampling(candidates, model_confidence, n)
        else:
            indices = self._uncertainty_sampling(model_confidence, n)

        self._selections += 1
        self._total_samples_selected += len(indices)
        return indices

    def _uncertainty_sampling(self, confidences: List[float], n: int) -> List[int]:
        """Select samples with lowest confidence (most uncertain)."""
        conf_arr = np.array(confidences, dtype=np.float64)
        # Lower confidence = more uncertain = more informative
        indices = np.argsort(conf_arr)[:n]
        return indices.tolist()

    def _margin_sampling(self, confidences: List[float], n: int) -> List[int]:
        """Select samples with smallest margin between confidence and 0.5.

        Samples closest to the decision boundary are most informative.
        """
        conf_arr = np.array(confidences, dtype=np.float64)
        margins = np.abs(conf_arr - 0.5)
        indices = np.argsort(margins)[:n]
        return indices.tolist()

    def _entropy_sampling(self, confidences: List[float], n: int) -> List[int]:
        """Select samples with highest entropy (most uncertain)."""
        conf_arr = np.clip(np.array(confidences, dtype=np.float64), 1e-10, 1 - 1e-10)
        # Binary entropy
        entropy = -(conf_arr * np.log2(conf_arr) + (1 - conf_arr) * np.log2(1 - conf_arr))
        indices = np.argsort(-entropy)[:n]  # Highest entropy first
        return indices.tolist()

    def diversity_sampling(self, candidates: List[np.ndarray], n: int) -> List[int]:
        """Select samples that maximize coverage of the feature space.

        Uses greedy farthest-first traversal.
        """
        if not candidates or n <= 0:
            return []

        n = min(n, len(candidates))
        data = np.array(candidates, dtype=np.float64)

        # Start with random seed
        selected = [np.random.randint(len(data))]

        for _ in range(n - 1):
            # Compute min distance from each candidate to selected set
            min_dists = np.full(len(data), np.inf)
            for idx in selected:
                dists = np.linalg.norm(data - data[idx], axis=1)
                min_dists = np.minimum(min_dists, dists)
            # Set already-selected to -inf
            for idx in selected:
                min_dists[idx] = -np.inf
            # Pick the farthest point
            next_idx = int(np.argmax(min_dists))
            selected.append(next_idx)

        return selected

    def _combined_sampling(
        self,
        candidates: List[np.ndarray],
        confidences: List[float],
        n: int,
    ) -> List[int]:
        """Combined uncertainty + diversity sampling.

        First select 2*n uncertain samples, then pick n diverse ones.
        """
        # Get uncertain candidates
        n_uncertain = min(n * 2, len(candidates))
        uncertain_indices = self._uncertainty_sampling(confidences, n_uncertain)

        if len(uncertain_indices) <= n:
            return uncertain_indices[:n]

        # From uncertain subset, select diverse
        subset = [candidates[i] for i in uncertain_indices]
        diverse_within = self.diversity_sampling(subset, n)
        return [uncertain_indices[i] for i in diverse_within]

    def record_outcome(self, strategy: str, improvement: float) -> None:
        """Record the outcome of a selection strategy for meta-learning.

        Args:
            strategy: Which strategy was used.
            improvement: How much the model improved after training on selected samples.
        """
        if strategy in self._strategy_outcomes:
            outcomes = self._strategy_outcomes[strategy]
            outcomes.append(improvement)
            if len(outcomes) > self._max_outcomes:
                self._strategy_outcomes[strategy] = outcomes[-self._max_outcomes:]

    def best_strategy(self) -> str:
        """Return the strategy with the best average outcome."""
        best_name = self._strategy
        best_avg = -np.inf
        for name, outcomes in self._strategy_outcomes.items():
            if outcomes:
                avg = float(np.mean(outcomes[-50:]))
                if avg > best_avg:
                    best_avg = avg
                    best_name = name
        return best_name

    def get_stats(self) -> dict:
        """Return active learner statistics."""
        strategy_avgs = {}
        for name, outcomes in self._strategy_outcomes.items():
            if outcomes:
                strategy_avgs[name] = float(np.mean(outcomes[-50:]))
        return {
            "selections": self._selections,
            "total_samples_selected": self._total_samples_selected,
            "current_strategy": self._strategy,
            "best_strategy": self.best_strategy(),
            "strategy_averages": strategy_avgs,
        }
