"""
TF-IDF Index for Knowledge Graph — Semantic Search

Replaces naive keyword matching with TF-IDF cosine similarity.
Maintains an inverted index that updates incrementally as nodes are added.
"""
import math
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Common stop words to filter out
_STOP_WORDS = frozenset({
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
    'before', 'after', 'above', 'below', 'between', 'out', 'off', 'over',
    'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
    'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'because', 'but', 'and',
    'or', 'if', 'while', 'about', 'up', 'it', 'its', 'this', 'that',
    'these', 'those', 'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he',
    'him', 'his', 'she', 'her', 'they', 'them', 'their', 'what', 'which',
    'who', 'whom', 'also', 'well', 'like', 'even', 'still', 'much',
})

_TOKEN_RE = re.compile(r'[a-z0-9]+')


def _tokenize(text: str) -> List[str]:
    """Lowercase, split into tokens, filter stop words and short tokens."""
    return [
        t for t in _TOKEN_RE.findall(text.lower())
        if t not in _STOP_WORDS and len(t) > 2
    ]


def _extract_text(content: dict) -> str:
    """Extract searchable text from a KeterNode's content dict."""
    parts = []
    for key in ('text', 'description', 'subject', 'query', 'content',
                'block_hash', 'miner_address', 'node_type'):
        val = content.get(key)
        if isinstance(val, str):
            parts.append(val)
    return ' '.join(parts)


class TFIDFIndex:
    """
    Incremental TF-IDF index over knowledge graph nodes.

    Maintains:
      - inverted_index: {term: {node_id: tf_score}}
      - doc_freq: {term: count_of_docs_containing_term}
      - doc_norms: {node_id: L2 norm of TF-IDF vector}

    Supports incremental updates — no full rebuild needed when new nodes arrive.
    """

    # Refresh IDF cache every N additions instead of on every query.
    # With 693K+ nodes and millions of terms, full IDF refresh takes 5-10s.
    _IDF_REFRESH_INTERVAL: int = 1000

    def __init__(self) -> None:
        # term -> {node_id: raw term frequency}
        self.inverted_index: Dict[str, Dict[int, float]] = defaultdict(dict)
        # term -> number of documents containing term
        self.doc_freq: Dict[str, int] = defaultdict(int)
        # node_id -> set of terms (for removal)
        self.node_terms: Dict[int, set] = {}
        # total documents indexed
        self.n_docs: int = 0
        # cached IDF values (refreshed periodically, not on every query)
        self._idf_cache: Dict[str, float] = {}
        self._idf_dirty: bool = True
        self._adds_since_refresh: int = 0

    def add_node(self, node_id: int, content: dict) -> None:
        """Index a single node's content. Incremental — no rebuild needed."""
        text = _extract_text(content)
        tokens = _tokenize(text)
        if not tokens:
            return

        # Compute term frequencies
        tf: Dict[str, float] = defaultdict(float)
        for token in tokens:
            tf[token] += 1.0

        # Normalize TF by max frequency in document
        max_tf = max(tf.values()) if tf else 1.0
        for term in tf:
            tf[term] = 0.5 + 0.5 * (tf[term] / max_tf)  # augmented TF

        # Update inverted index
        new_terms = set()
        for term, score in tf.items():
            if node_id not in self.inverted_index[term]:
                self.doc_freq[term] += 1
            self.inverted_index[term][node_id] = score
            new_terms.add(term)

        self.node_terms[node_id] = new_terms
        self.n_docs += 1
        self._adds_since_refresh += 1
        # Amortize IDF refresh: update every N additions, not on every query.
        # This prevents 5-10s stalls when search is called with a dirty cache.
        if self._adds_since_refresh >= self._IDF_REFRESH_INTERVAL:
            self._refresh_idf()
            self._adds_since_refresh = 0
        else:
            self._idf_dirty = True

    def remove_node(self, node_id: int) -> None:
        """Remove a node from the index."""
        terms = self.node_terms.pop(node_id, set())
        for term in terms:
            if term in self.inverted_index:
                self.inverted_index[term].pop(node_id, None)
                self.doc_freq[term] = max(0, self.doc_freq.get(term, 1) - 1)
                if not self.inverted_index[term]:
                    del self.inverted_index[term]
                    del self.doc_freq[term]
        self.n_docs = max(0, self.n_docs - 1)
        self._idf_dirty = True

    def query(self, query_text: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Search the index with a natural language query.

        Returns:
            List of (node_id, cosine_similarity_score) tuples, highest first.
        """
        if self.n_docs == 0:
            return []

        tokens = _tokenize(query_text)
        if not tokens:
            return []

        # Use stale IDF cache if available — only refresh if cache is empty.
        # Amortized refresh happens during add_node() every N additions.
        if not self._idf_cache:
            self._refresh_idf()

        # Build query TF-IDF vector
        q_tf: Dict[str, float] = defaultdict(float)
        for t in tokens:
            q_tf[t] += 1.0
        max_q = max(q_tf.values()) if q_tf else 1.0

        q_tfidf: Dict[str, float] = {}
        for term, count in q_tf.items():
            if term in self._idf_cache:
                q_tfidf[term] = (0.5 + 0.5 * count / max_q) * self._idf_cache[term]

        if not q_tfidf:
            return []

        q_norm = math.sqrt(sum(v * v for v in q_tfidf.values()))
        if q_norm == 0:
            return []

        # Score each candidate document
        scores: Dict[int, float] = defaultdict(float)
        for term, q_weight in q_tfidf.items():
            idf = self._idf_cache.get(term, 0)
            for node_id, tf_score in self.inverted_index.get(term, {}).items():
                scores[node_id] += q_weight * (tf_score * idf)

        # Normalize by document norms for cosine similarity
        results = []
        for node_id, dot_product in scores.items():
            # Compute doc norm on-the-fly
            doc_terms = self.node_terms.get(node_id, set())
            doc_norm_sq = sum(
                (self.inverted_index.get(t, {}).get(node_id, 0) * self._idf_cache.get(t, 0)) ** 2
                for t in doc_terms
            )
            doc_norm = math.sqrt(doc_norm_sq) if doc_norm_sq > 0 else 1.0
            cosine = dot_product / (q_norm * doc_norm)
            results.append((node_id, cosine))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _refresh_idf(self) -> None:
        """Recompute IDF cache if dirty."""
        if not self._idf_dirty:
            return
        n = max(self.n_docs, 1)
        # Smoothed IDF: log((1 + n) / (1 + df)) + 1  (sklearn default)
        self._idf_cache = {
            term: math.log((1 + n) / (1 + df)) + 1.0
            for term, df in self.doc_freq.items()
        }
        self._idf_dirty = False

    def get_stats(self) -> dict:
        """Return index statistics."""
        return {
            'total_docs': self.n_docs,
            'unique_terms': len(self.doc_freq),
            'avg_terms_per_doc': (
                sum(len(t) for t in self.node_terms.values()) / max(self.n_docs, 1)
            ),
        }
