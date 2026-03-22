"""
#89: Few-Shot Learning (1-5 examples)

Learn from very few examples using prototypical networks and matching
networks approaches.  Classifies queries by distance to class prototypes
computed from the support set.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FewShotResult:
    """Result of a few-shot classification."""
    predicted_label: str
    confidence: float
    distances: Dict[str, float]


class FewShotLearner:
    """Few-shot learner using prototypical and matching networks.

    Supports 1-5 examples per class.  Two modes:
      - prototypical: compute class centroids, classify by Euclidean distance
      - matching:     attention-weighted vote over support set
    """

    def __init__(self, dim: int = 32, mode: str = 'prototypical') -> None:
        self._dim = dim
        self._mode = mode  # 'prototypical' or 'matching'
        # Adaptation state (MAML-lite)
        self._adapted_weights: Optional[np.ndarray] = None
        # Per-domain accuracy tracking
        self._domain_accuracy: Dict[str, List[bool]] = {}
        # Stats
        self._total_queries = 0
        self._total_correct = 0
        self._total_adaptations = 0

    # ------------------------------------------------------------------
    # Prototypical classification
    # ------------------------------------------------------------------

    def learn(
        self,
        examples: List[Tuple[np.ndarray, str]],
        query: np.ndarray,
    ) -> Tuple[str, float]:
        """Classify query using few-shot examples.

        Args:
            examples: List of (feature_vector, label) pairs (1-5 per class).
            query: Feature vector to classify.

        Returns:
            (predicted_label, confidence)
        """
        if not examples:
            return ('unknown', 0.0)

        self._total_queries += 1

        if self._mode == 'matching':
            return self._matching_classify(examples, query)
        return self._prototypical_classify(examples, query)

    def _prototypical_classify(
        self,
        examples: List[Tuple[np.ndarray, str]],
        query: np.ndarray,
    ) -> Tuple[str, float]:
        """Prototypical network: classify by distance to class centroids."""
        # Compute class prototypes (centroids)
        prototypes: Dict[str, List[np.ndarray]] = {}
        for vec, label in examples:
            if label not in prototypes:
                prototypes[label] = []
            prototypes[label].append(vec)

        centroids: Dict[str, np.ndarray] = {}
        for label, vecs in prototypes.items():
            centroids[label] = np.mean(vecs, axis=0)

        # Compute distances
        distances: Dict[str, float] = {}
        for label, centroid in centroids.items():
            dist = float(np.linalg.norm(query - centroid))
            distances[label] = dist

        # Softmax over negative distances for probabilities
        labels = list(distances.keys())
        neg_dists = np.array([-distances[l] for l in labels])
        # Numerical stability
        neg_dists -= np.max(neg_dists)
        exp_vals = np.exp(neg_dists)
        probs = exp_vals / (np.sum(exp_vals) + 1e-12)

        best_idx = int(np.argmax(probs))
        return (labels[best_idx], float(probs[best_idx]))

    def _matching_classify(
        self,
        examples: List[Tuple[np.ndarray, str]],
        query: np.ndarray,
    ) -> Tuple[str, float]:
        """Matching network: attention-weighted vote over support set."""
        # Compute attention weights (cosine similarity)
        similarities: List[float] = []
        labels: List[str] = []
        for vec, label in examples:
            norm_v = np.linalg.norm(vec)
            norm_q = np.linalg.norm(query)
            if norm_v < 1e-12 or norm_q < 1e-12:
                sim = 0.0
            else:
                sim = float(np.dot(vec, query) / (norm_v * norm_q))
            similarities.append(sim)
            labels.append(label)

        # Softmax attention
        sims = np.array(similarities)
        sims -= np.max(sims)
        attn = np.exp(sims)
        attn /= np.sum(attn) + 1e-12

        # Weighted vote
        label_scores: Dict[str, float] = {}
        for i, label in enumerate(labels):
            label_scores[label] = label_scores.get(label, 0.0) + float(attn[i])

        best_label = max(label_scores, key=label_scores.get)  # type: ignore
        return (best_label, label_scores[best_label])

    # ------------------------------------------------------------------
    # Fast adaptation (MAML-lite)
    # ------------------------------------------------------------------

    def adapt(
        self,
        support_set: List[dict],
        n_steps: int = 5,
        lr: float = 0.01,
    ) -> dict:
        """Fast adaptation on a support set (MAML-lite inner loop).

        Args:
            support_set: List of dicts with 'features' (np.ndarray) and 'label' (str).
            n_steps: Number of gradient steps.
            lr: Learning rate.

        Returns:
            Dict with adaptation results.
        """
        if not support_set:
            return {'adapted': False, 'steps': 0}

        self._total_adaptations += 1

        # Initialize weights if needed
        dim = len(support_set[0].get('features', np.zeros(self._dim)))
        if self._adapted_weights is None or len(self._adapted_weights) != dim:
            self._adapted_weights = np.random.randn(dim) * 0.1

        # Collect unique labels
        unique_labels = list(set(s['label'] for s in support_set if 'label' in s))
        if len(unique_labels) < 2:
            return {'adapted': False, 'steps': 0, 'reason': 'need_2+_classes'}

        label_to_idx = {l: i for i, l in enumerate(unique_labels)}

        # Simple gradient descent on prototype loss
        weights = self._adapted_weights.copy()
        losses: List[float] = []
        for step in range(n_steps):
            total_loss = 0.0
            grad = np.zeros_like(weights)
            for sample in support_set:
                feat = np.array(sample.get('features', np.zeros(dim)))
                label = sample.get('label', '')
                if label not in label_to_idx:
                    continue
                # Transform features
                transformed = feat * weights
                # Loss: distance to own prototype should be small
                proto = np.mean([
                    np.array(s.get('features', np.zeros(dim))) * weights
                    for s in support_set if s.get('label') == label
                ], axis=0)
                diff = transformed - proto
                loss = float(np.sum(diff ** 2))
                total_loss += loss
                # Gradient
                grad += 2 * diff * feat / len(support_set)

            weights -= lr * grad
            losses.append(total_loss / max(len(support_set), 1))

        self._adapted_weights = weights
        return {
            'adapted': True,
            'steps': n_steps,
            'final_loss': losses[-1] if losses else 0.0,
            'loss_reduction': (losses[0] - losses[-1]) if len(losses) > 1 else 0.0,
        }

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        domain: str,
        correct: bool,
    ) -> None:
        """Record whether a few-shot prediction was correct."""
        if domain not in self._domain_accuracy:
            self._domain_accuracy[domain] = []
        self._domain_accuracy[domain].append(correct)
        if len(self._domain_accuracy[domain]) > 500:
            self._domain_accuracy[domain] = self._domain_accuracy[domain][-500:]
        if correct:
            self._total_correct += 1

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return few-shot learner statistics."""
        accuracy = self._total_correct / max(self._total_queries, 1)
        domain_acc: Dict[str, float] = {}
        for domain, outcomes in self._domain_accuracy.items():
            domain_acc[domain] = sum(outcomes) / max(len(outcomes), 1)
        return {
            'total_queries': self._total_queries,
            'total_correct': self._total_correct,
            'accuracy': accuracy,
            'total_adaptations': self._total_adaptations,
            'mode': self._mode,
            'domain_accuracy': domain_acc,
            'has_adapted_weights': self._adapted_weights is not None,
        }
