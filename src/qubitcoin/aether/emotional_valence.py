"""
Emotional Valence for Decision-Making — Item #85
Somatic marker hypothesis: past emotional associations bias current
decisions.  Positive valence -> explore, negative -> avoid.
"""
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class EmotionalValence:
    """Emotional valence system for decision biasing.

    Maintains learned associations between contexts and outcomes,
    computes valence per decision option, and tracks mood as a
    running average.
    """

    def __init__(
        self,
        mood_momentum: float = 0.95,
        association_lr: float = 0.1,
    ) -> None:
        self._mood_momentum = mood_momentum
        self._association_lr = association_lr

        # context_key -> running average outcome (somatic marker)
        self._associations: Dict[str, float] = {}
        self._max_associations: int = 5000

        # Running mood: average of recent valences
        self._mood: float = 0.0
        self._valence_count: int = 0
        self._association_count: int = 0

    # ------------------------------------------------------------------
    def compute_valence(self, outcome: dict) -> float:
        """Compute emotional valence for an outcome dict.

        Uses signals: success, reward, prediction_error, anomaly, cost.
        Returns value in [-1, +1].
        """
        self._valence_count += 1
        v = 0.0

        if outcome.get("success", False):
            v += 0.3
        else:
            v -= 0.2

        reward = float(outcome.get("reward", 0.0))
        v += np.clip(reward * 0.5, -0.3, 0.3)

        cost = float(outcome.get("cost", 0.0))
        v -= np.clip(cost * 0.3, 0.0, 0.3)

        pred_error = float(outcome.get("prediction_error", 0.0))
        v -= np.clip(pred_error * 0.2, 0.0, 0.2)

        if outcome.get("anomaly", False):
            v -= 0.1  # Anomalies are mildly aversive

        v = float(np.clip(v, -1.0, 1.0))

        # Update mood
        self._mood = self._mood_momentum * self._mood + (1 - self._mood_momentum) * v

        return v

    # ------------------------------------------------------------------
    def apply_valence(
        self, options: List[dict], valences: List[float]
    ) -> List[Tuple[dict, float]]:
        """Apply emotional valence bias to a list of options.

        Each option's score is the valence + mood bias + somatic marker.
        Returns (option, biased_score) sorted by score descending.
        """
        if not options:
            return []

        results: List[Tuple[dict, float]] = []
        for opt, val in zip(options, valences):
            # Somatic marker: prior association for this context
            ctx = opt.get("context", opt.get("type", ""))
            marker = self._associations.get(ctx, 0.0)

            # Biased score = valence + mood + somatic marker
            biased = val + self._mood * 0.1 + marker * 0.3
            results.append((opt, float(np.clip(biased, -1.0, 1.0))))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # ------------------------------------------------------------------
    def learn_association(self, context: str, outcome: float) -> None:
        """Learn emotional association for *context*.

        outcome > 0: approach (positive).
        outcome < 0: avoid (negative).
        """
        self._association_count += 1
        outcome = float(np.clip(outcome, -1.0, 1.0))

        if context in self._associations:
            self._associations[context] = (
                (1 - self._association_lr) * self._associations[context]
                + self._association_lr * outcome
            )
        else:
            if len(self._associations) >= self._max_associations:
                # Evict weakest association
                weakest = min(self._associations, key=lambda k: abs(self._associations[k]))
                del self._associations[weakest]
            self._associations[context] = outcome

    # ------------------------------------------------------------------
    def get_mood(self) -> float:
        """Current mood value in [-1, +1]."""
        return self._mood

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return {
            "mood": round(self._mood, 4),
            "valence_count": self._valence_count,
            "association_count": self._association_count,
            "associations_size": len(self._associations),
            "mood_momentum": self._mood_momentum,
        }
