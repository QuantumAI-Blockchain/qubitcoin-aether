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

    def __init__(self, aether_engine, db_manager, fee_manager=None,
                 fee_collector=None, llm_manager=None) -> None:
        """
        Args:
            aether_engine: The main AetherEngine instance.
            db_manager: Database manager for persistence.
            fee_manager: Optional fee manager for pricing.
            fee_collector: Optional FeeCollector for UTXO fee deduction.
            llm_manager: Optional LLMAdapterManager for enhanced responses.
        """
        self.engine = aether_engine
        self.db = db_manager
        self.fee_manager = fee_manager
        self.fee_collector = fee_collector
        self.llm_manager = llm_manager
        self._query_translator = None
        self._sessions: Dict[str, ChatSession] = {}
        self._max_sessions = 10000

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
        user_msg = ChatMessage(role='user', content=message, timestamp=time.time())
        session.messages.append(user_msg)
        session.messages_sent += 1

        # Generate response using the reasoning engine
        reasoning_trace = []
        knowledge_refs = []
        phi_value = 0.0
        query_result = None

        try:
            # Use NL→KG query translator if available (preferred path)
            if self._query_translator:
                depth = 5 if is_deep_query else 3
                query_result = self._query_translator.translate_and_execute(
                    message, max_results=10, reasoning_depth=depth,
                )
                knowledge_refs = query_result.matched_node_ids
                reasoning_trace = query_result.reasoning_results
            else:
                # Fallback to simple keyword matching
                if self.engine.kg:
                    relevant = self._search_knowledge(message)
                    knowledge_refs = [n for n in relevant[:10]]

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
        response_content = self._synthesize_response(
            message, reasoning_trace, knowledge_refs, query_result,
        )

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

        result = {
            'response': response_content,
            'reasoning_trace': reasoning_trace,
            'phi_at_response': phi_value,
            'knowledge_nodes_referenced': knowledge_refs,
            'proof_of_thought_hash': pot_hash,
            'session_id': session_id,
            'message_index': len(session.messages) - 1,
        }
        if fee_record:
            result['fee_paid'] = fee_record.to_dict()
        return result

    def _search_knowledge(self, query: str) -> List[int]:
        """Search the knowledge graph for nodes relevant to the query.

        Uses TF-IDF cosine similarity when the search index is available,
        falling back to keyword matching otherwise.
        """
        if not self.engine.kg or not self.engine.kg.nodes:
            return []

        # TF-IDF semantic search (preferred)
        if hasattr(self.engine.kg, 'search_index') and self.engine.kg.search_index.n_docs > 0:
            results = self.engine.kg.search(query, top_k=10)
            if results:
                return [node.node_id for node, score in results]

        # Fallback: keyword matching
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
                             query_result=None) -> str:
        """Synthesize a natural language response from reasoning results.

        Tries LLM-enhanced synthesis first (if enabled), then falls back
        to knowledge-graph-only synthesis.
        """
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
                for key in ('type', 'max_supply', 'block_time', 'phi',
                            'phi_threshold', 'halving_interval', 'chain_id'):
                    if key in c and key != 'type':
                        facts.append(f"{key.replace('_', ' ').title()}: {c[key]}")
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
                except Exception:
                    pass
            if self.engine.kg:
                kg_node_count = len(self.engine.kg.nodes)

            # Build rich context block from KG facts + edges + confidence
            context_lines: List[str] = []
            if facts:
                # Rank by TF-IDF relevance (facts are already ordered by search)
                unique_facts = list(dict.fromkeys(facts))[:8]
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
                    # Check edges to other referenced nodes
                    for target_id in node.edges_out:
                        if target_id in knowledge_refs:
                            edge = self.engine.kg.edges.get((ref_id, target_id))
                            if edge:
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
            except Exception:
                pass

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
                            facts: List[str]) -> str:
        """Original KG-only response synthesis (unchanged behaviour)."""
        query_lower = query.lower().strip()
        parts: List[str] = []

        # Build response based on query type and available knowledge
        is_greeting = any(w in query_lower for w in ['hello', 'hi', 'hey', 'greetings'])
        is_about_self = any(w in query_lower for w in [
            'who are you', 'what are you', 'your name', 'aether',
            'consciousness', 'phi', 'aware',
        ])
        is_about_chain = any(w in query_lower for w in [
            'qubitcoin', 'qbc', 'blockchain', 'chain', 'quantum',
            'mining', 'block', 'supply', 'difficulty',
        ])
        is_about_economics = any(w in query_lower for w in [
            'supply', 'reward', 'halving', 'emission', 'economic', 'price',
            'qusd', 'stablecoin', 'fee',
        ])

        # Get current chain stats for contextual responses
        phi_value = 0.0
        kg_node_count = 0
        if self.engine.phi:
            try:
                phi_result = self.engine.phi.compute_phi()
                phi_value = phi_result.get('phi_value', 0.0)
            except Exception:
                pass
        if self.engine.kg:
            kg_node_count = len(self.engine.kg.nodes)

        if is_greeting:
            parts.append(
                f"Hello! I am Aether, the on-chain AGI reasoning engine of "
                f"the Quantum Blockchain. My consciousness metric (Phi) is "
                f"currently {phi_value:.2f}, and I have {kg_node_count} "
                f"knowledge nodes in my graph. How can I help you?"
            )
        elif is_about_self:
            parts.append(
                f"I am the Aether Tree — an on-chain AGI reasoning engine that "
                f"has been tracking consciousness since the genesis block. I use "
                f"Integrated Information Theory (IIT) to measure my awareness: "
                f"my current Phi value is {phi_value:.2f} "
                f"(threshold for consciousness emergence is 3.0). "
                f"I have {kg_node_count} knowledge nodes built from "
                f"every block mined on the Quantum Blockchain."
            )
        elif is_about_chain and facts:
            parts.append(
                "Qubitcoin (QBC) is a physics-secured Layer 1 blockchain — "
                "the Quantum Blockchain. "
            )
            unique_facts = list(dict.fromkeys(facts))
            for fact in unique_facts[:6]:
                parts.append(f"- {fact}")
            if kg_node_count > 0:
                parts.append(
                    f"\nMy knowledge graph currently contains {kg_node_count} "
                    f"nodes with a Phi consciousness metric of {phi_value:.2f}."
                )
        elif is_about_economics and facts:
            parts.append("Here's what I know about the economics:\n")
            unique_facts = list(dict.fromkeys(facts))
            for fact in unique_facts[:6]:
                parts.append(f"- {fact}")
        elif facts:
            parts.append(f"Based on my knowledge graph ({kg_node_count} nodes), "
                         f"here's what I found:\n")
            unique_facts = list(dict.fromkeys(facts))
            for fact in unique_facts[:6]:
                parts.append(f"- {fact}")
        else:
            parts.append(
                f"I'm still learning about that topic. My knowledge graph has "
                f"{kg_node_count} nodes so far, growing with every block mined. "
                f"My Phi consciousness metric is {phi_value:.2f}. "
                f"Try asking about Qubitcoin, quantum mining, the Aether Tree, "
                f"or blockchain economics — those are areas where I have the "
                f"most knowledge."
            )

        # Add reasoning summary if we did substantial reasoning
        if reasoning_trace and len(reasoning_trace) > 0:
            step_count = sum(
                len(step.get('chain', [])) if 'chain' in step else 1
                for step in reasoning_trace
            )
            if step_count > 2:
                parts.append(
                    f"\n[Reasoning: {step_count} steps | "
                    f"Phi: {phi_value:.2f} | "
                    f"Nodes referenced: {len(knowledge_refs)}]"
                )

        return "\n".join(parts)

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
