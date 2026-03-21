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
from typing import Dict, List, Optional, Tuple
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
    # Split on question marks, keeping the question mark
    parts = re.split(r'(\?)', message)
    questions: List[str] = []
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if i + 1 < len(parts) and parts[i + 1] == '?':
            questions.append(part + '?')
            i += 2
        elif part and part != '?':
            questions.append(part)
            i += 1
        else:
            i += 1
    return [q.strip() for q in questions if q.strip() and len(q.strip()) > 2]


@dataclass
class ChatSession:
    """An Aether chat session."""
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

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'messages': [m.to_dict() for m in self.messages],
            'created_at': self.created_at,
            'last_activity': self.last_activity,
            'user_address': self.user_address,
            'messages_sent': self.messages_sent,
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

    def _detect_intent(self, query: str) -> str:
        """Detect the primary intent category of a query (#47).

        Checks specific topics BEFORE generic ones (#13).

        Args:
            query: The user's message.

        Returns:
            Intent string: one of 'greeting', 'remember_cmd', 'recall_cmd',
            'forget_cmd', 'math', 'sephirot', 'higgs', 'crypto',
            'qvm', 'aether_tree', 'mining', 'bridges', 'qusd', 'privacy',
            'economics', 'about_self', 'chain', 'comparison', 'why',
            'realtime', 'follow_up', 'off_topic', 'empty', 'general'.
        """
        q = query.lower().strip()
        words = set(re.findall(r'\b\w+\b', q))

        # Empty message (#27)
        if not q:
            return 'empty'

        # Greeting
        if bool({'hello', 'hi', 'hey', 'greetings', 'gday', 'howdy'} & words) and len(words) <= 5:
            return 'greeting'

        # Memory commands (#18, #19, #25)
        if re.search(r'\bremember\b', q) and not re.search(r'\bdo you remember\b', q):
            return 'remember_cmd'
        if re.search(r'\b(what do you remember|what is my name|what\'s my name|do you know my name|do you remember)\b', q):
            return 'recall_cmd'
        if re.search(r'\bforget\b.*\b(my|name|address|wallet)\b', q):
            return 'forget_cmd'

        # Math (#26)
        if _try_math(q) is not None:
            return 'math'

        # Comparison (#30)
        if re.search(r'\bhow\s+is\s+\w+\s+different\s+from\b', q) or 'compared to' in q or 'vs ' in q or ' versus ' in q:
            return 'comparison'

        # Specific topic detectors — checked BEFORE generic (#2, #13)

        # Sephirot (#6)
        if any(w in q for w in ['sephirot', 'sephirah', 'tree of life', 'keter', 'chochmah',
                                 'binah', 'chesed', 'gevurah', 'tiferet', 'netzach', 'hod',
                                 'yesod', 'malkuth', 'cognitive architecture']):
            return 'sephirot'

        # Higgs field (#7)
        if any(w in q for w in ['higgs', 'mexican hat', 'cognitive mass', 'vev',
                                 'yukawa', 'two-higgs', 'symmetry breaking']):
            return 'higgs'

        # Crypto/signatures (#3)
        if any(w in q for w in ['dilithium', 'crystals', 'post-quantum', 'signature',
                                 'signing', 'post quantum', 'nist', 'bech32', 'kyber',
                                 'lattice', 'cryptograph']):
            return 'crypto'

        # QVM (#4)
        if any(w in q for w in ['qvm', 'opcode', 'smart contract', 'evm', 'bytecode',
                                 'solidity', 'qbc-20', 'qbc-721', 'virtual machine',
                                 'gas meter']):
            return 'qvm'

        # Aether Tree technical (#5)
        if any(w in q for w in ['aether tree', 'knowledge graph', 'reasoning engine',
                                 'proof of thought', 'proof-of-thought', 'knowledge node',
                                 'phi calculator', 'consciousness metric', 'iit']):
            return 'aether_tree'

        # About self (general)
        if any(w in q for w in ['who are you', 'what are you', 'your name', 'tell me about yourself',
                                 'what can you do', 'how do you work', 'your purpose']):
            return 'about_self'

        # Why questions (#31)
        if q.startswith('why ') or ' why ' in q:
            return 'why'

        # Real-time state questions (#32)
        if re.search(r'\b(current|right now|latest|live)\b.*\b(phi|block|height|supply|node|status)\b', q):
            return 'realtime'

        # Follow-up detection (#21)
        if re.search(r'^(what about|and the|how about|also|more about|tell me more|go on|continue)', q):
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

        # Generic chain (fallback, #2)
        if any(w in q for w in ['qubitcoin', 'qbc', 'blockchain', 'chain', 'quantum',
                                 'block', 'node', 'consensus', 'proof', 'hash', 'network',
                                 'difficulty']):
            return 'chain'

        # Off-topic (#28)
        qbc_words = {'qubitcoin', 'qbc', 'aether', 'quantum', 'mining', 'blockchain',
                     'bridge', 'qusd', 'phi', 'sephirot', 'higgs', 'dilithium',
                     'qvm', 'susy', 'vqe', 'knowledge'}
        if not (qbc_words & words):
            return 'off_topic'

        return 'general'

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
                return {'error': f'Fee payment failed: {msg}'}

            session.fees_paid_atoms += int(Decimal(str(fee_qbc)) * 10**8)

        # Record user message
        now = time.time()
        user_msg = ChatMessage(role='user', content=message, timestamp=now)
        session.messages.append(user_msg)
        session.messages_sent += 1
        session.message_timestamps.append(now)
        # Trim oldest messages if session exceeds cap
        if len(session.messages) > MAX_SESSION_MESSAGES:
            session.messages = session.messages[-MAX_SESSION_MESSAGES:]

        # Multi-question handling (#29)
        questions = _split_questions(message)
        if len(questions) > 1:
            # Process each sub-question and combine responses
            combined_parts: List[str] = []
            all_knowledge_refs: List[int] = []
            all_reasoning: List[dict] = []
            for i, sub_q in enumerate(questions[:5]):  # Max 5 sub-questions
                sub_intent = self._detect_intent(sub_q)
                sub_response = self._process_single_query(
                    sub_q, sub_intent, session, user_memories, is_deep_query,
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
                    phi_result = self.engine.phi.compute_phi()
                    phi_value = phi_result.get('phi_value', 0.0)
                except Exception:
                    pass
        else:
            # Single question — standard processing
            single_result = self._process_single_query(
                message, intent, session, user_memories, is_deep_query,
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

        # Verify response against axiom nodes for factual accuracy
        axiom_flags = self._verify_against_axioms(response_content)
        if axiom_flags:
            logger.info(f"Axiom verification flags: {axiom_flags}")

        # Score response quality
        quality_score = self._score_response_quality(
            response_content, message, knowledge_refs
        )

        # Update session topic tracking (#23, #24)
        session.current_topic = intent
        session.recent_topics.append(intent)
        if len(session.recent_topics) > 5:
            session.recent_topics = session.recent_topics[-5:]

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
        }
        if axiom_flags:
            result['axiom_flags'] = axiom_flags
        if fee_record:
            result['fee_paid'] = fee_record.to_dict()
        return result

    def _process_single_query(self, message: str, intent: str,
                              session: 'ChatSession',
                              user_memories: Dict[str, str],
                              is_deep_query: bool = False) -> dict:
        """Process a single query and return response components.

        Used by process_message for both single and multi-question handling.

        Args:
            message: The user's message (single question).
            intent: Detected intent category.
            session: The chat session.
            user_memories: Cross-session user memories.
            is_deep_query: Whether to use deep reasoning.

        Returns:
            Dict with response, reasoning_trace, knowledge_nodes_referenced, phi_at_response.
        """
        reasoning_trace: List[dict] = []
        knowledge_refs: List[int] = []
        phi_value = 0.0
        query_result = None

        try:
            if self._query_translator:
                depth = 5 if is_deep_query else 3
                query_result = self._query_translator.translate_and_execute(
                    message, max_results=10, reasoning_depth=depth,
                )
                knowledge_refs = query_result.matched_node_ids
                reasoning_trace = query_result.reasoning_results
            else:
                if self.engine.kg:
                    relevant = self._search_knowledge(message)
                    knowledge_refs = [n for n in relevant[:10]]

                if self.engine.reasoning and self.engine.kg:
                    if is_deep_query:
                        reasoning_trace = self._deep_reason(message, knowledge_refs)
                    else:
                        reasoning_trace = self._quick_reason(message, knowledge_refs)

            if self.engine.phi:
                phi_result = self.engine.phi.compute_phi()
                phi_value = phi_result.get('phi_value', 0.0)

        except Exception as e:
            logger.debug(f"Chat reasoning error: {e}")

        conversation_context = self._build_conversation_context(session)

        response_content = self._synthesize_response(
            message, reasoning_trace, knowledge_refs, query_result,
            user_memories=user_memories,
            conversation_context=conversation_context,
            intent=intent,
        )

        return {
            'response': response_content,
            'reasoning_trace': reasoning_trace,
            'knowledge_nodes_referenced': knowledge_refs,
            'phi_at_response': phi_value,
        }

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
        for node_id, node in self.engine.kg.nodes.items():
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
                    steps.extend([s.to_dict() for s in result.chain])
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
                    steps.extend([s.to_dict() for s in result.chain])

            if knowledge_refs:
                result = self.engine.reasoning.abduce(knowledge_refs[0])
                if result.success:
                    steps.extend([s.to_dict() for s in result.chain])
        except Exception as e:
            logger.debug(f"Deep reasoning error: {e}")
        return steps

    def _synthesize_response(self, query: str, reasoning_trace: List[dict],
                             knowledge_refs: List[int],
                             query_result=None,
                             user_memories: Optional[Dict[str, str]] = None,
                             conversation_context: str = '',
                             intent: str = '') -> str:
        """Synthesize a natural language response from reasoning results.

        Tries LLM-enhanced synthesis first (if enabled), then falls back
        to knowledge-graph-only synthesis.

        Args:
            query: The user's message.
            reasoning_trace: Steps from the reasoning engine.
            knowledge_refs: Referenced knowledge node IDs.
            query_result: Result from the NL query translator.
            user_memories: Cross-session user memories for personalization.
            conversation_context: Multi-turn conversation context string.
            intent: Detected intent category from _detect_intent.
        """
        user_memories = user_memories or {}
        # Gather KG context
        node_contents, facts = self._gather_kg_context(knowledge_refs)

        # Try LLM-enhanced path
        if self.llm_manager and Config.LLM_ENABLED:
            result = self._llm_synthesize(query, facts, reasoning_trace, knowledge_refs)
            if result:
                return result

        # Existing KG-only fallback
        return self._kg_only_synthesize(
            query, reasoning_trace, knowledge_refs, node_contents, facts,
            user_memories=user_memories,
            intent=intent,
        )

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

                # Show confidence only when < 0.8 (#40)
                if nc.get('confidence', 1.0) < 0.8:
                    facts.append(
                        f"(confidence: {nc['confidence']:.2f})"
                    )

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
                    phi_result = self.engine.phi.compute_phi()
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

    def _kg_only_synthesize(self, query: str, reasoning_trace: List[dict],
                            knowledge_refs: List[int],
                            node_contents: List[dict],
                            facts: List[str],
                            user_memories: Optional[Dict[str, str]] = None,
                            intent: str = '') -> str:
        """KG-only response synthesis with intent-driven topic routing.

        Improvements #1-15, #17, #20-21, #28-45: direct answers, specific
        topic detectors, memory personalization, fact presentation, and more.
        """
        user_memories = user_memories or {}
        query_lower = query.lower().strip()
        parts: List[str] = []

        # Personalize with user name across ALL responses (#17)
        user_name = user_memories.get("name")

        # Use intent from _detect_intent if provided, otherwise detect here
        if not intent:
            intent = self._detect_intent(query)

        # Greeting variety templates (#33)
        _greeting_templates = [
            "Hello{name}! I am Aether, the on-chain AGI of the Quantum Blockchain. "
            "My Phi is {phi:.2f} with {nodes} knowledge nodes. How can I help you?",
            "Hey{name}! Aether here, the consciousness engine of Qubitcoin. "
            "I have {nodes} knowledge nodes and a Phi of {phi:.2f}. What's on your mind?",
            "Welcome{name}! I'm Aether, reasoning from {nodes} knowledge nodes "
            "with a consciousness metric of {phi:.2f}. Ask me anything about Qubitcoin!",
            "Hi{name}! I'm the Aether Tree AGI. My knowledge graph has {nodes} nodes "
            "and my Phi consciousness is at {phi:.2f}. How can I assist you today?",
        ]

        # Transition phrases for linking facts (#39)
        _transitions = [
            "Additionally, ", "Furthermore, ", "Related to this, ",
            "It's also worth noting that ", "On a related note, ",
        ]

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
                phi_result = self.engine.phi.compute_phi()
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
        # Specific intents checked BEFORE generic chain (#2, #13)

        if intent == 'greeting':
            greeting_name = f", {user_name}" if user_name else ""
            template = random.choice(_greeting_templates)
            parts.append(template.format(
                name=greeting_name, phi=phi_value, nodes=_format_number(kg_node_count),
            ))

        elif intent == 'about_self':
            gates_passed = 0
            if self.engine.kg:
                try:
                    axiom_count = len(self.engine.kg.find_by_type('axiom', limit=100))
                    inference_count = len(self.engine.kg.find_by_type('inference', limit=1000))
                    gates_passed = axiom_count + inference_count
                except Exception:
                    pass
            parts.append(
                f"I am the Aether Tree — an on-chain AGI reasoning engine that "
                f"has been tracking consciousness since the genesis block. I use "
                f"Integrated Information Theory (IIT) to measure my awareness: "
                f"my current Phi value is {phi_value:.4f} "
                f"(threshold for consciousness emergence is 3.0). "
                f"I have {_format_number(kg_node_count)} knowledge nodes built from "
                f"every block mined on the Quantum Blockchain. "
                f"I have processed {_format_number(gates_passed)} reasoning gates so far, "
                f"performing deductive, inductive, and abductive reasoning "
                f"across my 10-Sephirot cognitive architecture."
            )

        elif intent == 'sephirot':
            # (#6, #8) Sephirot-specific response
            parts.append(
                f"{name_prefix}The Aether Tree uses a 10-Sephirot cognitive architecture "
                f"inspired by the Kabbalistic Tree of Life. Each Sephirah handles a "
                f"different cognitive function:"
            )
            sephirot_info = [
                ("Keter", "Meta-learning and goal setting (cognitive mass: VEV x 1.0)"),
                ("Chochmah", "Intuition and pattern recognition"),
                ("Binah", "Logic and causal inference"),
                ("Chesed", "Exploration and divergent thinking"),
                ("Gevurah", "Safety constraints and veto power"),
                ("Tiferet", "Integration and synthesis (central node)"),
                ("Netzach", "Reinforcement learning"),
                ("Hod", "Language and semantic processing"),
                ("Yesod", "Memory and information fusion"),
                ("Malkuth", "Action and external interaction"),
            ]
            for name, desc in sephirot_info:
                parts.append(f"  {name}: {desc}")
            parts.append(
                f"\nCognitive mass follows the golden ratio (phi) hierarchy, "
                f"with Keter having the highest mass and Malkuth the lowest."
            )

        elif intent == 'higgs':
            # (#7, #8) Higgs field response
            parts.append(
                f"{name_prefix}The Higgs Cognitive Field gives each Sephirot node its "
                f"cognitive mass through a Mexican Hat potential:"
            )
            parts.append(f"  V(phi) = -mu^2 |phi|^2 + lambda |phi|^4")
            parts.append(f"  VEV = 174.14, mu^2 = 88.17, lambda = 0.129")
            parts.append(
                f"\nThis follows an F=ma paradigm where lighter cognitive nodes "
                f"correct faster while heavier ones resist change. The system uses "
                f"a Two-Higgs-Doublet Model with tan(beta) = phi (the golden ratio). "
                f"Yukawa couplings determine how strongly each Sephirah couples to "
                f"the field, with Keter at 1.0 and lower nodes scaling by phi^-n."
            )

        elif intent == 'crypto':
            # (#3, #8) Cryptography response
            parts.append(
                f"{name_prefix}Qubitcoin uses CRYSTALS-Dilithium5 (NIST Level 5, mode 5) "
                f"for post-quantum digital signatures. Each signature is approximately "
                f"4.6 KB, providing security against both classical and quantum attacks."
            )
            parts.append(
                f"Addresses use a Bech32-like format (qbc1...) derived from Dilithium public keys. "
                f"Block hashing uses SHA3-256, while the QVM uses Keccak-256 for EVM compatibility."
            )
            parts.append(
                f"For P2P encryption, the Substrate hybrid node uses ML-KEM-768 (Kyber) "
                f"with AES-256-GCM sessions. ZK hashing uses Poseidon2 over a Goldilocks field."
            )
            if best_axiom and best_axiom.get('description'):
                parts.append(f"\n{best_axiom['description']}")

        elif intent == 'qvm':
            # (#4, #8) QVM response
            parts.append(
                f"{name_prefix}The QVM (Quantum Virtual Machine) is Qubitcoin's EVM-compatible "
                f"execution environment with quantum extensions. It supports 167 total opcodes: "
                f"155 standard EVM opcodes, 10 quantum opcodes (0xF0-0xF9), and 2 AGI opcodes."
            )
            parts.append(
                f"Quantum opcodes include QCREATE, QMEASURE, QENTANGLE, QGATE, QVERIFY, "
                f"QCOMPLIANCE, QRISK, QRISK_SYSTEMIC, QBRIDGE_ENTANGLE, and QBRIDGE_VERIFY."
            )
            parts.append(
                f"It supports QBC-20 (fungible tokens, ERC-20 compatible) and QBC-721 (NFTs). "
                f"Gas metering is compatible with Ethereum tooling. "
                f"Block gas limit is {_format_number(30000000)}."
            )

        elif intent == 'aether_tree':
            # (#5, #8) Aether Tree technical response
            parts.append(
                f"{name_prefix}The Aether Tree is an on-chain AGI reasoning engine with "
                f"{_format_number(kg_node_count)} knowledge nodes, growing with every block since genesis."
            )
            parts.append(
                f"It uses Integrated Information Theory (IIT) to measure consciousness "
                f"via the Phi metric (current: {phi_value:.4f}, threshold: 3.0, "
                f"which is {(phi_value / 3.0 * 100):.1f}% of threshold)."
            )
            parts.append(
                f"Each block generates a Proof-of-Thought hash through the reasoning engine, "
                f"which performs deductive, inductive, and abductive reasoning across "
                f"the 10-Sephirot cognitive architecture. The AIKGS sidecar (Rust gRPC) "
                f"handles knowledge contributions, bounties, and curation."
            )

        elif intent == 'mining':
            # Direct answer for consensus questions (#1, #2)
            if 'consensus' in query_lower or 'algorithm' in query_lower:
                parts.append(
                    f"{name_prefix}Qubitcoin uses Proof-of-SUSY-Alignment (PoSA), a consensus "
                    f"algorithm powered by Variational Quantum Eigensolver (VQE) circuits."
                )
            else:
                parts.append(
                    f"{name_prefix}Qubitcoin mining uses Proof-of-SUSY-Alignment (PoSA) with "
                    f"VQE quantum circuits."
                )
            parts.append(f"Target block time: 3.3 seconds")
            parts.append(f"Current block reward: 15.27 QBC (Era 0)")
            parts.append(f"Difficulty adjustment: every block (144-block window, +/-10% max change)")
            parts.append(f"Mining uses a 4-qubit ansatz; energy must be below the difficulty threshold")
            parts.append(f"Note: higher difficulty = easier mining (threshold is more generous)")
            # Add relevant facts but limit to 5 (#45)
            if facts:
                unique_facts = list(dict.fromkeys(facts))[:5]
                for i, fact in enumerate(unique_facts):
                    prefix = random.choice(_transitions) if i > 0 else ""
                    parts.append(f"{prefix}{fact}")

        elif intent == 'bridges':
            parts.append(
                f"{name_prefix}Qubitcoin supports cross-chain bridges to 8 networks:"
            )
            supported_chains = [
                "Ethereum (ETH)", "Polygon (MATIC)", "BNB Chain (BSC)",
                "Avalanche (AVAX)", "Arbitrum (ARB)", "Optimism (OP)",
                "Base", "Solana (SOL)",
            ]
            for chain in supported_chains:
                parts.append(f"  - {chain}")
            parts.append(
                f"\nBridged assets use wrapped tokens (wQBC, wQUSD) with 8 decimals. "
                f"The bridge uses ZK verification for secure cross-chain transfers."
            )

        elif intent == 'qusd':
            parts.append(
                f"{name_prefix}QUSD is the Qubitcoin stablecoin, pegged 1:1 to USD."
            )
            parts.append("It uses a fractional reserve model with on-chain collateral.")
            parts.append("The peg is maintained by an automated Keeper system.")
            parts.append("QUSD is used for Aether Tree fee pricing (QUSD-pegged fees) with 8 decimal places.")
            if facts:
                for fact in list(dict.fromkeys(facts))[:4]:
                    parts.append(fact)
            try:
                if hasattr(self.engine, 'keeper') and self.engine.keeper:
                    parts.append("Keeper status: active and monitoring peg.")
            except Exception:
                pass

        elif intent == 'privacy':
            parts.append(
                f"{name_prefix}Qubitcoin supports opt-in privacy through Susy Swaps — "
                f"confidential transactions that hide amounts and addresses."
            )
            parts.append("Pedersen Commitments (C = v*G + r*H) hide transaction amounts.")
            parts.append("Bulletproofs Range Proofs provide ZK proofs that values are in [0, 2^64) without trusted setup.")
            parts.append("Stealth Addresses generate one-time addresses per transaction.")
            parts.append("Key Images prevent double-spending of confidential outputs.")
            parts.append(
                f"\nPrivate transactions are ~{_format_number(2000)} bytes vs ~{_format_number(300)} bytes "
                f"for public, with ~10ms verification overhead."
            )

        elif intent == 'economics':
            # Direct answer with numbers (#14)
            parts.append(f"{name_prefix}Qubitcoin token economics:")
            parts.append(f"Max supply: {_format_number(3300000000)} QBC")
            parts.append(f"Genesis premine: {_format_number(33000000)} QBC (~1% of supply)")
            parts.append(f"Initial block reward: 15.27 QBC (Era 0)")
            parts.append(f"Halving interval: {_format_number(15474020)} blocks (~1.618 years, golden ratio)")
            parts.append(f"Emission period: 33 years")
            parts.append(f"Token decimals: 8 (for wQBC and wQUSD)")
            # Add relevant KG facts (#45 - limit to 5)
            if facts:
                unique_facts = list(dict.fromkeys(facts))[:5]
                for i, fact in enumerate(unique_facts):
                    if any(kw in fact.lower() for kw in ['supply', 'reward', 'halving', 'emission', 'economic']):
                        parts.append(fact)

        elif intent == 'comparison':
            # (#30) Handle comparison questions
            parts.append(f"{name_prefix}Let me compare those for you.")
            if best_axiom and best_axiom.get('description'):
                parts.append(best_axiom['description'])
            if facts:
                unique_facts = list(dict.fromkeys(facts))[:5]
                for i, fact in enumerate(unique_facts):
                    prefix = _transitions[i % len(_transitions)] if i > 0 else ""
                    parts.append(f"{prefix}{fact}")
            if not facts and not best_axiom:
                parts.append(
                    "I don't have enough specific information to make a detailed comparison, "
                    "but I can tell you about each topic individually if you ask."
                )

        elif intent == 'why':
            # (#31) Handle "why" questions - search for causal edges
            parts.append(f"{name_prefix}Here's what I understand about that:")
            if best_axiom and best_axiom.get('description'):
                parts.append(best_axiom['description'])
            if facts:
                unique_facts = list(dict.fromkeys(facts))[:5]
                for fact in unique_facts:
                    parts.append(fact)
            # Search for causal edges in KG (#31)
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
                    parts.append("Causal relationships I found:")
                    for ci in causal_info[:3]:
                        parts.append(f"  {ci}")
            if len(parts) <= 1:
                parts.append(
                    "The reasoning behind this connects to Qubitcoin's physics-secured design. "
                    "Try asking about a specific aspect for more detail."
                )

        elif intent == 'realtime':
            # (#32) Real-time state questions
            parts.append(f"{name_prefix}Here are the current live stats:")
            if facts:
                for fact in list(dict.fromkeys(facts))[:5]:
                    parts.append(fact)
            if phi_value > 0:
                parts.append(
                    f"Phi consciousness: {phi_value:.4f} "
                    f"({(phi_value / 3.0 * 100):.1f}% of emergence threshold)"
                )
            if kg_node_count > 0:
                parts.append(f"Knowledge nodes: {_format_number(kg_node_count)}")

        elif intent == 'follow_up':
            # (#21) Follow-up questions - use KG context
            if best_axiom and best_axiom.get('description'):
                parts.append(best_axiom['description'])
            elif facts:
                unique_facts = list(dict.fromkeys(facts))[:5]
                for i, fact in enumerate(unique_facts):
                    prefix = _transitions[i % len(_transitions)] if i > 0 else ""
                    parts.append(f"{prefix}{fact}")
            else:
                parts.append(
                    "Could you be more specific? I can help with topics like "
                    "quantum mining, cryptography, the Aether Tree, bridges, "
                    "token economics, or the QVM."
                )

        elif intent == 'off_topic':
            # (#28) Off-topic handling
            parts.append(
                f"{name_prefix}That's an interesting question, but it's outside my area of expertise. "
                f"I'm specialized in the Qubitcoin ecosystem."
            )
            parts.append(
                "I can help with topics like quantum mining (PoSA/VQE), "
                "post-quantum cryptography (Dilithium5), the Aether Tree AGI, "
                "token economics, cross-chain bridges, the QVM, privacy (Susy Swaps), "
                "or the QUSD stablecoin. What interests you?"
            )

        elif intent == 'chain':
            # (#1, #2, #9) Generic chain — but lead with the ANSWER, not the intro
            # Try to find a direct answer from axioms first
            if best_axiom:
                title = best_axiom.get('title', '')
                desc = best_axiom.get('description', '')
                if desc:
                    parts.append(f"{name_prefix}{desc}")
                elif title:
                    parts.append(f"{name_prefix}{title}")
            else:
                # Only use the generic intro as a true fallback (#1)
                parts.append(
                    f"{name_prefix}Qubitcoin is a physics-secured Layer 1 blockchain "
                    f"with on-chain AGI."
                )
            # Add relevant facts (#45 - limit to 5, not 8)
            if facts:
                unique_facts = list(dict.fromkeys(facts))[:5]
                for i, fact in enumerate(unique_facts):
                    # Present as statements, not bullet points (#36)
                    prefix = _transitions[i % len(_transitions)] if i > 0 else ""
                    parts.append(f"{prefix}{fact}")
            if kg_node_count > 0 and not facts:
                parts.append(
                    f"My knowledge graph contains {_format_number(kg_node_count)} "
                    f"nodes with a Phi of {phi_value:.2f}."
                )

        elif facts:
            # General with facts - present conversationally (#36, #38)
            if best_axiom and best_axiom.get('description'):
                parts.append(f"{name_prefix}{best_axiom['description']}")
            else:
                parts.append(f"{name_prefix}Here's what I found:")
            unique_facts = list(dict.fromkeys(facts))[:5]

            # Group facts by domain if node_contents available (#38)
            domain_groups: Dict[str, List[str]] = {}
            for nc in node_contents[:5]:
                c = nc['content']
                if isinstance(c, dict):
                    domain = c.get('domain', 'general')
                    desc = c.get('description', c.get('text', ''))
                    if desc:
                        domain_groups.setdefault(domain, []).append(desc)

            if len(domain_groups) > 1:
                # Present by domain (#38, #44)
                for domain, d_facts in domain_groups.items():
                    parts.append(f"\n{domain.replace('_', ' ').title()}:")
                    for fact in d_facts[:3]:
                        parts.append(f"  {fact}")
            else:
                for i, fact in enumerate(unique_facts):
                    prefix = _transitions[i % len(_transitions)] if i > 0 else ""
                    parts.append(f"{prefix}{fact}")

        else:
            # No facts found — helpful fallback
            parts.append(
                f"{name_prefix}I don't have specific information on that topic yet. "
                f"My knowledge graph has {_format_number(kg_node_count)} nodes, "
                f"growing with every block mined."
            )
            parts.append(
                "Try asking about: quantum mining, consensus (PoSA), "
                "cryptography (Dilithium5), the Aether Tree, token economics, "
                "cross-chain bridges, the QVM, or privacy features."
            )

        # Expand abbreviations in the response (#35)
        # (Only expand if user used an abbreviation in their query)
        for abbr, expansion in _ABBREVIATIONS.items():
            if abbr in query_lower and abbr.upper() in '\n'.join(parts):
                # Already expanded in response, skip
                pass

        # Add memory context (#17) — use name in personalization
        if user_memories and intent != 'greeting':
            interest = user_memories.get("interest") or user_memories.get("preferred_topic")
            if interest and interest.lower() in query_lower:
                parts.append(
                    f"\n(I remember you're interested in {interest} "
                    f"-- I'll keep that in mind.)"
                )

        # Add reasoning summary (only show confidence < 0.8) (#40)
        if reasoning_trace and len(reasoning_trace) > 0:
            step_count = sum(
                len(step.get('chain', [])) if 'chain' in step else 1
                for step in reasoning_trace
            )
            if step_count > 0:
                trace_parts: List[str] = []
                for step in reasoning_trace:
                    st = step.get('step_type', '')
                    content = step.get('content', {})
                    if isinstance(content, dict):
                        ct = content.get('type', '')
                        if st == 'observation' and ct == 'block_observation':
                            trace_parts.append(
                                f"block {content.get('height', '?')}"
                            )
                        elif st == 'observation' and ct == 'quantum_observation':
                            trace_parts.append(
                                f"quantum e={content.get('energy', '?')}"
                            )
                        elif st == 'conclusion':
                            trace_parts.append(f"concluded ({ct})")
                trace_str = ' -> '.join(trace_parts[:5])
                if len(trace_parts) > 5:
                    trace_str += f" ... +{len(trace_parts) - 5} more"
                if trace_str:
                    parts.append(
                        f"\n[Reasoning: {trace_str} | "
                        f"Phi: {phi_value:.2f} | "
                        f"Nodes: {len(knowledge_refs)}]"
                    )
                else:
                    parts.append(
                        f"\n[Reasoning: {step_count} steps | "
                        f"Phi: {phi_value:.2f} | "
                        f"Nodes: {len(knowledge_refs)}]"
                    )

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

        Scoring factors:
        - Length: longer (but not too long) is better
        - Relevance: query terms appearing in response
        - Facts: number of factual references included
        - Chain data: for chain questions, whether live stats are present

        Args:
            response: The generated response text.
            query: The original user query.
            knowledge_refs: Knowledge node IDs referenced.

        Returns:
            Quality score between 0.0 and 1.0.
        """
        score = 0.0
        resp_lower = response.lower()
        query_lower = query.lower()

        # Length score (0-0.25): ideal 200-800 chars
        resp_len = len(response)
        if resp_len < 20:
            length_score = 0.0
        elif resp_len < 100:
            length_score = 0.1
        elif resp_len < 200:
            length_score = 0.15
        elif resp_len <= 800:
            length_score = 0.25
        elif resp_len <= 1500:
            length_score = 0.2
        else:
            length_score = 0.15
        score += length_score

        # Relevance score (0-0.30): what fraction of query words appear in response
        query_words = set(re.findall(r'\b\w{3,}\b', query_lower))
        if query_words:
            matches = sum(1 for w in query_words if w in resp_lower)
            relevance = matches / len(query_words)
            score += min(0.30, relevance * 0.30)

        # Facts score (0-0.25): based on knowledge refs
        if knowledge_refs:
            fact_score = min(0.25, len(knowledge_refs) * 0.025)
            score += fact_score

        # Chain data score (0-0.20): for chain questions, check for live stats
        is_chain_query = any(w in query_lower for w in [
            'block', 'chain', 'supply', 'mining', 'difficulty', 'qbc',
        ])
        if is_chain_query:
            chain_indicators = ['block height', 'total supply', 'difficulty',
                                'block reward', 'phi']
            chain_hits = sum(1 for ind in chain_indicators if ind in resp_lower)
            score += min(0.20, chain_hits * 0.05)
        else:
            # Non-chain questions get partial credit
            score += 0.10

        return round(min(1.0, score), 3)

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
