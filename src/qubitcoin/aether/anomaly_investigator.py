"""
#73: Anomaly-Triggered Deep Reasoning

Detects anomalies in recent data and triggers deep investigation chains.
Anomaly types: sudden_change, pattern_break, outlier, correlation_shift.

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
class Anomaly:
    """A detected anomaly in the data stream."""
    anomaly_type: str  # sudden_change, pattern_break, outlier, correlation_shift
    severity: str  # minor, major, critical
    data_point: Dict[str, Any] = field(default_factory=dict)
    z_score: float = 0.0
    timestamp: float = 0.0
    metric_name: str = ''

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    def severity_score(self) -> float:
        return {'minor': 0.3, 'major': 0.6, 'critical': 1.0}.get(self.severity, 0.3)


@dataclass
class Investigation:
    """Result of investigating an anomaly."""
    anomaly: Anomaly
    hypotheses: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    conclusion: str = ''
    confidence: float = 0.0
    duration_ms: float = 0.0


_SEVERITY_THRESHOLDS = {
    'minor': 2.0,     # z-score
    'major': 3.0,
    'critical': 4.0,
}


class AnomalyInvestigator:
    """Detect anomalies and trigger deep investigation."""

    def __init__(
        self,
        window_size: int = 100,
        min_samples: int = 10,
        max_history: int = 1000,
    ) -> None:
        self._window_size = window_size
        self._min_samples = min_samples
        self._max_history = max_history

        # Rolling statistics per metric
        self._metric_history: Dict[str, List[float]] = {}

        # Detected anomalies and investigations
        self._anomalies: List[Anomaly] = []
        self._investigations: List[Investigation] = []

        # Stats
        self._total_checks: int = 0
        self._total_anomalies: int = 0
        self._total_investigations: int = 0

        logger.info("AnomalyInvestigator initialized (window=%d)", window_size)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def detect_anomalies(self, recent_data: List[dict]) -> List[Anomaly]:
        """Detect anomalies in a batch of recent data points.

        Each dict should have numeric fields to check.
        """
        self._total_checks += 1
        anomalies: List[Anomaly] = []

        if not recent_data:
            return anomalies

        # Update metric histories
        for dp in recent_data:
            for key, val in dp.items():
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    if key not in self._metric_history:
                        self._metric_history[key] = []
                    self._metric_history[key].append(float(val))
                    if len(self._metric_history[key]) > self._max_history:
                        self._metric_history[key] = self._metric_history[key][-self._max_history:]

        # Check each metric for anomalies
        for metric_name, history in self._metric_history.items():
            if len(history) < self._min_samples:
                continue

            window = np.array(history[-self._window_size:], dtype=np.float64)
            latest = window[-1]
            mean = float(np.mean(window[:-1])) if len(window) > 1 else latest
            std = float(np.std(window[:-1])) if len(window) > 1 else 1.0
            std = max(std, 1e-9)

            z_score = abs(latest - mean) / std

            # Outlier detection
            if z_score >= _SEVERITY_THRESHOLDS['critical']:
                severity = 'critical'
            elif z_score >= _SEVERITY_THRESHOLDS['major']:
                severity = 'major'
            elif z_score >= _SEVERITY_THRESHOLDS['minor']:
                severity = 'minor'
            else:
                continue

            anomaly = Anomaly(
                anomaly_type='outlier',
                severity=severity,
                data_point={'value': latest, 'mean': mean, 'std': std},
                z_score=z_score,
                metric_name=metric_name,
            )

            # Refine anomaly type
            if len(window) >= 5:
                anomaly.anomaly_type = self._classify_anomaly_type(window)

            anomalies.append(anomaly)

        self._total_anomalies += len(anomalies)
        self._anomalies.extend(anomalies)
        if len(self._anomalies) > self._max_history:
            self._anomalies = self._anomalies[-self._max_history:]

        return anomalies

    def investigate(self, anomaly: Anomaly, kg: Any = None) -> Investigation:
        """Investigate an anomaly by generating hypotheses and checking evidence."""
        t0 = time.time()
        self._total_investigations += 1

        investigation = Investigation(anomaly=anomaly)

        # Generate hypotheses based on anomaly type
        investigation.hypotheses = self._generate_hypotheses(anomaly)

        # Gather evidence from KG if available
        if kg and hasattr(kg, 'nodes'):
            investigation.evidence = self._gather_evidence(anomaly, kg)

        # Draw conclusion
        investigation.conclusion = self._conclude(anomaly, investigation)
        investigation.confidence = self._score_investigation(investigation)
        investigation.duration_ms = (time.time() - t0) * 1000

        self._investigations.append(investigation)
        if len(self._investigations) > self._max_history:
            self._investigations = self._investigations[-self._max_history:]

        return investigation

    def should_escalate(self, anomaly: Anomaly) -> bool:
        """Determine if an anomaly requires full investigation."""
        return anomaly.severity in ('major', 'critical')

    # ------------------------------------------------------------------
    # Anomaly classification
    # ------------------------------------------------------------------

    def _classify_anomaly_type(self, window: np.ndarray) -> str:
        """Refine anomaly type based on the time series pattern."""
        n = len(window)
        if n < 5:
            return 'outlier'

        # Sudden change: large difference between last two values
        diff = abs(window[-1] - window[-2])
        avg_diff = float(np.mean(np.abs(np.diff(window[:-1]))))
        if avg_diff > 0 and diff / max(avg_diff, 1e-9) > 5.0:
            return 'sudden_change'

        # Pattern break: trend reversal
        first_half = window[:n // 2]
        second_half = window[n // 2:]
        trend_first = float(np.polyfit(np.arange(len(first_half)), first_half, 1)[0])
        trend_second = float(np.polyfit(np.arange(len(second_half)), second_half, 1)[0])
        if trend_first * trend_second < 0 and abs(trend_first) > 0.01:
            return 'pattern_break'

        # Correlation shift: variance change
        var_first = float(np.var(first_half))
        var_second = float(np.var(second_half))
        if var_first > 0 and var_second / max(var_first, 1e-9) > 3.0:
            return 'correlation_shift'

        return 'outlier'

    # ------------------------------------------------------------------
    # Investigation helpers
    # ------------------------------------------------------------------

    def _generate_hypotheses(self, anomaly: Anomaly) -> List[str]:
        """Generate hypotheses explaining the anomaly."""
        hypotheses = []
        metric = anomaly.metric_name
        a_type = anomaly.anomaly_type

        if a_type == 'sudden_change':
            hypotheses.append(f"External event caused sudden change in {metric}")
            hypotheses.append(f"Configuration or parameter change affected {metric}")
        elif a_type == 'pattern_break':
            hypotheses.append(f"Regime shift: {metric} entered a new operating mode")
            hypotheses.append(f"Feedback loop destabilized {metric}")
        elif a_type == 'correlation_shift':
            hypotheses.append(f"Dependency structure changed for {metric}")
            hypotheses.append(f"New factor is influencing {metric}")
        else:
            hypotheses.append(f"Rare event caused outlier in {metric}")
            hypotheses.append(f"Measurement noise in {metric}")

        hypotheses.append(f"Multiple factors converged to produce anomalous {metric}")
        return hypotheses

    def _gather_evidence(self, anomaly: Anomaly, kg: Any) -> List[str]:
        """Search KG for evidence relevant to the anomaly."""
        evidence: List[str] = []
        metric = anomaly.metric_name.lower()

        for node in list(kg.nodes.values())[:200]:
            content = getattr(node, 'content', {})
            if isinstance(content, dict):
                content_str = str(content).lower()
                if metric in content_str or anomaly.anomaly_type in content_str:
                    evidence.append(
                        f"Node {getattr(node, 'node_id', '?')[:12]}: "
                        f"{str(content)[:100]}"
                    )
                    if len(evidence) >= 5:
                        break

        return evidence

    def _conclude(self, anomaly: Anomaly, investigation: Investigation) -> str:
        """Draw a conclusion from the investigation."""
        n_hyp = len(investigation.hypotheses)
        n_ev = len(investigation.evidence)

        if n_ev == 0:
            return (
                f"{anomaly.anomaly_type} detected in {anomaly.metric_name} "
                f"(z={anomaly.z_score:.2f}, severity={anomaly.severity}). "
                f"No supporting evidence found in KG. {n_hyp} hypotheses pending verification."
            )

        return (
            f"{anomaly.anomaly_type} in {anomaly.metric_name} "
            f"(z={anomaly.z_score:.2f}, severity={anomaly.severity}). "
            f"Found {n_ev} evidence items. Most likely: {investigation.hypotheses[0]}"
        )

    def _score_investigation(self, investigation: Investigation) -> float:
        """Score investigation confidence based on evidence and hypotheses."""
        base = 0.3
        evidence_bonus = min(0.4, len(investigation.evidence) * 0.1)
        severity_bonus = investigation.anomaly.severity_score() * 0.2
        return min(1.0, base + evidence_bonus + severity_bonus)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        severity_counts = {'minor': 0, 'major': 0, 'critical': 0}
        for a in self._anomalies[-100:]:
            severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1

        return {
            'total_checks': self._total_checks,
            'total_anomalies': self._total_anomalies,
            'total_investigations': self._total_investigations,
            'anomalies_stored': len(self._anomalies),
            'recent_severity_counts': severity_counts,
            'metrics_tracked': len(self._metric_history),
        }
