"""
Sentiment Analyzer — Lexicon-based sentiment analysis for Aether Tree

Item #45: AFINN-style word-level sentiment with crypto-specific terms,
negation handling, and knowledge node analysis.
"""
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    score: float        # Normalized score in [-1, 1]
    label: str          # "positive", "negative", or "neutral"
    confidence: float   # 0.0–1.0
    raw_score: float = 0.0       # Unnormalized sum
    word_count: int = 0          # Total words analyzed
    sentiment_words: int = 0     # Words that contributed to sentiment


# ---------------------------------------------------------------------------
# Sentiment lexicon (AFINN-style, values from -5 to +5)
# ---------------------------------------------------------------------------

_LEXICON: Dict[str, int] = {
    # Positive general
    "good": 3, "great": 3, "excellent": 4, "amazing": 4, "wonderful": 4,
    "fantastic": 4, "awesome": 4, "brilliant": 4, "outstanding": 5,
    "superb": 4, "perfect": 5, "best": 4, "better": 2, "nice": 2,
    "fine": 1, "love": 3, "like": 2, "enjoy": 2, "happy": 3,
    "glad": 2, "pleased": 2, "excited": 3, "thrilled": 4,
    "impressive": 3, "remarkable": 3, "exceptional": 4,
    "beautiful": 3, "elegant": 3, "innovative": 3, "revolutionary": 4,
    "breakthrough": 4, "success": 3, "successful": 3, "win": 3,
    "winning": 3, "victory": 3, "achieve": 2, "achievement": 3,
    "progress": 2, "improve": 2, "improved": 2, "improvement": 2,
    "upgrade": 2, "enhanced": 2, "strong": 2, "powerful": 2,
    "efficient": 2, "effective": 2, "reliable": 2, "stable": 2,
    "secure": 2, "safe": 2, "trust": 2, "trusted": 2, "confident": 2,
    "optimistic": 3, "promising": 3, "opportunity": 2, "potential": 2,
    "growth": 2, "growing": 2, "gain": 2, "profit": 2, "profitable": 3,
    "valuable": 2, "worth": 2, "reward": 2, "rewarding": 3,
    "fast": 2, "quick": 1, "easy": 1, "simple": 1, "clean": 1,
    "smooth": 1, "solid": 2, "robust": 2, "healthy": 2,
    "right": 1, "correct": 1, "true": 1, "fair": 2, "free": 1,
    "support": 1, "supported": 1, "helpful": 2, "useful": 2,
    "interesting": 2, "cool": 2, "fun": 2, "exciting": 3,
    "positive": 2, "approved": 2, "confirmed": 2, "verified": 2,
    "launched": 2, "live": 2, "working": 1, "running": 1,

    # Negative general
    "bad": -3, "terrible": -4, "horrible": -4, "awful": -4, "worst": -5,
    "worse": -3, "poor": -2, "weak": -2, "fail": -3, "failed": -3,
    "failure": -3, "error": -2, "bug": -2, "broken": -3, "crash": -4,
    "crashed": -4, "down": -2, "slow": -2, "lag": -2, "laggy": -2,
    "stuck": -2, "frozen": -2, "dead": -3, "lost": -3, "lose": -3,
    "losing": -3, "loss": -3, "damage": -3, "damaged": -3,
    "risk": -2, "risky": -2, "danger": -3, "dangerous": -3,
    "threat": -3, "vulnerable": -3, "vulnerability": -3, "exploit": -4,
    "hack": -4, "hacked": -4, "scam": -5, "fraud": -5, "fake": -4,
    "spam": -3, "malicious": -4, "attack": -3, "attacked": -3,
    "fear": -2, "scared": -2, "worried": -2, "concerned": -1,
    "angry": -3, "furious": -4, "frustrated": -3, "annoyed": -2,
    "disappointed": -3, "sad": -2, "depressed": -3, "hate": -4,
    "ugly": -3, "mess": -2, "messy": -2, "confusing": -2,
    "complicated": -1, "difficult": -1, "hard": -1, "impossible": -3,
    "useless": -3, "worthless": -4, "waste": -3, "wasted": -3,
    "expensive": -1, "overpriced": -2, "decline": -2, "declining": -2,
    "drop": -2, "dropped": -2, "falling": -2, "plunge": -3, "plunged": -3,
    "reject": -2, "rejected": -2, "deny": -2, "denied": -2,
    "problem": -2, "issue": -1, "trouble": -2, "wrong": -2,
    "negative": -2, "suspicious": -2, "doubt": -2, "uncertain": -1,
    "unstable": -2, "insecure": -3, "abandoned": -3, "dead": -3,

    # Crypto-specific positive
    "bullish": 3, "moon": 3, "mooning": 4, "pump": 2, "pumping": 2,
    "rally": 3, "breakout": 3, "ath": 3, "adoption": 3,
    "decentralized": 2, "defi": 2, "hodl": 2, "diamond": 2,
    "accumulate": 2, "accumulating": 2, "undervalued": 2,
    "mainnet": 2, "upgrade": 2, "partnership": 3, "listing": 3,
    "listed": 3, "airdrop": 2, "staking": 1, "yield": 2,
    "liquidity": 1, "volume": 1, "whitepaper": 1, "audit": 1,
    "audited": 2, "verified": 2, "transparent": 2, "governance": 1,
    "consensus": 1, "quantum": 2, "aether": 2, "consciousness": 2,
    "phi": 1, "golden": 1, "genesis": 1, "milestone": 2,

    # Crypto-specific negative
    "bearish": -3, "dump": -3, "dumping": -4, "rug": -5, "rugpull": -5,
    "ponzi": -5, "bubble": -3, "fud": -3, "rekt": -4,
    "liquidated": -4, "liquidation": -3, "capitulation": -4,
    "correction": -2, "dip": -1, "bleeding": -3, "panic": -3,
    "sell": -1, "selling": -1, "selloff": -3, "whale": -1,
    "overvalued": -2, "centralized": -2, "censored": -3,
    "delisted": -3, "banned": -3, "illegal": -4, "regulation": -1,
    "shutdown": -3, "offline": -2, "forked": -1, "fork": -1,
    "reorg": -3, "orphan": -2, "double": -1, "doublespend": -5,
}

# Negation words that flip the next sentiment word
_NEGATORS = frozenset({
    "not", "no", "never", "neither", "nobody", "nothing", "nowhere",
    "nor", "without", "hardly", "barely", "scarcely",
    "don't", "dont", "doesn't", "doesnt", "didn't", "didnt",
    "won't", "wont", "wouldn't", "wouldnt", "can't", "cant",
    "cannot", "couldn't", "couldnt", "shouldn't", "shouldnt",
    "isn't", "isnt", "aren't", "arent", "wasn't", "wasnt",
    "weren't", "werent", "haven't", "havent", "hasn't", "hasnt",
    "hadn't", "hadnt",
})

# Intensifiers that amplify the next sentiment word
_INTENSIFIERS: Dict[str, float] = {
    "very": 1.5, "really": 1.5, "extremely": 2.0, "incredibly": 2.0,
    "absolutely": 2.0, "totally": 1.5, "completely": 1.5,
    "highly": 1.5, "super": 1.5, "so": 1.3, "quite": 1.2,
    "fairly": 0.8, "somewhat": 0.7, "slightly": 0.5, "barely": 0.3,
}

_TOKEN_RE = re.compile(r"[a-z0-9']+")


class SentimentAnalyzer:
    """Lexicon-based sentiment analyzer with negation and intensifier handling."""

    def __init__(self) -> None:
        self._calls: int = 0
        self._total_time: float = 0.0
        self._label_counts: Dict[str, int] = {
            "positive": 0, "negative": 0, "neutral": 0,
        }

    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of a text string.

        Args:
            text: Input text.

        Returns:
            SentimentResult with score, label, and confidence.
        """
        t0 = time.time()
        self._calls += 1

        tokens = _TOKEN_RE.findall(text.lower())
        word_count = len(tokens)

        if word_count == 0:
            self._total_time += time.time() - t0
            return SentimentResult(
                score=0.0, label="neutral", confidence=0.5,
                raw_score=0.0, word_count=0, sentiment_words=0,
            )

        raw_score = 0.0
        sentiment_words = 0
        negate = False
        intensifier = 1.0

        for token in tokens:
            # Check if this is a negator
            if token in _NEGATORS:
                negate = True
                continue

            # Check if this is an intensifier
            if token in _INTENSIFIERS:
                intensifier = _INTENSIFIERS[token]
                continue

            # Check lexicon
            if token in _LEXICON:
                val = float(_LEXICON[token])
                val *= intensifier

                if negate:
                    val = -val * 0.75  # Negation flips but dampens slightly
                    negate = False

                raw_score += val
                sentiment_words += 1

            # Reset modifiers after a non-modifier word
            intensifier = 1.0
            if token not in _NEGATORS:
                negate = False

        # Normalize score to [-1, 1] using tanh-like scaling
        # Scale factor: sentiment score per word tends to be small
        max_possible = sentiment_words * 5.0 if sentiment_words > 0 else 1.0
        normalized = raw_score / max_possible if max_possible > 0 else 0.0
        # Clamp to [-1, 1]
        normalized = max(-1.0, min(1.0, normalized))

        # Label
        if normalized > 0.05:
            label = "positive"
        elif normalized < -0.05:
            label = "negative"
        else:
            label = "neutral"

        # Confidence: higher when more sentiment words found relative to total
        if word_count > 0 and sentiment_words > 0:
            coverage = sentiment_words / word_count
            magnitude = abs(normalized)
            confidence = min(1.0, 0.3 + coverage * 0.4 + magnitude * 0.3)
        else:
            confidence = 0.3  # Low confidence when no sentiment words

        self._label_counts[label] += 1
        self._total_time += time.time() - t0

        return SentimentResult(
            score=round(normalized, 4),
            label=label,
            confidence=round(confidence, 4),
            raw_score=round(raw_score, 4),
            word_count=word_count,
            sentiment_words=sentiment_words,
        )

    def analyze_knowledge_node(self, node_content: dict) -> SentimentResult:
        """Analyze sentiment of a knowledge graph node.

        Args:
            node_content: The node's content dict.

        Returns:
            SentimentResult for the node's textual content.
        """
        # Build text from node content fields
        parts: List[str] = []

        if isinstance(node_content, dict):
            for key in ("description", "text", "content", "summary",
                        "explanation", "type", "domain", "topic"):
                val = node_content.get(key)
                if val and isinstance(val, str):
                    parts.append(val)

            # Also check nested content
            nested = node_content.get("data") or node_content.get("observation")
            if isinstance(nested, dict):
                for val in nested.values():
                    if isinstance(val, str):
                        parts.append(val)
        elif isinstance(node_content, str):
            parts.append(node_content)

        text = " ".join(parts) if parts else ""
        return self.analyze(text)

    def get_stats(self) -> dict:
        """Return analyzer statistics."""
        return {
            "calls": self._calls,
            "total_time_s": round(self._total_time, 4),
            "label_counts": dict(self._label_counts),
            "avg_time_per_call_ms": (
                round(self._total_time / self._calls * 1000, 2)
                if self._calls else 0.0
            ),
            "lexicon_size": len(_LEXICON),
        }
