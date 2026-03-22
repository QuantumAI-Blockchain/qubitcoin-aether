"""Tests for the MCTS Planner (AGI Roadmap Item #38)."""

import pytest
from unittest.mock import MagicMock

from qubitcoin.aether.mcts_planner import (
    MCTSPlanner,
    MCTSNode,
    PlanState,
    ACTION_TYPES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_kg():
    """Minimal mock KnowledgeGraph."""
    kg = MagicMock()
    kg.nodes = {
        'n1': MagicMock(node_id='n1', domain='physics', node_type='observation',
                        confidence=0.8, edges_out=[], edges_in=[]),
        'n2': MagicMock(node_id='n2', domain='math', node_type='inference',
                        confidence=0.7, edges_out=[], edges_in=[]),
        'n3': MagicMock(node_id='n3', domain='physics', node_type='observation',
                        confidence=0.6, edges_out=[], edges_in=[]),
    }
    kg.edges = []
    kg.get_domain_stats.return_value = {
        'physics': {'count': 20},
        'math': {'count': 5},
    }
    return kg


@pytest.fixture
def mock_reasoning():
    """Minimal mock ReasoningEngine."""
    return MagicMock()


@pytest.fixture
def planner(mock_kg, mock_reasoning):
    """MCTSPlanner with mocked dependencies."""
    return MCTSPlanner(
        knowledge_graph=mock_kg,
        reasoning_engine=mock_reasoning,
        max_iterations=50,
        exploration_c=1.414,
    )


# ---------------------------------------------------------------------------
# PlanState tests
# ---------------------------------------------------------------------------

class TestPlanState:
    def test_default_state(self):
        s = PlanState()
        assert len(s.explored_node_ids) == 0
        assert len(s.explored_domains) == 0
        assert s.confidence_sum == 0.0
        assert s.steps_taken == 0

    def test_with_action_adds_node(self):
        s = PlanState()
        action = {'target_id': 'n1', 'domain': 'physics', 'expected_confidence': 0.7}
        s2 = s.with_action(action)
        assert 'n1' in s2.explored_node_ids
        assert 'physics' in s2.explored_domains
        assert s2.confidence_sum == pytest.approx(0.7)
        assert s2.steps_taken == 1
        # Original is immutable
        assert len(s.explored_node_ids) == 0

    def test_with_action_default_confidence(self):
        s = PlanState()
        action = {'target_id': '', 'domain': ''}
        s2 = s.with_action(action)
        assert s2.confidence_sum == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# MCTSNode tests
# ---------------------------------------------------------------------------

class TestMCTSNode:
    def test_is_fully_expanded_empty(self):
        node = MCTSNode(state=PlanState(), untried_actions=[])
        assert node.is_fully_expanded is True

    def test_is_fully_expanded_with_actions(self):
        node = MCTSNode(
            state=PlanState(),
            untried_actions=[{'action_type': 'reason_about'}],
        )
        assert node.is_fully_expanded is False

    def test_is_terminal(self):
        node = MCTSNode(state=PlanState(steps_taken=6))
        assert node.is_terminal is True

        node2 = MCTSNode(state=PlanState(steps_taken=3))
        assert node2.is_terminal is False


# ---------------------------------------------------------------------------
# MCTSPlanner tests
# ---------------------------------------------------------------------------

class TestMCTSPlanner:
    def test_plan_returns_list(self, planner):
        goal = {'type': 'explore_domain', 'target': 'math', 'priority': 0.9}
        result = planner.plan(goal, {})
        assert isinstance(result, list)
        # Should produce at least one action
        assert len(result) >= 1

    def test_plan_actions_have_required_keys(self, planner):
        goal = {'type': 'explore_domain', 'target': 'physics', 'priority': 0.8}
        result = planner.plan(goal, {})
        for action in result:
            assert 'action_type' in action
            assert 'domain' in action or 'target_id' in action

    def test_plan_action_types_are_valid(self, planner):
        goal = {'type': 'investigate_contradiction', 'target_ids': ['n1', 'n2'],
                'priority': 0.9}
        result = planner.plan(goal, {})
        for action in result:
            assert action['action_type'] in ACTION_TYPES

    def test_plan_with_existing_state(self, planner):
        goal = {'type': 'bridge_gap', 'target_ids': ['n1'], 'priority': 0.7}
        state = {
            'explored_node_ids': {'n1'},
            'explored_domains': {'physics'},
            'confidence_sum': 1.5,
        }
        result = planner.plan(goal, state)
        assert isinstance(result, list)

    def test_plan_verify_prediction(self, planner):
        goal = {'type': 'verify_prediction', 'target': 'verify_pred', 'priority': 0.8}
        result = planner.plan(goal, {})
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_plan_empty_when_no_actions(self):
        """Planner with no KG should still work (generic fallback actions)."""
        planner = MCTSPlanner(
            knowledge_graph=None,
            reasoning_engine=None,
            max_iterations=10,
        )
        goal = {'type': 'explore_domain', 'target': 'test', 'priority': 0.5}
        result = planner.plan(goal, {})
        # Should still produce actions from generic fallbacks
        assert isinstance(result, list)

    def test_stats(self, planner):
        stats = planner.get_stats()
        assert stats['plans_generated'] == 0
        assert stats['total_iterations'] == 0

        planner.plan({'type': 'explore_domain', 'target': 'x', 'priority': 0.5}, {})
        stats = planner.get_stats()
        assert stats['plans_generated'] == 1
        assert stats['total_iterations'] > 0

    def test_backpropagate(self, planner):
        root = MCTSNode(state=PlanState())
        child = MCTSNode(state=PlanState(steps_taken=1), parent=root)
        root.children.append(child)

        planner._backpropagate(child, 0.8)
        assert child.visits == 1
        assert child.value == pytest.approx(0.8)
        assert root.visits == 1
        assert root.value == pytest.approx(0.8)

    def test_ucb1_prefers_unvisited(self, planner):
        root = MCTSNode(state=PlanState(), visits=10)
        c1 = MCTSNode(state=PlanState(steps_taken=1), parent=root, visits=5, value=2.0)
        c2 = MCTSNode(state=PlanState(steps_taken=1), parent=root, visits=0, value=0.0)
        root.children = [c1, c2]

        selected = planner._ucb1_child(root)
        assert selected is c2  # unvisited child chosen first

    def test_select_returns_expandable_node(self, planner):
        root = MCTSNode(
            state=PlanState(),
            untried_actions=[{'action_type': 'reason_about', 'domain': 'x',
                              'target_id': '', 'expected_confidence': 0.5,
                              'priority': 0.5}],
        )
        selected = planner._select(root)
        assert selected is root  # root itself is not fully expanded

    def test_expand_creates_child(self, planner):
        root = MCTSNode(
            state=PlanState(),
            untried_actions=[{'action_type': 'explore_domain', 'domain': 'math',
                              'target_id': '', 'expected_confidence': 0.6,
                              'priority': 0.7}],
        )
        goal = {'type': 'explore_domain', 'target': 'math', 'priority': 0.8}
        child = planner._expand(root, goal)
        assert child is not root
        assert child.parent is root
        assert len(root.children) == 1
        assert child.state.steps_taken == 1

    def test_simulate_returns_bounded_reward(self, planner):
        node = MCTSNode(
            state=PlanState(),
            action={'action_type': 'explore_domain', 'domain': 'physics'},
        )
        goal = {'type': 'explore_domain', 'target': 'physics'}
        reward = planner._simulate(node, goal)
        assert 0.0 <= reward <= 1.0

    def test_deterministic_with_same_seed(self, mock_kg, mock_reasoning):
        """Two planners with same seed produce same plans."""
        p1 = MCTSPlanner(mock_kg, mock_reasoning, max_iterations=30)
        p2 = MCTSPlanner(mock_kg, mock_reasoning, max_iterations=30)
        goal = {'type': 'explore_domain', 'target': 'math', 'priority': 0.9}

        r1 = p1.plan(goal, {})
        r2 = p2.plan(goal, {})
        # Same seed → same results
        assert len(r1) == len(r2)
        for a1, a2 in zip(r1, r2):
            assert a1['action_type'] == a2['action_type']


# ---------------------------------------------------------------------------
# Integration with AetherEngine (import check)
# ---------------------------------------------------------------------------

class TestMCTSIntegration:
    def test_mcts_planner_importable(self):
        """Verify the module can be imported without errors."""
        from qubitcoin.aether.mcts_planner import MCTSPlanner, PlanState, MCTSNode
        assert MCTSPlanner is not None

    def test_action_types_defined(self):
        assert len(ACTION_TYPES) == 6
        assert 'reason_about' in ACTION_TYPES
        assert 'explore_domain' in ACTION_TYPES
        assert 'seek_contradiction' in ACTION_TYPES
