"""
#75: Self-Repair Mechanisms

Detects degraded subsystems and auto-recovers by applying targeted
repair actions.  Monitors rolling averages of key metrics and triggers
repairs when thresholds are breached.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Diagnosis:
    """Diagnosis of a subsystem issue."""
    subsystem: str
    issue: str
    severity: str  # minor, major, critical
    suggested_fix: str
    metric_value: float = 0.0
    threshold: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class RepairResult:
    """Result of a repair action."""
    success: bool
    action_taken: str
    before_metric: float
    after_metric: float
    subsystem: str = ''
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Repair action registry
# ---------------------------------------------------------------------------
_REPAIR_ACTIONS = {
    'reset_weights': 'Re-initialize model weights to break out of degenerate state',
    'clear_cache': 'Clear internal caches to free memory and reset state',
    'restart_training': 'Reset training counters and learning rate',
    'reduce_capacity': 'Reduce buffer/history sizes to lower memory pressure',
    'increase_threshold': 'Raise minimum quality thresholds to reject noise',
}

# Threshold configurations per subsystem metric
_HEALTH_THRESHOLDS: Dict[str, Dict[str, float]] = {
    'accuracy': {'minor': 0.3, 'major': 0.15, 'critical': 0.05},
    'error_rate': {'minor': 0.3, 'major': 0.5, 'critical': 0.8},
    'memory_usage': {'minor': 0.7, 'major': 0.85, 'critical': 0.95},
    'output_rate': {'minor': 0.1, 'major': 0.02, 'critical': 0.0},
}


class SelfRepair:
    """Detect degraded subsystems and auto-recover."""

    def __init__(
        self,
        window_size: int = 10,
        max_history: int = 500,
    ) -> None:
        self._window_size = window_size
        self._max_history = max_history

        # Rolling metric history per subsystem
        self._metric_history: Dict[str, Dict[str, List[float]]] = {}

        # Diagnosis and repair history
        self._diagnoses: List[Diagnosis] = []
        self._repairs: List[RepairResult] = []

        # Stats
        self._total_diagnoses: int = 0
        self._total_repairs: int = 0
        self._successful_repairs: int = 0

        logger.info("SelfRepair initialized (window=%d)", window_size)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def diagnose(self, subsystem_stats: dict) -> List[Diagnosis]:
        """Diagnose issues across subsystems.

        Args:
            subsystem_stats: Dict mapping subsystem names to their metric dicts.
                Each metric dict should have keys like 'accuracy', 'error_count',
                'memory_usage', 'output_count', etc.
        """
        diagnoses: List[Diagnosis] = []

        for subsystem, metrics in subsystem_stats.items():
            if not isinstance(metrics, dict):
                continue

            # Update rolling history
            if subsystem not in self._metric_history:
                self._metric_history[subsystem] = {}

            for metric_name, value in metrics.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                if metric_name not in self._metric_history[subsystem]:
                    self._metric_history[subsystem][metric_name] = []
                history = self._metric_history[subsystem][metric_name]
                history.append(float(value))
                if len(history) > self._max_history:
                    self._metric_history[subsystem][metric_name] = history[-self._max_history:]

            # Check health conditions
            diag = self._check_accuracy(subsystem, metrics)
            if diag:
                diagnoses.append(diag)

            diag = self._check_error_rate(subsystem, metrics)
            if diag:
                diagnoses.append(diag)

            diag = self._check_memory(subsystem, metrics)
            if diag:
                diagnoses.append(diag)

            diag = self._check_zero_output(subsystem, metrics)
            if diag:
                diagnoses.append(diag)

            diag = self._check_training_divergence(subsystem, metrics)
            if diag:
                diagnoses.append(diag)

        self._total_diagnoses += len(diagnoses)
        self._diagnoses.extend(diagnoses)
        if len(self._diagnoses) > self._max_history:
            self._diagnoses = self._diagnoses[-self._max_history:]

        return diagnoses

    def repair(self, diagnosis: Diagnosis) -> RepairResult:
        """Execute a repair action based on the diagnosis."""
        self._total_repairs += 1
        action = diagnosis.suggested_fix
        before = diagnosis.metric_value

        # Simulate repair outcome (actual repair would modify the subsystem)
        # The caller is expected to apply the suggested fix to the actual subsystem
        success = True
        after = before

        if action == 'reset_weights':
            after = 0.5  # Reset to neutral
        elif action == 'clear_cache':
            after = max(0.0, before * 0.5)
        elif action == 'restart_training':
            after = 0.3  # Restart from modest baseline
        elif action == 'reduce_capacity':
            after = max(0.0, before * 0.7)
        elif action == 'increase_threshold':
            after = min(1.0, before + 0.1)
        else:
            success = False

        if success:
            self._successful_repairs += 1

        result = RepairResult(
            success=success,
            action_taken=action,
            before_metric=before,
            after_metric=after,
            subsystem=diagnosis.subsystem,
        )

        self._repairs.append(result)
        if len(self._repairs) > self._max_history:
            self._repairs = self._repairs[-self._max_history:]

        return result

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def _check_accuracy(self, subsystem: str, metrics: dict) -> Optional[Diagnosis]:
        accuracy = metrics.get('accuracy', None)
        if accuracy is None:
            return None
        thresholds = _HEALTH_THRESHOLDS['accuracy']
        if accuracy < thresholds['critical']:
            return Diagnosis(
                subsystem=subsystem,
                issue=f"Accuracy critically low: {accuracy:.4f}",
                severity='critical',
                suggested_fix='reset_weights',
                metric_value=accuracy,
                threshold=thresholds['critical'],
            )
        elif accuracy < thresholds['major']:
            return Diagnosis(
                subsystem=subsystem,
                issue=f"Accuracy degraded: {accuracy:.4f}",
                severity='major',
                suggested_fix='restart_training',
                metric_value=accuracy,
                threshold=thresholds['major'],
            )
        elif accuracy < thresholds['minor']:
            return Diagnosis(
                subsystem=subsystem,
                issue=f"Accuracy below target: {accuracy:.4f}",
                severity='minor',
                suggested_fix='increase_threshold',
                metric_value=accuracy,
                threshold=thresholds['minor'],
            )
        return None

    def _check_error_rate(self, subsystem: str, metrics: dict) -> Optional[Diagnosis]:
        error_count = metrics.get('error_count', 0)
        total = metrics.get('total_operations', metrics.get('blocks_active', 1))
        if total <= 0:
            return None
        error_rate = error_count / max(total, 1)

        thresholds = _HEALTH_THRESHOLDS['error_rate']
        if error_rate > thresholds['critical']:
            return Diagnosis(
                subsystem=subsystem,
                issue=f"Error rate critical: {error_rate:.2%}",
                severity='critical',
                suggested_fix='reset_weights',
                metric_value=error_rate,
                threshold=thresholds['critical'],
            )
        elif error_rate > thresholds['major']:
            return Diagnosis(
                subsystem=subsystem,
                issue=f"Error rate high: {error_rate:.2%}",
                severity='major',
                suggested_fix='clear_cache',
                metric_value=error_rate,
                threshold=thresholds['major'],
            )
        return None

    def _check_memory(self, subsystem: str, metrics: dict) -> Optional[Diagnosis]:
        mem = metrics.get('memory_usage', None)
        if mem is None:
            return None
        thresholds = _HEALTH_THRESHOLDS['memory_usage']
        if mem > thresholds['critical']:
            return Diagnosis(
                subsystem=subsystem,
                issue=f"Memory usage critical: {mem:.2%}",
                severity='critical',
                suggested_fix='reduce_capacity',
                metric_value=mem,
                threshold=thresholds['critical'],
            )
        elif mem > thresholds['major']:
            return Diagnosis(
                subsystem=subsystem,
                issue=f"Memory usage high: {mem:.2%}",
                severity='major',
                suggested_fix='clear_cache',
                metric_value=mem,
                threshold=thresholds['major'],
            )
        return None

    def _check_zero_output(self, subsystem: str, metrics: dict) -> Optional[Diagnosis]:
        """Detect if subsystem has stopped producing output."""
        history = self._metric_history.get(subsystem, {})
        output_history = history.get('output_count', history.get('total_operations', []))
        if len(output_history) < self._window_size:
            return None

        recent = output_history[-self._window_size:]
        if all(v == recent[0] for v in recent):
            # No change in output count over the window — possibly stuck
            return Diagnosis(
                subsystem=subsystem,
                issue="Zero output detected (subsystem may be stuck)",
                severity='major',
                suggested_fix='restart_training',
                metric_value=0.0,
                threshold=0.0,
            )
        return None

    def _check_training_divergence(self, subsystem: str, metrics: dict) -> Optional[Diagnosis]:
        """Detect if training loss is diverging."""
        history = self._metric_history.get(subsystem, {})
        loss_history = history.get('loss', history.get('training_loss', []))
        if len(loss_history) < self._window_size:
            return None

        recent = np.array(loss_history[-self._window_size:], dtype=np.float64)
        # Check for monotonically increasing loss
        diffs = np.diff(recent)
        if np.all(diffs > 0) and recent[-1] > recent[0] * 2:
            return Diagnosis(
                subsystem=subsystem,
                issue=f"Training divergence: loss {recent[0]:.4f} -> {recent[-1]:.4f}",
                severity='critical',
                suggested_fix='reset_weights',
                metric_value=float(recent[-1]),
                threshold=float(recent[0]),
            )
        return None

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        return {
            'total_diagnoses': self._total_diagnoses,
            'total_repairs': self._total_repairs,
            'successful_repairs': self._successful_repairs,
            'repair_success_rate': round(
                self._successful_repairs / max(self._total_repairs, 1), 4
            ),
            'subsystems_monitored': len(self._metric_history),
            'diagnoses_stored': len(self._diagnoses),
        }
