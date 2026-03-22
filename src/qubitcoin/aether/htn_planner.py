"""
HTN Planner — Hierarchical Task Network for AGI goal decomposition.

Decomposes high-level goals into primitive actions through a hierarchy
of methods, with backtracking when preconditions fail.

AGI Roadmap Item #56.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HTNTask:
    """A task in the hierarchical task network."""
    name: str
    subtasks: List[str] = field(default_factory=list)
    preconditions: Dict[str, Any] = field(default_factory=dict)
    effects: Dict[str, Any] = field(default_factory=dict)
    is_primitive: bool = False


@dataclass
class HTNMethod:
    """A decomposition method for a compound task."""
    task_name: str
    subtasks: List[str]
    preconditions: Dict[str, Any] = field(default_factory=dict)
    name: str = ""


class HTNPlanner:
    """Hierarchical Task Network planner for AGI goal decomposition."""

    def __init__(self, max_depth: int = 10, max_backtrack: int = 50) -> None:
        self._methods: Dict[str, List[HTNMethod]] = {}
        self._primitives: Dict[str, HTNTask] = {}
        self._max_depth: int = max_depth
        self._max_backtrack: int = max_backtrack
        self._plans_generated: int = 0
        self._backtrack_count: int = 0
        self._decomposition_failures: int = 0

        # Pre-built AGI task decompositions
        self._register_builtin_methods()

    def _register_builtin_methods(self) -> None:
        """Register pre-built methods for common AGI tasks."""
        # investigate_anomaly
        self.add_method(
            "investigate_anomaly",
            ["detect_anomaly", "analyze_context", "hypothesize_cause", "verify_hypothesis"],
            preconditions={"kg_size_min": 10},
            method_name="standard_investigation",
        )

        # improve_accuracy
        self.add_method(
            "improve_accuracy",
            ["collect_training_data", "train_model", "validate_results", "adjust_parameters"],
            preconditions={"data_available": True},
            method_name="standard_improvement",
        )

        # explore_knowledge_gap
        self.add_method(
            "explore_knowledge_gap",
            ["identify_gap", "generate_queries", "gather_evidence", "integrate_findings"],
            preconditions={"kg_size_min": 5},
            method_name="standard_exploration",
        )

        # resolve_contradiction
        self.add_method(
            "resolve_contradiction",
            ["identify_conflicting_beliefs", "gather_evidence", "evaluate_evidence", "revise_beliefs"],
            preconditions={},
            method_name="standard_resolution",
        )

        # self_optimize
        self.add_method(
            "self_optimize",
            ["evaluate_performance", "identify_bottleneck", "propose_modification", "test_modification"],
            preconditions={"blocks_processed_min": 100},
            method_name="standard_optimization",
        )

        # Register primitives
        for prim_name in [
            "detect_anomaly", "analyze_context", "hypothesize_cause", "verify_hypothesis",
            "collect_training_data", "train_model", "validate_results", "adjust_parameters",
            "identify_gap", "generate_queries", "gather_evidence", "integrate_findings",
            "identify_conflicting_beliefs", "evaluate_evidence", "revise_beliefs",
            "evaluate_performance", "identify_bottleneck", "propose_modification",
            "test_modification",
        ]:
            self.add_primitive(prim_name)

    def add_method(
        self,
        task_name: str,
        subtasks: List[str],
        preconditions: Optional[Dict[str, Any]] = None,
        method_name: str = "",
    ) -> None:
        """Add a decomposition method for a compound task."""
        method = HTNMethod(
            task_name=task_name,
            subtasks=subtasks,
            preconditions=preconditions or {},
            name=method_name or f"{task_name}_method_{len(self._methods.get(task_name, []))}",
        )
        if task_name not in self._methods:
            self._methods[task_name] = []
        self._methods[task_name].append(method)

    def add_primitive(self, name: str, preconditions: Optional[Dict[str, Any]] = None,
                      effects: Optional[Dict[str, Any]] = None) -> None:
        """Register a primitive (directly executable) task."""
        self._primitives[name] = HTNTask(
            name=name,
            is_primitive=True,
            preconditions=preconditions or {},
            effects=effects or {},
        )

    def _check_preconditions(self, preconditions: Dict[str, Any],
                             world_state: Dict[str, Any]) -> bool:
        """Check if all preconditions are satisfied by the world state."""
        for key, required in preconditions.items():
            if key.endswith("_min"):
                actual_key = key[:-4]
                actual = world_state.get(actual_key, 0)
                if actual < required:
                    return False
            elif key.endswith("_max"):
                actual_key = key[:-4]
                actual = world_state.get(actual_key, float("inf"))
                if actual > required:
                    return False
            else:
                actual = world_state.get(key)
                if actual != required:
                    return False
        return True

    def _apply_effects(self, effects: Dict[str, Any],
                       world_state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply task effects to a copy of the world state."""
        new_state = dict(world_state)
        for key, value in effects.items():
            if key.startswith("inc_"):
                actual_key = key[4:]
                new_state[actual_key] = new_state.get(actual_key, 0) + value
            elif key.startswith("dec_"):
                actual_key = key[4:]
                new_state[actual_key] = new_state.get(actual_key, 0) - value
            else:
                new_state[key] = value
        return new_state

    def _decompose_recursive(
        self,
        task_name: str,
        world_state: Dict[str, Any],
        depth: int,
        backtrack_budget: List[int],
    ) -> Optional[List[str]]:
        """Recursively decompose a task into primitives with backtracking."""
        if depth > self._max_depth:
            return None

        # If primitive, check preconditions and return
        if task_name in self._primitives:
            prim = self._primitives[task_name]
            if self._check_preconditions(prim.preconditions, world_state):
                return [task_name]
            return None

        # Try each method for this task
        methods = self._methods.get(task_name, [])
        for method in methods:
            if backtrack_budget[0] <= 0:
                break

            if not self._check_preconditions(method.preconditions, world_state):
                backtrack_budget[0] -= 1
                self._backtrack_count += 1
                continue

            # Try to decompose all subtasks in order
            plan: List[str] = []
            current_state = dict(world_state)
            success = True

            for subtask in method.subtasks:
                sub_plan = self._decompose_recursive(
                    subtask, current_state, depth + 1, backtrack_budget
                )
                if sub_plan is None:
                    success = False
                    backtrack_budget[0] -= 1
                    self._backtrack_count += 1
                    break
                plan.extend(sub_plan)
                # Apply effects of each primitive
                for action in sub_plan:
                    if action in self._primitives:
                        current_state = self._apply_effects(
                            self._primitives[action].effects, current_state
                        )

            if success:
                return plan

        self._decomposition_failures += 1
        return None

    def decompose(self, goal: str, world_state: Optional[Dict[str, Any]] = None) -> List[str]:
        """Decompose a high-level goal into a sequence of primitive actions.

        Args:
            goal: The high-level goal to decompose.
            world_state: Current world state for precondition checks.

        Returns:
            List of primitive action names, or empty list if decomposition fails.
        """
        state = world_state or {}
        backtrack_budget = [self._max_backtrack]
        result = self._decompose_recursive(goal, state, 0, backtrack_budget)
        if result is not None:
            self._plans_generated += 1
            logger.debug(f"HTN decomposed '{goal}' into {len(result)} primitives")
            return result
        logger.debug(f"HTN failed to decompose '{goal}'")
        return []

    def plan(self, goal: str, state: Optional[Dict[str, Any]] = None) -> List[str]:
        """Alias for decompose — plan a sequence of actions for a goal."""
        return self.decompose(goal, state)

    def get_stats(self) -> dict:
        """Return planner statistics."""
        return {
            "plans_generated": self._plans_generated,
            "backtrack_count": self._backtrack_count,
            "decomposition_failures": self._decomposition_failures,
            "registered_methods": sum(len(v) for v in self._methods.values()),
            "registered_primitives": len(self._primitives),
        }
