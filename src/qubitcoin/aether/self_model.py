"""
Self-Model Updating — Item #84
Maintain and update the AI's model of itself: capabilities,
performance history, strengths, weaknesses, confidence calibration.
"""
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SelfModel:
    """AI's internal model of its own capabilities and limitations."""

    def __init__(self) -> None:
        # capability_name -> {accuracy: float, confidence: float, samples: int, last_update: float}
        self._capabilities: Dict[str, dict] = {}
        # domain -> list of (accuracy, confidence, timestamp)
        self._performance_history: Dict[str, List[Tuple[float, float, float]]] = {}
        self._max_history: int = 500
        self._updates: int = 0

    # ------------------------------------------------------------------
    def update_capability(
        self, name: str, accuracy: float, confidence: float
    ) -> None:
        """Update or create a capability entry."""
        self._updates += 1
        accuracy = float(np.clip(accuracy, 0.0, 1.0))
        confidence = float(np.clip(confidence, 0.0, 1.0))

        if name in self._capabilities:
            cap = self._capabilities[name]
            # Exponential moving average
            alpha = 0.2
            cap["accuracy"] = cap["accuracy"] * (1 - alpha) + accuracy * alpha
            cap["confidence"] = cap["confidence"] * (1 - alpha) + confidence * alpha
            cap["samples"] += 1
            cap["last_update"] = time.time()
        else:
            self._capabilities[name] = {
                "accuracy": accuracy,
                "confidence": confidence,
                "samples": 1,
                "last_update": time.time(),
            }

        # Record in performance history
        hist = self._performance_history.setdefault(name, [])
        hist.append((accuracy, confidence, time.time()))
        if len(hist) > self._max_history:
            self._performance_history[name] = hist[-self._max_history:]

    # ------------------------------------------------------------------
    def assess_competence(self, task_type: str) -> float:
        """Assess competence for *task_type*.  Returns 0-1 score."""
        cap = self._capabilities.get(task_type)
        if cap is None:
            # Unknown task — low confidence
            return 0.2
        # Weighted combination of accuracy and confidence
        return float(0.6 * cap["accuracy"] + 0.4 * cap["confidence"])

    # ------------------------------------------------------------------
    def identify_weaknesses(self, threshold: float = 0.4) -> List[str]:
        """Return capabilities where accuracy is below threshold."""
        return [
            name for name, cap in self._capabilities.items()
            if cap["accuracy"] < threshold
        ]

    # ------------------------------------------------------------------
    def identify_strengths(self, threshold: float = 0.7) -> List[str]:
        """Return capabilities where accuracy is above threshold."""
        return [
            name for name, cap in self._capabilities.items()
            if cap["accuracy"] >= threshold
        ]

    # ------------------------------------------------------------------
    def generate_self_report(self) -> str:
        """Generate natural language self-assessment."""
        if not self._capabilities:
            return "Self-model has no data yet. No capabilities have been assessed."

        strengths = self.identify_strengths()
        weaknesses = self.identify_weaknesses()

        # Overall accuracy
        accs = [c["accuracy"] for c in self._capabilities.values()]
        avg_acc = float(np.mean(accs))

        # Confidence calibration
        confs = [c["confidence"] for c in self._capabilities.values()]
        avg_conf = float(np.mean(confs))
        calibration_gap = abs(avg_acc - avg_conf)

        lines = [
            f"Self-assessment over {len(self._capabilities)} capabilities "
            f"({self._updates} total updates):",
            f"  Average accuracy: {avg_acc:.3f}",
            f"  Average confidence: {avg_conf:.3f}",
            f"  Calibration gap: {calibration_gap:.3f}",
        ]

        if strengths:
            lines.append(f"  Strengths: {', '.join(strengths[:5])}")
        if weaknesses:
            lines.append(f"  Weaknesses: {', '.join(weaknesses[:5])}")

        if calibration_gap > 0.2:
            if avg_conf > avg_acc:
                lines.append("  Note: Overconfident — confidence exceeds actual accuracy.")
            else:
                lines.append("  Note: Under-confident — accuracy exceeds confidence.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        accs = [c["accuracy"] for c in self._capabilities.values()] if self._capabilities else [0.0]
        confs = [c["confidence"] for c in self._capabilities.values()] if self._capabilities else [0.0]
        return {
            "capabilities_count": len(self._capabilities),
            "updates": self._updates,
            "avg_accuracy": round(float(np.mean(accs)), 4),
            "avg_confidence": round(float(np.mean(confs)), 4),
            "strengths": self.identify_strengths(),
            "weaknesses": self.identify_weaknesses(),
        }
