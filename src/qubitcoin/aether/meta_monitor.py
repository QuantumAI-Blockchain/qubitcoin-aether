"""
Metacognitive Monitor — Detect failing reasoning and switch strategies.

Monitors subsystem health, tracks per-strategy per-task performance,
and auto-switches strategies when the current one fails repeatedly.

AI Roadmap Item #65.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MonitorResult:
    """Result of monitoring a subsystem."""
    subsystem: str
    status: str  # healthy, degraded, failing
    recommendation: str
    confidence: float
    strategy_switch: Optional[str] = None


class MetaMonitor:
    """Monitor AI subsystems and auto-switch strategies on failure.

    Tracks performance per strategy per task type and switches
    to the next best strategy after consecutive failures.
    """

    # Strategy catalog
    STRATEGY_CATALOG: Dict[str, List[str]] = {
        "reasoning": ["deductive", "inductive", "abductive", "analogical"],
        "memory": ["recency", "relevance", "frequency"],
        "planning": ["mcts", "htn", "rl"],
    }

    # Failure threshold before switching
    FAILURE_THRESHOLD: int = 3
    # Performance window for evaluation
    EVAL_WINDOW: int = 50

    def __init__(self) -> None:
        # Current active strategy per task type
        self._active_strategies: Dict[str, str] = {}
        for task_type, strategies in self.STRATEGY_CATALOG.items():
            self._active_strategies[task_type] = strategies[0]

        # Performance tracking: {(task_type, strategy): [success_bool, ...]}
        self._performance: Dict[tuple, List[bool]] = {}
        self._max_performance_history: int = 500

        # Consecutive failure count per task type
        self._consecutive_failures: Dict[str, int] = {}

        # Strategy switch history
        self._switches: List[dict] = []
        self._max_switches: int = 200

        # Subsystem health tracking
        self._subsystem_metrics: Dict[str, List[dict]] = {}
        self._max_metrics_per_subsystem: int = 200

        # Stats
        self._monitor_calls: int = 0
        self._strategy_switches: int = 0
        self._auto_fallbacks: int = 0

    def monitor(self, subsystem: str, metrics: dict) -> MonitorResult:
        """Monitor a subsystem and return health assessment.

        Args:
            subsystem: Name of the subsystem.
            metrics: Dict with keys like 'accuracy', 'latency', 'error_count',
                     'utilization', 'blocks_active'.

        Returns:
            MonitorResult with status and recommendations.
        """
        self._monitor_calls += 1

        # Record metrics
        if subsystem not in self._subsystem_metrics:
            self._subsystem_metrics[subsystem] = []
        history = self._subsystem_metrics[subsystem]
        history.append({"timestamp": time.time(), **metrics})
        if len(history) > self._max_metrics_per_subsystem:
            self._subsystem_metrics[subsystem] = history[-self._max_metrics_per_subsystem:]

        # Assess health
        accuracy = metrics.get("accuracy", 0.5)
        error_count = metrics.get("error_count", 0)
        utilization = metrics.get("utilization", 0.5)

        # Determine status
        if accuracy < 0.2 or error_count > 50:
            status = "failing"
            confidence = 0.9
        elif accuracy < 0.4 or error_count > 20 or utilization > 0.95:
            status = "degraded"
            confidence = 0.7
        else:
            status = "healthy"
            confidence = 0.85

        # Generate recommendation
        recommendation = self._generate_recommendation(subsystem, status, metrics)

        # Check if a strategy switch is needed
        strategy_switch = None
        task_type = self._subsystem_to_task_type(subsystem)
        if task_type and status == "failing":
            new_strategy = self._auto_fallback(task_type)
            if new_strategy:
                strategy_switch = new_strategy

        return MonitorResult(
            subsystem=subsystem,
            status=status,
            recommendation=recommendation,
            confidence=confidence,
            strategy_switch=strategy_switch,
        )

    def record_strategy_outcome(self, task_type: str, strategy: str,
                                success: bool) -> None:
        """Record the outcome of using a strategy for a task type.

        Args:
            task_type: Category of the task.
            strategy: Strategy that was used.
            success: Whether the strategy succeeded.
        """
        key = (task_type, strategy)
        if key not in self._performance:
            self._performance[key] = []
        self._performance[key].append(success)
        if len(self._performance[key]) > self._max_performance_history:
            self._performance[key] = self._performance[key][-self._max_performance_history:]

        # Track consecutive failures
        if not success:
            self._consecutive_failures[task_type] = (
                self._consecutive_failures.get(task_type, 0) + 1
            )
        else:
            self._consecutive_failures[task_type] = 0

        # Auto-fallback if too many consecutive failures
        if self._consecutive_failures.get(task_type, 0) >= self.FAILURE_THRESHOLD:
            self._auto_fallback(task_type)

    def select_strategy(self, task_type: str,
                        history: Optional[List[dict]] = None) -> str:
        """Select the best strategy for a task type based on performance history.

        Args:
            task_type: Category of the task.
            history: Optional extra context.

        Returns:
            Name of the recommended strategy.
        """
        strategies = self.STRATEGY_CATALOG.get(task_type, [])
        if not strategies:
            return self._active_strategies.get(task_type, "default")

        best_strategy = strategies[0]
        best_score = -1.0

        for strategy in strategies:
            key = (task_type, strategy)
            outcomes = self._performance.get(key, [])
            if not outcomes:
                # Untried strategy gets a default score
                score = 0.5
            else:
                recent = outcomes[-self.EVAL_WINDOW:]
                score = sum(1 for s in recent if s) / len(recent)

            if score > best_score:
                best_score = score
                best_strategy = strategy

        return best_strategy

    def _auto_fallback(self, task_type: str) -> Optional[str]:
        """Switch to the next best strategy after repeated failures.

        Returns the new strategy name if switched, else None.
        """
        current = self._active_strategies.get(task_type, "")
        strategies = self.STRATEGY_CATALOG.get(task_type, [])
        if not strategies:
            return None

        # Find next best strategy (not the current one)
        best_strategy = None
        best_score = -1.0

        for strategy in strategies:
            if strategy == current:
                continue
            key = (task_type, strategy)
            outcomes = self._performance.get(key, [])
            if not outcomes:
                score = 0.5  # Untried gets benefit of doubt
            else:
                recent = outcomes[-self.EVAL_WINDOW:]
                score = sum(1 for s in recent if s) / len(recent)

            if score > best_score:
                best_score = score
                best_strategy = strategy

        if best_strategy and best_strategy != current:
            self._active_strategies[task_type] = best_strategy
            self._consecutive_failures[task_type] = 0
            self._strategy_switches += 1
            self._auto_fallbacks += 1

            switch_record = {
                "task_type": task_type,
                "from_strategy": current,
                "to_strategy": best_strategy,
                "reason": f"consecutive_failures >= {self.FAILURE_THRESHOLD}",
                "timestamp": time.time(),
            }
            self._switches.append(switch_record)
            if len(self._switches) > self._max_switches:
                self._switches = self._switches[-self._max_switches:]

            logger.info(
                f"Meta-monitor: switched {task_type} strategy "
                f"from '{current}' to '{best_strategy}' "
                f"(score={best_score:.3f})"
            )
            return best_strategy

        return None

    def _generate_recommendation(self, subsystem: str, status: str,
                                 metrics: dict) -> str:
        """Generate a human-readable recommendation."""
        if status == "healthy":
            return f"{subsystem} is performing well"
        elif status == "degraded":
            issues = []
            if metrics.get("accuracy", 1.0) < 0.4:
                issues.append("low accuracy")
            if metrics.get("error_count", 0) > 20:
                issues.append("high error count")
            if metrics.get("utilization", 0) > 0.95:
                issues.append("near capacity")
            return f"{subsystem} is degraded: {', '.join(issues) or 'multiple factors'}"
        else:
            return f"{subsystem} is failing — consider strategy switch or restart"

    def _subsystem_to_task_type(self, subsystem: str) -> Optional[str]:
        """Map a subsystem name to a task type category."""
        mapping = {
            "reasoning_engine": "reasoning",
            "neural_reasoner": "reasoning",
            "causal_engine": "reasoning",
            "memory_manager": "memory",
            "attention_memory": "memory",
            "hopfield_memory": "memory",
            "mcts_planner": "planning",
            "htn_planner": "planning",
            "rl_planner": "planning",
        }
        return mapping.get(subsystem)

    def get_active_strategies(self) -> Dict[str, str]:
        """Get currently active strategies per task type."""
        return dict(self._active_strategies)

    def get_stats(self) -> dict:
        """Return meta-monitor statistics."""
        strategy_scores: Dict[str, float] = {}
        for (task_type, strategy), outcomes in self._performance.items():
            if outcomes:
                recent = outcomes[-self.EVAL_WINDOW:]
                strategy_scores[f"{task_type}/{strategy}"] = (
                    sum(1 for s in recent if s) / len(recent)
                )

        return {
            "monitor_calls": self._monitor_calls,
            "strategy_switches": self._strategy_switches,
            "auto_fallbacks": self._auto_fallbacks,
            "active_strategies": dict(self._active_strategies),
            "subsystems_tracked": len(self._subsystem_metrics),
            "strategy_scores": strategy_scores,
            "consecutive_failures": dict(self._consecutive_failures),
        }
