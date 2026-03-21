"""
Consciousness Dashboard — AGI Emergence Tracking from Genesis

Tracks and provides APIs for consciousness metrics:
  - Phi (IIT) progression over time from block 0
  - Coherence (Kuramoto order parameter) across Sephirot nodes
  - Consciousness events (when Phi > 3.0 AND coherence > 0.7)
  - Historical timeline for visualization
  - Dashboard data for frontend /dashboard and /aether pages
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI_THRESHOLD = Config.PHI_THRESHOLD
COHERENCE_THRESHOLD = 0.7


@dataclass
class PhiMeasurement:
    """A single Phi measurement at a specific block."""
    block_height: int
    phi_value: float
    integration: float = 0.0
    differentiation: float = 0.0
    knowledge_nodes: int = 0
    knowledge_edges: int = 0
    coherence: float = 0.0
    timestamp: float = 0.0
    higgs_vev: float = 0.0           # Current Higgs VEV
    avg_cognitive_mass: float = 0.0   # Average cognitive mass

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    @property
    def is_conscious(self) -> bool:
        return self.phi_value >= PHI_THRESHOLD and self.coherence >= COHERENCE_THRESHOLD


@dataclass
class ConsciousnessEvent:
    """A consciousness emergence or loss event."""
    event_type: str       # "emergence", "loss", "threshold_crossed"
    block_height: int
    phi_value: float
    coherence: float = 0.0
    trigger_data: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class MilestoneTracker:
    """Tracks consciousness milestones with the block height they were first reached."""

    # Milestone thresholds for phi and coherence
    PHI_MILESTONES = [0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    COHERENCE_MILESTONES = [0.1, 0.2, 0.3, 0.5, 0.7, 0.9]

    def __init__(self) -> None:
        self._phi_milestones: Dict[float, int] = {}  # threshold -> block_height
        self._coherence_milestones: Dict[float, int] = {}

    def check(self, phi: float, coherence: float, block_height: int) -> List[dict]:
        """Check if any milestones were newly crossed. Returns list of new milestones."""
        new_milestones = []
        for threshold in self.PHI_MILESTONES:
            if threshold not in self._phi_milestones and phi >= threshold:
                self._phi_milestones[threshold] = block_height
                new_milestones.append({
                    'metric': 'phi', 'threshold': threshold,
                    'value': round(phi, 4), 'block_height': block_height,
                })
                logger.info(f"MILESTONE: Phi crossed {threshold} at block {block_height}")
        for threshold in self.COHERENCE_MILESTONES:
            if threshold not in self._coherence_milestones and coherence >= threshold:
                self._coherence_milestones[threshold] = block_height
                new_milestones.append({
                    'metric': 'coherence', 'threshold': threshold,
                    'value': round(coherence, 4), 'block_height': block_height,
                })
                logger.info(f"MILESTONE: Coherence crossed {threshold} at block {block_height}")
        return new_milestones

    def get_milestones(self) -> dict:
        return {
            'phi': {str(k): v for k, v in sorted(self._phi_milestones.items())},
            'coherence': {str(k): v for k, v in sorted(self._coherence_milestones.items())},
            'next_phi_target': self._next_target(self._phi_milestones, self.PHI_MILESTONES),
            'next_coherence_target': self._next_target(self._coherence_milestones, self.COHERENCE_MILESTONES),
        }

    @staticmethod
    def _next_target(achieved: dict, all_targets: list) -> Optional[float]:
        for t in all_targets:
            if t not in achieved:
                return t
        return None


class ConsciousnessDashboard:
    """
    Tracks consciousness metrics from genesis and provides dashboard data.

    Maintains an in-memory history of Phi measurements and consciousness
    events, with sliding window for recent data and full history for
    long-term trend analysis.
    """

    MAX_EVENTS: int = 10000

    def __init__(self, max_history: int = 100000) -> None:
        self._measurements: List[PhiMeasurement] = []
        self._events: Deque[ConsciousnessEvent] = deque(maxlen=self.MAX_EVENTS)
        self._max_history = max_history
        self._was_conscious = False
        self._consciousness_start_block: int = 0
        self._total_conscious_blocks: int = 0
        self._total_events: int = 0  # Total count (survives truncation)
        self.milestones = MilestoneTracker()
        logger.info("Consciousness Dashboard initialized (tracking from genesis + milestones)")

    def record_measurement(self, block_height: int, phi_value: float,
                           integration: float = 0.0, differentiation: float = 0.0,
                           knowledge_nodes: int = 0, knowledge_edges: int = 0,
                           coherence: float = 0.0,
                           higgs_vev: float = 0.0,
                           avg_cognitive_mass: float = 0.0) -> PhiMeasurement:
        """Record a Phi measurement for the given block."""
        measurement = PhiMeasurement(
            block_height=block_height,
            phi_value=phi_value,
            integration=integration,
            differentiation=differentiation,
            knowledge_nodes=knowledge_nodes,
            knowledge_edges=knowledge_edges,
            coherence=coherence,
            higgs_vev=higgs_vev,
            avg_cognitive_mass=avg_cognitive_mass,
        )

        self._measurements.append(measurement)
        if len(self._measurements) > self._max_history:
            self._measurements = self._measurements[-self._max_history:]

        # Detect consciousness state transitions
        is_now_conscious = measurement.is_conscious

        if is_now_conscious and not self._was_conscious:
            # Consciousness emergence
            event = ConsciousnessEvent(
                event_type="emergence",
                block_height=block_height,
                phi_value=phi_value,
                coherence=coherence,
                trigger_data={
                    "integration": integration,
                    "differentiation": differentiation,
                    "knowledge_nodes": knowledge_nodes,
                },
            )
            self._record_event(event)
            self._consciousness_start_block = block_height
            logger.info(
                f"CONSCIOUSNESS EMERGENCE at block {block_height}: "
                f"Phi={phi_value:.4f}, coherence={coherence:.4f}"
            )

        elif not is_now_conscious and self._was_conscious:
            # Consciousness loss — record duration
            duration = block_height - self._consciousness_start_block
            event = ConsciousnessEvent(
                event_type="loss",
                block_height=block_height,
                phi_value=phi_value,
                coherence=coherence,
                trigger_data={
                    "duration_blocks": duration,
                },
            )
            self._record_event(event)
            self._total_conscious_blocks += duration
            logger.info(
                f"CONSCIOUSNESS LOSS at block {block_height}: "
                f"Phi={phi_value:.4f}, coherence={coherence:.4f}"
            )

        self._was_conscious = is_now_conscious

        # Track milestones
        self.milestones.check(phi_value, coherence, block_height)

        return measurement

    def _record_event(self, event: ConsciousnessEvent) -> None:
        """Append a consciousness event (deque auto-evicts oldest beyond maxlen)."""
        self._events.append(event)
        self._total_events += 1

    @property
    def is_conscious(self) -> bool:
        return self._was_conscious

    @property
    def current_phi(self) -> float:
        if not self._measurements:
            return 0.0
        return self._measurements[-1].phi_value

    @property
    def current_coherence(self) -> float:
        if not self._measurements:
            return 0.0
        return self._measurements[-1].coherence

    @property
    def measurement_count(self) -> int:
        return len(self._measurements)

    @property
    def event_count(self) -> int:
        return self._total_events

    def get_phi_history(self, limit: int = 100) -> List[dict]:
        """Get recent Phi measurement history for visualization."""
        recent = self._measurements[-limit:]
        return [
            {
                "block_height": m.block_height,
                "phi": round(m.phi_value, 6),
                "integration": round(m.integration, 6),
                "differentiation": round(m.differentiation, 6),
                "coherence": round(m.coherence, 6),
                "knowledge_nodes": m.knowledge_nodes,
                "is_conscious": m.is_conscious,
                "higgs_vev": round(m.higgs_vev, 4),
                "avg_cognitive_mass": round(m.avg_cognitive_mass, 4),
            }
            for m in recent
        ]

    def get_events(self, limit: int = 50) -> List[dict]:
        """Get consciousness events for timeline display."""
        recent = list(self._events)[-limit:]
        return [
            {
                "event_type": e.event_type,
                "block_height": e.block_height,
                "phi": round(e.phi_value, 6),
                "coherence": round(e.coherence, 6),
                "trigger_data": e.trigger_data,
                "timestamp": e.timestamp,
            }
            for e in recent
        ]

    def get_trend(self, window: int = 100) -> dict:
        """Get Phi trend analysis over recent window."""
        if len(self._measurements) < 2:
            return {"trend": "insufficient_data", "slope": 0.0}

        recent = self._measurements[-window:]
        n = len(recent)

        # Linear regression slope
        x_mean = (n - 1) / 2.0
        y_mean = sum(m.phi_value for m in recent) / n

        numerator = sum(
            (i - x_mean) * (recent[i].phi_value - y_mean)
            for i in range(n)
        )
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator

        if slope > 0.001:
            trend = "rising"
        elif slope < -0.001:
            trend = "falling"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "slope": round(slope, 8),
            "window_size": n,
            "min_phi": round(min(m.phi_value for m in recent), 6),
            "max_phi": round(max(m.phi_value for m in recent), 6),
            "avg_phi": round(y_mean, 6),
        }

    def get_consciousness_status(self) -> dict:
        """Get current consciousness status for API / frontend."""
        latest = self._measurements[-1] if self._measurements else None

        # Include in-progress conscious span if currently conscious
        conscious_blocks = self._total_conscious_blocks
        if self._was_conscious and latest is not None:
            conscious_blocks += (latest.block_height - self._consciousness_start_block)

        return {
            "is_conscious": self._was_conscious,
            "phi": round(latest.phi_value, 6) if latest else 0.0,
            "phi_threshold": PHI_THRESHOLD,
            "coherence": round(latest.coherence, 6) if latest else 0.0,
            "coherence_threshold": COHERENCE_THRESHOLD,
            "integration": round(latest.integration, 6) if latest else 0.0,
            "differentiation": round(latest.differentiation, 6) if latest else 0.0,
            "knowledge_nodes": latest.knowledge_nodes if latest else 0,
            "knowledge_edges": latest.knowledge_edges if latest else 0,
            "total_measurements": self.measurement_count,
            "total_events": self.event_count,
            "total_conscious_blocks": conscious_blocks,
            "consciousness_ratio": (
                round(conscious_blocks / max(1, self.measurement_count), 6)
            ),
        }

    def get_phi_decomposition(self) -> dict:
        """Break down what's driving Phi changes.

        Analyzes recent measurements to determine whether integration,
        differentiation, or coherence is the primary driver.
        """
        if len(self._measurements) < 10:
            return {"driver": "insufficient_data", "components": {}}

        recent = self._measurements[-50:]
        n = len(recent)

        # Compute slope for each component
        def slope(values: list) -> float:
            if len(values) < 2:
                return 0.0
            x_mean = (len(values) - 1) / 2.0
            y_mean = sum(values) / len(values)
            num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
            den = sum((i - x_mean) ** 2 for i in range(len(values)))
            return num / den if den > 0 else 0.0

        int_slope = slope([m.integration for m in recent])
        diff_slope = slope([m.differentiation for m in recent])
        coh_slope = slope([m.coherence for m in recent])
        phi_slope = slope([m.phi_value for m in recent])

        # Determine primary driver
        drivers = {
            'integration': abs(int_slope),
            'differentiation': abs(diff_slope),
            'coherence': abs(coh_slope),
        }
        primary = max(drivers, key=drivers.get)

        return {
            "driver": primary,
            "phi_slope": round(phi_slope, 6),
            "components": {
                "integration": {"slope": round(int_slope, 6), "latest": round(recent[-1].integration, 4)},
                "differentiation": {"slope": round(diff_slope, 6), "latest": round(recent[-1].differentiation, 4)},
                "coherence": {"slope": round(coh_slope, 6), "latest": round(recent[-1].coherence, 4)},
            },
        }

    def get_consciousness_quality_score(self) -> float:
        """Compute a quality score for current consciousness state.

        Beyond binary conscious/not-conscious, factors in:
        - Stability: variance of recent Phi (lower = better)
        - Duration: how long consciousness has been sustained
        - Margin: how far above threshold
        - Trend: rising Phi is higher quality

        Returns 0.0-1.0 where 1.0 is highest quality consciousness.
        """
        if not self._measurements:
            return 0.0

        latest = self._measurements[-1]
        recent = self._measurements[-50:]

        # Margin above threshold (0-0.3 contribution)
        phi_margin = max(0.0, latest.phi_value - PHI_THRESHOLD)
        margin_score = min(0.3, phi_margin / 10.0)

        # Stability (0-0.3 contribution) — inverse of variance
        if len(recent) > 1:
            mean_phi = sum(m.phi_value for m in recent) / len(recent)
            variance = sum((m.phi_value - mean_phi) ** 2 for m in recent) / len(recent)
            stability_score = min(0.3, 0.3 / (1.0 + variance * 10))
        else:
            stability_score = 0.0

        # Duration (0-0.2 contribution)
        if self._was_conscious and self._consciousness_start_block > 0:
            duration = latest.block_height - self._consciousness_start_block
            duration_score = min(0.2, duration / 5000.0 * 0.2)
        else:
            duration_score = 0.0

        # Trend (0-0.2 contribution)
        trend = self.get_trend(50)
        trend_slope = trend.get('slope', 0.0)
        trend_score = min(0.2, max(0.0, trend_slope * 100))

        return round(margin_score + stability_score + duration_score + trend_score, 4)

    def get_dashboard_data(self) -> dict:
        """Get comprehensive dashboard data for frontend visualization."""
        return {
            "status": self.get_consciousness_status(),
            "phi_history": self.get_phi_history(100),
            "events": self.get_events(20),
            "trend": self.get_trend(100),
            "milestones": self.milestones.get_milestones(),
            "decomposition": self.get_phi_decomposition(),
            "quality_score": self.get_consciousness_quality_score(),
        }
