"""
#66: Curiosity-Driven Exploration Engine

Intrinsic motivation system that uses prediction error as a curiosity
signal.  A lightweight forward model predicts the next state from the
current state + action; the magnitude of the prediction error drives
exploration towards novel, information-rich regions of the knowledge
space.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Forward model parameters
# ---------------------------------------------------------------------------
_STATE_DIM = 32
_ACTION_DIM = 8
_LEARNING_RATE = 0.005
_EPSILON = 1e-8


@dataclass
class ExplorationBonus:
    """Tracks per-domain exploration statistics."""
    domain: str
    visit_count: int = 0
    total_curiosity: float = 0.0
    last_visited: float = 0.0


class CuriosityEngine:
    """Intrinsic motivation via prediction-error curiosity."""

    def __init__(
        self,
        state_dim: int = _STATE_DIM,
        action_dim: int = _ACTION_DIM,
        lr: float = _LEARNING_RATE,
        max_history: int = 5000,
    ) -> None:
        self._state_dim = state_dim
        self._action_dim = action_dim
        self._lr = lr
        self._max_history = max_history

        # Forward model: W_forward @ [state; action] + bias -> predicted_next_state
        input_dim = state_dim + action_dim
        self._W_forward: np.ndarray = np.random.randn(state_dim, input_dim).astype(np.float64) * 0.01
        self._b_forward: np.ndarray = np.zeros(state_dim, dtype=np.float64)

        # Per-domain exploration bonuses
        self._domain_bonuses: Dict[str, ExplorationBonus] = {}

        # History of curiosity scores
        self._curiosity_history: List[float] = []
        self._total_computations: int = 0
        self._total_explorations: int = 0
        self._train_steps: int = 0

        logger.info("CuriosityEngine initialized (state_dim=%d, action_dim=%d)", state_dim, action_dim)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def compute_curiosity(
        self, state: np.ndarray, next_state: np.ndarray, action: Optional[np.ndarray] = None,
    ) -> float:
        """Compute curiosity as prediction error.

        Args:
            state: Current state vector (state_dim,).
            next_state: Actual next state vector (state_dim,).
            action: Optional action vector (action_dim,).  Zeros if not given.

        Returns:
            Curiosity score (L2 prediction error).
        """
        state = self._ensure_shape(state, self._state_dim)
        next_state = self._ensure_shape(next_state, self._state_dim)
        if action is None:
            action = np.zeros(self._action_dim, dtype=np.float64)
        else:
            action = self._ensure_shape(action, self._action_dim)

        predicted = self._forward_predict(state, action)
        error = float(np.linalg.norm(predicted - next_state))

        # Online learning: update forward model to reduce future error
        self._update_forward_model(state, action, next_state, predicted)

        self._curiosity_history.append(error)
        if len(self._curiosity_history) > self._max_history:
            self._curiosity_history = self._curiosity_history[-self._max_history:]
        self._total_computations += 1

        return error

    def select_exploration_target(self, candidates: List[dict]) -> dict:
        """Pick the most curious option from a set of candidates.

        Each candidate dict should contain:
            - 'state': np.ndarray or list  (current state proxy)
            - 'next_state': np.ndarray or list  (expected state proxy)
            - 'domain': str  (optional domain label)

        Falls back to the first candidate if none can be scored.

        Returns:
            The candidate dict with highest curiosity score.
        """
        if not candidates:
            return {}

        best_score = -1.0
        best_candidate = candidates[0]

        for cand in candidates:
            state = np.asarray(cand.get('state', np.zeros(self._state_dim)), dtype=np.float64)
            next_state = np.asarray(cand.get('next_state', np.zeros(self._state_dim)), dtype=np.float64)
            score = self.compute_curiosity(state, next_state)

            # Add exploration bonus for under-visited domains
            domain = cand.get('domain', 'general')
            bonus = self._get_exploration_bonus(domain)
            total_score = score + bonus

            if total_score > best_score:
                best_score = total_score
                best_candidate = cand

        self._total_explorations += 1
        # Update domain visit count for winner
        domain = best_candidate.get('domain', 'general')
        self._record_domain_visit(domain, best_score)

        return best_candidate

    def estimate_information_gain(self, candidates: List[dict]) -> List[float]:
        """Estimate information gain (entropy reduction) for each candidate.

        Uses prediction uncertainty as a proxy for information gain:
        higher uncertainty about a candidate means observing it would
        reduce entropy more.

        Returns:
            List of information gain estimates, one per candidate.
        """
        gains: List[float] = []
        for cand in candidates:
            state = np.asarray(cand.get('state', np.zeros(self._state_dim)), dtype=np.float64)
            state = self._ensure_shape(state, self._state_dim)
            action = np.zeros(self._action_dim, dtype=np.float64)

            predicted = self._forward_predict(state, action)
            # Uncertainty = variance of predicted components (higher = more uncertain)
            variance = float(np.var(predicted))
            # Domain novelty bonus
            domain = cand.get('domain', 'general')
            db = self._domain_bonuses.get(domain)
            novelty = 1.0 / (1.0 + (db.visit_count if db else 0))
            gains.append(variance + novelty)

        return gains

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _forward_predict(self, state: np.ndarray, action: np.ndarray) -> np.ndarray:
        """Forward model: predict next state from state + action."""
        x = np.concatenate([state, action])
        return self._W_forward @ x + self._b_forward

    def _update_forward_model(
        self,
        state: np.ndarray,
        action: np.ndarray,
        target: np.ndarray,
        predicted: np.ndarray,
    ) -> None:
        """Single SGD step on the forward model."""
        x = np.concatenate([state, action])
        error = predicted - target  # (state_dim,)
        # Gradient of MSE w.r.t. W and b
        grad_W = np.outer(error, x)
        grad_b = error
        self._W_forward -= self._lr * grad_W
        self._b_forward -= self._lr * grad_b
        self._train_steps += 1

    def _ensure_shape(self, arr: np.ndarray, dim: int) -> np.ndarray:
        arr = np.asarray(arr, dtype=np.float64).ravel()
        if len(arr) < dim:
            arr = np.pad(arr, (0, dim - len(arr)))
        elif len(arr) > dim:
            arr = arr[:dim]
        return arr

    def _get_exploration_bonus(self, domain: str) -> float:
        """Return exploration bonus inversely proportional to visit count."""
        db = self._domain_bonuses.get(domain)
        if db is None:
            return 1.0  # Never visited — maximum bonus
        return 1.0 / (1.0 + db.visit_count)

    def _record_domain_visit(self, domain: str, curiosity: float) -> None:
        if domain not in self._domain_bonuses:
            self._domain_bonuses[domain] = ExplorationBonus(domain=domain)
        db = self._domain_bonuses[domain]
        db.visit_count += 1
        db.total_curiosity += curiosity
        db.last_visited = time.time()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        avg_curiosity = float(np.mean(self._curiosity_history[-100:])) if self._curiosity_history else 0.0
        return {
            'total_computations': self._total_computations,
            'total_explorations': self._total_explorations,
            'train_steps': self._train_steps,
            'avg_curiosity_100': round(avg_curiosity, 6),
            'domains_tracked': len(self._domain_bonuses),
            'history_size': len(self._curiosity_history),
        }
