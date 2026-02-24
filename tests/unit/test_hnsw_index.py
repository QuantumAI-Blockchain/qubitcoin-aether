"""
Tests for HNSWIndex and VectorIndex HNSW integration.

Covers:
- HNSWIndex standalone: add, search, remove, stats
- Multi-layer structure
- Cosine similarity correctness
- VectorIndex HNSW auto-switching
- VectorIndex forced HNSW mode
- Edge cases (empty index, single vector, duplicate IDs)
"""
import math
import random

import pytest

from qubitcoin.aether.vector_index import HNSWIndex, VectorIndex, cosine_similarity


# ============================================================================
# Helper functions
# ============================================================================

def _random_vector(dim: int = 64, seed: int = 0) -> list:
    """Generate a deterministic random unit vector."""
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _similar_vector(base: list, noise: float = 0.05, seed: int = 0) -> list:
    """Generate a vector similar to base with small noise."""
    rng = random.Random(seed)
    vec = [x + rng.gauss(0, noise) for x in base]
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


# ============================================================================
# 1. HNSWIndex standalone tests
# ============================================================================

class TestHNSWIndexBasic:
    """Basic HNSWIndex operations."""

    def test_add_single_vector(self) -> None:
        """Adding a single vector succeeds and index has length 1."""
        idx = HNSWIndex()
        vec = _random_vector(dim=32, seed=1)
        idx.add_vector(1, vec)
        assert len(idx) == 1
        assert 1 in idx

    def test_add_multiple_vectors(self) -> None:
        """Adding multiple vectors maintains correct count."""
        idx = HNSWIndex(max_connections=4, max_layers=3)
        for i in range(100):
            idx.add_vector(i, _random_vector(dim=16, seed=i))
        assert len(idx) == 100

    def test_search_returns_k_results(self) -> None:
        """Search returns exactly k results when enough vectors exist."""
        idx = HNSWIndex(max_connections=8, max_layers=3)
        for i in range(50):
            idx.add_vector(i, _random_vector(dim=32, seed=i))
        query = _random_vector(dim=32, seed=999)
        results = idx.search(query, k=5)
        assert len(results) == 5

    def test_search_returns_similarity_scores(self) -> None:
        """Search results contain (node_id, similarity) tuples."""
        idx = HNSWIndex(max_connections=8)
        for i in range(20):
            idx.add_vector(i, _random_vector(dim=16, seed=i))
        results = idx.search(_random_vector(dim=16, seed=100), k=3)
        for node_id, similarity in results:
            assert isinstance(node_id, int)
            assert isinstance(similarity, float)
            assert -1.0 <= similarity <= 1.0 + 1e-6

    def test_search_finds_exact_match(self) -> None:
        """Searching for an existing vector finds it as top result."""
        idx = HNSWIndex(max_connections=8, max_layers=3)
        target = _random_vector(dim=32, seed=77777)
        for i in range(50):
            idx.add_vector(i, _random_vector(dim=32, seed=i + 10000))
        idx.add_vector(999, target)

        results = idx.search(target, k=1)
        assert len(results) >= 1
        top_id, top_sim = results[0]
        assert top_id == 999
        assert top_sim > 0.99

    def test_search_ranks_similar_higher(self) -> None:
        """A vector similar to the query ranks higher than a random one."""
        idx = HNSWIndex(max_connections=8, max_layers=3)
        base = _random_vector(dim=32, seed=0)
        similar = _similar_vector(base, noise=0.01, seed=1)
        dissimilar = _random_vector(dim=32, seed=100)

        idx.add_vector(1, similar)
        idx.add_vector(2, dissimilar)

        results = idx.search(base, k=2)
        # Similar vector should rank first
        assert results[0][0] == 1
        assert results[0][1] > results[1][1]

    def test_remove_vector(self) -> None:
        """Removing a vector decreases count and excludes it from search."""
        idx = HNSWIndex(max_connections=4)
        for i in range(10):
            idx.add_vector(i, _random_vector(dim=16, seed=i))

        assert len(idx) == 10
        idx.remove(5)
        assert len(idx) == 9
        assert 5 not in idx

        # Search should not return removed vector
        results = idx.search(_random_vector(dim=16, seed=5), k=10)
        result_ids = {r[0] for r in results}
        assert 5 not in result_ids

    def test_remove_nonexistent_is_noop(self) -> None:
        """Removing a nonexistent vector does nothing."""
        idx = HNSWIndex()
        idx.add_vector(1, _random_vector(dim=8, seed=1))
        idx.remove(999)  # Should not raise
        assert len(idx) == 1

    def test_remove_entry_point(self) -> None:
        """Removing the entry point selects a new one."""
        idx = HNSWIndex(max_connections=4, max_layers=2)
        for i in range(5):
            idx.add_vector(i, _random_vector(dim=8, seed=i))

        entry = idx._entry_point
        idx.remove(entry)
        assert idx._entry_point is not None
        assert idx._entry_point != entry

    def test_search_empty_index(self) -> None:
        """Searching an empty index returns empty list."""
        idx = HNSWIndex()
        results = idx.search(_random_vector(dim=8, seed=0), k=5)
        assert results == []

    def test_get_stats(self) -> None:
        """get_stats returns expected fields."""
        idx = HNSWIndex(max_connections=8, ef_construction=100, max_layers=3)
        for i in range(10):
            idx.add_vector(i, _random_vector(dim=16, seed=i))

        stats = idx.get_stats()
        assert stats['total_vectors'] == 10
        assert stats['M'] == 8
        assert stats['ef_construction'] == 100
        assert stats['dim'] == 16
        assert stats['max_level'] >= 0
        assert stats['total_edges'] > 0


# ============================================================================
# 2. HNSWIndex multi-layer structure
# ============================================================================

class TestHNSWLayers:
    """Tests for multi-layer graph structure."""

    def test_layers_are_created(self) -> None:
        """Adding enough vectors creates multiple layers."""
        idx = HNSWIndex(max_connections=4, max_layers=4)
        # Add enough nodes that at least some land on higher layers
        random.seed(42)
        for i in range(200):
            idx.add_vector(i, _random_vector(dim=8, seed=i))
        assert idx._max_level >= 1, "Expected at least 2 layers with 200 nodes"

    def test_max_layers_respected(self) -> None:
        """No node exceeds the max_layers limit."""
        idx = HNSWIndex(max_connections=4, max_layers=3)
        random.seed(123)
        for i in range(100):
            idx.add_vector(i, _random_vector(dim=8, seed=i))
        for nid, level in idx._node_layers.items():
            assert level < 3, f"Node {nid} at level {level} exceeds max_layers=3"


# ============================================================================
# 3. Cosine similarity correctness
# ============================================================================

class TestCosineDistance:
    """Tests for cosine distance computation in HNSW."""

    def test_identical_vectors_zero_distance(self) -> None:
        """Identical vectors have cosine distance 0."""
        idx = HNSWIndex()
        vec = [1.0, 2.0, 3.0]
        assert abs(idx._cosine_distance(vec, vec)) < 1e-10

    def test_orthogonal_vectors_distance_one(self) -> None:
        """Orthogonal vectors have cosine distance 1."""
        idx = HNSWIndex()
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(idx._cosine_distance(a, b) - 1.0) < 1e-10

    def test_opposite_vectors_distance_two(self) -> None:
        """Opposite vectors have cosine distance 2."""
        idx = HNSWIndex()
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(idx._cosine_distance(a, b) - 2.0) < 1e-10

    def test_zero_vector_distance_one(self) -> None:
        """Zero vector has distance 1 from any vector."""
        idx = HNSWIndex()
        assert idx._cosine_distance([0.0, 0.0], [1.0, 2.0]) == 1.0


# ============================================================================
# 4. VectorIndex HNSW integration
# ============================================================================

class TestVectorIndexHNSW:
    """Tests for VectorIndex with HNSW integration."""

    def test_auto_mode_default(self) -> None:
        """Default VectorIndex has use_hnsw=None (auto mode)."""
        vi = VectorIndex()
        assert vi._use_hnsw is None

    def test_forced_hnsw_mode(self) -> None:
        """VectorIndex(use_hnsw=True) forces HNSW for all queries."""
        vi = VectorIndex(use_hnsw=True)
        assert vi._use_hnsw is True
        assert vi._should_use_hnsw() is True

    def test_forced_sequential_mode(self) -> None:
        """VectorIndex(use_hnsw=False) forces sequential search."""
        vi = VectorIndex(use_hnsw=False)
        assert vi._use_hnsw is False
        assert vi._should_use_hnsw() is False

    def test_auto_mode_switches_at_threshold(self) -> None:
        """Auto mode activates HNSW when embeddings exceed threshold."""
        vi = VectorIndex()
        # Below threshold: sequential
        for i in range(100):
            vi.embeddings[i] = _random_vector(dim=16, seed=i)
        assert vi._should_use_hnsw() is False

        # Above threshold
        for i in range(100, 1100):
            vi.embeddings[i] = _random_vector(dim=16, seed=i)
        vi._dim = 16
        assert vi._should_use_hnsw() is True

    def test_ensure_py_hnsw_builds_index(self) -> None:
        """_ensure_py_hnsw builds and returns the HNSW index when forced."""
        vi = VectorIndex(use_hnsw=True)
        for i in range(20):
            vi.embeddings[i] = _random_vector(dim=16, seed=i)
        vi._dim = 16

        hnsw = vi._ensure_py_hnsw()
        assert hnsw is not None
        assert isinstance(hnsw, HNSWIndex)
        assert len(hnsw) == 20

    def test_query_by_embedding_uses_hnsw(self) -> None:
        """query_by_embedding returns results via HNSW when forced."""
        vi = VectorIndex(use_hnsw=True)
        target = _random_vector(dim=16, seed=42)
        for i in range(30):
            vi.embeddings[i] = _random_vector(dim=16, seed=i)
        vi.embeddings[999] = target
        vi._dim = 16
        vi._py_hnsw_dirty = True

        results = vi.query_by_embedding(target, top_k=5)
        assert len(results) >= 1
        # The target itself should be the top match
        top_id, top_sim = results[0]
        assert top_id == 999
        assert top_sim > 0.99

    def test_get_stats_includes_hnsw_info(self) -> None:
        """get_stats reports HNSW status."""
        vi = VectorIndex(use_hnsw=True)
        for i in range(10):
            vi.embeddings[i] = _random_vector(dim=8, seed=i)
        vi._dim = 8
        vi._ensure_py_hnsw()

        stats = vi.get_stats()
        assert 'uses_py_hnsw' in stats
        assert 'hnsw_mode' in stats
        assert stats['uses_py_hnsw'] is True
        assert 'py_hnsw_stats' in stats

    def test_remove_node_marks_hnsw_dirty(self) -> None:
        """Removing a node marks the HNSW index as dirty."""
        vi = VectorIndex(use_hnsw=True)
        for i in range(10):
            vi.embeddings[i] = _random_vector(dim=8, seed=i)
        vi._dim = 8
        vi._ensure_py_hnsw()
        assert vi._py_hnsw_dirty is False

        vi.remove_node(5)
        assert vi._py_hnsw_dirty is True


# ============================================================================
# 5. HNSWIndex with many vectors (scale test)
# ============================================================================

class TestHNSWScale:
    """Tests for HNSW at moderate scale."""

    def test_500_vectors_search_accuracy(self) -> None:
        """HNSW search on 500 vectors finds the true nearest neighbor."""
        idx = HNSWIndex(max_connections=16, ef_construction=200, max_layers=4)
        dim = 32
        random.seed(0)
        vectors = {}
        for i in range(500):
            vec = _random_vector(dim=dim, seed=i)
            vectors[i] = vec
            idx.add_vector(i, vec)

        # Query with a known vector — should find itself
        query_id = 250
        results = idx.search(vectors[query_id], k=1)
        assert results[0][0] == query_id

    def test_500_vectors_top_5_quality(self) -> None:
        """Top-5 HNSW results overlap with brute-force top-5 for most queries."""
        idx = HNSWIndex(max_connections=16, ef_construction=200, max_layers=4)
        dim = 32
        vectors = {}
        for i in range(500):
            vec = _random_vector(dim=dim, seed=i)
            vectors[i] = vec
            idx.add_vector(i, vec)

        # Check a few queries for recall
        queries = [_random_vector(dim=dim, seed=1000 + q) for q in range(5)]
        for query in queries:
            hnsw_results = idx.search(query, k=5, ef_search=100)
            hnsw_ids = {r[0] for r in hnsw_results}

            # Brute-force ground truth
            brute = []
            for nid, vec in vectors.items():
                sim = cosine_similarity(query, vec)
                brute.append((nid, sim))
            brute.sort(key=lambda x: x[1], reverse=True)
            brute_ids = {r[0] for r in brute[:5]}

            # At least 3 out of 5 should overlap (HNSW is approximate)
            overlap = len(hnsw_ids & brute_ids)
            assert overlap >= 3, f"Only {overlap}/5 overlap: hnsw={hnsw_ids}, brute={brute_ids}"
