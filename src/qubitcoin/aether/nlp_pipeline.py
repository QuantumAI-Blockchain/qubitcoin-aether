"""
NLP Pipeline — Lightweight Natural Language Processing for Aether Tree

Item #41: Tokenizer, POS tagger, NER, dependency parsing.
All rule-based / regex — no external NLP libraries required.
"""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NLPEntity:
    """A named entity extracted from text."""
    text: str
    label: str          # Address, Amount, BlockRef, TxRef, ContractRef, CryptoTerm, etc.
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class Dependency:
    """A single dependency arc."""
    token_index: int
    head_index: int     # -1 = root
    relation: str       # nsubj, dobj, root, amod, prep, det, etc.


@dataclass
class NLPResult:
    """Full result of NLP pipeline processing."""
    raw_text: str
    tokens: List[str]
    pos_tags: List[str]
    entities: List[NLPEntity]
    deps: List[Dependency]


# ---------------------------------------------------------------------------
# Suffix → POS heuristics
# ---------------------------------------------------------------------------

_SUFFIX_POS: List[Tuple[str, str]] = [
    ("ing", "VBG"),
    ("tion", "NN"),
    ("sion", "NN"),
    ("ment", "NN"),
    ("ness", "NN"),
    ("ity", "NN"),
    ("ance", "NN"),
    ("ence", "NN"),
    ("ism", "NN"),
    ("ist", "NN"),
    ("ous", "JJ"),
    ("ive", "JJ"),
    ("ful", "JJ"),
    ("less", "JJ"),
    ("able", "JJ"),
    ("ible", "JJ"),
    ("al", "JJ"),
    ("ial", "JJ"),
    ("ed", "VBD"),
    ("ly", "RB"),
    ("er", "NN"),
    ("est", "JJS"),
    ("es", "NNS"),
    ("s", "NNS"),
]

_DETERMINERS = {"a", "an", "the", "this", "that", "these", "those", "my", "your",
                "his", "her", "its", "our", "their", "some", "any", "no", "every"}
_PREPOSITIONS = {"in", "on", "at", "to", "for", "with", "from", "by", "of",
                 "about", "into", "through", "during", "before", "after",
                 "above", "below", "between", "under", "over", "across"}
_CONJUNCTIONS = {"and", "or", "but", "nor", "yet", "so", "because", "although",
                 "while", "if", "when", "unless", "since", "until"}
_PRONOUNS = {"i", "me", "you", "he", "she", "it", "we", "they", "him", "her",
             "us", "them", "who", "what", "which", "whom", "whose", "myself"}
_AUX_VERBS = {"is", "am", "are", "was", "were", "be", "been", "being",
              "have", "has", "had", "do", "does", "did", "will", "would",
              "shall", "should", "may", "might", "can", "could", "must"}
_COMMON_VERBS = {"get", "got", "make", "go", "went", "gone", "take", "took",
                 "come", "came", "see", "saw", "know", "knew", "think",
                 "thought", "say", "said", "give", "gave", "find", "found",
                 "tell", "told", "ask", "asked", "use", "used", "work",
                 "worked", "call", "called", "try", "tried", "need",
                 "needed", "run", "ran", "mine", "mined", "send", "sent",
                 "create", "created", "deploy", "deployed", "stake", "staked",
                 "transfer", "transferred", "bridge", "bridged"}
_WH_WORDS = {"what", "who", "where", "when", "why", "how", "which", "whom"}

# NER dictionaries
_CRYPTO_TERMS = {
    "bitcoin", "btc", "ethereum", "eth", "qubitcoin", "qbc", "qusd",
    "dilithium", "quantum", "mining", "consensus", "staking", "defi",
    "nft", "token", "blockchain", "block", "hash", "utxo", "wallet",
    "bridge", "swap", "liquidity", "gas", "aether", "sephirot", "phi",
    "susy", "vqe", "hamiltonian", "entanglement", "qvm", "solidity",
    "contract", "governance", "dao", "yield", "miner", "validator",
    "merkle", "genesis", "mainnet", "testnet", "mempool", "difficulty",
    "reward", "halving", "emission", "supply", "address", "signature",
    "keypair", "node", "peer", "gossip", "p2p", "rpc", "api",
}

# Regex patterns for NER
_ADDR_HEX = re.compile(r'\b0x[0-9a-fA-F]{40}\b')
_ADDR_QBC = re.compile(r'\bqbc1[0-9a-z]{38,62}\b')
_TX_HASH = re.compile(r'\b0x[0-9a-fA-F]{64}\b')
_BLOCK_REF = re.compile(r'\bblock\s*#?\s*(\d+)\b', re.IGNORECASE)
_AMOUNT_QBC = re.compile(r'\b(\d+(?:\.\d+)?)\s*(?:QBC|qbc|QUSD|qusd)\b')
_AMOUNT_NUM = re.compile(r'\b(\d+(?:\.\d+)?)\s*(?:tokens?|coins?)\b', re.IGNORECASE)
_CONTRACT_NAME = re.compile(
    r'\b(QBC-?20|QBC-?721|ERC-?20|ERC-?721|QUSD|AetherTree|HiggsField|SUSYToken)\b',
    re.IGNORECASE,
)
_TIMESTAMP_ISO = re.compile(r'\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2})?Z?\b')

# Tokenizer regex: split on whitespace and punctuation
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+(?:'[A-Za-z]+)?|[^\s]")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class NLPPipeline:
    """Lightweight NLP pipeline: tokenize → POS tag → NER → dependency parse."""

    def __init__(self) -> None:
        self._calls: int = 0
        self._total_tokens: int = 0
        self._total_entities: int = 0
        self._total_time: float = 0.0

    # ----- tokenizer --------------------------------------------------------

    def tokenize(self, text: str) -> List[str]:
        """Whitespace + punctuation splitting with lowercasing and normalization."""
        # Normalize unicode dashes, quotes
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2014", " -- ").replace("\u2013", " - ")
        tokens = _TOKEN_RE.findall(text)
        return tokens

    # ----- POS tagger -------------------------------------------------------

    def pos_tag(self, tokens: List[str]) -> List[str]:
        """Rule-based POS tagging using suffix heuristics and word lists."""
        tags: List[str] = []
        for token in tokens:
            lower = token.lower()

            # Punctuation
            if len(token) == 1 and not token.isalnum():
                if token in ".!?":
                    tags.append(".")
                elif token in ",;:":
                    tags.append(",")
                else:
                    tags.append("SYM")
                continue

            # Numbers
            if token.replace(".", "", 1).replace(",", "").isdigit():
                tags.append("CD")
                continue

            # Hex addresses / hashes
            if lower.startswith("0x"):
                tags.append("NNP")
                continue

            # Closed-class words
            if lower in _DETERMINERS:
                tags.append("DT")
            elif lower in _PREPOSITIONS:
                tags.append("IN")
            elif lower in _CONJUNCTIONS:
                tags.append("CC")
            elif lower in _PRONOUNS:
                tags.append("PRP")
            elif lower in _WH_WORDS:
                tags.append("WP")
            elif lower in _AUX_VERBS:
                tags.append("VB")
            elif lower in _COMMON_VERBS:
                tags.append("VB")
            elif lower in _CRYPTO_TERMS:
                tags.append("NN")
            elif token[0].isupper() and len(token) > 1:
                tags.append("NNP")  # Proper noun
            else:
                # Suffix-based
                assigned = False
                for suffix, pos in _SUFFIX_POS:
                    if lower.endswith(suffix) and len(lower) > len(suffix) + 1:
                        tags.append(pos)
                        assigned = True
                        break
                if not assigned:
                    tags.append("NN")  # Default to noun

        return tags

    # ----- NER --------------------------------------------------------------

    def extract_entities(self, text: str, tokens: List[str]) -> List[NLPEntity]:
        """Regex + dictionary-based Named Entity Recognition."""
        entities: List[NLPEntity] = []

        # Hex addresses (20 bytes)
        for m in _ADDR_HEX.finditer(text):
            # Distinguish 32-byte tx hash from 20-byte address
            if len(m.group()) == 66:
                entities.append(NLPEntity(
                    text=m.group(), label="TxRef",
                    start=m.start(), end=m.end(), confidence=0.95,
                ))
            else:
                entities.append(NLPEntity(
                    text=m.group(), label="Address",
                    start=m.start(), end=m.end(), confidence=0.95,
                ))

        # QBC addresses
        for m in _ADDR_QBC.finditer(text):
            entities.append(NLPEntity(
                text=m.group(), label="Address",
                start=m.start(), end=m.end(), confidence=0.95,
            ))

        # TX hashes (64 hex chars)
        for m in _TX_HASH.finditer(text):
            # Only if not already matched as address
            if not any(e.start == m.start() for e in entities):
                entities.append(NLPEntity(
                    text=m.group(), label="TxRef",
                    start=m.start(), end=m.end(), confidence=0.90,
                ))

        # Block references
        for m in _BLOCK_REF.finditer(text):
            entities.append(NLPEntity(
                text=m.group(), label="BlockRef",
                start=m.start(), end=m.end(), confidence=0.90,
            ))

        # Amounts (QBC/QUSD)
        for m in _AMOUNT_QBC.finditer(text):
            entities.append(NLPEntity(
                text=m.group(), label="Amount",
                start=m.start(), end=m.end(), confidence=0.90,
            ))

        # Amounts (generic tokens/coins)
        for m in _AMOUNT_NUM.finditer(text):
            entities.append(NLPEntity(
                text=m.group(), label="Amount",
                start=m.start(), end=m.end(), confidence=0.75,
            ))

        # Contract names
        for m in _CONTRACT_NAME.finditer(text):
            entities.append(NLPEntity(
                text=m.group(), label="ContractRef",
                start=m.start(), end=m.end(), confidence=0.85,
            ))

        # Timestamps
        for m in _TIMESTAMP_ISO.finditer(text):
            entities.append(NLPEntity(
                text=m.group(), label="Timestamp",
                start=m.start(), end=m.end(), confidence=0.85,
            ))

        # Crypto terms (token-level)
        for i, tok in enumerate(tokens):
            if tok.lower() in _CRYPTO_TERMS:
                entities.append(NLPEntity(
                    text=tok, label="CryptoTerm",
                    start=0, end=0,  # Token-level, not char-level
                    confidence=0.80,
                ))

        # Deduplicate by (start, end, label) — keep highest confidence
        seen: Dict[Tuple[int, int, str], NLPEntity] = {}
        for ent in entities:
            key = (ent.start, ent.end, ent.label)
            if key not in seen or ent.confidence > seen[key].confidence:
                seen[key] = ent
        return sorted(seen.values(), key=lambda e: e.start)

    # ----- Dependency parsing -----------------------------------------------

    def parse_dependencies(self, tokens: List[str], pos_tags: List[str]) -> List[Dependency]:
        """Simple head-finding dependency parse.

        Strategy:
        - Find first verb → mark as ROOT
        - Nouns/pronouns before root → nsubj
        - Nouns after root → dobj
        - Determiners → det (head = next noun)
        - Adjectives → amod (head = next noun)
        - Prepositions → prep (head = root or nearest verb)
        - Everything else → dep (head = root)
        """
        n = len(tokens)
        if n == 0:
            return []

        deps: List[Dependency] = [
            Dependency(token_index=i, head_index=-1, relation="dep")
            for i in range(n)
        ]

        # Find root: first verb
        root_idx = -1
        for i, tag in enumerate(pos_tags):
            if tag.startswith("VB"):
                root_idx = i
                break
        if root_idx == -1:
            # No verb found — use first noun as root
            for i, tag in enumerate(pos_tags):
                if tag.startswith("NN"):
                    root_idx = i
                    break
        if root_idx == -1:
            root_idx = 0

        deps[root_idx] = Dependency(
            token_index=root_idx, head_index=-1, relation="root"
        )

        for i in range(n):
            if i == root_idx:
                continue
            tag = pos_tags[i]

            if tag == "DT":
                # Determiner → head is next noun
                head = self._find_next_pos(pos_tags, i + 1, ("NN", "NNS", "NNP"))
                deps[i] = Dependency(
                    token_index=i,
                    head_index=head if head >= 0 else root_idx,
                    relation="det",
                )
            elif tag in ("JJ", "JJS"):
                # Adjective → head is next noun
                head = self._find_next_pos(pos_tags, i + 1, ("NN", "NNS", "NNP"))
                deps[i] = Dependency(
                    token_index=i,
                    head_index=head if head >= 0 else root_idx,
                    relation="amod",
                )
            elif tag == "RB":
                # Adverb → head is nearest verb
                head = self._find_nearest_pos(pos_tags, i, ("VB", "VBD", "VBG"))
                deps[i] = Dependency(
                    token_index=i,
                    head_index=head if head >= 0 else root_idx,
                    relation="advmod",
                )
            elif tag == "IN":
                deps[i] = Dependency(
                    token_index=i, head_index=root_idx, relation="prep",
                )
            elif tag == "CC":
                deps[i] = Dependency(
                    token_index=i, head_index=root_idx, relation="cc",
                )
            elif tag in ("PRP", "WP"):
                if i < root_idx:
                    deps[i] = Dependency(
                        token_index=i, head_index=root_idx, relation="nsubj",
                    )
                else:
                    deps[i] = Dependency(
                        token_index=i, head_index=root_idx, relation="dobj",
                    )
            elif tag.startswith("NN"):
                if i < root_idx:
                    deps[i] = Dependency(
                        token_index=i, head_index=root_idx, relation="nsubj",
                    )
                else:
                    deps[i] = Dependency(
                        token_index=i, head_index=root_idx, relation="dobj",
                    )
            elif tag == "CD":
                # Number → head is nearest noun
                head = self._find_nearest_pos(pos_tags, i, ("NN", "NNS", "NNP"))
                deps[i] = Dependency(
                    token_index=i,
                    head_index=head if head >= 0 else root_idx,
                    relation="nummod",
                )
            elif tag == ".":
                deps[i] = Dependency(
                    token_index=i, head_index=root_idx, relation="punct",
                )
            else:
                deps[i] = Dependency(
                    token_index=i, head_index=root_idx, relation="dep",
                )

        return deps

    # ----- Main entry point -------------------------------------------------

    def process(self, text: str) -> NLPResult:
        """Run full NLP pipeline: tokenize → POS → NER → deps.

        Args:
            text: Input text to process.

        Returns:
            NLPResult with tokens, pos_tags, entities, deps.
        """
        t0 = time.time()
        tokens = self.tokenize(text)
        pos_tags = self.pos_tag(tokens)
        entities = self.extract_entities(text, tokens)
        deps = self.parse_dependencies(tokens, pos_tags)

        self._calls += 1
        self._total_tokens += len(tokens)
        self._total_entities += len(entities)
        self._total_time += time.time() - t0

        return NLPResult(
            raw_text=text,
            tokens=tokens,
            pos_tags=pos_tags,
            entities=entities,
            deps=deps,
        )

    # ----- helpers ----------------------------------------------------------

    @staticmethod
    def _find_next_pos(tags: List[str], start: int,
                       prefixes: Tuple[str, ...]) -> int:
        """Find the next token whose POS tag starts with one of *prefixes*."""
        for i in range(start, len(tags)):
            for p in prefixes:
                if tags[i].startswith(p):
                    return i
        return -1

    @staticmethod
    def _find_nearest_pos(tags: List[str], origin: int,
                          prefixes: Tuple[str, ...]) -> int:
        """Find the nearest token (before or after) matching *prefixes*."""
        best = -1
        best_dist = len(tags) + 1
        for i, tag in enumerate(tags):
            if i == origin:
                continue
            for p in prefixes:
                if tag.startswith(p):
                    dist = abs(i - origin)
                    if dist < best_dist:
                        best = i
                        best_dist = dist
                    break
        return best

    # ----- stats ------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return pipeline statistics."""
        return {
            "calls": self._calls,
            "total_tokens_processed": self._total_tokens,
            "total_entities_found": self._total_entities,
            "avg_tokens_per_call": (
                self._total_tokens / self._calls if self._calls else 0.0
            ),
            "avg_entities_per_call": (
                self._total_entities / self._calls if self._calls else 0.0
            ),
            "total_time_s": round(self._total_time, 4),
            "avg_time_per_call_ms": (
                round(self._total_time / self._calls * 1000, 2)
                if self._calls else 0.0
            ),
        }
