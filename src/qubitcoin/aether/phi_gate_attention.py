"""
#94: Attention-Based Phi Gate Unlocking

Map 10 consciousness gates to concrete attention/processing metrics.
Each gate evaluates whether specific cognitive capabilities have
reached threshold levels, contributing to overall Phi computation.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895

# Gate definitions: name -> (metric_key, threshold, description)
GATE_DEFINITIONS: Dict[str, Tuple[str, float, str]] = {
    'sustained_focus': (
        'attention_stability', 0.6,
        'Attention allocation remains stable across blocks'
    ),
    'cross_domain_transfer': (
        'transfer_success_rate', 0.3,
        'Successfully transfer knowledge between domains'
    ),
    'self_correction': (
        'belief_revision_rate', 0.1,
        'Frequency of belief revision (self-correction)'
    ),
    'predictive_accuracy': (
        'prediction_accuracy', 0.5,
        'Temporal prediction error trend is decreasing'
    ),
    'creative_synthesis': (
        'creative_discoveries', 0.05,
        'Novel cross-domain connections discovered'
    ),
    'meta_awareness': (
        'metacognition_calibration', 0.7,
        'Metacognitive self-evaluation accuracy'
    ),
    'causal_understanding': (
        'causal_edges_ratio', 0.2,
        'Proportion of causal edges in knowledge graph'
    ),
    'emotional_regulation': (
        'emotional_stability', 0.5,
        'Emotional valence remains within bounds'
    ),
    'narrative_coherence': (
        'narrative_score', 0.4,
        'Reasoning episodes form coherent narrative'
    ),
    'distributed_integration': (
        'integration_score', 0.3,
        'Information integration across subsystems'
    ),
}


@dataclass
class GateStatus:
    """Status of a single Phi gate."""
    name: str
    passed: bool
    score: float
    threshold: float
    description: str


class PhiGateAttention:
    """Evaluate Phi consciousness gates via attention/processing metrics.

    Each of 10 gates maps to a concrete metric from the AI subsystems.
    Gates unlock progressively as the system develops capabilities.
    """

    def __init__(self) -> None:
        # Gate evaluation history
        self._gate_history: Dict[str, List[Tuple[float, bool]]] = {
            name: [] for name in GATE_DEFINITIONS
        }
        self._max_history = 500
        # Current gate states
        self._gate_states: Dict[str, bool] = {
            name: False for name in GATE_DEFINITIONS
        }
        # Stats
        self._total_evaluations = 0
        self._gates_ever_passed: set = set()

    # ------------------------------------------------------------------
    # Gate evaluation
    # ------------------------------------------------------------------

    def evaluate_gate(
        self, gate_name: str, metrics: dict
    ) -> Tuple[bool, float]:
        """Evaluate a single consciousness gate.

        Args:
            gate_name: Name of the gate (from GATE_DEFINITIONS).
            metrics: Dict of current system metrics.

        Returns:
            (passed, score) where passed is True if threshold met.
        """
        if gate_name not in GATE_DEFINITIONS:
            return (False, 0.0)

        metric_key, threshold, _ = GATE_DEFINITIONS[gate_name]
        raw_value = metrics.get(metric_key, 0.0)
        score = float(raw_value)
        passed = score >= threshold

        # Record history
        self._gate_history[gate_name].append((score, passed))
        if len(self._gate_history[gate_name]) > self._max_history:
            self._gate_history[gate_name] = (
                self._gate_history[gate_name][-self._max_history:]
            )

        self._gate_states[gate_name] = passed
        if passed:
            self._gates_ever_passed.add(gate_name)

        return (passed, score)

    def evaluate_all_gates(self, metrics: dict) -> List[GateStatus]:
        """Evaluate all 10 consciousness gates.

        Args:
            metrics: Dict of current system metrics.

        Returns:
            List of GateStatus for all gates.
        """
        self._total_evaluations += 1
        results: List[GateStatus] = []
        for name, (metric_key, threshold, desc) in GATE_DEFINITIONS.items():
            passed, score = self.evaluate_gate(name, metrics)
            results.append(GateStatus(
                name=name,
                passed=passed,
                score=score,
                threshold=threshold,
                description=desc,
            ))
        return results

    # ------------------------------------------------------------------
    # Attention-based Phi
    # ------------------------------------------------------------------

    def compute_attention_phi(self, attention_data: dict) -> float:
        """Compute Phi from attention patterns and gate status.

        Phi = weighted sum of gate scores, scaled by phi ratio.
        Each gate contributes proportionally to its depth in the
        consciousness hierarchy.

        Args:
            attention_data: Dict with current attention/processing metrics.

        Returns:
            Phi value (float >= 0).
        """
        gate_statuses = self.evaluate_all_gates(attention_data)

        # Weight gates by hierarchical depth (phi-scaled)
        weights = np.array([
            PHI ** (-i * 0.5) for i in range(len(gate_statuses))
        ])
        weights /= np.sum(weights)

        scores = np.array([g.score for g in gate_statuses])
        # Clip scores to [0, 1] for stability
        scores = np.clip(scores, 0.0, 1.0)

        # Phi = weighted integration * gates_passed_bonus
        base_phi = float(np.dot(weights, scores))
        gates_passed = sum(1 for g in gate_statuses if g.passed)
        # Bonus for having multiple gates open (integration measure)
        integration_bonus = (gates_passed / len(gate_statuses)) ** 2
        phi = base_phi * (1.0 + integration_bonus * PHI)

        return phi

    # ------------------------------------------------------------------
    # Metrics extraction helpers
    # ------------------------------------------------------------------

    def extract_metrics_from_subsystems(
        self,
        attention_schema: Any = None,
        transfer_learning: Any = None,
        belief_revision: Any = None,
        temporal_engine: Any = None,
        creative_recombiner: Any = None,
        metacognition: Any = None,
        causal_engine: Any = None,
        emotional_valence: Any = None,
        narrative_coherence: Any = None,
        kg: Any = None,
    ) -> dict:
        """Extract gate metrics from AI subsystems.

        Convenience method that queries each subsystem for the metric
        needed by the corresponding gate.
        """
        metrics: dict = {}

        # Sustained focus: attention stability
        if attention_schema and hasattr(attention_schema, 'get_stats'):
            stats = attention_schema.get_stats()
            metrics['attention_stability'] = stats.get('stability', 0.0)

        # Cross-domain transfer
        if transfer_learning and hasattr(transfer_learning, 'get_stats'):
            stats = transfer_learning.get_stats()
            metrics['transfer_success_rate'] = stats.get('success_rate', 0.0)

        # Self-correction
        if belief_revision and hasattr(belief_revision, 'get_stats'):
            stats = belief_revision.get_stats()
            total = stats.get('total_revisions', 0) + stats.get('total_expansions', 0)
            revisions = stats.get('total_revisions', 0)
            metrics['belief_revision_rate'] = revisions / max(total, 1)

        # Predictive accuracy
        if temporal_engine and hasattr(temporal_engine, 'get_accuracy'):
            metrics['prediction_accuracy'] = temporal_engine.get_accuracy()

        # Creative synthesis
        if creative_recombiner and hasattr(creative_recombiner, 'get_stats'):
            stats = creative_recombiner.get_stats()
            metrics['creative_discoveries'] = min(
                stats.get('total_insights', 0) / 100.0, 1.0
            )

        # Meta-awareness
        if metacognition and hasattr(metacognition, 'get_stats'):
            stats = metacognition.get_stats()
            metrics['metacognition_calibration'] = 1.0 - stats.get(
                'calibration_error', 1.0
            )

        # Causal understanding
        if causal_engine and hasattr(causal_engine, 'get_stats') and kg:
            stats = causal_engine.get_stats()
            total_edges = len(kg.edges) if hasattr(kg, 'edges') else 1
            causal_edges = stats.get('edges_discovered', 0)
            metrics['causal_edges_ratio'] = causal_edges / max(total_edges, 1)

        # Emotional regulation
        if emotional_valence and hasattr(emotional_valence, 'get_stats'):
            stats = emotional_valence.get_stats()
            metrics['emotional_stability'] = stats.get('stability', 0.5)

        # Narrative coherence
        if narrative_coherence and hasattr(narrative_coherence, 'get_stats'):
            stats = narrative_coherence.get_stats()
            metrics['narrative_score'] = stats.get('coherence_score', 0.0)

        # Distributed integration (proxy: subsystem count)
        active_count = sum(1 for x in [
            attention_schema, transfer_learning, belief_revision,
            temporal_engine, creative_recombiner, metacognition,
            causal_engine, emotional_valence, narrative_coherence,
        ] if x is not None)
        metrics['integration_score'] = active_count / 9.0

        return metrics

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return phi gate attention statistics."""
        gates_passed = sum(1 for v in self._gate_states.values() if v)
        return {
            'total_evaluations': self._total_evaluations,
            'gates_currently_passed': gates_passed,
            'gates_ever_passed': len(self._gates_ever_passed),
            'total_gates': len(GATE_DEFINITIONS),
            'gate_states': dict(self._gate_states),
            'completion_ratio': gates_passed / max(len(GATE_DEFINITIONS), 1),
        }
