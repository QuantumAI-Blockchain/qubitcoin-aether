"""
Contrastive Learning for Concept Boundaries (Item #28)

Learns concept prototype embeddings via triplet loss (contrastive learning).
Works alongside existing concept_formation.py but with learned boundaries
instead of fixed clustering thresholds.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConceptPrototype:
    """A learned concept with a prototype embedding and update history."""

    __slots__ = ('name', 'embedding', 'count', 'created_at', 'last_updated')

    def __init__(self, name: str, embedding: np.ndarray) -> None:
        self.name = name
        self.embedding = embedding.astype(np.float64)
        self.count: int = 1
        self.created_at: float = time.time()
        self.last_updated: float = time.time()


class ContrastiveConcepts:
    """
    Learn concept boundaries via contrastive (triplet) learning.

    Each concept has a prototype embedding that is refined through
    triplet loss: max(0, margin + d(anchor, positive) - d(anchor, negative)).
    """

    def __init__(self, dim: int = 32, margin: float = 1.0,
                 lr: float = 0.01, discovery_threshold: float = 2.0,
                 max_concepts: int = 500) -> None:
        self.dim = dim
        self.margin = margin
        self.lr = lr
        self.discovery_threshold = discovery_threshold
        self.max_concepts = max_concepts

        self._concepts: Dict[str, ConceptPrototype] = {}

        # Projection matrix for input embeddings of variable size
        self._proj: Optional[np.ndarray] = None
        self._proj_input_dim: int = 0

        # Stats
        self._train_steps: int = 0
        self._total_loss: float = 0.0
        self._concepts_discovered: int = 0
        self._classifications: int = 0
        self._created_at: float = time.time()

    def _project(self, vec: np.ndarray) -> np.ndarray:
        """Project input vector to concept space dimension."""
        vec = np.asarray(vec, dtype=np.float64).flatten()
        if vec.shape[0] == self.dim:
            return vec
        if vec.shape[0] < self.dim:
            return np.pad(vec, (0, self.dim - vec.shape[0]))
        # Project down via random (but fixed) projection
        if self._proj is None or self._proj_input_dim != vec.shape[0]:
            np.random.seed(42)  # deterministic projection
            self._proj = np.random.randn(vec.shape[0], self.dim).astype(np.float64)
            self._proj /= np.sqrt(vec.shape[0])
            self._proj_input_dim = vec.shape[0]
        return vec @ self._proj

    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """L2 distance between two vectors."""
        return float(np.linalg.norm(a - b))

    def add_concept(self, name: str, embedding: np.ndarray) -> None:
        """Register a concept with its initial prototype embedding."""
        emb = self._project(embedding)
        self._concepts[name] = ConceptPrototype(name, emb)
        self._concepts_discovered += 1
        logger.debug(f"Added concept '{name}' (total: {len(self._concepts)})")

    def train_step(self, anchor: np.ndarray, positive: np.ndarray,
                   negative: np.ndarray) -> float:
        """
        One contrastive training step using triplet loss.

        Loss = max(0, margin + d(anchor, positive) - d(anchor, negative))

        Gradients:
        - If loss > 0:
          dL/d_anchor   = (anchor - positive) / d_pos - (anchor - negative) / d_neg
          dL/d_positive = (positive - anchor) / d_pos
          dL/d_negative = (negative - anchor) / d_neg  (but negative direction)

        Args:
            anchor: Anchor embedding (the query point).
            positive: Embedding from same concept as anchor.
            negative: Embedding from different concept.

        Returns:
            Triplet loss value.
        """
        a = self._project(anchor)
        p = self._project(positive)
        n = self._project(negative)

        d_pos = self._distance(a, p)
        d_neg = self._distance(a, n)
        loss = max(0.0, self.margin + d_pos - d_neg)

        if loss > 0:
            # Compute gradients
            eps = 1e-8
            grad_a_pos = (a - p) / (d_pos + eps)
            grad_a_neg = (a - n) / (d_neg + eps)
            grad_a = grad_a_pos - grad_a_neg

            # Update: pull anchor toward positive, push away from negative
            # We update the nearest concept prototypes
            a_updated = a - self.lr * grad_a
            p_updated = p - self.lr * (p - a) / (d_pos + eps)
            n_updated = n + self.lr * (n - a) / (d_neg + eps)

            # Update concept prototypes if they match
            for concept in self._concepts.values():
                sim_a = 1.0 / (self._distance(concept.embedding, a) + eps)
                sim_p = 1.0 / (self._distance(concept.embedding, p) + eps)
                sim_n = 1.0 / (self._distance(concept.embedding, n) + eps)

                # Only update the closest matching concept
                if sim_p > 10.0:  # very close to positive
                    concept.embedding = 0.9 * concept.embedding + 0.1 * p_updated
                    concept.last_updated = time.time()
                if sim_n > 10.0:  # very close to negative
                    concept.embedding = 0.9 * concept.embedding + 0.1 * n_updated
                    concept.last_updated = time.time()

        self._train_steps += 1
        self._total_loss += loss
        return loss

    def classify(self, embedding: np.ndarray) -> Tuple[str, float]:
        """
        Classify an embedding by finding the nearest concept prototype.

        Args:
            embedding: Input embedding to classify.

        Returns:
            (concept_name, distance) tuple. Returns ('unknown', inf) if no concepts.
        """
        self._classifications += 1

        if not self._concepts:
            return ('unknown', float('inf'))

        emb = self._project(embedding)
        best_name = 'unknown'
        best_dist = float('inf')

        for concept in self._concepts.values():
            d = self._distance(emb, concept.embedding)
            if d < best_dist:
                best_dist = d
                best_name = concept.name

        return (best_name, best_dist)

    def discover_new_concept(self, embeddings: List[np.ndarray],
                             threshold: Optional[float] = None) -> Optional[str]:
        """
        Attempt to discover a new concept from a cluster of embeddings.

        A new concept is created if the centroid of the embeddings is far
        enough from all existing concept prototypes.

        Args:
            embeddings: List of embeddings that may form a new concept.
            threshold: Distance threshold (defaults to self.discovery_threshold).

        Returns:
            Name of newly created concept, or None if no new concept found.
        """
        if not embeddings:
            return None
        if len(self._concepts) >= self.max_concepts:
            return None

        threshold = threshold if threshold is not None else self.discovery_threshold

        # Compute centroid
        projected = [self._project(e) for e in embeddings]
        centroid = np.mean(projected, axis=0)

        # Check distance from all existing concepts
        for concept in self._concepts.values():
            if self._distance(centroid, concept.embedding) < threshold:
                return None  # Too close to existing concept

        # Create new concept
        concept_id = f"concept_{self._concepts_discovered + 1}"
        self.add_concept(concept_id, centroid)
        proto = self._concepts[concept_id]
        proto.count = len(embeddings)

        logger.info(
            f"Discovered new concept '{concept_id}' from {len(embeddings)} "
            f"embeddings (total concepts: {len(self._concepts)})"
        )
        return concept_id

    def get_concept_names(self) -> List[str]:
        """Return list of known concept names."""
        return list(self._concepts.keys())

    def get_concept_embedding(self, name: str) -> Optional[np.ndarray]:
        """Get the prototype embedding for a concept."""
        c = self._concepts.get(name)
        return c.embedding.copy() if c else None

    def get_stats(self) -> Dict[str, Any]:
        """Return contrastive concepts statistics."""
        avg_loss = (self._total_loss / self._train_steps
                    if self._train_steps > 0 else 0.0)
        return {
            'dim': self.dim,
            'margin': self.margin,
            'num_concepts': len(self._concepts),
            'max_concepts': self.max_concepts,
            'concepts_discovered': self._concepts_discovered,
            'train_steps': self._train_steps,
            'avg_loss': round(avg_loss, 6),
            'classifications': self._classifications,
            'discovery_threshold': self.discovery_threshold,
            'concept_names': list(self._concepts.keys())[:20],  # cap for stats
        }
