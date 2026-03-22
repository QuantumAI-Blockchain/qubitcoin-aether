"""
Recurrent Sephirot Processing — Item #80
Real recurrent processing between Sephirot nodes with GRU-like gating
and Tree of Life topology connections.
"""
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Tree of Life adjacency (undirected connections between Sephirot)
_TREE_OF_LIFE: Dict[str, List[str]] = {
    "keter":    ["chochmah", "binah", "tiferet"],
    "chochmah": ["keter", "binah", "chesed", "tiferet"],
    "binah":    ["keter", "chochmah", "gevurah", "tiferet"],
    "chesed":   ["chochmah", "gevurah", "tiferet", "netzach"],
    "gevurah":  ["binah", "chesed", "tiferet", "hod"],
    "tiferet":  ["keter", "chesed", "gevurah", "netzach", "hod", "yesod"],
    "netzach":  ["chesed", "tiferet", "hod", "yesod", "malkuth"],
    "hod":      ["gevurah", "tiferet", "netzach", "yesod", "malkuth"],
    "yesod":    ["tiferet", "netzach", "hod", "malkuth"],
    "malkuth":  ["netzach", "hod", "yesod"],
}

SEPHIROT_NAMES = list(_TREE_OF_LIFE.keys())


class SephirotRecurrent:
    """Recurrent processing between Sephirot with GRU-like gates.

    Each Sephirah has a state vector.  At each step, the state is
    updated via a GRU gate that mixes the previous state with
    messages aggregated from connected Sephirot on the Tree of Life.
    """

    def __init__(self, dim: int = 16, learning_rate: float = 0.01) -> None:
        self._dim = dim
        self._lr = learning_rate
        rng = np.random.default_rng(42)

        # State vectors per Sephirah
        self._states: Dict[str, np.ndarray] = {
            name: rng.normal(0, 0.1, dim).astype(np.float64)
            for name in SEPHIROT_NAMES
        }

        # GRU parameters per Sephirah (update gate, reset gate, candidate)
        self._Wz: Dict[str, np.ndarray] = {}  # update gate
        self._Wr: Dict[str, np.ndarray] = {}  # reset gate
        self._Wh: Dict[str, np.ndarray] = {}  # candidate
        for name in SEPHIROT_NAMES:
            in_dim = dim * 2  # [state; neighbor_aggregate]
            self._Wz[name] = rng.normal(0, 0.1, (dim, in_dim)).astype(np.float64)
            self._Wr[name] = rng.normal(0, 0.1, (dim, in_dim)).astype(np.float64)
            self._Wh[name] = rng.normal(0, 0.1, (dim, in_dim)).astype(np.float64)

        self._steps_total: int = 0
        self._convergence_runs: int = 0
        self._avg_convergence_steps: float = 0.0

    # ------------------------------------------------------------------
    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -15, 15)))

    # ------------------------------------------------------------------
    def step(
        self, inputs: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Run one recurrent processing step.

        Args:
            inputs: Optional external input per Sephirah.  Missing names
                    receive zero input.

        Returns:
            Updated state vectors per Sephirah.
        """
        self._steps_total += 1
        new_states: Dict[str, np.ndarray] = {}

        for name in SEPHIROT_NAMES:
            h_prev = self._states[name]

            # Aggregate neighbour states
            neighbours = _TREE_OF_LIFE[name]
            if neighbours:
                agg = np.mean(
                    [self._states[n] for n in neighbours], axis=0
                )
            else:
                agg = np.zeros(self._dim, dtype=np.float64)

            # Add external input
            ext = inputs.get(name, np.zeros(self._dim, dtype=np.float64))
            ext = np.asarray(ext, dtype=np.float64).ravel()
            if len(ext) < self._dim:
                ext = np.pad(ext, (0, self._dim - len(ext)))
            else:
                ext = ext[:self._dim]
            agg = agg + ext

            # GRU update
            concat = np.concatenate([h_prev, agg])
            z = self._sigmoid(self._Wz[name] @ concat)  # update gate
            r = self._sigmoid(self._Wr[name] @ concat)  # reset gate
            concat_reset = np.concatenate([r * h_prev, agg])
            h_cand = np.tanh(self._Wh[name] @ concat_reset)  # candidate
            new_states[name] = (1 - z) * h_prev + z * h_cand

        self._states = new_states
        return {k: v.copy() for k, v in new_states.items()}

    # ------------------------------------------------------------------
    def run_to_convergence(
        self,
        inputs: Dict[str, np.ndarray],
        max_steps: int = 10,
        threshold: float = 0.01,
    ) -> Dict[str, np.ndarray]:
        """Run steps until convergence or *max_steps*.

        Convergence = max state change across all Sephirot < threshold.
        """
        self._convergence_runs += 1
        for i in range(max_steps):
            prev = {k: v.copy() for k, v in self._states.items()}
            self.step(inputs)
            max_change = max(
                float(np.max(np.abs(self._states[k] - prev[k])))
                for k in SEPHIROT_NAMES
            )
            if max_change < threshold:
                steps_taken = i + 1
                # Update running average
                self._avg_convergence_steps = (
                    0.9 * self._avg_convergence_steps + 0.1 * steps_taken
                )
                return {k: v.copy() for k, v in self._states.items()}

        self._avg_convergence_steps = (
            0.9 * self._avg_convergence_steps + 0.1 * max_steps
        )
        return {k: v.copy() for k, v in self._states.items()}

    # ------------------------------------------------------------------
    def get_state(self, name: str) -> Optional[np.ndarray]:
        return self._states.get(name)

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        state_norms = {
            k: float(np.linalg.norm(v)) for k, v in self._states.items()
        }
        return {
            "dim": self._dim,
            "steps_total": self._steps_total,
            "convergence_runs": self._convergence_runs,
            "avg_convergence_steps": round(self._avg_convergence_steps, 2),
            "state_norms": state_norms,
        }
