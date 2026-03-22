"""
#90: Continual Learning with EWC (Elastic Weight Consolidation)

Prevents catastrophic forgetting by tracking Fisher information per
parameter and penalizing changes to important weights when learning
new tasks.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TaskSnapshot:
    """Snapshot of weights and Fisher information after learning a task."""
    task_id: str
    weights: np.ndarray
    fisher: np.ndarray
    performance: float
    timestamp: float = field(default_factory=time.time)


class ContinualLearning:
    """Elastic Weight Consolidation for continual learning.

    Tracks Fisher information to identify important parameters and
    applies importance-weighted regularization when learning new tasks.
    """

    def __init__(self, lambda_ewc: float = 1000.0, max_tasks: int = 50) -> None:
        self._lambda_ewc = lambda_ewc
        self._max_tasks = max_tasks
        # Accumulated Fisher and optimal weights per task
        self._task_snapshots: List[TaskSnapshot] = []
        # Current consolidated Fisher (sum of all tasks)
        self._consolidated_fisher: Optional[np.ndarray] = None
        self._consolidated_weights: Optional[np.ndarray] = None
        # Performance tracking per task
        self._task_performance: Dict[str, List[float]] = {}
        # Stats
        self._total_updates = 0
        self._total_fisher_computations = 0
        self._forgetting_events = 0

    # ------------------------------------------------------------------
    # Fisher information
    # ------------------------------------------------------------------

    def compute_fisher(
        self,
        model_weights: np.ndarray,
        data: List[np.ndarray],
        task_id: str = 'default',
    ) -> np.ndarray:
        """Compute empirical Fisher information matrix (diagonal approx).

        The Fisher measures how sensitive the loss is to each parameter.
        High Fisher = important parameter = should be preserved.

        Args:
            model_weights: Current model weights (1-D array).
            data: List of data samples (each a 1-D array).
            task_id: Identifier for the current task.

        Returns:
            Diagonal Fisher information (same shape as model_weights).
        """
        self._total_fisher_computations += 1
        n = len(model_weights)
        fisher = np.zeros(n, dtype=np.float64)

        if not data:
            return fisher

        for sample in data:
            # Approximate gradient: finite difference of squared-error proxy
            sample_flat = sample.flatten()[:n]
            if len(sample_flat) < n:
                sample_flat = np.pad(sample_flat, (0, n - len(sample_flat)))
            # Pseudo-gradient: difference between prediction and data
            prediction = model_weights * sample_flat
            error = prediction - sample_flat
            grad = 2 * error * sample_flat / len(data)
            fisher += grad ** 2

        fisher /= max(len(data), 1)

        # Store snapshot
        snapshot = TaskSnapshot(
            task_id=task_id,
            weights=model_weights.copy(),
            fisher=fisher.copy(),
            performance=1.0,
        )
        self._task_snapshots.append(snapshot)
        if len(self._task_snapshots) > self._max_tasks:
            self._task_snapshots = self._task_snapshots[-self._max_tasks:]

        # Update consolidated Fisher
        self._update_consolidated(model_weights, fisher)

        return fisher

    def _update_consolidated(
        self, weights: np.ndarray, fisher: np.ndarray
    ) -> None:
        """Update running sum of Fisher matrices."""
        if self._consolidated_fisher is None:
            self._consolidated_fisher = fisher.copy()
            self._consolidated_weights = weights.copy()
        else:
            n = min(len(self._consolidated_fisher), len(fisher))
            self._consolidated_fisher[:n] += fisher[:n]
            self._consolidated_weights = weights.copy()

    # ------------------------------------------------------------------
    # EWC loss and update
    # ------------------------------------------------------------------

    def ewc_loss(
        self,
        current_weights: np.ndarray,
        old_weights: Optional[np.ndarray] = None,
        fisher: Optional[np.ndarray] = None,
    ) -> float:
        """Compute EWC penalty: sum_i F_i * (theta_i - theta*_i)^2.

        Args:
            current_weights: Current parameter values.
            old_weights: Parameters from previous task (uses consolidated if None).
            fisher: Fisher information (uses consolidated if None).

        Returns:
            EWC penalty (scalar).
        """
        if old_weights is None:
            old_weights = self._consolidated_weights
        if fisher is None:
            fisher = self._consolidated_fisher
        if old_weights is None or fisher is None:
            return 0.0

        n = min(len(current_weights), len(old_weights), len(fisher))
        diff = current_weights[:n] - old_weights[:n]
        penalty = float(0.5 * self._lambda_ewc * np.sum(fisher[:n] * diff ** 2))
        return penalty

    def update_with_ewc(
        self,
        weights: np.ndarray,
        gradient: np.ndarray,
        lr: float = 0.01,
        lambda_ewc: Optional[float] = None,
    ) -> np.ndarray:
        """Apply gradient update with EWC regularization.

        new_weights = weights - lr * (gradient + lambda * F * (weights - old))

        Args:
            weights: Current model weights.
            gradient: Task-specific gradient.
            lr: Learning rate.
            lambda_ewc: Override for EWC strength.

        Returns:
            Updated weights.
        """
        self._total_updates += 1
        lam = lambda_ewc if lambda_ewc is not None else self._lambda_ewc

        ewc_grad = np.zeros_like(weights)
        if self._consolidated_fisher is not None and self._consolidated_weights is not None:
            n = min(len(weights), len(self._consolidated_fisher))
            diff = weights[:n] - self._consolidated_weights[:n]
            ewc_grad[:n] = lam * self._consolidated_fisher[:n] * diff

        total_grad = gradient + ewc_grad
        new_weights = weights - lr * total_grad
        return new_weights

    # ------------------------------------------------------------------
    # Performance tracking / forgetting detection
    # ------------------------------------------------------------------

    def record_task_performance(
        self, task_id: str, performance: float
    ) -> None:
        """Record current performance on a task (for forgetting detection)."""
        if task_id not in self._task_performance:
            self._task_performance[task_id] = []
        self._task_performance[task_id].append(performance)
        if len(self._task_performance[task_id]) > 200:
            self._task_performance[task_id] = self._task_performance[task_id][-200:]

        # Detect forgetting: significant drop from peak
        history = self._task_performance[task_id]
        if len(history) >= 3:
            peak = max(history[:-1])
            if performance < peak * 0.7:
                self._forgetting_events += 1
                logger.info(
                    f"Forgetting detected on task '{task_id}': "
                    f"peak={peak:.3f}, current={performance:.3f}"
                )

    def get_old_task_performance(self) -> Dict[str, float]:
        """Get latest performance on all known tasks."""
        result: Dict[str, float] = {}
        for task_id, history in self._task_performance.items():
            if history:
                result[task_id] = history[-1]
        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return continual learning statistics."""
        return {
            'total_updates': self._total_updates,
            'total_fisher_computations': self._total_fisher_computations,
            'task_snapshots': len(self._task_snapshots),
            'forgetting_events': self._forgetting_events,
            'lambda_ewc': self._lambda_ewc,
            'has_consolidated_fisher': self._consolidated_fisher is not None,
            'tasks_tracked': len(self._task_performance),
            'old_task_performance': self.get_old_task_performance(),
        }
