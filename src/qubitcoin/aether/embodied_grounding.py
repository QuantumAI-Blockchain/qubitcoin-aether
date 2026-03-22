"""
Embodied Grounding via Chain Interaction — Item #79
Ground abstract concepts in real blockchain data and operations.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GroundingResult:
    """Result of grounding an abstract concept in chain data."""
    concept: str
    grounded_value: float
    source: str
    confidence: float
    timestamp: float
    grounding_type: str  # metric, state, trend, event


# Mapping from abstract concepts to chain data keys and grounding types
_GROUNDING_MAP: Dict[str, dict] = {
    "difficulty": {"key": "difficulty", "type": "metric", "default": 0.0},
    "network_health": {"key": "component_count", "type": "metric", "default": 0.0},
    "activity": {"key": "tx_count", "type": "metric", "default": 0.0},
    "block_production": {"key": "height", "type": "metric", "default": 0.0},
    "knowledge_size": {"key": "kg_nodes", "type": "metric", "default": 0.0},
    "reasoning_quality": {"key": "phi_value", "type": "metric", "default": 0.0},
    "mining_reward": {"key": "reward", "type": "metric", "default": 0.0},
    "energy_efficiency": {"key": "energy", "type": "metric", "default": 0.0},
    "chain_state": {"key": "chain_state", "type": "state", "default": "unknown"},
    "growth_trend": {"key": "kg_nodes", "type": "trend", "default": 0.0},
    "difficulty_trend": {"key": "difficulty", "type": "trend", "default": 0.0},
}


class EmbodiedGrounding:
    """Ground abstract concepts in real blockchain operations."""

    def __init__(self, staleness_blocks: int = 1000) -> None:
        self._staleness_blocks = staleness_blocks
        self._groundings: Dict[str, GroundingResult] = {}
        self._history: Dict[str, List[float]] = {}
        self._max_history: int = 500
        self._ground_count: int = 0
        self._verify_count: int = 0
        self._stale_count: int = 0

    # ------------------------------------------------------------------
    def ground(
        self, concept: str, chain_data: dict, block_height: int = 0
    ) -> GroundingResult:
        """Ground *concept* using *chain_data*.

        Args:
            concept: Abstract concept name (e.g. 'difficulty', 'activity').
            chain_data: Dict of current chain metrics.
            block_height: Current block height for staleness tracking.

        Returns:
            GroundingResult with concrete value and metadata.
        """
        self._ground_count += 1

        mapping = _GROUNDING_MAP.get(concept, {"key": concept, "type": "metric", "default": 0.0})
        key = mapping["key"]
        grounding_type = mapping["type"]

        raw_value = chain_data.get(key, mapping["default"])

        if grounding_type == "trend":
            # Compute trend from history
            hist = self._history.get(key, [])
            if len(hist) >= 2:
                recent = np.array(hist[-20:], dtype=np.float64)
                trend = float(np.polyfit(np.arange(len(recent)), recent, 1)[0])
                grounded_value = trend
            else:
                grounded_value = 0.0
        elif grounding_type == "state":
            grounded_value = 1.0 if raw_value not in (None, "unknown", "") else 0.0
        else:
            grounded_value = float(raw_value) if raw_value is not None else 0.0

        # Track history for trends
        if isinstance(raw_value, (int, float)):
            hist = self._history.setdefault(key, [])
            hist.append(float(raw_value))
            if len(hist) > self._max_history:
                self._history[key] = hist[-self._max_history:]

        # Confidence based on data freshness and availability
        confidence = 0.9 if raw_value is not None else 0.3

        result = GroundingResult(
            concept=concept,
            grounded_value=grounded_value,
            source=key,
            confidence=confidence,
            timestamp=time.time(),
            grounding_type=grounding_type,
        )
        self._groundings[concept] = result
        return result

    # ------------------------------------------------------------------
    def verify_grounding(
        self, concept: str, current_block: int = 0
    ) -> bool:
        """Check if grounding for *concept* is still valid (not stale)."""
        self._verify_count += 1
        gr = self._groundings.get(concept)
        if gr is None:
            return False
        # Check staleness by time (fallback)
        age = time.time() - gr.timestamp
        if age > self._staleness_blocks * 3.3:  # approximate blocks -> seconds
            self._stale_count += 1
            return False
        return True

    # ------------------------------------------------------------------
    def get_all_groundings(self) -> Dict[str, GroundingResult]:
        return dict(self._groundings)

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return {
            "ground_count": self._ground_count,
            "verify_count": self._verify_count,
            "stale_count": self._stale_count,
            "active_groundings": len(self._groundings),
            "known_concepts": list(_GROUNDING_MAP.keys()),
            "history_keys": list(self._history.keys()),
        }
