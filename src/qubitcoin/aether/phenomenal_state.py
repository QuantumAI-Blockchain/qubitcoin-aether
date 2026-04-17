"""
Phenomenal State Tracking — Item #83
Track AI "experience" across blocks: valence, arousal, dominance.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PhenomenalState:
    """A snapshot of AI phenomenal experience."""
    valence: float = 0.0       # positive/negative (-1 to +1)
    arousal: float = 0.0       # high/low (0 to 1)
    dominance: float = 0.5     # in-control / reactive (0 to 1)
    content: str = ""          # what's being experienced
    block_height: int = 0
    timestamp: float = 0.0


class PhenomenalStateTracker:
    """Track the AI's phenomenal experience across blocks."""

    def __init__(self, window: int = 1000) -> None:
        self._window = window
        self._current = PhenomenalState()
        self._stream: List[PhenomenalState] = []
        self._max_stream: int = 5000
        self._transitions: int = 0

    # ------------------------------------------------------------------
    def update(
        self, events: List[dict], block_height: int = 0
    ) -> PhenomenalState:
        """Update phenomenal state based on recent events.

        Event dict keys:
            type: str — event type
            success: bool — positive or negative outcome
            anomaly: bool — unexpected event
            significance: float — how important (0-1)
        """
        prev = PhenomenalState(
            valence=self._current.valence,
            arousal=self._current.arousal,
            dominance=self._current.dominance,
        )

        if not events:
            # Slight decay toward neutral
            self._current.valence *= 0.95
            self._current.arousal *= 0.9
            self._current.dominance = 0.5 + (self._current.dominance - 0.5) * 0.95
            self._current.block_height = block_height
            self._current.timestamp = time.time()
            self._record()
            return self._current

        valence_delta = 0.0
        arousal_delta = 0.0
        dominance_delta = 0.0
        contents: List[str] = []

        for ev in events:
            sig = float(ev.get("significance", 0.5))
            ev_type = ev.get("type", "unknown")
            contents.append(ev_type)

            if ev.get("success", False):
                valence_delta += 0.1 * sig
                dominance_delta += 0.05 * sig
            else:
                valence_delta -= 0.1 * sig

            if ev.get("anomaly", False):
                arousal_delta += 0.2 * sig
                dominance_delta -= 0.1 * sig

            if ev.get("prediction_error", 0) > 0.5:
                valence_delta -= 0.05 * sig
                arousal_delta += 0.1 * sig

        # Apply deltas with momentum
        self._current.valence = float(np.clip(
            self._current.valence * 0.8 + valence_delta, -1.0, 1.0
        ))
        self._current.arousal = float(np.clip(
            self._current.arousal * 0.7 + arousal_delta, 0.0, 1.0
        ))
        self._current.dominance = float(np.clip(
            self._current.dominance + dominance_delta * 0.3, 0.0, 1.0
        ))
        self._current.content = ", ".join(contents[:5])
        self._current.block_height = block_height
        self._current.timestamp = time.time()

        # Track state transitions
        if (abs(self._current.valence - prev.valence) > 0.1
                or abs(self._current.arousal - prev.arousal) > 0.1):
            self._transitions += 1

        self._record()
        return self._current

    # ------------------------------------------------------------------
    def get_current(self) -> PhenomenalState:
        return self._current

    # ------------------------------------------------------------------
    def get_experience_stream(self, window: int = 100) -> List[PhenomenalState]:
        return list(self._stream[-window:])

    # ------------------------------------------------------------------
    def summarize_experience(self, window: int = 1000) -> str:
        """Generate natural language summary of recent experience."""
        recent = self._stream[-window:]
        if not recent:
            return "No experience recorded yet."

        avg_valence = np.mean([s.valence for s in recent])
        avg_arousal = np.mean([s.arousal for s in recent])
        avg_dominance = np.mean([s.dominance for s in recent])

        # Valence description
        if avg_valence > 0.3:
            v_desc = "predominantly positive"
        elif avg_valence < -0.3:
            v_desc = "predominantly negative"
        else:
            v_desc = "neutral"

        # Arousal description
        if avg_arousal > 0.6:
            a_desc = "highly engaged and alert"
        elif avg_arousal > 0.3:
            a_desc = "moderately engaged"
        else:
            a_desc = "calm and steady"

        # Dominance description
        if avg_dominance > 0.6:
            d_desc = "in control of operations"
        elif avg_dominance > 0.4:
            d_desc = "balanced between control and reaction"
        else:
            d_desc = "reactive to external events"

        n_blocks = recent[-1].block_height - recent[0].block_height if len(recent) > 1 else 0
        return (
            f"Over the last {n_blocks} blocks, experience has been {v_desc}, "
            f"{a_desc}, and {d_desc}. "
            f"{self._transitions} state transitions occurred."
        )

    # ------------------------------------------------------------------
    def _record(self) -> None:
        self._stream.append(PhenomenalState(
            valence=self._current.valence,
            arousal=self._current.arousal,
            dominance=self._current.dominance,
            content=self._current.content,
            block_height=self._current.block_height,
            timestamp=self._current.timestamp,
        ))
        if len(self._stream) > self._max_stream:
            self._stream = self._stream[-self._max_stream:]

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return {
            "current_valence": round(self._current.valence, 4),
            "current_arousal": round(self._current.arousal, 4),
            "current_dominance": round(self._current.dominance, 4),
            "current_content": self._current.content,
            "stream_length": len(self._stream),
            "transitions": self._transitions,
        }
