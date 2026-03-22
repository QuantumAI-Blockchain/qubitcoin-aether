"""
Dialogue State Tracking (#52)

Track conversation state across turns for multi-turn chat:
- Entity tracking and slot filling
- Topic stack with shift detection
- Ambiguity detection and clarification suggestions
- Grounding context summarization
"""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DialogueState:
    """Current state of a dialogue across turns."""
    entities: Dict[str, Any] = field(default_factory=dict)
    intents: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    turn_count: int = 0
    context_slots: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'entities': dict(self.entities),
            'intents': list(self.intents),
            'topics': list(self.topics),
            'turn_count': self.turn_count,
            'context_slots': dict(self.context_slots),
        }


class DialogueTracker:
    """Track conversation state across turns for the Aether Tree chat."""

    # Maximum items to retain per collection
    MAX_ENTITIES: int = 100
    MAX_INTENTS: int = 50
    MAX_TOPICS: int = 30
    MAX_SLOTS: int = 50

    def __init__(self) -> None:
        self._state = DialogueState()
        self._topic_stack: List[str] = []
        self._max_topic_stack: int = 20
        self._entity_history: List[Dict[str, Any]] = []
        self._max_entity_history: int = 200

        # Stats
        self._updates: int = 0
        self._clarifications_suggested: int = 0
        self._topic_shifts: int = 0
        self._last_update: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> DialogueState:
        """Current dialogue state (read-only view)."""
        return self._state

    def update(self, user_message: str, system_response: str,
               entities: Optional[Dict[str, Any]] = None,
               intent: str = '') -> DialogueState:
        """Update dialogue state after a turn.

        Args:
            user_message: The user's message text.
            system_response: The system's response text.
            entities: Extracted entities dict (key=type, value=entity value).
            intent: Detected intent string.

        Returns:
            Updated DialogueState.
        """
        self._updates += 1
        self._last_update = time.time()
        self._state.turn_count += 1

        # Update entities
        if entities:
            for key, value in entities.items():
                self._state.entities[key] = value
                self._entity_history.append({
                    'turn': self._state.turn_count,
                    'key': key,
                    'value': value,
                })
            # Bound entities
            if len(self._state.entities) > self.MAX_ENTITIES:
                keys = list(self._state.entities.keys())
                for k in keys[:len(keys) - self.MAX_ENTITIES]:
                    del self._state.entities[k]
            # Bound entity history
            if len(self._entity_history) > self._max_entity_history:
                self._entity_history = self._entity_history[-self._max_entity_history:]

        # Update intents
        if intent:
            self._state.intents.append(intent)
            if len(self._state.intents) > self.MAX_INTENTS:
                self._state.intents = self._state.intents[-self.MAX_INTENTS:]

        # Topic tracking
        topic = self._infer_topic(user_message, intent)
        if topic:
            old_topic = self._topic_stack[-1] if self._topic_stack else ''
            if topic != old_topic:
                self._topic_shifts += 1
            self._topic_stack.append(topic)
            if len(self._topic_stack) > self._max_topic_stack:
                self._topic_stack = self._topic_stack[-self._max_topic_stack:]
            self._state.topics = list(self._topic_stack)

        # Slot filling from user message
        self._fill_slots(user_message, entities or {})

        return self._state

    def should_clarify(self) -> Optional[str]:
        """Detect ambiguity in the current state and suggest clarification.

        Returns:
            Clarification question string, or None if no ambiguity detected.
        """
        # Check for dangling pronoun references without antecedent
        if self._state.turn_count > 1 and not self._state.entities:
            self._clarifications_suggested += 1
            return "Could you clarify what you're referring to? I don't have enough context yet."

        # Check for conflicting slot values
        recent_intents = self._state.intents[-3:] if self._state.intents else []
        if len(set(recent_intents)) >= 3 and self._state.turn_count < 5:
            self._clarifications_suggested += 1
            return "You've asked about several different topics. Which one would you like to focus on?"

        # Check for empty slots that should be filled
        expected_slots = self._get_expected_slots()
        missing = [s for s in expected_slots if s not in self._state.context_slots]
        if missing and self._state.turn_count > 2:
            slot_name = missing[0].replace('_', ' ')
            self._clarifications_suggested += 1
            return f"To give you a better answer, could you tell me the {slot_name}?"

        return None

    def get_grounding_context(self) -> str:
        """Summarize what has been established in the conversation.

        Returns:
            Human-readable summary of grounded context.
        """
        parts: List[str] = []

        if self._state.entities:
            entity_strs = [
                f"{k}: {v}" for k, v in list(self._state.entities.items())[-5:]
            ]
            parts.append("Known entities: " + ", ".join(entity_strs))

        if self._topic_stack:
            current = self._topic_stack[-1]
            parts.append(f"Current topic: {current}")
            if len(self._topic_stack) > 1:
                prev = self._topic_stack[-2]
                if prev != current:
                    parts.append(f"Previous topic: {prev}")

        if self._state.context_slots:
            slot_strs = [
                f"{k}={v}" for k, v in list(self._state.context_slots.items())[-5:]
            ]
            parts.append("Context: " + ", ".join(slot_strs))

        parts.append(f"Turn {self._state.turn_count}")

        return ". ".join(parts) if parts else "No established context yet."

    def reset(self) -> None:
        """Start a new conversation — clear all state."""
        self._state = DialogueState()
        self._topic_stack = []
        self._entity_history = []

    def get_stats(self) -> dict:
        """Return runtime statistics."""
        return {
            'updates': self._updates,
            'turn_count': self._state.turn_count,
            'entities_tracked': len(self._state.entities),
            'topics_tracked': len(self._topic_stack),
            'slots_filled': len(self._state.context_slots),
            'clarifications_suggested': self._clarifications_suggested,
            'topic_shifts': self._topic_shifts,
            'last_update': self._last_update,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _infer_topic(self, message: str, intent: str) -> str:
        """Infer conversation topic from message and intent."""
        msg_lower = message.lower()

        # Topic keywords ordered by specificity
        topic_map = {
            'consciousness': ['consciousness', 'phi', 'iit', 'awareness', 'sentient'],
            'mining': ['mining', 'miner', 'hashrate', 'difficulty', 'vqe', 'block reward'],
            'quantum': ['quantum', 'qubit', 'hamiltonian', 'entangle', 'superposition'],
            'economics': ['economics', 'supply', 'halving', 'emission', 'reward', 'price'],
            'smart_contracts': ['contract', 'deploy', 'solidity', 'opcode', 'qvm', 'bytecode'],
            'security': ['security', 'dilithium', 'cryptography', 'post-quantum', 'signature'],
            'network': ['peer', 'node', 'p2p', 'gossip', 'network', 'sync'],
            'bridge': ['bridge', 'cross-chain', 'wormhole', 'wrap'],
            'privacy': ['privacy', 'confidential', 'stealth', 'susy swap'],
            'aether': ['aether', 'knowledge graph', 'reasoning', 'sephirot'],
            'wallet': ['wallet', 'balance', 'address', 'metamask', 'send', 'transfer'],
        }

        for topic, keywords in topic_map.items():
            if any(kw in msg_lower for kw in keywords):
                return topic

        # Fall back to intent as topic
        if intent and intent not in ('greeting', 'empty', 'math',
                                      'remember_cmd', 'recall_cmd', 'forget_cmd'):
            return intent

        return 'general'

    def _fill_slots(self, message: str, entities: Dict[str, Any]) -> None:
        """Fill context slots from message text and entities."""
        # Direct entity slots
        for key, value in entities.items():
            self._state.context_slots[key] = value

        msg_lower = message.lower()

        # Block height slot
        height_match = re.search(r'block\s+#?(\d+)', msg_lower)
        if height_match:
            self._state.context_slots['block_height'] = int(height_match.group(1))

        # Address slot
        addr_match = re.search(r'(0x[0-9a-fA-F]{40}|qbc1[0-9a-z]{38,62})', message)
        if addr_match:
            self._state.context_slots['address'] = addr_match.group(1)

        # Time range slot
        time_patterns = {
            'last_hour': r'last\s+hour',
            'last_day': r'last\s+(?:day|24\s*h)',
            'last_week': r'last\s+week',
            'today': r'\btoday\b',
        }
        for label, pattern in time_patterns.items():
            if re.search(pattern, msg_lower):
                self._state.context_slots['time_range'] = label
                break

        # Bound slots
        if len(self._state.context_slots) > self.MAX_SLOTS:
            keys = list(self._state.context_slots.keys())
            for k in keys[:len(keys) - self.MAX_SLOTS]:
                del self._state.context_slots[k]

    def _get_expected_slots(self) -> List[str]:
        """Determine which slots should be filled based on current topic."""
        topic = self._topic_stack[-1] if self._topic_stack else ''
        expected: List[str] = []

        if topic == 'mining':
            expected = ['block_height']
        elif topic == 'wallet':
            expected = ['address']
        elif topic == 'smart_contracts':
            expected = ['address']
        elif topic == 'bridge':
            expected = ['source_chain', 'target_chain']

        return expected
