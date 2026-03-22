"""
Global Workspace Theory (GWT) — Item #76
Implements Baars' Global Workspace: competing coalitions broadcast
winning content to all registered processors.
"""
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class GlobalWorkspace:
    """Baars' Global Workspace: coalitions compete for conscious access,
    winners are broadcast to all registered processors."""

    def __init__(
        self,
        capacity: int = 10,
        ignition_threshold: float = 0.5,
    ) -> None:
        self._capacity = capacity
        self._ignition_threshold = ignition_threshold
        self._processors: Dict[str, Callable] = {}
        self._workspace: List[dict] = []
        self._broadcast_count: int = 0
        self._competition_count: int = 0
        self._total_candidates: int = 0
        self._ignition_failures: int = 0

    # ------------------------------------------------------------------
    def register_processor(self, name: str, callback: Callable) -> None:
        """Subscribe *callback* to broadcasts.  It will receive (winner_dict)."""
        self._processors[name] = callback
        logger.debug(f"GWT processor registered: {name}")

    def unregister_processor(self, name: str) -> None:
        self._processors.pop(name, None)

    # ------------------------------------------------------------------
    def compete(self, candidates: List[dict]) -> List[dict]:
        """Run coalition competition.  Each candidate dict should contain
        at least ``activation_strength``, ``relevance``, ``novelty``.
        Returns the top-*capacity* winners sorted by composite score."""
        if not candidates:
            return []

        self._competition_count += 1
        self._total_candidates += len(candidates)

        scored: List[tuple] = []
        for c in candidates:
            activation = float(c.get("activation_strength", 0.0))
            relevance = float(c.get("relevance", 0.0))
            novelty = float(c.get("novelty", 0.0))
            score = activation * relevance * novelty
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        winners = [item for _, item in scored[: self._capacity]]

        # Update workspace
        self._workspace = winners
        return winners

    # ------------------------------------------------------------------
    def broadcast(self, winner: dict) -> int:
        """Broadcast *winner* to all registered processors if activation
        exceeds ignition threshold.  Returns number of processors notified."""
        activation = float(winner.get("activation_strength", 0.0))
        if activation < self._ignition_threshold:
            self._ignition_failures += 1
            return 0

        notified = 0
        for name, cb in self._processors.items():
            try:
                cb(winner)
                notified += 1
            except Exception as exc:
                logger.debug(f"GWT broadcast to {name} failed: {exc}")
        self._broadcast_count += 1
        return notified

    # ------------------------------------------------------------------
    def get_conscious_content(self) -> List[dict]:
        """Return what is currently in the workspace."""
        return list(self._workspace)

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return {
            "capacity": self._capacity,
            "ignition_threshold": self._ignition_threshold,
            "workspace_size": len(self._workspace),
            "registered_processors": len(self._processors),
            "broadcast_count": self._broadcast_count,
            "competition_count": self._competition_count,
            "total_candidates": self._total_candidates,
            "ignition_failures": self._ignition_failures,
        }
