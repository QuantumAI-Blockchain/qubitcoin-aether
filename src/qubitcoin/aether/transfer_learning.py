"""
#88: Cross-Domain Transfer Learning

Transfer patterns learned in one domain to another via domain similarity,
direct/adapted/analogical transfer strategies, and meta-learning about
transfer success.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895


@dataclass
class TransferRecord:
    """Record of a transfer attempt."""
    source_domain: str
    target_domain: str
    strategy: str
    success: bool
    transferability: float
    timestamp: float = field(default_factory=time.time)


class TransferLearning:
    """Cross-domain transfer learning for Aether Tree knowledge.

    Transfers learned patterns (weights, embeddings, rules) from a source
    domain to a target domain using three strategies:
      - direct:     copy weights as-is (same structure)
      - adapted:    scale weights by domain similarity
      - analogical: map structure via correspondence matrix
    """

    def __init__(self, dim: int = 32) -> None:
        self._dim = dim
        # Domain embeddings (centroid of observed data per domain)
        self._domain_embeddings: Dict[str, np.ndarray] = {}
        self._domain_counts: Dict[str, int] = {}
        # Similarity cache
        self._similarity_cache: Dict[Tuple[str, str], float] = {}
        # Transfer history for meta-learning
        self._history: List[TransferRecord] = []
        self._max_history = 2000
        # Per-pair success tracking
        self._pair_successes: Dict[Tuple[str, str], List[bool]] = {}
        # Stats
        self._total_transfers = 0
        self._successful_transfers = 0

    # ------------------------------------------------------------------
    # Domain registration
    # ------------------------------------------------------------------

    def register_domain(self, domain: str, data: np.ndarray) -> None:
        """Register or update a domain embedding from observed data.

        Args:
            domain: Domain name (e.g. 'blockchain', 'quantum_physics').
            data: 2-D array (n_samples, dim) or 1-D (dim,).
        """
        if data.ndim == 1:
            data = data.reshape(1, -1)
        centroid = np.mean(data, axis=0)
        if domain in self._domain_embeddings:
            # Running average
            n = self._domain_counts[domain]
            self._domain_embeddings[domain] = (
                self._domain_embeddings[domain] * n + centroid
            ) / (n + 1)
            self._domain_counts[domain] = n + 1
        else:
            self._domain_embeddings[domain] = centroid.copy()
            self._domain_counts[domain] = 1
        # Invalidate similarity cache entries involving this domain
        self._similarity_cache = {
            k: v for k, v in self._similarity_cache.items()
            if domain not in k
        }

    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------

    def compute_transferability(self, source: str, target: str) -> float:
        """Compute how transferable knowledge is from source to target.

        Returns a float in [0, 1].  1 = identical domains, 0 = unrelated.
        """
        key = (source, target)
        if key in self._similarity_cache:
            return self._similarity_cache[key]

        s_emb = self._domain_embeddings.get(source)
        t_emb = self._domain_embeddings.get(target)
        if s_emb is None or t_emb is None:
            return 0.0

        # Cosine similarity
        norm_s = np.linalg.norm(s_emb)
        norm_t = np.linalg.norm(t_emb)
        if norm_s < 1e-12 or norm_t < 1e-12:
            sim = 0.0
        else:
            sim = float(np.dot(s_emb, t_emb) / (norm_s * norm_t))
            sim = max(0.0, sim)  # clamp negative cosine

        # Adjust by historical success rate for this pair
        pair_history = self._pair_successes.get(key, [])
        if pair_history:
            hist_rate = sum(pair_history) / len(pair_history)
            sim = 0.7 * sim + 0.3 * hist_rate

        self._similarity_cache[key] = sim
        return sim

    def domain_similarity_matrix(self) -> Tuple[List[str], np.ndarray]:
        """Compute pairwise similarity matrix across all known domains.

        Returns:
            (domain_names, similarity_matrix) where matrix[i,j] is the
            transferability score between domain i and domain j.
        """
        names = sorted(self._domain_embeddings.keys())
        n = len(names)
        mat = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            mat[i, i] = 1.0
            for j in range(i + 1, n):
                s = self.compute_transferability(names[i], names[j])
                mat[i, j] = s
                mat[j, i] = s
        return names, mat

    # ------------------------------------------------------------------
    # Transfer strategies
    # ------------------------------------------------------------------

    def transfer(
        self,
        source_domain: str,
        target_domain: str,
        model_weights: np.ndarray,
        strategy: Optional[str] = None,
    ) -> np.ndarray:
        """Transfer model weights from source domain to target domain.

        Args:
            source_domain: Where the weights were trained.
            target_domain: Where we want to apply them.
            model_weights: The weight array to transfer.
            strategy: 'direct', 'adapted', or 'analogical'.  If None,
                      auto-selects based on transferability score.

        Returns:
            Transferred weight array (same shape as input).
        """
        sim = self.compute_transferability(source_domain, target_domain)

        if strategy is None:
            if sim > 0.8:
                strategy = 'direct'
            elif sim > 0.4:
                strategy = 'adapted'
            else:
                strategy = 'analogical'

        if strategy == 'direct':
            result = self._transfer_direct(model_weights)
        elif strategy == 'adapted':
            result = self._transfer_adapted(model_weights, sim)
        else:
            result = self._transfer_analogical(
                model_weights, source_domain, target_domain, sim
            )

        self._total_transfers += 1
        return result

    def _transfer_direct(self, weights: np.ndarray) -> np.ndarray:
        """Direct transfer -- copy weights unchanged."""
        return weights.copy()

    def _transfer_adapted(self, weights: np.ndarray, similarity: float) -> np.ndarray:
        """Adapted transfer -- scale weights by similarity, add noise."""
        scale = similarity * PHI / (1.0 + PHI)  # phi-scaled factor
        noise = np.random.randn(*weights.shape) * (1.0 - similarity) * 0.1
        return weights * scale + noise

    def _transfer_analogical(
        self,
        weights: np.ndarray,
        source: str,
        target: str,
        similarity: float,
    ) -> np.ndarray:
        """Analogical transfer -- map structure via rotation matrix.

        Builds a pseudo-rotation from source embedding to target embedding
        and applies it to the weight matrix.
        """
        s_emb = self._domain_embeddings.get(source)
        t_emb = self._domain_embeddings.get(target)
        if s_emb is None or t_emb is None:
            return self._transfer_adapted(weights, similarity)

        # Build mapping vector
        diff = t_emb - s_emb
        norm = np.linalg.norm(diff)
        if norm < 1e-12:
            return self._transfer_direct(weights)

        direction = diff / norm
        # Project weights along mapping direction and shift
        flat = weights.flatten()
        d = min(len(flat), len(direction))
        projection = np.dot(flat[:d], direction[:d])
        shifted = flat.copy()
        shifted[:d] += direction[:d] * projection * similarity * 0.5
        return shifted.reshape(weights.shape)

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        source_domain: str,
        target_domain: str,
        strategy: str,
        success: bool,
    ) -> None:
        """Record whether a transfer was successful for meta-learning."""
        rec = TransferRecord(
            source_domain=source_domain,
            target_domain=target_domain,
            strategy=strategy,
            success=success,
        )
        self._history.append(rec)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        key = (source_domain, target_domain)
        if key not in self._pair_successes:
            self._pair_successes[key] = []
        self._pair_successes[key].append(success)
        if len(self._pair_successes[key]) > 200:
            self._pair_successes[key] = self._pair_successes[key][-200:]

        if success:
            self._successful_transfers += 1

        # Invalidate cached similarity
        self._similarity_cache.pop(key, None)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return transfer learning statistics."""
        success_rate = (
            self._successful_transfers / max(self._total_transfers, 1)
        )
        return {
            'total_transfers': self._total_transfers,
            'successful_transfers': self._successful_transfers,
            'success_rate': success_rate,
            'known_domains': len(self._domain_embeddings),
            'history_size': len(self._history),
            'pair_count': len(self._pair_successes),
        }
