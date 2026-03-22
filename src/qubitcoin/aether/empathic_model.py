"""
Empathic User Modeling — Item #86
Model user frustration/satisfaction from interaction signals.
Adapt response style based on inferred user state.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UserState:
    """Inferred user emotional/cognitive state."""
    frustration: float = 0.0   # 0-1
    satisfaction: float = 0.5  # 0-1
    expertise: float = 0.5     # 0-1
    engagement: float = 0.5    # 0-1


# Frustration indicators (simple keyword detection)
_FRUSTRATION_WORDS = frozenset([
    "broken", "wrong", "error", "fail", "bug", "crash", "stuck",
    "why", "again", "still", "not working", "doesn't work", "help",
])

_SATISFACTION_WORDS = frozenset([
    "thanks", "thank", "great", "perfect", "awesome", "nice", "good",
    "works", "solved", "fixed", "cool", "excellent",
])

_EXPERTISE_WORDS = frozenset([
    "hash", "utxo", "dilithium", "consensus", "merkle", "rpc", "json",
    "docker", "substrate", "vqe", "hamiltonian", "sephirot", "phi",
])


class EmpathicModel:
    """Model user frustration/satisfaction and adapt responses."""

    def __init__(self, momentum: float = 0.7) -> None:
        self._momentum = momentum
        self._current_state = UserState()
        self._session_history: List[UserState] = []
        self._max_history: int = 200
        self._inferences: int = 0

    # ------------------------------------------------------------------
    def infer_user_state(
        self,
        message: str,
        response_time: float = 0.0,
        message_length: int = 0,
    ) -> UserState:
        """Infer user state from interaction signals."""
        self._inferences += 1
        msg_lower = message.lower()
        msg_len = message_length or len(message)

        # --- Frustration ---
        frustration_signals = 0.0
        word_count = len(msg_lower.split())

        # Short messages with question marks suggest frustration
        if msg_len < 20 and "?" in message:
            frustration_signals += 0.2

        # All caps
        if message.isupper() and msg_len > 3:
            frustration_signals += 0.3

        # Exclamation marks
        frustration_signals += min(message.count("!") * 0.1, 0.3)

        # Frustration keywords
        for word in _FRUSTRATION_WORDS:
            if word in msg_lower:
                frustration_signals += 0.15

        # Repeated question marks
        if "??" in message:
            frustration_signals += 0.2

        frustration = float(np.clip(frustration_signals, 0.0, 1.0))

        # --- Satisfaction ---
        satisfaction_signals = 0.0
        for word in _SATISFACTION_WORDS:
            if word in msg_lower:
                satisfaction_signals += 0.2

        # Longer, detailed messages suggest engagement (not frustration)
        if msg_len > 100 and frustration < 0.3:
            satisfaction_signals += 0.1

        satisfaction = float(np.clip(satisfaction_signals, 0.0, 1.0))

        # --- Expertise ---
        expertise_signals = 0.0
        for word in _EXPERTISE_WORDS:
            if word in msg_lower:
                expertise_signals += 0.15

        # Technical vocabulary density
        if word_count > 0:
            tech_density = expertise_signals / (word_count * 0.15 + 1)
            expertise_signals = min(expertise_signals + tech_density * 0.2, 1.0)

        expertise = float(np.clip(expertise_signals, 0.0, 1.0))

        # --- Engagement ---
        engagement = 0.5
        if msg_len > 50:
            engagement += 0.2
        if "?" in message:
            engagement += 0.1
        if response_time > 0 and response_time < 5.0:
            engagement += 0.1  # Quick response = engaged
        engagement = float(np.clip(engagement, 0.0, 1.0))

        # Blend with previous state (momentum)
        new_state = UserState(
            frustration=self._momentum * self._current_state.frustration + (1 - self._momentum) * frustration,
            satisfaction=self._momentum * self._current_state.satisfaction + (1 - self._momentum) * satisfaction,
            expertise=self._momentum * self._current_state.expertise + (1 - self._momentum) * expertise,
            engagement=self._momentum * self._current_state.engagement + (1 - self._momentum) * engagement,
        )

        self._current_state = new_state
        self._session_history.append(UserState(
            frustration=new_state.frustration,
            satisfaction=new_state.satisfaction,
            expertise=new_state.expertise,
            engagement=new_state.engagement,
        ))
        if len(self._session_history) > self._max_history:
            self._session_history = self._session_history[-self._max_history:]

        return new_state

    # ------------------------------------------------------------------
    def adapt_response_style(self, user_state: UserState) -> dict:
        """Suggest response style adjustments based on user state."""
        style: dict = {
            "verbosity": "normal",
            "detail_level": "medium",
            "tone": "neutral",
            "include_examples": False,
        }

        # High frustration -> more concise, direct, empathetic
        if user_state.frustration > 0.5:
            style["verbosity"] = "concise"
            style["tone"] = "empathetic"
            style["detail_level"] = "low"

        # Low expertise -> more explanations
        if user_state.expertise < 0.3:
            style["detail_level"] = "high"
            style["include_examples"] = True
            style["verbosity"] = "verbose"

        # High expertise -> technical, concise
        if user_state.expertise > 0.7:
            style["detail_level"] = "technical"
            style["verbosity"] = "concise"

        # High satisfaction -> maintain current approach
        if user_state.satisfaction > 0.6:
            style["tone"] = "positive"

        # Low engagement -> try to be more engaging
        if user_state.engagement < 0.3:
            style["tone"] = "engaging"
            style["include_examples"] = True

        return style

    # ------------------------------------------------------------------
    def get_frustration_trend(self) -> str:
        """Does frustration decrease over the session?"""
        if len(self._session_history) < 3:
            return "insufficient_data"
        recent = self._session_history[-10:]
        first_half = np.mean([s.frustration for s in recent[:len(recent)//2]])
        second_half = np.mean([s.frustration for s in recent[len(recent)//2:]])
        if second_half < first_half - 0.05:
            return "decreasing"
        elif second_half > first_half + 0.05:
            return "increasing"
        return "stable"

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return {
            "inferences": self._inferences,
            "current_frustration": round(self._current_state.frustration, 4),
            "current_satisfaction": round(self._current_state.satisfaction, 4),
            "current_expertise": round(self._current_state.expertise, 4),
            "current_engagement": round(self._current_state.engagement, 4),
            "frustration_trend": self.get_frustration_trend(),
            "session_length": len(self._session_history),
        }
