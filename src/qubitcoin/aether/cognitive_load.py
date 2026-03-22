"""
#98: Cognitive Load Balancing

Dynamic compute allocation across AGI subsystems.  Distributes a
total budget of 1.0 proportionally to priority * demand, with
throttle/boost controls and automatic rebalancing.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895


class CognitiveLoadBalancer:
    """Dynamic compute allocation across AGI subsystems.

    Manages a total budget of 1.0, distributing resources proportionally
    to each subsystem's priority and current demand.
    """

    def __init__(self, total_budget: float = 1.0) -> None:
        self._total_budget = total_budget
        # Current allocations: subsystem -> fraction of budget
        self._allocations: Dict[str, float] = {}
        # Priorities: subsystem -> priority weight
        self._priorities: Dict[str, float] = {}
        # Demand history: subsystem -> recent demand values
        self._demand_history: Dict[str, List[float]] = {}
        self._max_history = 100
        # Utilization tracking
        self._utilization: Dict[str, List[float]] = {}
        # Manual overrides
        self._throttle_factors: Dict[str, float] = {}
        self._boost_factors: Dict[str, float] = {}
        # Stats
        self._total_balances = 0
        self._bottlenecks_detected = 0

    # ------------------------------------------------------------------
    # Main balancing
    # ------------------------------------------------------------------

    def balance(
        self,
        subsystem_loads: Dict[str, float],
        priorities: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Compute balanced allocation across subsystems.

        Args:
            subsystem_loads: Current demand per subsystem (0-1 scale).
            priorities: Priority weight per subsystem (higher = more important).

        Returns:
            Dict mapping subsystem to allocated fraction (sums to ~1.0).
        """
        self._total_balances += 1

        if priorities:
            self._priorities.update(priorities)

        if not subsystem_loads:
            return {}

        # Record demand history
        for sub, load in subsystem_loads.items():
            if sub not in self._demand_history:
                self._demand_history[sub] = []
            self._demand_history[sub].append(load)
            if len(self._demand_history[sub]) > self._max_history:
                self._demand_history[sub] = (
                    self._demand_history[sub][-self._max_history:]
                )

        # Compute effective demand = priority * load * factors
        effective: Dict[str, float] = {}
        for sub, load in subsystem_loads.items():
            pri = self._priorities.get(sub, 0.5)
            throttle = self._throttle_factors.get(sub, 1.0)
            boost = self._boost_factors.get(sub, 1.0)
            effective[sub] = max(load * pri * throttle * boost, 1e-6)

        # Normalize to total budget
        total = sum(effective.values())
        allocations: Dict[str, float] = {}
        for sub, eff in effective.items():
            allocations[sub] = (eff / total) * self._total_budget

        self._allocations = allocations

        # Detect bottlenecks (subsystem wants much more than allocated)
        for sub, load in subsystem_loads.items():
            alloc = allocations.get(sub, 0.0)
            if load > 0.8 and alloc < 0.2:
                self._bottlenecks_detected += 1
                logger.debug(
                    f"Bottleneck: {sub} demands {load:.2f} "
                    f"but allocated {alloc:.2f}"
                )

        return allocations

    # ------------------------------------------------------------------
    # Manual controls
    # ------------------------------------------------------------------

    def throttle(self, subsystem: str, factor: float) -> None:
        """Reduce a subsystem's allocation by multiplying by factor.

        Args:
            subsystem: Subsystem name.
            factor: Throttle factor (0-1, lower = more throttled).
        """
        self._throttle_factors[subsystem] = max(0.01, min(factor, 1.0))
        logger.debug(f"Throttled {subsystem} to factor={factor:.2f}")

    def boost(self, subsystem: str, factor: float) -> None:
        """Increase a subsystem's allocation by multiplying by factor.

        Args:
            subsystem: Subsystem name.
            factor: Boost factor (1-5, higher = more resources).
        """
        self._boost_factors[subsystem] = max(1.0, min(factor, 5.0))
        logger.debug(f"Boosted {subsystem} to factor={factor:.2f}")

    def reset_overrides(self, subsystem: Optional[str] = None) -> None:
        """Reset throttle/boost overrides.

        Args:
            subsystem: If given, reset only this subsystem. Otherwise reset all.
        """
        if subsystem:
            self._throttle_factors.pop(subsystem, None)
            self._boost_factors.pop(subsystem, None)
        else:
            self._throttle_factors.clear()
            self._boost_factors.clear()

    # ------------------------------------------------------------------
    # Auto-balance
    # ------------------------------------------------------------------

    def auto_balance(self) -> Dict[str, float]:
        """Automatically shift resources from idle to busy subsystems.

        Uses demand history to detect idle and overloaded subsystems.
        """
        if not self._demand_history:
            return self._allocations

        avg_demands: Dict[str, float] = {}
        for sub, history in self._demand_history.items():
            avg_demands[sub] = float(np.mean(history[-20:])) if history else 0.0

        # Find idle (avg < 0.1) and busy (avg > 0.7) subsystems
        idle = [s for s, d in avg_demands.items() if d < 0.1]
        busy = [s for s, d in avg_demands.items() if d > 0.7]

        # Shift from idle to busy
        for idle_sub in idle:
            self.throttle(idle_sub, 0.3)
        for busy_sub in busy:
            self.boost(busy_sub, 1.5)

        return self.balance(avg_demands)

    # ------------------------------------------------------------------
    # Utilization tracking
    # ------------------------------------------------------------------

    def record_utilization(
        self, subsystem: str, utilization: float
    ) -> None:
        """Record actual utilization for a subsystem.

        Args:
            subsystem: Subsystem name.
            utilization: Actual utilization (0-1).
        """
        if subsystem not in self._utilization:
            self._utilization[subsystem] = []
        self._utilization[subsystem].append(utilization)
        if len(self._utilization[subsystem]) > self._max_history:
            self._utilization[subsystem] = (
                self._utilization[subsystem][-self._max_history:]
            )

    def get_utilization_summary(self) -> Dict[str, float]:
        """Get average utilization per subsystem."""
        summary: Dict[str, float] = {}
        for sub, history in self._utilization.items():
            summary[sub] = float(np.mean(history)) if history else 0.0
        return summary

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return cognitive load balancer statistics."""
        return {
            'total_balances': self._total_balances,
            'bottlenecks_detected': self._bottlenecks_detected,
            'subsystems_tracked': len(self._demand_history),
            'current_allocations': dict(self._allocations),
            'active_throttles': len(self._throttle_factors),
            'active_boosts': len(self._boost_factors),
            'utilization': self.get_utilization_summary(),
        }
