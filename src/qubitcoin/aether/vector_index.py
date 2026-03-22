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

Includes a pure-Python HNSW (Hierarchical Navigable Small World) index
for O(log n) approximate nearest neighbor search at scale, used as the
default backend when vectors > 1000.
"""
import math
import random
import re
import heapq
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

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
    """TF-IDF weighted bag-of-words embedder as fallback when no transformer available.

    Uses term frequency with inverse document frequency weighting for
    better semantic representation than raw bag-of-words.
    """

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim
        self._vocab: Dict[str, int] = {}
        self._next_slot = 0
        # Document frequency tracking for IDF
        self._doc_freq: Dict[int, int] = {}  # dim_slot -> count of docs containing it
        self._total_docs: int = 0

    def encode(self, texts: List[str]) -> List[List[float]]:
        """Encode texts into dense vectors using TF-IDF weighted hashing."""
        self._total_docs += len(texts)
        results = []
        # First pass: compute TF and update document frequencies
        for text in texts:
            tokens = [t for t in _TOKEN_RE.findall(text.lower())
                      if t not in _STOP_WORDS and len(t) > 2]
            vec = [0.0] * self.dim
            seen_dims: set = set()
            for token in tokens:
                h = abs(hash(token)) % self.dim
                vec[h] += 1.0
                if h not in seen_dims:
                    seen_dims.add(h)
                    self._doc_freq[h] = self._doc_freq.get(h, 0) + 1

            # Apply TF-IDF: TF = log(1 + count), IDF = log(N / df)
            total_docs = max(self._total_docs, 1)
            for h in range(self.dim):
                if vec[h] > 0:
                    tf = math.log1p(vec[h])
                    df = self._doc_freq.get(h, 1)
                    idf = math.log(total_docs / df) if df > 0 else 0.0
                    vec[h] = tf * idf

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


# ============================================================================
# HNSW (Hierarchical Navigable Small World) Index
# ============================================================================

class HNSWIndex:
    """
    Pure-Python HNSW graph for O(log n) approximate nearest neighbor search.

    Implements the core HNSW algorithm from Malkov & Yashunin (2016/2018):
    - Multi-layer navigable small world graph
    - Greedy search with beam width (ef)
    - Layer assignment via exponential decay: floor(-ln(uniform) * mL)
    - Cosine similarity as distance metric

    Parameters:
        max_connections: Max connections per node per layer (M).
        max_connections_layer0: Max connections on layer 0 (2 * M).
        ef_construction: Beam width during index construction.
        max_layers: Maximum number of layers in the hierarchy.
    """

    def __init__(self, max_connections: int = 16,
                 ef_construction: int = 200,
                 max_layers: int = 4) -> None:
        self.M: int = max_connections
        self.M0: int = 2 * max_connections  # layer 0 gets 2x connections
        self.ef_construction: int = ef_construction
        self.max_layers: int = max_layers
        self.mL: float = 1.0 / math.log(max_connections) if max_connections > 1 else 1.0

        # node_id -> embedding vector
        self._vectors: Dict[int, List[float]] = {}
        # node_id -> layer (the highest layer this node appears in)
        self._node_layers: Dict[int, int] = {}
        # layer -> {node_id -> set of connected node_ids}
        self._graph: Dict[int, Dict[int, Set[int]]] = defaultdict(lambda: defaultdict(set))
        # Entry point for search (node at the highest layer)
        self._entry_point: Optional[int] = None
        self._max_level: int = -1
        self._dim: int = 0

    def _cosine_distance(self, a: List[float], b: List[float]) -> float:
        """Compute cosine distance: 1 - cosine_similarity."""
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for x, y in zip(a, b):
            dot += x * y
            norm_a += x * x
            norm_b += y * y
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        return 1.0 - dot / (math.sqrt(norm_a) * math.sqrt(norm_b))

    def _random_level(self) -> int:
        """Assign a random layer level using exponential decay."""
        r = random.random()
        if r == 0.0:
            r = 1e-12
        level = int(-math.log(r) * self.mL)
        return min(level, self.max_layers - 1)

    def _search_layer(self, query: List[float], entry_point: int,
                      ef: int, layer: int) -> List[Tuple[float, int]]:
        """
        Greedy beam search on a single layer.

        Uses a min-heap for candidates (closest first) and a max-heap for
        results (farthest first for efficient pruning). This avoids the
        O(n^2) sort-inside-loop bug from the original implementation.

        Returns list of (distance, node_id) sorted by distance ascending,
        up to ef candidates.
        """
        visited: Set[int] = {entry_point}
        dist = self._cosine_distance(query, self._vectors[entry_point])
        # candidates: min-heap (closest first)
        candidates: List[Tuple[float, int]] = [(dist, entry_point)]
        # results: max-heap using negated distances (farthest first)
        results: List[Tuple[float, int]] = [(-dist, entry_point)]

        heapq.heapify(candidates)
        while candidates:
            # Pop the closest candidate
            current_dist, current = heapq.heappop(candidates)

            # If closest candidate is farther than farthest result, stop
            if len(results) >= ef and current_dist > -results[0][0]:
                break

            # Explore neighbors
            neighbors = self._graph[layer].get(current, set())
            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                visited.add(neighbor)

                if neighbor not in self._vectors:
                    continue

                n_dist = self._cosine_distance(query, self._vectors[neighbor])

                # Check if result should be added
                if len(results) < ef or n_dist < -results[0][0]:
                    heapq.heappush(candidates, (n_dist, neighbor))
                    heapq.heappush(results, (-n_dist, neighbor))
                    if len(results) > ef:
                        heapq.heappop(results)  # remove farthest

        # Convert max-heap back to sorted ascending list
        final = [(-neg_dist, nid) for neg_dist, nid in results]
        final.sort(key=lambda x: x[0])
        return final[:ef]

    def _select_neighbors(self, candidates: List[Tuple[float, int]],
                          max_neighbors: int) -> List[Tuple[float, int]]:
        """Select the best neighbors from candidates (simple selection)."""
        candidates.sort(key=lambda x: x[0])
        return candidates[:max_neighbors]

    def add_vector(self, node_id: int, embedding: List[float]) -> None:
        """
        Insert a vector into the HNSW graph.

        Args:
            node_id: Unique identifier for the vector.
            embedding: Dense embedding vector.
        """
        if not embedding:
            return

        if not self._dim:
            self._dim = len(embedding)

        self._vectors[node_id] = embedding
        level = self._random_level()
        self._node_layers[node_id] = level

        # First node — make it the entry point
        if self._entry_point is None:
            self._entry_point = node_id
            self._max_level = level
            # Initialize empty adjacency at all layers
            for lc in range(level + 1):
                self._graph[lc][node_id] = set()
            return

        # Traverse from top layer down to level+1, greedy search with ef=1
        current_entry = self._entry_point
        for lc in range(self._max_level, level, -1):
            if lc in self._graph and current_entry in self._graph[lc]:
                result = self._search_layer(embedding, current_entry, ef=1, layer=lc)
                if result:
                    current_entry = result[0][1]

        # For layers min(level, max_level) down to 0, find & connect neighbors
        for lc in range(min(level, self._max_level), -1, -1):
            max_conn = self.M0 if lc == 0 else self.M

            # Ensure node has adjacency list at this layer
            if node_id not in self._graph[lc]:
                self._graph[lc][node_id] = set()

            # Search for nearest neighbors at this layer
            if current_entry in self._vectors:
                candidates = self._search_layer(
                    embedding, current_entry, self.ef_construction, lc
                )
            else:
                candidates = []

            # Select the best neighbors
            neighbors = self._select_neighbors(candidates, max_conn)

            # Add bidirectional connections
            for dist, neighbor_id in neighbors:
                if neighbor_id == node_id:
                    continue
                self._graph[lc][node_id].add(neighbor_id)
                if neighbor_id not in self._graph[lc]:
                    self._graph[lc][neighbor_id] = set()
                self._graph[lc][neighbor_id].add(node_id)

                # Prune neighbor's connections if over limit
                if len(self._graph[lc][neighbor_id]) > max_conn:
                    # Keep only the closest max_conn neighbors
                    n_emb = self._vectors[neighbor_id]
                    scored = []
                    for conn in self._graph[lc][neighbor_id]:
                        if conn in self._vectors:
                            d = self._cosine_distance(n_emb, self._vectors[conn])
                            scored.append((d, conn))
                    scored.sort(key=lambda x: x[0])
                    keep = {s[1] for s in scored[:max_conn]}
                    self._graph[lc][neighbor_id] = keep

            if candidates:
                current_entry = candidates[0][1]

        # Update entry point if new node is at a higher level
        if level > self._max_level:
            self._entry_point = node_id
            self._max_level = level

    def search(self, query_embedding: List[float], k: int = 5,
               ef_search: int = 0) -> List[Tuple[int, float]]:
        """
        Find k approximate nearest neighbors.

        Args:
            query_embedding: Query vector.
            k: Number of neighbors to return.
            ef_search: Search beam width (default: max(k, 50)).

        Returns:
            List of (node_id, cosine_similarity) tuples, highest similarity first.
        """
        if not self._vectors or self._entry_point is None:
            return []

        if ef_search <= 0:
            ef_search = max(k, 50)

        # Traverse from top layer to layer 1 with ef=1
        current_entry = self._entry_point
        for lc in range(self._max_level, 0, -1):
            if lc in self._graph and current_entry in self._graph[lc]:
                result = self._search_layer(query_embedding, current_entry, ef=1, layer=lc)
                if result:
                    current_entry = result[0][1]

        # Search layer 0 with full ef
        candidates = self._search_layer(query_embedding, current_entry, ef_search, layer=0)

        # Convert distance to similarity and return top k
        results = []
        for dist, node_id in candidates[:k]:
            similarity = 1.0 - dist
            results.append((node_id, similarity))

        return results

    def remove(self, node_id: int) -> None:
        """
        Remove a vector from the HNSW graph.

        Removes the node and all its connections. If the removed node
        was the entry point, selects a new entry point.

        Args:
            node_id: ID of the node to remove.
        """
        if node_id not in self._vectors:
            return

        level = self._node_layers.get(node_id, 0)

        # Remove from all layers
        for lc in range(level + 1):
            if lc in self._graph and node_id in self._graph[lc]:
                # Remove node from all neighbors' adjacency lists
                for neighbor in list(self._graph[lc][node_id]):
                    if neighbor in self._graph[lc]:
                        self._graph[lc][neighbor].discard(node_id)
                del self._graph[lc][node_id]

        del self._vectors[node_id]
        del self._node_layers[node_id]

        # Update entry point if needed
        if self._entry_point == node_id:
            if not self._vectors:
                self._entry_point = None
                self._max_level = -1
            else:
                # Find the node at the highest layer
                best_id = None
                best_level = -1
                for nid, nlevel in self._node_layers.items():
                    if nlevel > best_level:
                        best_level = nlevel
                        best_id = nid
                self._entry_point = best_id
                self._max_level = best_level

    def __len__(self) -> int:
        return len(self._vectors)

    def __contains__(self, node_id: int) -> bool:
        return node_id in self._vectors

    def save_index(self, path: str) -> bool:
        """Save HNSW index to disk for persistence.

        Serializes vectors, graph structure, and metadata to a JSON file.

        Args:
            path: File path to save the index to.

        Returns:
            True if saved successfully, False otherwise.
        """
        import json as _json
        try:
            data = {
                'M': self.M,
                'M0': self.M0,
                'ef_construction': self.ef_construction,
                'max_layers': self.max_layers,
                'dim': self._dim,
                'entry_point': self._entry_point,
                'max_level': self._max_level,
                'vectors': {str(k): v for k, v in self._vectors.items()},
                'node_layers': {str(k): v for k, v in self._node_layers.items()},
                'graph': {
                    str(layer): {
                        str(node): list(neighbors)
                        for node, neighbors in layer_nodes.items()
                    }
                    for layer, layer_nodes in self._graph.items()
                },
            }
            with open(path, 'w') as f:
                _json.dump(data, f)
            logger.info(f"HNSW index saved to {path} ({len(self._vectors)} vectors)")
            return True
        except Exception as e:
            logger.error(f"Failed to save HNSW index: {e}")
            return False

    def load_index(self, path: str) -> bool:
        """Load HNSW index from disk.

        Args:
            path: File path to load the index from.

        Returns:
            True if loaded successfully, False otherwise.
        """
        import json as _json
        import os
        try:
            if not os.path.exists(path):
                return False
            with open(path, 'r') as f:
                data = _json.load(f)
            self.M = data['M']
            self.M0 = data['M0']
            self.ef_construction = data['ef_construction']
            self.max_layers = data['max_layers']
            self._dim = data['dim']
            self._entry_point = data.get('entry_point')
            self._max_level = data.get('max_level', -1)
            self._vectors = {int(k): v for k, v in data['vectors'].items()}
            self._node_layers = {int(k): v for k, v in data['node_layers'].items()}
            self._graph = defaultdict(lambda: defaultdict(set))
            for layer_str, layer_nodes in data['graph'].items():
                layer = int(layer_str)
                for node_str, neighbors in layer_nodes.items():
                    self._graph[layer][int(node_str)] = set(neighbors)
            logger.info(f"HNSW index loaded from {path} ({len(self._vectors)} vectors)")
            return True
        except Exception as e:
            logger.error(f"Failed to load HNSW index: {e}")
            return False

    def get_stats(self) -> dict:
        """Return HNSW index statistics."""
        total_edges = sum(
            sum(len(adj) for adj in layer_graph.values())
            for layer_graph in self._graph.values()
        )
        return {
            'total_vectors': len(self._vectors),
            'max_level': self._max_level,
            'entry_point': self._entry_point,
            'total_edges': total_edges,
            'dim': self._dim,
            'M': self.M,
            'ef_construction': self.ef_construction,
        }


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

    # Threshold for switching from sequential to HNSW search
    _HNSW_AUTO_THRESHOLD = 1000

    def __init__(self, use_hnsw: Optional[bool] = None) -> None:
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
        # Pure-Python HNSW index (always available, no external deps)
        self._py_hnsw: Optional[HNSWIndex] = None
        self._py_hnsw_dirty: bool = True
        # use_hnsw: None = auto (switch at > _HNSW_AUTO_THRESHOLD vectors),
        #           True = always use HNSW, False = never use HNSW
        self._use_hnsw: Optional[bool] = use_hnsw

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

    def _should_use_hnsw(self) -> bool:
        """Determine if HNSW should be used for search."""
        if self._use_hnsw is True:
            return True
        if self._use_hnsw is False:
            return False
        # Auto mode: use HNSW when vector count exceeds threshold
        return len(self.embeddings) > self._HNSW_AUTO_THRESHOLD

    def _ensure_py_hnsw(self) -> Optional[HNSWIndex]:
        """Ensure the pure-Python HNSW index is built and up-to-date."""
        if not self._should_use_hnsw() or not self.embeddings:
            return None

        if self._py_hnsw is not None and not self._py_hnsw_dirty:
            return self._py_hnsw

        # Build from scratch
        hnsw = HNSWIndex(max_connections=16, ef_construction=200, max_layers=4)
        for nid, emb in self.embeddings.items():
            hnsw.add_vector(nid, emb)
        self._py_hnsw = hnsw
        self._py_hnsw_dirty = False
        logger.debug(f"VectorIndex: rebuilt pure-Python HNSW with {len(self.embeddings)} vectors")
        return self._py_hnsw

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
            self._py_hnsw_dirty = True
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
            self._py_hnsw_dirty = True
            return len(embs)
        except Exception as e:
            logger.debug(f"VectorIndex: batch embed failed: {e}")
            return 0

    def remove_node(self, node_id: int) -> None:
        """Remove a node's embedding."""
        self.embeddings.pop(node_id, None)
        self._hnsw_dirty = True
        self._py_hnsw_dirty = True

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

        # Try hnswlib ANN search first (external C++ library)
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
                pass  # fall through to pure-Python HNSW

        # Try pure-Python HNSW (no external deps)
        py_hnsw = self._ensure_py_hnsw()
        if py_hnsw is not None:
            try:
                return py_hnsw.search(query_emb, k=top_k)
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
            except Exception as e:
                logger.debug("hnswlib search failed, falling back: %s", e)

        # Try pure-Python HNSW
        py_hnsw = self._ensure_py_hnsw()
        if py_hnsw is not None:
            try:
                return py_hnsw.search(query_emb, k=top_k)
            except Exception as e:
                logger.debug("Pure-Python HNSW search failed, falling back to brute-force: %s", e)

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

    def save_index(self, path: str) -> bool:
        """Save the vector index (embeddings + HNSW) to disk.

        Args:
            path: Base path for index files (will create .embeddings.json
                  and optionally .hnsw.json).

        Returns:
            True if saved successfully.
        """
        import json as _json
        try:
            emb_path = path + '.embeddings.json'
            data = {
                'dim': self._dim,
                'embeddings': {str(k): v for k, v in self.embeddings.items()},
            }
            with open(emb_path, 'w') as f:
                _json.dump(data, f)

            # Save HNSW if available
            if self._py_hnsw is not None:
                self._py_hnsw.save_index(path + '.hnsw.json')

            logger.info(f"VectorIndex saved to {path} ({len(self.embeddings)} embeddings)")
            return True
        except Exception as e:
            logger.error(f"Failed to save VectorIndex: {e}")
            return False

    def load_index(self, path: str) -> bool:
        """Load vector index from disk.

        Args:
            path: Base path for index files.

        Returns:
            True if loaded successfully.
        """
        import json as _json
        import os
        try:
            emb_path = path + '.embeddings.json'
            if not os.path.exists(emb_path):
                return False
            with open(emb_path, 'r') as f:
                data = _json.load(f)
            self._dim = data.get('dim', 0)
            self.embeddings = {int(k): v for k, v in data['embeddings'].items()}
            self._hnsw_dirty = True
            self._py_hnsw_dirty = True

            # Load HNSW if available
            hnsw_path = path + '.hnsw.json'
            if os.path.exists(hnsw_path):
                hnsw = HNSWIndex()
                if hnsw.load_index(hnsw_path):
                    self._py_hnsw = hnsw
                    self._py_hnsw_dirty = False

            logger.info(f"VectorIndex loaded from {path} ({len(self.embeddings)} embeddings)")
            return True
        except Exception as e:
            logger.error(f"Failed to load VectorIndex: {e}")
            return False

    def query_diversified(self, query_text: str, top_k: int = 10,
                          domain_map: Optional[Dict[int, str]] = None) -> List[Tuple[int, float]]:
        """Search with result diversification across domains.

        Ensures results come from multiple domains when possible,
        not just the single most similar cluster.

        Args:
            query_text: Search query.
            top_k: Number of results to return.
            domain_map: Optional mapping of node_id -> domain name.

        Returns:
            List of (node_id, similarity) tuples with domain diversity.
        """
        # Get more candidates than needed
        candidates = self.query(query_text, top_k=top_k * 3)

        if not domain_map or len(candidates) <= top_k:
            return candidates[:top_k]

        # Greedy diversification: pick best from each unseen domain first
        selected: List[Tuple[int, float]] = []
        domains_seen: set = set()
        remaining: List[Tuple[int, float]] = []

        for nid, score in candidates:
            domain = domain_map.get(nid, 'unknown')
            if domain not in domains_seen and len(selected) < top_k:
                selected.append((nid, score))
                domains_seen.add(domain)
            else:
                remaining.append((nid, score))

        # Fill remaining slots with best-scoring candidates
        for nid, score in remaining:
            if len(selected) >= top_k:
                break
            if nid not in {s[0] for s in selected}:
                selected.append((nid, score))

        return selected[:top_k]

    def get_stats(self) -> dict:
        """Return index statistics."""
        stats = {
            'total_embeddings': len(self.embeddings),
            'embedding_dim': self._dim,
            'uses_transformer': _USE_TRANSFORMER and _model is not None,
            'uses_hnswlib': self._hnsw_available and self._hnsw is not None,
            'uses_py_hnsw': self._py_hnsw is not None and not self._py_hnsw_dirty,
            'hnsw_mode': 'auto' if self._use_hnsw is None else str(self._use_hnsw),
            'hnsw_auto_threshold': self._HNSW_AUTO_THRESHOLD,
        }
        if self._py_hnsw is not None and not self._py_hnsw_dirty:
            stats['py_hnsw_stats'] = self._py_hnsw.get_stats()
        return stats


# --- Rust acceleration shim ---
# Only replace HNSWIndex with Rust version. VectorIndex keeps the Python
# implementation because it has add_node/add_nodes_batch/query wrappers
# that compute embeddings from content dicts — the Rust VectorIndex only
# exposes low-level add_embedding/query_by_embedding and lacks these.
try:
    from aether_core import HNSWIndex as _RustHNSWIndex  # noqa: F811
    HNSWIndex = _RustHNSWIndex  # type: ignore[misc]
    logger.info("VectorIndex: using Rust-accelerated HNSWIndex backend")
except ImportError:
    logger.debug("aether_core not installed — using pure-Python HNSWIndex")
