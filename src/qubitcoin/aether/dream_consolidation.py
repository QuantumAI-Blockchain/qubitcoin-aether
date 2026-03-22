"""
#93: Dream-State Consolidation

Offline processing during low-activity periods: random memory
reactivation, pattern strengthening, pruning of weak memories,
and creative discovery of novel connections.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895


@dataclass
class ConsolidationResult:
    """Result of a dream consolidation cycle."""
    merged_count: int = 0
    strengthened_count: int = 0
    pruned_count: int = 0
    new_connections: int = 0
    creative_discoveries: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class DreamConsolidation:
    """Dream-state memory consolidation engine.

    Runs during low-activity periods (slow blocks) to:
      1. Randomly reactivate and replay memories in new combinations
      2. Strengthen frequently co-occurring patterns
      3. Prune low-confidence, low-access memories
      4. Discover novel connections via random node combination
    """

    def __init__(
        self,
        slow_block_threshold: float = 10.0,
        prune_confidence_threshold: float = 0.3,
        prune_min_age_blocks: int = 500,
        max_creative_attempts: int = 20,
    ) -> None:
        self._slow_threshold = slow_block_threshold
        self._prune_conf_threshold = prune_confidence_threshold
        self._prune_min_age = prune_min_age_blocks
        self._max_creative = max_creative_attempts
        # Co-occurrence tracking
        self._cooccurrence: Dict[Tuple[str, str], int] = {}
        self._max_cooccurrence = 5000
        # Stats
        self._total_consolidations = 0
        self._total_merged = 0
        self._total_strengthened = 0
        self._total_pruned = 0
        self._total_creative = 0
        self._last_consolidation_block: int = 0

    # ------------------------------------------------------------------
    # Activity check
    # ------------------------------------------------------------------

    def is_low_activity(self, block_time: float) -> bool:
        """Check if this is a slow block suitable for dream consolidation.

        Args:
            block_time: Time since last block in seconds.

        Returns:
            True if block_time exceeds the slow threshold.
        """
        return block_time > self._slow_threshold

    # ------------------------------------------------------------------
    # Main consolidation
    # ------------------------------------------------------------------

    def consolidate(
        self,
        memories: List[dict],
        kg: Any = None,
        block_height: int = 0,
    ) -> ConsolidationResult:
        """Run dream consolidation on a set of memories.

        Args:
            memories: List of memory dicts with keys:
                'node_id', 'content', 'confidence', 'access_count',
                'source_block', 'domain'.
            kg: Optional knowledge graph for adding new connections.
            block_height: Current block height.

        Returns:
            ConsolidationResult with counts and discoveries.
        """
        start = time.time()
        self._total_consolidations += 1
        self._last_consolidation_block = block_height

        result = ConsolidationResult()

        if not memories:
            return result

        # Phase 1: Random reactivation + merge similar memories
        result.merged_count = self._merge_similar(memories)
        self._total_merged += result.merged_count

        # Phase 2: Strengthen frequently co-occurring patterns
        result.strengthened_count = self._strengthen_patterns(memories)
        self._total_strengthened += result.strengthened_count

        # Phase 3: Prune weak memories
        result.pruned_count = self._prune_weak(memories, block_height)
        self._total_pruned += result.pruned_count

        # Phase 4: Creative discovery
        creative = self._creative_discovery(memories, kg, block_height)
        result.new_connections = len(creative)
        result.creative_discoveries = creative
        self._total_creative += len(creative)

        result.duration_ms = (time.time() - start) * 1000
        return result

    # ------------------------------------------------------------------
    # Phase 1: Merge similar
    # ------------------------------------------------------------------

    def _merge_similar(self, memories: List[dict]) -> int:
        """Find and flag similar memories for merging.

        Groups memories by domain and merges those with high content overlap.
        """
        merged = 0
        # Group by domain
        by_domain: Dict[str, List[dict]] = {}
        for m in memories:
            d = m.get('domain', 'general')
            if d not in by_domain:
                by_domain[d] = []
            by_domain[d].append(m)

        for domain, group in by_domain.items():
            if len(group) < 2:
                continue
            # Compare pairs (limited to avoid O(n^2) explosion)
            for i in range(min(len(group) - 1, 50)):
                for j in range(i + 1, min(len(group), i + 10)):
                    sim = self._content_similarity(group[i], group[j])
                    if sim > 0.8:
                        # Merge: boost stronger memory, mark weaker for removal
                        if group[i].get('confidence', 0) >= group[j].get('confidence', 0):
                            group[i]['confidence'] = min(
                                group[i].get('confidence', 0.5) + 0.05, 1.0
                            )
                            group[j]['_merged'] = True
                        else:
                            group[j]['confidence'] = min(
                                group[j].get('confidence', 0.5) + 0.05, 1.0
                            )
                            group[i]['_merged'] = True
                        merged += 1
        return merged

    def _content_similarity(self, a: dict, b: dict) -> float:
        """Simple content similarity between two memory dicts."""
        a_str = str(a.get('content', ''))
        b_str = str(b.get('content', ''))
        if not a_str or not b_str:
            return 0.0
        # Character-level Jaccard
        sa = set(a_str.lower().split())
        sb = set(b_str.lower().split())
        union = len(sa | sb)
        if union == 0:
            return 0.0
        return len(sa & sb) / union

    # ------------------------------------------------------------------
    # Phase 2: Strengthen patterns
    # ------------------------------------------------------------------

    def _strengthen_patterns(self, memories: List[dict]) -> int:
        """Strengthen memories that frequently co-occur."""
        strengthened = 0
        # Track co-occurrence by domain pairs
        ids = [m.get('node_id', str(i)) for i, m in enumerate(memories)]
        # Random replay: pick random pairs
        n = len(memories)
        if n < 2:
            return 0

        rng = np.random.RandomState(int(time.time()) % 2**31)
        num_pairs = min(n * 2, 100)
        for _ in range(num_pairs):
            i, j = rng.choice(n, size=2, replace=False)
            key = (ids[i], ids[j]) if ids[i] < ids[j] else (ids[j], ids[i])
            self._cooccurrence[key] = self._cooccurrence.get(key, 0) + 1

            # Strengthen if co-occurrence is high
            if self._cooccurrence[key] >= 3:
                for idx in (i, j):
                    old_conf = memories[idx].get('confidence', 0.5)
                    memories[idx]['confidence'] = min(old_conf + 0.02, 1.0)
                    strengthened += 1

        # Prune co-occurrence dict if too large
        if len(self._cooccurrence) > self._max_cooccurrence:
            # Keep top half by count
            sorted_pairs = sorted(
                self._cooccurrence.items(), key=lambda x: x[1], reverse=True
            )
            self._cooccurrence = dict(sorted_pairs[:self._max_cooccurrence // 2])

        return strengthened

    # ------------------------------------------------------------------
    # Phase 3: Prune weak
    # ------------------------------------------------------------------

    def _prune_weak(self, memories: List[dict], block_height: int) -> int:
        """Mark low-confidence, old, low-access memories for pruning."""
        pruned = 0
        for m in memories:
            conf = m.get('confidence', 0.5)
            access = m.get('access_count', 0)
            age = block_height - m.get('source_block', block_height)
            if (conf < self._prune_conf_threshold
                    and age > self._prune_min_age
                    and access < 3):
                m['_pruned'] = True
                pruned += 1
        return pruned

    # ------------------------------------------------------------------
    # Phase 4: Creative discovery
    # ------------------------------------------------------------------

    def _creative_discovery(
        self,
        memories: List[dict],
        kg: Any,
        block_height: int,
    ) -> List[str]:
        """Randomly combine nodes to discover novel connections."""
        discoveries: List[str] = []
        if len(memories) < 3:
            return discoveries

        rng = np.random.RandomState(block_height % 2**31)
        n = len(memories)

        for _ in range(min(self._max_creative, n)):
            i, j = rng.choice(n, size=2, replace=False)
            m1 = memories[i]
            m2 = memories[j]
            d1 = m1.get('domain', 'general')
            d2 = m2.get('domain', 'general')
            # Cross-domain combinations are more interesting
            if d1 == d2:
                continue
            # Check if they share any content patterns
            sim = self._content_similarity(m1, m2)
            if 0.2 < sim < 0.7:
                # Partial overlap = interesting connection
                discovery = (
                    f"Novel link: {d1}/{m1.get('node_id', '?')} <-> "
                    f"{d2}/{m2.get('node_id', '?')} (overlap={sim:.2f})"
                )
                discoveries.append(discovery)

                # Add edge to KG if available
                if kg and hasattr(kg, 'add_edge'):
                    try:
                        n1 = m1.get('node_id')
                        n2 = m2.get('node_id')
                        if n1 and n2:
                            kg.add_edge(n1, n2, 'dream_discovered')
                    except Exception:
                        pass

        return discoveries[:10]  # Cap

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return dream consolidation statistics."""
        return {
            'total_consolidations': self._total_consolidations,
            'total_merged': self._total_merged,
            'total_strengthened': self._total_strengthened,
            'total_pruned': self._total_pruned,
            'total_creative_discoveries': self._total_creative,
            'cooccurrence_pairs': len(self._cooccurrence),
            'last_consolidation_block': self._last_consolidation_block,
        }
