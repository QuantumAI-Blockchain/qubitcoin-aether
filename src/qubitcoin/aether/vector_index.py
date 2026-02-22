"""
Vector Index for Knowledge Graph — Dense Embedding Search

Provides semantic similarity search using dense embeddings.
Uses sentence-transformers (all-MiniLM-L6-v2) for embedding generation.
Falls back to a simple bag-of-words embedding if sentence-transformers
is not installed, ensuring the node can always start.

This complements the TF-IDF index by capturing *meaning*, not just
keyword overlap.  "quantum entanglement enables secure communication"
and "Bell pairs provide cryptographic guarantees" will score high
similarity here even though they share zero keywords.
"""
import math
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Lazy-loaded transformer model
_model = None
_model_load_attempted = False
_USE_TRANSFORMER = True


def _load_model():
    """Lazily load the sentence-transformer model."""
    global _model, _model_load_attempted, _USE_TRANSFORMER
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("VectorIndex: loaded sentence-transformer all-MiniLM-L6-v2")
    except Exception as e:
        _USE_TRANSFORMER = False
        logger.info(f"VectorIndex: sentence-transformers not available ({e}), using fallback BoW embeddings")
    return _model


def _extract_text(content: dict) -> str:
    """Extract searchable text from a KeterNode's content dict."""
    parts = []
    for key in ('text', 'description', 'subject', 'query', 'content',
                'type', 'pattern', 'block_hash', 'miner_address', 'node_type'):
        val = content.get(key)
        if isinstance(val, str):
            parts.append(val)
    return ' '.join(parts)


# ============================================================================
# Fallback BoW embedding (no external deps)
# ============================================================================
_TOKEN_RE = re.compile(r'[a-z0-9]+')
_STOP_WORDS = frozenset({
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'can', 'to', 'of', 'in', 'for', 'on',
    'with', 'at', 'by', 'from', 'as', 'into', 'through', 'and', 'or',
    'but', 'not', 'it', 'its', 'this', 'that', 'all', 'each', 'no',
})


class _BoWEmbedder:
    """Simple bag-of-words embedder as fallback when no transformer available."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim
        self._vocab: Dict[str, int] = {}
        self._next_slot = 0

    def encode(self, texts: List[str]) -> List[List[float]]:
        """Encode texts into dense vectors using hashed BoW."""
        results = []
        for text in texts:
            tokens = [t for t in _TOKEN_RE.findall(text.lower())
                      if t not in _STOP_WORDS and len(t) > 2]
            vec = [0.0] * self.dim
            for token in tokens:
                # Deterministic hash to dimension
                h = hash(token) % self.dim
                vec[h] += 1.0
            # L2 normalize
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            results.append(vec)
        return results


_bow_embedder = _BoWEmbedder()


def _compute_embedding(text: str) -> List[float]:
    """Compute embedding for a single text string."""
    model = _load_model()
    if model is not None:
        emb = model.encode([text], show_progress_bar=False)[0]
        return emb.tolist()
    else:
        return _bow_embedder.encode([text])[0]


def _compute_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Compute embeddings for a batch of texts."""
    if not texts:
        return []
    model = _load_model()
    if model is not None:
        embs = model.encode(texts, show_progress_bar=False, batch_size=64)
        return [e.tolist() for e in embs]
    else:
        return _bow_embedder.encode(texts)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorIndex:
    """
    Dense embedding index over knowledge graph nodes.

    Stores per-node embeddings and supports:
    - Incremental add/remove
    - Cosine similarity search (ANN via hnswlib when available, brute-force fallback)
    - Batch embedding computation
    - Near-duplicate detection (for Phi redundancy penalty)
    """

    # Threshold for rebuilding hnswlib index vs incremental add
    _HNSW_REBUILD_THRESHOLD = 1000

    def __init__(self) -> None:
        # node_id -> embedding vector
        self.embeddings: Dict[int, List[float]] = {}
        # Embedding dimension (set on first add)
        self._dim: int = 0
        # hnswlib ANN index (lazy-initialized)
        self._hnsw = None
        self._hnsw_available: bool = False
        self._hnsw_id_to_label: Dict[int, int] = {}   # node_id -> hnsw internal label
        self._hnsw_label_to_id: Dict[int, int] = {}   # hnsw label -> node_id
        self._hnsw_next_label: int = 0
        self._hnsw_dirty: bool = True
        try:
            import hnswlib as _hnsw_mod  # noqa: F401
            self._hnsw_available = True
        except ImportError:
            pass

    def _ensure_hnsw(self) -> bool:
        """Rebuild hnswlib index if dirty and enough embeddings exist."""
        if not self._hnsw_available or not self._dim or len(self.embeddings) < 20:
            return False
        if not self._hnsw_dirty and self._hnsw is not None:
            return True
        try:
            import hnswlib
            import numpy as np
            n = len(self.embeddings)
            index = hnswlib.Index(space='cosine', dim=self._dim)
            index.init_index(max_elements=max(n * 2, 1000), ef_construction=200, M=16)
            self._hnsw_id_to_label.clear()
            self._hnsw_label_to_id.clear()
            ids_list = []
            vectors = []
            for i, (node_id, emb) in enumerate(self.embeddings.items()):
                ids_list.append(i)
                vectors.append(emb)
                self._hnsw_id_to_label[node_id] = i
                self._hnsw_label_to_id[i] = node_id
            index.add_items(
                np.array(vectors, dtype=np.float32),
                np.array(ids_list, dtype=np.int64),
            )
            index.set_ef(50)
            self._hnsw = index
            self._hnsw_next_label = len(ids_list)
            self._hnsw_dirty = False
            return True
        except Exception as e:
            logger.debug(f"hnswlib rebuild failed: {e}")
            self._hnsw_available = False
            return False

    def add_node(self, node_id: int, content: dict) -> None:
        """Compute and store embedding for a node."""
        text = _extract_text(content)
        if not text.strip():
            return
        try:
            emb = _compute_embedding(text)
            self.embeddings[node_id] = emb
            if not self._dim:
                self._dim = len(emb)
            self._hnsw_dirty = True
        except Exception as e:
            logger.debug(f"VectorIndex: failed to embed node {node_id}: {e}")

    def add_nodes_batch(self, nodes: Dict[int, dict]) -> int:
        """Batch-embed multiple nodes at once (faster than individual adds)."""
        ids = []
        texts = []
        for nid, content in nodes.items():
            text = _extract_text(content)
            if text.strip():
                ids.append(nid)
                texts.append(text)

        if not texts:
            return 0

        try:
            embs = _compute_embeddings_batch(texts)
            for nid, emb in zip(ids, embs):
                self.embeddings[nid] = emb
            if not self._dim and embs:
                self._dim = len(embs[0])
            self._hnsw_dirty = True
            return len(embs)
        except Exception as e:
            logger.debug(f"VectorIndex: batch embed failed: {e}")
            return 0

    def remove_node(self, node_id: int) -> None:
        """Remove a node's embedding."""
        self.embeddings.pop(node_id, None)
        self._hnsw_dirty = True

    def query(self, query_text: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Search by semantic similarity. Uses hnswlib O(log n) when available,
        falls back to brute-force O(n).

        Returns:
            List of (node_id, cosine_similarity) tuples, highest first.
        """
        if not self.embeddings:
            return []

        try:
            query_emb = _compute_embedding(query_text)
        except Exception:
            return []

        # Try hnswlib ANN search first
        if self._ensure_hnsw():
            try:
                import numpy as np
                k = min(top_k, len(self.embeddings))
                labels, distances = self._hnsw.knn_query(
                    np.array([query_emb], dtype=np.float32), k=k
                )
                results = []
                for label, dist in zip(labels[0], distances[0]):
                    nid = self._hnsw_label_to_id.get(int(label))
                    if nid is not None:
                        # hnswlib cosine distance = 1 - cosine_similarity
                        results.append((nid, 1.0 - float(dist)))
                return results
            except Exception:
                pass  # fall through to brute-force

        # Brute-force fallback
        scores = []
        for nid, emb in self.embeddings.items():
            sim = cosine_similarity(query_emb, emb)
            scores.append((nid, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def query_by_embedding(self, query_emb: List[float], top_k: int = 10) -> List[Tuple[int, float]]:
        """Search by pre-computed embedding vector."""
        if not self.embeddings:
            return []

        if self._ensure_hnsw():
            try:
                import numpy as np
                k = min(top_k, len(self.embeddings))
                labels, distances = self._hnsw.knn_query(
                    np.array([query_emb], dtype=np.float32), k=k
                )
                results = []
                for label, dist in zip(labels[0], distances[0]):
                    nid = self._hnsw_label_to_id.get(int(label))
                    if nid is not None:
                        results.append((nid, 1.0 - float(dist)))
                return results
            except Exception:
                pass

        scores = []
        for nid, emb in self.embeddings.items():
            sim = cosine_similarity(query_emb, emb)
            scores.append((nid, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_embedding(self, node_id: int) -> Optional[List[float]]:
        """Get the embedding vector for a node."""
        return self.embeddings.get(node_id)

    def find_near_duplicates(self, threshold: float = 0.95) -> List[Tuple[int, int, float]]:
        """Find pairs of nodes with cosine similarity above threshold.

        Uses hnswlib k-NN per node when available (O(n*k log n)),
        falls back to brute-force O(n^2) with sampling for large graphs.

        Returns:
            List of (node_a, node_b, similarity) tuples.
        """
        ids = list(self.embeddings.keys())
        duplicates = []

        # Use hnswlib for efficient duplicate detection
        if self._ensure_hnsw() and len(ids) > 100:
            try:
                import numpy as np
                seen_pairs: set = set()
                for nid in ids:
                    emb = self.embeddings[nid]
                    k = min(10, len(ids))  # check top-10 neighbors
                    labels, distances = self._hnsw.knn_query(
                        np.array([emb], dtype=np.float32), k=k
                    )
                    for label, dist in zip(labels[0], distances[0]):
                        other_nid = self._hnsw_label_to_id.get(int(label))
                        if other_nid is None or other_nid == nid:
                            continue
                        sim = 1.0 - float(dist)
                        if sim >= threshold:
                            pair = (min(nid, other_nid), max(nid, other_nid))
                            if pair not in seen_pairs:
                                seen_pairs.add(pair)
                                duplicates.append((pair[0], pair[1], sim))
                return duplicates
            except Exception:
                pass  # fall through to brute-force

        # Brute-force fallback with sampling
        if len(ids) > 5000:
            import random
            ids = random.sample(ids, 5000)

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sim = cosine_similarity(
                    self.embeddings[ids[i]],
                    self.embeddings[ids[j]]
                )
                if sim >= threshold:
                    duplicates.append((ids[i], ids[j], sim))
        return duplicates

    def compute_partition_mutual_info(self, partition_a: List[int],
                                       partition_b: List[int]) -> float:
        """Compute approximate mutual information between two graph partitions.

        Uses embedding distributions to estimate I(A;B) = H(A) + H(B) - H(A,B)
        where H is the entropy of the embedding distribution.

        Used by Phi v3 for information-theoretic integration.
        """
        embs_a = [self.embeddings[nid] for nid in partition_a if nid in self.embeddings]
        embs_b = [self.embeddings[nid] for nid in partition_b if nid in self.embeddings]

        if not embs_a or not embs_b:
            return 0.0

        h_a = self._embedding_entropy(embs_a)
        h_b = self._embedding_entropy(embs_b)
        h_ab = self._embedding_entropy(embs_a + embs_b)

        # Mutual information (can be negative due to estimation, clamp to 0)
        mi = max(0.0, h_a + h_b - h_ab)
        return mi

    def _embedding_entropy(self, embeddings: List[List[float]]) -> float:
        """Estimate entropy of an embedding distribution.

        Uses per-dimension variance as a proxy: H ≈ 0.5 * sum(log(2πe * var_d))
        """
        if not embeddings or not embeddings[0]:
            return 0.0

        dim = len(embeddings[0])
        n = len(embeddings)
        if n < 2:
            return 0.0

        entropy = 0.0
        for d in range(dim):
            values = [emb[d] for emb in embeddings]
            mean = sum(values) / n
            var = sum((v - mean) ** 2 for v in values) / n
            if var > 1e-12:
                # Gaussian entropy approximation: 0.5 * log(2πe * var)
                entropy += 0.5 * math.log(2 * math.pi * math.e * var)

        return max(0.0, entropy)

    def get_stats(self) -> dict:
        """Return index statistics."""
        return {
            'total_embeddings': len(self.embeddings),
            'embedding_dim': self._dim,
            'uses_transformer': _USE_TRANSFORMER and _model is not None,
            'uses_hnswlib': self._hnsw_available and self._hnsw is not None,
        }
