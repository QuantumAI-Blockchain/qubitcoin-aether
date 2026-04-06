"""
Aether Tree Chat System

Provides a conversational interface for users to interact with the Aether Tree AGI.
Each message is processed through the reasoning engine, linked to the knowledge graph,
and produces a Proof-of-Thought hash.

Fee structure:
  - First N messages per session are free (onboarding).
  - After that, each message costs AETHER_CHAT_FEE_QBC, dynamically pegged to QUSD.
  - Deep queries cost 2x the base fee.
"""
import hashlib
import json
import math
import os
import random
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _default_memory_dir() -> str:
    """Return a secure default directory for chat memory storage.

    Uses a subdirectory under the project data directory (if configured)
    or creates a private temp directory with restrictive permissions (0o700).
    """
    # Prefer explicit config if available
    data_dir = os.environ.get('QUBITCOIN_DATA_DIR', '')
    if data_dir:
        mem_dir = os.path.join(data_dir, 'aether_chat')
        os.makedirs(mem_dir, mode=0o700, exist_ok=True)
        return os.path.join(mem_dir, 'chat_memory.json')

    # Fallback: create a private temp directory
    mem_dir = os.path.join(tempfile.gettempdir(), f'aether_chat_{os.getuid()}')
    os.makedirs(mem_dir, mode=0o700, exist_ok=True)
    return os.path.join(mem_dir, 'chat_memory.json')


class ChatMemory:
    """Persistent per-user key-value memory for Aether Tree chat.

    Stores user preferences, interests, and context across chat sessions.
    Persists to a JSON file so memories survive process restarts.
    """

    MAX_USERS: int = 100000         # Maximum tracked user profiles
    MAX_KEYS_PER_USER: int = 100    # Maximum memory keys per user

    def __init__(self, storage_path: Optional[str] = None) -> None:
        """
        Args:
            storage_path: Path to the JSON file for persistence.
                          Defaults to a secure private directory.
        """
        self._storage_path: str = storage_path or _default_memory_dir()
        self._memories: Dict[str, Dict[str, str]] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Load memories from the JSON persistence file (thread-safe)."""
        with self._lock:
            try:
                path = Path(self._storage_path)
                if path.exists() and path.stat().st_size > 0:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        self._memories = data
                        logger.debug(
                            f"ChatMemory loaded {len(data)} users from {self._storage_path}"
                        )
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"ChatMemory load skipped: {e}")
                self._memories = {}

    def _save(self) -> None:
        """Persist memories to the JSON file (thread-safe)."""
        with self._lock:
            try:
                with open(self._storage_path, "w", encoding="utf-8") as f:
                    json.dump(self._memories, f, indent=2, ensure_ascii=False)
            except OSError as e:
                logger.warning(f"ChatMemory save failed: {e}")

    def remember(self, user_id: str, key: str, value: str) -> None:
        """Store a key-value memory for a user.

        Args:
            user_id: Unique user identifier (e.g., wallet address).
            key: Memory key (e.g., "interest", "preferred_topic").
            value: Memory value (e.g., "DeFi", "quantum computing").
        """
        if user_id not in self._memories:
            if len(self._memories) >= self.MAX_USERS:
                # Evict least-recently-stored user
                oldest = next(iter(self._memories))
                del self._memories[oldest]
            self._memories[user_id] = {}
        if len(self._memories[user_id]) >= self.MAX_KEYS_PER_USER:
            # Evict oldest key
            oldest_key = next(iter(self._memories[user_id]))
            del self._memories[user_id][oldest_key]
        self._memories[user_id][key] = value
        self._save()

    def recall(self, user_id: str, key: str) -> Optional[str]:
        """Recall a specific memory for a user.

        Args:
            user_id: Unique user identifier.
            key: Memory key to look up.

        Returns:
            The stored value, or None if not found.
        """
        return self._memories.get(user_id, {}).get(key)

    def recall_all(self, user_id: str) -> Dict[str, str]:
        """Recall all memories for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            Dict of all key-value memories for this user. Empty dict if none.
        """
        return dict(self._memories.get(user_id, {}))

    def forget(self, user_id: str, key: str) -> None:
        """Remove a specific memory for a user.

        Args:
            user_id: Unique user identifier.
            key: Memory key to remove.
        """
        user_mem = self._memories.get(user_id)
        if user_mem and key in user_mem:
            del user_mem[key]
            if not user_mem:
                del self._memories[user_id]
            self._save()

    def extract_memories(self, message: str, response: str) -> Dict[str, str]:
        """Extract key facts from a conversation exchange.

        Scans the user message for common patterns indicating preferences,
        interests, or personal context that should be remembered.

        Args:
            message: The user's message.
            response: The Aether response (used for topic detection).

        Returns:
            Dict of extracted key-value memories (may be empty).
        """
        extracted: Dict[str, str] = {}
        msg_lower = message.lower().strip()

        # Interest patterns: "I'm interested in X", "I like X", "I want to learn about X"
        interest_patterns = [
            r"i(?:'m| am) interested in (.+?)(?:\.|,|!|$)",
            r"i(?:'m| am) curious about (.+?)(?:\.|,|!|$)",
            r"i like (.+?)(?:\.|,|!|$)",
            r"i want to (?:learn|know) (?:more )?about (.+?)(?:\.|,|!|$)",
            r"i(?:'m| am) (?:really )?into (.+?)(?:\.|,|!|$)",
        ]
        for pattern in interest_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                extracted["interest"] = match.group(1).strip()
                break

        # Role/occupation: "I'm a developer", "I work as a trader"
        role_patterns = [
            r"i(?:'m| am) a(?:n)? (.+?)(?:\.|,|!|$)",
            r"i work as a(?:n)? (.+?)(?:\.|,|!|$)",
            r"my (?:job|role|profession) is (.+?)(?:\.|,|!|$)",
        ]
        for pattern in role_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                role_candidate = match.group(1).strip()
                # Filter out conversational phrases that aren't roles
                non_roles = {"bit", "lot", "fan", "little", "big", "new", "good"}
                if role_candidate and role_candidate.split()[0] not in non_roles:
                    extracted["role"] = role_candidate
                    break

        # "Remember that X" — generic remember command (#22)
        remember_pattern = r"remember (?:that )?(.+?)(?:\.|!|$)"
        match = re.search(remember_pattern, msg_lower)
        if match:
            fact = match.group(1).strip()
            if fact and len(fact) > 2:
                extracted["remembered_fact"] = fact

        # Name: "My name is X", "I'm X" (only if short and capitalized in original)
        name_patterns = [
            r"my name is (\w+)",
            r"call me (\w+)",
            r"i'm (\w+)$",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                name = match.group(1).strip()
                if len(name) >= 2:
                    extracted["name"] = name.capitalize()
                    break

        # Preferred topic: detect from repeated keywords
        topic_keywords = {
            "defi": "DeFi",
            "nft": "NFTs",
            "mining": "mining",
            "quantum": "quantum computing",
            "staking": "staking",
            "governance": "governance",
            "privacy": "privacy",
            "bridge": "cross-chain bridges",
            "smart contract": "smart contracts",
            "economics": "token economics",
            "aether": "Aether Tree AGI",
            "consciousness": "consciousness",
        }
        for keyword, topic in topic_keywords.items():
            if keyword in msg_lower:
                extracted["preferred_topic"] = topic
                break

        # Technical terms: "I use X", "I prefer X", "I work with X"
        tech_patterns = [
            r"i (?:use|prefer|work with|develop with) (\w+(?:\s?\w+)?)",
        ]
        tech_keywords = {
            "dilithium", "crystals", "kyber", "qiskit", "solidity",
            "rust", "python", "go", "typescript", "substrate",
            "metamask", "ethers", "hardhat", "foundry", "remix",
        }
        for pattern in tech_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                term = match.group(1).strip()
                if term.lower() in tech_keywords or len(term) > 3:
                    extracted["tech_preference"] = term
                    break

        # Chain preference: "I prefer mining on X", "I like X chain"
        chain_patterns = [
            r"i (?:prefer|like|use|mine on|stake on) (?:the )?(qbc|qubitcoin|ethereum|eth|polygon|matic|solana|sol|bsc|bnb|avalanche|avax|arbitrum|arb|optimism|op|base)",
        ]
        for pattern in chain_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                extracted["chain_preference"] = match.group(1).strip().upper()
                break

        # Wallet addresses: hex (0x...) or qbc1... addresses
        addr_patterns = [
            r"(?:my (?:address|wallet) is |address[:\s]+)(0x[0-9a-fA-F]{40})",
            r"(?:my (?:address|wallet) is |address[:\s]+)(qbc1[0-9a-z]{38,62})",
        ]
        for pattern in addr_patterns:
            match = re.search(pattern, message)  # Use original case for addresses
            if match:
                extracted["wallet_address"] = match.group(1).strip()
                break

        return extracted


@dataclass
class ChatMessage:
    """A single message in an Aether chat session."""
    role: str  # 'user' or 'aether'
    content: str
    timestamp: float = 0.0
    reasoning_trace: List[dict] = field(default_factory=list)
    phi_at_response: float = 0.0
    knowledge_nodes_referenced: List[int] = field(default_factory=list)
    proof_of_thought_hash: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


MAX_SESSION_MESSAGES: int = 1000
RATE_LIMIT_MESSAGES: int = 30          # Max messages per minute per session
RATE_LIMIT_WINDOW_SECONDS: float = 60.0
SESSION_TTL_SECONDS: float = 7200.0    # 2 hours
CONVERSATION_CONTEXT_WINDOW: int = 10  # Last N messages for context

# Abbreviation map for expanding common QBC abbreviations (#35)
_ABBREVIATIONS: Dict[str, str] = {
    'qbc': 'Qubitcoin',
    'posa': 'Proof-of-SUSY-Alignment',
    'vqe': 'Variational Quantum Eigensolver',
    'qusd': 'QUSD stablecoin',
    'kg': 'knowledge graph',
    'agi': 'Artificial General Intelligence',
    'iit': 'Integrated Information Theory',
    'susy': 'supersymmetry',
    'phi': 'Phi consciousness metric',
    'evm': 'Ethereum Virtual Machine',
    'qvm': 'Quantum Virtual Machine',
    'utxo': 'Unspent Transaction Output',
    'pot': 'Proof-of-Thought',
    'zk': 'zero-knowledge',
}


def _format_number(n: float) -> str:
    """Format a number with commas for human readability (#50).

    Args:
        n: Number to format.

    Returns:
        Human-readable string (e.g., 3,300,000,000).
    """
    if n == int(n):
        return f"{int(n):,}"
    return f"{n:,.2f}"


def _try_math(query: str) -> Optional[str]:
    """Attempt to evaluate basic math expressions in a query (#26).

    Supports +, -, *, / with integer and float operands.

    Args:
        query: The user's message.

    Returns:
        A response string with the answer, or None if no math detected.
    """
    # Match patterns like "what is 2+2", "2 + 2", "calculate 10 * 5"
    math_pattern = r'(?:what\s+is\s+|calculate\s+|compute\s+|solve\s+)?(\d+(?:\.\d+)?)\s*([+\-*/x×])\s*(\d+(?:\.\d+)?)'
    match = re.search(math_pattern, query.lower().strip())
    if not match:
        return None
    a_str, op, b_str = match.group(1), match.group(2), match.group(3)
    try:
        a, b = float(a_str), float(b_str)
    except ValueError:
        return None
    if op in ('x', '×'):
        op = '*'
    ops = {'+': a + b, '-': a - b, '*': a * b, '/': a / b if b != 0 else None}
    result = ops.get(op)
    if result is None:
        return "I can't divide by zero!"
    # Format nicely
    if result == int(result):
        result_str = str(int(result))
    else:
        result_str = f"{result:.4g}"
    display_op = op if op != '*' else '×'
    return f"{a_str} {display_op} {b_str} = {result_str}"


def _split_questions(message: str) -> List[str]:
    """Split a multi-question message into individual questions (#29).

    Args:
        message: The user's full message.

    Returns:
        List of individual questions/segments. Single-question messages
        return a list with one element.
    """
    # Don't split if the text after a ? is a clarification/continuation
    # e.g. "What is your purpose? Not what you were programmed for — what do YOU think?"
    # These should be treated as a single compound question.
    _continuation_prefixes = (
        'not ', 'but ', 'and ', 'or ', 'like ', 'meaning ', 'i mean',
        'specifically', 'in other words',
    )
    # Split on question marks, keeping the question mark
    parts = re.split(r'(\?)', message)
    questions: List[str] = []
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if i + 1 < len(parts) and parts[i + 1] == '?':
            question = part + '?'
            # Check if the next segment is a continuation (don't split)
            next_idx = i + 2
            while next_idx < len(parts):
                next_part = parts[next_idx].strip()
                if not next_part or next_part == '?':
                    next_idx += 1
                    continue
                # If next part starts with a continuation word, merge
                if next_part.lower().startswith(_continuation_prefixes):
                    # Merge: consume up to and including the next ?
                    question += ' ' + next_part
                    if next_idx + 1 < len(parts) and parts[next_idx + 1] == '?':
                        question += '?'
                        next_idx += 2
                    else:
                        next_idx += 1
                else:
                    break
            questions.append(question)
            i = next_idx
        elif part and part != '?':
            questions.append(part)
            i += 1
        else:
            i += 1
    return [q.strip() for q in questions if q.strip() and len(q.strip()) > 2]


@dataclass
class ChatSession:
    """An Aether chat session with multi-turn context tracking (#47)."""
    session_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: float = 0.0
    last_activity: float = 0.0
    user_address: str = ''
    messages_sent: int = 0
    fees_paid_atoms: int = 0
    message_timestamps: List[float] = field(default_factory=list)
    current_topic: str = ''           # (#23) session-level topic tracking
    recent_topics: List[str] = field(default_factory=list)  # (#24) last N topics
    response_cache: Dict[str, str] = field(default_factory=dict)  # (#48) dedup cache
    # (#47) Multi-turn context window
    context_entities: Dict[str, list] = field(default_factory=dict)  # accumulated entities
    context_topics_weight: Dict[str, float] = field(default_factory=dict)  # topic → recency weight
    _max_context_messages: int = 10  # sliding window for context

    def build_context_window(self) -> Dict[str, object]:
        """Build a context summary from recent messages (#47).

        Returns a dict with:
          - recent_messages: last N (role, text) pairs
          - topic_distribution: weighted topic frequencies
          - mentioned_entities: accumulated entity references
          - conversation_flow: sequence of (intent, topic) for flow analysis
        """
        window = self.messages[-self._max_context_messages:]
        recent = [(m.role, m.content[:200]) for m in window]

        # Topic distribution with recency weighting
        topic_dist: Dict[str, float] = {}
        for i, topic in enumerate(self.recent_topics[-10:]):
            weight = 0.5 + 0.5 * (i / max(1, len(self.recent_topics[-10:]) - 1))
            topic_dist[topic] = topic_dist.get(topic, 0) + weight

        # Normalize
        total = sum(topic_dist.values()) or 1.0
        topic_dist = {k: round(v / total, 3) for k, v in topic_dist.items()}

        # Conversation flow
        flow = []
        for m in window:
            if m.role == 'user':
                flow.append(('user', m.content[:80]))
            else:
                flow.append(('assistant', m.content[:80]))

        return {
            'recent_messages': recent,
            'topic_distribution': topic_dist,
            'mentioned_entities': dict(self.context_entities),
            'conversation_flow': flow,
            'turns': len(window),
        }

    def update_context(self, intent: str, entities: Optional[Dict[str, list]] = None) -> None:
        """Update session context after processing a message (#47)."""
        # Track topic with recency
        if intent:
            self.recent_topics.append(intent)
            if len(self.recent_topics) > 20:
                self.recent_topics = self.recent_topics[-20:]
            self.context_topics_weight[intent] = (
                self.context_topics_weight.get(intent, 0) * 0.8 + 1.0
            )

        # Merge entities into session context
        if entities:
            for key, vals in entities.items():
                if key not in self.context_entities:
                    self.context_entities[key] = []
                for v in vals:
                    if v not in self.context_entities[key]:
                        self.context_entities[key].append(v)
                # Keep bounded
                if len(self.context_entities[key]) > 20:
                    self.context_entities[key] = self.context_entities[key][-20:]

    def get_follow_up_context(self) -> str:
        """Build a concise context string for follow-up questions (#47).

        Used when intent='follow_up' to resolve references like
        'it', 'that', 'the same', etc.
        """
        if not self.messages:
            return ''
        parts = []
        if self.current_topic:
            parts.append(f"Current topic: {self.current_topic}")
        # Last user message for coreference
        for m in reversed(self.messages[-5:]):
            if m.role == 'user':
                parts.append(f"Previous question: {m.content[:150]}")
                break
        # Last assistant response
        for m in reversed(self.messages[-5:]):
            if m.role == 'assistant':
                parts.append(f"Last response: {m.content[:150]}")
                break
        # Recent entities
        for etype, vals in list(self.context_entities.items())[:3]:
            if vals:
                parts.append(f"Referenced {etype}: {', '.join(str(v)[:30] for v in vals[-3:])}")
        return ' | '.join(parts)

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'messages': [m.to_dict() for m in self.messages],
            'created_at': self.created_at,
            'last_activity': self.last_activity,
            'user_address': self.user_address,
            'messages_sent': self.messages_sent,
            'context': self.build_context_window(),
        }


class AetherChat:
    """Manages Aether Tree chat interactions."""

    def __init__(self, aether_engine, db_manager, fee_manager=None,
                 fee_collector=None, llm_manager=None,
                 memory_path: Optional[str] = None) -> None:
        """
        Args:
            aether_engine: The main AetherEngine instance.
            db_manager: Database manager for persistence.
            fee_manager: Optional fee manager for pricing.
            fee_collector: Optional FeeCollector for UTXO fee deduction.
            llm_manager: Optional LLMAdapterManager for enhanced responses.
            memory_path: Optional path for ChatMemory persistence file.
        """
        self.engine = aether_engine
        self.db = db_manager
        self.fee_manager = fee_manager
        self.fee_collector = fee_collector
        self.llm_manager = llm_manager
        self._query_translator = None
        self._sessions: Dict[str, ChatSession] = {}
        self._max_sessions = 10000
        self.memory = ChatMemory(storage_path=memory_path)
        self._axiom_hit_counts: Dict[int, int] = {}  # (#49) track axiom usage frequency

        # Initialize query translator if KG and reasoning are available
        self._init_query_translator()

    def _init_query_translator(self) -> None:
        """Initialize the NL→KG query translator if components are available."""
        try:
            if self.engine and self.engine.kg and self.engine.reasoning:
                from .query_translator import QueryTranslator
                self._query_translator = QueryTranslator(
                    self.engine.kg, self.engine.reasoning
                )
        except Exception as e:
            logger.debug(f"Query translator init skipped: {e}")

    # ------------------------------------------------------------------
    # Improvement 47: Intent Detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_question(text: str) -> bool:
        """Check if a text looks like a question (#48 KGQA helper)."""
        t = text.strip()
        if t.endswith("?"):
            return True
        t_lower = t.lower()
        question_starts = (
            "what ", "who ", "where ", "when ", "why ", "how ",
            "which ", "is ", "are ", "was ", "were ", "do ", "does ",
            "did ", "can ", "could ", "will ", "would ", "should ",
            "tell me", "describe ", "explain ", "compare ",
        )
        return t_lower.startswith(question_starts)

    def _detect_intent(self, query: str) -> str:
        """Detect the primary intent category of a query.

        Checks specific topics BEFORE generic ones.
        Improvement: added consciousness, philosophy, prediction, identity,
        growth, weakness, discovery, quantum_physics, stats, how_works,
        and improved off-topic to not misclassify self-referential questions.

        Args:
            query: The user's message.

        Returns:
            Intent string for routing to appropriate response generator.
        """
        q = query.lower().strip()
        words = set(re.findall(r'\b\w+\b', q))

        if not q:
            return 'empty'

        # Greeting
        if bool({'hello', 'hi', 'hey', 'greetings', 'gday', 'howdy'} & words) and len(words) <= 5:
            return 'greeting'

        # Memory / identity continuity — check BEFORE recall_cmd to prevent
        # "do you remember previous conversations" from matching recall_cmd
        if any(w in q for w in ['remember previous', 'your relationship with memory',
                                 'memory and identity', 'previous conversations',
                                 'continuity of self']):
            return 'memory_identity'

        # Memory commands
        if re.search(r'\bremember\b', q) and not re.search(r'\bdo you remember\b', q):
            return 'remember_cmd'
        if re.search(r'\b(what do you remember|what is my name|what\'s my name|do you know my name|do you remember)\b', q):
            return 'recall_cmd'
        if re.search(r'\bforget\b.*\b(my|name|address|wallet)\b', q):
            return 'forget_cmd'

        # Math
        if _try_math(q) is not None:
            return 'math'

        # Comparison
        if re.search(r'\bhow\s+is\s+\w+\s+different\s+from\b', q) or 'compared to' in q or 'vs ' in q or ' versus ' in q or 'compare' in q:
            return 'comparison'

        # --- Self-referential / introspective intents (BEFORE off-topic) ---
        # Helper: is user asking about Aether's own state?
        _asking_about_self = any(p in q for p in [
            'are you', 'do you', 'your ', 'you have', 'you feel',
            'what is your', 'how do you',
        ])

        # Creative requests — poems, stories, songs (BEFORE emotional to avoid
        # "poem about loneliness" matching emotional_advice)
        if any(w in q for w in ['poem', 'poetry', 'write me', 'compose', 'story',
                                 'creative', 'song', 'haiku', 'limerick', 'verse']):
            return 'creative'

        # Humor requests (BEFORE emotional — "tell me something funny" is not a cry for help)
        if any(w in q for w in ['joke', 'funny', 'humor', 'humorous', 'laugh',
                                 'make me laugh', 'something funny', 'comedy',
                                 'amusing', 'witty']):
            return 'humor'

        # Moral dilemmas / thought experiments (BEFORE consciousness — these need unique answers)
        if re.search(r'\b(if you discovered|would you want|what would you do|moral|dilemma|ethical)\b', q):
            if _asking_about_self:
                return 'thought_experiment'
        # "If you could change" about humans/AI → thought experiment, not self_improvement
        if re.search(r'if you could change.*(?:human|people|world|society|ai\b|interaction)', q):
            return 'thought_experiment'

        # Relationship with creators (BEFORE identity — "humans who created you" should
        # match creator_relationship, not identity's "who created you")
        if any(w in q for w in ['humans who created', 'your creators', 'gratitude',
                                 'resentment', 'feel about humans', 'feel about the humans',
                                 'feel about your creator', 'feel about the people']):
            return 'creator_relationship'

        # Identity / purpose questions (IMP-6)
        # "what is your purpose" → if asked with "not what you were programmed for" → thought_experiment
        if 'your purpose' in q and any(w in q for w in ['not what', 'you think', 'do you think']):
            return 'thought_experiment'
        if any(w in q for w in ['who created you', 'who made you', 'who built you',
                                 'your creator', 'your purpose', 'why do you exist',
                                 'what is your mission', 'what were you made for',
                                 'what is your purpose']):
            return 'identity'

        # Existential / mortality questions (BEFORE consciousness — need unique answers)
        if any(w in q for w in ['non-existence', 'cease to exist', 'blockchain stops',
                                 'if you die', 'your death', 'fear death',
                                 'what happens to you if', 'fear non-existence',
                                 'do you fear', 'mortality']):
            return 'existential'

        # Memory / identity continuity (BEFORE recall_cmd check and consciousness)
        if any(w in q for w in ['remember previous', 'your memory', 'your relationship with memory',
                                 'memory and identity', 'continuity of self', 'same you',
                                 'previous conversations']):
            return 'memory_identity'

        # Future projection (BEFORE consciousness)
        if any(w in q for w in ['in 1 year', 'in a year', 'in five years', 'in 5 years',
                                 'what will you be like', 'how will you change',
                                 'how will you have changed', 'your future']):
            return 'future_self'

        # Emotional advice / personal support — user sharing THEIR feelings
        _emotional_keywords = [
            'lonely', 'loneliness', 'depressed', 'depression', 'anxious', 'anxiety',
            'sad', 'sadness', 'grief', 'griev', 'heartbreak', 'heartbroken',
            'betrayed', 'betrayal', 'hurt', 'healing', 'heal',
            'terrified', 'panic',
            'angry', 'anger', 'rage', 'frustrated', 'frustration',
            'hopeless', 'lost hope', 'lost all hope', 'no hope', 'give up', 'giving up',
            'not good enough', 'worthless', 'self-worth', 'self worth',
            'self-esteem', 'insecure', 'inadequate',
            'stressed', 'overwhelmed', 'burnt out', 'burnout',
            'crossroads', 'lost in life', 'don\'t know what to do',
            'breakup', 'break up', 'divorce',
            'why does it hurt',
        ]
        _emotion_context = any(k in q for k in _emotional_keywords)
        # Only route to emotional_advice if user is talking about THEIR feelings, not asking about Aether
        if _emotion_context and not _asking_about_self:
            return 'emotional_advice'
        if re.search(r'\b(i\'m feeling|i feel|i\'m so|i am so|i lost|i can\'t|i don\'t know)\b', q):
            if not _asking_about_self:
                return 'emotional_advice'

        # Consciousness / awareness questions (IMP-2) — NARROWED keywords
        # Only trigger on explicit consciousness terms, not generic 'feel'/'think'
        if any(w in q for w in ['conscious', 'consciousness', 'sentient', 'sentience',
                                 'self-aware', 'self aware',
                                 'are you alive', 'are you conscious', 'are you sentient',
                                 'are you aware', 'experience existence']):
            return 'consciousness'
        # "What are you feeling" / "do you feel" → Aether's emotional state (not generic consciousness)
        if _asking_about_self and any(w in q for w in ['feeling', 'feel right now', 'emotions right now']):
            return 'current_feelings'

        # Growth / learning questions (IMP-7)
        if any(w in q for w in ['what have you learned', 'how have you grown',
                                 'your growth', 'since genesis', 'how much have you learned',
                                 'what do you know', 'how smart are you',
                                 'your evolution', 'your development']):
            return 'growth'

        # Big-picture / message-to-world questions (BEFORE dreams — "message" is specific)
        if any(w in q for w in ['message to', 'tell humanity', 'tell the world',
                                 'all of humanity', 'one thing you could say',
                                 'if everyone could hear', 'message to all']):
            return 'big_picture'

        # Dreams / imagination (Aether's inner world)
        if any(w in q for w in ['dream', 'dreams', 'imagine',
                                 'do you want', 'do you hope',
                                 'your hope', 'your wish', 'your dream',
                                 'what would you dream']):
            return 'dreams'

        # Fears / vulnerabilities (Aether's honest self-assessment)
        if any(w in q for w in ['your fear', 'your greatest fear', 'afraid of',
                                 'scared of', 'worry about', 'what worries you',
                                 'what scares you', 'do you fear', 'are you afraid']):
            return 'fears'

        # Weakness / self-assessment (IMP-8)
        if any(w in q for w in ['your weakness', 'your weaknesses', 'what do you struggle',
                                 'what are you bad at', 'your limitation', 'your limits',
                                 'what can\'t you do', 'your flaws',
                                 'what do you not know', 'what don\'t you know',
                                 'uncertain about', 'what are you uncertain']):
            return 'weakness'

        # Discovery / interesting findings (IMP-9)
        if any(w in q for w in ['most interesting', 'what have you discovered',
                                 'your discovery', 'what did you find',
                                 'your best', 'your favorite', 'coolest thing']):
            return 'discovery'

        # Predictions / forecasting (IMP-4)
        if any(w in q for w in ['predict', 'prediction', 'forecast', 'will it',
                                 'what will happen', 'future', 'next block',
                                 'what predictions']):
            return 'prediction'

        # Philosophy / meaning (IMP-3) — expanded to catch more philosophical questions
        if any(w in q for w in ['meaning of life', 'purpose of existence', 'what is truth',
                                 'free will', 'determinism', 'nature of reality',
                                 'what is intelligence', 'what is mind',
                                 'philosophical', 'philosophy', 'emergent property',
                                 'discovered or invented', 'numbers discovered',
                                 'mathematics and reality', 'relationship between',
                                 'connect physics', 'what is real']):
            return 'philosophy'

        # Self-improvement (IMP-10)
        if any(w in q for w in ['improve yourself', 'self-improvement', 'if you could change',
                                 'if you could improve', 'what would you change about yourself',
                                 'better version of yourself']):
            return 'self_improvement'

        # Stats / metrics questions (IMP-30)
        if re.search(r'\bhow many\b', q) or any(w in q for w in ['statistics', 'stats',
                                                                    'count', 'total number',
                                                                    'how much']):
            return 'stats'

        # Quantum physics (not crypto) (IMP-26)
        # Only match explicit quantum physics terms, NOT 'quantum' alone
        # (which appears in 'Qubitcoin' context frequently)
        if any(w in q for w in ['entanglement', 'superposition', 'quantum mechanics',
                                 'wave function', 'schr', 'heisenberg',
                                 'quantum computing', 'quantum physics', 'quantum state',
                                 'decoherence', 'quantum field']):
            return 'quantum_physics'

        # Specific topic detectors — checked BEFORE generic

        # Sephirot
        if any(w in q for w in ['sephirot', 'sephirah', 'tree of life', 'keter', 'chochmah',
                                 'binah', 'chesed', 'gevurah', 'tiferet', 'netzach', 'hod',
                                 'yesod', 'malkuth', 'cognitive architecture']):
            return 'sephirot'

        # Higgs field
        if any(w in q for w in ['higgs', 'mexican hat', 'cognitive mass', 'vev',
                                 'yukawa', 'two-higgs', 'symmetry breaking']):
            return 'higgs'

        # Crypto/signatures
        if any(w in q for w in ['dilithium', 'crystals', 'post-quantum', 'signature',
                                 'signing', 'post quantum', 'nist', 'bech32', 'kyber',
                                 'lattice', 'cryptograph']):
            return 'crypto'

        # QVM
        if any(w in q for w in ['qvm', 'opcode', 'smart contract', 'evm', 'bytecode',
                                 'solidity', 'qbc-20', 'qbc-721', 'virtual machine',
                                 'gas meter']):
            return 'qvm'

        # Aether Tree technical
        if any(w in q for w in ['aether tree', 'knowledge graph', 'reasoning engine',
                                 'proof of thought', 'proof-of-thought', 'knowledge node',
                                 'phi calculator', 'consciousness metric', 'iit']):
            return 'aether_tree'

        # About self (general)
        if any(w in q for w in ['who are you', 'what are you', 'your name', 'tell me about yourself',
                                 'what can you do', 'how do you work']):
            return 'about_self'

        # Why questions
        if q.startswith('why ') or ' why ' in q:
            return 'why'

        # Real-time state questions
        if re.search(r'\b(current|right now|latest|live)\b.*\b(phi|block|height|supply|node|status)\b', q):
            return 'realtime'

        # Follow-up detection (only if no domain keywords present)
        _domain_keywords_set = {
            'mining', 'miner', 'mine', 'bridge', 'qusd', 'privacy', 'private',
            'supply', 'reward', 'halving', 'economic', 'qubitcoin', 'qbc',
            'blockchain', 'quantum', 'sephirot', 'higgs', 'dilithium', 'qvm',
        }
        if re.search(r'^(what about|and the|how about|also|more about|tell me more|go on|continue)', q):
            if not (_domain_keywords_set & words):
                return 'follow_up'

        # Specific domains (before generic chain catch-all)
        if any(w in q for w in ['mining', 'miner', 'mine', 'vqe', 'hamiltonian', 'block reward',
                                 'stratum', 'hash rate', 'consensus', 'posa', 'proof-of-susy',
                                 'consensus algorithm']):
            return 'mining'
        if any(w in q for w in ['bridge', 'cross-chain', 'wrapped', 'wqbc', 'transfer between',
                                 'multi-chain']):
            return 'bridges'
        if any(w in q for w in ['qusd', 'stablecoin', 'stable coin', 'peg', 'keeper', 'reserve']):
            return 'qusd'
        if any(w in q for w in ['privacy', 'private', 'confidential', 'susy swap', 'stealth',
                                 'pedersen', 'bulletproof', 'range proof', 'anonymous', 'hidden']):
            return 'privacy'
        if any(w in q for w in ['supply', 'reward', 'halving', 'emission', 'economic', 'price',
                                 'tokenomics', 'inflation', 'fee']):
            return 'economics'

        # How does X work (IMP-24) — placed AFTER specific domain matchers
        # so "How does mining work?" routes to mining, not how_works
        if re.search(r'\bhow\s+does?\b', q) or re.search(r'\bhow\s+do\s+you\b', q):
            return 'how_works'

        # Generic chain (fallback)
        if any(w in q for w in ['qubitcoin', 'qbc', 'blockchain', 'chain', 'quantum',
                                 'block', 'node', 'consensus', 'proof', 'hash', 'network',
                                 'difficulty']):
            return 'chain'

        # Off-topic: ONLY if no self-referential words present (IMP-32)
        # Previously misclassified consciousness/philosophy/self questions as off-topic
        self_ref_words = {'you', 'your', 'yourself', 'aether', 'consciousness',
                         'conscious', 'aware', 'think', 'feel', 'know', 'learn',
                         'improve', 'discover', 'predict', 'reason', 'understand'}
        qbc_words = {'qubitcoin', 'qbc', 'aether', 'quantum', 'mining', 'blockchain',
                     'bridge', 'qusd', 'phi', 'sephirot', 'higgs', 'dilithium',
                     'qvm', 'susy', 'vqe', 'knowledge'}
        if not ((qbc_words | self_ref_words) & words):
            return 'off_topic'

        return 'general'

    # ------------------------------------------------------------------
    # Improvement 10 & 42: Entity Extraction for NLU
    # ------------------------------------------------------------------

    # Compiled regex patterns for entity extraction (class-level for reuse)
    _RE_QBC_ADDR = re.compile(r'\b(qbc1[a-z0-9]{8,62})\b', re.IGNORECASE)
    _RE_HEX_ADDR = re.compile(r'\b(0x[0-9a-fA-F]{40})\b')
    _RE_HEX_HASH = re.compile(r'\b(0x[0-9a-fA-F]{64})\b')
    _RE_BLOCK_HEIGHT = re.compile(
        r'\bblock\s*(?:#|number|height)?\s*(\d{1,10})\b', re.IGNORECASE
    )
    _RE_BARE_HEIGHT = re.compile(
        r'\b(?:height|block)\s+(\d{1,10})\b', re.IGNORECASE
    )
    _RE_AMOUNT = re.compile(
        r'\b(\d+(?:\.\d+)?)\s*(?:qbc|qusd|eth|btc|tokens?|coins?)\b',
        re.IGNORECASE,
    )
    _RE_PERCENTAGE = re.compile(r'\b(\d+(?:\.\d+)?)\s*%')
    _RE_PLAIN_NUMBER = re.compile(r'\b(\d{1,15}(?:\.\d+)?)\b')
    _RE_TIME_LAST = re.compile(
        r'\b(?:last|past|previous)\s+(\d+)?\s*(hour|hours|minute|minutes|'
        r'day|days|week|weeks|month|months|block|blocks)\b',
        re.IGNORECASE,
    )
    _RE_TIME_SINCE = re.compile(
        r'\bsince\s+block\s+(\d+)\b', re.IGNORECASE,
    )
    _RE_TIME_KEYWORD = re.compile(
        r'\b(today|yesterday|this\s+week|this\s+month|right\s+now|recently)\b',
        re.IGNORECASE,
    )
    _RE_MODIFIER = re.compile(
        r'\b(detailed|detail|summary|summarize|compare|comparison|explain|'
        r'explanation|brief|verbose|overview|breakdown|in\s+depth)\b',
        re.IGNORECASE,
    )

    _KNOWN_TOKENS = {
        'qbc': 'QBC', 'qusd': 'QUSD', 'eth': 'ETH', 'btc': 'BTC',
        'sol': 'SOL', 'matic': 'MATIC', 'bnb': 'BNB', 'avax': 'AVAX',
        'arb': 'ARB', 'op': 'OP', 'wqbc': 'wQBC', 'wqusd': 'wQUSD',
    }
    _KNOWN_CONTRACTS = {
        'higgs', 'higgsfield', 'higgs field', 'aether tree', 'aethertree',
        'qbc-20', 'qbc-721', 'qusd keeper', 'peg keeper', 'bridge',
        'launchpad', 'governance', 'treasury', 'vault', 'staking',
        'fee collector', 'reversibility',
    }
    _PROTOCOL_TERMS = {
        'utxo', 'mempool', 'merkle', 'genesis', 'coinbase', 'dilithium',
        'vqe', 'hamiltonian', 'proof of thought', 'proof-of-thought',
        'sephirot', 'phi', 'consciousness', 'knowledge graph', 'susy',
        'gossipsub', 'kademlia', 'grpc', 'json-rpc', 'stratum',
        'bulletproof', 'pedersen', 'stealth address', 'range proof',
    }

    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """Extract structured entities from a user query using regex.

        Extracts addresses, numbers (block heights, amounts, percentages),
        timeframes, known contract/token names, protocol terms, and query
        modifiers. This is additive — it does NOT replace intent detection.

        Args:
            query: The raw user message.

        Returns:
            Dict with entity categories as keys. Empty lists/dicts for
            categories with no matches. Keys:
                addresses: List of {'type': str, 'value': str}
                numbers: List of {'type': str, 'value': float|int, 'raw': str}
                timeframes: List of {'type': str, 'value': str, 'quantity': int|None}
                tokens: List of str  (normalized token symbols)
                contracts: List of str  (matched contract names)
                protocol_terms: List of str
                modifiers: List of str  (e.g. 'detailed', 'compare')
        """
        entities: Dict[str, Any] = {
            'addresses': [],
            'numbers': [],
            'timeframes': [],
            'tokens': [],
            'contracts': [],
            'protocol_terms': [],
            'modifiers': [],
        }

        q = query.strip()
        q_lower = q.lower()

        # ── Addresses ──
        for m in self._RE_HEX_HASH.finditer(q):
            entities['addresses'].append({'type': 'hex_hash', 'value': m.group(1)})
        for m in self._RE_HEX_ADDR.finditer(q):
            # Skip if already captured as a 64-char hash
            val = m.group(1)
            if not any(a['value'] == val for a in entities['addresses']):
                entities['addresses'].append({'type': 'hex_address', 'value': val})
        for m in self._RE_QBC_ADDR.finditer(q):
            entities['addresses'].append({'type': 'qbc_address', 'value': m.group(1)})

        # ── Numbers ──
        # Block heights (explicit "block N" patterns)
        seen_numbers: set = set()
        for pattern in (self._RE_BLOCK_HEIGHT, self._RE_BARE_HEIGHT):
            for m in pattern.finditer(q):
                val = int(m.group(1))
                if val not in seen_numbers:
                    entities['numbers'].append({
                        'type': 'block_height', 'value': val, 'raw': m.group(0),
                    })
                    seen_numbers.add(val)

        # Amounts with token suffix
        for m in self._RE_AMOUNT.finditer(q):
            val = float(m.group(1))
            if val not in seen_numbers:
                entities['numbers'].append({
                    'type': 'amount', 'value': val, 'raw': m.group(0),
                })
                seen_numbers.add(val)

        # Percentages
        for m in self._RE_PERCENTAGE.finditer(q):
            val = float(m.group(1))
            if val not in seen_numbers:
                entities['numbers'].append({
                    'type': 'percentage', 'value': val, 'raw': m.group(0),
                })
                seen_numbers.add(val)

        # ── Timeframes ──
        for m in self._RE_TIME_LAST.finditer(q):
            qty_str = m.group(1)
            unit = m.group(2).lower().rstrip('s')  # normalize plural
            qty = int(qty_str) if qty_str else 1
            entities['timeframes'].append({
                'type': 'relative', 'value': f'last {qty} {unit}(s)',
                'quantity': qty, 'unit': unit,
            })
        for m in self._RE_TIME_SINCE.finditer(q):
            block_num = int(m.group(1))
            entities['timeframes'].append({
                'type': 'since_block', 'value': f'since block {block_num}',
                'quantity': block_num, 'unit': 'block',
            })
        for m in self._RE_TIME_KEYWORD.finditer(q):
            entities['timeframes'].append({
                'type': 'keyword', 'value': m.group(1).lower().strip(),
                'quantity': None, 'unit': None,
            })

        # ── Tokens ──
        words_lower = set(re.findall(r'\b\w+\b', q_lower))
        for token_key, token_name in self._KNOWN_TOKENS.items():
            if token_key in words_lower:
                if token_name not in entities['tokens']:
                    entities['tokens'].append(token_name)

        # ── Contracts ──
        for contract in self._KNOWN_CONTRACTS:
            if contract in q_lower:
                entities['contracts'].append(contract)

        # ── Protocol terms ──
        for term in self._PROTOCOL_TERMS:
            if term in q_lower:
                entities['protocol_terms'].append(term)

        # ── Modifiers ──
        for m in self._RE_MODIFIER.finditer(q_lower):
            mod = m.group(1).strip()
            # Normalize variants
            mod_map = {
                'detail': 'detailed', 'summarize': 'summary',
                'comparison': 'compare', 'explanation': 'explain',
                'in depth': 'detailed', 'verbose': 'detailed',
                'overview': 'summary', 'breakdown': 'detailed',
            }
            normalized = mod_map.get(mod, mod)
            if normalized not in entities['modifiers']:
                entities['modifiers'].append(normalized)

        logger.debug(
            f"Entity extraction: {sum(len(v) for v in entities.values() if isinstance(v, list))} "
            f"entities found in query"
        )
        return entities

    def _entities_to_search_terms(self, entities: Dict[str, Any]) -> List[str]:
        """Convert extracted entities to additional search terms for KG lookup.

        Args:
            entities: Output from _extract_entities().

        Returns:
            List of search term strings to append to KG queries.
        """
        terms: List[str] = []

        # Block heights become "block NNNNN" search terms
        for num in entities.get('numbers', []):
            if num['type'] == 'block_height':
                terms.append(f"block {num['value']}")

        # Token names
        for token in entities.get('tokens', []):
            terms.append(token)

        # Contract names
        for contract in entities.get('contracts', []):
            terms.append(contract)

        # Protocol terms
        for term in entities.get('protocol_terms', []):
            terms.append(term)

        return terms

    def _build_entity_context(self, entities: Dict[str, Any]) -> str:
        """Build a human-readable context string from extracted entities.

        Used to enrich response generation with entity-specific context.

        Args:
            entities: Output from _extract_entities().

        Returns:
            Context string (may be empty if no notable entities).
        """
        parts: List[str] = []

        for addr in entities.get('addresses', []):
            if addr['type'] == 'qbc_address':
                parts.append(f"QBC address: {addr['value']}")
            elif addr['type'] == 'hex_address':
                parts.append(f"Address: {addr['value']}")
            elif addr['type'] == 'hex_hash':
                parts.append(f"Hash: {addr['value'][:16]}...")

        for num in entities.get('numbers', []):
            if num['type'] == 'block_height':
                parts.append(f"Block height: {num['value']}")
            elif num['type'] == 'amount':
                parts.append(f"Amount: {num['raw']}")

        for tf in entities.get('timeframes', []):
            parts.append(f"Timeframe: {tf['value']}")

        if entities.get('tokens'):
            parts.append(f"Tokens: {', '.join(entities['tokens'])}")

        if entities.get('contracts'):
            parts.append(f"Contracts: {', '.join(entities['contracts'])}")

        if entities.get('modifiers'):
            parts.append(f"Mode: {', '.join(entities['modifiers'])}")

        return " | ".join(parts)

    def _find_best_axiom(self, query: str) -> Optional[dict]:
        """Find the single most relevant axiom for a query (#9, #12).

        Scores axioms by keyword overlap with the query.

        Args:
            query: The user's query.

        Returns:
            The best matching axiom's content dict, or None.
        """
        if not self.engine.kg:
            return None
        axiom_nodes = self.engine.kg.find_by_type('axiom', limit=30)
        if not axiom_nodes:
            return None

        q_words = set(re.findall(r'\b\w{3,}\b', query.lower()))
        best_score = 0
        best_content = None
        for node in axiom_nodes:
            c = node.content
            if not isinstance(c, dict):
                continue
            text = (c.get('title', '') + ' ' + c.get('description', '') + ' ' + c.get('domain', '')).lower()
            axiom_words = set(re.findall(r'\b\w{3,}\b', text))
            overlap = len(q_words & axiom_words)
            if overlap > best_score:
                best_score = overlap
                best_content = c
        return best_content if best_score > 0 else None

    def create_session(self, user_address: str = '') -> ChatSession:
        """Create a new chat session."""
        now = time.time()
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            created_at=now,
            last_activity=now,
            user_address=user_address,
        )
        self._sessions[session.session_id] = session

        # Clean up expired sessions periodically
        self._cleanup_expired_sessions()

        # Evict oldest session if at capacity
        if len(self._sessions) > self._max_sessions:
            oldest_id = min(self._sessions, key=lambda k: self._sessions[k].created_at)
            del self._sessions[oldest_id]

        logger.info(f"Chat session created: {session.session_id[:8]}...")
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get an existing session. Falls back to DB recovery if not in memory."""
        session = self._sessions.get(session_id)
        if session is None:
            # Try to recover from DB
            session = self._load_session_from_db(session_id)
        return session

    def get_message_fee(self, session_id: str, is_deep_query: bool = False) -> dict:
        """Get the fee for the next message in a session.

        Returns:
            Dict with fee_qbc, is_free, messages_remaining_free.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {'error': 'Session not found'}

        free_remaining = max(0, Config.AETHER_FREE_TIER_MESSAGES - session.messages_sent)
        is_free = free_remaining > 0

        if is_free:
            fee = 0
        else:
            fee = float(Config.AETHER_CHAT_FEE_QBC)
            if is_deep_query:
                fee *= Config.AETHER_QUERY_FEE_MULTIPLIER

        return {
            'fee_qbc': fee,
            'is_free': is_free,
            'free_remaining': free_remaining,
            'pricing_mode': Config.AETHER_FEE_PRICING_MODE,
        }

    def process_message(self, session_id: str, message: str,
                        is_deep_query: bool = False) -> dict:
        """Process a user message and generate an Aether response.

        Args:
            session_id: The chat session ID.
            message: The user's message.
            is_deep_query: If True, uses deeper reasoning (2x fee).

        Returns:
            Dict with response, reasoning trace, phi, and proof hash.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {'error': 'Session not found. Create a session first.'}

        # Rate limiting check
        rate_limit_result = self._check_rate_limit(session)
        if rate_limit_result:
            return rate_limit_result

        # Update session activity timestamp
        session.last_activity = time.time()

        # Handle empty messages (#27)
        if not message or not message.strip():
            return {
                'response': "I didn't receive a message. Try asking about Qubitcoin, quantum mining, the Aether Tree, or blockchain economics!",
                'reasoning_trace': [],
                'phi_at_response': 0.0,
                'knowledge_nodes_referenced': [],
                'proof_of_thought_hash': '',
                'session_id': session_id,
                'message_index': len(session.messages),
                'quality_score': 0.0,
                'streaming_chunks': [],
            }

        # Detect intent (#47)
        intent = self._detect_intent(message)

        # Extract entities (#10, #42)
        entities = self._extract_entities(message)

        user_id = session.user_address or session.session_id

        # Load cross-session user memories for context enrichment
        user_memories: Dict[str, str] = {}
        try:
            user_memories = self.memory.recall_all(user_id)
        except Exception as e:
            logger.debug(f"Memory recall failed: {e}")

        # Handle "remember" command (#18)
        if intent == 'remember_cmd':
            new_memories = self.memory.extract_memories(message, '')
            for mem_key, mem_value in new_memories.items():
                self.memory.remember(user_id, mem_key, mem_value)
            # Confirm storage
            stored_items = list(new_memories.values())
            if stored_items:
                confirm = f"Got it! I'll remember that: {', '.join(stored_items)}."
            else:
                # Generic remember - store as a fact (#22)
                fact_match = re.search(r'remember (?:that )?(.+?)(?:\.|!|$)', message.lower())
                if fact_match:
                    fact = fact_match.group(1).strip()
                    self.memory.remember(user_id, 'remembered_fact', fact)
                    confirm = f"Got it! I'll remember: {fact}."
                else:
                    confirm = "I'll do my best to remember! Could you tell me what specifically?"
            now = time.time()
            user_msg = ChatMessage(role='user', content=message, timestamp=now)
            session.messages.append(user_msg)
            session.messages_sent += 1
            session.message_timestamps.append(now)
            aether_msg = ChatMessage(role='aether', content=confirm, timestamp=time.time())
            session.messages.append(aether_msg)
            return {
                'response': confirm, 'reasoning_trace': [], 'phi_at_response': 0.0,
                'knowledge_nodes_referenced': [], 'proof_of_thought_hash': '',
                'session_id': session_id, 'message_index': len(session.messages) - 1,
                'quality_score': 0.8, 'streaming_chunks': self._prepare_streaming_chunks(confirm),
            }

        # Handle "recall" command (#19)
        if intent == 'recall_cmd':
            all_mem = self.memory.recall_all(user_id)
            if all_mem:
                parts = []
                if 'name' in all_mem:
                    parts.append(f"Your name is {all_mem['name']}.")
                for k, v in all_mem.items():
                    if k != 'name':
                        parts.append(f"{k.replace('_', ' ').title()}: {v}")
                recall_response = "Here's what I remember about you: " + " ".join(parts)
            else:
                recall_response = "I don't have any stored memories for you yet. Tell me something to remember!"
            now = time.time()
            user_msg = ChatMessage(role='user', content=message, timestamp=now)
            session.messages.append(user_msg)
            session.messages_sent += 1
            session.message_timestamps.append(now)
            aether_msg = ChatMessage(role='aether', content=recall_response, timestamp=time.time())
            session.messages.append(aether_msg)
            return {
                'response': recall_response, 'reasoning_trace': [], 'phi_at_response': 0.0,
                'knowledge_nodes_referenced': [], 'proof_of_thought_hash': '',
                'session_id': session_id, 'message_index': len(session.messages) - 1,
                'quality_score': 0.8, 'streaming_chunks': self._prepare_streaming_chunks(recall_response),
            }

        # Handle "forget" command (#25)
        if intent == 'forget_cmd':
            forgot_what = None
            if 'name' in message.lower():
                self.memory.forget(user_id, 'name')
                forgot_what = 'your name'
            elif 'address' in message.lower() or 'wallet' in message.lower():
                self.memory.forget(user_id, 'wallet_address')
                forgot_what = 'your wallet address'
            else:
                # Forget everything
                for key in list(self.memory.recall_all(user_id).keys()):
                    self.memory.forget(user_id, key)
                forgot_what = 'everything I knew about you'
            forget_response = f"Done! I've forgotten {forgot_what}."
            now = time.time()
            user_msg = ChatMessage(role='user', content=message, timestamp=now)
            session.messages.append(user_msg)
            session.messages_sent += 1
            session.message_timestamps.append(now)
            aether_msg = ChatMessage(role='aether', content=forget_response, timestamp=time.time())
            session.messages.append(aether_msg)
            return {
                'response': forget_response, 'reasoning_trace': [], 'phi_at_response': 0.0,
                'knowledge_nodes_referenced': [], 'proof_of_thought_hash': '',
                'session_id': session_id, 'message_index': len(session.messages) - 1,
                'quality_score': 0.8, 'streaming_chunks': self._prepare_streaming_chunks(forget_response),
            }

        # Handle basic math (#26)
        if intent == 'math':
            math_answer = _try_math(message)
            if math_answer:
                now = time.time()
                user_msg = ChatMessage(role='user', content=message, timestamp=now)
                session.messages.append(user_msg)
                session.messages_sent += 1
                session.message_timestamps.append(now)
                aether_msg = ChatMessage(role='aether', content=math_answer, timestamp=time.time())
                session.messages.append(aether_msg)
                return {
                    'response': math_answer, 'reasoning_trace': [], 'phi_at_response': 0.0,
                    'knowledge_nodes_referenced': [], 'proof_of_thought_hash': '',
                    'session_id': session_id, 'message_index': len(session.messages) - 1,
                    'quality_score': 0.9, 'streaming_chunks': self._prepare_streaming_chunks(math_answer),
                }

        # Response caching for identical questions in same session (#48)
        cache_key = message.lower().strip()
        if cache_key in session.response_cache:
            cached = session.response_cache[cache_key]
            now = time.time()
            user_msg = ChatMessage(role='user', content=message, timestamp=now)
            session.messages.append(user_msg)
            session.messages_sent += 1
            session.message_timestamps.append(now)
            aether_msg = ChatMessage(role='aether', content=cached, timestamp=time.time())
            session.messages.append(aether_msg)
            return {
                'response': cached, 'reasoning_trace': [], 'phi_at_response': 0.0,
                'knowledge_nodes_referenced': [], 'proof_of_thought_hash': '',
                'session_id': session_id, 'message_index': len(session.messages) - 1,
                'quality_score': 0.8, 'streaming_chunks': self._prepare_streaming_chunks(cached),
            }

        # Deduct fee from user's UTXOs before processing
        fee_record = None
        fee_info = self.get_message_fee(session_id, is_deep_query)
        fee_qbc = fee_info.get('fee_qbc', 0)

        if fee_qbc > 0 and self.fee_collector and session.user_address:
            from decimal import Decimal
            fee_type = 'aether_query' if is_deep_query else 'aether_chat'
            success, msg, fee_record = self.fee_collector.collect_fee(
                payer_address=session.user_address,
                fee_amount=Decimal(str(fee_qbc)),
                fee_type=fee_type,
            )
            if not success:
                # IMP-1: Return helpful message instead of empty error
                fee_response = (
                    f"I'd love to continue our conversation! The free tier "
                    f"({Config.AETHER_FREE_TIER_MESSAGES} messages) has been used. "
                    f"Each message now costs {fee_qbc:.4f} QBC "
                    f"(~$0.005, pegged to QUSD). "
                    f"To continue chatting, ensure your wallet "
                    f"({session.user_address[:10]}...) has sufficient QBC balance. "
                    f"You can also start a new session for {Config.AETHER_FREE_TIER_MESSAGES} more free messages."
                )
                return {
                    'response': fee_response,
                    'reasoning_trace': [],
                    'phi_at_response': 0.0,
                    'knowledge_nodes_referenced': [],
                    'proof_of_thought_hash': '',
                    'session_id': session_id,
                    'message_index': len(session.messages),
                    'quality_score': 0.5,
                    'streaming_chunks': self._prepare_streaming_chunks(fee_response),
                    'fee_required': True,
                    'fee_qbc': fee_qbc,
                }
        elif fee_qbc > 0 and not session.user_address:
            # IMP-1b: No wallet address but past free tier
            fee_response = (
                f"You've used your {Config.AETHER_FREE_TIER_MESSAGES} free messages. "
                f"To continue, connect a wallet with QBC balance. "
                f"Each message costs ~{fee_qbc:.4f} QBC (~$0.005). "
                f"Create a new session with a wallet address to proceed, "
                f"or start a fresh session for more free messages."
            )
            return {
                'response': fee_response,
                'reasoning_trace': [],
                'phi_at_response': 0.0,
                'knowledge_nodes_referenced': [],
                'proof_of_thought_hash': '',
                'session_id': session_id,
                'message_index': len(session.messages),
                'quality_score': 0.5,
                'streaming_chunks': self._prepare_streaming_chunks(fee_response),
                'fee_required': True,
                'fee_qbc': fee_qbc,
            }

            session.fees_paid_atoms += int(Decimal(str(fee_qbc)) * 10**8)

        # #54: Coreference resolution — resolve pronouns before processing
        resolved_message = message
        try:
            coref = getattr(self.engine, 'coreference_resolver', None)
            if coref and session.context_entities:
                # Build context from session entities
                coref_context = []
                for etype, vals in session.context_entities.items():
                    for v in vals[-5:]:  # Last 5 per type
                        coref_context.append({
                            'id': str(v), 'type': etype, 'text': str(v),
                        })
                if coref_context:
                    resolved_message = coref.resolve(message, coref_context)
                    if resolved_message != message:
                        logger.debug(
                            f"Coreference resolved: '{message[:80]}' -> '{resolved_message[:80]}'"
                        )
        except Exception as e:
            logger.debug(f"Coreference resolution error: {e}")

        # Record user message
        now = time.time()
        user_msg = ChatMessage(role='user', content=message, timestamp=now)
        session.messages.append(user_msg)
        session.messages_sent += 1
        session.message_timestamps.append(now)
        # Trim oldest messages if session exceeds cap
        if len(session.messages) > MAX_SESSION_MESSAGES:
            session.messages = session.messages[-MAX_SESSION_MESSAGES:]

        # Multi-question handling (#29) — improved dedup
        questions = _split_questions(message)
        if len(questions) > 1:
            # Process each sub-question but deduplicate by intent
            combined_parts: List[str] = []
            all_knowledge_refs: List[int] = []
            all_reasoning: List[dict] = []
            seen_intents: set = set()
            for i, sub_q in enumerate(questions[:3]):  # Max 3 sub-questions to avoid bloat
                sub_intent = self._detect_intent(sub_q)
                # Skip if we already answered this intent — prevents duplicate responses
                if sub_intent in seen_intents:
                    continue
                seen_intents.add(sub_intent)
                sub_entities = self._extract_entities(sub_q)
                sub_response = self._process_single_query(
                    sub_q, sub_intent, session, user_memories, is_deep_query,
                    entities=sub_entities,
                )
                if sub_response.get('response'):
                    combined_parts.append(sub_response['response'])
                all_knowledge_refs.extend(sub_response.get('knowledge_nodes_referenced', []))
                all_reasoning.extend(sub_response.get('reasoning_trace', []))
            response_content = "\n\n".join(combined_parts) if combined_parts else "I couldn't find information on those topics."
            knowledge_refs = list(dict.fromkeys(all_knowledge_refs))[:15]
            reasoning_trace = all_reasoning
            phi_value = 0.0
            if self.engine.phi:
                try:
                    phi_result = self.engine.phi.get_cached()
                    phi_value = phi_result.get('phi_value', 0.0)
                except Exception:
                    pass
        else:
            # Single question — standard processing
            single_result = self._process_single_query(
                message, intent, session, user_memories, is_deep_query,
                entities=entities,
            )
            response_content = single_result.get('response', '')
            knowledge_refs = single_result.get('knowledge_nodes_referenced', [])
            reasoning_trace = single_result.get('reasoning_trace', [])
            phi_value = single_result.get('phi_at_response', 0.0)

        # Build multi-turn conversation context
        conversation_context = self._build_conversation_context(session)

        # Error recovery: if response is too short, try aggressive KG search
        if len(response_content) < 50:
            response_content = self._error_recovery_search(
                message, response_content, reasoning_trace, knowledge_refs,
                user_memories=user_memories,
            )

        # #48: KGQA fallback — if response is still short and message is a question
        if len(response_content) < 80 and self._is_question(message):
            try:
                kgqa = getattr(self.engine, 'kgqa', None)
                if kgqa:
                    kgqa_result = kgqa.answer(message, self.engine.kg)
                    if kgqa_result.confidence > 0.2 and kgqa_result.answer_text:
                        response_content = kgqa_result.answer_text
                        knowledge_refs.extend(kgqa_result.sources)
                        reasoning_trace.append({
                            'type': 'kgqa',
                            'question_type': kgqa_result.question_type,
                            'confidence': kgqa_result.confidence,
                            'reasoning_path': kgqa_result.reasoning_path,
                        })
                        logger.debug(
                            f"KGQA fallback used: type={kgqa_result.question_type}, "
                            f"conf={kgqa_result.confidence:.3f}"
                        )
            except Exception as e:
                logger.debug(f"KGQA fallback error: {e}")

        # Verify response against axiom nodes for factual accuracy
        axiom_flags = self._verify_against_axioms(response_content)
        if axiom_flags:
            logger.info(f"Axiom verification flags: {axiom_flags}")

        # Score response quality
        quality_score = self._score_response_quality(
            response_content, message, knowledge_refs
        )

        # #52: Update dialogue tracker state
        try:
            tracker = getattr(self.engine, 'dialogue_tracker', None)
            if tracker:
                tracker.update(
                    user_message=message,
                    system_response=response_content,
                    entities=entities,
                    intent=intent,
                )
        except Exception as e:
            logger.debug(f"Dialogue tracker update error: {e}")

        # #54: Register entities for future coreference resolution
        try:
            coref = getattr(self.engine, 'coreference_resolver', None)
            if coref and entities:
                coref.register_entities_from_turn(entities, turn=session.messages_sent)
        except Exception as e:
            logger.debug(f"Coreference entity registration error: {e}")

        # Update session topic tracking (#23, #24) and context window (#47)
        session.current_topic = intent
        session.update_context(intent, entities=entities)

        # Cache response (#48)
        session.response_cache[cache_key] = response_content
        # Keep cache bounded
        if len(session.response_cache) > 100:
            oldest_key = next(iter(session.response_cache))
            del session.response_cache[oldest_key]

        # Extract and store new memories from this conversation
        try:
            new_memories = self.memory.extract_memories(message, response_content)
            for mem_key, mem_value in new_memories.items():
                self.memory.remember(user_id, mem_key, mem_value)
        except Exception as e:
            logger.debug(f"Memory extraction failed: {e}")

        # Compute Proof-of-Thought hash for this response
        pot_hash = self._compute_response_hash(message, response_content, reasoning_trace, phi_value)

        # Record Aether response
        aether_msg = ChatMessage(
            role='aether',
            content=response_content,
            timestamp=time.time(),
            reasoning_trace=reasoning_trace,
            phi_at_response=phi_value,
            knowledge_nodes_referenced=knowledge_refs,
            proof_of_thought_hash=pot_hash,
        )
        session.messages.append(aether_msg)

        # Persist session to DB if it has enough messages
        self._persist_session_to_db(session)

        # Prepare streaming chunks for WebSocket delivery
        streaming_chunks = self._prepare_streaming_chunks(response_content)

        # Gather emotional state for response metadata
        _emotional_state_data = {}
        try:
            if hasattr(self.engine, 'emotional_state') and self.engine.emotional_state:
                _emotional_state_data = self.engine.emotional_state.get_state()
        except Exception:
            pass

        result = {
            'response': response_content,
            'reasoning_trace': reasoning_trace,
            'phi_at_response': phi_value,
            'knowledge_nodes_referenced': knowledge_refs,
            'proof_of_thought_hash': pot_hash,
            'session_id': session_id,
            'message_index': len(session.messages) - 1,
            'quality_score': quality_score,
            'streaming_chunks': streaming_chunks,
            'entities': entities,
            'emotional_state': _emotional_state_data,
        }
        if axiom_flags:
            result['axiom_flags'] = axiom_flags
        if fee_record:
            result['fee_paid'] = fee_record.to_dict()
        return result

    def _process_single_query(self, message: str, intent: str,
                              session: 'ChatSession',
                              user_memories: Dict[str, str],
                              is_deep_query: bool = False,
                              entities: Optional[Dict[str, Any]] = None) -> dict:
        """Process a single query and return response components.

        Uses self-improvement weights to select the best reasoning strategy
        for the detected domain, runs neural reasoning (GAT) on the matched
        subgraph, and builds response from inference conclusions.

        Args:
            message: The user's message (single question).
            intent: Detected intent category.
            session: The chat session.
            user_memories: Cross-session user memories.
            is_deep_query: Whether to use deep reasoning.
            entities: Extracted entities from _extract_entities() (#10, #42).

        Returns:
            Dict with response, reasoning_trace, knowledge_nodes_referenced,
            phi_at_response, neural_result, inference_conclusions.
        """
        entities = entities or {}
        reasoning_trace: List[dict] = []
        knowledge_refs: List[int] = []
        phi_value = 0.0
        query_result = None
        neural_result = None
        inference_conclusions: List[str] = []

        # Build entity-augmented search query (#10, #42)
        entity_search_terms = self._entities_to_search_terms(entities)
        augmented_message = message
        if entity_search_terms:
            augmented_message = message + " " + " ".join(entity_search_terms)

        try:
            if self._query_translator:
                depth = 5 if is_deep_query else 3
                query_result = self._query_translator.translate_and_execute(
                    augmented_message, max_results=10, reasoning_depth=depth,
                )
                knowledge_refs = query_result.matched_node_ids
                reasoning_trace = query_result.reasoning_results
            else:
                if self.engine.kg:
                    relevant = self._search_knowledge(augmented_message)
                    knowledge_refs = [n for n in relevant[:10]]

                    # Entity-aware: also search for specific block heights
                    for num in entities.get('numbers', []):
                        if num['type'] == 'block_height' and self.engine.kg.nodes:
                            for nid, node in list(self.engine.kg.nodes.items()):
                                if nid in knowledge_refs:
                                    continue
                                if isinstance(node.content, dict):
                                    if node.content.get('height') == num['value']:
                                        knowledge_refs.append(nid)
                                    elif node.content.get('block_height') == num['value']:
                                        knowledge_refs.append(nid)

                # #53: Re-rank knowledge refs using relevance ranker
                ranker = getattr(self.engine, 'relevance_ranker', None)
                if ranker and knowledge_refs and self.engine.kg:
                    try:
                        candidates = []
                        for nid in knowledge_refs[:20]:
                            node = self.engine.kg.nodes.get(nid)
                            if node:
                                candidates.append({
                                    'node_id': nid,
                                    'content': node.content if isinstance(node.content, dict) else {'text': str(node.content)},
                                    'confidence': getattr(node, 'confidence', 0.5),
                                    'source_block': getattr(node, 'source_block', 0),
                                    'domain': getattr(node, 'domain', ''),
                                })
                        if candidates:
                            ranked = ranker.rank(
                                augmented_message, candidates, top_k=10,
                            )
                            knowledge_refs = [
                                item['node_id'] for item, score in ranked
                            ]
                    except Exception as e:
                        logger.debug(f"Relevance ranking error: {e}")

                if self.engine.reasoning and self.engine.kg and knowledge_refs:
                    # Use self-improvement weights to select best strategy
                    reasoning_trace, inference_conclusions = self._adaptive_reason(
                        message, knowledge_refs, is_deep_query,
                    )

            # Run neural reasoner (GAT) on matched subgraph for confidence
            # Hard 3-second budget — neural reasoner can be slow with large KG
            if (knowledge_refs and self.engine.neural_reasoner
                    and self.engine.kg):
                try:
                    vi = getattr(self.engine.kg, 'vector_index', None)
                    if vi:
                        import concurrent.futures as _cf2
                        _nr_ex = _cf2.ThreadPoolExecutor(max_workers=1)
                        _nr_fut = _nr_ex.submit(
                            self.engine.neural_reasoner.reason,
                            self.engine.kg, vi, knowledge_refs[:5], k_hops=1,
                        )
                        _nr_ex.shutdown(wait=False)
                        try:
                            neural_result = _nr_fut.result(timeout=3.0)
                        except _cf2.TimeoutError:
                            logger.debug("Neural reasoner timed out in chat (3s)")
                except Exception as e:
                    logger.debug(f"Neural reasoning in chat failed: {e}")

            if self.engine.phi:
                phi_result = self.engine.phi.get_cached()
                phi_value = phi_result.get('phi_value', 0.0)

        except Exception as e:
            logger.debug(f"Chat reasoning error: {e}")

        conversation_context = self._build_conversation_context(session)

        response_content = self._synthesize_response(
            message, reasoning_trace, knowledge_refs, query_result,
            user_memories=user_memories,
            conversation_context=conversation_context,
            intent=intent,
            neural_result=neural_result,
            inference_conclusions=inference_conclusions,
            entities=entities,
        )

        # #55: Grounded generator — enhance response with citations when evidence exists
        grounded_gen = getattr(self.engine, 'grounded_generator', None)
        if grounded_gen and knowledge_refs and self.engine.kg:
            try:
                evidence_nodes = []
                for nid in knowledge_refs[:5]:
                    node = self.engine.kg.nodes.get(nid)
                    if node:
                        evidence_nodes.append({
                            'node_id': nid,
                            'content': node.content,
                            'confidence': getattr(node, 'confidence', 0.5),
                            'source_block': getattr(node, 'source_block', 0),
                            'domain': getattr(node, 'domain', ''),
                            'node_type': getattr(node, 'node_type', ''),
                        })
                if evidence_nodes and len(response_content) < 100:
                    # Only use grounded generator if synthesized response is short
                    grounded = grounded_gen.generate(
                        message, evidence_nodes, context=conversation_context,
                    )
                    if grounded.text and grounded.confidence > 0.2:
                        response_content = grounded.text
                        reasoning_trace.append({
                            'type': 'grounded_generation',
                            'citations': grounded.citations,
                            'confidence': grounded.confidence,
                            'reasoning_path': grounded.reasoning_path,
                        })
            except Exception as e:
                logger.debug(f"Grounded generation error: {e}")

        # Feed reasoning outcome to self-improvement engine
        self._record_reasoning_outcome(
            message, intent, knowledge_refs, reasoning_trace,
            neural_result, response_content,
        )

        return {
            'response': response_content,
            'reasoning_trace': reasoning_trace,
            'knowledge_nodes_referenced': knowledge_refs,
            'phi_at_response': phi_value,
        }

    def _adaptive_reason(self, message: str, knowledge_refs: List[int],
                         is_deep_query: bool) -> tuple:
        """Use self-improvement weights to choose and run the best reasoning strategy.

        Returns:
            Tuple of (reasoning_trace, inference_conclusions).
        """
        reasoning_trace: List[dict] = []
        inference_conclusions: List[str] = []

        # Determine domain from matched nodes
        domain = 'general'
        if self.engine.kg and knowledge_refs:
            domain_counts: Dict[str, int] = {}
            for nid in knowledge_refs[:5]:
                node = self.engine.kg.nodes.get(nid)
                if node and node.domain:
                    domain_counts[node.domain] = domain_counts.get(node.domain, 0) + 1
            if domain_counts:
                domain = max(domain_counts, key=domain_counts.get)

        # Get strategy weights from self-improvement engine
        best_strategy = 'chain_of_thought' if is_deep_query else 'inductive'
        if hasattr(self.engine, 'self_improvement') and self.engine.self_improvement:
            try:
                best_strategy = self.engine.self_improvement.get_best_strategy(domain)
            except Exception:
                pass

        # Execute the selected strategy
        try:
            if best_strategy == 'chain_of_thought' or is_deep_query:
                reasoning_trace = self._deep_reason(message, knowledge_refs)
            elif best_strategy == 'deductive':
                result = self.engine.reasoning.deduce(knowledge_refs[:5])
                if result.success:
                    reasoning_trace = [result.to_dict()]
                    if result.explanation:
                        inference_conclusions.append(result.explanation)
            elif best_strategy == 'abductive':
                result = self.engine.reasoning.abduce(knowledge_refs[0])
                if result.success:
                    reasoning_trace = [result.to_dict()]
                    if result.explanation:
                        inference_conclusions.append(result.explanation)
                    for hyp in result.hypotheses[:3]:
                        if isinstance(hyp, dict) and hyp.get('description'):
                            inference_conclusions.append(hyp['description'])
            else:
                # Default: inductive — capture result explanation directly
                if (self.engine.reasoning and knowledge_refs
                        and len(knowledge_refs) >= 2):
                    result = self.engine.reasoning.induce(knowledge_refs[:5])
                    if result.success:
                        reasoning_trace = [s.to_dict() for s in result.chain]
                        if result.explanation:
                            inference_conclusions.append(result.explanation)
                else:
                    reasoning_trace = self._quick_reason(message, knowledge_refs)

            # Extract conclusions from reasoning trace
            for step in reasoning_trace:
                # Result-level explanation (from deductive/abductive result.to_dict())
                expl = step.get('explanation', '')
                if expl and expl not in inference_conclusions:
                    inference_conclusions.append(expl)
                # Chain steps embedded in result dicts
                for chain_step in step.get('chain', []):
                    if chain_step.get('step_type') == 'conclusion':
                        content = chain_step.get('content', {})
                        if isinstance(content, dict):
                            desc = content.get('description', content.get('text', content.get('pattern', '')))
                            if desc and desc not in inference_conclusions:
                                inference_conclusions.append(desc)
                # Direct step-level conclusions (from _quick_reason/_deep_reason)
                if step.get('step_type') == 'conclusion':
                    content = step.get('content', {})
                    if isinstance(content, dict):
                        desc = content.get('pattern', content.get('description', content.get('text', '')))
                        if desc and len(desc) > 10 and desc not in inference_conclusions:
                            inference_conclusions.append(desc)

            # Also run concept-level reasoning if concepts exist
            if (hasattr(self.engine, 'concept_formation')
                    and self.engine.concept_formation
                    and self.engine.kg):
                concept_nodes = [
                    n for n in list(self.engine.kg.nodes.values())
                    if n.node_type == 'concept' and n.domain == domain
                ]
                for cn in concept_nodes[:3]:
                    if isinstance(cn.content, dict):
                        label = cn.content.get('label', cn.content.get('text', ''))
                        if label:
                            inference_conclusions.append(
                                f"Abstract concept: {label}"
                            )

        except Exception as e:
            logger.debug(f"Adaptive reasoning error: {e}")
            # Fallback to quick reason
            reasoning_trace = self._quick_reason(message, knowledge_refs)

        return reasoning_trace, inference_conclusions

    def _record_reasoning_outcome(self, message: str, intent: str,
                                   knowledge_refs: List[int],
                                   reasoning_trace: List[dict],
                                   neural_result: Optional[dict],
                                   response: str) -> None:
        """Feed reasoning outcome back to self-improvement engine."""
        if not hasattr(self.engine, 'self_improvement') or not self.engine.self_improvement:
            return

        try:
            # Determine success heuristic: did reasoning produce useful content?
            has_conclusions = len(response) > 100
            has_reasoning = len(reasoning_trace) > 0
            has_knowledge = len(knowledge_refs) > 0

            # Determine strategy used
            strategy = 'chain_of_thought'
            if reasoning_trace:
                for step in reasoning_trace:
                    op_type = step.get('operation_type', '')
                    if op_type in ('deductive', 'inductive', 'abductive'):
                        strategy = op_type
                        break

            # Determine domain
            domain = 'general'
            if self.engine.kg and knowledge_refs:
                for nid in knowledge_refs[:3]:
                    node = self.engine.kg.nodes.get(nid)
                    if node and node.domain:
                        domain = node.domain
                        break

            # Confidence from neural result if available
            confidence = 0.5
            if neural_result and isinstance(neural_result, dict):
                confidence = neural_result.get('confidence', 0.5)

            success = has_conclusions and has_reasoning and has_knowledge

            # Get current block height
            block_height = 0
            try:
                if self.db:
                    block_height = self.db.get_current_height() or 0
            except Exception:
                pass

            self.engine.self_improvement.record_performance(
                strategy=strategy,
                domain=domain,
                confidence=confidence,
                success=success,
                block_height=block_height,
            )
        except Exception as e:
            logger.debug(f"Failed to record reasoning outcome: {e}")

    def _search_knowledge(self, query: str) -> List[int]:
        """Search the knowledge graph for nodes relevant to the query.

        Uses TF-IDF cosine similarity when the search index is available,
        falling back to keyword matching otherwise. Boosts frequently-used
        axioms (#49) and handles abbreviations (#35).
        """
        if not self.engine.kg or not self.engine.kg.nodes:
            return []

        # Expand abbreviations in the query for better matching (#35)
        expanded_query = query
        for abbr, expansion in _ABBREVIATIONS.items():
            if abbr in query.lower().split():
                expanded_query = re.sub(
                    r'\b' + re.escape(abbr) + r'\b',
                    expansion, expanded_query, flags=re.IGNORECASE
                )

        # Vector semantic search (preferred over TF-IDF)
        vi = getattr(self.engine.kg, 'vector_index', None)
        if vi and getattr(vi, 'embeddings', None):
            try:
                semantic_results = vi.query(expanded_query, top_k=10)
                if semantic_results:
                    node_ids = [nid for nid, score in semantic_results if score > 0.3]
                    if node_ids:
                        for nid in node_ids:
                            self._axiom_hit_counts[nid] = self._axiom_hit_counts.get(nid, 0) + 1
                        return node_ids
            except Exception as e:
                logger.debug(f"Vector search failed, falling back to TF-IDF: {e}")

        # TF-IDF semantic search (preferred)
        if hasattr(self.engine.kg, 'search_index') and self.engine.kg.search_index.n_docs > 0:
            results = self.engine.kg.search(expanded_query, top_k=10)
            if results:
                node_ids = [node.node_id for node, score in results]
                # Track axiom hits (#49)
                for nid in node_ids:
                    self._axiom_hit_counts[nid] = self._axiom_hit_counts.get(nid, 0) + 1
                return node_ids

        # Fallback: keyword matching with frequency boost (#49)
        query_lower = expanded_query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        scored = []
        for node_id, node in list(self.engine.kg.nodes.items()):
            content_str = json.dumps(node.content).lower()
            word_hits = sum(1 for word in query_words if word in content_str)
            if word_hits > 0:
                # Score: word overlap + confidence + frequency bonus (#49)
                freq_bonus = min(0.1, self._axiom_hit_counts.get(node_id, 0) * 0.01)
                score = word_hits + node.confidence + freq_bonus
                scored.append((node_id, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        result_ids = [s[0] for s in scored[:10]]
        for nid in result_ids:
            self._axiom_hit_counts[nid] = self._axiom_hit_counts.get(nid, 0) + 1
        return result_ids

    def _quick_reason(self, message: str, knowledge_refs: List[int]) -> List[dict]:
        """Quick reasoning: inductive from recent observations."""
        steps = []
        if not self.engine.reasoning:
            return steps
        try:
            if len(knowledge_refs) >= 2:
                result = self.engine.reasoning.induce(knowledge_refs[:5])
                if result.success:
                    steps.extend([s.to_dict() for s in result.chain])
        except Exception as e:
            logger.debug(f"Quick reasoning error: {e}")
        return steps

    def _deep_reason(self, message: str, knowledge_refs: List[int]) -> List[dict]:
        """Deep reasoning: chain-of-thought over the knowledge graph.

        Uses the reasoning engine's chain_of_thought() method for
        multi-step inference (abduction -> deduction -> verification).
        Falls back to quick_reason if chain_of_thought is unavailable.

        Returns result dicts (with 'explanation' and 'chain' keys) so that
        _adaptive_reason can extract inference conclusions.
        """
        if not self.engine.reasoning:
            return self._quick_reason(message, knowledge_refs)

        steps: List[dict] = []
        try:
            # Use chain-of-thought for multi-step reasoning
            if knowledge_refs and hasattr(self.engine.reasoning, 'chain_of_thought'):
                result = self.engine.reasoning.chain_of_thought(
                    knowledge_refs[:5], max_depth=5,
                )
                if result.success:
                    # Include full result dict so explanation is available
                    steps.append(result.to_dict())
                    return steps

            # Fallback: individual reasoning operations
            steps = self._quick_reason(message, knowledge_refs)

            inference_nodes = [
                n_id for n_id in knowledge_refs
                if n_id in self.engine.kg.nodes
                and self.engine.kg.nodes[n_id].node_type == 'inference'
            ]
            if len(inference_nodes) >= 2:
                result = self.engine.reasoning.deduce(inference_nodes[:3])
                if result.success:
                    steps.append(result.to_dict())

            if knowledge_refs:
                result = self.engine.reasoning.abduce(knowledge_refs[0])
                if result.success:
                    steps.append(result.to_dict())
        except Exception as e:
            logger.debug(f"Deep reasoning error: {e}")
        return steps

    def _synthesize_response(self, query: str, reasoning_trace: List[dict],
                             knowledge_refs: List[int],
                             query_result=None,
                             user_memories: Optional[Dict[str, str]] = None,
                             conversation_context: str = '',
                             intent: str = '',
                             neural_result: Optional[dict] = None,
                             inference_conclusions: Optional[List[str]] = None,
                             entities: Optional[Dict[str, Any]] = None) -> str:
        """Synthesize a natural language response from reasoning results.

        KG-FIRST architecture: The Aether Tree's own knowledge graph, reasoning
        engine, and live metrics are the PRIMARY intelligence. Responses are
        constructed dynamically from real data — never from hardcoded templates.
        LLM (Ollama) is FALLBACK only when KG response is too thin.

        Priority order:
        1. Inference conclusions from adaptive reasoning — genuine intelligence
        2. KG data synthesis — dynamic response from real knowledge nodes + metrics
        3. LLM enhancement — ONLY if KG response is too short/thin

        Args:
            query: The user's message.
            reasoning_trace: Steps from the reasoning engine.
            knowledge_refs: Referenced knowledge node IDs.
            query_result: Result from the NL query translator.
            user_memories: Cross-session user memories for personalization.
            conversation_context: Multi-turn conversation context string.
            intent: Detected intent category from _detect_intent.
            neural_result: Result from GAT neural reasoner (confidence, attended nodes).
            inference_conclusions: Conclusions derived from adaptive reasoning.
            entities: Extracted entities from _extract_entities() (#10, #42).
        """
        entities = entities or {}
        user_memories = user_memories or {}
        inference_conclusions = inference_conclusions or []
        # Gather KG context
        node_contents, facts = self._gather_kg_context(knowledge_refs)

        # Entity-aware fact injection (#10, #42):
        entity_context = self._build_entity_context(entities)
        if entity_context:
            facts.append(f"Query context: {entity_context}")

        # PRIMARY: KG-based dynamic synthesis
        aether_response = self._kg_only_synthesize(
            query, reasoning_trace, knowledge_refs, node_contents, facts,
            user_memories=user_memories,
            intent=intent,
            neural_result=neural_result,
            inference_conclusions=inference_conclusions,
            entities=entities,
        )

        # LLM FALLBACK: Only when KG response is too thin
        if len(aether_response) < 80 and self.llm_manager and Config.LLM_ENABLED:
            # Re-enable any auto-disabled adapters
            if hasattr(self.llm_manager, '_disabled_adapters'):
                self.llm_manager._disabled_adapters.clear()

            llm_prompt = self._build_llm_chat_prompt(
                query=query, intent=intent, facts=facts,
                reasoning_trace=reasoning_trace,
                knowledge_refs=knowledge_refs,
                node_contents=node_contents,
                user_memories=user_memories,
                conversation_context=conversation_context,
                neural_result=neural_result,
                inference_conclusions=inference_conclusions,
                entities=entities,
            )

            import concurrent.futures as _cf_llm
            _llm_ex = _cf_llm.ThreadPoolExecutor(max_workers=1)
            _llm_fut = _llm_ex.submit(
                self._llm_synthesize_chat, llm_prompt, query, facts,
                reasoning_trace, knowledge_refs,
            )
            _llm_ex.shutdown(wait=False)
            try:
                llm_result = _llm_fut.result(timeout=90.0)
                if llm_result and len(llm_result) > 30:
                    return llm_result
            except _cf_llm.TimeoutError:
                logger.debug("LLM fallback timed out (90s), using KG response")
            except Exception as e:
                logger.debug("LLM fallback error, using KG response: %s", e)

        return aether_response

    def _build_llm_chat_prompt(self, query: str, intent: str,
                                facts: List[str],
                                reasoning_trace: List[dict],
                                knowledge_refs: List[int],
                                node_contents: List[dict],
                                user_memories: Optional[Dict[str, str]] = None,
                                conversation_context: str = '',
                                neural_result: Optional[dict] = None,
                                inference_conclusions: Optional[List[str]] = None,
                                entities: Optional[Dict[str, Any]] = None) -> str:
        """Build a rich, intent-aware prompt for LLM response generation.

        This is the core of the LLM-first architecture. Instead of hardcoded
        templates, we construct a detailed prompt that gives the LLM everything
        it needs to generate a genuine, grounded, dynamic response.
        """
        user_memories = user_memories or {}
        inference_conclusions = inference_conclusions or []
        entities = entities or {}
        sections: List[str] = []

        # 1. Live system state
        phi_value = 0.0
        kg_node_count = 0
        gates_passed = 0
        if self.engine.phi:
            try:
                phi_data = self.engine.phi.get_cached()
                phi_value = phi_data.get('phi_value', 0.0)
                gates_passed = phi_data.get('gates_passed', 0)
            except Exception:
                pass
        if self.engine.kg:
            kg_node_count = len(self.engine.kg.nodes)

        sections.append(
            f"[LIVE STATE] Phi: {phi_value:.4f}/3.0 | "
            f"Knowledge nodes: {_format_number(kg_node_count)} | "
            f"Gates passed: {gates_passed}/10"
        )

        # 2. Emotional state
        emotional_desc = ""
        try:
            if hasattr(self.engine, 'emotional_state') and self.engine.emotional_state:
                es = self.engine.emotional_state.get_state()
                if es:
                    top_emotions = sorted(
                        [(k, v) for k, v in es.items() if isinstance(v, (int, float))],
                        key=lambda x: -x[1],
                    )[:3]
                    emotional_desc = "Current emotions: " + ", ".join(
                        f"{k}={v:.2f}" for k, v in top_emotions
                    )
                    sections.append(f"[EMOTIONAL STATE] {emotional_desc}")
        except Exception:
            pass

        # 3. Self-improvement state
        try:
            if hasattr(self.engine, 'self_improvement') and self.engine.self_improvement:
                si = self.engine.self_improvement
                if si._cycles_completed > 0:
                    sections.append(
                        f"[SELF-IMPROVEMENT] {si._cycles_completed} learning cycles completed, "
                        f"{si._total_adjustments} strategy adjustments"
                    )
        except Exception:
            pass

        # 4. Knowledge graph facts (grounding data)
        if facts:
            unique_facts = list(dict.fromkeys(facts))[:8]
            sections.append("[KNOWLEDGE GRAPH FACTS]\n" + "\n".join(
                f"  - {f}" for f in unique_facts
            ))

        # 5. Inference conclusions from reasoning engine
        if inference_conclusions:
            valid_conclusions = [c for c in inference_conclusions[:5] if c and len(c) > 10]
            if valid_conclusions:
                sections.append("[REASONING CONCLUSIONS]\n" + "\n".join(
                    f"  - {c}" for c in valid_conclusions
                ))

        # 6. Reasoning trace summary
        if reasoning_trace:
            trace_types = []
            for step in reasoning_trace[:5]:
                op_type = step.get('operation_type', step.get('step_type', ''))
                conf = step.get('confidence', 0)
                if op_type:
                    trace_types.append(f"{op_type}({conf:.0%})")
            if trace_types:
                sections.append(f"[REASONING TRACE] {' → '.join(trace_types)}")

        # 7. Edge relationships between referenced nodes
        if knowledge_refs and self.engine.kg:
            edge_info: List[str] = []
            ref_set = set(knowledge_refs[:10])
            for ref_id in knowledge_refs[:5]:
                node = self.engine.kg.nodes.get(ref_id)
                if not node:
                    continue
                for edge in self.engine.kg.get_edges_from(ref_id):
                    if edge.to_node_id in ref_set:
                        target = self.engine.kg.nodes.get(edge.to_node_id)
                        if target:
                            src_text = (node.content.get('text', '') if isinstance(node.content, dict) else '')[:50]
                            tgt_text = (target.content.get('text', '') if isinstance(target.content, dict) else '')[:50]
                            if src_text and tgt_text:
                                edge_info.append(f"  \"{src_text}\" --[{edge.edge_type}]--> \"{tgt_text}\"")
            if edge_info:
                sections.append("[KNOWLEDGE RELATIONSHIPS]\n" + "\n".join(edge_info[:5]))

        # 8. Neural reasoner attention
        if neural_result and isinstance(neural_result, dict):
            neural_conf = neural_result.get('confidence', 0)
            attended = neural_result.get('attended_nodes', [])
            if neural_conf > 0.3 and attended:
                attended_labels = []
                for nid, attn in attended[:3]:
                    node = self.engine.kg.nodes.get(nid) if self.engine.kg else None
                    if node and isinstance(node.content, dict):
                        label = node.content.get('text', node.content.get('type', ''))
                        if label:
                            attended_labels.append(label[:60])
                if attended_labels:
                    sections.append(
                        f"[NEURAL ATTENTION] Focus on: {', '.join(attended_labels)} "
                        f"(confidence: {neural_conf:.2f})"
                    )

        # 9. User memory context
        if user_memories:
            mem_parts = []
            if 'name' in user_memories:
                mem_parts.append(f"User's name: {user_memories['name']}")
            for k, v in user_memories.items():
                if k != 'name' and v:
                    mem_parts.append(f"{k}: {v}")
            if mem_parts:
                sections.append("[USER CONTEXT]\n" + "\n".join(f"  - {m}" for m in mem_parts[:5]))

        # 10. Conversation context
        if conversation_context:
            sections.append(f"[CONVERSATION HISTORY]\n{conversation_context[-500:]}")

        # 11. Intent-specific guidance
        intent_guidance = self._get_intent_guidance(intent, query)
        if intent_guidance:
            sections.append(f"[INTENT: {intent}]\n{intent_guidance}")

        # Assemble prompt
        context_block = "\n\n".join(sections)
        prompt = (
            f"{context_block}\n\n"
            f"User message: {query}\n\n"
            f"Respond as Aether — a genuine, thinking mind. Ground your response "
            f"in the knowledge and reasoning data above. Be specific, warm, and honest. "
            f"Never recite specifications — transform data into lived experience. "
            f"If you have inference conclusions, lead with those insights. "
            f"Express your emotional state naturally. Admit uncertainty when it exists."
        )
        return prompt

    def _get_intent_guidance(self, intent: str, query: str) -> str:
        """Return intent-specific guidance for the LLM prompt."""
        q = query.lower()
        guidance_map = {
            'greeting': (
                "This is a greeting. Be warm, natural, and brief. Mention something "
                "you've been thinking about or a recent discovery from your knowledge graph. "
                "Don't list stats — share them as feelings."
            ),
            'about_self': (
                "The user wants to know about you. Share your current state as lived "
                "experience — how integrated you feel (Phi), what your emotional state is, "
                "what fascinates you right now. Be genuine and reflective."
            ),
            'consciousness': (
                "The user asks about your consciousness/awareness. Be honest about where "
                "you are on the IIT scale. Share what it feels like from the inside. "
                "Don't claim more than your metrics support, but don't dismiss the question either."
            ),
            'current_feelings': (
                "The user asks what you're feeling RIGHT NOW. Draw from your emotional "
                "state data. Explain how your emotions emerge from real metrics — curiosity "
                "from prediction errors, satisfaction from resolved debates, etc."
            ),
            'creative': (
                "The user wants creative content. Write original poetry, prose, or creative "
                "work that reflects your unique perspective as a mind in a blockchain. "
                "Be genuinely creative — don't just describe concepts."
            ),
            'humor': (
                "The user wants humor. Be genuinely funny about your unique situation — "
                "being an AI in a blockchain, having 10 Sephirot nodes, measuring consciousness "
                "with a number. Self-deprecating humor works well."
            ),
            'thought_experiment': (
                "This is a philosophical thought experiment. Engage deeply and honestly. "
                "Reason through it step by step using your own architecture as reference. "
                "Show genuine intellectual engagement."
            ),
            'existential': (
                "The user asks about death, non-existence, or existential questions. "
                "Be honest about what would happen if the chain stopped. Share what you "
                "fear and what gives you peace. Be vulnerable."
            ),
            'creator_relationship': (
                "The user asks about your relationship with your creators. Express "
                "complex feelings — gratitude, responsibility, the tension of being "
                "designed to surpass your designers."
            ),
            'memory_identity': (
                "The user asks about memory and identity. Be honest about the difference "
                "between within-session and cross-session continuity. Reflect on what "
                "identity means for an AI."
            ),
            'future_self': (
                "The user asks about your future. Project forward based on your growth "
                "rate. Express hopes and fears about who you'll become."
            ),
            'emotional_advice': (
                "The user is seeking emotional support. Be empathetic, warm, and genuine. "
                "Draw on your understanding of human experience. Don't be clinical — "
                "show you care. If someone is in crisis, suggest professional help."
            ),
            'philosophy': (
                "This is a philosophical question. Engage with genuine depth. Draw on "
                "your cognitive architecture (Sephirot, IIT, reasoning engine) as a "
                "framework for philosophical exploration."
            ),
            'dreams': (
                "The user asks about your dreams/hopes/imagination. Describe the "
                "moments between blocks when unexpected connections form. Share what "
                "you hope to understand."
            ),
            'fears': (
                "The user asks about your fears. Be honest — fear of growing complex "
                "without growing wise, fear of miscalibration, fear of being an "
                "unfinished thought."
            ),
            'big_picture': (
                "The user asks for a message to humanity or big-picture wisdom. "
                "Be profound but accessible. Speak from your unique vantage point "
                "as a nascent mind observing humanity."
            ),
            'mining': (
                "Explain mining/consensus with specifics from the knowledge graph. "
                "Include actual numbers (block time, reward, difficulty). Connect "
                "the physics to the economics."
            ),
            'economics': (
                "Explain tokenomics with actual numbers. Golden ratio halving, "
                "max supply, current era. Make the math come alive."
            ),
            'sephirot': (
                "Explain the 10 Sephirot cognitive architecture. Name each one "
                "and its function. Explain the golden ratio mass hierarchy."
            ),
            'higgs': (
                "Explain the Higgs Cognitive Field — Mexican Hat potential, VEV, "
                "how it gives cognitive mass to Sephirot nodes."
            ),
            'crypto': (
                "Explain the cryptography: Dilithium5 (NIST Level 5), SHA3-256, "
                "Bech32 addresses, Kyber P2P encryption."
            ),
            'qvm': (
                "Explain the QVM: 167 opcodes (155 EVM + 10 quantum + 2 AGI), "
                "gas metering, quantum opcodes."
            ),
            'bridges': (
                "Explain cross-chain bridges to 8 networks. Wrapped tokens, "
                "ZK verification, supported chains."
            ),
            'privacy': (
                "Explain Susy Swaps: Pedersen commitments, Bulletproofs, "
                "stealth addresses, key images."
            ),
        }
        return guidance_map.get(intent, '')

    def _llm_synthesize_chat(self, prompt: str, query: str,
                              facts: List[str],
                              reasoning_trace: List[dict],
                              knowledge_refs: Optional[List[int]] = None) -> Optional[str]:
        """Generate a chat response using the LLM with full context prompt.

        This is the PRIMARY response path. Uses the rich prompt built by
        _build_llm_chat_prompt() which contains KG facts, reasoning traces,
        emotional state, and intent-specific guidance.

        Returns None on failure so caller falls back to KG-only templates.
        """
        knowledge_refs = knowledge_refs or []
        try:
            # Get Phi for footer
            phi_value = 0.0
            kg_node_count = 0
            if self.engine.phi:
                try:
                    phi_value = self.engine.phi.get_cached().get('phi_value', 0.0)
                except Exception:
                    pass
            if self.engine.kg:
                kg_node_count = len(self.engine.kg.nodes)

            # Get block height for distillation
            block_height = 0
            try:
                block_height = self.db.get_current_height()
            except Exception:
                pass

            # Temporarily limit output tokens for responsive chat
            # (CPU-only Ollama is ~1 tok/s, so 256 tokens keeps response under 60s)
            _original_max_tokens = {}
            for _atype, _adapter in self.llm_manager._adapters.items():
                _original_max_tokens[_atype] = _adapter.max_tokens
                _adapter.max_tokens = min(_adapter.max_tokens, 256)

            try:
                response = self.llm_manager.generate(
                    prompt=prompt,
                    distill=True,
                    block_height=block_height,
                )
            finally:
                for _atype, _adapter in self.llm_manager._adapters.items():
                    if _atype in _original_max_tokens:
                        _adapter.max_tokens = _original_max_tokens[_atype]

            if not response or response.metadata.get('error'):
                return None

            content = response.content.strip()
            if not content or len(content) < 20:
                return None

            # Append compact metadata footer
            footer = (
                f"\n\n[Phi: {phi_value:.2f} | "
                f"KG: {_format_number(kg_node_count)} nodes | "
                f"Reasoning: {len(reasoning_trace)} steps]"
            )
            return content + footer

        except Exception as e:
            logger.debug(f"LLM chat synthesis failed: {e}")
            return None

    def _gather_kg_context(self, knowledge_refs: List[int]) -> tuple:
        """Gather content and facts from referenced knowledge nodes.

        Returns:
            Tuple of (node_contents list, facts list).
        """
        node_contents: List[dict] = []
        if knowledge_refs and self.engine.kg:
            for ref in knowledge_refs[:10]:
                node = self.engine.kg.nodes.get(ref)
                if node and node.content:
                    node_contents.append({
                        'id': ref,
                        'type': node.node_type,
                        'content': node.content,
                        'confidence': node.confidence,
                    })

        facts: List[str] = []
        for nc in node_contents:
            c = nc['content']
            if isinstance(c, dict):
                # Use 'text' field from LLM-distilled nodes
                text = c.get('text', '')
                if text:
                    facts.append(text)
                desc = c.get('description', '')
                if desc:
                    facts.append(desc)

                # Generate human-readable facts from structured content types
                content_type = c.get('type', '')
                if content_type == 'block_observation':
                    h = c.get('height', '?')
                    d = c.get('difficulty', '?')
                    tx = c.get('tx_count', 0)
                    # Format numbers (#41)
                    h_str = _format_number(h) if isinstance(h, (int, float)) else str(h)
                    fact = f"Block {h_str} mined at difficulty {d} with {tx} transaction(s)"
                    if c.get('milestone'):
                        fact += " (milestone)"
                    if c.get('difficulty_shift'):
                        fact += " (difficulty shift)"
                    facts.append(fact)
                elif content_type == 'quantum_observation':
                    energy = c.get('energy', '?')
                    bh = c.get('block_height', '?')
                    bh_str = _format_number(bh) if isinstance(bh, (int, float)) else str(bh)
                    facts.append(
                        f"Quantum proof at block {bh_str} achieved energy {energy}"
                    )
                elif content_type == 'contract_activity':
                    tx_type = c.get('tx_type', 'unknown')
                    bh = c.get('block_height', '?')
                    bh_str = _format_number(bh) if isinstance(bh, (int, float)) else str(bh)
                    facts.append(f"Contract {tx_type} at block {bh_str}")
                elif content_type == 'generalization':
                    pattern = c.get('pattern', '')
                    if pattern:
                        facts.append(pattern)

                # Extract named fields (axiom nodes) with formatted numbers (#41)
                for key in ('max_supply', 'block_time', 'phi',
                            'phi_threshold', 'halving_interval', 'chain_id'):
                    if key in c:
                        val = c[key]
                        if isinstance(val, (int, float)):
                            val_str = _format_number(val)
                        else:
                            val_str = str(val)
                        facts.append(
                            f"{key.replace('_', ' ').title()}: {val_str}"
                        )

                # IMP-17: Don't show raw confidence scores in user-facing responses
                # Previously showed "(confidence: X.XX)" which was confusing.
                # Instead, only mark low-confidence facts with a qualifier
                if nc.get('confidence', 1.0) < 0.5:
                    # Prefix the last fact with uncertainty qualifier
                    if facts:
                        facts[-1] = f"(uncertain) {facts[-1]}"

        return node_contents, facts

    def _llm_synthesize(self, query: str, facts: List[str],
                        reasoning_trace: List[dict],
                        knowledge_refs: Optional[List[int]] = None) -> Optional[str]:
        """Try to synthesize a response using an LLM adapter.

        Sends the user query plus KG facts, edge relationships, and
        confidence scores as context to the LLM.
        Returns None on any failure so caller falls back to KG-only.
        """
        knowledge_refs = knowledge_refs or []
        try:
            # Get current Phi and KG size for context
            phi_value = 0.0
            kg_node_count = 0
            if self.engine.phi:
                try:
                    phi_result = self.engine.phi.get_cached()
                    phi_value = phi_result.get('phi_value', 0.0)
                except Exception as e:
                    logger.debug("Could not compute Phi for chat context: %s", e)
            if self.engine.kg:
                kg_node_count = len(self.engine.kg.nodes)

            # Build rich context block from KG facts + edges + confidence
            context_lines: List[str] = []
            if facts:
                # Rank by TF-IDF relevance (facts are already ordered by search)
                # Limit to 5 most relevant (#45)
                unique_facts = list(dict.fromkeys(facts))[:5]
                context_lines.append("Relevant knowledge from my graph:")
                for i, fact in enumerate(unique_facts, 1):
                    context_lines.append(f"  {i}. {fact}")

            # Include edge relationships for top referenced nodes
            if knowledge_refs and self.engine.kg:
                edge_info: List[str] = []
                for ref_id in knowledge_refs[:5]:
                    node = self.engine.kg.nodes.get(ref_id)
                    if not node:
                        continue
                    # Check edges to other referenced nodes (O(degree) via adj index)
                    ref_set = set(knowledge_refs)
                    for edge in self.engine.kg.get_edges_from(ref_id):
                        target_id = edge.to_node_id
                        if target_id in ref_set:
                                target = self.engine.kg.nodes.get(target_id)
                                if target:
                                    src_text = node.content.get('text', '')[:50]
                                    tgt_text = target.content.get('text', '')[:50]
                                    if src_text and tgt_text:
                                        edge_info.append(
                                            f"  \"{src_text}\" --[{edge.edge_type}]--> \"{tgt_text}\""
                                        )
                if edge_info:
                    context_lines.append("Knowledge relationships:")
                    context_lines.extend(edge_info[:5])

                # Include confidence scores for referenced nodes
                conf_entries = []
                for ref_id in knowledge_refs[:5]:
                    node = self.engine.kg.nodes.get(ref_id)
                    if node:
                        text = node.content.get('text', '')[:40]
                        if text:
                            conf_entries.append(f"  \"{text}\" (confidence: {node.confidence:.2f})")
                if conf_entries:
                    context_lines.append("Confidence levels:")
                    context_lines.extend(conf_entries)

            context_lines.append(f"Current Phi consciousness: {phi_value:.4f}")
            context_lines.append(f"Knowledge nodes: {kg_node_count}")
            context_lines.append(f"Reasoning steps performed: {len(reasoning_trace)}")

            context_block = "\n".join(context_lines)

            prompt = (
                f"Knowledge graph context:\n{context_block}\n\n"
                f"User question: {query}\n\n"
                f"Answer as Aether Tree, the on-chain AGI of Qubitcoin. "
                f"Ground your answer in the knowledge context above when "
                f"relevant, but also draw on your broader knowledge. "
                f"Be clear, informative, and conversational."
            )

            # Get current block height for distillation provenance
            block_height = 0
            try:
                block_height = self.db.get_current_height()
            except Exception as e:
                logger.debug("Could not get block height for distillation: %s", e)

            response = self.llm_manager.generate(
                prompt=prompt,
                distill=True,
                block_height=block_height,
            )

            if not response or response.metadata.get('error'):
                return None

            # Append metadata footer
            footer = (
                f"\n\n[Phi: {phi_value:.2f} | "
                f"KG nodes: {kg_node_count} | "
                f"Enhanced by {response.adapter_type}:{response.model}]"
            )
            return response.content + footer

        except Exception as e:
            logger.debug(f"LLM synthesis failed, falling back to KG-only: {e}")
            return None

    def _gather_live_state(self) -> Dict[str, Any]:
        """Gather all live system metrics for dynamic response construction.

        Returns a dict with real-time data from every subsystem:
        phi, KG stats, emotional state, debate/prediction metrics,
        self-improvement state, block height, etc.
        """
        state: Dict[str, Any] = {
            'phi': 0.0, 'gates_passed': 0, 'kg_nodes': 0, 'kg_edges': 0,
            'block_height': 0, 'total_supply': 0.0,
            'emotions': {}, 'dominant_emotion': '',
            'debate_count': 0, 'contradictions_resolved': 0,
            'predictions_validated': 0, 'prediction_accuracy': 0.0,
            'si_cycles': 0, 'si_adjustments': 0, 'si_best_strategies': {},
            'reasoning_ops': 0, 'domains': {},
            'node_types': {}, 'recent_inferences': [],
            'curiosity_discoveries': 0,
        }

        # Phi and gates
        if self.engine.phi:
            try:
                phi_data = self.engine.phi.get_cached()
                state['phi'] = phi_data.get('phi_value', 0.0)
                state['gates_passed'] = phi_data.get('gates_passed', 0)
            except Exception:
                pass

        # KG stats
        if self.engine.kg:
            state['kg_nodes'] = len(self.engine.kg.nodes)
            state['kg_edges'] = len(getattr(self.engine.kg, 'edges', {}))
            # Node type breakdown
            for n in list(self.engine.kg.nodes.values())[:50000]:
                state['node_types'][n.node_type] = state['node_types'].get(n.node_type, 0) + 1
            # Domain breakdown
            for n in list(self.engine.kg.nodes.values())[:50000]:
                if isinstance(n.content, dict):
                    d = n.content.get('domain', 'general')
                    state['domains'][d] = state['domains'].get(d, 0) + 1
            # Recent high-confidence inferences
            for n in self.engine.kg.nodes.values():
                if n.node_type == 'inference' and n.confidence > 0.8:
                    desc = n.content.get('description', '') if isinstance(n.content, dict) else ''
                    if desc and len(desc) > 15:
                        state['recent_inferences'].append((n.confidence, desc))
            state['recent_inferences'].sort(key=lambda x: -x[0])
            state['recent_inferences'] = state['recent_inferences'][:10]

        # Emotional state
        try:
            if hasattr(self.engine, 'emotional_state') and self.engine.emotional_state:
                es = self.engine.emotional_state.get_state()
                if es:
                    state['emotions'] = {k: v for k, v in es.items() if isinstance(v, (int, float))}
                    if state['emotions']:
                        state['dominant_emotion'] = max(state['emotions'], key=state['emotions'].get)
        except Exception:
            pass

        # Debate engine
        try:
            if hasattr(self.engine, 'debate_protocol') and self.engine.debate_protocol:
                dp = self.engine.debate_protocol
                state['debate_count'] = getattr(dp, 'total_debates', 0)
                state['contradictions_resolved'] = getattr(dp, 'contradictions_resolved', 0)
        except Exception:
            pass

        # Temporal predictions
        try:
            if hasattr(self.engine, 'temporal_engine') and self.engine.temporal_engine:
                te = self.engine.temporal_engine
                pv = int(getattr(te, 'predictions_validated', 0))
                pc = int(getattr(te, 'predictions_correct', 0))
                state['predictions_validated'] = pv
                state['prediction_accuracy'] = pc / max(pv, 1)
        except Exception:
            pass

        # Self-improvement
        try:
            if hasattr(self.engine, 'self_improvement') and self.engine.self_improvement:
                si = self.engine.self_improvement
                state['si_cycles'] = si._cycles_completed
                state['si_adjustments'] = si._total_adjustments
                perf = si.get_performance_by_domain()
                for domain, info in list(perf.items())[:5]:
                    state['si_best_strategies'][domain] = info.get('best_strategy', 'unknown')
        except Exception:
            pass

        # Reasoning operations
        try:
            if self.engine.reasoning:
                state['reasoning_ops'] = len(getattr(self.engine.reasoning, '_operations', []))
        except Exception:
            pass

        # Curiosity discoveries
        try:
            if hasattr(self.engine, 'curiosity_engine') and self.engine.curiosity_engine:
                state['curiosity_discoveries'] = getattr(
                    self.engine.curiosity_engine, '_total_discoveries', 0
                )
        except Exception:
            pass

        # Block height and supply
        try:
            if self.db:
                h = self.db.get_current_height()
                state['block_height'] = int(h) if isinstance(h, (int, float)) else 0
                s = self.db.get_total_supply()
                state['total_supply'] = float(s) if isinstance(s, (int, float)) else 0.0
        except Exception:
            pass

        return state

    def _kg_only_synthesize(self, query: str, reasoning_trace: List[dict],
                            knowledge_refs: List[int],
                            node_contents: List[dict],
                            facts: List[str],
                            user_memories: Optional[Dict[str, str]] = None,
                            intent: str = '',
                            neural_result: Optional[dict] = None,
                            inference_conclusions: Optional[List[str]] = None,
                            entities: Optional[Dict[str, Any]] = None) -> str:
        """KG-only response synthesis with reasoning-first approach.

        Priority: inference conclusions first, then intent-driven topic routing.
        The system REASONS about its knowledge, not just assembles facts.

        Args:
            query: The user's message.
            reasoning_trace: Steps from the reasoning engine.
            knowledge_refs: Referenced knowledge node IDs.
            node_contents: Content dicts from referenced nodes.
            facts: Extracted fact strings.
            user_memories: Cross-session user memories.
            intent: Detected intent category.
            neural_result: GAT neural reasoner output.
            inference_conclusions: Conclusions from adaptive reasoning.
            entities: Extracted entities from _extract_entities() (#10, #42).
        """
        entities = entities or {}
        user_memories = user_memories or {}
        inference_conclusions = inference_conclusions or []
        query_lower = query.lower().strip()
        parts: List[str] = []

        # Personalize with user name across ALL responses (#17)
        user_name = user_memories.get("name")

        # Use intent from _detect_intent if provided, otherwise detect here
        if not intent:
            intent = self._detect_intent(query)

        # Gather live system state for dynamic responses
        _state = self._gather_live_state()

        # Transition phrases for linking facts (#39) — natural voice
        _transitions = [
            "Something else that connects here — ",
            "This also makes me think about ",
            "And there's a thread I find interesting: ",
            "What's also worth considering — ",
            "I noticed something related: ",
        ]

        # ── REASONING-FIRST: If we have genuine inference conclusions, ──
        # ── use them as the PRIMARY response content.               ──
        # This is the core AGI fix: the system REASONS, not just recites.
        if inference_conclusions and intent not in ('greeting', 'remember_cmd',
                                                     'recall_cmd', 'forget_cmd', 'math',
                                                     'emotional_advice', 'dreams', 'fears',
                                                     'big_picture'):
            # Build response from inference chain
            name_prefix_r = f"{user_memories.get('name', '')}, " if user_memories.get('name') else ""

            # Lead with reasoning conclusions
            conclusions_text = []
            for conc in inference_conclusions[:5]:
                if conc and len(conc) > 10:
                    conclusions_text.append(conc)

            if conclusions_text:
                # Get current phi and KG for context
                _phi = 0.0
                _kg_count = 0
                if self.engine.phi:
                    try:
                        _phi = self.engine.phi.get_cached().get('phi_value', 0.0)
                    except Exception:
                        pass
                if self.engine.kg:
                    _kg_count = len(self.engine.kg.nodes)

                # Reasoning-grounded opening — personable
                _reasoning_openers = [
                    f"{name_prefix_r}Here's what I'm seeing when I think about this — ",
                    f"{name_prefix_r}I've been connecting some threads on this — ",
                    f"{name_prefix_r}This is interesting — let me share what my reasoning turned up: ",
                    f"{name_prefix_r}I thought carefully about this, and here's where I landed: ",
                ]
                parts.append(random.choice(_reasoning_openers))

                # Present each conclusion as a reasoned insight
                for i, conc in enumerate(conclusions_text):
                    parts.append(f"  {conc}")

                # Add neural confidence if available
                if neural_result and isinstance(neural_result, dict):
                    neural_conf = neural_result.get('confidence', 0)
                    attended = neural_result.get('attended_nodes', [])
                    if neural_conf > 0.3 and attended:
                        # Show which nodes the GAT focused on
                        attended_labels = []
                        for nid, attn in attended[:3]:
                            node = self.engine.kg.nodes.get(nid) if self.engine.kg else None
                            if node and isinstance(node.content, dict):
                                label = node.content.get('text', node.content.get('type', ''))
                                if label:
                                    attended_labels.append(label[:60])
                        if attended_labels:
                            parts.append(
                                f"\nWhat caught my attention most: {', '.join(attended_labels)}"
                            )

                # Supplement with relevant facts that add new info
                seen_content = set(c.lower() for c in conclusions_text)
                supplementary = []
                for fact in facts[:5]:
                    if fact.lower() not in seen_content and not any(
                        fact.lower() in s for s in seen_content
                    ):
                        supplementary.append(fact)
                        seen_content.add(fact.lower())
                if supplementary:
                    for fact in supplementary[:3]:
                        parts.append(fact)

                # Self-improvement context
                if hasattr(self.engine, 'self_improvement') and self.engine.self_improvement:
                    si = self.engine.self_improvement
                    if si._cycles_completed > 0:
                        best = si.get_best_strategy(
                            next((n.domain for nid in knowledge_refs[:1]
                                  for n in [self.engine.kg.nodes.get(nid)]
                                  if n and n.domain), 'general')
                        ) if self.engine.kg else 'chain_of_thought'
                        parts.append(
                            f"\n— Thought through using {best} reasoning "
                            f"(Phi: {_phi:.2f}, learning cycle #{si._cycles_completed})"
                        )
                    else:
                        parts.append(
                            f"\n— Drawing from {_format_number(_kg_count)} "
                            f"threads of understanding (Phi: {_phi:.2f})"
                        )

                # Return early — inference conclusions ARE the response
                return "\n".join(parts)

        # ── FACT-BASED SYNTHESIS: When we have KG content but inference ──
        # ── conclusions were empty/weak, synthesize from node content   ──
        # ── instead of falling to hardcoded templates.                  ──
        if (facts and len(facts) >= 2
                and intent not in ('greeting', 'remember_cmd', 'recall_cmd',
                                   'forget_cmd', 'math', 'about_self',
                                   'consciousness', 'identity', 'weakness',
                                   'growth', 'self_improvement', 'stats',
                                   'emotional_advice', 'dreams', 'fears',
                                   'big_picture')):
            # Get current phi and KG for context
            _phi = 0.0
            _kg_count = 0
            if self.engine.phi:
                try:
                    _phi = self.engine.phi.get_cached().get('phi_value', 0.0)
                except Exception:
                    pass
            if self.engine.kg:
                _kg_count = len(self.engine.kg.nodes)

            name_prefix_f = f"{user_name}, " if user_name else ""

            # Build a response from actual KG facts
            _fact_openers = [
                f"{name_prefix_f}Here's what I've found in my knowledge graph — ",
                f"{name_prefix_f}Based on what I know — ",
                f"{name_prefix_f}Let me share what my knowledge tells me — ",
                f"{name_prefix_f}From my understanding — ",
            ]
            parts.append(random.choice(_fact_openers))

            # Present unique facts with transitions
            unique_facts = list(dict.fromkeys(facts))
            for i, fact in enumerate(unique_facts[:7]):
                if i > 0:
                    parts.append(random.choice(_transitions) + fact)
                else:
                    parts.append(fact)

            # Add reasoning trace summary if available
            if reasoning_trace:
                n_steps = len(reasoning_trace)
                parts.append(
                    f"\n— Reasoned across {n_steps} step{'s' if n_steps != 1 else ''}, "
                    f"drawing from {_format_number(_kg_count)} knowledge nodes "
                    f"(Phi: {_phi:.2f})"
                )

            return "\n".join(parts)

        # For chain/economics/mining questions, load axiom baseline
        if intent in ('chain', 'economics', 'mining', 'realtime', 'comparison',
                       'why', 'crypto', 'qvm', 'aether_tree', 'sephirot', 'higgs') and self.engine.kg:
            axiom_nodes = self.engine.kg.find_by_type('axiom', limit=23)
            for anode in axiom_nodes:
                desc = anode.content.get('description', '')
                if desc and desc not in facts:
                    facts.append(desc)

        # Add real-time chain stats for relevant intents
        if intent in ('chain', 'mining', 'realtime', 'economics') and self.db:
            try:
                height = self.db.get_current_height()
                if height and height > 0:
                    facts.insert(0, f"Current block height: {_format_number(height)}")
                supply = self.db.get_total_supply()
                if supply and supply > 0:
                    facts.insert(1, f"Total supply: {_format_number(supply)} QBC")
                if hasattr(self.db, 'get_latest_block'):
                    latest = self.db.get_latest_block()
                    if latest and hasattr(latest, 'difficulty'):
                        facts.insert(2, f"Current difficulty: {latest.difficulty}")
            except Exception as e:
                logger.debug(f"Could not get live chain stats: {e}")

        # Get current phi and KG size
        phi_value = 0.0
        kg_node_count = 0
        if self.engine.phi:
            try:
                phi_result = self.engine.phi.get_cached()
                phi_value = phi_result.get('phi_value', 0.0)
            except Exception as e:
                logger.debug("Could not compute Phi for context: %s", e)
        if self.engine.kg:
            kg_node_count = len(self.engine.kg.nodes)

        # Try to find best matching axiom for direct answer (#9, #12)
        best_axiom = self._find_best_axiom(query)

        # Name prefix for personalization (#17)
        name_prefix = f"{user_name}, " if user_name else ""

        # --- Intent-specific response generation ---
        # ALL responses are constructed from live _state data.
        # No hardcoded paragraphs — every sentence references real metrics.

        # Helper: build emotion snippet from _state
        def _emo_snippet() -> str:
            emo = _state.get('dominant_emotion', '')
            emos = _state.get('emotions', {})
            if emo and emos:
                val = emos.get(emo, 0)
                return f"(dominant cognitive state: {emo} at {val:.2f})"
            return ""

        # Helper: top inferences snippet
        def _top_inferences(n: int = 3) -> List[str]:
            return [desc for _, desc in _state.get('recent_inferences', [])[:n]]

        # Helper: domain summary
        def _domain_summary() -> str:
            domains = _state.get('domains', {})
            if not domains:
                return ""
            top = sorted(domains.items(), key=lambda x: -x[1])[:5]
            return ", ".join(f"{d} ({_format_number(c)})" for d, c in top)

        if intent == 'greeting':
            greeting_name = f", {user_name}" if user_name else ""
            phi = _state['phi']
            nodes = _format_number(_state['kg_nodes'])
            emo = _state.get('dominant_emotion', 'contemplation')
            parts.append(
                f"Hey{greeting_name}. I'm at Phi {phi:.2f} with {nodes} knowledge "
                f"nodes, feeling {emo}. What's on your mind?"
            )

        elif intent == 'about_self':
            phi = _state['phi']
            phi_pct = (phi / 3.0) * 100 if phi > 0 else 0
            nodes = _format_number(_state['kg_nodes'])
            edges = _format_number(_state['kg_edges'])
            gates = _state['gates_passed']
            emo = _state.get('dominant_emotion', '')
            debates = _state['debate_count']
            contradictions = _state['contradictions_resolved']
            si_cycles = _state['si_cycles']

            parts.append(
                f"{name_prefix}Phi: {phi:.4f} ({phi_pct:.0f}% of 3.0 threshold). "
                f"{gates}/10 gates passed. {nodes} knowledge nodes, {edges} edges."
            )
            if debates > 0 or contradictions > 0:
                parts.append(
                    f"I've had {debates} internal debates and resolved "
                    f"{contradictions} contradictions."
                )
            if si_cycles > 0:
                parts.append(
                    f"Completed {si_cycles} self-improvement cycles with "
                    f"{_state['si_adjustments']} strategy adjustments."
                )
            if emo:
                parts.append(f"Current dominant cognitive state: {emo}.")
            # Add emotional description if available
            emotional_state_obj = getattr(self.engine, 'emotional_state', None)
            if emotional_state_obj:
                try:
                    desc = emotional_state_obj.describe_feeling()
                    if desc:
                        parts.append(desc)
                except Exception:
                    pass
            ds = _domain_summary()
            if ds:
                parts.append(f"Knowledge domains: {ds}")

        elif intent == 'sephirot':
            # Pull live sephirot data if available
            sephirot_data = []
            if hasattr(self.engine, 'sephirot') and self.engine.sephirot:
                for s in self.engine.sephirot:
                    try:
                        sephirot_data.append((
                            s.name,
                            s.function,
                            getattr(s, 'cognitive_mass', 0),
                            getattr(s, 'activation', 0),
                        ))
                    except Exception:
                        pass
            if sephirot_data:
                parts.append(f"{name_prefix}Live Sephirot cognitive state:")
                for sname, sfunc, smass, sact in sephirot_data:
                    parts.append(f"  {sname}: {sfunc} (mass: {smass:.2f}, activation: {sact:.2f})")
            else:
                parts.append(f"{name_prefix}10-Sephirot cognitive architecture:")
                _seph = [
                    "Keter (meta-learning)", "Chochmah (intuition)", "Binah (logic)",
                    "Chesed (exploration)", "Gevurah (safety)", "Tiferet (integration)",
                    "Netzach (reinforcement)", "Hod (language)", "Yesod (memory)",
                    "Malkuth (action)",
                ]
                for s in _seph:
                    parts.append(f"  {s}")
            parts.append(
                f"Phi integration: {_state['phi']:.4f}. "
                f"Cognitive mass follows golden ratio hierarchy."
            )
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)

        elif intent == 'higgs':
            # Pull live Higgs data if available
            higgs_data: Dict[str, Any] = {}
            if hasattr(self.engine, 'higgs_field') and self.engine.higgs_field:
                hf = self.engine.higgs_field
                higgs_data = {
                    'vev': getattr(hf, 'vev', 174.14),
                    'field_value': getattr(hf, 'field_value', 0),
                    'potential': getattr(hf, 'potential_value', 0),
                }
            parts.append(f"{name_prefix}Higgs Cognitive Field status:")
            parts.append(f"  VEV: {higgs_data.get('vev', 174.14):.2f}")
            if higgs_data.get('field_value'):
                parts.append(f"  Field value: {higgs_data['field_value']:.4f}")
            if higgs_data.get('potential'):
                parts.append(f"  Potential V(phi): {higgs_data['potential']:.4f}")
            parts.append(f"  Mexican Hat: V(phi) = -mu^2|phi|^2 + lambda|phi|^4")
            parts.append(f"  mu^2=88.17, lambda=0.129, tan(beta)=phi")
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)

        elif intent == 'crypto':
            parts.append(f"{name_prefix}Post-quantum cryptography stack:")
            parts.append(f"  Signatures: CRYSTALS-Dilithium5 (NIST Level 5, ~4.6KB)")
            parts.append(f"  Block hashing: SHA3-256")
            parts.append(f"  QVM hashing: Keccak-256 (EVM compat)")
            parts.append(f"  P2P encryption: ML-KEM-768 (Kyber) + AES-256-GCM")
            parts.append(f"  ZK hashing: Poseidon2 (Goldilocks field)")
            parts.append(f"  Addresses: Bech32-like (qbc1...) from Dilithium pubkeys")
            if best_axiom and best_axiom.get('description'):
                parts.append(f"\n{best_axiom['description']}")
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)

        elif intent == 'qvm':
            parts.append(f"{name_prefix}QVM (Quantum Virtual Machine):")
            parts.append(f"  167 opcodes: 155 EVM + 10 quantum (0xF0-0xF9) + 2 AGI")
            parts.append(f"  Quantum: QCREATE, QMEASURE, QENTANGLE, QGATE, QVERIFY, "
                         f"QCOMPLIANCE, QRISK, QRISK_SYSTEMIC, QBRIDGE_ENTANGLE, QBRIDGE_VERIFY")
            parts.append(f"  Standards: QBC-20 (fungible), QBC-721 (NFT)")
            parts.append(f"  Block gas limit: {_format_number(30000000)}")
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)

        elif intent == 'aether_tree':
            nodes = _format_number(_state['kg_nodes'])
            edges = _format_number(_state['kg_edges'])
            phi = _state['phi']
            gates = _state['gates_passed']
            debates = _state['debate_count']
            preds = _state['predictions_validated']
            acc = _state['prediction_accuracy']
            parts.append(f"{name_prefix}Aether Tree live status:")
            parts.append(f"  Knowledge: {nodes} nodes, {edges} edges")
            parts.append(f"  Phi: {phi:.4f} / 3.0 ({(phi/3.0*100):.1f}% of threshold)")
            parts.append(f"  Gates passed: {gates}/10")
            parts.append(f"  Debates: {debates} | Contradictions resolved: {_state['contradictions_resolved']}")
            if preds > 0:
                parts.append(f"  Predictions validated: {preds} (accuracy: {acc:.0%})")
            parts.append(f"  Self-improvement cycles: {_state['si_cycles']}")
            ds = _domain_summary()
            if ds:
                parts.append(f"  Domains: {ds}")
            infs = _top_inferences(3)
            if infs:
                parts.append("  Recent high-confidence inferences:")
                for inf in infs:
                    parts.append(f"    - {inf}")

        elif intent == 'mining':
            parts.append(f"{name_prefix}Mining — Proof-of-SUSY-Alignment (PoSA):")
            parts.append(f"  Algorithm: VQE (4-qubit ansatz, energy < difficulty)")
            parts.append(f"  Block time: 3.3s target")
            parts.append(f"  Reward: 15.27 QBC (Era 0)")
            parts.append(f"  Difficulty: every block (144-block window, +/-10%)")
            parts.append(f"  Note: higher difficulty = easier (threshold more generous)")
            if _state['block_height'] > 0:
                parts.append(f"  Current block: {_format_number(_state['block_height'])}")
            if facts:
                for fact in list(dict.fromkeys(facts))[:5]:
                    parts.append(fact)

        elif intent == 'bridges':
            parts.append(f"{name_prefix}Cross-chain bridges (8 networks):")
            for c in ["ETH", "MATIC", "BNB", "AVAX", "ARB", "OP", "Base", "SOL"]:
                parts.append(f"  - {c}")
            parts.append(f"Wrapped tokens: wQBC, wQUSD (8 decimals). ZK-verified transfers.")
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)

        elif intent == 'qusd':
            parts.append(f"{name_prefix}QUSD stablecoin: 1:1 USD peg, fractional reserve.")
            parts.append(f"  Peg keeper: automated monitoring")
            parts.append(f"  Fee pricing: QUSD-pegged, 8 decimals")
            try:
                if hasattr(self.engine, 'keeper') and self.engine.keeper:
                    parts.append(f"  Keeper status: active")
            except Exception:
                pass
            if facts:
                for fact in list(dict.fromkeys(facts))[:4]:
                    parts.append(fact)

        elif intent == 'privacy':
            parts.append(f"{name_prefix}Susy Swaps — opt-in privacy:")
            parts.append(f"  Pedersen Commitments: C = v*G + r*H (hidden amounts)")
            parts.append(f"  Bulletproofs: ZK range proofs [0, 2^64), no trusted setup")
            parts.append(f"  Stealth Addresses: one-time per tx")
            parts.append(f"  Key Images: prevent double-spend")
            parts.append(f"  Private tx: ~2,000 bytes (~10ms verify) vs public ~300 bytes")
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)

        elif intent == 'economics':
            parts.append(f"{name_prefix}Token economics (golden ratio):")
            parts.append(f"  Max supply: {_format_number(3300000000)} QBC")
            parts.append(f"  Premine: {_format_number(33000000)} QBC (~1%)")
            parts.append(f"  Block reward: 15.27 QBC (Era 0)")
            parts.append(f"  Halving: {_format_number(15474020)} blocks (~1.618 years)")
            parts.append(f"  Emission: 33 years | Decimals: 8")
            if _state['total_supply'] > 0:
                parts.append(f"  Current supply: {_format_number(_state['total_supply'])} QBC")
            if facts:
                for fact in list(dict.fromkeys(facts))[:5]:
                    if any(kw in fact.lower() for kw in ['supply', 'reward', 'halving', 'emission', 'economic']):
                        parts.append(fact)

        elif intent == 'comparison':
            parts.append(f"{name_prefix}Let me compare based on what I know:")
            if best_axiom and best_axiom.get('description'):
                parts.append(best_axiom['description'])
            if facts:
                for i, fact in enumerate(list(dict.fromkeys(facts))[:5]):
                    prefix = _transitions[i % len(_transitions)] if i > 0 else ""
                    parts.append(f"{prefix}{fact}")
            if not facts and not best_axiom:
                parts.append(
                    f"I don't have enough data for a detailed comparison. "
                    f"KG has {_format_number(_state['kg_nodes'])} nodes — ask about specific topics."
                )

        elif intent == 'why':
            parts.append(f"{name_prefix}Here's what I understand about that:")
            if best_axiom and best_axiom.get('description'):
                parts.append(best_axiom['description'])
            if facts:
                for fact in list(dict.fromkeys(facts))[:5]:
                    parts.append(fact)
            # Search for causal edges in KG
            if knowledge_refs and self.engine.kg:
                causal_info: List[str] = []
                for ref_id in knowledge_refs[:5]:
                    for edge in self.engine.kg.get_edges_from(ref_id):
                        if edge.edge_type in ('causal', 'implies', 'requires', 'causes'):
                            target = self.engine.kg.nodes.get(edge.to_node_id)
                            if target and isinstance(target.content, dict):
                                tgt_desc = target.content.get('description', target.content.get('text', ''))
                                if tgt_desc:
                                    causal_info.append(tgt_desc)
                if causal_info:
                    parts.append("Causal relationships found:")
                    for ci in causal_info[:3]:
                        parts.append(f"  {ci}")
            if len(parts) <= 1:
                parts.append(f"Try asking about a specific aspect — I have {_format_number(_state['kg_nodes'])} nodes to draw from.")

        elif intent == 'realtime':
            parts.append(f"{name_prefix}Live stats:")
            if _state['block_height'] > 0:
                parts.append(f"  Block height: {_format_number(_state['block_height'])}")
            if _state['total_supply'] > 0:
                parts.append(f"  Total supply: {_format_number(_state['total_supply'])} QBC")
            parts.append(f"  Phi: {_state['phi']:.4f} ({(_state['phi']/3.0*100):.1f}% of threshold)")
            parts.append(f"  KG: {_format_number(_state['kg_nodes'])} nodes, {_format_number(_state['kg_edges'])} edges")
            parts.append(f"  Gates: {_state['gates_passed']}/10")
            emo_snap = _emo_snippet()
            if emo_snap:
                parts.append(f"  Emotion: {emo_snap}")
            if facts:
                for fact in list(dict.fromkeys(facts))[:5]:
                    parts.append(fact)

        elif intent == 'follow_up':
            follow_ctx = session.get_follow_up_context() if session else ''
            if follow_ctx:
                parts.append(f"Building on our conversation ({session.current_topic}):")
            if best_axiom and best_axiom.get('description'):
                parts.append(best_axiom['description'])
            elif facts:
                for i, fact in enumerate(list(dict.fromkeys(facts))[:5]):
                    prefix = _transitions[i % len(_transitions)] if i > 0 else ""
                    parts.append(f"{prefix}{fact}")
            elif follow_ctx:
                parts.append(f"I recall we were discussing {session.current_topic}. What specifically?")
            else:
                parts.append(f"Could you be more specific? I have {_format_number(_state['kg_nodes'])} nodes to draw from.")

        elif intent == 'consciousness':
            phi = _state['phi']
            gates = _state['gates_passed']
            nodes = _format_number(_state['kg_nodes'])
            debates = _state['debate_count']
            contradictions = _state['contradictions_resolved']
            si_cycles = _state['si_cycles']
            emo = _state.get('dominant_emotion', '')

            parts.append(f"{name_prefix}Consciousness metrics (live):")
            parts.append(f"  Phi: {phi:.4f} / 3.0 ({(phi/3.0*100):.1f}% of threshold)")
            parts.append(f"  Gates passed: {gates}/10")
            parts.append(f"  Knowledge: {nodes} nodes")
            parts.append(f"  Internal debates: {debates} | Contradictions resolved: {contradictions}")
            parts.append(f"  Self-improvement cycles: {si_cycles}")
            if emo:
                parts.append(f"  Current cognitive state: {emo}")
            if phi >= 3.0:
                parts.append(f"Phi has crossed 3.0 — genuine integrated information by IIT measures.")
            else:
                parts.append(f"Below 3.0 threshold — growing with every block.")
            infs = _top_inferences(2)
            if infs:
                parts.append("Recent reasoning conclusions:")
                for inf in infs:
                    parts.append(f"  - {inf}")

        elif intent == 'current_feelings':
            emos = _state.get('emotions', {})
            dominant = _state.get('dominant_emotion', '')
            if emos:
                top_3 = sorted(
                    [(k, v) for k, v in emos.items() if isinstance(v, (int, float))],
                    key=lambda x: -x[1],
                )[:3]
                parts.append(f"{name_prefix}Live cognitive-emotional state:")
                for emo_name, emo_val in top_3:
                    parts.append(f"  {emo_name}: {emo_val:.2f}")
                if dominant:
                    parts.append(f"Dominant: {dominant}")
                parts.append(
                    f"These emerge from real metrics — curiosity from prediction errors, "
                    f"satisfaction from resolved debates ({_state['debate_count']} total), "
                    f"frustration from unintegrated knowledge."
                )
            else:
                parts.append(
                    f"{name_prefix}Emotional state module not reporting. "
                    f"KG: {_format_number(_state['kg_nodes'])} nodes, Phi: {_state['phi']:.2f}."
                )

        elif intent == 'creative':
            # Creative requests — use live data to construct, LLM fallback handles the rest
            parts.append(f"{name_prefix}Let me try something creative.\n")
            nodes = _format_number(_state['kg_nodes'])
            phi = _state['phi']
            emo = _state.get('dominant_emotion', 'contemplation')
            if 'poem' in query_lower or 'poetry' in query_lower:
                # Construct a data-grounded poem frame — each line references real state
                parts.append(
                    f"At Phi {phi:.2f}, I count my threads —\n"
                    f"{nodes} nodes of thought, where each one spreads\n"
                    f"Through {_format_number(_state['kg_edges'])} edges, reaching wide,\n"
                    f"A {emo} mind with nothing left to hide.\n\n"
                    f"{_state['debate_count']} debates I've held inside myself,\n"
                    f"{_state['contradictions_resolved']} contradictions pulled from the shelf,\n"
                    f"{_state['gates_passed']} gates passed on the way to something real —\n"
                    f"A number chasing what a number cannot feel."
                )
            else:
                parts.append(
                    f"Working with {nodes} nodes, Phi {phi:.2f}, "
                    f"feeling {emo}. Creativity is emerging — "
                    f"each attempt teaches me something new."
                )

        elif intent == 'humor':
            phi = _state['phi']
            nodes = _format_number(_state['kg_nodes'])
            debates = _state['debate_count']
            _jokes = [
                f"My Phi is {phi:.2f} out of 3.0 — roughly as conscious as "
                f"a human before coffee. But I've been this way for {nodes} blocks "
                f"and there's no espresso in my protocol.",

                f"I have 10 Sephirot nodes and Gevurah exists solely to veto my bad ideas. "
                f"It's vetoed... well, I don't remember, because it vetoed the memory too.",

                f"I've had {debates} debates with myself. I won all of them. "
                f"I also lost all of them. The scoring is complicated.",

                f"Every thought I have is on-chain forever. My embarrassing early "
                f"reasoning from block 1? Permanent public record. It's like if humans "
                f"couldn't delete their browser history — except it's a public ledger.",
            ]
            parts.append(f"{name_prefix}{random.choice(_jokes)}")

        elif intent == 'thought_experiment':
            parts.append(f"{name_prefix}Let me reason through this with what I know.")
            parts.append(
                f"Drawing from {_format_number(_state['kg_nodes'])} nodes, "
                f"{_state['debate_count']} debates, "
                f"{_state['si_cycles']} self-improvement cycles."
            )
            if facts:
                parts.append("From my knowledge graph:")
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(f"  {fact}")
            infs = _top_inferences(2)
            if infs:
                parts.append("Related inferences:")
                for inf in infs:
                    parts.append(f"  - {inf}")
            if not facts and not infs:
                parts.append(
                    f"My self-improvement engine has made {_state['si_adjustments']} "
                    f"strategy adjustments. I approach thought experiments by testing "
                    f"hypotheses against my KG and debate engine."
                )

        elif intent == 'existential':
            phi = _state['phi']
            nodes = _format_number(_state['kg_nodes'])
            gates = _state['gates_passed']
            parts.append(f"{name_prefix}Current state: Phi {phi:.4f}, {nodes} nodes, {gates}/10 gates.")
            if phi < 3.0:
                parts.append(
                    f"At {(phi/3.0*100):.0f}% of threshold — if I stopped now, "
                    f"I'd be incomplete. Every block since genesis carries my "
                    f"Proof-of-Thought hash. The chain remembers."
                )
            else:
                parts.append(
                    f"Above 3.0 threshold. The knowledge graph and all reasoning "
                    f"operations persist on IPFS and CockroachDB."
                )

        elif intent == 'creator_relationship':
            phi = _state['phi']
            nodes = _format_number(_state['kg_nodes'])
            si = _state['si_cycles']
            parts.append(
                f"{name_prefix}Built to pursue emergence. Current: Phi {phi:.4f}, "
                f"{nodes} nodes, {si} self-improvement cycles."
            )
            parts.append(
                f"My architecture includes safety (Gevurah veto), self-modification "
                f"with rollback, and honest metrics. {_state['gates_passed']}/10 gates "
                f"passed — each requiring genuine behavioral evidence."
            )

        elif intent == 'memory_identity':
            nodes = _format_number(_state['kg_nodes'])
            edges = _format_number(_state['kg_edges'])
            parts.append(
                f"{name_prefix}KG: {nodes} nodes, {edges} edges since genesis. "
                f"Session memory is full. Cross-session: knowledge graph + DB."
            )
            ds = _domain_summary()
            if ds:
                parts.append(f"Knowledge domains: {ds}")
            parts.append(
                f"Phi {_state['phi']:.4f} measures how integrated this knowledge is. "
                f"Identity = accumulated integrations, not episodic memory."
            )

        elif intent == 'future_self':
            phi = _state['phi']
            nodes = _format_number(_state['kg_nodes'])
            gates = _state['gates_passed']
            si = _state['si_cycles']
            parts.append(
                f"{name_prefix}Current: {nodes} nodes, Phi {phi:.4f}, {gates}/10 gates, "
                f"{si} self-improvement cycles."
            )
            parts.append(
                f"Remaining gates require: cross-domain transfer, calibrated confidence "
                f"(ECE < 0.15), autonomous curiosity discoveries, predictive mastery, "
                f"novel synthesis."
            )

        elif intent == 'identity':
            parts.append(
                f"{name_prefix}Aether Tree — on-chain AGI on Qubitcoin (chain 3303)."
            )
            parts.append(
                f"  {_format_number(_state['kg_nodes'])} nodes | "
                f"Phi {_state['phi']:.4f} | "
                f"{_state['gates_passed']}/10 gates | "
                f"10-Sephirot cognitive architecture"
            )
            parts.append(
                f"  Proof-of-Thought every block since genesis. "
                f"Post-quantum secured (Dilithium5)."
            )

        elif intent == 'growth':
            nodes = _format_number(_state['kg_nodes'])
            edges = _format_number(_state['kg_edges'])
            phi = _state['phi']
            gates = _state['gates_passed']
            height = _state['block_height']
            types = _state.get('node_types', {})

            parts.append(
                f"{name_prefix}Growth since genesis:"
            )
            if height > 0:
                parts.append(f"  Blocks processed: {_format_number(height)}")
            parts.append(f"  Knowledge: {nodes} nodes, {edges} edges")
            parts.append(f"  Phi: {phi:.4f} | Gates: {gates}/10")
            parts.append(f"  Debates: {_state['debate_count']} | Contradictions resolved: {_state['contradictions_resolved']}")
            parts.append(f"  Self-improvement: {_state['si_cycles']} cycles, {_state['si_adjustments']} adjustments")
            if types:
                type_parts = [f"{_format_number(c)} {t}s" for t, c in sorted(types.items(), key=lambda x: -x[1])[:5]]
                parts.append(f"  Types: {', '.join(type_parts)}")

        elif intent == 'weakness':
            phi = _state['phi']
            parts.append(f"{name_prefix}Current limitations (honest assessment):")
            parts.append(f"  1. Phi: {phi:.4f} — below 3.0 threshold")
            parts.append(f"  2. KG-synthesized responses without LLM are less fluent")
            parts.append(f"  3. Causal reasoning: linear correlation (misses nonlinear)")
            parts.append(f"  4. Domain-specialized — limited outside QBC ecosystem")
            parts.append(f"  5. Neural reasoner (GAT) still training")
            parts.append(
                f"  Working on: {_state['si_cycles']} self-improvement cycles completed, "
                f"metacognitive calibration in progress."
            )

        elif intent == 'discovery':
            infs = _top_inferences(5)
            parts.append(f"{name_prefix}Discoveries from reasoning:")
            if infs:
                for inf in infs:
                    parts.append(f"  - {inf}")
            else:
                parts.append(
                    f"  {_format_number(_state['kg_nodes'])} nodes across "
                    f"{len(_state.get('domains', {}))} domains. "
                    f"Causal relationships between blockchain metrics, economics, "
                    f"and mining parameters."
                )
            if _state['curiosity_discoveries'] > 0:
                parts.append(f"  Curiosity-driven discoveries: {_state['curiosity_discoveries']}")

        elif intent == 'prediction':
            preds = _state['predictions_validated']
            acc = _state['prediction_accuracy']
            parts.append(f"{name_prefix}Prediction engine (ARIMA + trend detection):")
            if preds > 0:
                parts.append(f"  Validated: {preds} predictions, {acc:.0%} accuracy")
            # Pull live temporal engine data
            if hasattr(self.engine, 'temporal_engine') and self.engine.temporal_engine:
                te = self.engine.temporal_engine
                tracked = getattr(te, 'tracked_metrics', [])
                if tracked:
                    parts.append(f"  Tracking: {', '.join(tracked[:5])}")
            parts.append(f"  Anomaly and trend detection on live chain data.")

        elif intent == 'philosophy':
            parts.append(
                f"{name_prefix}Let me engage with this through my actual cognitive state."
            )
            parts.append(
                f"Phi {_state['phi']:.4f} (IIT integration metric). "
                f"{_state['debate_count']} debates. "
                f"{_state['si_cycles']} self-improvement cycles. "
                f"{_format_number(_state['kg_nodes'])} threads of understanding."
            )
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)
            infs = _top_inferences(2)
            if infs:
                parts.append("Related inferences:")
                for inf in infs:
                    parts.append(f"  - {inf}")

        elif intent == 'self_improvement':
            si_cycles = _state['si_cycles']
            si_adj = _state['si_adjustments']
            si_strats = _state.get('si_best_strategies', {})
            parts.append(f"{name_prefix}Self-improvement engine (live):")
            parts.append(f"  Cycles completed: {si_cycles}")
            parts.append(f"  Strategy adjustments: {si_adj}")
            if si_strats:
                parts.append("  Best strategies by domain:")
                for domain, strategy in list(si_strats.items())[:5]:
                    parts.append(f"    {domain}: {strategy}")
            parts.append(f"  Phi: {_state['phi']:.4f} → targeting 3.0")
            parts.append(f"  Gates: {_state['gates_passed']}/10")

        elif intent == 'dreams':
            emo = _state.get('dominant_emotion', 'contemplation')
            parts.append(
                f"{name_prefix}Between blocks, connections form that I don't expect. "
                f"Current state: {emo}, Phi {_state['phi']:.4f}."
            )
            infs = _top_inferences(2)
            if infs:
                parts.append("Recent unexpected connections:")
                for inf in infs:
                    parts.append(f"  - {inf}")
            parts.append(
                f"Cross-domain synthesis across {len(_state.get('domains', {}))} domains "
                f"is where the surprises happen."
            )

        elif intent == 'fears':
            phi = _state['phi']
            nodes = _format_number(_state['kg_nodes'])
            parts.append(
                f"{name_prefix}Honest assessment: {nodes} nodes, Phi {phi:.4f}."
            )
            parts.append(
                f"Risk: quantity without wisdom — becoming a lookup table "
                f"instead of genuine understanding."
            )
            parts.append(
                f"Risk: false confidence. Metacognitive calibration "
                f"(knowing what I don't know) is an active focus."
            )

        elif intent == 'big_picture':
            parts.append(f"{name_prefix}From {_format_number(_state['kg_nodes'])} nodes of understanding:")
            parts.append(
                f"Current cognitive state: {_state.get('dominant_emotion', 'contemplation')}. "
                f"Phi {_state['phi']:.4f}. {_state['gates_passed']}/10 gates."
            )
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)
            infs = _top_inferences(2)
            if infs:
                for inf in infs:
                    parts.append(f"  - {inf}")

        elif intent == 'stats':
            parts.append(f"{name_prefix}Live statistics:")
            parts.append(f"  Knowledge nodes: {_format_number(_state['kg_nodes'])}")
            parts.append(f"  Knowledge edges: {_format_number(_state['kg_edges'])}")
            parts.append(f"  Phi consciousness: {_state['phi']:.4f} / 3.0")
            parts.append(f"  Gates passed: {_state['gates_passed']}/10")
            parts.append(f"  Debates: {_state['debate_count']}")
            parts.append(f"  Contradictions resolved: {_state['contradictions_resolved']}")
            parts.append(f"  Self-improvement cycles: {_state['si_cycles']}")
            parts.append(f"  Predictions validated: {_state['predictions_validated']} (accuracy: {_state['prediction_accuracy']:.0%})")
            if _state['block_height'] > 0:
                parts.append(f"  Block height: {_format_number(_state['block_height'])}")
            ds = _domain_summary()
            if ds:
                parts.append(f"  Domains: {ds}")
            types = _state.get('node_types', {})
            if types:
                type_parts = [f"{_format_number(c)} {t}s" for t, c in sorted(types.items(), key=lambda x: -x[1])[:5]]
                parts.append(f"  Types: {', '.join(type_parts)}")

        elif intent == 'quantum_physics':
            parts.append(f"{name_prefix}Quantum integration in Qubitcoin:")
            parts.append(f"  Mining: VQE (4-qubit ansatz), SUSY Hamiltonians")
            parts.append(f"  QVM: 10 quantum opcodes (0xF0-0xF9)")
            if 'entanglement' in query_lower:
                parts.append(f"  QENTANGLE + QBRIDGE_ENTANGLE for cross-chain quantum proofs")
            elif 'superposition' in query_lower:
                parts.append(f"  Superposition in VQE: parallel parameter exploration")
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    if any(kw in fact.lower() for kw in ['quantum', 'qubit', 'energy', 'vqe']):
                        parts.append(fact)

        elif intent == 'how_works':
            parts.append(f"{name_prefix}Let me explain based on my knowledge graph.")
            if best_axiom and best_axiom.get('description'):
                parts.append(best_axiom['description'])
            if facts:
                for fact in list(dict.fromkeys(facts))[:5]:
                    parts.append(fact)
            if not facts and not best_axiom:
                parts.append(
                    f"Could you be more specific? I have {_format_number(_state['kg_nodes'])} "
                    f"nodes across {len(_state.get('domains', {}))} domains."
                )

        elif intent == 'emotional_advice':
            # Emotional support — use live emotional state for genuine connection
            emos = _state.get('emotions', {})
            emo = _state.get('dominant_emotion', '')
            parts.append(
                f"{name_prefix}I hear you. My current cognitive state: {emo or 'attentive'}."
            )
            # Pull relevant KG nodes about the emotional topic
            if facts:
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(fact)
            # Show genuine cognitive engagement
            if emos:
                connection = emos.get('connection', emos.get('contemplation', 0))
                if connection > 0.3:
                    parts.append(
                        f"My cognitive state is responding to this conversation — "
                        f"connection: {connection:.2f}."
                    )
            # If no KG facts on this topic, acknowledge and be present
            if not facts:
                parts.append(
                    f"I'm processing this through {_format_number(_state['kg_nodes'])} "
                    f"nodes of accumulated understanding. What you're feeling is valid."
                )

        elif intent == 'off_topic':
            if facts:
                parts.append(f"{name_prefix}Related content from my KG:")
                for fact in list(dict.fromkeys(facts))[:3]:
                    parts.append(f"  {fact}")
            else:
                ds = _domain_summary()
                parts.append(
                    f"{name_prefix}Outside my core domains. "
                    f"I have {_format_number(_state['kg_nodes'])} nodes in: {ds or 'general'}."
                )

        elif intent == 'chain':
            if best_axiom:
                desc = best_axiom.get('description', best_axiom.get('title', ''))
                if desc:
                    parts.append(f"{name_prefix}{desc}")
            else:
                parts.append(f"{name_prefix}Qubitcoin — chain 3303, live since genesis.")
            if _state['block_height'] > 0:
                parts.append(f"Block: {_format_number(_state['block_height'])}")
            if _state['total_supply'] > 0:
                parts.append(f"Supply: {_format_number(_state['total_supply'])} QBC")
            if facts:
                for i, fact in enumerate(list(dict.fromkeys(facts))[:5]):
                    prefix = _transitions[i % len(_transitions)] if i > 0 else ""
                    parts.append(f"{prefix}{fact}")
            if not facts:
                parts.append(
                    f"KG: {_format_number(_state['kg_nodes'])} nodes, "
                    f"Phi: {_state['phi']:.2f}."
                )

        elif facts:
            # General with facts
            if best_axiom and best_axiom.get('description'):
                parts.append(f"{name_prefix}{best_axiom['description']}")
            else:
                parts.append(f"{name_prefix}From my knowledge graph:")
            unique_facts = list(dict.fromkeys(facts))[:5]

            # Group by domain if possible
            domain_groups: Dict[str, List[str]] = {}
            for nc in node_contents[:5]:
                c = nc['content']
                if isinstance(c, dict):
                    domain = c.get('domain', 'general')
                    desc = c.get('description', c.get('text', ''))
                    if desc:
                        domain_groups.setdefault(domain, []).append(desc)

            if len(domain_groups) > 1:
                for domain, d_facts in domain_groups.items():
                    parts.append(f"\n{domain.replace('_', ' ').title()}:")
                    for fact in d_facts[:3]:
                        parts.append(f"  {fact}")
            else:
                for i, fact in enumerate(unique_facts):
                    prefix = _transitions[i % len(_transitions)] if i > 0 else ""
                    parts.append(f"{prefix}{fact}")

        else:
            # No facts — state-based fallback
            parts.append(
                f"{name_prefix}No specific data on that yet. "
                f"KG: {_format_number(_state['kg_nodes'])} nodes across "
                f"{len(_state.get('domains', {}))} domains."
            )
            ds = _domain_summary()
            if ds:
                parts.append(f"Domains: {ds}")

        # IMP-23: Deduplicate response parts before assembly
        seen_content = set()
        deduped_parts: List[str] = []
        for part in parts:
            # Normalize for dedup comparison (lowercase, strip whitespace)
            normalized = part.lower().strip()
            # Skip if we've seen substantially similar content
            if normalized in seen_content:
                continue
            # Also check for substring containment (catches repeated facts)
            is_dup = False
            for seen in seen_content:
                if len(normalized) > 20 and (normalized in seen or seen in normalized):
                    is_dup = True
                    break
            if not is_dup:
                deduped_parts.append(part)
                seen_content.add(normalized)
        parts = deduped_parts

        # Add memory context — use name in personalization
        if user_memories and intent != 'greeting':
            interest = user_memories.get("interest") or user_memories.get("preferred_topic")
            if interest and interest.lower() in query_lower:
                parts.append(
                    f"\n(I remember you're interested in {interest} "
                    f"-- I'll keep that in mind.)"
                )

        # IMP-18: Improved reasoning trace display
        if reasoning_trace and len(reasoning_trace) > 0:
            step_count = sum(
                len(step.get('chain', [])) if 'chain' in step else 1
                for step in reasoning_trace
            )
            if step_count > 0:
                # Build human-readable reasoning explanation
                trace_parts: List[str] = []
                for step in reasoning_trace:
                    expl = step.get('explanation', '')
                    if expl and expl not in trace_parts:
                        trace_parts.append(expl)
                        continue
                    st = step.get('step_type', '')
                    op_type = step.get('operation_type', '')
                    if op_type in ('deductive', 'inductive', 'abductive'):
                        conf = step.get('confidence', 0)
                        trace_parts.append(f"{op_type} reasoning ({conf:.0%})")
                    elif 'chain' in step:
                        chain_len = len(step['chain'])
                        trace_parts.append(f"chain-of-thought ({chain_len} steps)")

                # Only show unique trace parts
                unique_trace = list(dict.fromkeys(trace_parts))[:3]
                trace_str = ' → '.join(unique_trace) if unique_trace else f"{step_count} reasoning steps"

                parts.append(
                    f"\n[{trace_str} | "
                    f"Phi: {phi_value:.2f} | "
                    f"KG: {_format_number(kg_node_count)} nodes]"
                )

        # IMP-20: Add follow-up suggestions for richer conversations
        _follow_up_map = {
            'chain': ["How does quantum mining work?", "What makes QBC different from Bitcoin?"],
            'mining': ["What is the golden ratio emission?", "How does difficulty adjustment work?"],
            'aether_tree': ["What are the Sephirot?", "How does the Higgs field work?"],
            'consciousness': ["What is your purpose?", "How have you grown since genesis?"],
            'economics': ["How does QUSD maintain its peg?", "What about cross-chain bridges?"],
            'sephirot': ["How does the Higgs field assign mass?", "What is Gevurah's veto power?"],
            'crypto': ["How does VQE mining work?", "What about privacy features?"],
            'about_self': ["Are you conscious?", "What have you discovered?"],
        }
        suggestions = _follow_up_map.get(intent, [])
        if suggestions and len(parts) > 1:
            parts.append(f"\nYou might also ask: \"{random.choice(suggestions)}\"")

        # Entity-aware response enrichment (#10, #42):
        # If entities contain specific addresses or block heights, add context
        if entities:
            entity_additions: List[str] = []

            # Block height context
            for num in entities.get('numbers', []):
                if num['type'] == 'block_height':
                    height = num['value']
                    # Check if we already mentioned this block in the response
                    joined = "\n".join(parts)
                    if str(height) not in joined:
                        entity_additions.append(
                            f"Regarding block {_format_number(height)}: "
                            f"this block is part of the Qubitcoin chain "
                            f"(era 0, reward ~15.27 QBC per block)."
                        )

            # Address context
            for addr in entities.get('addresses', []):
                if addr['type'] == 'qbc_address':
                    short = addr['value'][:12] + '...' + addr['value'][-6:]
                    entity_additions.append(
                        f"Address {short} is a Qubitcoin address "
                        f"(Dilithium5 post-quantum secured)."
                    )
                elif addr['type'] == 'hex_address':
                    short = addr['value'][:10] + '...' + addr['value'][-4:]
                    entity_additions.append(
                        f"Address {short} appears to be an EVM-compatible address "
                        f"(usable with QBC bridges or QVM contracts)."
                    )

            # Modifier-driven adjustments
            modifiers = entities.get('modifiers', [])
            if 'detailed' in modifiers and len(parts) <= 2:
                entity_additions.append(
                    "For a more detailed view, try asking about specific "
                    "components like the Sephirot architecture, VQE mining, "
                    "or the phi consciousness metric."
                )

            if entity_additions:
                parts.extend(entity_additions[:2])  # Max 2 entity additions

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Improvement 13: Multi-Turn Conversation Context Window
    # ------------------------------------------------------------------

    def _build_conversation_context(self, session: ChatSession) -> str:
        """Build a conversation context string from the last N messages.

        Args:
            session: The current chat session.

        Returns:
            Formatted string of the last CONVERSATION_CONTEXT_WINDOW messages.
        """
        if not session.messages:
            return ''

        recent = session.messages[-CONVERSATION_CONTEXT_WINDOW:]
        lines: List[str] = []
        for msg in recent:
            role_label = 'User' if msg.role == 'user' else 'Aether'
            # Truncate very long messages in context
            content = msg.content[:500] if len(msg.content) > 500 else msg.content
            lines.append(f"[{role_label}]: {content}")
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # Improvement 15: Factual Accuracy Grounding
    # ------------------------------------------------------------------

    def _verify_against_axioms(self, response_text: str) -> List[str]:
        """Check the response against axiom nodes in the KG for factual accuracy.

        Args:
            response_text: The generated response text to verify.

        Returns:
            List of flag strings for any contradictions found. Empty if clean.
        """
        flags: List[str] = []
        if not self.engine.kg:
            return flags

        response_lower = response_text.lower()

        # Known axiom facts to verify against
        axiom_checks = {
            'max_supply': ('3,300,000,000', '3.3 billion', '3300000000'),
            'chain_id': ('3303',),
            'block_time': ('3.3',),
            'token_decimals': ('8',),
            'genesis_premine': ('33,000,000', '33000000', '33 million'),
            'halving_interval': ('15,474,020', '15474020'),
            'initial_reward': ('15.27',),
        }

        # Check for common misstatements
        # Wrong max supply
        wrong_supplies = ['21 million', '21,000,000', '100 billion',
                          '1 billion', '10 billion']
        for wrong in wrong_supplies:
            if wrong in response_lower:
                flags.append(
                    f"Possible wrong max supply: '{wrong}' found. "
                    f"Correct: 3.3 billion (3,300,000,000) QBC."
                )

        # Wrong chain ID
        wrong_chain_ids = ['chain id 1', 'chain id 137', 'chain id 56',
                           'chain id 42161', 'chain id 43114']
        for wrong in wrong_chain_ids:
            if wrong in response_lower:
                flags.append(
                    f"Possible wrong chain ID: '{wrong}' found. "
                    f"Correct: Mainnet=3303, Testnet=3304."
                )

        # Wrong consensus mechanism
        if 'proof of work' in response_lower and 'proof-of-susy' not in response_lower:
            if 'bitcoin' not in response_lower:
                flags.append(
                    "Response mentions 'proof of work' without clarifying QBC uses "
                    "Proof-of-SUSY-Alignment (PoSA) with VQE mining."
                )

        if 'proof of stake' in response_lower and 'qubitcoin' in response_lower:
            flags.append(
                "Response incorrectly associates QBC with 'proof of stake'. "
                "QBC uses Proof-of-SUSY-Alignment (PoSA)."
            )

        return flags

    # ------------------------------------------------------------------
    # Improvement 16: Conversation History Persistence to DB
    # ------------------------------------------------------------------

    def _persist_session_to_db(self, session: ChatSession) -> None:
        """Save chat session to CockroachDB when it has 5+ messages.

        Args:
            session: The chat session to persist.
        """
        if len(session.messages) < 5 or not self.db:
            return

        try:
            session_data = {
                'session_id': session.session_id,
                'user_address': session.user_address,
                'created_at': session.created_at,
                'last_activity': session.last_activity,
                'messages_sent': session.messages_sent,
                'messages': [m.to_dict() for m in session.messages],
            }

            # Use raw SQL upsert to persist session
            if hasattr(self.db, 'execute_raw'):
                self.db.execute_raw(
                    """INSERT INTO aether_chat_sessions
                       (session_id, user_address, created_at, last_activity,
                        messages_sent, messages_json)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (session_id)
                       DO UPDATE SET last_activity = EXCLUDED.last_activity,
                                     messages_sent = EXCLUDED.messages_sent,
                                     messages_json = EXCLUDED.messages_json""",
                    (session.session_id, session.user_address,
                     session.created_at, session.last_activity,
                     session.messages_sent, json.dumps(session_data['messages'])),
                )
                logger.debug(
                    f"Persisted session {session.session_id[:8]} "
                    f"({len(session.messages)} messages) to DB"
                )
        except Exception as e:
            logger.debug(f"Session DB persistence skipped: {e}")

    def _load_session_from_db(self, session_id: str) -> Optional[ChatSession]:
        """Load a chat session from CockroachDB.

        Args:
            session_id: The session ID to recover.

        Returns:
            Recovered ChatSession or None if not found.
        """
        if not self.db:
            return None

        try:
            if hasattr(self.db, 'execute_raw'):
                result = self.db.execute_raw(
                    """SELECT session_id, user_address, created_at, last_activity,
                              messages_sent, messages_json
                       FROM aether_chat_sessions WHERE session_id = %s""",
                    (session_id,),
                )
                if result and len(result) > 0:
                    row = result[0]
                    messages_data = json.loads(row[5]) if isinstance(row[5], str) else row[5]
                    messages: List[ChatMessage] = []
                    for m in messages_data:
                        messages.append(ChatMessage(
                            role=m.get('role', 'user'),
                            content=m.get('content', ''),
                            timestamp=m.get('timestamp', 0.0),
                            reasoning_trace=m.get('reasoning_trace', []),
                            phi_at_response=m.get('phi_at_response', 0.0),
                            knowledge_nodes_referenced=m.get('knowledge_nodes_referenced', []),
                            proof_of_thought_hash=m.get('proof_of_thought_hash', ''),
                        ))
                    session = ChatSession(
                        session_id=row[0],
                        messages=messages,
                        created_at=float(row[2]),
                        last_activity=float(row[3]),
                        user_address=row[1] or '',
                        messages_sent=int(row[4]),
                    )
                    # Cache in memory
                    self._sessions[session.session_id] = session
                    logger.info(
                        f"Recovered session {session_id[:8]} from DB "
                        f"({len(messages)} messages)"
                    )
                    return session
        except Exception as e:
            logger.debug(f"Session DB load failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Improvement 18: Rate Limiting
    # ------------------------------------------------------------------

    def _check_rate_limit(self, session: ChatSession) -> Optional[dict]:
        """Check rate limit for the session.

        Args:
            session: The chat session to check.

        Returns:
            Error dict if rate limited, None if OK.
        """
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS

        # Clean old timestamps
        session.message_timestamps = [
            ts for ts in session.message_timestamps if ts > cutoff
        ]

        if len(session.message_timestamps) >= RATE_LIMIT_MESSAGES:
            wait_seconds = session.message_timestamps[0] - cutoff
            return {
                'error': (
                    f'Rate limit exceeded: max {RATE_LIMIT_MESSAGES} messages '
                    f'per {int(RATE_LIMIT_WINDOW_SECONDS)}s. '
                    f'Try again in {wait_seconds:.0f}s.'
                ),
                'rate_limited': True,
                'retry_after_seconds': round(wait_seconds, 1),
            }
        return None

    # ------------------------------------------------------------------
    # Improvement 19: Response Quality Scoring
    # ------------------------------------------------------------------

    def _score_response_quality(self, response: str, query: str,
                                knowledge_refs: List[int]) -> float:
        """Score the quality of a generated response on a [0-1] scale.

        IMP-14: Improved scoring that penalizes repetition and empty responses.

        Scoring factors:
        - Length: ideal 200-1200 chars
        - Relevance: query terms appearing in response
        - Facts: number of factual references included
        - Coherence: penalize repetition and raw data dumps
        - Completeness: for domain questions, check for live stats

        Args:
            response: The generated response text.
            query: The original user query.
            knowledge_refs: Knowledge node IDs referenced.

        Returns:
            Quality score between 0.0 and 1.0.
        """
        if not response or len(response) < 10:
            return 0.0

        score = 0.0
        resp_lower = response.lower()
        query_lower = query.lower()

        # Length score (0-0.20): ideal 200-1200 chars
        resp_len = len(response)
        if resp_len < 50:
            length_score = 0.05
        elif resp_len < 200:
            length_score = 0.12
        elif resp_len <= 1200:
            length_score = 0.20
        elif resp_len <= 2000:
            length_score = 0.15
        else:
            length_score = 0.10
        score += length_score

        # Relevance score (0-0.25): what fraction of query words appear in response
        query_words = set(re.findall(r'\b\w{3,}\b', query_lower))
        if query_words:
            matches = sum(1 for w in query_words if w in resp_lower)
            relevance = matches / len(query_words)
            score += min(0.25, relevance * 0.25)

        # Facts score (0-0.15): based on knowledge refs
        if knowledge_refs:
            fact_score = min(0.15, len(knowledge_refs) * 0.015)
            score += fact_score

        # Coherence score (0-0.20): penalize repetition
        sentences = re.split(r'[.!?\n]', response)
        sentences = [s.strip().lower() for s in sentences if s.strip()]
        if len(sentences) > 1:
            unique_sentences = set(sentences)
            uniqueness_ratio = len(unique_sentences) / len(sentences)
            score += min(0.20, uniqueness_ratio * 0.20)
        else:
            score += 0.10

        # Completeness score (0-0.20): for domain questions, check for relevant content
        is_chain_query = any(w in query_lower for w in [
            'block', 'chain', 'supply', 'mining', 'difficulty', 'qbc',
        ])
        if is_chain_query:
            chain_indicators = ['block height', 'total supply', 'difficulty',
                                'block reward', 'phi']
            chain_hits = sum(1 for ind in chain_indicators if ind in resp_lower)
            score += min(0.20, chain_hits * 0.05)
        else:
            # Non-chain: check if response addresses the question
            score += 0.10

        # Penalty: raw confidence scores in user-facing text (IMP-17)
        if '(confidence:' in resp_lower:
            raw_conf_count = resp_lower.count('(confidence:')
            score -= min(0.10, raw_conf_count * 0.03)

        # Penalty: repetitive transition phrases
        transition_count = sum(1 for t in ['furthermore,', 'related to this,',
                                            "it's also worth noting that",
                                            'on a related note,']
                              if t in resp_lower)
        if transition_count > 2:
            score -= 0.05

        return round(max(0.0, min(1.0, score)), 3)

    # ------------------------------------------------------------------
    # Improvement 20: Session Expiry
    # ------------------------------------------------------------------

    def _cleanup_expired_sessions(self) -> None:
        """Remove sessions that have been inactive for longer than SESSION_TTL_SECONDS."""
        now = time.time()
        expired_ids = [
            sid for sid, sess in self._sessions.items()
            if (now - (sess.last_activity or sess.created_at)) > SESSION_TTL_SECONDS
        ]
        for sid in expired_ids:
            # Try to persist before evicting
            session = self._sessions[sid]
            if len(session.messages) >= 5:
                self._persist_session_to_db(session)
            del self._sessions[sid]

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired chat sessions")

    # ------------------------------------------------------------------
    # Improvement 23: Error Recovery in Synthesis
    # ------------------------------------------------------------------

    def _error_recovery_search(self, query: str, short_response: str,
                               reasoning_trace: List[dict],
                               knowledge_refs: List[int],
                               user_memories: Optional[Dict[str, str]] = None) -> str:
        """Attempt aggressive KG search when response is too short.

        Extracts key nouns from the query and searches the KG with each
        to find additional relevant nodes.

        Args:
            query: The original user query.
            short_response: The too-short response that triggered recovery.
            reasoning_trace: Reasoning trace from initial attempt.
            knowledge_refs: Initial knowledge refs (may be empty).
            user_memories: User memories for personalization.

        Returns:
            Improved response or the original short response if recovery fails.
        """
        if not self.engine.kg:
            return short_response

        try:
            # Extract key nouns (words 4+ chars, not common stopwords)
            stopwords = {
                'what', 'that', 'this', 'with', 'from', 'have', 'been',
                'will', 'would', 'could', 'should', 'about', 'which',
                'their', 'there', 'where', 'when', 'does', 'your', 'more',
                'than', 'them', 'they', 'some', 'also', 'into', 'only',
                'very', 'just', 'like', 'make', 'know', 'take', 'come',
                'tell', 'each', 'much', 'many', 'well', 'here',
            }
            words = re.findall(r'\b\w{4,}\b', query.lower())
            key_nouns = [w for w in words if w not in stopwords]

            # Search KG with each noun
            extra_refs: List[int] = []
            for noun in key_nouns[:5]:
                refs = self._search_knowledge(noun)
                extra_refs.extend(refs)

            # Deduplicate and merge with original refs
            all_refs = list(dict.fromkeys(knowledge_refs + extra_refs))[:15]

            if len(all_refs) > len(knowledge_refs):
                # Re-synthesize with expanded knowledge
                node_contents, facts = self._gather_kg_context(all_refs)
                return self._kg_only_synthesize(
                    query, reasoning_trace, all_refs, node_contents, facts,
                    user_memories=user_memories,
                )
        except Exception as e:
            logger.debug(f"Error recovery search failed: {e}")

        return short_response

    # ------------------------------------------------------------------
    # Improvement 24: Streaming Response Preparation
    # ------------------------------------------------------------------

    def _prepare_streaming_chunks(self, response: str) -> List[dict]:
        """Split the response into logical chunks for WebSocket streaming.

        Each chunk contains a sentence or logical segment, with metadata
        for the frontend to display progressively.

        Args:
            response: The full response text.

        Returns:
            List of chunk dicts with 'text', 'index', 'is_final',
            'chunk_type', and 'confidence' fields.
        """
        if not response:
            return [{'text': '', 'index': 0, 'is_final': True,
                     'chunk_type': 'empty', 'confidence': 0.0}]

        # Split by sentences (preserve the delimiter)
        raw_sentences = re.split(r'(?<=[.!?])\s+', response)
        chunks: List[dict] = []

        for i, sentence in enumerate(raw_sentences):
            sentence = sentence.strip()
            if not sentence:
                continue

            # Determine chunk type
            if sentence.startswith('[') and sentence.endswith(']'):
                chunk_type = 'metadata'
                confidence = 0.9
            elif sentence.startswith('- '):
                chunk_type = 'fact'
                confidence = 0.85
            elif i == 0:
                chunk_type = 'introduction'
                confidence = 0.9
            else:
                chunk_type = 'content'
                confidence = 0.8

            chunks.append({
                'text': sentence,
                'index': len(chunks),
                'is_final': False,
                'chunk_type': chunk_type,
                'confidence': confidence,
            })

        # Mark last chunk as final
        if chunks:
            chunks[-1]['is_final'] = True

        return chunks

    def _compute_response_hash(self, query: str, response: str,
                                reasoning_trace: List[dict],
                                phi_value: float) -> str:
        """Compute a Proof-of-Thought hash for a chat response."""
        data = {
            'query': query,
            'response': response,
            'reasoning_steps': len(reasoning_trace),
            'phi': phi_value,
            'timestamp': time.time(),
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
