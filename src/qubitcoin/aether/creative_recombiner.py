"""
#69: Creative Cross-Domain Recombination

Generates novel insights by combining concepts from different domains.
Identifies structural analogies, causal parallels, metric correlations,
and temporal patterns across domain boundaries.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Insight:
    """A creative insight combining concepts across domains."""
    description: str
    source_domains: List[str]
    novelty_score: float
    plausibility: float
    connection_type: str  # structural_analogy, causal_parallel, metric_correlation, temporal_pattern
    concept_a: dict = field(default_factory=dict)
    concept_b: dict = field(default_factory=dict)
    timestamp: float = 0.0
    insight_id: str = ''

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.insight_id:
            h = hashlib.sha256(self.description.encode()[:200]).hexdigest()[:12]
            self.insight_id = f"insight_{h}"

    def quality_score(self) -> float:
        return self.novelty_score * self.plausibility


_CONNECTION_TYPES = [
    'structural_analogy',
    'causal_parallel',
    'metric_correlation',
    'temporal_pattern',
]

# Domain distance matrix (higher = more distant = more novel recombination)
_DOMAIN_DISTANCE: Dict[Tuple[str, str], float] = {}


def _domain_novelty(domain_a: str, domain_b: str) -> float:
    """Novelty bonus based on how different two domains are."""
    if domain_a == domain_b:
        return 0.1
    key = tuple(sorted([domain_a, domain_b]))
    if key in _DOMAIN_DISTANCE:
        return _DOMAIN_DISTANCE[key]
    # Default: moderate novelty for cross-domain
    return 0.6


class CreativeRecombiner:
    """Generate insights by combining concepts across domains."""

    def __init__(
        self,
        min_plausibility: float = 0.15,
        max_insights: int = 2000,
    ) -> None:
        self._min_plausibility = min_plausibility
        self._max_insights = max_insights
        self._insights: List[Insight] = []
        self._total_attempts: int = 0
        self._total_generated: int = 0
        self._total_filtered: int = 0

        logger.info("CreativeRecombiner initialized")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def recombine(self, concept_a: dict, concept_b: dict) -> Optional[Insight]:
        """Attempt to recombine two concepts into a novel insight.

        Each concept dict should have at least:
            - 'domain': str
            - 'content' or 'description': str
            - 'metrics': dict (optional numeric features)
        """
        self._total_attempts += 1

        domain_a = concept_a.get('domain', 'general')
        domain_b = concept_b.get('domain', 'general')

        # Try each connection type and pick the best
        best_insight: Optional[Insight] = None
        best_quality = -1.0

        for conn_type in _CONNECTION_TYPES:
            candidate = self._try_connection(concept_a, concept_b, conn_type)
            if candidate and candidate.quality_score() > best_quality:
                best_quality = candidate.quality_score()
                best_insight = candidate

        if best_insight is None or best_insight.plausibility < self._min_plausibility:
            self._total_filtered += 1
            return None

        self._total_generated += 1
        self._insights.append(best_insight)
        if len(self._insights) > self._max_insights:
            self._insights = self._insights[-self._max_insights:]

        return best_insight

    def find_cross_domain_patterns(
        self, kg: Any, domain_a: str, domain_b: str, max_pairs: int = 20,
    ) -> List[Insight]:
        """Search the KG for cross-domain recombination opportunities."""
        if not kg or not hasattr(kg, 'nodes'):
            return []

        nodes_a: List[Any] = []
        nodes_b: List[Any] = []

        for node in kg.nodes.values():
            content = getattr(node, 'content', {})
            domain = content.get('domain', 'general') if isinstance(content, dict) else 'general'
            if domain == domain_a and len(nodes_a) < max_pairs:
                nodes_a.append(node)
            elif domain == domain_b and len(nodes_b) < max_pairs:
                nodes_b.append(node)

        insights: List[Insight] = []
        for na in nodes_a[:max_pairs]:
            for nb in nodes_b[:max_pairs]:
                concept_a = self._node_to_concept(na, domain_a)
                concept_b = self._node_to_concept(nb, domain_b)
                insight = self.recombine(concept_a, concept_b)
                if insight:
                    insights.append(insight)
                if len(insights) >= max_pairs:
                    break
            if len(insights) >= max_pairs:
                break

        return insights

    # ------------------------------------------------------------------
    # Connection type evaluators
    # ------------------------------------------------------------------

    def _try_connection(
        self, concept_a: dict, concept_b: dict, conn_type: str,
    ) -> Optional[Insight]:
        domain_a = concept_a.get('domain', 'general')
        domain_b = concept_b.get('domain', 'general')
        novelty = _domain_novelty(domain_a, domain_b)

        desc_a = str(concept_a.get('description', concept_a.get('content', '')))[:100]
        desc_b = str(concept_b.get('description', concept_b.get('content', '')))[:100]

        if conn_type == 'structural_analogy':
            plausibility = self._structural_similarity(concept_a, concept_b)
            desc = f"Structural analogy: '{desc_a}' ({domain_a}) mirrors '{desc_b}' ({domain_b})"

        elif conn_type == 'causal_parallel':
            plausibility = self._causal_similarity(concept_a, concept_b)
            desc = f"Causal parallel: mechanisms in {domain_a} parallel {domain_b}"

        elif conn_type == 'metric_correlation':
            plausibility = self._metric_correlation(concept_a, concept_b)
            desc = f"Metric correlation: numeric patterns shared between {domain_a} and {domain_b}"

        elif conn_type == 'temporal_pattern':
            plausibility = self._temporal_similarity(concept_a, concept_b)
            desc = f"Temporal pattern: evolution in {domain_a} echoes {domain_b}"

        else:
            return None

        if plausibility < 0.05:
            return None

        return Insight(
            description=desc,
            source_domains=[domain_a, domain_b],
            novelty_score=novelty,
            plausibility=plausibility,
            connection_type=conn_type,
            concept_a=concept_a,
            concept_b=concept_b,
        )

    def _structural_similarity(self, a: dict, b: dict) -> float:
        """Check if two concepts have similar structure (key overlap)."""
        keys_a = set(str(k) for k in a.keys())
        keys_b = set(str(k) for k in b.keys())
        if not keys_a or not keys_b:
            return 0.0
        overlap = len(keys_a & keys_b)
        union = len(keys_a | keys_b)
        return overlap / max(union, 1)

    def _causal_similarity(self, a: dict, b: dict) -> float:
        """Heuristic for causal parallel (shared cause-effect structure)."""
        # Check if both have similar typed fields
        type_a = str(a.get('type', '')).lower()
        type_b = str(b.get('type', '')).lower()
        if type_a and type_b and type_a == type_b:
            return 0.7
        # Check content overlap
        content_a = str(a.get('content', '')).lower().split()
        content_b = str(b.get('content', '')).lower().split()
        if content_a and content_b:
            overlap = len(set(content_a) & set(content_b))
            return min(0.8, overlap / max(len(set(content_a) | set(content_b)), 1))
        return 0.1

    def _metric_correlation(self, a: dict, b: dict) -> float:
        """Check if numeric metrics are correlated."""
        metrics_a = a.get('metrics', {})
        metrics_b = b.get('metrics', {})
        if not isinstance(metrics_a, dict) or not isinstance(metrics_b, dict):
            return 0.1

        shared_keys = set(metrics_a.keys()) & set(metrics_b.keys())
        if not shared_keys:
            return 0.1

        # Simple correlation check via cosine similarity of shared metric values
        vals_a = []
        vals_b = []
        for k in shared_keys:
            va = metrics_a.get(k)
            vb = metrics_b.get(k)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                vals_a.append(float(va))
                vals_b.append(float(vb))

        if len(vals_a) < 2:
            return 0.1

        arr_a = np.array(vals_a)
        arr_b = np.array(vals_b)
        norm_a = np.linalg.norm(arr_a)
        norm_b = np.linalg.norm(arr_b)
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 0.1
        cosine = float(np.dot(arr_a, arr_b) / (norm_a * norm_b))
        return max(0.0, cosine)

    def _temporal_similarity(self, a: dict, b: dict) -> float:
        """Check if concepts have similar temporal patterns."""
        ts_a = a.get('timestamp', a.get('block_height', 0))
        ts_b = b.get('timestamp', b.get('block_height', 0))
        if not ts_a or not ts_b:
            return 0.1
        # Closer in time = more likely temporal pattern
        diff = abs(float(ts_a) - float(ts_b))
        return max(0.1, 1.0 / (1.0 + diff * 0.001))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _node_to_concept(self, node: Any, domain: str) -> dict:
        content = getattr(node, 'content', {})
        if not isinstance(content, dict):
            content = {'content': str(content)}
        concept = dict(content)
        concept['domain'] = domain
        concept['confidence'] = getattr(node, 'confidence', 0.5)
        return concept

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        avg_quality = (
            float(np.mean([i.quality_score() for i in self._insights[-100:]]))
            if self._insights else 0.0
        )
        return {
            'total_attempts': self._total_attempts,
            'total_generated': self._total_generated,
            'total_filtered': self._total_filtered,
            'insights_stored': len(self._insights),
            'avg_quality_100': round(avg_quality, 4),
        }
