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
import time
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


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


@dataclass
class ChatSession:
    """An Aether chat session."""
    session_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: float = 0.0
    user_address: str = ''
    messages_sent: int = 0
    fees_paid_atoms: int = 0

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'messages': [m.to_dict() for m in self.messages],
            'created_at': self.created_at,
            'user_address': self.user_address,
            'messages_sent': self.messages_sent,
        }


class AetherChat:
    """Manages Aether Tree chat interactions."""

    def __init__(self, aether_engine, db_manager, fee_manager=None) -> None:
        """
        Args:
            aether_engine: The main AetherEngine instance.
            db_manager: Database manager for persistence.
            fee_manager: Optional fee manager for pricing.
        """
        self.engine = aether_engine
        self.db = db_manager
        self.fee_manager = fee_manager
        self._sessions: Dict[str, ChatSession] = {}
        self._max_sessions = 10000

    def create_session(self, user_address: str = '') -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            created_at=time.time(),
            user_address=user_address,
        )
        self._sessions[session.session_id] = session

        # Evict oldest session if at capacity
        if len(self._sessions) > self._max_sessions:
            oldest_id = min(self._sessions, key=lambda k: self._sessions[k].created_at)
            del self._sessions[oldest_id]

        logger.info(f"Chat session created: {session.session_id[:8]}...")
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get an existing session."""
        return self._sessions.get(session_id)

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

        # Record user message
        user_msg = ChatMessage(role='user', content=message, timestamp=time.time())
        session.messages.append(user_msg)
        session.messages_sent += 1

        # Generate response using the reasoning engine
        reasoning_trace = []
        knowledge_refs = []
        phi_value = 0.0

        try:
            # Use knowledge graph to find relevant nodes
            if self.engine.kg:
                relevant = self._search_knowledge(message)
                knowledge_refs = [n for n in relevant[:10]]

            # Run reasoning
            if self.engine.reasoning and self.engine.kg:
                if is_deep_query:
                    reasoning_trace = self._deep_reason(message, knowledge_refs)
                else:
                    reasoning_trace = self._quick_reason(message, knowledge_refs)

            # Compute current Phi
            if self.engine.phi:
                phi_result = self.engine.phi.compute_phi()
                phi_value = phi_result.get('phi_value', 0.0)

        except Exception as e:
            logger.debug(f"Chat reasoning error: {e}")

        # Generate response content from reasoning trace
        response_content = self._synthesize_response(message, reasoning_trace, knowledge_refs)

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

        return {
            'response': response_content,
            'reasoning_trace': reasoning_trace,
            'phi_at_response': phi_value,
            'knowledge_nodes_referenced': knowledge_refs,
            'proof_of_thought_hash': pot_hash,
            'session_id': session_id,
            'message_index': len(session.messages) - 1,
        }

    def _search_knowledge(self, query: str) -> List[int]:
        """Search the knowledge graph for nodes relevant to the query."""
        if not self.engine.kg or not self.engine.kg.nodes:
            return []
        # Simple keyword matching on node content
        query_lower = query.lower()
        scored = []
        for node_id, node in self.engine.kg.nodes.items():
            content_str = json.dumps(node.content).lower()
            if any(word in content_str for word in query_lower.split() if len(word) > 2):
                scored.append((node_id, node.confidence))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:10]]

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
        """Deep reasoning: multiple reasoning types combined."""
        steps = self._quick_reason(message, knowledge_refs)
        if not self.engine.reasoning:
            return steps
        try:
            # Also try deductive and abductive reasoning
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
                             knowledge_refs: List[int]) -> str:
        """Synthesize a natural language response from reasoning results.

        This is a placeholder that generates structured responses from the
        knowledge graph and reasoning trace. A production system would use
        an LLM adapter for natural language generation.
        """
        parts = []

        if reasoning_trace:
            conclusions = [
                step.get('conclusion', step.get('result', ''))
                for step in reasoning_trace
                if step.get('conclusion') or step.get('result')
            ]
            if conclusions:
                parts.append(f"Based on {len(reasoning_trace)} reasoning steps, "
                             f"I found {len(conclusions)} relevant conclusions.")
                for i, c in enumerate(conclusions[:3], 1):
                    parts.append(f"  {i}. {c}")

        if knowledge_refs and self.engine.kg:
            node_types = {}
            for ref in knowledge_refs[:5]:
                node = self.engine.kg.nodes.get(ref)
                if node:
                    t = node.node_type
                    node_types[t] = node_types.get(t, 0) + 1
            if node_types:
                type_str = ", ".join(f"{v} {k}" for k, v in node_types.items())
                parts.append(f"Referenced {len(knowledge_refs)} knowledge nodes ({type_str}).")

        if not parts:
            parts.append(f"I received your message about '{query[:50]}'. "
                         "The knowledge graph is still building. "
                         "As more blocks are mined, my reasoning capabilities will grow.")

        return " ".join(parts)

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
