"""
#71: Resource-Aware Planning

Considers compute cost in strategy selection.  Uses knapsack-style
optimization to maximize value within resource constraints and tracks
actual vs estimated costs for calibration.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceEstimate:
    """Estimated resource requirements for an action."""
    cpu_time_ms: float = 0.0
    memory_mb: float = 0.0
    io_ops: int = 0
    total_cost: float = 0.0

    def __post_init__(self) -> None:
        if self.total_cost == 0.0:
            self.total_cost = (
                self.cpu_time_ms * 0.001
                + self.memory_mb * 0.01
                + self.io_ops * 0.1
            )

    def exceeds(self, budget: 'ResourceEstimate') -> bool:
        return self.total_cost > budget.total_cost


# Default cost profiles for known action types
_DEFAULT_COSTS: Dict[str, ResourceEstimate] = {
    'explore': ResourceEstimate(cpu_time_ms=5.0, memory_mb=2.0, io_ops=1),
    'reason': ResourceEstimate(cpu_time_ms=20.0, memory_mb=5.0, io_ops=2),
    'consolidate': ResourceEstimate(cpu_time_ms=10.0, memory_mb=3.0, io_ops=3),
    'train': ResourceEstimate(cpu_time_ms=50.0, memory_mb=10.0, io_ops=1),
    'debate': ResourceEstimate(cpu_time_ms=30.0, memory_mb=5.0, io_ops=2),
    'causal_discovery': ResourceEstimate(cpu_time_ms=40.0, memory_mb=8.0, io_ops=3),
    'pattern_detect': ResourceEstimate(cpu_time_ms=15.0, memory_mb=4.0, io_ops=1),
    'self_test': ResourceEstimate(cpu_time_ms=25.0, memory_mb=5.0, io_ops=2),
    'cross_domain': ResourceEstimate(cpu_time_ms=35.0, memory_mb=6.0, io_ops=2),
    'anomaly_check': ResourceEstimate(cpu_time_ms=10.0, memory_mb=3.0, io_ops=1),
}

# Default value (benefit) per action type
_DEFAULT_VALUES: Dict[str, float] = {
    'explore': 0.6,
    'reason': 0.8,
    'consolidate': 0.5,
    'train': 0.7,
    'debate': 0.6,
    'causal_discovery': 0.7,
    'pattern_detect': 0.5,
    'self_test': 0.4,
    'cross_domain': 0.8,
    'anomaly_check': 0.6,
}


class ResourcePlanner:
    """Consider compute cost in strategy selection."""

    def __init__(
        self,
        load_threshold: float = 0.8,
        calibration_window: int = 200,
    ) -> None:
        self._load_threshold = load_threshold
        self._calibration_window = calibration_window

        # Calibration: actual vs estimated cost history
        self._actual_costs: Dict[str, List[float]] = {}
        self._estimated_costs: Dict[str, List[float]] = {}

        # Stats
        self._total_estimates: int = 0
        self._total_plans: int = 0
        self._total_skips: int = 0

        logger.info("ResourcePlanner initialized (load_threshold=%.2f)", load_threshold)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def estimate_cost(self, action: str, complexity: dict = None) -> ResourceEstimate:
        """Estimate resource cost of an action.

        Uses default profiles calibrated by historical actual costs.
        """
        self._total_estimates += 1
        complexity = complexity or {}

        base = _DEFAULT_COSTS.get(action, ResourceEstimate(cpu_time_ms=10.0, memory_mb=2.0, io_ops=1))

        # Scale by complexity factors
        scale = 1.0
        if 'nodes' in complexity:
            scale *= 1.0 + complexity['nodes'] / 10000.0
        if 'edges' in complexity:
            scale *= 1.0 + complexity['edges'] / 20000.0
        if 'depth' in complexity:
            scale *= 1.0 + complexity['depth'] * 0.1

        # Apply calibration correction
        correction = self._get_calibration_factor(action)

        return ResourceEstimate(
            cpu_time_ms=base.cpu_time_ms * scale * correction,
            memory_mb=base.memory_mb * scale * correction,
            io_ops=max(1, int(base.io_ops * scale)),
        )

    def plan_within_budget(
        self,
        actions: List[str],
        budget: ResourceEstimate,
        values: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """Select actions to maximize value within resource budget.

        Uses a greedy knapsack approach (value/cost ratio).
        """
        self._total_plans += 1
        values = values or _DEFAULT_VALUES

        # Build (action, cost, value) tuples
        items: List[Tuple[str, float, float]] = []
        for action in actions:
            est = self.estimate_cost(action)
            val = values.get(action, 0.5)
            items.append((action, est.total_cost, val))

        # Sort by value/cost ratio (descending)
        items.sort(key=lambda x: x[2] / max(x[1], 1e-9), reverse=True)

        selected: List[str] = []
        remaining_budget = budget.total_cost
        for action, cost, val in items:
            if cost <= remaining_budget:
                selected.append(action)
                remaining_budget -= cost

        return selected

    def record_actual_cost(self, action: str, actual_ms: float) -> None:
        """Record the actual cost of an action for calibration."""
        if action not in self._actual_costs:
            self._actual_costs[action] = []
            self._estimated_costs[action] = []

        self._actual_costs[action].append(actual_ms)
        est = _DEFAULT_COSTS.get(action, ResourceEstimate())
        self._estimated_costs[action].append(est.cpu_time_ms)

        # Trim to window
        if len(self._actual_costs[action]) > self._calibration_window:
            self._actual_costs[action] = self._actual_costs[action][-self._calibration_window:]
            self._estimated_costs[action] = self._estimated_costs[action][-self._calibration_window:]

    def should_skip(self, action: str, current_load: float) -> bool:
        """Decide whether to skip an expensive action under load.

        Args:
            action: The action to consider.
            current_load: Current system load [0, 1].

        Returns:
            True if the action should be skipped.
        """
        if current_load < self._load_threshold:
            return False

        # Skip expensive actions more aggressively under high load
        est = self.estimate_cost(action)
        cost_threshold = 20.0 * (1.0 - current_load)  # Lower threshold at higher load
        skip = est.cpu_time_ms > cost_threshold
        if skip:
            self._total_skips += 1
        return skip

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def _get_calibration_factor(self, action: str) -> float:
        """Return ratio of actual/estimated cost for calibration."""
        actuals = self._actual_costs.get(action, [])
        estimates = self._estimated_costs.get(action, [])
        if len(actuals) < 5:
            return 1.0
        mean_actual = float(np.mean(actuals[-50:]))
        mean_est = float(np.mean(estimates[-50:]))
        if mean_est < 1e-9:
            return 1.0
        return max(0.1, min(10.0, mean_actual / mean_est))

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        calibration_factors = {
            action: round(self._get_calibration_factor(action), 3)
            for action in self._actual_costs
        }
        return {
            'total_estimates': self._total_estimates,
            'total_plans': self._total_plans,
            'total_skips': self._total_skips,
            'calibrated_actions': len(self._actual_costs),
            'calibration_factors': calibration_factors,
        }
