"""
Modern Hopfield Network for Associative Memory — Pattern Completion in KG

AGI Roadmap Item #40: Implements a modern (exponential) Hopfield network
for associative memory and pattern completion over knowledge graph nodes.

Unlike classical Hopfield (binary, quadratic energy), modern Hopfield uses
continuous patterns with exponential storage capacity. Given a partial
query, it retrieves the closest stored pattern — enabling:
  - Pattern completion: partial knowledge → full context
  - Content-addressable memory: retrieve by similarity
  - Attention-like retrieval: soft association across stored patterns

Reference: Ramsauer et al., "Hopfield Networks is All You Need" (2021)

Uses only numpy — no PyTorch dependency.
"""
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ModernHopfield:
    """Modern Hopfield network with exponential storage capacity.

    Stores patterns as rows in a memory matrix. Retrieval uses
    softmax attention: output = softmax(beta * query @ memory.T) @ memory

    This provides:
      - Exponential storage capacity (exp(d) patterns vs d for classical)
      - One-step convergence (no iterative dynamics needed)
      - Soft retrieval (weighted combination of similar patterns)
    """

    def __init__(self, dim: int = 32, beta: float = 8.0,
                 max_patterns: int = 5000) -> None:
        """Initialize Modern Hopfield network.

        Args:
            dim: Dimensionality of stored patterns.
            beta: Inverse temperature for softmax (higher = sharper retrieval).
            max_patterns: Maximum number of stored patterns before eviction.
        """
        self.dim = dim
        self.beta = beta
        self.max_patterns = max_patterns

        # Pattern storage: each row is a stored pattern
        self._patterns: np.ndarray = np.zeros((0, dim), dtype=np.float64)
        # Pattern metadata: maps row index -> (node_id, timestamp)
        self._metadata: List[dict] = []
        # Access counts for LRU eviction
        self._access_counts: np.ndarray = np.zeros(0, dtype=np.int64)
        # Stats
        self._retrievals: int = 0
        self._stores: int = 0

    @property
    def num_patterns(self) -> int:
        return len(self._metadata)

    def store(self, pattern: np.ndarray, node_id: int = -1,
              metadata: Optional[dict] = None) -> int:
        """Store a new pattern in the Hopfield network.

        Args:
            pattern: Feature vector of shape (dim,).
            node_id: Optional KG node ID for cross-reference.
            metadata: Optional metadata dict.

        Returns:
            Index of the stored pattern.
        """
        if pattern.shape != (self.dim,):
            # Pad or truncate to match dim
            padded = np.zeros(self.dim, dtype=np.float64)
            n = min(len(pattern), self.dim)
            padded[:n] = pattern[:n]
            pattern = padded

        # Normalize
        norm = np.linalg.norm(pattern)
        if norm > 0:
            pattern = pattern / norm

        # Evict if at capacity (LRU: remove least accessed)
        if self.num_patterns >= self.max_patterns:
            evict_idx = int(np.argmin(self._access_counts))
            self._patterns[evict_idx] = pattern
            self._metadata[evict_idx] = {
                'node_id': node_id,
                **(metadata or {}),
            }
            self._access_counts[evict_idx] = 0
            self._stores += 1
            return evict_idx

        # Append new pattern
        if self.num_patterns == 0:
            self._patterns = pattern.reshape(1, -1)
        else:
            self._patterns = np.vstack([self._patterns, pattern.reshape(1, -1)])

        self._metadata.append({
            'node_id': node_id,
            **(metadata or {}),
        })
        self._access_counts = np.append(self._access_counts, 0)
        self._stores += 1
        return self.num_patterns - 1

    def retrieve(self, query: np.ndarray, top_k: int = 5) -> List[Tuple[int, float, dict]]:
        """Retrieve patterns most similar to the query.

        Uses modern Hopfield retrieval: softmax(beta * query @ memory.T).
        Returns top-k patterns by attention weight.

        Args:
            query: Query vector of shape (dim,).
            top_k: Number of patterns to retrieve.

        Returns:
            List of (pattern_index, attention_weight, metadata) tuples.
        """
        if self.num_patterns == 0:
            return []

        self._retrievals += 1

        # Normalize query
        if query.shape != (self.dim,):
            padded = np.zeros(self.dim, dtype=np.float64)
            n = min(len(query), self.dim)
            padded[:n] = query[:n]
            query = padded

        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        # Compute attention scores: softmax(beta * query @ memory.T)
        logits = self.beta * (self._patterns @ query)

        # Numerically stable softmax
        logits_max = np.max(logits)
        exp_logits = np.exp(logits - logits_max)
        attn_weights = exp_logits / (np.sum(exp_logits) + 1e-10)

        # Get top-k
        top_indices = np.argsort(attn_weights)[-top_k:][::-1]
        results = []
        for idx in top_indices:
            idx = int(idx)
            weight = float(attn_weights[idx])
            meta = self._metadata[idx] if idx < len(self._metadata) else {}
            results.append((idx, weight, meta))
            self._access_counts[idx] += 1

        return results

    def retrieve_soft(self, query: np.ndarray) -> np.ndarray:
        """Soft retrieval: return weighted combination of all patterns.

        This is the modern Hopfield update rule:
        output = softmax(beta * query @ memory.T) @ memory

        Useful for pattern completion — the output fills in missing
        features from stored patterns.
        """
        if self.num_patterns == 0:
            return np.zeros(self.dim, dtype=np.float64)

        if query.shape != (self.dim,):
            padded = np.zeros(self.dim, dtype=np.float64)
            n = min(len(query), self.dim)
            padded[:n] = query[:n]
            query = padded

        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        logits = self.beta * (self._patterns @ query)
        logits_max = np.max(logits)
        exp_logits = np.exp(logits - logits_max)
        attn_weights = exp_logits / (np.sum(exp_logits) + 1e-10)

        # Weighted sum of stored patterns
        output = attn_weights @ self._patterns
        return output

    def pattern_completion(self, partial: np.ndarray,
                           mask: Optional[np.ndarray] = None,
                           iterations: int = 3) -> np.ndarray:
        """Complete a partial pattern using iterative retrieval.

        Args:
            partial: Partial pattern vector.
            mask: Binary mask (1 = known, 0 = unknown). If None, treats
                  zero entries as unknown.
            iterations: Number of retrieval iterations for convergence.

        Returns:
            Completed pattern vector.
        """
        if self.num_patterns == 0:
            return partial.copy()

        if mask is None:
            mask = (np.abs(partial) > 1e-6).astype(np.float64)

        current = partial.copy()
        for _ in range(iterations):
            retrieved = self.retrieve_soft(current)
            # Keep known parts, fill unknown from retrieval
            current = mask * partial + (1.0 - mask) * retrieved

        return current

    def store_kg_node(self, node: object, feature_extractor: Optional[object] = None) -> int:
        """Store a KG node as a pattern.

        Extracts features from the node and stores them. Uses a simple
        hash-based feature representation if no extractor is provided.
        """
        features = np.zeros(self.dim, dtype=np.float64)

        if feature_extractor and hasattr(feature_extractor, '_extract_node_features'):
            try:
                raw = feature_extractor._extract_node_features(node)
                if raw is not None:
                    arr = np.array(raw, dtype=np.float64).ravel()
                    n = min(len(arr), self.dim)
                    features[:n] = arr[:n]
            except Exception:
                pass

        if np.linalg.norm(features) < 1e-10:
            # Fallback: hash-based features from node content
            node_id = getattr(node, 'node_id', 0)
            conf = getattr(node, 'confidence', 0.5)
            node_type = getattr(node, 'node_type', 'unknown')

            # Simple deterministic features
            np.random.seed(hash(str(node_id)) % (2**31))
            features = np.random.randn(self.dim).astype(np.float64) * 0.1
            features[0] = conf
            features[1] = hash(node_type) % 100 / 100.0
            np.random.seed(None)  # Reset seed

        meta = {
            'node_id': getattr(node, 'node_id', -1),
            'node_type': getattr(node, 'node_type', 'unknown'),
            'confidence': getattr(node, 'confidence', 0.0),
        }

        return self.store(features, node_id=meta['node_id'], metadata=meta)

    def get_stats(self) -> dict:
        return {
            'num_patterns': self.num_patterns,
            'max_patterns': self.max_patterns,
            'dim': self.dim,
            'beta': self.beta,
            'total_stores': self._stores,
            'total_retrievals': self._retrievals,
        }
