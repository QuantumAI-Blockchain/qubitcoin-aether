"""
#74: Prioritized Experience Replay

Priority-based replay buffer for neural training.  Uses a sum-tree
for O(log n) proportional sampling and importance sampling weights
to correct for bias.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

_EPSILON = 1e-6  # Small constant to avoid zero priority
_ALPHA = 0.6     # Prioritization exponent (0 = uniform, 1 = full priority)
_BETA_START = 0.4
_BETA_ANNEAL = 1e-5


class SumTree:
    """Binary sum tree for O(log n) proportional sampling."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._tree: np.ndarray = np.zeros(2 * capacity - 1, dtype=np.float64)
        self._data: List[Optional[dict]] = [None] * capacity
        self._write_idx: int = 0
        self._size: int = 0

    @property
    def total(self) -> float:
        return float(self._tree[0])

    def add(self, priority: float, data: dict) -> int:
        """Add an experience with given priority. Returns the index."""
        idx = self._write_idx + self.capacity - 1
        self._data[self._write_idx] = data
        self._update(idx, priority)
        ret_idx = self._write_idx
        self._write_idx = (self._write_idx + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)
        return ret_idx

    def _update(self, tree_idx: int, priority: float) -> None:
        change = priority - self._tree[tree_idx]
        self._tree[tree_idx] = priority
        while tree_idx > 0:
            tree_idx = (tree_idx - 1) // 2
            self._tree[tree_idx] += change

    def update_priority(self, data_idx: int, priority: float) -> None:
        tree_idx = data_idx + self.capacity - 1
        self._update(tree_idx, priority)

    def get(self, cumsum: float) -> Tuple[int, float, Optional[dict]]:
        """Find the leaf whose cumulative sum covers `cumsum`.

        Returns (data_idx, priority, data).
        """
        idx = 0
        while idx < self.capacity - 1:
            left = 2 * idx + 1
            right = left + 1
            if cumsum <= self._tree[left]:
                idx = left
            else:
                cumsum -= self._tree[left]
                idx = right
        data_idx = idx - (self.capacity - 1)
        return data_idx, float(self._tree[idx]), self._data[data_idx]

    @property
    def min_priority(self) -> float:
        leaf_start = self.capacity - 1
        leaves = self._tree[leaf_start:leaf_start + self._size]
        if len(leaves) == 0:
            return _EPSILON
        positive = leaves[leaves > 0]
        return float(positive.min()) if len(positive) > 0 else _EPSILON


class ExperienceReplay:
    """Prioritized experience replay buffer."""

    def __init__(
        self,
        capacity: int = 10000,
        alpha: float = _ALPHA,
        beta_start: float = _BETA_START,
        beta_anneal: float = _BETA_ANNEAL,
    ) -> None:
        self._capacity = capacity
        self._alpha = alpha
        self._beta = beta_start
        self._beta_anneal = beta_anneal
        self._tree = SumTree(capacity)
        self._max_priority: float = 1.0

        # Stats
        self._total_stored: int = 0
        self._total_sampled: int = 0
        self._total_updates: int = 0

        logger.info("ExperienceReplay initialized (capacity=%d, alpha=%.2f)", capacity, alpha)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def store(self, experience: dict, td_error: float = 0.0) -> None:
        """Store an experience with priority based on TD error.

        Priority = |TD error| + epsilon, raised to alpha.
        """
        priority = (abs(td_error) + _EPSILON) ** self._alpha
        self._max_priority = max(self._max_priority, priority)
        self._tree.add(priority, experience)
        self._total_stored += 1

    def sample(self, batch_size: int) -> List[dict]:
        """Sample a batch of experiences proportional to priority.

        Returns list of dicts, each containing:
            - original experience fields
            - '_replay_idx': int (for updating priority)
            - '_replay_weight': float (importance sampling weight)
        """
        if self._tree._size == 0:
            return []

        batch_size = min(batch_size, self._tree._size)
        segment = self._tree.total / max(batch_size, 1)

        # Anneal beta toward 1
        self._beta = min(1.0, self._beta + self._beta_anneal)

        min_prob = self._tree.min_priority / max(self._tree.total, _EPSILON)
        max_weight = (min_prob * self._tree._size) ** (-self._beta) if min_prob > 0 else 1.0

        batch: List[dict] = []
        for i in range(batch_size):
            low = segment * i
            high = segment * (i + 1)
            cumsum = np.random.uniform(low, high)
            data_idx, priority, data = self._tree.get(cumsum)

            if data is None:
                continue

            # Importance sampling weight
            prob = priority / max(self._tree.total, _EPSILON)
            weight = (prob * self._tree._size) ** (-self._beta) / max(max_weight, _EPSILON)

            entry = dict(data)
            entry['_replay_idx'] = data_idx
            entry['_replay_weight'] = weight
            batch.append(entry)

        self._total_sampled += len(batch)
        return batch

    def update_priority(self, idx: int, new_td_error: float) -> None:
        """Update priority for an experience after training."""
        priority = (abs(new_td_error) + _EPSILON) ** self._alpha
        self._max_priority = max(self._max_priority, priority)
        self._tree.update_priority(idx, priority)
        self._total_updates += 1

    @property
    def size(self) -> int:
        return self._tree._size

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        return {
            'capacity': self._capacity,
            'current_size': self._tree._size,
            'total_stored': self._total_stored,
            'total_sampled': self._total_sampled,
            'total_updates': self._total_updates,
            'max_priority': round(self._max_priority, 6),
            'beta': round(self._beta, 4),
        }
