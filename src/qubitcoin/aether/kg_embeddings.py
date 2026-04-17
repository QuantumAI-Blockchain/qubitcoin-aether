"""
Knowledge Graph Embeddings — TransE/RotatE for Entity/Relation Learning

AI Roadmap Item #33: Learn entity and relation embeddings from the
knowledge graph structure. Embeddings enable:
  - Similarity search between entities
  - Link prediction (which edges are missing?)
  - Analogy detection (A:B :: C:?)
  - Transfer learning across domains

Implements TransE (translational embeddings) using only numpy.
h + r ≈ t for valid triples (head, relation, tail).
"""
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class TransEEmbeddings:
    """TransE knowledge graph embedding model.

    For each triple (h, r, t): score = ||h + r - t||
    Low score = plausible triple. Trained via margin-based ranking loss.

    Uses numpy only — no PyTorch dependency. Supports incremental
    training as new nodes/edges arrive.
    """

    def __init__(self, dim: int = 32, lr: float = 0.01,
                 margin: float = 1.0, max_entities: int = 100000) -> None:
        self.dim = dim
        self.lr = lr
        self.margin = margin
        self.max_entities = max_entities

        # Embeddings: entity_id -> vector, relation_name -> vector
        self._entity_emb: Dict[int, np.ndarray] = {}
        self._relation_emb: Dict[str, np.ndarray] = {}

        # Training stats
        self._train_steps: int = 0
        self._total_loss: float = 0.0
        self._entity_count: int = 0
        self._relation_count: int = 0

    def _get_entity_emb(self, entity_id: int) -> np.ndarray:
        """Get or initialize entity embedding."""
        if entity_id not in self._entity_emb:
            if self._entity_count >= self.max_entities:
                # Evict least-used (random for simplicity)
                if self._entity_emb:
                    evict_id = next(iter(self._entity_emb))
                    del self._entity_emb[evict_id]
                    self._entity_count -= 1
            vec = np.random.randn(self.dim).astype(np.float64) * 0.1
            vec /= np.linalg.norm(vec) + 1e-10  # Unit normalize
            self._entity_emb[entity_id] = vec
            self._entity_count += 1
        return self._entity_emb[entity_id]

    def _get_relation_emb(self, relation: str) -> np.ndarray:
        """Get or initialize relation embedding."""
        if relation not in self._relation_emb:
            vec = np.random.randn(self.dim).astype(np.float64) * 0.1
            self._relation_emb[relation] = vec
            self._relation_count += 1
        return self._relation_emb[relation]

    def score_triple(self, head_id: int, relation: str,
                     tail_id: int) -> float:
        """Score a triple (lower = more plausible).

        Returns L2 distance: ||h + r - t||
        """
        h = self._get_entity_emb(head_id)
        r = self._get_relation_emb(relation)
        t = self._get_entity_emb(tail_id)
        return float(np.linalg.norm(h + r - t))

    def train_step(self, triples: List[Tuple[int, str, int]],
                   all_entity_ids: List[int]) -> float:
        """Train on a batch of triples using margin-based ranking loss.

        For each positive triple (h, r, t), creates a negative by
        corrupting either h or t. Loss = max(0, margin + d_pos - d_neg).

        Args:
            triples: List of (head_id, relation, tail_id) tuples.
            all_entity_ids: Pool of entity IDs for negative sampling.

        Returns:
            Average loss for the batch.
        """
        if not triples or not all_entity_ids:
            return 0.0

        total_loss = 0.0
        entity_pool = np.array(all_entity_ids)

        for h_id, rel, t_id in triples:
            h = self._get_entity_emb(h_id)
            r = self._get_relation_emb(rel)
            t = self._get_entity_emb(t_id)

            # Positive distance
            d_pos = np.linalg.norm(h + r - t)

            # Negative sample: corrupt head or tail
            if np.random.random() < 0.5:
                neg_id = int(np.random.choice(entity_pool))
                neg = self._get_entity_emb(neg_id)
                d_neg = np.linalg.norm(neg + r - t)
                is_head_corrupt = True
            else:
                neg_id = int(np.random.choice(entity_pool))
                neg = self._get_entity_emb(neg_id)
                d_neg = np.linalg.norm(h + r - neg)
                is_head_corrupt = False

            # Margin loss
            loss = max(0.0, self.margin + d_pos - d_neg)
            total_loss += loss

            if loss > 0:
                # Gradient: d/d(h+r-t) of ||h+r-t|| = (h+r-t) / ||h+r-t||
                diff_pos = h + r - t
                norm_pos = np.linalg.norm(diff_pos) + 1e-10
                grad_pos = diff_pos / norm_pos

                # Update positive triple embeddings
                self._entity_emb[h_id] = h - self.lr * grad_pos
                self._relation_emb[rel] = r - self.lr * grad_pos
                self._entity_emb[t_id] = t + self.lr * grad_pos

                # Update negative triple
                if is_head_corrupt:
                    diff_neg = neg + r - t
                    norm_neg = np.linalg.norm(diff_neg) + 1e-10
                    grad_neg = diff_neg / norm_neg
                    self._entity_emb[neg_id] = neg + self.lr * grad_neg
                else:
                    diff_neg = h + r - neg
                    norm_neg = np.linalg.norm(diff_neg) + 1e-10
                    grad_neg = diff_neg / norm_neg
                    self._entity_emb[neg_id] = neg - self.lr * grad_neg

                # Re-normalize embeddings to unit sphere
                for eid in (h_id, t_id, neg_id):
                    emb = self._entity_emb[eid]
                    n = np.linalg.norm(emb)
                    if n > 0:
                        self._entity_emb[eid] = emb / n

        self._train_steps += 1
        avg_loss = total_loss / max(1, len(triples))
        self._total_loss += avg_loss
        return avg_loss

    def predict_tail(self, head_id: int, relation: str,
                     candidates: List[int], top_k: int = 10) -> List[Tuple[int, float]]:
        """Predict most likely tail entities for (head, relation, ?).

        Returns top-k candidates sorted by score (ascending = most plausible).
        """
        h = self._get_entity_emb(head_id)
        r = self._get_relation_emb(relation)

        scores = []
        for cid in candidates:
            t = self._get_entity_emb(cid)
            d = float(np.linalg.norm(h + r - t))
            scores.append((cid, d))

        scores.sort(key=lambda x: x[1])
        return scores[:top_k]

    def predict_head(self, relation: str, tail_id: int,
                     candidates: List[int], top_k: int = 10) -> List[Tuple[int, float]]:
        """Predict most likely head entities for (?, relation, tail)."""
        r = self._get_relation_emb(relation)
        t = self._get_entity_emb(tail_id)

        scores = []
        for cid in candidates:
            h = self._get_entity_emb(cid)
            d = float(np.linalg.norm(h + r - t))
            scores.append((cid, d))

        scores.sort(key=lambda x: x[1])
        return scores[:top_k]

    def entity_similarity(self, id_a: int, id_b: int) -> float:
        """Cosine similarity between two entity embeddings."""
        a = self._get_entity_emb(id_a)
        b = self._get_entity_emb(id_b)
        dot = float(np.dot(a, b))
        norm = float(np.linalg.norm(a) * np.linalg.norm(b))
        return dot / (norm + 1e-10)

    def find_analogies(self, a_id: int, b_id: int, c_id: int,
                       candidates: List[int], top_k: int = 5) -> List[Tuple[int, float]]:
        """Find d such that a:b :: c:d (analogy completion).

        d ≈ c + (b - a) in embedding space.
        """
        a = self._get_entity_emb(a_id)
        b = self._get_entity_emb(b_id)
        c = self._get_entity_emb(c_id)
        target = c + (b - a)

        scores = []
        for cid in candidates:
            if cid in (a_id, b_id, c_id):
                continue
            emb = self._get_entity_emb(cid)
            d = float(np.linalg.norm(target - emb))
            scores.append((cid, d))

        scores.sort(key=lambda x: x[1])
        return scores[:top_k]

    def train_from_kg(self, knowledge_graph: object, batch_size: int = 64) -> float:
        """Extract triples from KG and train one step.

        Samples edges from the KG, converts to (head, relation, tail)
        triples, and runs a training step.
        """
        kg = knowledge_graph
        if not hasattr(kg, '_adj_out') or not hasattr(kg, 'nodes'):
            return 0.0

        # Collect triples from KG edges
        triples: List[Tuple[int, str, int]] = []
        all_ids = list(kg.nodes.keys())
        if not all_ids:
            return 0.0

        for src_id, edges in kg._adj_out.items():
            for edge in edges:
                dst_id = edge.get('target', edge.get('dst'))
                rel = edge.get('edge_type', 'related')
                if dst_id is not None:
                    triples.append((src_id, rel, dst_id))

        if not triples:
            return 0.0

        # Sample a batch
        if len(triples) > batch_size:
            indices = np.random.choice(len(triples), batch_size, replace=False)
            batch = [triples[i] for i in indices]
        else:
            batch = triples

        return self.train_step(batch, all_ids)

    def get_stats(self) -> dict:
        return {
            'dim': self.dim,
            'entities': self._entity_count,
            'relations': self._relation_count,
            'train_steps': self._train_steps,
            'avg_loss': round(self._total_loss / max(1, self._train_steps), 6),
        }
