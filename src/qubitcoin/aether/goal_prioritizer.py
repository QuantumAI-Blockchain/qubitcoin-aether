"""
Goal Prioritizer — Multi-criteria utility-based goal ranking.

Maximizes expected utility across competing AGI goals using
impact, probability of success, cost, and urgency weighting.
Includes Pareto frontier detection for multi-objective decisions.

AGI Roadmap Item #57.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GoalScore:
    """Utility score breakdown for a goal."""
    goal: dict
    utility: float
    impact: float
    probability: float
    cost: float
    urgency: float
    is_pareto_optimal: bool = False


class GoalPrioritizer:
    """Prioritize AGI goals by expected utility with Pareto analysis."""

    def __init__(self, impact_weight: float = 1.0, prob_weight: float = 1.0,
                 cost_weight: float = 1.0, urgency_weight: float = 1.0) -> None:
        self._impact_weight: float = impact_weight
        self._prob_weight: float = prob_weight
        self._cost_weight: float = cost_weight
        self._urgency_weight: float = urgency_weight
        self._prioritizations: int = 0
        self._replans: int = 0
        self._history: List[dict] = []
        self._max_history: int = 1000

    def estimate_impact(self, goal: dict) -> float:
        """Estimate AGI score improvement from completing this goal.

        Uses goal metadata: 'domain_coverage', 'novelty', 'confidence_boost'.
        """
        coverage = goal.get("domain_coverage", 0.5)
        novelty = goal.get("novelty", 0.5)
        conf_boost = goal.get("confidence_boost", 0.1)
        # Impact is a weighted combination
        impact = 0.4 * coverage + 0.35 * novelty + 0.25 * min(conf_boost * 10, 1.0)
        return float(np.clip(impact, 0.0, 1.0))

    def estimate_cost(self, goal: dict) -> float:
        """Estimate computational cost of pursuing this goal.

        Uses goal metadata: 'compute_estimate', 'data_requirements', 'complexity'.
        """
        compute = goal.get("compute_estimate", 0.5)
        data_req = goal.get("data_requirements", 0.3)
        complexity = goal.get("complexity", 0.5)
        cost = 0.4 * compute + 0.3 * data_req + 0.3 * complexity
        return float(np.clip(cost, 0.01, 1.0))  # Min 0.01 to avoid division by zero

    def _compute_utility(self, goal: dict) -> GoalScore:
        """Compute expected utility for a single goal."""
        impact = self.estimate_impact(goal)
        probability = float(goal.get("probability_of_success", 0.5))
        cost = self.estimate_cost(goal)
        urgency = float(goal.get("urgency", 0.5))

        utility = (
            (impact ** self._impact_weight)
            * (probability ** self._prob_weight)
            * ((1.0 / cost) ** self._cost_weight)
            * (urgency ** self._urgency_weight)
        )

        return GoalScore(
            goal=goal,
            utility=float(utility),
            impact=impact,
            probability=probability,
            cost=cost,
            urgency=urgency,
        )

    def _detect_pareto_frontier(self, scores: List[GoalScore]) -> List[GoalScore]:
        """Mark goals on the Pareto frontier (non-dominated in impact vs cost)."""
        if not scores:
            return scores

        n = len(scores)
        # Objectives: maximize impact, minimize cost
        objectives = np.array([[s.impact, -s.cost] for s in scores])

        for i in range(n):
            dominated = False
            for j in range(n):
                if i == j:
                    continue
                # j dominates i if j is >= in all objectives and > in at least one
                if (objectives[j] >= objectives[i]).all() and (objectives[j] > objectives[i]).any():
                    dominated = True
                    break
            scores[i].is_pareto_optimal = not dominated

        return scores

    def prioritize(self, goals: List[dict]) -> List[Tuple[dict, float]]:
        """Sort goals by expected utility, highest first.

        Args:
            goals: List of goal dicts with metadata fields.

        Returns:
            List of (goal, utility) tuples sorted descending by utility.
        """
        if not goals:
            return []

        scores = [self._compute_utility(g) for g in goals]
        scores = self._detect_pareto_frontier(scores)
        scores.sort(key=lambda s: s.utility, reverse=True)

        self._prioritizations += 1
        if len(self._history) < self._max_history:
            self._history.append({
                "num_goals": len(goals),
                "top_utility": scores[0].utility if scores else 0.0,
                "pareto_count": sum(1 for s in scores if s.is_pareto_optimal),
            })

        logger.debug(
            f"Prioritized {len(goals)} goals, top utility={scores[0].utility:.4f}, "
            f"pareto_optimal={sum(1 for s in scores if s.is_pareto_optimal)}"
        )

        return [(s.goal, s.utility) for s in scores]

    def replan_on_failure(self, failed_goal: dict,
                          remaining_goals: List[dict]) -> List[Tuple[dict, float]]:
        """Re-prioritize remaining goals after a failure.

        Boosts goals similar to the failed one (they may address the same gap)
        and penalizes goals with similar cost profile.
        """
        self._replans += 1
        failed_domain = failed_goal.get("domain", "general")

        adjusted_goals = []
        for goal in remaining_goals:
            g = dict(goal)
            if g.get("domain") == failed_domain:
                # Boost urgency for same-domain goals
                g["urgency"] = min(g.get("urgency", 0.5) * 1.3, 1.0)
            # Penalize goals with high cost similar to the failed goal
            failed_cost = self.estimate_cost(failed_goal)
            goal_cost = self.estimate_cost(g)
            if abs(goal_cost - failed_cost) < 0.1:
                g["probability_of_success"] = g.get("probability_of_success", 0.5) * 0.8
            adjusted_goals.append(g)

        return self.prioritize(adjusted_goals)

    def get_stats(self) -> dict:
        """Return prioritizer statistics."""
        return {
            "prioritizations": self._prioritizations,
            "replans": self._replans,
            "history_size": len(self._history),
            "avg_top_utility": float(np.mean(
                [h["top_utility"] for h in self._history[-100:]]
            )) if self._history else 0.0,
            "avg_pareto_count": float(np.mean(
                [h["pareto_count"] for h in self._history[-100:]]
            )) if self._history else 0.0,
        }
