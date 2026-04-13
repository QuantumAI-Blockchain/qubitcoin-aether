"""
Autonomous Curiosity Engine for Aether Tree AGI.

Provides intrinsic motivation by tracking prediction errors per domain
and suggesting exploration goals based on knowledge gaps.  Higher
prediction error signals more interesting (less understood) territory,
driving the system to explore what it does not yet know.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph
    from .temporal_reasoner import TemporalReasoner

logger = get_logger(__name__)

# Rust acceleration (standalone engine for compute-heavy paths)
_RUST_AVAILABLE = False
try:
    from .rust_bridge import RUST_AVAILABLE, RustCuriosityEngine
    _RUST_AVAILABLE = RUST_AVAILABLE and RustCuriosityEngine is not None
except ImportError:
    pass

_ROLLING_WINDOW = 100


class CuriosityEngine:
    """Drives autonomous exploration via prediction-error curiosity."""

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        temporal_reasoner: Optional[TemporalReasoner] = None,
    ) -> None:
        self._kg = knowledge_graph
        self._temporal = temporal_reasoner

        # Rust acceleration: delegate all compute to Rust engine
        self._rust = None
        if _RUST_AVAILABLE and RustCuriosityEngine is not None:
            try:
                self._rust = RustCuriosityEngine()
                logger.info("CuriosityEngine: Rust acceleration ACTIVE")
            except Exception as exc:
                logger.warning("CuriosityEngine: Rust init failed (%s), using Python", exc)

        # Python fallback state (only used when Rust is unavailable)
        if self._rust is None:
            self._lock = threading.Lock()
            self.prediction_errors: dict[str, list[float]] = defaultdict(list)
            self.exploration_history: list[tuple[str, str, int]] = []
        else:
            self._lock = threading.Lock()  # still needed for KG access
            self.prediction_errors = defaultdict(list)
            self.exploration_history = []

        logger.info("CuriosityEngine initialized (window=%d, rust=%s)", _ROLLING_WINDOW, self._rust is not None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_curiosity_scores(self) -> dict[str, float]:
        """Return curiosity score per domain (mean prediction error)."""
        if self._rust is not None:
            try:
                return self._rust.compute_curiosity_scores()
            except Exception as exc:
                logger.debug("Rust compute_curiosity_scores failed: %s", exc)
        with self._lock:
            scores: dict[str, float] = {}
            for domain, errors in self.prediction_errors.items():
                if errors:
                    scores[domain] = sum(errors) / len(errors)
            return scores

    def suggest_exploration_goal(self) -> Optional[dict]:
        """Pick the highest-curiosity domain and generate a question.

        Returns:
            Dict with ``domain``, ``curiosity_score``, and ``question``
            keys, or ``None`` when no prediction data exists yet.
        """
        if self._rust is not None:
            try:
                result = self._rust.suggest_exploration_goal()
                if result is not None:
                    # Override with KG-aware question generation
                    result["question"] = self._generate_exploration_question(result["domain"])
                return result
            except Exception as exc:
                logger.debug("Rust suggest_exploration_goal failed: %s", exc)

        scores = self.compute_curiosity_scores()
        if not scores:
            return None

        best_domain = max(scores, key=scores.__getitem__)  # type: ignore[arg-type]
        question = self._generate_exploration_question(best_domain)

        logger.info(
            "Curiosity goal: domain=%s score=%.4f question='%s'",
            best_domain,
            scores[best_domain],
            question,
        )
        return {
            "domain": best_domain,
            "curiosity_score": scores[best_domain],
            "question": question,
        }

    def record_prediction_outcome(
        self,
        domain: str,
        predicted: float,
        actual: float,
        topic: str,
    ) -> None:
        """Record the absolute error of a prediction for *domain*."""
        if self._rust is not None:
            try:
                self._rust.record_prediction_outcome(domain, predicted, actual, topic)
                return
            except Exception as exc:
                logger.debug("Rust record_prediction_outcome failed: %s", exc)
        error = abs(predicted - actual)
        with self._lock:
            buf = self.prediction_errors[domain]
            buf.append(error)
            if len(buf) > _ROLLING_WINDOW:
                del buf[: len(buf) - _ROLLING_WINDOW]
        logger.debug(
            "Prediction outcome: domain=%s topic=%s error=%.4f",
            domain,
            topic,
            error,
        )

    def record_discovery(
        self,
        domain: str,
        topic: str,
        block_height: int,
    ) -> None:
        """Log a curiosity-driven discovery."""
        if self._rust is not None:
            try:
                self._rust.record_discovery(domain, topic, block_height)
                return
            except Exception as exc:
                logger.debug("Rust record_discovery failed: %s", exc)
        with self._lock:
            self.exploration_history.append((domain, topic, block_height))
        logger.info(
            "Curiosity discovery: domain=%s topic=%s block=%d",
            domain,
            topic,
            block_height,
        )

    def get_curiosity_stats(self) -> dict:
        """Return a summary dict of curiosity state."""
        if self._rust is not None:
            try:
                return self._rust.get_curiosity_stats()
            except Exception as exc:
                logger.debug("Rust get_curiosity_stats failed: %s", exc)
        scores = self.compute_curiosity_scores()
        sorted_domains = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        with self._lock:
            history_len = len(self.exploration_history)
        return {
            "curiosity_scores": scores,
            "top_interests": [d for d, _ in sorted_domains[:5]],
            "discoveries_count": history_len,
            "domains_tracked": len(scores),
        }

    @property
    def discoveries_count(self) -> int:
        """Total curiosity-driven discoveries (used by gate 8 checks)."""
        if self._rust is not None:
            try:
                return self._rust.discoveries_count
            except Exception as exc:
                logger.debug("Rust discoveries_count failed: %s", exc)
        with self._lock:
            return len(self.exploration_history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_exploration_question(self, domain: str) -> str:
        """Create a question targeting *domain*'s weakest prediction area.

        Scans the knowledge graph for nodes in *domain*, picks the one
        with the lowest confidence, and formulates a question around it.
        """
        weak_nodes: list[tuple[float, str]] = []
        for node in self._kg.nodes.values():
            if (node.domain or "general") != domain:
                continue
            text = ""
            if isinstance(node.content, dict):
                text = node.content.get("text", "")
            elif isinstance(node.content, str):
                text = node.content
            if text:
                weak_nodes.append((node.confidence, text))

        if not weak_nodes:
            return f"What are the foundational principles of {domain}?"

        # Pick the lowest-confidence node as the weak spot
        weak_nodes.sort(key=lambda t: t[0])
        snippet = weak_nodes[0][1][:120].strip()
        return (
            f"Why is the following claim in {domain} uncertain, "
            f'and what evidence would resolve it? "{snippet}"'
        )
