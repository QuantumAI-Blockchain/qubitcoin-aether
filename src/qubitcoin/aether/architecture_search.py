"""
Architecture Search — NAS-lite for AGI component auto-tuning.

Evaluates component performance, suggests modifications (prune, grow,
merge, split), and tracks which modifications helped vs hurt.

AGI Roadmap Item #61.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Modification:
    """A suggested architectural modification."""
    component: str
    action: str  # prune, grow, merge, split
    reason: str
    expected_improvement: float
    timestamp: float = 0.0
    applied: bool = False
    actual_improvement: Optional[float] = None


class ArchitectureSearch:
    """NAS-lite: evaluate and modify AGI subsystem architecture.

    Monitors component performance and suggests modifications:
    - Prune: remove underperforming components (accuracy < 0.3 for 1000+ blocks)
    - Grow: add capacity to overloaded components (utilization > 0.9)
    - Merge: combine similar components
    - Split: specialize over-generalized components
    """

    # Thresholds
    PRUNE_ACCURACY_THRESHOLD: float = 0.3
    PRUNE_MIN_BLOCKS: int = 1000
    GROW_UTILIZATION_THRESHOLD: float = 0.9
    MERGE_SIMILARITY_THRESHOLD: float = 0.85
    SPLIT_ERROR_VARIANCE_THRESHOLD: float = 0.5

    def __init__(self) -> None:
        self._component_history: Dict[str, List[dict]] = {}
        self._modifications: List[Modification] = []
        self._evaluations: int = 0
        self._suggestions: int = 0
        self._applied_count: int = 0
        self._helped_count: int = 0
        self._hurt_count: int = 0
        self._max_history_per_component: int = 500
        self._max_modifications: int = 200

    def evaluate_component(self, name: str, metrics: dict) -> float:
        """Evaluate a component's performance and record it.

        Args:
            name: Component name.
            metrics: Dict with keys like 'accuracy', 'utilization', 'latency',
                     'error_count', 'blocks_active'.

        Returns:
            Performance score in [0, 1].
        """
        self._evaluations += 1

        accuracy = metrics.get("accuracy", 0.5)
        utilization = metrics.get("utilization", 0.5)
        error_rate = metrics.get("error_count", 0) / max(metrics.get("blocks_active", 1), 1)
        latency = metrics.get("latency", 0.0)

        # Composite score
        score = (
            0.4 * accuracy
            + 0.2 * (1.0 - min(error_rate, 1.0))
            + 0.2 * min(utilization, 1.0)
            + 0.2 * max(1.0 - latency / 10.0, 0.0)
        )
        score = max(0.0, min(1.0, score))

        # Record history
        if name not in self._component_history:
            self._component_history[name] = []
        history = self._component_history[name]
        history.append({
            "score": score,
            "timestamp": time.time(),
            **metrics,
        })
        if len(history) > self._max_history_per_component:
            self._component_history[name] = history[-self._max_history_per_component:]

        return score

    def suggest_modification(self, components: Dict[str, dict]) -> List[Modification]:
        """Analyze all components and suggest modifications.

        Args:
            components: Dict mapping component name to its current metrics.

        Returns:
            List of suggested Modifications.
        """
        suggestions: List[Modification] = []

        for name, metrics in components.items():
            history = self._component_history.get(name, [])

            # Check for prune candidates
            if self._should_prune(name, metrics, history):
                suggestions.append(Modification(
                    component=name,
                    action="prune",
                    reason=f"Accuracy {metrics.get('accuracy', 0):.3f} < {self.PRUNE_ACCURACY_THRESHOLD} for {len(history)} blocks",
                    expected_improvement=0.1,
                    timestamp=time.time(),
                ))

            # Check for grow candidates
            if self._should_grow(name, metrics, history):
                suggestions.append(Modification(
                    component=name,
                    action="grow",
                    reason=f"Utilization {metrics.get('utilization', 0):.3f} > {self.GROW_UTILIZATION_THRESHOLD}",
                    expected_improvement=0.15,
                    timestamp=time.time(),
                ))

            # Check for split candidates
            if self._should_split(name, metrics, history):
                suggestions.append(Modification(
                    component=name,
                    action="split",
                    reason=f"High error variance suggests specialization needed",
                    expected_improvement=0.12,
                    timestamp=time.time(),
                ))

        # Check for merge candidates between pairs
        names = list(components.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if self._should_merge(names[i], names[j], components):
                    suggestions.append(Modification(
                        component=f"{names[i]}+{names[j]}",
                        action="merge",
                        reason=f"Components {names[i]} and {names[j]} have similar performance profiles",
                        expected_improvement=0.08,
                        timestamp=time.time(),
                    ))

        self._suggestions += len(suggestions)
        self._modifications.extend(suggestions)
        if len(self._modifications) > self._max_modifications:
            self._modifications = self._modifications[-self._max_modifications:]

        if suggestions:
            logger.debug(
                f"Architecture search suggested {len(suggestions)} modifications: "
                f"{[(s.component, s.action) for s in suggestions[:5]]}"
            )

        return suggestions

    def _should_prune(self, name: str, metrics: dict, history: List[dict]) -> bool:
        """Check if a component should be pruned."""
        if len(history) < self.PRUNE_MIN_BLOCKS:
            return False
        recent = history[-self.PRUNE_MIN_BLOCKS:]
        avg_accuracy = sum(h.get("accuracy", 0.5) for h in recent) / len(recent)
        return avg_accuracy < self.PRUNE_ACCURACY_THRESHOLD

    def _should_grow(self, name: str, metrics: dict, history: List[dict]) -> bool:
        """Check if a component needs more capacity."""
        utilization = metrics.get("utilization", 0.5)
        if utilization <= self.GROW_UTILIZATION_THRESHOLD:
            return False
        # Confirm sustained high utilization
        if len(history) >= 100:
            recent = history[-100:]
            avg_util = sum(h.get("utilization", 0.5) for h in recent) / len(recent)
            return avg_util > self.GROW_UTILIZATION_THRESHOLD
        return utilization > self.GROW_UTILIZATION_THRESHOLD

    def _should_split(self, name: str, metrics: dict, history: List[dict]) -> bool:
        """Check if a component should be specialized (split)."""
        if len(history) < 200:
            return False
        recent = history[-200:]
        scores = [h.get("score", 0.5) for h in recent]
        variance = sum((s - sum(scores) / len(scores)) ** 2 for s in scores) / len(scores)
        return variance > self.SPLIT_ERROR_VARIANCE_THRESHOLD

    def _should_merge(self, name_a: str, name_b: str,
                      components: Dict[str, dict]) -> bool:
        """Check if two components should be merged (very similar profiles)."""
        history_a = self._component_history.get(name_a, [])
        history_b = self._component_history.get(name_b, [])
        if len(history_a) < 50 or len(history_b) < 50:
            return False

        # Compare recent score distributions
        scores_a = [h.get("score", 0.5) for h in history_a[-50:]]
        scores_b = [h.get("score", 0.5) for h in history_b[-50:]]
        avg_a = sum(scores_a) / len(scores_a)
        avg_b = sum(scores_b) / len(scores_b)
        similarity = 1.0 - abs(avg_a - avg_b)
        return similarity > self.MERGE_SIMILARITY_THRESHOLD

    def record_modification_result(self, component: str, action: str,
                                   actual_improvement: float) -> None:
        """Record the outcome of an applied modification."""
        for mod in reversed(self._modifications):
            if mod.component == component and mod.action == action and not mod.applied:
                mod.applied = True
                mod.actual_improvement = actual_improvement
                self._applied_count += 1
                if actual_improvement > 0:
                    self._helped_count += 1
                else:
                    self._hurt_count += 1
                break

    def get_stats(self) -> dict:
        """Return architecture search statistics."""
        return {
            "evaluations": self._evaluations,
            "suggestions": self._suggestions,
            "applied": self._applied_count,
            "helped": self._helped_count,
            "hurt": self._hurt_count,
            "components_tracked": len(self._component_history),
            "pending_modifications": sum(
                1 for m in self._modifications if not m.applied
            ),
        }
