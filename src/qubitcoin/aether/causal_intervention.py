"""
Causal Intervention — do-calculus for interventional queries.

Computes interventional distributions using do-calculus,
average treatment effects, confounder identification,
and back-door / front-door criteria.

AI Roadmap Item #62.
"""
import numpy as np
from typing import Any, Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CausalIntervention:
    """Compute interventional distributions using do-calculus.

    Operates on a causal graph represented as an adjacency dict:
        graph = {
            "X": ["Y", "Z"],  # X -> Y, X -> Z
            "Z": ["Y"],       # Z -> Y
        }
    """

    def __init__(self) -> None:
        self._interventions: int = 0
        self._ate_computations: int = 0
        self._identifiability_checks: int = 0
        self._confounder_detections: int = 0

    def _get_parents(self, variable: str, graph: Dict[str, List[str]]) -> List[str]:
        """Get all parents (direct causes) of a variable."""
        parents = []
        for node, children in graph.items():
            if variable in children:
                parents.append(node)
        return parents

    def _get_children(self, variable: str, graph: Dict[str, List[str]]) -> List[str]:
        """Get all children (direct effects) of a variable."""
        return list(graph.get(variable, []))

    def _get_ancestors(self, variable: str, graph: Dict[str, List[str]]) -> Set[str]:
        """Get all ancestors of a variable via BFS."""
        ancestors: Set[str] = set()
        queue = self._get_parents(variable, graph)
        while queue:
            node = queue.pop(0)
            if node not in ancestors:
                ancestors.add(node)
                queue.extend(self._get_parents(node, graph))
        return ancestors

    def _get_descendants(self, variable: str, graph: Dict[str, List[str]]) -> Set[str]:
        """Get all descendants of a variable via BFS."""
        descendants: Set[str] = set()
        queue = self._get_children(variable, graph)
        while queue:
            node = queue.pop(0)
            if node not in descendants:
                descendants.add(node)
                queue.extend(self._get_children(node, graph))
        return descendants

    def do(self, variable: str, value: float,
           causal_graph: Dict[str, List[str]],
           data: Optional[Dict[str, np.ndarray]] = None) -> Dict[str, float]:
        """Perform an interventional query: do(variable = value).

        Mutilates the graph by removing all edges into `variable`,
        then estimates the effect on all descendants.

        Args:
            variable: The variable to intervene on.
            value: The value to set.
            causal_graph: Adjacency dict of the causal graph.
            data: Optional observational data {var_name: np.array of values}.

        Returns:
            Dict mapping each descendant to its estimated value under intervention.
        """
        self._interventions += 1

        # Mutilated graph: remove all edges into the treatment variable
        mutilated = {}
        for node, children in causal_graph.items():
            mutilated[node] = [c for c in children]
        # Remove edges pointing to `variable`
        for node in mutilated:
            mutilated[node] = [c for c in mutilated[node] if c != variable]
        # Ensure variable has its children
        if variable not in mutilated:
            mutilated[variable] = list(causal_graph.get(variable, []))

        # Propagate intervention effects through descendants
        descendants = self._get_descendants(variable, causal_graph)
        results: Dict[str, float] = {variable: value}

        if data is not None and len(data) > 0:
            # Use data to estimate conditional effects
            for desc in self._topological_sort(mutilated):
                if desc == variable:
                    continue
                if desc not in descendants:
                    continue
                parents = self._get_parents(desc, mutilated)
                if not parents:
                    # No parents in mutilated graph, use data mean
                    results[desc] = float(np.mean(data.get(desc, np.array([0.0]))))
                    continue
                # Simple linear estimate: desc = mean(parent_effects)
                parent_vals = [results.get(p, float(np.mean(data.get(p, np.array([0.0]))))) for p in parents]
                if parent_vals:
                    # Weighted mean + residual from data
                    base = float(np.mean(data.get(desc, np.array([0.0]))))
                    parent_effect = float(np.mean(parent_vals)) - float(np.mean(
                        [np.mean(data.get(p, np.array([0.0]))) for p in parents]
                    ))
                    results[desc] = base + parent_effect
                else:
                    results[desc] = float(np.mean(data.get(desc, np.array([0.0]))))
        else:
            # Without data, propagate value through graph with decay
            for desc in self._topological_sort(mutilated):
                if desc == variable or desc not in descendants:
                    continue
                parents = self._get_parents(desc, mutilated)
                parent_vals = [results.get(p, 0.0) for p in parents if p in results]
                if parent_vals:
                    results[desc] = float(np.mean(parent_vals)) * 0.8  # Decay factor
                else:
                    results[desc] = 0.0

        return results

    def compute_ate(self, treatment: str, outcome: str,
                    data: Dict[str, np.ndarray],
                    causal_graph: Optional[Dict[str, List[str]]] = None) -> float:
        """Compute Average Treatment Effect (ATE).

        ATE = E[Y | do(X=1)] - E[Y | do(X=0)]

        If causal_graph is provided and confounders are identifiable,
        uses the back-door adjustment formula. Otherwise, falls back
        to naive difference.

        Args:
            treatment: Treatment variable name.
            outcome: Outcome variable name.
            data: Observational data dict.

        Returns:
            Estimated ATE.
        """
        self._ate_computations += 1

        if treatment not in data or outcome not in data:
            return 0.0

        t_values = data[treatment]
        y_values = data[outcome]

        if causal_graph is not None:
            # Try back-door adjustment
            confounders = self.identify_confounders(treatment, outcome, causal_graph)
            if confounders and all(c in data for c in confounders):
                return self._backdoor_adjustment(
                    treatment, outcome, confounders, data
                )

        # Naive ATE: split by treatment value
        median_t = float(np.median(t_values))
        treated = y_values[t_values > median_t]
        control = y_values[t_values <= median_t]

        if len(treated) == 0 or len(control) == 0:
            return 0.0

        ate = float(np.mean(treated) - np.mean(control))
        return ate

    def _backdoor_adjustment(
        self,
        treatment: str,
        outcome: str,
        confounders: List[str],
        data: Dict[str, np.ndarray],
    ) -> float:
        """Back-door adjustment formula for ATE.

        ATE = sum_z P(Z=z) * [E[Y|X=1,Z=z] - E[Y|X=0,Z=z]]
        Approximated by stratification on confounders.
        """
        t_values = data[treatment]
        y_values = data[outcome]
        median_t = float(np.median(t_values))

        # Simple stratification: split confounders at their medians
        n = len(t_values)
        strata_mask = np.ones(n, dtype=bool)

        # Create a single stratification dimension
        if confounders:
            conf_vals = data[confounders[0]]
            median_c = float(np.median(conf_vals))
            high_strata = conf_vals > median_c
            low_strata = ~high_strata

            ate_parts = []
            for strata_mask in [high_strata, low_strata]:
                t_sub = t_values[strata_mask]
                y_sub = y_values[strata_mask]
                treated = y_sub[t_sub > median_t]
                control = y_sub[t_sub <= median_t]
                if len(treated) > 0 and len(control) > 0:
                    ate_parts.append(float(np.mean(treated) - np.mean(control)))

            if ate_parts:
                return float(np.mean(ate_parts))

        return 0.0

    def identify_confounders(
        self,
        treatment: str,
        outcome: str,
        graph: Dict[str, List[str]],
    ) -> List[str]:
        """Identify confounders between treatment and outcome.

        A confounder is a common ancestor of both treatment and outcome
        that opens a backdoor path.
        """
        self._confounder_detections += 1
        treatment_ancestors = self._get_ancestors(treatment, graph)
        outcome_ancestors = self._get_ancestors(outcome, graph)
        common = treatment_ancestors & outcome_ancestors
        return list(common)

    def check_backdoor_criterion(
        self,
        treatment: str,
        outcome: str,
        adjustment_set: Set[str],
        graph: Dict[str, List[str]],
    ) -> bool:
        """Check if an adjustment set satisfies the back-door criterion.

        The set Z satisfies the back-door criterion relative to (X, Y) if:
        1. No node in Z is a descendant of X
        2. Z blocks every path between X and Y that contains an arrow into X
        """
        # Condition 1: no descendant of treatment in adjustment set
        descendants = self._get_descendants(treatment, graph)
        if adjustment_set & descendants:
            return False

        # Condition 2: confounders blocked (simplified check)
        confounders = set(self.identify_confounders(treatment, outcome, graph))
        return confounders.issubset(adjustment_set)

    def check_frontdoor_criterion(
        self,
        treatment: str,
        outcome: str,
        mediator_set: Set[str],
        graph: Dict[str, List[str]],
    ) -> bool:
        """Check if a set of mediators satisfies the front-door criterion.

        Z satisfies front-door relative to (X, Y) if:
        1. X blocks all paths from Z to Y that don't go through X
        2. There is no unblocked back-door path from X to Z
        3. All directed paths from X to Y pass through Z
        """
        # Simplified check: mediators must be between treatment and outcome
        for m in mediator_set:
            if m not in self._get_descendants(treatment, graph):
                return False
            if outcome not in self._get_descendants(m, graph):
                return False
        return True

    def is_identifiable(self, query: dict, graph: Dict[str, List[str]]) -> bool:
        """Check if an interventional query is identifiable from observational data.

        Args:
            query: {"treatment": str, "outcome": str}
            graph: Causal graph.

        Returns:
            True if the causal effect is identifiable.
        """
        self._identifiability_checks += 1
        treatment = query.get("treatment", "")
        outcome = query.get("outcome", "")

        if not treatment or not outcome:
            return False

        # Check back-door: are all confounders observable?
        confounders = self.identify_confounders(treatment, outcome, graph)
        if not confounders:
            return True  # No confounders means direct identification

        # If confounders exist, back-door criterion with full confounder set
        if self.check_backdoor_criterion(treatment, outcome, set(confounders), graph):
            return True

        # Try front-door: find mediators
        children = set(self._get_children(treatment, graph))
        outcome_parents = set(self._get_parents(outcome, graph))
        mediators = children & outcome_parents
        if mediators and self.check_frontdoor_criterion(treatment, outcome, mediators, graph):
            return True

        return False

    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """Topological sort of the graph (Kahn's algorithm)."""
        in_degree: Dict[str, int] = {}
        all_nodes: Set[str] = set()
        for node, children in graph.items():
            all_nodes.add(node)
            for c in children:
                all_nodes.add(c)

        for node in all_nodes:
            in_degree[node] = 0
        for node, children in graph.items():
            for c in children:
                in_degree[c] = in_degree.get(c, 0) + 1

        queue = [n for n in all_nodes if in_degree.get(n, 0) == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for child in graph.get(node, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return result

    def get_stats(self) -> dict:
        """Return causal intervention statistics."""
        return {
            "interventions": self._interventions,
            "ate_computations": self._ate_computations,
            "identifiability_checks": self._identifiability_checks,
            "confounder_detections": self._confounder_detections,
        }
