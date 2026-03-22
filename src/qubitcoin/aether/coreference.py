"""
Coreference Resolution for Multi-Turn Chat (#54)

Resolve pronouns and references in multi-turn Aether Tree conversations:
- Pronoun resolution (it, this, that, they, them, etc.)
- Domain-specific references (the contract, the block, the transaction)
- Most-recent-entity-of-matching-type resolution strategy
- Mention tracking across turns
"""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Mention:
    """A mention of an entity in text."""
    text: str          # The surface form (e.g., "it", "the block")
    entity_id: str     # Resolved entity ID or key
    position: int      # Character position in text
    type: str          # Entity type (block, transaction, address, contract, etc.)

    def to_dict(self) -> dict:
        return {
            'text': self.text,
            'entity_id': self.entity_id,
            'position': self.position,
            'type': self.type,
        }


# Pronoun → expected entity types mapping
_PRONOUN_TYPES: Dict[str, List[str]] = {
    'it': ['block', 'transaction', 'contract', 'address', 'metric', 'token', 'concept'],
    'its': ['block', 'transaction', 'contract', 'address', 'metric', 'token', 'concept'],
    'this': ['block', 'transaction', 'contract', 'address', 'metric', 'topic', 'concept'],
    'that': ['block', 'transaction', 'contract', 'address', 'metric', 'topic', 'concept'],
    'they': ['address', 'node', 'peer', 'validator', 'agent'],
    'them': ['address', 'node', 'peer', 'validator', 'agent'],
    'their': ['address', 'node', 'peer', 'validator', 'agent'],
    'these': ['block', 'transaction', 'contract', 'node'],
    'those': ['block', 'transaction', 'contract', 'node'],
}

# Domain-specific references → expected entity types
_REFERENCE_PATTERNS: List[Tuple[str, str]] = [
    (r'\bthe\s+block\b', 'block'),
    (r'\bthe\s+transaction\b', 'transaction'),
    (r'\bthe\s+tx\b', 'transaction'),
    (r'\bthe\s+contract\b', 'contract'),
    (r'\bthe\s+address\b', 'address'),
    (r'\bthe\s+wallet\b', 'address'),
    (r'\bthe\s+miner\b', 'address'),
    (r'\bthe\s+node\b', 'node'),
    (r'\bthe\s+peer\b', 'peer'),
    (r'\bthe\s+token\b', 'token'),
    (r'\bthe\s+bridge\b', 'bridge'),
    (r'\bthe\s+chain\b', 'chain'),
    (r'\bthe\s+network\b', 'network'),
    (r'\bthe\s+reward\b', 'metric'),
    (r'\bthe\s+difficulty\b', 'metric'),
    (r'\bthe\s+phi\b', 'metric'),
    (r'\bthe\s+same\s+(\w+)\b', 'same_ref'),  # "the same block"
]


class CoreferenceResolver:
    """Resolve pronouns and references in multi-turn chat."""

    def __init__(self) -> None:
        self._entity_register: List[Dict[str, Any]] = []
        self._max_register: int = 200

        # Stats
        self._resolves: int = 0
        self._mentions_tracked: int = 0
        self._successful_resolutions: int = 0
        self._last_resolve: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, text: str, context: List[Dict[str, Any]]) -> str:
        """Resolve pronouns and references in text using context.

        Args:
            text: The user's message text.
            context: List of dicts with entity info from previous turns.
                     Each dict should have: 'id' (str), 'type' (str),
                     'text' (str, display name), 'turn' (int, optional).

        Returns:
            Text with pronouns replaced by their referents (in brackets).
        """
        self._resolves += 1
        self._last_resolve = time.time()

        # Update entity register with new context
        for entity in context:
            self._register_entity(entity)

        if not self._entity_register:
            return text

        resolved = text
        replacements: List[Tuple[int, int, str]] = []

        # Resolve pronouns
        for pronoun, expected_types in _PRONOUN_TYPES.items():
            pattern = re.compile(
                r'\b' + re.escape(pronoun) + r'\b',
                re.IGNORECASE,
            )
            for match in pattern.finditer(text):
                referent = self._find_referent(expected_types)
                if referent:
                    self._successful_resolutions += 1
                    replacement = f"[{referent['text']}]"
                    replacements.append((match.start(), match.end(), replacement))

        # Resolve domain-specific references ("the block", "the contract")
        for pattern_str, entity_type in _REFERENCE_PATTERNS:
            if entity_type == 'same_ref':
                continue  # Handle separately
            pattern = re.compile(pattern_str, re.IGNORECASE)
            for match in pattern.finditer(text):
                referent = self._find_referent([entity_type])
                if referent:
                    self._successful_resolutions += 1
                    replacement = f"[{referent['text']}]"
                    replacements.append((match.start(), match.end(), replacement))

        # Resolve "the same X" references
        same_pattern = re.compile(r'\bthe\s+same\s+(\w+)\b', re.IGNORECASE)
        for match in same_pattern.finditer(text):
            ref_type = self._type_from_word(match.group(1))
            if ref_type:
                referent = self._find_referent([ref_type])
                if referent:
                    self._successful_resolutions += 1
                    replacement = f"[{referent['text']}]"
                    replacements.append((match.start(), match.end(), replacement))

        # Apply replacements in reverse order to preserve positions
        if replacements:
            # Remove overlapping replacements (keep first match)
            replacements.sort(key=lambda r: r[0])
            non_overlapping: List[Tuple[int, int, str]] = []
            last_end = -1
            for start, end, repl in replacements:
                if start >= last_end:
                    non_overlapping.append((start, end, repl))
                    last_end = end

            # Apply in reverse
            for start, end, repl in reversed(non_overlapping):
                resolved = resolved[:start] + repl + resolved[end:]

        return resolved

    def track_mentions(self, text: str,
                       entities: List[Dict[str, Any]]) -> List[Mention]:
        """Track entity mentions in text.

        Args:
            text: Text to scan for mentions.
            entities: Known entities with 'id', 'type', 'text' fields.

        Returns:
            List of Mention objects found in text.
        """
        mentions: List[Mention] = []
        text_lower = text.lower()

        for entity in entities:
            entity_text = str(entity.get('text', '')).lower()
            entity_id = str(entity.get('id', ''))
            entity_type = str(entity.get('type', 'unknown'))

            if not entity_text or len(entity_text) < 2:
                continue

            # Find all occurrences
            start = 0
            while True:
                idx = text_lower.find(entity_text, start)
                if idx == -1:
                    break
                mentions.append(Mention(
                    text=text[idx:idx + len(entity_text)],
                    entity_id=entity_id,
                    position=idx,
                    type=entity_type,
                ))
                start = idx + 1

            # Register for future coreference resolution
            self._register_entity(entity)

        self._mentions_tracked += len(mentions)
        return mentions

    def register_entities_from_turn(self, entities: Dict[str, Any],
                                     turn: int = 0) -> None:
        """Register entities from a processed turn for future resolution.

        Args:
            entities: Dict of entity_type -> entity_value from extraction.
            turn: Turn number for recency tracking.
        """
        for etype, evalue in entities.items():
            if isinstance(evalue, list):
                for item in evalue:
                    self._register_entity({
                        'id': str(item),
                        'type': etype,
                        'text': str(item),
                        'turn': turn,
                    })
            elif isinstance(evalue, dict):
                for k, v in evalue.items():
                    self._register_entity({
                        'id': str(v),
                        'type': etype,
                        'text': str(v),
                        'turn': turn,
                    })
            else:
                self._register_entity({
                    'id': str(evalue),
                    'type': etype,
                    'text': str(evalue),
                    'turn': turn,
                })

    def reset(self) -> None:
        """Clear the entity register for a new conversation."""
        self._entity_register = []

    def get_stats(self) -> dict:
        """Return runtime statistics."""
        return {
            'resolves': self._resolves,
            'mentions_tracked': self._mentions_tracked,
            'successful_resolutions': self._successful_resolutions,
            'entities_registered': len(self._entity_register),
            'last_resolve': self._last_resolve,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_entity(self, entity: Dict[str, Any]) -> None:
        """Add an entity to the register (most recent first)."""
        if not entity.get('id') or not entity.get('type'):
            return

        # Check for duplicates — update turn if same entity
        for existing in self._entity_register:
            if existing['id'] == entity['id'] and existing['type'] == entity['type']:
                existing['turn'] = entity.get('turn', existing.get('turn', 0))
                return

        self._entity_register.append(entity)

        # Bound register size
        if len(self._entity_register) > self._max_register:
            self._entity_register = self._entity_register[-self._max_register:]

    def _find_referent(self, expected_types: List[str]) -> Optional[Dict[str, Any]]:
        """Find the most recent entity matching any of the expected types.

        Strategy: most recent entity of matching type (last in register).
        """
        for entity in reversed(self._entity_register):
            if entity.get('type') in expected_types:
                return entity
        # Fallback: return most recent entity regardless of type
        if self._entity_register:
            return self._entity_register[-1]
        return None

    @staticmethod
    def _type_from_word(word: str) -> Optional[str]:
        """Map a natural language word to an entity type."""
        word_lower = word.lower()
        word_to_type = {
            'block': 'block',
            'transaction': 'transaction',
            'tx': 'transaction',
            'contract': 'contract',
            'address': 'address',
            'wallet': 'address',
            'miner': 'address',
            'node': 'node',
            'peer': 'peer',
            'token': 'token',
            'bridge': 'bridge',
            'chain': 'chain',
            'network': 'network',
            'reward': 'metric',
            'difficulty': 'metric',
            'one': None,  # "the same one" — too ambiguous
        }
        return word_to_type.get(word_lower)
