"""
Semantic Similarity — TF-IDF based semantic similarity for Aether Tree

Item #44: Real semantic similarity using learned TF-IDF embeddings.
Vocabulary pruning, cosine similarity, batch similarity matrix.
"""
import math
import re
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Simple tokenizer: lowercase, split on non-alphanumeric
_TOKEN_RE = re.compile(r'[a-z0-9]+')

# Default stopwords (common English words that carry little meaning)
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "must", "i", "me", "my",
    "you", "your", "he", "she", "it", "we", "they", "him", "her", "its",
    "our", "their", "this", "that", "these", "those", "in", "on", "at",
    "to", "for", "with", "from", "by", "of", "about", "and", "or", "but",
    "not", "no", "so", "if", "as", "up", "out", "then", "than", "too",
    "very", "just", "also", "more", "most", "some", "any", "all", "each",
    "every", "both", "few", "many", "much", "own", "other", "such",
    "what", "which", "who", "whom", "how", "when", "where", "why",
})


def _tokenize(text: str) -> List[str]:
    """Lowercase and tokenize text, removing stopwords."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class SemanticSimilarity:
    """TF-IDF vectorizer with cosine similarity for semantic matching."""

    def __init__(self, min_df: int = 2, max_df_ratio: float = 0.85,
                 max_vocab: int = 50000) -> None:
        """
        Args:
            min_df: Minimum document frequency for a term to be included.
            max_df_ratio: Maximum document frequency ratio (0–1) for pruning.
            max_vocab: Maximum vocabulary size.
        """
        self._min_df = min_df
        self._max_df_ratio = max_df_ratio
        self._max_vocab = max_vocab

        # Vocabulary: term → index
        self._vocab: Dict[str, int] = {}
        # IDF weights (shape: [vocab_size])
        self._idf: Optional[np.ndarray] = None
        # Number of documents used in fit
        self._n_docs: int = 0
        # Whether the model has been fit
        self._fitted: bool = False

        # Stats
        self._fit_calls: int = 0
        self._encode_calls: int = 0
        self._similarity_calls: int = 0
        self._total_time: float = 0.0

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, texts: List[str]) -> None:
        """Build vocabulary and compute IDF weights from a corpus.

        Args:
            texts: List of text documents to learn vocabulary from.
        """
        t0 = time.time()
        n = len(texts)
        if n == 0:
            return

        # Count document frequency for each term
        df: Dict[str, int] = {}
        for text in texts:
            tokens = set(_tokenize(text))
            for tok in tokens:
                df[tok] = df.get(tok, 0) + 1

        # Prune: remove terms below min_df or above max_df_ratio
        max_df = int(n * self._max_df_ratio)
        pruned = {
            term: count for term, count in df.items()
            if count >= self._min_df and count <= max_df
        }

        # Sort by frequency (descending) and limit vocabulary size
        sorted_terms = sorted(pruned.items(), key=lambda x: -x[1])
        if len(sorted_terms) > self._max_vocab:
            sorted_terms = sorted_terms[:self._max_vocab]

        self._vocab = {term: idx for idx, (term, _) in enumerate(sorted_terms)}
        vocab_size = len(self._vocab)

        # Compute IDF: log(N / df) + 1 (smooth)
        self._idf = np.zeros(vocab_size, dtype=np.float64)
        for term, idx in self._vocab.items():
            self._idf[idx] = math.log(n / (pruned[term] + 1)) + 1.0

        self._n_docs = n
        self._fitted = True
        self._fit_calls += 1
        self._total_time += time.time() - t0

        logger.info(
            f"SemanticSimilarity fit: {n} docs, {vocab_size} vocab terms, "
            f"pruned {len(df) - vocab_size} terms"
        )

    # ------------------------------------------------------------------
    # Encode
    # ------------------------------------------------------------------

    def encode(self, text: str) -> np.ndarray:
        """Encode text as a TF-IDF vector.

        Args:
            text: Input text.

        Returns:
            TF-IDF vector (shape: [vocab_size]). Zero vector if not fitted.
        """
        self._encode_calls += 1

        if not self._fitted or self._idf is None:
            return np.zeros(1, dtype=np.float64)

        tokens = _tokenize(text)
        vocab_size = len(self._vocab)
        tf = np.zeros(vocab_size, dtype=np.float64)

        for tok in tokens:
            idx = self._vocab.get(tok)
            if idx is not None:
                tf[idx] += 1.0

        # Normalize TF (sublinear: 1 + log(tf))
        nonzero = tf > 0
        tf[nonzero] = 1.0 + np.log(tf[nonzero])

        # TF-IDF = TF * IDF
        tfidf = tf * self._idf

        # L2 normalize
        norm = np.linalg.norm(tfidf)
        if norm > 0:
            tfidf /= norm

        return tfidf

    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------

    def similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two texts.

        Args:
            text_a: First text.
            text_b: Second text.

        Returns:
            Cosine similarity in [-1, 1] (typically [0, 1] for TF-IDF).
        """
        t0 = time.time()
        self._similarity_calls += 1

        vec_a = self.encode(text_a)
        vec_b = self.encode(text_b)

        dot = float(np.dot(vec_a, vec_b))
        self._total_time += time.time() - t0
        return dot  # Already L2-normalized

    def find_similar(self, query: str, corpus: List[str],
                     top_k: int = 5) -> List[Tuple[str, float]]:
        """Find the most similar texts in a corpus.

        Args:
            query: Query text.
            corpus: List of candidate texts.
            top_k: Number of results to return.

        Returns:
            List of (text, similarity_score) tuples, descending by score.
        """
        t0 = time.time()
        query_vec = self.encode(query)

        scores: List[Tuple[int, float]] = []
        for i, text in enumerate(corpus):
            vec = self.encode(text)
            score = float(np.dot(query_vec, vec))
            scores.append((i, score))

        scores.sort(key=lambda x: -x[1])
        results = [(corpus[idx], score) for idx, score in scores[:top_k]]
        self._total_time += time.time() - t0
        return results

    def batch_similarity(self, queries: List[str],
                         corpus: List[str]) -> np.ndarray:
        """Compute similarity matrix between queries and corpus.

        Args:
            queries: List of query texts.
            corpus: List of corpus texts.

        Returns:
            Similarity matrix of shape (len(queries), len(corpus)).
        """
        t0 = time.time()

        if not self._fitted:
            return np.zeros((len(queries), len(corpus)), dtype=np.float64)

        q_vecs = np.array([self.encode(q) for q in queries])
        c_vecs = np.array([self.encode(c) for c in corpus])

        # Matrix multiplication for batch cosine similarity
        # Both are already L2-normalized
        sim_matrix = q_vecs @ c_vecs.T

        self._total_time += time.time() - t0
        return sim_matrix

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def vocab_size(self) -> int:
        """Current vocabulary size."""
        return len(self._vocab)

    @property
    def is_fitted(self) -> bool:
        """Whether the model has been fit."""
        return self._fitted

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return similarity engine statistics."""
        return {
            "fitted": self._fitted,
            "vocab_size": len(self._vocab),
            "n_docs_trained": self._n_docs,
            "fit_calls": self._fit_calls,
            "encode_calls": self._encode_calls,
            "similarity_calls": self._similarity_calls,
            "total_time_s": round(self._total_time, 4),
        }
