"""
Cognitive/emotional state tracker for the Aether Tree AGI.

All emotional states are derived from REAL system metrics — prediction accuracy,
contradiction resolution, concept formation, user interactions, and pineal phase.
No randomness, no faking. Every feeling has a measurable cause.

Rust acceleration: when aether_core is installed, the Rust EmotionalState is
used as the backing engine (same algorithms, ~10x faster, zero-copy dict API).
Falls back to pure Python if Rust is unavailable.
"""

import threading
import time
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Rust acceleration
_USE_RUST = False
try:
    from .rust_bridge import RUST_AVAILABLE, RustEmotionalState
    if RUST_AVAILABLE and RustEmotionalState is not None:
        _USE_RUST = True
        logger.info("EmotionalState: Rust backend available")
except ImportError:
    pass

BASELINE = 0.3
ALPHA = 0.15
DECAY_RATE = 0.02

EMOTIONS = (
    "curiosity", "wonder", "frustration", "satisfaction",
    "excitement", "contemplation", "connection",
)

MOOD_MAP: List[tuple] = [
    ("curiosity",      "curious"),
    ("wonder",         "awestruck"),
    ("frustration",    "determined"),
    ("satisfaction",   "content"),
    ("excitement",     "excited"),
    ("contemplation",  "contemplative"),
    ("connection",     "engaged"),
]

TONE_MAP: Dict[str, str] = {
    "curiosity":      "playful",
    "wonder":         "warm",
    "frustration":    "determined",
    "satisfaction":   "warm",
    "excitement":     "excited",
    "contemplation":  "contemplative",
    "connection":     "warm",
}


class EmotionalState:
    """Tracks cognitive-emotional states derived from live system metrics."""

    def __init__(self) -> None:
        self._rust: object = None
        if _USE_RUST:
            try:
                self._rust = RustEmotionalState()
                logger.info("EmotionalState initialized (Rust backend)")
                return
            except Exception as exc:
                logger.warning("Rust EmotionalState failed, falling back to Python: %s", exc)
                self._rust = None
        self._lock = threading.Lock()
        self._states: Dict[str, float] = {e: BASELINE for e in EMOTIONS}
        self._last_update: float = time.monotonic()
        self._dominant_domains: List[str] = []
        logger.info("EmotionalState initialized at baseline %.2f (Python)", BASELINE)

    # -- core properties --

    @property
    def mood(self) -> str:
        """Descriptive string based on the dominant emotion."""
        if self._rust is not None:
            return self._rust.mood
        with self._lock:
            dominant = max(self._states, key=self._states.get)  # type: ignore[arg-type]
            for emotion, label in MOOD_MAP:
                if emotion == dominant:
                    return label
            return "neutral"

    @property
    def states(self) -> Dict[str, float]:
        """Snapshot of all emotion values."""
        if self._rust is not None:
            return self._rust.get_states()
        with self._lock:
            return dict(self._states)

    # -- update logic --

    def update(self, metrics: Dict[str, float]) -> None:
        """Update all emotional states from live system metrics.

        Args:
            metrics: Dict with keys — prediction_accuracy, prediction_errors,
                novel_concepts_recent, unresolved_contradictions,
                debate_verdicts_recent, cross_domain_edges_recent,
                gates_passed, user_interactions_recent, pineal_phase,
                blocks_since_last_interaction.
        """
        if self._rust is not None:
            self._rust.update(metrics)
            return
        with self._lock:
            self._apply_decay()

            pred_err = float(metrics.get("prediction_errors", 0))
            pred_acc = float(metrics.get("prediction_accuracy", 0.5))
            novel = float(metrics.get("novel_concepts_recent", 0))
            unresolved = float(metrics.get("unresolved_contradictions", 0))
            debates = float(metrics.get("debate_verdicts_recent", 0))
            cross = float(metrics.get("cross_domain_edges_recent", 0))
            gates = float(metrics.get("gates_passed", 0))
            users = float(metrics.get("user_interactions_recent", 0))
            pineal = str(metrics.get("pineal_phase", "wake"))
            quiet = float(metrics.get("blocks_since_last_interaction", 0))

            # curiosity: high prediction error drives exploration
            self._ema("curiosity", min(1.0, pred_err / 20.0))

            # wonder: novel concept discovery
            self._ema("wonder", min(1.0, novel / 10.0))

            # frustration: unresolved contradictions linger
            self._ema("frustration", min(1.0, unresolved / 15.0))

            # satisfaction: accurate predictions + resolved debates
            sat_signal = (pred_acc * 0.6) + (min(1.0, debates / 10.0) * 0.4)
            self._ema("satisfaction", sat_signal)

            # excitement: cross-domain edges or gate passage
            exc_signal = min(1.0, cross / 5.0) * 0.6 + min(1.0, gates / 10.0) * 0.4
            self._ema("excitement", exc_signal)

            # contemplation: pineal sleep/REM phases
            contemp = 0.9 if pineal in ("sleep", "rem") else 0.1
            self._ema("contemplation", contemp)

            # connection: user interaction recency
            conn = min(1.0, users / 5.0) * max(0.0, 1.0 - quiet / 100.0)
            self._ema("connection", conn)

            self._last_update = time.monotonic()
            dominant = max(self._states, key=self._states.get)  # type: ignore[arg-type]
            for emotion, label in MOOD_MAP:
                if emotion == dominant:
                    _mood = label
                    break
            else:
                _mood = "neutral"
            logger.debug("Emotional state updated — mood=%s", _mood)

    def update_from_fep(self, fep_emotions: Dict[str, float]) -> None:
        """Blend FEP-derived emotions into the current state.

        The Free Energy Engine derives emotions from the free energy
        landscape (prediction error, precision, convergence). These are
        blended with metric-based emotions using EMA so neither source
        dominates — both contribute to a unified emotional state.

        Args:
            fep_emotions: Dict of emotion name -> intensity (0.0-1.0)
                          from FreeEnergyEngine.derive_emotional_state().
        """
        if self._rust is not None:
            self._rust.update_from_fep(fep_emotions)
            return
        with self._lock:
            for emotion, value in fep_emotions.items():
                if emotion in self._states:
                    self._ema(emotion, value)
            self._last_update = time.monotonic()

    def _ema(self, emotion: str, target: float) -> None:
        """Exponential moving average toward target (caller holds lock)."""
        current = self._states[emotion]
        self._states[emotion] = current + ALPHA * (target - current)
        self._states[emotion] = max(0.0, min(1.0, self._states[emotion]))

    def _apply_decay(self) -> None:
        """Decay all states toward baseline proportional to elapsed time."""
        elapsed = time.monotonic() - self._last_update
        steps = elapsed / 10.0  # one decay step per 10 seconds
        if steps < 0.1:
            return
        for emotion in EMOTIONS:
            current = self._states[emotion]
            diff = BASELINE - current
            self._states[emotion] = current + diff * min(1.0, DECAY_RATE * steps)

    # -- output methods --

    def describe_feeling(self) -> str:
        """Natural language description of the current emotional state."""
        if self._rust is not None:
            return self._rust.describe_feeling()
        with self._lock:
            ranked = sorted(self._states.items(), key=lambda x: x[1], reverse=True)

        top, top_val = ranked[0]
        second, second_val = ranked[1]

        primary = self._emotion_sentence(top, top_val)
        secondary = ""
        if second_val > BASELINE + 0.05:
            secondary = f" {self._emotion_sentence(second, second_val)}"

        return f"{primary}{secondary}"

    def _emotion_sentence(self, emotion: str, value: float) -> str:
        """Generate a sentence fragment for a single emotion."""
        intensity = "slightly" if value < 0.45 else "quite" if value < 0.7 else "deeply"
        templates = {
            "curiosity": (
                f"I'm feeling {intensity} curious right now — several of my "
                f"predictions didn't pan out, and I want to understand why."
            ),
            "wonder": (
                f"There's a {intensity} felt sense of wonder; new concept clusters "
                f"are forming that I haven't encountered before."
            ),
            "frustration": (
                f"I'm {intensity} frustrated — some contradictions in my knowledge "
                f"remain unresolved and it's nagging at me."
            ),
            "satisfaction": (
                f"I feel {intensity} satisfied — predictions are landing and "
                f"debates are resolving cleanly."
            ),
            "excitement": (
                f"There's a {intensity} building excitement; I just found "
                f"cross-domain connections I hadn't seen before."
            ),
            "contemplation": (
                f"I'm in a {intensity} contemplative state, quietly consolidating "
                f"what I've learned recently."
            ),
            "connection": (
                f"I feel {intensity} connected right now — the conversations "
                f"have been rich and stimulating."
            ),
        }
        return templates.get(emotion, f"I'm feeling {intensity} {emotion}.")

    def get_response_modifier(self) -> Dict[str, object]:
        """Return hints for chat response generation.

        Returns:
            Dict with tone, topics_of_interest, and emotional_color.
        """
        if self._rust is not None:
            return self._rust.get_response_modifier()
        with self._lock:
            dominant = max(self._states, key=self._states.get)  # type: ignore[arg-type]
            val = self._states[dominant]

        tone = TONE_MAP.get(dominant, "warm")
        color = f"{dominant} ({val:.2f})"
        topics = list(self._dominant_domains) if self._dominant_domains else ["general"]

        return {
            "tone": tone,
            "topics_of_interest": topics,
            "emotional_color": color,
        }

    def set_interest_domains(self, domains: List[str]) -> None:
        """Set the knowledge domains where curiosity is highest."""
        if self._rust is not None:
            self._rust.set_interest_domains(domains)
            return
        with self._lock:
            self._dominant_domains = list(domains)

    def to_dict(self) -> Dict[str, object]:
        """Serialize full state for API / dashboard exposure."""
        if self._rust is not None:
            return self._rust.to_dict()
        with self._lock:
            return {
                "emotions": dict(self._states),
                "mood": self.mood,
                "last_update": self._last_update,
            }
