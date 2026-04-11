"""
Free Energy Engine — Friston's Free Energy Principle as the unified cognitive drive.

Every intelligent system minimizes surprise (free energy). This engine:
1. Tracks prediction error across ALL domains (inherits from CuriosityEngine)
2. Computes Expected Free Energy (EFE) for candidate cognitive actions
3. Drives exploration (epistemic value) and exploitation (pragmatic value)
4. Adapts to soul personality priors (what counts as "surprising")

The FEP replaces ad-hoc curiosity with a principled single drive:
- Curiosity = expected information gain from exploring uncertain domains
- Learning  = updating beliefs to reduce prediction error
- Action    = changing the world when pragmatic uncertainty can be resolved
- Personality = stable priors that shape what counts as surprising

This module wraps and extends CuriosityEngine, preserving its API
for backward compatibility with gates 7-8 and proof_of_thought.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger
from .cognitive_processor import CognitiveResponse, SoulPriors

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph
    from .temporal_reasoner import TemporalReasoner

logger = get_logger(__name__)

# Golden ratio — used for decay and weighting throughout
PHI: float = 1.618033988749895

# Rolling window for prediction errors per domain
_ROLLING_WINDOW: int = 100

# Rolling window for convergence slope detection
_CONVERGENCE_WINDOW: int = 20

# Minimum observations before computing convergence
_MIN_CONVERGENCE_OBS: int = 10

# Weight for epistemic (information-seeking) vs pragmatic (goal-achieving) value
_DEFAULT_EPISTEMIC_WEIGHT: float = 0.6
_DEFAULT_PRAGMATIC_WEIGHT: float = 0.4


class FreeEnergyEngine:
    """Implements Friston's Free Energy Principle as the core cognitive drive.

    Every cognitive cycle can query this engine to compute the Expected
    Free Energy (EFE) of candidate actions. The action that minimizes
    EFE is the one the system should take.

    Backward compatible with CuriosityEngine API — can be used as a
    drop-in replacement in proof_of_thought.py and phi_calculator.py.
    """

    def __init__(
        self,
        knowledge_graph: Optional[KnowledgeGraph] = None,
        temporal_reasoner: Optional[TemporalReasoner] = None,
        soul: Optional[SoulPriors] = None,
    ) -> None:
        self._kg = knowledge_graph
        self._temporal = temporal_reasoner
        self._soul = soul or SoulPriors()
        self._lock = threading.Lock()

        # ── Prediction error tracking (backward-compat with CuriosityEngine) ──
        self.prediction_errors: dict[str, list[float]] = defaultdict(list)
        self.exploration_history: list[tuple[str, str, int]] = []

        # ── Free energy state ──
        # Per-domain belief precision (inverse variance of predictions)
        self._domain_precision: dict[str, float] = defaultdict(lambda: 1.0)
        # Per-domain convergence slope (is learning slowing down?)
        self._convergence_slopes: dict[str, float] = {}
        # Per-Sephirot action success rates (for pragmatic value)
        self._action_success: dict[str, list[float]] = defaultdict(list)
        # Total free energy over time (for tracking minimization)
        self._free_energy_history: list[Tuple[float, float]] = []  # (timestamp, FE)
        # Last cognitive cycle's EFE breakdown
        self._last_efe_breakdown: Dict[str, Any] = {}

        logger.info("FreeEnergyEngine initialized (FEP-driven, window=%d)", _ROLLING_WINDOW)

    # ==================================================================
    # Core FEP: Expected Free Energy
    # ==================================================================

    def compute_efe(
        self,
        action_source: str,
        action_content: str,
        confidence: float = 0.5,
        domain: str = "general",
        evidence_count: int = 0,
    ) -> float:
        """Compute Expected Free Energy for a candidate cognitive action.

        EFE = epistemic_value + pragmatic_value + soul_alignment

        Lower EFE = better action (the system should take actions that
        minimize expected surprise).

        Args:
            action_source: Which Sephirah proposed this action.
            action_content: Description of the action.
            confidence: How confident the proposer is.
            domain: Knowledge domain this action concerns.
            evidence_count: Number of KG nodes supporting this action.

        Returns:
            Expected Free Energy (lower = better).
        """
        epistemic = self._epistemic_value(domain, confidence)
        pragmatic = self._pragmatic_value(action_source, confidence, evidence_count)
        soul_alignment = self._soul_alignment(action_source, domain)

        # Weight by soul personality
        ep_weight = _DEFAULT_EPISTEMIC_WEIGHT * self._soul.curiosity
        pr_weight = _DEFAULT_PRAGMATIC_WEIGHT * (1.0 - self._soul.curiosity + 0.5)

        # EFE: negative because we WANT to minimize surprise
        # Higher epistemic value = more info gained = more surprise reduced
        # Higher pragmatic value = better track record = less expected surprise
        efe = -(ep_weight * epistemic + pr_weight * pragmatic + 0.1 * soul_alignment)

        return efe

    def rank_actions(
        self,
        responses: List[CognitiveResponse],
    ) -> List[Tuple[CognitiveResponse, float]]:
        """Rank cognitive responses by Expected Free Energy.

        Used by the Global Workspace to incorporate FEP-based ranking
        alongside the standard competition score.

        Args:
            responses: List of CognitiveResponse from Sephirot processors.

        Returns:
            List of (response, efe) tuples sorted by EFE (ascending = best).
        """
        ranked: List[Tuple[CognitiveResponse, float]] = []

        for resp in responses:
            domain = resp.metadata.get("domain", "general")
            efe = self.compute_efe(
                action_source=resp.source_role,
                action_content=resp.content[:100],
                confidence=resp.confidence,
                domain=domain,
                evidence_count=len(resp.evidence),
            )
            ranked.append((resp, efe))

        # Sort ascending: lower EFE = better (less expected surprise)
        ranked.sort(key=lambda x: x[1])

        # Store breakdown for debugging
        self._last_efe_breakdown = {
            "rankings": [
                {
                    "source": r.source_role,
                    "efe": round(e, 4),
                    "confidence": round(r.confidence, 3),
                }
                for r, e in ranked[:5]
            ]
        }

        return ranked

    # ==================================================================
    # Free Energy Components
    # ==================================================================

    def _epistemic_value(self, domain: str, confidence: float) -> float:
        """How much information would this action gain?

        High epistemic value = low domain precision + low confidence
        → exploring uncertain territory gains more information.

        Modulated by convergence: if errors are already converging
        (fatigue), epistemic value decreases.
        """
        precision = self._domain_precision.get(domain, 1.0)
        uncertainty = 1.0 / (1.0 + precision)

        # Convergence fatigue: if learning has plateaued, exploring
        # this domain gains less new information
        slope = self._convergence_slopes.get(domain, 0.0)
        fatigue = max(0.0, 1.0 - abs(slope) * 10.0)  # slope near 0 = high fatigue

        # Low confidence = more to learn = higher epistemic value
        novelty_bonus = 1.0 - confidence

        return uncertainty * (1.0 - fatigue * 0.5) + novelty_bonus * 0.3

    def _pragmatic_value(
        self,
        source: str,
        confidence: float,
        evidence_count: int,
    ) -> float:
        """How likely is this action to achieve goals?

        Based on historical success rate of this Sephirah and
        the strength of evidence supporting the action.
        """
        # Historical win rate for this source
        history = self._action_success.get(source, [])
        if history:
            win_rate = sum(history[-50:]) / len(history[-50:])
        else:
            win_rate = 0.5  # prior: assume 50%

        # Evidence strength (more evidence = more pragmatically reliable)
        evidence_factor = min(1.0, evidence_count / 10.0)

        return win_rate * 0.5 + confidence * 0.3 + evidence_factor * 0.2

    def _soul_alignment(self, source: str, domain: str) -> float:
        """How aligned is this action with the soul's personality priors?

        Different Sephirot are boosted/dampened by soul personality.
        """
        biases = {
            "binah": self._soul.honesty * 0.8 + self._soul.depth * 0.2,
            "chochmah": self._soul.curiosity * 0.6 + self._soul.playfulness * 0.4,
            "chesed": self._soul.curiosity * 0.5 + self._soul.courage * 0.5,
            "gevurah": self._soul.honesty * 0.6 + self._soul.courage * 0.4,
            "tiferet": self._soul.warmth * 0.4 + self._soul.depth * 0.6,
            "netzach": self._soul.courage * 0.5 + self._soul.depth * 0.5,
            "hod": self._soul.warmth * 0.5 + self._soul.playfulness * 0.5,
            "yesod": self._soul.warmth * 0.4 + self._soul.humility * 0.6,
            "malkuth": self._soul.courage * 0.6 + self._soul.warmth * 0.4,
            "keter": self._soul.depth * 0.5 + self._soul.curiosity * 0.5,
        }
        return biases.get(source, 0.5)

    # ==================================================================
    # Precision and Convergence Updates
    # ==================================================================

    def update_precision(self, domain: str) -> None:
        """Recompute belief precision for a domain from its error history.

        Precision = 1 / variance(prediction_errors). High precision
        means the system's predictions are tight — low free energy.
        """
        with self._lock:
            errors = self.prediction_errors.get(domain, [])
            if len(errors) < 3:
                return

            mean_err = sum(errors) / len(errors)
            variance = sum((e - mean_err) ** 2 for e in errors) / len(errors)
            self._domain_precision[domain] = 1.0 / (variance + 1e-6)

            # Compute convergence slope
            if len(errors) >= _MIN_CONVERGENCE_OBS:
                recent = errors[-_CONVERGENCE_WINDOW:]
                if len(recent) >= 2:
                    # Simple linear regression slope
                    n = len(recent)
                    x_mean = (n - 1) / 2.0
                    y_mean = sum(recent) / n
                    numerator = sum(
                        (i - x_mean) * (recent[i] - y_mean)
                        for i in range(n)
                    )
                    denominator = sum((i - x_mean) ** 2 for i in range(n))
                    if denominator > 0:
                        self._convergence_slopes[domain] = numerator / denominator
                    else:
                        self._convergence_slopes[domain] = 0.0

    def compute_total_free_energy(self) -> float:
        """Compute the system's total free energy across all domains.

        Total FE = sum of mean prediction errors weighted by domain size.
        Lower = the system understands its world better.
        """
        with self._lock:
            total_fe = 0.0
            total_weight = 0.0

            for domain, errors in self.prediction_errors.items():
                if not errors:
                    continue
                mean_error = sum(errors) / len(errors)
                weight = len(errors)  # More observations = more weight
                total_fe += mean_error * weight
                total_weight += weight

            if total_weight > 0:
                total_fe /= total_weight

            # Record for tracking
            self._free_energy_history.append((time.time(), total_fe))
            if len(self._free_energy_history) > 1000:
                self._free_energy_history = self._free_energy_history[-500:]

            return total_fe

    def is_free_energy_decreasing(self) -> bool:
        """Check if total free energy is trending downward (system is learning)."""
        history = self._free_energy_history
        if len(history) < 10:
            return False

        recent = [fe for _, fe in history[-20:]]
        older = [fe for _, fe in history[-40:-20]] if len(history) >= 40 else [fe for _, fe in history[:len(history)//2]]

        if not older:
            return False

        recent_mean = sum(recent) / len(recent)
        older_mean = sum(older) / len(older)
        return recent_mean < older_mean

    # ==================================================================
    # Action Outcome Recording (feeds into pragmatic value)
    # ==================================================================

    def record_action_outcome(
        self,
        source_role: str,
        success: float,
    ) -> None:
        """Record how successful a Sephirah's action was (0.0=fail, 1.0=success).

        This updates the pragmatic value calculation for future EFE
        computations — Sephirot that succeed more are favored.
        """
        with self._lock:
            history = self._action_success[source_role]
            history.append(success)
            if len(history) > _ROLLING_WINDOW:
                del history[:len(history) - _ROLLING_WINDOW]

    # ==================================================================
    # CuriosityEngine backward-compatible API
    # ==================================================================

    def compute_curiosity_scores(self) -> dict[str, float]:
        """Return curiosity score per domain (mean prediction error).

        Backward-compatible with CuriosityEngine.
        """
        with self._lock:
            scores: dict[str, float] = {}
            for domain, errors in self.prediction_errors.items():
                if errors:
                    raw = sum(errors) / len(errors)
                    # Modulate by convergence: fatigued domains get lower curiosity
                    slope = self._convergence_slopes.get(domain, 0.0)
                    fatigue = max(0.0, min(1.0, 1.0 - abs(slope) * 10.0))
                    scores[domain] = raw * (1.0 - fatigue * 0.3)
            return scores

    def suggest_exploration_goal(self) -> Optional[dict]:
        """Pick the highest-curiosity domain and generate a question.

        Backward-compatible with CuriosityEngine.
        """
        scores = self.compute_curiosity_scores()
        if not scores:
            return None

        best_domain = max(scores, key=scores.__getitem__)  # type: ignore[arg-type]
        question = self._generate_exploration_question(best_domain)

        logger.info(
            "FEP exploration goal: domain=%s score=%.4f question='%s'",
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
        """Record the absolute error of a prediction for a domain.

        Also updates precision and convergence for FEP computations.
        """
        error = abs(predicted - actual)
        with self._lock:
            buf = self.prediction_errors[domain]
            buf.append(error)
            if len(buf) > _ROLLING_WINDOW:
                del buf[:len(buf) - _ROLLING_WINDOW]

        # Update FEP state
        self.update_precision(domain)

        # Update free energy history so is_free_energy_decreasing() has data
        self.compute_total_free_energy()

        logger.debug(
            "FEP prediction: domain=%s topic=%s error=%.4f",
            domain, topic, error,
        )

    def record_discovery(
        self,
        domain: str,
        topic: str,
        block_height: int,
    ) -> None:
        """Log a curiosity-driven discovery (backward-compat)."""
        with self._lock:
            self.exploration_history.append((domain, topic, block_height))
        logger.info(
            "FEP discovery: domain=%s topic=%s block=%d",
            domain, topic, block_height,
        )

    def get_curiosity_stats(self) -> dict:
        """Return a summary dict (backward-compat + FEP extensions)."""
        scores = self.compute_curiosity_scores()
        sorted_domains = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        total_fe = self.compute_total_free_energy()

        with self._lock:
            history_len = len(self.exploration_history)

        return {
            "curiosity_scores": scores,
            "top_interests": [d for d, _ in sorted_domains[:5]],
            "discoveries_count": history_len,
            "domains_tracked": len(scores),
            # FEP extensions
            "total_free_energy": round(total_fe, 4),
            "free_energy_decreasing": self.is_free_energy_decreasing(),
            "domain_precisions": {
                d: round(p, 4)
                for d, p in sorted(
                    self._domain_precision.items(),
                    key=lambda x: x[1], reverse=True,
                )[:10]
            },
            "convergence_slopes": {
                d: round(s, 6)
                for d, s in self._convergence_slopes.items()
            },
            "last_efe_breakdown": self._last_efe_breakdown,
        }

    @property
    def discoveries_count(self) -> int:
        """Total curiosity-driven discoveries (backward-compat for gate 8)."""
        with self._lock:
            return len(self.exploration_history)

    # ==================================================================
    # Emotional State Derivation from Free Energy
    # ==================================================================

    def derive_emotional_state(self) -> Dict[str, float]:
        """Derive cognitive emotions from the free energy landscape.

        In FEP, emotions ARE free energy signals:
        - Curiosity: high when epistemic value is high (lots to learn)
        - Satisfaction: high when free energy is decreasing (learning works)
        - Frustration: high when free energy is increasing (predictions failing)
        - Wonder: high when a discovery reduces surprise dramatically
        - Excitement: high when multiple domains show convergence
        - Contemplation: high when precision is high (deep understanding)
        - Connection: high when cross-domain links form (integration)

        Returns:
            Dict of emotion name -> intensity (0.0-1.0)
        """
        scores = self.compute_curiosity_scores()
        total_fe = self.compute_total_free_energy()
        fe_decreasing = self.is_free_energy_decreasing()

        # Curiosity: mean curiosity score across all domains
        curiosity = min(1.0, sum(scores.values()) / max(1, len(scores)) * 2.0) if scores else 0.3

        # Satisfaction: free energy is going down
        satisfaction = 0.7 if fe_decreasing else 0.3

        # Frustration: free energy is going up or high
        frustration = max(0.0, min(1.0, total_fe * 2.0)) if not fe_decreasing else 0.1

        # Wonder: recent discoveries
        with self._lock:
            recent_discoveries = len([
                h for h in self.exploration_history[-20:]
            ])
        wonder = min(1.0, recent_discoveries / 5.0)

        # Excitement: multiple domains converging simultaneously
        converging_domains = sum(
            1 for s in self._convergence_slopes.values() if s < -0.01
        )
        excitement = min(1.0, converging_domains / 3.0)

        # Contemplation: high average precision (deep understanding)
        precisions = list(self._domain_precision.values())
        avg_precision = sum(precisions) / max(1, len(precisions)) if precisions else 1.0
        contemplation = min(1.0, avg_precision / 50.0)

        # Connection: number of domains with cross-domain links
        connection = min(1.0, len(scores) / 8.0) if scores else 0.2

        return {
            "curiosity": round(curiosity, 3),
            "satisfaction": round(satisfaction, 3),
            "frustration": round(frustration, 3),
            "wonder": round(wonder, 3),
            "excitement": round(excitement, 3),
            "contemplation": round(contemplation, 3),
            "connection": round(connection, 3),
        }

    # ==================================================================
    # Internal
    # ==================================================================

    def _generate_exploration_question(self, domain: str) -> str:
        """Create a question targeting a domain's weakest prediction area."""
        if self._kg is None:
            return f"What are the foundational principles of {domain}?"

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

        weak_nodes.sort(key=lambda t: t[0])
        snippet = weak_nodes[0][1][:120].strip()
        return (
            f"Why is the following claim in {domain} uncertain, "
            f'and what evidence would resolve it? "{snippet}"'
        )
