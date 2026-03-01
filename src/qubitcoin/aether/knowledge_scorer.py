"""
AIKGS Knowledge Scorer — Quality, novelty, and anti-gaming scoring.

Evaluates knowledge contributions on three axes:
  1. Quality (0-1.0): Specificity, concreteness, coherence, factual density
  2. Novelty (0-1.0): Cosine similarity against existing knowledge (lower sim = higher novelty)
  3. Gaming detection: Detects spam, paraphrasing, low-effort submissions

The combined score determines the contributor's quality tier:
  - Diamond (>= 0.90): Exceptional, expert-level contributions
  - Gold    (>= 0.70): High quality, well-researched
  - Silver  (>= 0.40): Acceptable quality
  - Bronze  (< 0.40):  Basic contributions
"""
import hashlib
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ContributionScore:
    """Result of scoring a knowledge contribution."""
    quality_score: float        # 0.0-1.0
    novelty_score: float        # 0.0-1.0
    combined_score: float       # Weighted combination
    tier: str                   # bronze, silver, gold, diamond
    is_spam: bool               # Flagged as spam/gaming
    spam_reason: str = ''       # Why it was flagged
    domain: str = ''            # Detected knowledge domain
    content_hash: str = ''      # SHA-256 of content for dedup
    scoring_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            'quality_score': round(self.quality_score, 4),
            'novelty_score': round(self.novelty_score, 4),
            'combined_score': round(self.combined_score, 4),
            'tier': self.tier,
            'is_spam': self.is_spam,
            'spam_reason': self.spam_reason,
            'domain': self.domain,
            'content_hash': self.content_hash,
            'scoring_time_ms': round(self.scoring_time_ms, 2),
        }


# Domain keywords for classification
DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    'quantum_physics': ['quantum', 'qubit', 'superposition', 'entanglement', 'hamiltonian', 'vqe'],
    'mathematics': ['theorem', 'proof', 'equation', 'formula', 'integral', 'algebra'],
    'computer_science': ['algorithm', 'complexity', 'compiler', 'data structure', 'hash', 'graph'],
    'blockchain': ['block', 'transaction', 'consensus', 'mining', 'chain', 'utxo', 'merkle'],
    'cryptography': ['cipher', 'encryption', 'signature', 'dilithium', 'kyber', 'hash'],
    'philosophy': ['consciousness', 'epistemology', 'ontology', 'ethics', 'reason'],
    'biology': ['cell', 'protein', 'gene', 'dna', 'evolution', 'organism'],
    'physics': ['force', 'energy', 'mass', 'velocity', 'relativity', 'particle'],
    'economics': ['market', 'supply', 'demand', 'inflation', 'monetary', 'fiscal'],
    'ai_ml': ['neural', 'training', 'model', 'inference', 'gradient', 'transformer'],
}


class KnowledgeScorer:
    """Evaluates quality and novelty of knowledge contributions."""

    def __init__(self, vector_index: object = None,
                 knowledge_graph: object = None) -> None:
        """
        Args:
            vector_index: VectorIndex for novelty computation (cosine similarity).
            knowledge_graph: KnowledgeGraph for cross-referencing.
        """
        self._vector_index = vector_index
        self._kg = knowledge_graph
        self._lock = threading.Lock()
        self._content_hashes: set = set()  # Fast duplicate detection
        self._recent_contributions: List[str] = []  # Last N for paraphrase detection
        self._max_recent = 1000
        self._max_hashes = 100000  # Maximum stored hashes
        self._score_count: int = 0
        self._flagged_count: int = 0

        # Configurable weights
        self._quality_weight = float(getattr(Config, 'AIKGS_QUALITY_WEIGHT', 0.6))
        self._novelty_weight = float(getattr(Config, 'AIKGS_NOVELTY_WEIGHT', 0.4))

    def score_contribution(self, content: str, contributor_address: str = '',
                           metadata: Optional[dict] = None) -> ContributionScore:
        """Score a knowledge contribution.

        Args:
            content: The contribution text.
            contributor_address: QBC address of the contributor.
            metadata: Optional metadata (source, context, etc.).

        Returns:
            ContributionScore with quality, novelty, tier, and spam detection.
        """
        start = time.time()

        # Content hash for dedup
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # 1. Spam / gaming detection
        is_spam, spam_reason = self._detect_gaming(content, content_hash, contributor_address)
        if is_spam:
            self._flagged_count += 1
            return ContributionScore(
                quality_score=0.0,
                novelty_score=0.0,
                combined_score=0.0,
                tier='bronze',
                is_spam=True,
                spam_reason=spam_reason,
                content_hash=content_hash,
                scoring_time_ms=(time.time() - start) * 1000,
            )

        # 2. Quality scoring
        quality = self._score_quality(content)

        # 3. Novelty scoring
        novelty = self._score_novelty(content)

        # 4. Domain detection
        domain = self._detect_domain(content)

        # 5. Combined score
        combined = (quality * self._quality_weight) + (novelty * self._novelty_weight)

        # 6. Determine tier
        tier = self._determine_tier(combined)

        # Track for future paraphrase detection (thread-safe)
        with self._lock:
            self._content_hashes.add(content_hash)
            # Evict oldest hashes if over limit (C14 memory bounds)
            if len(self._content_hashes) > self._max_hashes:
                # Convert to list, drop oldest half, rebuild set
                hash_list = list(self._content_hashes)
                self._content_hashes = set(hash_list[len(hash_list) // 2:])
            self._recent_contributions.append(content.lower())
            if len(self._recent_contributions) > self._max_recent:
                self._recent_contributions = self._recent_contributions[-self._max_recent:]
            self._score_count += 1

        return ContributionScore(
            quality_score=quality,
            novelty_score=novelty,
            combined_score=combined,
            tier=tier,
            is_spam=False,
            domain=domain,
            content_hash=content_hash,
            scoring_time_ms=(time.time() - start) * 1000,
        )

    def _score_quality(self, content: str) -> float:
        """Score content quality (0.0 - 1.0).

        Checks specificity, factual density, coherence, and length.
        """
        score = 0.5  # Baseline

        lower = content.lower()
        words = content.split()
        word_count = len(words)

        # Length bonus/penalty
        if word_count < 10:
            score -= 0.3
        elif word_count < 30:
            score -= 0.1
        elif word_count > 100:
            score += 0.1
        elif word_count > 50:
            score += 0.05

        # Specificity: concrete claims with numbers, names, formulas
        numbers = re.findall(r'\d+\.?\d*', content)
        score += min(0.15, len(numbers) * 0.03)

        # Technical terms (multi-syllable domain-relevant words)
        technical = [w for w in words if len(w) > 8]
        score += min(0.1, len(technical) * 0.02)

        # Factual signals
        factual_signals = [
            'defined as', 'measured', 'equals', 'consists of',
            'proven', 'demonstrated', 'published', 'according to',
            'formula', 'theorem', 'equation', 'property',
        ]
        fact_hits = sum(1 for s in factual_signals if s in lower)
        score += min(0.15, fact_hits * 0.05)

        # Vague penalties
        vague_signals = [
            'it depends', 'generally', 'it varies', 'maybe',
            'sort of', 'kind of', 'basically', 'honestly',
        ]
        vague_hits = sum(1 for s in vague_signals if s in lower)
        score -= min(0.2, vague_hits * 0.05)

        # Structure bonus (uses paragraphs, lists, or logical markers)
        structure_signals = ['first', 'second', 'therefore', 'however',
                             'furthermore', 'in conclusion', 'because']
        struct_hits = sum(1 for s in structure_signals if s in lower)
        score += min(0.1, struct_hits * 0.03)

        # Unique word ratio (penalize repetition)
        if word_count > 10:
            unique_ratio = len(set(w.lower() for w in words)) / word_count
            if unique_ratio < 0.4:
                score -= 0.15  # Very repetitive
            elif unique_ratio > 0.7:
                score += 0.05

        return max(0.0, min(1.0, score))

    def _score_novelty(self, content: str) -> float:
        """Score content novelty (0.0 - 1.0).

        Uses vector similarity against existing knowledge. Lower similarity
        to existing content = higher novelty score.
        """
        if not self._vector_index:
            return 0.5  # Neutral when no index available

        try:
            # Search for similar existing content using VectorIndex.query()
            results = self._vector_index.query(content, top_k=5)

            if not results:
                return 0.9  # Very novel — nothing similar found

            # Max similarity among top results
            max_similarity = max(score for _, score in results) if results else 0.0

            # Convert: high similarity = low novelty
            # sim 0.0 → novelty 1.0, sim 0.5 → novelty 0.5, sim 1.0 → novelty 0.0
            novelty = max(0.0, 1.0 - max_similarity)

            return novelty

        except Exception as e:
            logger.debug(f"Novelty scoring failed: {e}")
            return 0.5  # Neutral on error

    def _detect_gaming(self, content: str, content_hash: str,
                       contributor_address: str) -> Tuple[bool, str]:
        """Detect spam and gaming attempts.

        Checks:
        1. Exact duplicate (same content hash)
        2. Near-duplicate (high Jaccard similarity to recent)
        3. Low-effort (very short, gibberish, all-caps)
        4. Copy-paste patterns (repeated phrases)
        """
        # 1. Exact duplicate (read under lock for thread safety)
        with self._lock:
            is_dup = content_hash in self._content_hashes
        if is_dup:
            return True, "exact_duplicate"

        lower = content.lower().strip()

        # 2. Too short
        if len(lower) < 20:
            return True, "too_short"

        # 3. Gibberish detection (low letter ratio)
        alpha_count = sum(1 for c in content if c.isalpha())
        if len(content) > 0 and alpha_count / len(content) < 0.4:
            return True, "gibberish"

        # 4. All caps (shouting)
        upper_count = sum(1 for c in content if c.isupper())
        if len(content) > 20 and upper_count / len(content) > 0.8:
            return True, "all_caps"

        # 5. Repetition within content (same word repeated >30%)
        words = lower.split()
        if len(words) > 5:
            word_freq = {}
            for w in words:
                word_freq[w] = word_freq.get(w, 0) + 1
            max_freq = max(word_freq.values())
            if max_freq / len(words) > 0.3 and max_freq > 5:
                return True, "excessive_repetition"

        # 6. Near-duplicate via Jaccard similarity with recent submissions
        content_words = set(lower.split())
        for recent in self._recent_contributions[-100:]:  # Check last 100
            recent_words = set(recent.split())
            if not content_words or not recent_words:
                continue
            intersection = len(content_words & recent_words)
            union = len(content_words | recent_words)
            if union > 0 and intersection / union > 0.85:
                return True, "near_duplicate"

        return False, ""

    def _detect_domain(self, content: str) -> str:
        """Detect the knowledge domain of a contribution."""
        lower = content.lower()
        scores: Dict[str, int] = {}

        for domain, keywords in DOMAIN_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in lower)
            if count > 0:
                scores[domain] = count

        if not scores:
            return 'general'

        return max(scores, key=scores.get)

    @staticmethod
    def _determine_tier(combined_score: float) -> str:
        """Map combined score to quality tier."""
        if combined_score >= 0.90:
            return 'diamond'
        if combined_score >= 0.70:
            return 'gold'
        if combined_score >= 0.40:
            return 'silver'
        return 'bronze'

    def get_stats(self) -> dict:
        """Get scorer statistics."""
        return {
            'total_scored': self._score_count,
            'total_flagged': self._flagged_count,
            'unique_hashes': len(self._content_hashes),
            'recent_buffer_size': len(self._recent_contributions),
            'quality_weight': self._quality_weight,
            'novelty_weight': self._novelty_weight,
            'vector_index_available': self._vector_index is not None,
        }
