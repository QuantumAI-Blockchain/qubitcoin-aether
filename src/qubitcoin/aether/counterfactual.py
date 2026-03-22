"""
#91: Counterfactual Reasoning over Knowledge Graph

"What if" reasoning: simulate alternative realities by intervening on
variables in a structural causal model built from the knowledge graph.
Computes necessity and sufficiency of causes.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CounterfactualResult:
    """Result of a counterfactual query."""
    variable: str
    original_value: float
    counterfactual_value: float
    affected_variables: Dict[str, Tuple[float, float]]  # var -> (original, new)
    differences: List[str]
    timestamp: float = field(default_factory=time.time)


class CounterfactualReasoner:
    """Counterfactual reasoning engine for "what if" scenarios.

    Uses structural causal models to:
      - Simulate interventions (do-calculus style)
      - Compare actual vs counterfactual worlds
      - Compute necessity and sufficiency of causes
    """

    def __init__(self) -> None:
        # Learned causal strengths: (cause, effect) -> weight
        self._causal_weights: Dict[Tuple[str, str], float] = {}
        # Observation history for baseline estimation
        self._observations: List[Dict[str, float]] = []
        self._max_observations = 2000
        # Stats
        self._total_queries = 0
        self._total_necessity = 0
        self._total_sufficiency = 0

    # ------------------------------------------------------------------
    # Causal model
    # ------------------------------------------------------------------

    def learn_causal_weights(
        self, graph: Dict[str, List[str]], data: Dict[str, np.ndarray]
    ) -> None:
        """Learn causal relationship strengths from data.

        Args:
            graph: Adjacency list {cause: [effects]}.
            data: Observed time series per variable {var: array}.
        """
        for cause, effects in graph.items():
            if cause not in data:
                continue
            cause_data = data[cause]
            for effect in effects:
                if effect not in data:
                    continue
                effect_data = data[effect]
                n = min(len(cause_data), len(effect_data))
                if n < 5:
                    continue
                # Correlation as proxy for causal strength
                c = cause_data[:n]
                e = effect_data[:n]
                c_std = np.std(c)
                e_std = np.std(e)
                if c_std < 1e-12 or e_std < 1e-12:
                    weight = 0.0
                else:
                    corr = np.corrcoef(c, e)[0, 1]
                    weight = float(corr) if not np.isnan(corr) else 0.0
                self._causal_weights[(cause, effect)] = weight

    # ------------------------------------------------------------------
    # What-if simulation
    # ------------------------------------------------------------------

    def what_if(
        self,
        variable: str,
        new_value: float,
        kg_state: Dict[str, float],
        graph: Optional[Dict[str, List[str]]] = None,
    ) -> CounterfactualResult:
        """Simulate an alternative reality where variable takes new_value.

        Args:
            variable: The variable to intervene on.
            new_value: The counterfactual value.
            kg_state: Current state of all variables {name: value}.
            graph: Causal graph (optional, uses learned weights if absent).

        Returns:
            CounterfactualResult with affected variables and differences.
        """
        self._total_queries += 1
        original_value = kg_state.get(variable, 0.0)

        # Build counterfactual state via forward propagation
        cf_state = dict(kg_state)
        cf_state[variable] = new_value

        # Get downstream effects
        if graph is None:
            graph = self._graph_from_weights()

        visited = set()
        self._propagate(variable, new_value - original_value, cf_state, graph, visited)

        # Compute differences
        affected: Dict[str, Tuple[float, float]] = {}
        differences: List[str] = []
        for var, cf_val in cf_state.items():
            orig_val = kg_state.get(var, 0.0)
            if abs(cf_val - orig_val) > 1e-6:
                affected[var] = (orig_val, cf_val)
                delta = cf_val - orig_val
                direction = "increase" if delta > 0 else "decrease"
                differences.append(
                    f"{var} would {direction} by {abs(delta):.4f} "
                    f"({orig_val:.4f} -> {cf_val:.4f})"
                )

        return CounterfactualResult(
            variable=variable,
            original_value=original_value,
            counterfactual_value=new_value,
            affected_variables=affected,
            differences=differences,
        )

    def _propagate(
        self,
        variable: str,
        delta: float,
        state: Dict[str, float],
        graph: Dict[str, List[str]],
        visited: set,
    ) -> None:
        """Propagate intervention effects through causal graph."""
        if variable in visited:
            return
        visited.add(variable)

        effects = graph.get(variable, [])
        for effect in effects:
            weight = self._causal_weights.get((variable, effect), 0.5)
            effect_delta = delta * weight
            if abs(effect_delta) > 1e-8:
                state[effect] = state.get(effect, 0.0) + effect_delta
                self._propagate(effect, effect_delta, state, graph, visited)

    def _graph_from_weights(self) -> Dict[str, List[str]]:
        """Build adjacency list from learned causal weights."""
        graph: Dict[str, List[str]] = {}
        for (cause, effect), weight in self._causal_weights.items():
            if abs(weight) > 0.1:
                if cause not in graph:
                    graph[cause] = []
                graph[cause].append(effect)
        return graph

    # ------------------------------------------------------------------
    # Compare worlds
    # ------------------------------------------------------------------

    def compare_worlds(
        self, actual: Dict[str, float], counterfactual: Dict[str, float]
    ) -> List[str]:
        """Describe differences between actual and counterfactual worlds."""
        differences: List[str] = []
        all_vars = set(actual.keys()) | set(counterfactual.keys())
        for var in sorted(all_vars):
            a = actual.get(var, 0.0)
            c = counterfactual.get(var, 0.0)
            if abs(a - c) > 1e-6:
                differences.append(f"{var}: actual={a:.4f}, counterfactual={c:.4f}")
        return differences

    # ------------------------------------------------------------------
    # Necessity and sufficiency
    # ------------------------------------------------------------------

    def compute_necessity(
        self,
        cause: str,
        effect: str,
        graph: Dict[str, List[str]],
        kg_state: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute probability of necessity: P(~E | do(~C), E, C).

        Was the cause *necessary* for the effect?  If we remove the cause,
        does the effect disappear?

        Returns float in [0, 1].
        """
        self._total_necessity += 1
        if kg_state is None:
            kg_state = {}

        # Baseline: effect with cause present
        baseline_effect = kg_state.get(effect, 1.0)
        if abs(baseline_effect) < 1e-8:
            return 0.0

        # Intervene: set cause to 0
        cf_result = self.what_if(cause, 0.0, kg_state, graph)
        cf_effect = cf_result.affected_variables.get(
            effect, (baseline_effect, baseline_effect)
        )[1]

        # Necessity = how much effect decreases when cause is removed
        if abs(baseline_effect) < 1e-12:
            return 0.0
        necessity = max(0.0, 1.0 - abs(cf_effect / baseline_effect))
        return min(necessity, 1.0)

    def compute_sufficiency(
        self,
        cause: str,
        effect: str,
        graph: Dict[str, List[str]],
        kg_state: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute probability of sufficiency: P(E | do(C), ~E, ~C).

        Was the cause *sufficient* for the effect?  If we add the cause,
        does the effect appear?

        Returns float in [0, 1].
        """
        self._total_sufficiency += 1
        if kg_state is None:
            kg_state = {}

        # Baseline: state without cause
        no_cause_state = dict(kg_state)
        no_cause_state[cause] = 0.0
        baseline_effect = no_cause_state.get(effect, 0.0)

        # Intervene: set cause to 1
        cf_result = self.what_if(cause, 1.0, no_cause_state, graph)
        cf_effect = cf_result.affected_variables.get(
            effect, (baseline_effect, baseline_effect)
        )[1]

        # Sufficiency = how much effect increases when cause is introduced
        delta = abs(cf_effect - baseline_effect)
        return min(delta, 1.0)

    # ------------------------------------------------------------------
    # Observation recording
    # ------------------------------------------------------------------

    def record_observation(self, observation: Dict[str, float]) -> None:
        """Record a state observation for baseline estimation."""
        self._observations.append(observation)
        if len(self._observations) > self._max_observations:
            self._observations = self._observations[-self._max_observations:]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return counterfactual reasoning statistics."""
        return {
            'total_queries': self._total_queries,
            'total_necessity_checks': self._total_necessity,
            'total_sufficiency_checks': self._total_sufficiency,
            'causal_weights_learned': len(self._causal_weights),
            'observations_recorded': len(self._observations),
        }
