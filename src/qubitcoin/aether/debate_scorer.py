"""
Neural Debate Scoring (Item #29)

A 2-layer neural network (numpy) that learns to score debate outcomes.
Input features describe argument quality metrics; output is a verdict
(accept/reject/modify) with confidence.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

VERDICTS: List[str] = ['accept', 'reject', 'modify']


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return np.where(
        x >= 0,
        1.0 / (1.0 + np.exp(-x)),
        np.exp(x) / (1.0 + np.exp(x)),
    )


def _softmax(x: np.ndarray) -> np.ndarray:
    """Softmax over 1D array."""
    e = np.exp(x - np.max(x))
    return e / (e.sum() + 1e-12)


class DebateScorer:
    """
    2-layer neural network for scoring debate outcomes.

    Architecture: input(8) -> hidden(16, sigmoid) -> output(3, softmax)
    Training: online SGD with cross-entropy loss.
    """

    def __init__(self, input_dim: int = 8, hidden_dim: int = 16,
                 lr: float = 0.01) -> None:
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = len(VERDICTS)
        self.lr = lr

        # Xavier initialization
        self.W1 = np.random.randn(input_dim, hidden_dim).astype(np.float64) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros(hidden_dim, dtype=np.float64)
        self.W2 = np.random.randn(hidden_dim, self.output_dim).astype(np.float64) * np.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros(self.output_dim, dtype=np.float64)

        # Stats
        self._train_steps: int = 0
        self._total_loss: float = 0.0
        self._total_scores: int = 0
        self._verdict_counts: Dict[str, int] = {v: 0 for v in VERDICTS}
        self._correct_predictions: int = 0
        self._created_at: float = time.time()

    def _forward(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Forward pass.

        Returns: (output_probs, hidden_activations, pre_softmax_logits)
        """
        x = np.asarray(x, dtype=np.float64).flatten()
        if x.shape[0] < self.input_dim:
            x = np.pad(x, (0, self.input_dim - x.shape[0]))
        elif x.shape[0] > self.input_dim:
            x = x[:self.input_dim]

        # Hidden layer
        z1 = x @ self.W1 + self.b1
        h1 = _sigmoid(z1)

        # Output layer
        z2 = h1 @ self.W2 + self.b2
        probs = _softmax(z2)

        return probs, h1, z2

    def score_debate(self, features: np.ndarray) -> Tuple[str, float]:
        """
        Score a debate and return verdict with confidence.

        Args:
            features: 8-dimensional feature vector.

        Returns:
            (verdict_string, confidence) tuple.
        """
        self._total_scores += 1
        probs, _, _ = self._forward(features)
        best_idx = int(np.argmax(probs))
        verdict = VERDICTS[best_idx]
        confidence = float(probs[best_idx])
        self._verdict_counts[verdict] += 1
        return verdict, confidence

    def train_on_outcome(self, features: np.ndarray,
                         actual_verdict: str) -> float:
        """
        Online training: backpropagation with cross-entropy loss.

        Args:
            features: Input feature vector.
            actual_verdict: Ground truth verdict string.

        Returns:
            Cross-entropy loss value.
        """
        if actual_verdict not in VERDICTS:
            logger.warning(f"Unknown verdict '{actual_verdict}', skipping training")
            return 0.0

        target_idx = VERDICTS.index(actual_verdict)

        # Prepare input
        x = np.asarray(features, dtype=np.float64).flatten()
        if x.shape[0] < self.input_dim:
            x = np.pad(x, (0, self.input_dim - x.shape[0]))
        elif x.shape[0] > self.input_dim:
            x = x[:self.input_dim]

        # Forward
        z1 = x @ self.W1 + self.b1
        h1 = _sigmoid(z1)
        z2 = h1 @ self.W2 + self.b2
        probs = _softmax(z2)

        # Cross-entropy loss
        loss = -np.log(probs[target_idx] + 1e-12)

        # Check if prediction was correct
        if int(np.argmax(probs)) == target_idx:
            self._correct_predictions += 1

        # Backpropagation
        # dL/dz2 = probs - one_hot(target)
        one_hot = np.zeros(self.output_dim, dtype=np.float64)
        one_hot[target_idx] = 1.0
        dz2 = probs - one_hot  # (output_dim,)

        # Gradients for W2, b2
        dW2 = np.outer(h1, dz2)  # (hidden, output)
        db2 = dz2

        # Backprop through hidden layer
        dh1 = dz2 @ self.W2.T  # (hidden,)
        # sigmoid derivative: h1 * (1 - h1)
        dz1 = dh1 * h1 * (1.0 - h1)  # (hidden,)

        # Gradients for W1, b1
        dW1 = np.outer(x, dz1)  # (input, hidden)
        db1 = dz1

        # SGD updates
        self.W2 -= self.lr * dW2
        self.b2 -= self.lr * db2
        self.W1 -= self.lr * dW1
        self.b1 -= self.lr * db1

        self._train_steps += 1
        self._total_loss += float(loss)
        return float(loss)

    def extract_features(self, debate_result: Dict[str, Any]) -> np.ndarray:
        """
        Extract an 8-dimensional feature vector from debate result data.

        Features:
        0: argument_strength (0-1, avg of proposer argument qualities)
        1: evidence_count (normalized)
        2: reasoning_depth (number of reasoning steps, normalized)
        3: counterargument_quality (0-1, avg quality of counter-arguments)
        4: num_rounds (normalized by max expected rounds)
        5: consensus_score (0-1, agreement level among judges)
        6: novelty_score (0-1, how novel the arguments are)
        7: logical_coherence (0-1, internal consistency)
        """
        features = np.zeros(self.input_dim, dtype=np.float64)

        features[0] = float(debate_result.get('argument_strength', 0.5))
        features[1] = min(float(debate_result.get('evidence_count', 0)) / 20.0, 1.0)
        features[2] = min(float(debate_result.get('reasoning_depth', 0)) / 10.0, 1.0)
        features[3] = float(debate_result.get('counterargument_quality', 0.5))
        features[4] = min(float(debate_result.get('num_rounds', 1)) / 5.0, 1.0)
        features[5] = float(debate_result.get('consensus_score', 0.5))
        features[6] = float(debate_result.get('novelty_score', 0.5))
        features[7] = float(debate_result.get('logical_coherence', 0.5))

        return features

    def get_stats(self) -> Dict[str, Any]:
        """Return debate scorer statistics."""
        avg_loss = (self._total_loss / self._train_steps
                    if self._train_steps > 0 else 0.0)
        accuracy = (self._correct_predictions / self._train_steps
                    if self._train_steps > 0 else 0.0)
        return {
            'input_dim': self.input_dim,
            'hidden_dim': self.hidden_dim,
            'train_steps': self._train_steps,
            'total_scores': self._total_scores,
            'avg_loss': round(avg_loss, 6),
            'accuracy': round(accuracy, 4),
            'verdict_counts': dict(self._verdict_counts),
            'correct_predictions': self._correct_predictions,
        }
