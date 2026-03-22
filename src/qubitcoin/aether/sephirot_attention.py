"""
Multi-Head Attention for Sephirot Routing — Item #35

Learned attention mechanism that routes messages between the 10 Sephirot
cognitive nodes. Uses multi-head attention (4 heads) with learnable
key/query/value matrices per Sephirah, reinforced by outcome feedback.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

# The 10 Sephirot in Tree of Life order
SEPHIROT_NAMES: List[str] = [
    'Keter', 'Chochmah', 'Binah', 'Chesed', 'Gevurah',
    'Tiferet', 'Netzach', 'Hod', 'Yesod', 'Malkuth',
]
NUM_SEPHIROT = len(SEPHIROT_NAMES)


class SephirotAttention:
    """Multi-head attention router for inter-Sephirot message passing."""

    def __init__(self, embed_dim: int = 32, num_heads: int = 4,
                 temperature: float = 1.0, lr: float = 0.005) -> None:
        """Initialize attention routing matrices.

        Args:
            embed_dim: Dimension of message embeddings.
            num_heads: Number of attention heads.
            temperature: Softmax temperature (lower = sharper routing).
            lr: Learning rate for reinforcement updates.
        """
        self._embed_dim = embed_dim
        self._num_heads = num_heads
        self._temperature = temperature
        self._lr = lr
        self._head_dim = embed_dim // num_heads
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads"

        rng = np.random.default_rng(42)
        scale = 0.1

        # Per-Sephirah learnable matrices: W_Q, W_K, W_V
        # Shape: (num_sephirot, num_heads, head_dim, head_dim)
        self._W_Q = rng.normal(0, scale, (NUM_SEPHIROT, num_heads, self._head_dim, self._head_dim))
        self._W_K = rng.normal(0, scale, (NUM_SEPHIROT, num_heads, self._head_dim, self._head_dim))
        self._W_V = rng.normal(0, scale, (NUM_SEPHIROT, num_heads, self._head_dim, self._head_dim))

        # Output projection per Sephirah
        self._W_O = rng.normal(0, scale, (NUM_SEPHIROT, embed_dim, embed_dim))

        # Sephirah position embeddings (added to messages from that source)
        self._position_emb = rng.normal(0, 0.02, (NUM_SEPHIROT, embed_dim))

        # Name-to-index mapping
        self._name_to_idx: Dict[str, int] = {
            name: i for i, name in enumerate(SEPHIROT_NAMES)
        }

        # Stats
        self._routes_computed: int = 0
        self._train_steps: int = 0
        self._total_reward: float = 0.0
        self._route_history: List[Dict[str, float]] = []
        self._max_history: int = 1000

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Temperature-scaled softmax."""
        x_scaled = x / max(self._temperature, 1e-6)
        x_shifted = x_scaled - np.max(x_scaled)
        exp_x = np.exp(x_shifted)
        return exp_x / (np.sum(exp_x) + 1e-12)

    def route_message(self, message_embedding: np.ndarray,
                      source_sephirah: str) -> Dict[str, float]:
        """Route a message from source Sephirah to all 10 Sephirot.

        Computes multi-head attention scores from the source to each
        target Sephirah and returns normalized routing weights.

        Args:
            message_embedding: Message vector of shape (embed_dim,).
            source_sephirah: Name of the source Sephirah (e.g. 'Keter').

        Returns:
            Dict mapping Sephirah name to attention weight (0-1, sums to 1).
        """
        src_idx = self._name_to_idx.get(source_sephirah)
        if src_idx is None:
            logger.warning(f"Unknown source Sephirah: {source_sephirah}")
            # Uniform routing fallback
            return {name: 1.0 / NUM_SEPHIROT for name in SEPHIROT_NAMES}

        msg = np.asarray(message_embedding, dtype=np.float64).flatten()
        if msg.shape[0] != self._embed_dim:
            # Pad or truncate
            if msg.shape[0] < self._embed_dim:
                msg = np.pad(msg, (0, self._embed_dim - msg.shape[0]))
            else:
                msg = msg[:self._embed_dim]

        # Add source position embedding
        msg = msg + self._position_emb[src_idx]

        # Split into heads: (num_heads, head_dim)
        msg_heads = msg.reshape(self._num_heads, self._head_dim)

        # Compute query from source
        # query[h] = msg_heads[h] @ W_Q[src, h]
        queries = np.zeros((self._num_heads, self._head_dim))
        for h in range(self._num_heads):
            queries[h] = msg_heads[h] @ self._W_Q[src_idx, h]

        # Compute key and value for each target Sephirah
        attention_scores = np.zeros(NUM_SEPHIROT)
        for tgt_idx in range(NUM_SEPHIROT):
            # Target key embedding = position embedding projected through W_K
            tgt_emb = self._position_emb[tgt_idx]
            tgt_heads = tgt_emb.reshape(self._num_heads, self._head_dim)

            head_scores = np.zeros(self._num_heads)
            for h in range(self._num_heads):
                key = tgt_heads[h] @ self._W_K[tgt_idx, h]
                # Scaled dot-product attention
                score = np.dot(queries[h], key) / np.sqrt(self._head_dim)
                head_scores[h] = score

            # Average across heads
            attention_scores[tgt_idx] = np.mean(head_scores)

        # Softmax to get routing weights
        weights = self._softmax(attention_scores)

        result = {
            SEPHIROT_NAMES[i]: float(weights[i])
            for i in range(NUM_SEPHIROT)
        }

        self._routes_computed += 1
        if len(self._route_history) < self._max_history:
            self._route_history.append(result)

        return result

    def train_on_outcome(self, source: str, targets: Dict[str, float],
                         reward: float) -> None:
        """Reinforce routing weights based on outcome feedback.

        Uses a simple policy gradient update: increase weights for
        targets that received messages when reward is positive,
        decrease when negative.

        Args:
            source: Source Sephirah name.
            targets: The routing weights that were used.
            reward: Positive = good routing, negative = bad routing.
        """
        src_idx = self._name_to_idx.get(source)
        if src_idx is None:
            return

        self._train_steps += 1
        self._total_reward += reward

        # Policy gradient: adjust position embeddings toward/away from targets
        for name, weight in targets.items():
            tgt_idx = self._name_to_idx.get(name)
            if tgt_idx is None:
                continue

            # Gradient: reward * (weight - uniform_prob) * position_embedding_diff
            advantage = reward * (weight - 1.0 / NUM_SEPHIROT)
            gradient = advantage * self._lr

            # Update position embeddings to encourage/discourage this routing
            self._position_emb[tgt_idx] += gradient * self._position_emb[src_idx]

            # Update W_Q for source to change query projection
            for h in range(self._num_heads):
                self._W_Q[src_idx, h] += gradient * 0.1 * np.outer(
                    self._position_emb[src_idx].reshape(self._num_heads, self._head_dim)[h],
                    self._position_emb[tgt_idx].reshape(self._num_heads, self._head_dim)[h],
                )

        # Clip weights to prevent explosion
        clip_val = 3.0
        self._W_Q = np.clip(self._W_Q, -clip_val, clip_val)
        self._W_K = np.clip(self._W_K, -clip_val, clip_val)
        self._position_emb = np.clip(self._position_emb, -2.0, 2.0)

    def set_temperature(self, temperature: float) -> None:
        """Set softmax temperature for sharper or softer routing.

        Args:
            temperature: > 1.0 = softer (more uniform),
                         < 1.0 = sharper (more peaked).
        """
        self._temperature = max(temperature, 0.01)

    def get_top_routes(self, source: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Get top-k most likely routing targets for a source Sephirah.

        Args:
            source: Source Sephirah name.
            top_k: Number of top targets to return.

        Returns:
            List of (sephirah_name, weight) tuples sorted by weight descending.
        """
        # Use a dummy message to get current routing preferences
        dummy = self._position_emb[self._name_to_idx.get(source, 0)]
        weights = self.route_message(dummy, source)
        sorted_routes = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        return sorted_routes[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        """Return attention router statistics."""
        avg_entropy = 0.0
        if self._route_history:
            entropies = []
            for route in self._route_history[-100:]:
                probs = np.array(list(route.values()))
                probs = probs[probs > 0]
                entropy = -np.sum(probs * np.log(probs + 1e-12))
                entropies.append(entropy)
            avg_entropy = float(np.mean(entropies))

        return {
            'routes_computed': self._routes_computed,
            'train_steps': self._train_steps,
            'total_reward': round(self._total_reward, 4),
            'avg_reward': round(self._total_reward / max(self._train_steps, 1), 4),
            'temperature': self._temperature,
            'embed_dim': self._embed_dim,
            'num_heads': self._num_heads,
            'avg_routing_entropy': round(avg_entropy, 4),
            'sephirot_count': NUM_SEPHIROT,
        }
