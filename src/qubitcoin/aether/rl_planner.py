"""
Reinforcement Learning Goal Planner (Item #27)

Q-learning based planner that selects AI exploration actions based on
discretized knowledge graph state features. Uses epsilon-greedy exploration
with decay.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Available actions the planner can choose
ACTIONS: List[str] = [
    'explore_domain',
    'deepen_knowledge',
    'verify_predictions',
    'seek_contradictions',
    'create_hypotheses',
    'consolidate_memory',
]


class RLPlanner:
    """
    Tabular Q-learning planner for AI goal selection.

    State space: Discretized KG features (node counts per domain, edge density,
    prediction accuracy, etc.)
    Action space: 6 high-level AI strategies.
    """

    def __init__(self, num_state_bins: int = 10, lr: float = 0.1,
                 gamma: float = 0.95, epsilon_start: float = 0.3,
                 epsilon_end: float = 0.05, epsilon_decay: float = 0.999) -> None:
        self.num_state_bins = num_state_bins
        self.lr = lr
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.num_actions = len(ACTIONS)

        # Q-table: maps discretized state tuple -> action values
        self._q_table: Dict[Tuple[int, ...], np.ndarray] = {}

        # Feature statistics for discretization (running min/max)
        self._feature_min: Optional[np.ndarray] = None
        self._feature_max: Optional[np.ndarray] = None
        self._feature_dim: int = 8  # Number of state features

        # Stats
        self._total_steps: int = 0
        self._total_reward: float = 0.0
        self._action_counts: Dict[str, int] = {a: 0 for a in ACTIONS}
        self._last_state: Optional[Tuple[int, ...]] = None
        self._last_action: Optional[str] = None
        self._created_at: float = time.time()

    def _discretize(self, features: np.ndarray) -> Tuple[int, ...]:
        """
        Discretize continuous state features into bin indices.
        Updates running min/max for adaptive binning.
        """
        features = np.asarray(features, dtype=np.float64).flatten()
        if features.shape[0] < self._feature_dim:
            features = np.pad(features, (0, self._feature_dim - features.shape[0]))
        elif features.shape[0] > self._feature_dim:
            features = features[:self._feature_dim]

        # Update running statistics
        if self._feature_min is None:
            self._feature_min = features.copy()
            self._feature_max = features.copy() + 1e-6
        else:
            self._feature_min = np.minimum(self._feature_min, features)
            self._feature_max = np.maximum(self._feature_max, features + 1e-6)

        # Normalize to [0, 1] then bin
        range_vec = self._feature_max - self._feature_min
        range_vec = np.where(range_vec < 1e-12, 1.0, range_vec)
        normalized = (features - self._feature_min) / range_vec
        bins = np.clip((normalized * self.num_state_bins).astype(int),
                       0, self.num_state_bins - 1)
        return tuple(bins.tolist())

    def _get_q_values(self, state: Tuple[int, ...]) -> np.ndarray:
        """Get Q-values for a state, initializing if unseen."""
        if state not in self._q_table:
            self._q_table[state] = np.zeros(self.num_actions, dtype=np.float64)
        return self._q_table[state]

    def select_action(self, state_features: np.ndarray) -> str:
        """
        Select an action using epsilon-greedy policy.

        Args:
            state_features: Continuous feature vector describing current KG state.

        Returns:
            Action name string.
        """
        state = self._discretize(state_features)
        q_values = self._get_q_values(state)

        # Epsilon-greedy
        if np.random.random() < self.epsilon:
            action_idx = np.random.randint(self.num_actions)
        else:
            action_idx = int(np.argmax(q_values))

        action = ACTIONS[action_idx]
        self._last_state = state
        self._last_action = action
        self._action_counts[action] += 1

        # Decay epsilon
        self.epsilon = max(self.epsilon_end,
                           self.epsilon * self.epsilon_decay)

        return action

    def update(self, state_features: np.ndarray, action: str,
               reward: float, next_state_features: np.ndarray) -> float:
        """
        Q-learning update: Q(s,a) += lr * (r + gamma * max_a' Q(s',a') - Q(s,a))

        Args:
            state_features: State when action was taken.
            action: Action that was taken.
            reward: Reward received.
            next_state_features: Resulting state.

        Returns:
            TD error magnitude.
        """
        state = self._discretize(state_features)
        next_state = self._discretize(next_state_features)
        action_idx = ACTIONS.index(action) if action in ACTIONS else 0

        q_values = self._get_q_values(state)
        next_q_values = self._get_q_values(next_state)

        # TD target
        td_target = reward + self.gamma * np.max(next_q_values)
        td_error = td_target - q_values[action_idx]

        # Update
        q_values[action_idx] += self.lr * td_error

        self._total_steps += 1
        self._total_reward += reward

        return float(abs(td_error))

    def get_best_plan(self, state_features: np.ndarray,
                      horizon: int = 5) -> List[str]:
        """
        Generate a plan of actions by greedily following Q-values.

        This simulates forward planning by assuming state transitions
        are deterministic and using the current Q-table to pick the
        best action at each step.

        Args:
            state_features: Current state features.
            horizon: Number of steps to plan ahead.

        Returns:
            List of action names.
        """
        plan = []
        current_features = np.asarray(state_features, dtype=np.float64).copy()

        for _ in range(horizon):
            state = self._discretize(current_features)
            q_values = self._get_q_values(state)

            # Pick best action (no exploration in planning)
            action_idx = int(np.argmax(q_values))
            action = ACTIONS[action_idx]
            plan.append(action)

            # Simulate state transition (small perturbation based on action)
            # This is a heuristic since we don't have a learned transition model
            delta = np.zeros(self._feature_dim, dtype=np.float64)
            if action == 'explore_domain':
                delta[0] += 0.5  # Increase node count feature
            elif action == 'deepen_knowledge':
                delta[1] += 0.3  # Increase edge density feature
            elif action == 'verify_predictions':
                delta[2] += 0.2  # Increase prediction accuracy feature
            elif action == 'seek_contradictions':
                delta[3] += 0.4  # Increase contradiction feature
            elif action == 'create_hypotheses':
                delta[4] += 0.3  # Increase hypothesis count
            elif action == 'consolidate_memory':
                delta[5] += 0.2  # Increase memory coherence

            padded = current_features.copy()
            if padded.shape[0] < self._feature_dim:
                padded = np.pad(padded, (0, self._feature_dim - padded.shape[0]))
            padded[:self._feature_dim] += delta
            current_features = padded

        return plan

    def extract_state_features(self, kg_stats: Dict[str, Any]) -> np.ndarray:
        """
        Extract state features from knowledge graph statistics.

        Creates an 8-dimensional feature vector from KG metrics.
        """
        features = np.zeros(self._feature_dim, dtype=np.float64)
        features[0] = kg_stats.get('total_nodes', 0) / 1000.0  # normalized node count
        features[1] = kg_stats.get('total_edges', 0) / 5000.0  # normalized edge count
        features[2] = kg_stats.get('edge_density', 0)
        features[3] = kg_stats.get('avg_confidence', 0)
        features[4] = kg_stats.get('domain_count', 0) / 10.0
        features[5] = kg_stats.get('prediction_accuracy', 0)
        features[6] = kg_stats.get('contradiction_count', 0) / 100.0
        features[7] = kg_stats.get('hypothesis_count', 0) / 100.0
        return features

    def get_stats(self) -> Dict[str, Any]:
        """Return RL planner statistics."""
        avg_reward = (self._total_reward / self._total_steps
                      if self._total_steps > 0 else 0.0)
        return {
            'total_steps': self._total_steps,
            'total_reward': round(self._total_reward, 4),
            'avg_reward': round(avg_reward, 4),
            'epsilon': round(self.epsilon, 4),
            'q_table_size': len(self._q_table),
            'action_counts': dict(self._action_counts),
            'last_action': self._last_action,
            'num_state_bins': self.num_state_bins,
        }
