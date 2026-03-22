"""
#72: Explanation Generation (Human-Readable)

Generates human-readable explanations of reasoning chains, predictions,
and decisions.  Uses templates with confidence-calibrated language.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Confidence language mapping
# ---------------------------------------------------------------------------
_CONFIDENCE_LANGUAGE = {
    'high': "I'm confident that",       # >0.8
    'medium': "It seems likely that",    # 0.5-0.8
    'low': "I'm uncertain, but",         # <0.5
}

_SIMPLIFICATION_LEVELS = ['technical', 'general', 'simple']


def _confidence_phrase(confidence: float) -> str:
    if confidence > 0.8:
        return _CONFIDENCE_LANGUAGE['high']
    elif confidence > 0.5:
        return _CONFIDENCE_LANGUAGE['medium']
    else:
        return _CONFIDENCE_LANGUAGE['low']


class Explainer:
    """Generate human-readable explanations of AGI reasoning."""

    def __init__(self) -> None:
        self._total_explanations: int = 0
        self._total_simplifications: int = 0
        self._total_predictions_explained: int = 0
        self._total_decisions_explained: int = 0

        logger.info("Explainer initialized")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def explain_reasoning(self, chain: List[dict]) -> str:
        """Generate a natural-language explanation of a reasoning chain.

        Each dict in the chain should have:
            - 'step_type': str
            - 'premise': str
            - 'conclusion': str
            - 'confidence': float
            - 'inference_type': str (optional)
        """
        self._total_explanations += 1

        if not chain:
            return "No reasoning steps were available to explain."

        parts: List[str] = []
        for i, step in enumerate(chain):
            step_type = step.get('step_type', 'step')
            premise = step.get('premise', '')[:200]
            conclusion = step.get('conclusion', '')[:200]
            confidence = float(step.get('confidence', 0.5))
            inference = step.get('inference_type', '')

            conf_phrase = _confidence_phrase(confidence)

            if step_type == 'observe':
                parts.append(f"First, I observed: {conclusion}")
            elif step_type == 'hypothesize':
                parts.append(f"Based on this, I hypothesized: {conclusion}")
            elif step_type == 'deduce':
                inf_label = f" ({inference})" if inference else ""
                parts.append(
                    f"Through {inference or 'logical'} reasoning{inf_label}, "
                    f"{conf_phrase} {conclusion}"
                )
            elif step_type == 'verify':
                if confidence > 0.5:
                    parts.append(f"This was verified with {confidence:.0%} confidence.")
                else:
                    parts.append(f"Verification was partial ({confidence:.0%} confidence).")
            elif step_type == 'conclude':
                parts.append(f"In conclusion: {conclusion}")
            else:
                parts.append(f"Step {i + 1} ({step_type}): {conclusion}")

        return " ".join(parts)

    def explain_prediction(self, prediction: dict) -> str:
        """Explain why a particular prediction was made.

        The prediction dict should have:
            - 'prediction': str or value
            - 'confidence': float
            - 'evidence': list of str (supporting facts)
            - 'method': str (optional — how it was derived)
        """
        self._total_predictions_explained += 1

        pred_value = prediction.get('prediction', 'unknown')
        confidence = float(prediction.get('confidence', 0.5))
        evidence = prediction.get('evidence', [])
        method = prediction.get('method', 'analysis')

        conf_phrase = _confidence_phrase(confidence)
        evidence_str = ""
        if evidence:
            top_evidence = evidence[:3]
            evidence_str = " This is supported by: " + "; ".join(str(e)[:100] for e in top_evidence) + "."

        return (
            f"{conf_phrase} the prediction is '{pred_value}' "
            f"(confidence: {confidence:.1%}), derived via {method}.{evidence_str}"
        )

    def explain_decision(
        self,
        decision: str,
        alternatives: List[str],
        scores: List[float],
    ) -> str:
        """Explain why a decision was chosen over alternatives.

        Args:
            decision: The chosen option.
            alternatives: All options considered.
            scores: Score for each alternative.
        """
        self._total_decisions_explained += 1

        if not alternatives or not scores:
            return f"The decision '{decision}' was made with no alternatives considered."

        # Find winning score
        best_idx = int(np.argmax(scores))
        best_score = scores[best_idx]
        margin = best_score - (sorted(scores, reverse=True)[1] if len(scores) > 1 else 0)

        # Build comparison
        comparison_parts: List[str] = []
        for alt, score in zip(alternatives, scores):
            if alt == decision:
                continue
            comparison_parts.append(f"'{alt}' (score: {score:.3f})")

        comparison = ", ".join(comparison_parts[:3]) if comparison_parts else "no other options"

        conf_phrase = _confidence_phrase(best_score)
        return (
            f"{conf_phrase} '{decision}' is the best choice "
            f"(score: {best_score:.3f}, margin: {margin:.3f}). "
            f"Alternatives considered: {comparison}."
        )

    def simplify(self, explanation: str, target_level: str = "general") -> str:
        """Adjust explanation complexity for the target audience.

        Levels:
            - 'technical': full detail
            - 'general': moderate simplification
            - 'simple': maximum simplification
        """
        self._total_simplifications += 1

        if target_level == 'technical':
            return explanation

        if target_level == 'simple':
            # Remove parentheticals, reduce to core message
            text = re.sub(r'\([^)]*\)', '', explanation)
            # Remove confidence percentages
            text = re.sub(r'\d+\.?\d*%', '', text)
            # Shorten to first two sentences
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            return '. '.join(sentences[:2]) + '.' if sentences else explanation

        # 'general' level: remove technical parentheticals but keep percentages
        text = re.sub(r'\((?:deductive|inductive|abductive|inference)[^)]*\)', '', explanation)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        return {
            'total_explanations': self._total_explanations,
            'total_predictions_explained': self._total_predictions_explained,
            'total_decisions_explained': self._total_decisions_explained,
            'total_simplifications': self._total_simplifications,
        }
