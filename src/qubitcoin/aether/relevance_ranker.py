"""
Relevance Ranking for Chat Responses (#53)

Rank KG nodes and candidate responses by relevance to a query:
- BM25-style term frequency scoring
- Text overlap (Jaccard similarity)
- Recency boost
- Domain and entity match boosts
- Confidence weighting
"""
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RankedResult:
    """A ranked candidate with score and explanation."""
    item: dict
    score: float
    explanation: str

    def to_dict(self) -> dict:
        return {
            'item': self.item,
            'score': round(self.score, 4),
            'explanation': self.explanation,
        }


class RelevanceRanker:
    """Rank KG nodes and candidate responses by relevance to a query."""

    # BM25 parameters
    K1: float = 1.5
    B: float = 0.75

    # Boost factors
    EXACT_ENTITY_BOOST: float = 2.0
    DOMAIN_MATCH_BOOST: float = 1.5
    RECENCY_BOOST: float = 1.3    # For items within recency_window blocks
    CONFIDENCE_WEIGHT: float = 0.5

    def __init__(self, recency_window: int = 100) -> None:
        self._recency_window = recency_window

        # Stats
        self._calls: int = 0
        self._total_candidates: int = 0
        self._last_call: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rank(self, query: str, candidates: List[dict],
             top_k: int = 5,
             current_block: int = 0,
             domain_hint: str = '') -> List[Tuple[dict, float]]:
        """Rank candidates by relevance to query.

        Args:
            query: The user's query string.
            candidates: List of dicts (each must have at least 'text' or 'content').
            top_k: Number of top results to return.
            current_block: Current block height (for recency scoring).
            domain_hint: Optional domain to boost matching candidates.

        Returns:
            List of (candidate_dict, score) tuples, sorted by descending score.
        """
        self._calls += 1
        self._last_call = time.time()
        self._total_candidates += len(candidates)

        if not candidates or not query.strip():
            return []

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Pre-compute average document length for BM25
        doc_lengths: List[int] = []
        doc_term_lists: List[List[str]] = []
        for cand in candidates:
            text = self._extract_text(cand)
            terms = self._tokenize(text)
            doc_term_lists.append(terms)
            doc_lengths.append(len(terms))

        avg_doc_len = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0

        # Compute IDF for query terms
        idf = self._compute_idf(query_terms, doc_term_lists)

        scored: List[Tuple[dict, float, str]] = []

        for i, cand in enumerate(candidates):
            doc_terms = doc_term_lists[i]
            explanations: List[str] = []

            # BM25 score
            bm25 = self.compute_bm25(query_terms, doc_terms, avg_doc_len, idf)
            explanations.append(f"BM25={bm25:.3f}")

            # Jaccard overlap
            jaccard = self._jaccard(set(query_terms), set(doc_terms))
            explanations.append(f"Jaccard={jaccard:.3f}")

            # Combined base score
            score = bm25 * 0.7 + jaccard * 0.3

            # Confidence boost
            confidence = cand.get('confidence', 0.5)
            score += confidence * self.CONFIDENCE_WEIGHT
            explanations.append(f"conf={confidence:.2f}")

            # Exact entity match boost
            entities = cand.get('entities', {})
            entity_text = ' '.join(str(v) for v in entities.values()).lower()
            if entity_text:
                query_lower = query.lower()
                if any(str(v).lower() in query_lower for v in entities.values()):
                    score *= self.EXACT_ENTITY_BOOST
                    explanations.append(f"entity_boost={self.EXACT_ENTITY_BOOST}x")

            # Domain match boost
            cand_domain = cand.get('domain', '')
            if domain_hint and cand_domain == domain_hint:
                score *= self.DOMAIN_MATCH_BOOST
                explanations.append(f"domain_boost={self.DOMAIN_MATCH_BOOST}x")

            # Recency boost
            source_block = cand.get('source_block', 0)
            if current_block > 0 and source_block > 0:
                age = current_block - source_block
                if age <= self._recency_window:
                    score *= self.RECENCY_BOOST
                    explanations.append(f"recency_boost={self.RECENCY_BOOST}x")

            scored.append((cand, score, "; ".join(explanations)))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            (item, score)
            for item, score, _ in scored[:top_k]
        ]

    def rank_with_explanations(self, query: str, candidates: List[dict],
                               top_k: int = 5,
                               current_block: int = 0,
                               domain_hint: str = '') -> List[RankedResult]:
        """Rank candidates and return RankedResult objects with explanations.

        Same as rank() but returns RankedResult with explanation strings.
        """
        self._calls += 1
        self._last_call = time.time()
        self._total_candidates += len(candidates)

        if not candidates or not query.strip():
            return []

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        doc_term_lists: List[List[str]] = []
        for cand in candidates:
            text = self._extract_text(cand)
            doc_term_lists.append(self._tokenize(text))

        avg_doc_len = (
            sum(len(dt) for dt in doc_term_lists) / len(doc_term_lists)
            if doc_term_lists else 1.0
        )

        idf = self._compute_idf(query_terms, doc_term_lists)

        results: List[RankedResult] = []

        for i, cand in enumerate(candidates):
            doc_terms = doc_term_lists[i]
            parts: List[str] = []

            bm25 = self.compute_bm25(query_terms, doc_terms, avg_doc_len, idf)
            jaccard = self._jaccard(set(query_terms), set(doc_terms))
            score = bm25 * 0.7 + jaccard * 0.3

            parts.append(f"BM25={bm25:.3f}")
            parts.append(f"Jaccard={jaccard:.3f}")

            confidence = cand.get('confidence', 0.5)
            score += confidence * self.CONFIDENCE_WEIGHT

            # Entity boost
            entities = cand.get('entities', {})
            query_lower = query.lower()
            if entities and any(str(v).lower() in query_lower for v in entities.values()):
                score *= self.EXACT_ENTITY_BOOST
                parts.append("entity_match")

            # Domain boost
            if domain_hint and cand.get('domain', '') == domain_hint:
                score *= self.DOMAIN_MATCH_BOOST
                parts.append("domain_match")

            # Recency boost
            source_block = cand.get('source_block', 0)
            if current_block > 0 and source_block > 0:
                if current_block - source_block <= self._recency_window:
                    score *= self.RECENCY_BOOST
                    parts.append("recent")

            results.append(RankedResult(
                item=cand,
                score=score,
                explanation="; ".join(parts),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def compute_bm25(self, query_terms: List[str], doc_terms: List[str],
                     avg_doc_len: float,
                     idf: Optional[Dict[str, float]] = None) -> float:
        """Compute BM25 score for a single document.

        Args:
            query_terms: Tokenized query.
            doc_terms: Tokenized document.
            avg_doc_len: Average document length across corpus.
            idf: Pre-computed IDF dict. If None, uses uniform IDF=1.

        Returns:
            BM25 score (float).
        """
        if not query_terms or not doc_terms:
            return 0.0

        # Term frequencies in document
        tf: Dict[str, int] = {}
        for t in doc_terms:
            tf[t] = tf.get(t, 0) + 1

        doc_len = len(doc_terms)
        score = 0.0

        for term in query_terms:
            if term not in tf:
                continue
            f = tf[term]
            term_idf = idf.get(term, 1.0) if idf else 1.0
            numerator = f * (self.K1 + 1)
            denominator = f + self.K1 * (1 - self.B + self.B * doc_len / max(avg_doc_len, 1.0))
            score += term_idf * (numerator / denominator)

        return score

    def get_stats(self) -> dict:
        """Return runtime statistics."""
        return {
            'calls': self._calls,
            'total_candidates_ranked': self._total_candidates,
            'recency_window': self._recency_window,
            'last_call': self._last_call,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple whitespace + punctuation tokenizer with lowercasing."""
        if not text:
            return []
        tokens = re.findall(r'\b\w+\b', text.lower())
        # Remove very short tokens and stop words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'can', 'shall',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'as', 'into', 'through', 'during', 'before', 'after', 'and',
            'but', 'or', 'not', 'no', 'if', 'then', 'else', 'when',
            'up', 'out', 'about', 'it', 'its', 'this', 'that', 'these',
            'those', 'i', 'me', 'my', 'we', 'our', 'you', 'your',
            'he', 'she', 'they', 'them', 'what', 'which', 'who',
        }
        return [t for t in tokens if len(t) > 1 and t not in stop_words]

    @staticmethod
    def _jaccard(set_a: set, set_b: set) -> float:
        """Jaccard similarity between two sets."""
        if not set_a and not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _compute_idf(query_terms: List[str],
                     doc_term_lists: List[List[str]]) -> Dict[str, float]:
        """Compute IDF for query terms across the document corpus."""
        n_docs = len(doc_term_lists)
        if n_docs == 0:
            return {}

        idf: Dict[str, float] = {}
        for term in set(query_terms):
            df = sum(1 for doc in doc_term_lists if term in doc)
            # BM25 IDF formula
            idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

        return idf

    @staticmethod
    def _extract_text(candidate: dict) -> str:
        """Extract searchable text from a candidate dict."""
        parts: List[str] = []

        for key in ('text', 'content', 'description', 'summary', 'title'):
            val = candidate.get(key)
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, dict):
                for v in val.values():
                    if isinstance(v, str):
                        parts.append(v)

        # Also include entity text
        entities = candidate.get('entities', {})
        if isinstance(entities, dict):
            for v in entities.values():
                if isinstance(v, (str, int, float)):
                    parts.append(str(v))

        return ' '.join(parts)
