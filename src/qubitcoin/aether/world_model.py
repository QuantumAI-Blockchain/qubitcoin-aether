"""
World Model — Model-based planning via state prediction.

Simulates outcomes before executing actions using a learned
linear transition model fit from historical state changes.

AI Roadmap Item #58.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Feature names for WorldState vector representation
STATE_FEATURES = [
    "kg_size", "confidence_avg", "phi", "active_goals",
    "recent_accuracy", "reasoning_ops", "edge_count", "contradiction_count",
]


@dataclass
class WorldState:
    """Represents the observable state of the AI system."""
    kg_size: float = 0.0
    confidence_avg: float = 0.5
    phi: float = 0.0
    active_goals: float = 0.0
    recent_accuracy: float = 0.5
    reasoning_ops: float = 0.0
    edge_count: float = 0.0
    contradiction_count: float = 0.0

    def to_vector(self) -> np.ndarray:
        """Convert to numpy feature vector."""
        return np.array([
            self.kg_size, self.confidence_avg, self.phi, self.active_goals,
            self.recent_accuracy, self.reasoning_ops, self.edge_count,
            self.contradiction_count,
        ], dtype=np.float64)

    @classmethod
    def from_vector(cls, vec: np.ndarray) -> "WorldState":
        """Create WorldState from a feature vector."""
        vals = vec.tolist()
        return cls(
            kg_size=vals[0] if len(vals) > 0 else 0.0,
            confidence_avg=vals[1] if len(vals) > 1 else 0.5,
            phi=vals[2] if len(vals) > 2 else 0.0,
            active_goals=vals[3] if len(vals) > 3 else 0.0,
            recent_accuracy=vals[4] if len(vals) > 4 else 0.5,
            reasoning_ops=vals[5] if len(vals) > 5 else 0.0,
            edge_count=vals[6] if len(vals) > 6 else 0.0,
            contradiction_count=vals[7] if len(vals) > 7 else 0.0,
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorldState":
        """Create WorldState from a dict (e.g. KG stats)."""
        return cls(
            kg_size=float(d.get("kg_size", d.get("total_nodes", 0))),
            confidence_avg=float(d.get("confidence_avg", d.get("avg_confidence", 0.5))),
            phi=float(d.get("phi", d.get("phi_value", 0.0))),
            active_goals=float(d.get("active_goals", 0)),
            recent_accuracy=float(d.get("recent_accuracy", 0.5)),
            reasoning_ops=float(d.get("reasoning_ops", d.get("total_operations", 0))),
            edge_count=float(d.get("edge_count", d.get("total_edges", 0))),
            contradiction_count=float(d.get("contradiction_count", 0)),
        )


class WorldModel:
    """Model-based planner that simulates outcomes before execution.

    Uses a learned linear transition model:
        next_state = W @ [state; action_one_hot] + bias
    """

    def __init__(self, lr: float = 0.01, max_history: int = 5000) -> None:
        self._dim: int = len(STATE_FEATURES)
        self._lr: float = lr
        self._max_history: int = max_history

        # Action vocabulary
        self._actions: List[str] = [
            "explore", "reason", "consolidate", "prune",
            "train", "debate", "calibrate", "investigate",
        ]
        self._action_to_idx: Dict[str, int] = {a: i for i, a in enumerate(self._actions)}
        self._n_actions: int = len(self._actions)

        # Linear transition model: W @ [state; action_one_hot] = delta_state
        input_dim = self._dim + self._n_actions
        self._W: np.ndarray = np.random.randn(self._dim, input_dim) * 0.01
        self._bias: np.ndarray = np.zeros(self._dim)

        # History of transitions for batch learning
        self._transitions: List[Tuple[np.ndarray, str, np.ndarray]] = []
        self._train_steps: int = 0
        self._predictions: int = 0
        self._simulations: int = 0

    def _encode_action(self, action: str) -> np.ndarray:
        """One-hot encode an action."""
        vec = np.zeros(self._n_actions, dtype=np.float64)
        idx = self._action_to_idx.get(action, 0)
        vec[idx] = 1.0
        return vec

    def predict_outcome(self, state: WorldState, action: str) -> WorldState:
        """Predict the next state after taking an action.

        Args:
            state: Current world state.
            action: Action name.

        Returns:
            Predicted next state.
        """
        self._predictions += 1
        state_vec = state.to_vector()
        action_vec = self._encode_action(action)
        x = np.concatenate([state_vec, action_vec])
        delta = self._W @ x + self._bias
        next_vec = state_vec + delta
        # Clamp non-negative features
        next_vec = np.maximum(next_vec, 0.0)
        return WorldState.from_vector(next_vec)

    def simulate_plan(self, state: WorldState,
                      actions: List[str]) -> List[WorldState]:
        """Simulate a full plan and return the trajectory.

        Args:
            state: Initial state.
            actions: Sequence of actions to simulate.

        Returns:
            List of states (length = len(actions) + 1, starting with initial).
        """
        self._simulations += 1
        trajectory = [state]
        current = state
        for action in actions:
            current = self.predict_outcome(current, action)
            trajectory.append(current)
        return trajectory

    def evaluate_plan(self, initial: WorldState,
                      trajectory: List[WorldState]) -> float:
        """Score a plan trajectory.

        Higher is better. Rewards:
        - Increasing phi
        - Increasing confidence
        - Increasing KG size
        - Decreasing contradictions
        """
        if len(trajectory) < 2:
            return 0.0

        final = trajectory[-1]
        init = initial

        score = 0.0
        # Phi improvement (most important)
        score += (final.phi - init.phi) * 3.0
        # Confidence improvement
        score += (final.confidence_avg - init.confidence_avg) * 2.0
        # KG growth (normalized)
        if init.kg_size > 0:
            score += (final.kg_size - init.kg_size) / max(init.kg_size, 1.0)
        # Contradiction reduction
        score -= (final.contradiction_count - init.contradiction_count) * 1.5

        return float(score)

    def update_model(self, state_before: WorldState, action: str,
                     state_after: WorldState) -> float:
        """Online learning: update the transition model from an observation.

        Args:
            state_before: State before action.
            action: Action taken.
            state_after: Observed state after action.

        Returns:
            Prediction error (L2 norm of delta).
        """
        state_vec = state_before.to_vector()
        action_vec = self._encode_action(action)
        x = np.concatenate([state_vec, action_vec])

        # Predicted delta
        predicted_delta = self._W @ x + self._bias
        # Actual delta
        actual_delta = state_after.to_vector() - state_vec
        # Error
        error = actual_delta - predicted_delta

        # Gradient descent update
        self._W += self._lr * np.outer(error, x)
        self._bias += self._lr * error

        self._train_steps += 1

        # Store transition
        self._transitions.append((state_vec, action, state_after.to_vector()))
        if len(self._transitions) > self._max_history:
            self._transitions = self._transitions[-self._max_history:]

        return float(np.linalg.norm(error))

    def get_stats(self) -> dict:
        """Return world model statistics."""
        return {
            "predictions": self._predictions,
            "simulations": self._simulations,
            "train_steps": self._train_steps,
            "transitions_stored": len(self._transitions),
            "num_actions": self._n_actions,
            "model_norm": float(np.linalg.norm(self._W)),
        }
