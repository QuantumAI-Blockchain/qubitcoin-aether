"""
Attention-based Working Memory (Item #24)

Content-addressable memory with attention-based read/write operations.
Replaces LRU eviction with importance-weighted eviction and supports
memory consolidation (merging similar entries, decaying old ones).
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax over a 1D array."""
    e = np.exp(x - np.max(x))
    return e / (e.sum() + 1e-12)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class MemorySlot:
    """Single memory entry with key, value, metadata, and importance."""

    __slots__ = ('key', 'value', 'metadata', 'importance', 'access_count',
                 'created_at', 'last_accessed')

    def __init__(self, key: np.ndarray, value: np.ndarray,
                 metadata: Dict[str, Any], importance: float = 1.0) -> None:
        self.key = key.astype(np.float64)
        self.value = value.astype(np.float64)
        self.metadata = metadata
        self.importance = importance
        self.access_count: int = 0
        self.created_at: float = time.time()
        self.last_accessed: float = time.time()


class AttentionMemory:
    """
    Content-addressable working memory with attention-based read/write.

    Features:
    - Write: stores key-value pairs with metadata
    - Read: attention-weighted retrieval (softmax(Q @ K^T / sqrt(d)))
    - Consolidation: merge similar memories, decay old ones
    - Eviction: importance-weighted (not LRU)
    """

    def __init__(self, dim: int = 64, capacity: int = 1000,
                 similarity_threshold: float = 0.85,
                 decay_rate: float = 0.995) -> None:
        self.dim = dim
        self.capacity = capacity
        self.similarity_threshold = similarity_threshold
        self.decay_rate = decay_rate

        self._slots: List[MemorySlot] = []

        # Stats
        self._total_writes: int = 0
        self._total_reads: int = 0
        self._total_evictions: int = 0
        self._total_consolidations: int = 0
        self._total_merges: int = 0
        self._created_at: float = time.time()

    def _project(self, vec: np.ndarray) -> np.ndarray:
        """Ensure vector matches memory dimension."""
        vec = np.asarray(vec, dtype=np.float64).flatten()
        if vec.shape[0] < self.dim:
            vec = np.pad(vec, (0, self.dim - vec.shape[0]))
        elif vec.shape[0] > self.dim:
            vec = vec[:self.dim]
        return vec

    def write(self, key: np.ndarray, value: np.ndarray,
              metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Write a key-value pair into memory.

        If a very similar key already exists, update it instead of creating
        a new entry (content-addressable deduplication).
        """
        key = self._project(key)
        value = self._project(value)
        metadata = metadata or {}
        self._total_writes += 1

        # Check for existing similar key
        for slot in self._slots:
            sim = _cosine_sim(key, slot.key)
            if sim > self.similarity_threshold:
                # Update existing: blend values, boost importance
                alpha = 0.3  # blend factor for new data
                slot.value = (1 - alpha) * slot.value + alpha * value
                slot.key = (1 - alpha) * slot.key + alpha * key
                slot.importance = min(slot.importance + 0.1, 10.0)
                slot.last_accessed = time.time()
                slot.access_count += 1
                slot.metadata.update(metadata)
                return

        # Create new slot
        slot = MemorySlot(key, value, metadata)
        self._slots.append(slot)

        # Evict if over capacity
        if len(self._slots) > self.capacity:
            self._evict()

    def read(self, query: np.ndarray, top_k: int = 5) -> List[Tuple[np.ndarray, float, Dict[str, Any]]]:
        """
        Attention-based read: retrieve top-k memories most relevant to query.

        Returns list of (value, attention_weight, metadata) tuples.
        """
        self._total_reads += 1

        if not self._slots:
            return []

        query = self._project(query)
        scale = np.sqrt(self.dim)

        # Compute attention scores: softmax(query @ keys^T / sqrt(d))
        keys = np.stack([s.key for s in self._slots])  # (N, dim)
        scores = keys @ query / scale  # (N,)

        # Weight by importance
        importances = np.array([s.importance for s in self._slots])
        scores = scores * np.log1p(importances)

        attn_weights = _softmax(scores)

        # Get top-k indices
        k = min(top_k, len(self._slots))
        top_indices = np.argsort(attn_weights)[-k:][::-1]

        results = []
        for idx in top_indices:
            slot = self._slots[idx]
            slot.access_count += 1
            slot.last_accessed = time.time()
            slot.importance += 0.01  # slight boost for access
            results.append((
                slot.value.copy(),
                float(attn_weights[idx]),
                dict(slot.metadata),
            ))

        return results

    def _evict(self) -> None:
        """Importance-weighted eviction: remove the least important memory."""
        if not self._slots:
            return

        # Score = importance * recency_factor * access_factor
        now = time.time()
        scores = []
        for slot in self._slots:
            age = now - slot.created_at + 1.0
            recency = 1.0 / (now - slot.last_accessed + 1.0)
            score = slot.importance * recency * np.log1p(slot.access_count)
            scores.append(score)

        # Remove the lowest-scoring entry
        worst_idx = int(np.argmin(scores))
        self._slots.pop(worst_idx)
        self._total_evictions += 1

    def consolidate(self) -> int:
        """
        Merge similar memories and decay old ones.

        Returns number of merges performed.
        """
        self._total_consolidations += 1
        merges = 0
        now = time.time()

        # Decay importance of all entries
        for slot in self._slots:
            age_hours = (now - slot.last_accessed) / 3600.0
            slot.importance *= self.decay_rate ** age_hours

        # Remove very low-importance entries
        before = len(self._slots)
        self._slots = [s for s in self._slots if s.importance > 0.01]
        removed = before - len(self._slots)
        self._total_evictions += removed

        # Merge highly similar entries
        if len(self._slots) < 2:
            return merges

        merged_indices = set()
        new_slots = []

        for i in range(len(self._slots)):
            if i in merged_indices:
                continue
            slot_i = self._slots[i]
            merged_with = []

            for j in range(i + 1, len(self._slots)):
                if j in merged_indices:
                    continue
                sim = _cosine_sim(slot_i.key, self._slots[j].key)
                if sim > self.similarity_threshold:
                    merged_with.append(j)
                    merged_indices.add(j)

            if merged_with:
                # Merge all similar slots into slot_i
                all_slots = [slot_i] + [self._slots[j] for j in merged_with]
                weights = np.array([s.importance for s in all_slots])
                weights = weights / (weights.sum() + 1e-12)

                merged_key = sum(w * s.key for w, s in zip(weights, all_slots))
                merged_value = sum(w * s.value for w, s in zip(weights, all_slots))
                merged_importance = max(s.importance for s in all_slots) * 1.1
                merged_meta = {}
                for s in all_slots:
                    merged_meta.update(s.metadata)
                merged_meta['merge_count'] = merged_meta.get('merge_count', 0) + len(merged_with)

                new_slot = MemorySlot(merged_key, merged_value, merged_meta, merged_importance)
                new_slot.access_count = sum(s.access_count for s in all_slots)
                new_slot.last_accessed = max(s.last_accessed for s in all_slots)
                new_slots.append(new_slot)
                merges += len(merged_with)
            else:
                new_slots.append(slot_i)

        self._slots = new_slots
        self._total_merges += merges
        return merges

    def size(self) -> int:
        """Current number of memory slots."""
        return len(self._slots)

    def clear(self) -> None:
        """Clear all memory."""
        self._slots.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Return attention memory statistics."""
        avg_importance = (
            float(np.mean([s.importance for s in self._slots]))
            if self._slots else 0.0
        )
        return {
            'dim': self.dim,
            'capacity': self.capacity,
            'current_size': len(self._slots),
            'total_writes': self._total_writes,
            'total_reads': self._total_reads,
            'total_evictions': self._total_evictions,
            'total_consolidations': self._total_consolidations,
            'total_merges': self._total_merges,
            'avg_importance': round(avg_importance, 4),
            'similarity_threshold': self.similarity_threshold,
            'decay_rate': self.decay_rate,
        }
