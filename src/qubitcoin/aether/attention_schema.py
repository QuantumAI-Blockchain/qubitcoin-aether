"""
Attention Schema Theory (AST) — Item #77
Models the AI's own attention allocation following Graziano's AST.
Tracks where attention is focused, provides meta-attention reports.
"""
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class AttentionSchema:
    """Model of the AI's own attention allocation.

    Maintains a budget of 1.0 distributed across active targets.
    Unattended items decay over time.
    """

    def __init__(
        self,
        decay_rate: float = 0.05,
        shift_momentum: float = 0.3,
    ) -> None:
        self._decay_rate = decay_rate
        self._shift_momentum = shift_momentum
        # target -> allocation (sums to 1.0)
        self._allocations: Dict[str, float] = {}
        # history for meta-attention
        self._history: List[Dict[str, float]] = []
        self._max_history: int = 500
        self._shifts: int = 0
        self._allocations_total: int = 0

    # ------------------------------------------------------------------
    def allocate(
        self, targets: List[str], importance: List[float]
    ) -> Dict[str, float]:
        """Allocate attention budget across *targets* proportional to
        *importance*.  Returns the resulting allocation map."""
        if not targets:
            return {}

        self._allocations_total += 1
        imp = np.array(importance, dtype=np.float64)
        imp = np.clip(imp, 0.0, None)
        total = imp.sum()
        if total < 1e-12:
            imp = np.ones(len(targets), dtype=np.float64)
            total = imp.sum()

        normed = imp / total
        new_alloc: Dict[str, float] = {}
        for t, w in zip(targets, normed.tolist()):
            new_alloc[t] = w

        # Blend with previous allocation for smooth transitions
        for t in new_alloc:
            if t in self._allocations:
                new_alloc[t] = (
                    self._shift_momentum * new_alloc[t]
                    + (1 - self._shift_momentum) * self._allocations[t]
                )

        # Re-normalise
        s = sum(new_alloc.values())
        if s > 1e-12:
            new_alloc = {k: v / s for k, v in new_alloc.items()}

        self._allocations = new_alloc
        self._record_snapshot()
        return dict(self._allocations)

    # ------------------------------------------------------------------
    def get_focus(self) -> str:
        """Return the target currently receiving the most attention."""
        if not self._allocations:
            return ""
        return max(self._allocations, key=self._allocations.get)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    def shift_attention(self, new_target: str, urgency: float) -> None:
        """Shift attention toward *new_target* proportional to *urgency* (0-1)."""
        urgency = float(np.clip(urgency, 0.0, 1.0))
        self._shifts += 1

        if not self._allocations:
            self._allocations = {new_target: 1.0}
            self._record_snapshot()
            return

        # Reduce others and give to new target
        steal = urgency * 0.5
        remaining = 1.0 - steal
        new_alloc: Dict[str, float] = {}
        for t, v in self._allocations.items():
            new_alloc[t] = v * remaining
        new_alloc[new_target] = new_alloc.get(new_target, 0.0) + steal

        # Normalise
        s = sum(new_alloc.values())
        if s > 1e-12:
            new_alloc = {k: v / s for k, v in new_alloc.items()}
        self._allocations = new_alloc
        self._record_snapshot()

    # ------------------------------------------------------------------
    def decay(self) -> None:
        """Apply decay to all allocations (items not attended lose weight)."""
        if not self._allocations:
            return
        focus = self.get_focus()
        new_alloc: Dict[str, float] = {}
        for t, v in self._allocations.items():
            if t == focus:
                new_alloc[t] = v  # focused item doesn't decay
            else:
                new_alloc[t] = v * (1.0 - self._decay_rate)
        # Normalise
        s = sum(new_alloc.values())
        if s > 1e-12:
            new_alloc = {k: v / s for k, v in new_alloc.items()}
        self._allocations = new_alloc

    # ------------------------------------------------------------------
    def meta_attention(self) -> dict:
        """Report on attention patterns — what gets most attention, what's neglected."""
        if not self._history:
            return {"focus": "", "most_attended": "", "neglected": [], "entropy": 0.0}

        # Aggregate attention over history
        totals: Dict[str, float] = {}
        for snap in self._history:
            for t, v in snap.items():
                totals[t] = totals.get(t, 0.0) + v

        if not totals:
            return {"focus": "", "most_attended": "", "neglected": [], "entropy": 0.0}

        s = sum(totals.values())
        if s > 1e-12:
            totals = {k: v / s for k, v in totals.items()}

        most_attended = max(totals, key=totals.get)  # type: ignore[arg-type]
        threshold = 1.0 / (len(totals) + 1)
        neglected = [t for t, v in totals.items() if v < threshold * 0.5]

        # Shannon entropy
        vals = np.array(list(totals.values()), dtype=np.float64)
        vals = vals[vals > 1e-12]
        entropy = float(-np.sum(vals * np.log2(vals))) if len(vals) > 0 else 0.0

        return {
            "focus": self.get_focus(),
            "most_attended": most_attended,
            "neglected": neglected,
            "entropy": entropy,
            "allocation": dict(self._allocations),
        }

    # ------------------------------------------------------------------
    def _record_snapshot(self) -> None:
        self._history.append(dict(self._allocations))
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        meta = self.meta_attention()
        return {
            "current_focus": self.get_focus(),
            "num_targets": len(self._allocations),
            "shifts": self._shifts,
            "allocations_total": self._allocations_total,
            "history_length": len(self._history),
            "entropy": meta.get("entropy", 0.0),
            "neglected_count": len(meta.get("neglected", [])),
        }
