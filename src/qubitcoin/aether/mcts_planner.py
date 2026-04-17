"""Monte Carlo Tree Search planner for AI goal decomposition.

Gives the Aether Tree the ability to plan multi-step exploration
actions by simulating outcomes via MCTS with UCB1 selection.

Roadmap item #38.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Action types that map to real reasoning operations
# ---------------------------------------------------------------------------

ACTION_TYPES: List[str] = [
    'reason_about',          # deductive reasoning on a node
    'explore_domain',        # inductive reasoning across a domain
    'investigate_node',      # deep-dive into a single node
    'create_hypothesis',     # abductive hypothesis generation
    'verify_prediction',     # temporal prediction validation
    'seek_contradiction',    # adversarial contradiction search
]


# ---------------------------------------------------------------------------
# State representation
# ---------------------------------------------------------------------------

@dataclass
class PlanState:
    """Lightweight representation of the exploration frontier.

    Attributes:
        explored_node_ids: Set of KG node IDs already examined.
        explored_domains: Set of domain names already targeted.
        confidence_sum: Running sum of confidence scores obtained.
        steps_taken: Number of actions executed so far.
    """
    explored_node_ids: FrozenSet[str] = field(default_factory=frozenset)
    explored_domains: FrozenSet[str] = field(default_factory=frozenset)
    confidence_sum: float = 0.0
    steps_taken: int = 0

    def with_action(self, action: Dict[str, Any]) -> "PlanState":
        """Return a new state after applying *action*."""
        new_nodes = set(self.explored_node_ids)
        new_domains = set(self.explored_domains)
        conf_delta = 0.0

        target_id = action.get('target_id', '')
        domain = action.get('domain', '')

        if target_id:
            new_nodes.add(target_id)
        if domain:
            new_domains.add(domain)

        conf_delta = action.get('expected_confidence', 0.5)

        return PlanState(
            explored_node_ids=frozenset(new_nodes),
            explored_domains=frozenset(new_domains),
            confidence_sum=self.confidence_sum + conf_delta,
            steps_taken=self.steps_taken + 1,
        )


# ---------------------------------------------------------------------------
# MCTS Node
# ---------------------------------------------------------------------------

@dataclass
class MCTSNode:
    """A single node in the MCTS search tree.

    Attributes:
        state: The plan state at this node.
        parent: Parent node (None for root).
        children: Expanded child nodes.
        visits: Number of times this node was visited during search.
        value: Cumulative reward collected through this node.
        action: The action that led to this node (None for root).
        untried_actions: Actions not yet expanded from this node.
    """
    state: PlanState
    parent: Optional["MCTSNode"] = None
    children: List["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    action: Optional[Dict[str, Any]] = None
    untried_actions: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_fully_expanded(self) -> bool:
        return len(self.untried_actions) == 0

    @property
    def is_terminal(self) -> bool:
        return self.state.steps_taken >= 6  # max plan depth


# ---------------------------------------------------------------------------
# MCTS Planner
# ---------------------------------------------------------------------------

class MCTSPlanner:
    """Monte Carlo Tree Search planner for Aether goal decomposition.

    Uses UCB1 selection, lightweight heuristic rollouts, and maps each
    action to a concrete reasoning operation that can be executed by the
    Aether engine.

    Args:
        knowledge_graph: KnowledgeGraph instance for state queries.
        reasoning_engine: ReasoningEngine for available operations.
        max_iterations: MCTS iterations per ``plan()`` call.
        exploration_c: UCB1 exploration constant (sqrt(2) by default).
        max_plan_depth: Maximum actions in a single plan.
    """

    def __init__(
        self,
        knowledge_graph: Any,
        reasoning_engine: Any,
        max_iterations: int = 100,
        exploration_c: float = 1.414,
        max_plan_depth: int = 6,
    ) -> None:
        self.kg = knowledge_graph
        self.reasoning = reasoning_engine
        self.max_iterations = max_iterations
        self.exploration_c = exploration_c
        self.max_plan_depth = max_plan_depth
        self._rng = random.Random(42)
        self._plans_generated: int = 0
        self._total_iterations: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, goal: Dict[str, Any], current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate an ordered list of actions to achieve *goal*.

        Args:
            goal: A curiosity goal dict (type, target, priority, ...).
            current_state: Dict with optional keys ``explored_node_ids``,
                ``explored_domains``, ``confidence_sum``.

        Returns:
            Ordered list of action dicts, each with keys ``action_type``,
            ``domain``, ``target_id``, ``expected_confidence``, ``priority``.
        """
        t0 = time.monotonic()

        root_state = PlanState(
            explored_node_ids=frozenset(current_state.get('explored_node_ids', set())),
            explored_domains=frozenset(current_state.get('explored_domains', set())),
            confidence_sum=current_state.get('confidence_sum', 0.0),
        )

        root = MCTSNode(state=root_state)
        root.untried_actions = self._generate_actions(root_state, goal)

        if not root.untried_actions:
            return []

        iterations = 0
        for _ in range(self.max_iterations):
            node = self._select(root)
            if not node.is_terminal:
                node = self._expand(node, goal)
            reward = self._simulate(node, goal)
            self._backpropagate(node, reward)
            iterations += 1

        self._total_iterations += iterations
        self._plans_generated += 1

        # Extract best path from root to a leaf
        plan = self._extract_best_plan(root)

        elapsed = time.monotonic() - t0
        logger.debug(
            "MCTS plan for goal type=%s: %d actions in %d iterations (%.1fms)",
            goal.get('type', '?'), len(plan), iterations, elapsed * 1000,
        )

        return plan

    def get_stats(self) -> Dict[str, Any]:
        """Return planner statistics."""
        return {
            'plans_generated': self._plans_generated,
            'total_iterations': self._total_iterations,
        }

    # ------------------------------------------------------------------
    # MCTS phases
    # ------------------------------------------------------------------

    def _select(self, node: MCTSNode) -> MCTSNode:
        """UCB1 tree-policy selection — descend to the most promising leaf."""
        while not node.is_terminal:
            if not node.is_fully_expanded:
                return node
            if not node.children:
                return node
            node = self._ucb1_child(node)
        return node

    def _expand(self, node: MCTSNode, goal: Dict[str, Any]) -> MCTSNode:
        """Expand one untried action from *node*."""
        if not node.untried_actions:
            # Generate fresh actions if needed
            node.untried_actions = self._generate_actions(node.state, goal)
            if not node.untried_actions:
                return node

        action = node.untried_actions.pop()
        new_state = node.state.with_action(action)
        child = MCTSNode(
            state=new_state,
            parent=node,
            action=action,
            untried_actions=self._generate_actions(new_state, goal),
        )
        node.children.append(child)
        return child

    def _simulate(self, node: MCTSNode, goal: Dict[str, Any]) -> float:
        """Lightweight heuristic rollout from *node* to estimate value.

        Uses a fast heuristic rather than full reasoning execution:
        - Domain coverage contributes positively
        - Node exploration breadth contributes positively
        - Matching the goal type gives a bonus
        - Diminishing returns on depth
        """
        state = node.state
        reward = 0.0

        # Simulate remaining steps with random actions
        sim_state = PlanState(
            explored_node_ids=state.explored_node_ids,
            explored_domains=state.explored_domains,
            confidence_sum=state.confidence_sum,
            steps_taken=state.steps_taken,
        )

        remaining = self.max_plan_depth - sim_state.steps_taken
        for _ in range(remaining):
            # Pick a random action type
            action_type = self._rng.choice(ACTION_TYPES)
            sim_confidence = self._rng.uniform(0.3, 0.8)
            fake_domain = f"sim_domain_{self._rng.randint(0, 5)}"
            sim_state = sim_state.with_action({
                'action_type': action_type,
                'domain': fake_domain,
                'target_id': '',
                'expected_confidence': sim_confidence,
            })

        # Reward heuristic
        goal_type = goal.get('type', '')
        domain_coverage = len(sim_state.explored_domains)
        node_coverage = len(sim_state.explored_node_ids)

        reward += min(domain_coverage * 0.15, 0.6)
        reward += min(node_coverage * 0.05, 0.4)
        reward += sim_state.confidence_sum / max(sim_state.steps_taken, 1) * 0.3

        # Goal-type alignment bonus
        if node.action:
            action_type = node.action.get('action_type', '')
            type_alignment = {
                'explore_domain': ['explore_domain', 'reason_about'],
                'investigate_contradiction': ['seek_contradiction', 'reason_about'],
                'bridge_gap': ['investigate_node', 'create_hypothesis'],
                'verify_prediction': ['verify_prediction', 'reason_about'],
            }
            aligned = type_alignment.get(goal_type, [])
            if action_type in aligned:
                reward += 0.3

        return min(reward, 1.0)

    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        """Propagate reward up the tree, updating visits and values."""
        current: Optional[MCTSNode] = node
        while current is not None:
            current.visits += 1
            current.value += reward
            current = current.parent

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ucb1_child(self, node: MCTSNode) -> MCTSNode:
        """Select the child with the highest UCB1 score."""
        log_parent = math.log(node.visits + 1)
        best_score = -1.0
        best_child = node.children[0]

        for child in node.children:
            if child.visits == 0:
                return child  # always try unvisited children first
            exploit = child.value / child.visits
            explore = self.exploration_c * math.sqrt(log_parent / child.visits)
            score = exploit + explore
            if score > best_score:
                best_score = score
                best_child = child

        return best_child

    def _generate_actions(
        self, state: PlanState, goal: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate candidate actions from the current state and goal.

        Actions are grounded in KG state when possible, falling back to
        goal-derived synthetic actions otherwise.
        """
        actions: List[Dict[str, Any]] = []
        goal_type = goal.get('type', '')
        goal_domain = goal.get('target', '')
        goal_target_ids = goal.get('target_ids', [])

        # Limit actions to keep the tree manageable
        max_actions = 6

        # --- Goal-aligned actions ---
        if goal_type == 'explore_domain':
            actions.append({
                'action_type': 'explore_domain',
                'domain': goal_domain,
                'target_id': '',
                'expected_confidence': 0.6,
                'priority': 0.9,
            })
            actions.append({
                'action_type': 'reason_about',
                'domain': goal_domain,
                'target_id': '',
                'expected_confidence': 0.5,
                'priority': 0.7,
            })

        elif goal_type == 'investigate_contradiction':
            for tid in goal_target_ids[:2]:
                actions.append({
                    'action_type': 'seek_contradiction',
                    'domain': '',
                    'target_id': tid,
                    'expected_confidence': 0.7,
                    'priority': 0.9,
                })
            actions.append({
                'action_type': 'reason_about',
                'domain': '',
                'target_id': goal_target_ids[0] if goal_target_ids else '',
                'expected_confidence': 0.5,
                'priority': 0.6,
            })

        elif goal_type == 'bridge_gap':
            for tid in goal_target_ids[:2]:
                actions.append({
                    'action_type': 'investigate_node',
                    'domain': '',
                    'target_id': tid,
                    'expected_confidence': 0.6,
                    'priority': 0.8,
                })
            actions.append({
                'action_type': 'create_hypothesis',
                'domain': '',
                'target_id': goal_target_ids[0] if goal_target_ids else '',
                'expected_confidence': 0.5,
                'priority': 0.7,
            })

        elif goal_type == 'verify_prediction':
            actions.append({
                'action_type': 'verify_prediction',
                'domain': '',
                'target_id': '',
                'expected_confidence': 0.7,
                'priority': 0.9,
            })

        # --- KG-derived exploration actions ---
        if self.kg and hasattr(self.kg, 'get_domain_stats'):
            try:
                domain_stats = self.kg.get_domain_stats()
                for domain, info in sorted(
                    domain_stats.items(), key=lambda x: x[1]['count']
                )[:2]:
                    if domain not in state.explored_domains:
                        actions.append({
                            'action_type': 'explore_domain',
                            'domain': domain,
                            'target_id': '',
                            'expected_confidence': 0.5,
                            'priority': 0.5,
                        })
            except Exception:
                pass

        # --- Generic fallback actions ---
        if len(actions) < 3:
            for at in ['reason_about', 'create_hypothesis', 'investigate_node']:
                actions.append({
                    'action_type': at,
                    'domain': goal_domain or 'general',
                    'target_id': '',
                    'expected_confidence': 0.4,
                    'priority': 0.3,
                })

        # Shuffle to avoid deterministic bias, then trim
        self._rng.shuffle(actions)
        return actions[:max_actions]

    def _extract_best_plan(self, root: MCTSNode) -> List[Dict[str, Any]]:
        """Walk the tree greedily by visit count to extract the best plan."""
        plan: List[Dict[str, Any]] = []
        node = root

        while node.children:
            # Pick child with most visits (robust selection)
            best = max(node.children, key=lambda c: c.visits)
            if best.action is not None:
                plan.append(best.action)
            node = best

        return plan
