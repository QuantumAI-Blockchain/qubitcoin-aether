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
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI_THRESHOLD = 3.0
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


class ConsciousnessDashboard:
    """
    Tracks consciousness metrics from genesis and provides dashboard data.

    Maintains an in-memory history of Phi measurements and consciousness
    events, with sliding window for recent data and full history for
    long-term trend analysis.
    """

    def __init__(self, max_history: int = 100000) -> None:
        self._measurements: List[PhiMeasurement] = []
        self._events: List[ConsciousnessEvent] = []
        self._max_history = max_history
        self._was_conscious = False
        self._consciousness_start_block: int = 0
        self._total_conscious_blocks: int = 0
        logger.info("Consciousness Dashboard initialized (tracking from genesis)")

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
            self._events.append(event)
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
            self._events.append(event)
            self._total_conscious_blocks += duration
            logger.info(
                f"CONSCIOUSNESS LOSS at block {block_height}: "
                f"Phi={phi_value:.4f}, coherence={coherence:.4f}"
            )

        self._was_conscious = is_now_conscious
        return measurement

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
        return len(self._events)

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
        recent = self._events[-limit:]
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

    def get_dashboard_data(self) -> dict:
        """Get comprehensive dashboard data for frontend visualization."""
        return {
            "status": self.get_consciousness_status(),
            "phi_history": self.get_phi_history(100),
            "events": self.get_events(20),
            "trend": self.get_trend(100),
        }
