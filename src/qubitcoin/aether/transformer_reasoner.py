"""
Transformer-based Reasoning over Knowledge Graph Sequences (Item #23)

A numpy-only mini-transformer that performs sequence-to-sequence reasoning
over KG node embedding sequences. Uses multi-head self-attention with
sinusoidal positional encoding.
"""
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax."""
    e = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e / (e.sum(axis=axis, keepdims=True) + 1e-12)


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0, x)


def _layer_norm(x: np.ndarray, gamma: np.ndarray, beta: np.ndarray,
                eps: float = 1e-5) -> np.ndarray:
    """Layer normalization over the last axis."""
    mean = x.mean(axis=-1, keepdims=True)
    var = x.var(axis=-1, keepdims=True)
    return gamma * (x - mean) / np.sqrt(var + eps) + beta


class TransformerReasoner:
    """
    Small numpy-only transformer for reasoning over KG node sequences.

    Architecture:
    - Sinusoidal positional encoding
    - Multi-head self-attention (4 heads, dim=64)
    - Feed-forward network with ReLU
    - Layer normalization
    - 2 transformer layers
    """

    def __init__(self, dim: int = 64, num_heads: int = 4,
                 ff_dim: int = 128, num_layers: int = 2,
                 max_seq_len: int = 128, lr: float = 0.001) -> None:
        self.dim = dim
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.ff_dim = ff_dim
        self.num_layers = num_layers
        self.max_seq_len = max_seq_len
        self.lr = lr

        assert dim % num_heads == 0, "dim must be divisible by num_heads"

        # Build positional encoding table
        self._pos_enc = self._sinusoidal_encoding(max_seq_len, dim)

        # Initialize parameters for each layer
        self.layers: List[Dict[str, np.ndarray]] = []
        for _ in range(num_layers):
            layer = self._init_layer()
            self.layers.append(layer)

        # Output projection (sequence -> single vector)
        self.W_out = np.random.randn(dim, dim).astype(np.float64) * 0.02
        self.b_out = np.zeros(dim, dtype=np.float64)

        # Stats tracking
        self._train_steps: int = 0
        self._total_reason_calls: int = 0
        self._total_train_loss: float = 0.0
        self._last_attention_weights: Optional[np.ndarray] = None
        self._created_at: float = time.time()

    def _init_layer(self) -> Dict[str, np.ndarray]:
        """Initialize one transformer layer's parameters."""
        d = self.dim
        ff = self.ff_dim
        scale = 0.02
        return {
            # Multi-head attention: Q, K, V projections
            'W_q': np.random.randn(d, d).astype(np.float64) * scale,
            'W_k': np.random.randn(d, d).astype(np.float64) * scale,
            'W_v': np.random.randn(d, d).astype(np.float64) * scale,
            'W_o': np.random.randn(d, d).astype(np.float64) * scale,
            # Layer norm 1
            'ln1_gamma': np.ones(d, dtype=np.float64),
            'ln1_beta': np.zeros(d, dtype=np.float64),
            # Feed-forward
            'W_ff1': np.random.randn(d, ff).astype(np.float64) * scale,
            'b_ff1': np.zeros(ff, dtype=np.float64),
            'W_ff2': np.random.randn(ff, d).astype(np.float64) * scale,
            'b_ff2': np.zeros(d, dtype=np.float64),
            # Layer norm 2
            'ln2_gamma': np.ones(d, dtype=np.float64),
            'ln2_beta': np.zeros(d, dtype=np.float64),
        }

    def _sinusoidal_encoding(self, max_len: int, dim: int) -> np.ndarray:
        """Generate sinusoidal positional encodings."""
        pe = np.zeros((max_len, dim), dtype=np.float64)
        positions = np.arange(max_len)[:, np.newaxis]
        div_term = np.exp(np.arange(0, dim, 2) * -(np.log(10000.0) / dim))
        pe[:, 0::2] = np.sin(positions * div_term)
        pe[:, 1::2] = np.cos(positions * div_term)
        return pe

    def _multi_head_attention(self, x: np.ndarray,
                              layer: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Multi-head self-attention.
        x: (seq_len, dim)
        Returns: (seq_len, dim), attention_weights (num_heads, seq_len, seq_len)
        """
        seq_len = x.shape[0]
        Q = x @ layer['W_q']  # (seq_len, dim)
        K = x @ layer['W_k']
        V = x @ layer['W_v']

        # Reshape to (num_heads, seq_len, head_dim)
        Q = Q.reshape(seq_len, self.num_heads, self.head_dim).transpose(1, 0, 2)
        K = K.reshape(seq_len, self.num_heads, self.head_dim).transpose(1, 0, 2)
        V = V.reshape(seq_len, self.num_heads, self.head_dim).transpose(1, 0, 2)

        # Scaled dot-product attention
        scale = np.sqrt(self.head_dim)
        scores = np.matmul(Q, K.transpose(0, 2, 1)) / scale  # (heads, seq, seq)
        attn_weights = _softmax(scores, axis=-1)

        # Weighted sum
        attn_out = np.matmul(attn_weights, V)  # (heads, seq, head_dim)
        # Concatenate heads
        attn_out = attn_out.transpose(1, 0, 2).reshape(seq_len, self.dim)

        # Output projection
        out = attn_out @ layer['W_o']
        return out, attn_weights

    def _feed_forward(self, x: np.ndarray,
                      layer: Dict[str, np.ndarray]) -> np.ndarray:
        """Position-wise feed-forward network."""
        h = _relu(x @ layer['W_ff1'] + layer['b_ff1'])
        return h @ layer['W_ff2'] + layer['b_ff2']

    def _forward(self, x: np.ndarray) -> Tuple[np.ndarray, List[np.ndarray]]:
        """
        Forward pass through all transformer layers.
        x: (seq_len, dim)
        Returns: (seq_len, dim), list of attention weights per layer
        """
        seq_len = x.shape[0]
        # Add positional encoding
        x = x + self._pos_enc[:seq_len]

        all_attn = []
        for layer in self.layers:
            # Self-attention + residual + layer norm
            attn_out, attn_w = self._multi_head_attention(x, layer)
            x = _layer_norm(x + attn_out, layer['ln1_gamma'], layer['ln1_beta'])
            all_attn.append(attn_w)

            # Feed-forward + residual + layer norm
            ff_out = self._feed_forward(x, layer)
            x = _layer_norm(x + ff_out, layer['ln2_gamma'], layer['ln2_beta'])

        return x, all_attn

    def reason_over_sequence(self, node_embeddings: List[np.ndarray]) -> np.ndarray:
        """
        Run transformer reasoning over a sequence of KG node embeddings.

        Args:
            node_embeddings: List of numpy arrays, each of shape (dim,) or adaptable.

        Returns:
            Reasoning output vector of shape (dim,).
        """
        self._total_reason_calls += 1

        if not node_embeddings:
            return np.zeros(self.dim, dtype=np.float64)

        # Pad/project embeddings to match dim
        seq = []
        for emb in node_embeddings[:self.max_seq_len]:
            emb = np.asarray(emb, dtype=np.float64).flatten()
            if emb.shape[0] < self.dim:
                emb = np.pad(emb, (0, self.dim - emb.shape[0]))
            elif emb.shape[0] > self.dim:
                emb = emb[:self.dim]
            seq.append(emb)

        x = np.stack(seq)  # (seq_len, dim)
        out, attn_weights = self._forward(x)
        self._last_attention_weights = attn_weights[-1] if attn_weights else None

        # Pool: mean over sequence + output projection
        pooled = out.mean(axis=0)
        result = pooled @ self.W_out + self.b_out
        return result

    def train_step(self, input_seq: List[np.ndarray],
                   target_seq: np.ndarray) -> float:
        """
        One training step with finite-difference gradient approximation.

        Args:
            input_seq: List of input embeddings.
            target_seq: Target output embedding (dim,).

        Returns:
            MSE loss value.
        """
        target = np.asarray(target_seq, dtype=np.float64).flatten()
        if target.shape[0] != self.dim:
            if target.shape[0] < self.dim:
                target = np.pad(target, (0, self.dim - target.shape[0]))
            else:
                target = target[:self.dim]

        # Forward pass
        output = self.reason_over_sequence(input_seq)
        loss = float(np.mean((output - target) ** 2))

        # Gradient approximation via perturbation on output projection
        # (full backprop through attention is expensive; we update W_out analytically)
        # dL/dW_out = dL/doutput * d(output)/dW_out
        # output = pooled @ W_out + b_out => d/dW_out = pooled^T

        # Recompute pooled (cached from last reason call)
        seq = []
        for emb in input_seq[:self.max_seq_len]:
            emb = np.asarray(emb, dtype=np.float64).flatten()
            if emb.shape[0] < self.dim:
                emb = np.pad(emb, (0, self.dim - emb.shape[0]))
            elif emb.shape[0] > self.dim:
                emb = emb[:self.dim]
            seq.append(emb)
        x = np.stack(seq)
        fwd_out, _ = self._forward(x)
        pooled = fwd_out.mean(axis=0)

        # Gradient for output layer
        grad_output = 2.0 * (output - target) / self.dim  # (dim,)
        grad_W_out = np.outer(pooled, grad_output)  # (dim, dim)
        grad_b_out = grad_output

        # SGD update on output projection
        self.W_out -= self.lr * grad_W_out
        self.b_out -= self.lr * grad_b_out

        # Perturbation-based update on attention weights (stochastic)
        # Perturb a random layer's Q/K/V weights
        eps = 1e-4
        layer_idx = self._train_steps % self.num_layers
        layer = self.layers[layer_idx]
        for key in ['W_q', 'W_k', 'W_v']:
            # Random direction perturbation
            direction = np.random.randn(*layer[key].shape) * eps
            # Estimate gradient in this direction
            layer[key] += direction
            out_plus = self.reason_over_sequence(input_seq)
            loss_plus = float(np.mean((out_plus - target) ** 2))
            layer[key] -= direction  # restore
            # Directional derivative
            grad_approx = (loss_plus - loss) / eps
            layer[key] -= self.lr * grad_approx * direction

        self._train_steps += 1
        self._total_train_loss += loss
        return loss

    def get_stats(self) -> Dict[str, Any]:
        """Return transformer reasoner statistics."""
        avg_loss = (self._total_train_loss / self._train_steps
                    if self._train_steps > 0 else 0.0)
        return {
            'dim': self.dim,
            'num_heads': self.num_heads,
            'num_layers': self.num_layers,
            'ff_dim': self.ff_dim,
            'max_seq_len': self.max_seq_len,
            'train_steps': self._train_steps,
            'total_reason_calls': self._total_reason_calls,
            'avg_train_loss': round(avg_loss, 6),
            'has_attention_weights': self._last_attention_weights is not None,
        }
