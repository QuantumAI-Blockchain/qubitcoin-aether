"""
Narrative Coherence — Item #87
Maintain coherent narrative across reasoning episodes.
Detect themes, track plot structure, identify key moments.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Episode:
    """A single narrative episode."""
    block_height: int
    event: str
    significance: float
    timestamp: float = 0.0
    theme: str = ""


class NarrativeCoherence:
    """Track narrative coherence across reasoning episodes.

    Maintains story arcs, detects recurring themes, and provides
    coherent natural-language summaries of chain history.
    """

    # Plot phases
    PHASES = ("setup", "rising_action", "climax", "resolution", "new_setup")

    def __init__(self, max_episodes: int = 5000) -> None:
        self._episodes: List[Episode] = []
        self._max_episodes = max_episodes
        self._themes: Dict[str, int] = {}  # theme -> occurrence count
        self._current_phase: str = "setup"
        self._phase_start_block: int = 0
        self._key_moments: List[Episode] = []
        self._max_key_moments: int = 100

        # Coherence tracking
        self._coherence_scores: List[float] = []
        self._max_scores: int = 500

    # ------------------------------------------------------------------
    def add_episode(
        self, block_height: int, event: str, significance: float
    ) -> None:
        """Add a narrative episode."""
        significance = float(np.clip(significance, 0.0, 1.0))
        theme = self._detect_theme(event)

        ep = Episode(
            block_height=block_height,
            event=event,
            significance=significance,
            timestamp=time.time(),
            theme=theme,
        )
        self._episodes.append(ep)
        if len(self._episodes) > self._max_episodes:
            self._episodes = self._episodes[-self._max_episodes:]

        # Track theme
        if theme:
            self._themes[theme] = self._themes.get(theme, 0) + 1

        # Key moment if significance > 0.7
        if significance > 0.7:
            self._key_moments.append(ep)
            if len(self._key_moments) > self._max_key_moments:
                self._key_moments = self._key_moments[-self._max_key_moments:]

        # Update plot phase
        self._update_phase(significance)

    # ------------------------------------------------------------------
    def get_narrative(self, window: int = 1000) -> str:
        """Generate a coherent story of what happened recently."""
        recent = self._episodes[-window:]
        if not recent:
            return "No narrative episodes recorded yet."

        # Group by theme
        theme_events: Dict[str, List[Episode]] = {}
        for ep in recent:
            t = ep.theme or "general"
            theme_events.setdefault(t, []).append(ep)

        lines: List[str] = []
        start_block = recent[0].block_height
        end_block = recent[-1].block_height
        lines.append(
            f"Narrative from block {start_block} to {end_block} "
            f"({len(recent)} episodes):"
        )

        # Top themes
        sorted_themes = sorted(
            theme_events.items(), key=lambda x: len(x[1]), reverse=True
        )
        for theme, eps in sorted_themes[:5]:
            avg_sig = np.mean([e.significance for e in eps])
            lines.append(
                f"  [{theme}] {len(eps)} events, avg significance {avg_sig:.2f}"
            )
            # Most significant event in this theme
            best = max(eps, key=lambda e: e.significance)
            lines.append(f"    Peak: block {best.block_height} — {best.event[:80]}")

        lines.append(f"  Current phase: {self._current_phase}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    def check_coherence(self, new_event: str) -> float:
        """Check if *new_event* fits the current narrative.

        Returns coherence score 0-1 (higher = better fit).
        """
        if not self._episodes:
            return 0.5  # No history, neutral

        new_theme = self._detect_theme(new_event)

        # Check if theme has appeared before
        theme_freq = self._themes.get(new_theme, 0)
        total = sum(self._themes.values()) if self._themes else 1
        theme_probability = theme_freq / total if total > 0 else 0.0

        # Recent theme distribution
        recent = self._episodes[-50:]
        recent_themes = [e.theme for e in recent]
        if new_theme in recent_themes:
            recency_bonus = 0.2
        else:
            recency_bonus = 0.0

        # Plot phase coherence (events in resolution phase should be lower significance)
        phase_fit = 0.5
        if self._current_phase == "climax":
            phase_fit = 0.8  # High significance events fit well during climax
        elif self._current_phase == "resolution":
            phase_fit = 0.6

        coherence = float(np.clip(
            theme_probability * 0.4 + recency_bonus + phase_fit * 0.3,
            0.0, 1.0
        ))

        self._coherence_scores.append(coherence)
        if len(self._coherence_scores) > self._max_scores:
            self._coherence_scores = self._coherence_scores[-self._max_scores:]

        return coherence

    # ------------------------------------------------------------------
    def get_key_moments(self, n: int = 10) -> List[dict]:
        """Return the *n* most significant events."""
        sorted_moments = sorted(
            self._key_moments, key=lambda e: e.significance, reverse=True
        )
        return [
            {
                "block_height": ep.block_height,
                "event": ep.event,
                "significance": ep.significance,
                "theme": ep.theme,
            }
            for ep in sorted_moments[:n]
        ]

    # ------------------------------------------------------------------
    def _detect_theme(self, event: str) -> str:
        """Simple theme detection from event text."""
        lower = event.lower()
        if any(w in lower for w in ("difficulty", "mining", "reward", "energy")):
            return "mining"
        if any(w in lower for w in ("knowledge", "reasoning", "phi", "consciousness")):
            return "cognition"
        if any(w in lower for w in ("transaction", "transfer", "utxo", "balance")):
            return "economy"
        if any(w in lower for w in ("contract", "deploy", "qvm")):
            return "contracts"
        if any(w in lower for w in ("anomaly", "error", "repair", "failure")):
            return "anomaly"
        if any(w in lower for w in ("milestone", "growth", "block")):
            return "growth"
        return "general"

    # ------------------------------------------------------------------
    def _update_phase(self, significance: float) -> None:
        """Update plot phase based on significance trajectory."""
        if not self._episodes:
            return

        recent_sigs = [e.significance for e in self._episodes[-20:]]
        if len(recent_sigs) < 5:
            return

        avg_recent = np.mean(recent_sigs[-5:])
        avg_older = np.mean(recent_sigs[:5])

        # Phase transitions
        if self._current_phase == "setup" and avg_recent > avg_older + 0.1:
            self._current_phase = "rising_action"
        elif self._current_phase == "rising_action" and avg_recent > 0.7:
            self._current_phase = "climax"
        elif self._current_phase == "climax" and avg_recent < avg_older - 0.1:
            self._current_phase = "resolution"
        elif self._current_phase == "resolution" and avg_recent < 0.3:
            self._current_phase = "new_setup"
            self._phase_start_block = (
                self._episodes[-1].block_height if self._episodes else 0
            )
        elif self._current_phase == "new_setup" and avg_recent > 0.3:
            self._current_phase = "setup"

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        avg_coherence = (
            float(np.mean(self._coherence_scores))
            if self._coherence_scores else 0.0
        )
        return {
            "total_episodes": len(self._episodes),
            "themes": dict(self._themes),
            "current_phase": self._current_phase,
            "key_moments_count": len(self._key_moments),
            "avg_coherence": round(avg_coherence, 4),
        }
