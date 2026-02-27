"""
Sephirot Node Implementations — Python base classes for Tree of Life AGI nodes.

Each Sephirah node has:
  - A role from the Tree of Life (Keter, Chochmah, ... Malkuth)
  - A quantum state (n-qubit density matrix placeholder)
  - Domain-specific processing logic
  - Message handling (send/receive via CSF transport)
  - SUSY balance tracking

These are the Python-side cognitive processors.
The Solidity contracts (.sol) handle on-chain state;
these classes handle off-chain reasoning and coordination.
"""
import hashlib
import math
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .sephirot import SephirahRole, SephirahState, QUBIT_ALLOCATION
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NodeMessage:
    """Message passed between Sephirot nodes via CSF transport."""
    sender: SephirahRole
    receiver: SephirahRole
    payload: Dict[str, Any]
    priority: float = 1.0
    timestamp: float = field(default_factory=time.time)
    message_id: str = ""

    def __post_init__(self) -> None:
        if not self.message_id:
            raw = f"{self.sender.value}:{self.receiver.value}:{self.timestamp}"
            self.message_id = hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class ProcessingResult:
    """Result from a Sephirah's processing step."""
    role: SephirahRole
    action: str
    output: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    messages_out: List[NodeMessage] = field(default_factory=list)
    success: bool = True


class BaseSephirah(ABC):
    """
    Abstract base class for all 10 Sephirot nodes.

    Subclasses implement domain-specific processing
    (meta-learning, intuition, logic, etc.) while this base
    provides common infrastructure: state management, message
    handling, quantum state placeholders, and logging.
    """

    def __init__(self, role: SephirahRole, knowledge_graph: Optional[object] = None) -> None:
        self.role = role
        self.kg = knowledge_graph
        self.state = SephirahState(
            role=role,
            qubits=QUBIT_ALLOCATION[role],
        )
        self._inbox: List[NodeMessage] = []
        self._outbox: List[NodeMessage] = []
        self._processing_count: int = 0
        self._quantum_state: Optional[List[List[complex]]] = None
        # Performance metrics for reward weighting (item 2.3)
        self._tasks_solved: int = 0
        self._knowledge_contributed: int = 0
        self._errors: int = 0
        logger.debug(f"Sephirah {role.value} initialized ({QUBIT_ALLOCATION[role]} qubits)")

    def serialize_state(self) -> Dict[str, Any]:
        """Serialize this node's state to a dict for DB persistence.

        Subclasses with additional state (goals, policies, etc.)
        should override and call super().
        """
        return {
            'role': self.role.value,
            'processing_count': self._processing_count,
            'tasks_solved': self._tasks_solved,
            'knowledge_contributed': self._knowledge_contributed,
            'errors': self._errors,
            'state': {
                'active': self.state.active,
                'energy': self.state.energy,
                'qbc_stake': self.state.qbc_stake,
                'messages_processed': self.state.messages_processed,
                'reasoning_ops': self.state.reasoning_ops,
            },
        }

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        """Restore this node's state from a serialized dict.

        Subclasses should override and call super().
        """
        self._processing_count = data.get('processing_count', 0)
        self._tasks_solved = data.get('tasks_solved', 0)
        self._knowledge_contributed = data.get('knowledge_contributed', 0)
        self._errors = data.get('errors', 0)
        state_data = data.get('state', {})
        self.state.active = state_data.get('active', True)
        self.state.energy = state_data.get('energy', 1.0)
        self.state.qbc_stake = state_data.get('qbc_stake', 0.0)
        self.state.messages_processed = state_data.get('messages_processed', 0)
        self.state.reasoning_ops = state_data.get('reasoning_ops', 0)

    def _energy_quality_factor(self) -> float:
        """Return a quality factor in [0.0, 1.0] based on node energy.

        High energy (>= 1.0) -> factor 1.0 (full reasoning depth).
        Low energy (approaching 0) -> factor approaches 0.1 (minimal reasoning).
        Used by specialized_reason() to modulate output quality.
        """
        e = max(0.0, self.state.energy)
        # Sigmoid-like ramp: factor = 0.1 + 0.9 * (1 - e^(-2*e))
        return 0.1 + 0.9 * (1.0 - math.exp(-2.0 * e))

    @abstractmethod
    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """
        Main processing method. Each node implements domain-specific logic.

        Args:
            context: Block context, knowledge graph state, messages, etc.

        Returns:
            ProcessingResult with outputs and outgoing messages
        """

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Domain-specific reasoning for this Sephirah.

        Subclasses MUST override this method to provide specialized reasoning
        appropriate to their cognitive function.

        Args:
            context: Dict with keys:
                - query (str): The reasoning query
                - knowledge_nodes (List[dict]): Relevant knowledge nodes
                - recent_reasoning (List[dict]): Recent reasoning operations
                - energy (float): Current energy level of this node

        Returns:
            Dict with keys:
                - result (str): The reasoning output
                - confidence (float): Confidence in the result [0.0, 1.0]
                - reasoning_type (str): Type of reasoning performed
                - steps (List[str]): Step-by-step reasoning trace
        """
        return {
            'result': 'No specialized reasoning implemented',
            'confidence': 0.0,
            'reasoning_type': 'none',
            'steps': [],
        }

    def receive_message(self, msg: NodeMessage) -> None:
        """Receive a message from another Sephirah."""
        self._inbox.append(msg)
        self.state.messages_processed += 1

    def get_outbox(self) -> List[NodeMessage]:
        """Drain and return pending outgoing messages."""
        msgs = list(self._outbox)
        self._outbox.clear()
        return msgs

    def send_message(self, receiver: SephirahRole, payload: Dict[str, Any],
                     priority: float = 1.0) -> NodeMessage:
        """Queue a message to another Sephirah."""
        msg = NodeMessage(
            sender=self.role,
            receiver=receiver,
            payload=payload,
            priority=priority,
        )
        self._outbox.append(msg)
        return msg

    def get_status(self) -> Dict[str, Any]:
        """Get node status for API/dashboard."""
        return {
            "role": self.role.value,
            "active": self.state.active,
            "energy": round(self.state.energy, 6),
            "qubits": self.state.qubit_allocation,
            "messages_processed": self.state.messages_processed,
            "reasoning_ops": self.state.reasoning_ops,
            "processing_count": self._processing_count,
            "inbox_size": len(self._inbox),
            "outbox_size": len(self._outbox),
            "tasks_solved": self._tasks_solved,
            "knowledge_contributed": self._knowledge_contributed,
            "errors": self._errors,
        }

    def get_performance_weight(self) -> float:
        """Compute performance weight for reward distribution.

        Weight = tasks_solved * 0.5 + knowledge_contributed * 0.3 + reasoning_ops * 0.2
        Minimum weight is 1.0 so idle nodes still get baseline reward.
        """
        return max(1.0, (
            self._tasks_solved * 0.5
            + self._knowledge_contributed * 0.3
            + self.state.reasoning_ops * 0.2
        ))

    def _consume_inbox(self) -> List[NodeMessage]:
        """Consume all messages from inbox."""
        msgs = list(self._inbox)
        self._inbox.clear()
        return msgs


class KeterNode(BaseSephirah):
    """
    Keter (Crown) — Meta-learning and goal formation.

    Brain analog: Prefrontal cortex
    Quantum state: 8 qubits (goal space superposition)

    Responsibilities:
    - Evaluate system-wide goals and priorities
    - Detect meta-patterns in other nodes' outputs
    - Form high-level objectives for the reasoning cycle
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.KETER, knowledge_graph)
        self._goals: List[Dict[str, Any]] = []
        self._meta_patterns: List[Dict[str, Any]] = []

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Evaluate goals and form meta-level objectives.

        Deep integration: reads metacognition strategy recommendation and
        Malkuth feedback from context to steer goal priorities.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        # Aggregate reports from other nodes (especially Malkuth feedback)
        reports = [m.payload for m in messages if m.payload.get("type") == "report"]

        # Track Malkuth KG mutation stats for self-assessment
        malkuth_stats = context.get('malkuth_stats', {})
        if malkuth_stats:
            kg_mutations = malkuth_stats.get('kg_mutations', 0)
            if kg_mutations == 0 and self._processing_count > 5:
                # No KG mutations — system is stagnating, raise exploration priority
                self._stagnation_counter = getattr(self, '_stagnation_counter', 0) + 1
            else:
                self._stagnation_counter = 0

        # Detect meta-patterns from aggregated reports
        if len(reports) >= 3:
            pattern = {
                "type": "meta_pattern",
                "source_count": len(reports),
                "block_height": context.get("block_height", 0),
            }
            self._meta_patterns.append(pattern)
            if len(self._meta_patterns) > 100:
                self._meta_patterns = self._meta_patterns[-100:]

        # Read metacognition recommended strategy (injected by pipeline)
        recommended_strategy = context.get('recommended_strategy', '')

        # Form goals based on context + metacognition guidance
        priority = context.get("priority", "normal")
        if recommended_strategy:
            # Use metacognition to set goal priority
            strategy_priority_map = {
                'inductive': 'explore',
                'deductive': 'verify',
                'abductive': 'hypothesize',
                'neural': 'pattern_match',
            }
            priority = strategy_priority_map.get(recommended_strategy, priority)

        # Boost exploration priority when stagnating
        stagnation = getattr(self, '_stagnation_counter', 0)
        if stagnation >= 3:
            priority = 'explore'

        goal = {
            "type": "goal",
            "priority": priority,
            "block_height": context.get("block_height", 0),
            "recommended_strategy": recommended_strategy,
        }
        self._goals.append(goal)
        if len(self._goals) > 50:
            self._goals = self._goals[-50:]

        # Broadcast goal to Tiferet (integration hub)
        # Include strategy directive so downstream nodes know the focus
        self.send_message(SephirahRole.TIFERET, {
            "type": "goal_directive",
            "goal": goal,
        })

        # Send strategy directive to Chochmah for intuition focus
        self.send_message(SephirahRole.CHOCHMAH, {
            "type": "strategy_directive",
            "strategy": recommended_strategy,
            "priority": priority,
        })

        return ProcessingResult(
            role=self.role,
            action="goal_formation",
            output={
                "goals": len(self._goals),
                "meta_patterns": len(self._meta_patterns),
                "recommended_strategy": recommended_strategy,
                "priority": priority,
            },
            confidence=0.85,
            messages_out=self.get_outbox(),
        )

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Meta-reasoning: evaluate reasoning strategies and select the optimal approach.

        Keter examines recent reasoning operations, scores each strategy on
        success rate and relevance to the current query, then recommends the
        best approach for the system to use.
        """
        query = context.get('query', '')
        recent = context.get('recent_reasoning', [])
        nodes = context.get('knowledge_nodes', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        # Enumerate candidate strategies
        strategies = {
            'deductive': 0.0,
            'inductive': 0.0,
            'abductive': 0.0,
            'neural': 0.0,
            'exploratory': 0.0,
        }

        steps.append(f"Energy quality factor: {qf:.2f}")

        # Score strategies by analyzing recent reasoning success
        if recent:
            max_recent = max(3, int(len(recent) * qf))
            for op in recent[-max_recent:]:
                strategy = op.get('type', op.get('reasoning_type', ''))
                success = op.get('success', op.get('confidence', 0.5))
                if strategy in strategies:
                    strategies[strategy] += float(success)
            steps.append(f"Analyzed {min(max_recent, len(recent))} recent operations")
        else:
            steps.append("No recent reasoning history; defaulting to balanced scores")
            for s in strategies:
                strategies[s] = 0.5

        # Boost by query content heuristics
        query_lower = query.lower()
        if any(kw in query_lower for kw in ['prove', 'verify', 'implies', 'therefore']):
            strategies['deductive'] += 1.0 * qf
            steps.append("Query contains deductive keywords -> boosting deductive")
        if any(kw in query_lower for kw in ['pattern', 'trend', 'often', 'usually']):
            strategies['inductive'] += 1.0 * qf
            steps.append("Query contains inductive keywords -> boosting inductive")
        if any(kw in query_lower for kw in ['why', 'explain', 'cause', 'because']):
            strategies['abductive'] += 1.0 * qf
            steps.append("Query contains abductive keywords -> boosting abductive")
        if any(kw in query_lower for kw in ['predict', 'estimate', 'similar']):
            strategies['neural'] += 1.0 * qf
            steps.append("Query contains neural keywords -> boosting neural")
        if any(kw in query_lower for kw in ['explore', 'novel', 'creative', 'new']):
            strategies['exploratory'] += 1.0 * qf
            steps.append("Query contains exploratory keywords -> boosting exploratory")

        # Boost based on knowledge graph density
        if len(nodes) > 50:
            strategies['neural'] += 0.5 * qf
            steps.append("Dense knowledge graph -> boosting neural strategy")
        elif len(nodes) < 10:
            strategies['exploratory'] += 0.5 * qf
            steps.append("Sparse knowledge graph -> boosting exploration")

        # Select the best strategy
        best_strategy = max(strategies, key=strategies.get)
        best_score = strategies[best_strategy]
        total_score = sum(strategies.values()) or 1.0
        confidence = min(1.0, (best_score / total_score) * qf)

        steps.append(f"Selected strategy: {best_strategy} (score={best_score:.2f}, "
                     f"total={total_score:.2f})")

        return {
            'result': f"Recommended strategy: {best_strategy}",
            'confidence': round(confidence, 4),
            'reasoning_type': 'meta_reasoning',
            'steps': steps,
            'strategy_scores': {k: round(v, 4) for k, v in strategies.items()},
        }

    def auto_generate_goals(self, domain_stats: Dict[str, dict] = None,
                            contradiction_count: int = 0) -> List[Dict[str, Any]]:
        """Generate goals autonomously based on knowledge gaps and contradictions.

        This is the first step toward autonomous AGI — the system decides
        what to learn based on its own self-assessment.

        Args:
            domain_stats: Dict of domain -> {count, avg_confidence} from KG.
            contradiction_count: Number of unresolved contradictions.

        Returns:
            List of newly generated goals (max 10 auto-goals).
        """
        auto_goals: List[Dict[str, Any]] = []

        # Goal 1: Learn about under-represented domains
        if domain_stats:
            sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1]['count'])
            for domain, info in sorted_domains[:3]:
                if info['count'] < 100:
                    auto_goals.append({
                        'type': 'learn_domain',
                        'domain': domain,
                        'current_count': info['count'],
                        'priority': 'high' if info['count'] < 20 else 'medium',
                        'source': 'auto',
                    })

        # Goal 2: Resolve contradictions
        if contradiction_count > 0:
            auto_goals.append({
                'type': 'resolve_contradictions',
                'count': contradiction_count,
                'priority': 'high' if contradiction_count > 5 else 'medium',
                'source': 'auto',
            })

        # Goal 3: Boost low-confidence domains
        if domain_stats:
            for domain, info in domain_stats.items():
                if info.get('avg_confidence', 1.0) < 0.5 and info['count'] > 10:
                    auto_goals.append({
                        'type': 'improve_confidence',
                        'domain': domain,
                        'avg_confidence': info['avg_confidence'],
                        'priority': 'medium',
                        'source': 'auto',
                    })
                    if len(auto_goals) >= 10:
                        break

        # Cap at 10 auto-goals, reserve 40 slots for external goals
        auto_goals = auto_goals[:10]

        # Remove old auto-goals, add new ones
        self._goals = [g for g in self._goals if g.get('source') != 'auto']
        self._goals.extend(auto_goals)
        if len(self._goals) > 50:
            self._goals = self._goals[-50:]

        if auto_goals:
            logger.info(f"Keter auto-generated {len(auto_goals)} goals")

        return auto_goals

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['goals'] = self._goals[-50:]
        data['meta_patterns'] = self._meta_patterns[-100:]
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._goals = data.get('goals', [])
        self._meta_patterns = data.get('meta_patterns', [])


class ChochmahNode(BaseSephirah):
    """
    Chochmah (Wisdom) — Intuition and pattern discovery.

    Brain analog: Right hemisphere
    Quantum state: 6 qubits (idea superposition)

    Responsibilities:
    - Detect non-obvious patterns in knowledge graph
    - Generate intuitive hypotheses
    - Feed creative insights to Binah for verification
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.CHOCHMAH, knowledge_graph)
        self._insights: List[Dict[str, Any]] = []

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Intuitive reasoning: pattern matching, rapid association, hypothesis generation.

        Chochmah looks for structural similarities between knowledge nodes, finds
        clusters of related concepts, and generates hypotheses from sparse data.
        """
        query = context.get('query', '')
        nodes = context.get('knowledge_nodes', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"Intuition quality factor: {qf:.2f}")

        # Extract key terms from query for association matching
        query_terms = set(query.lower().split())
        steps.append(f"Query terms: {len(query_terms)}")

        # Find nodes that share terms with the query (rapid association)
        associated: List[Tuple[dict, float]] = []
        for node in nodes:
            content = str(node.get('content', node.get('name', ''))).lower()
            node_terms = set(content.split())
            overlap = len(query_terms & node_terms)
            if overlap > 0:
                relevance = overlap / max(len(query_terms), 1)
                associated.append((node, relevance))

        associated.sort(key=lambda x: x[1], reverse=True)
        # Limit by energy (low energy = fewer associations considered)
        max_assoc = max(1, int(len(associated) * qf))
        associated = associated[:max_assoc]

        steps.append(f"Found {len(associated)} associated nodes")

        # Look for common patterns across associated nodes
        type_counts: Dict[str, int] = {}
        for node, _ in associated:
            ntype = node.get('node_type', node.get('type', 'unknown'))
            type_counts[ntype] = type_counts.get(ntype, 0) + 1

        # Generate hypotheses based on dominant patterns
        hypotheses: List[str] = []
        if type_counts:
            dominant_type = max(type_counts, key=type_counts.get)
            hypotheses.append(
                f"Dominant pattern: {dominant_type} nodes ({type_counts[dominant_type]}) "
                f"cluster around query concept"
            )
            steps.append(f"Dominant node type: {dominant_type}")

        # Cross-association: find non-obvious links between distant nodes
        if len(associated) >= 2 and qf > 0.5:
            first = associated[0][0]
            last = associated[-1][0]
            hypotheses.append(
                f"Potential hidden link between '{first.get('name', 'node_0')}' "
                f"and '{last.get('name', 'node_N')}'"
            )
            steps.append("Generated cross-association hypothesis from distant nodes")

        confidence = min(1.0, (len(associated) / max(len(nodes), 1)) * qf) if nodes else 0.1
        result_text = "; ".join(hypotheses) if hypotheses else "Insufficient data for pattern detection"

        return {
            'result': result_text,
            'confidence': round(confidence, 4),
            'reasoning_type': 'intuitive_pattern_matching',
            'steps': steps,
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Discover patterns and generate intuitive insights.

        Deep integration: uses neural_hints from GATReasoner to strengthen
        pattern detection and reads Keter strategy directives.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        # Read strategy directive from Keter
        strategy_focus = ''
        for msg in messages:
            if msg.payload.get("type") == "strategy_directive":
                strategy_focus = msg.payload.get("strategy", '')

        # Read neural hints injected by pipeline (from GATReasoner)
        neural_hints = context.get('neural_hints', {})
        neural_confidence = neural_hints.get('confidence', 0.0)
        neural_attended = neural_hints.get('attended_nodes', [])
        suggested_edge = neural_hints.get('suggested_edge_type', '')

        insight = None
        insight_confidence = 0.6  # default

        if self.kg and hasattr(self.kg, 'nodes') and len(self.kg.nodes) >= 3:
            # Look for clusters of related nodes
            recent = sorted(
                self.kg.nodes.values(),
                key=lambda n: n.source_block,
                reverse=True,
            )[:10]
            if len(recent) >= 2:
                insight = {
                    "type": "pattern_insight",
                    "node_count": len(recent),
                    "block_height": context.get("block_height", 0),
                }

                # Enrich insight with neural reasoner hints if available
                if neural_confidence > 0.3:
                    insight["neural_confidence"] = neural_confidence
                    insight["neural_attended_count"] = len(neural_attended)
                    insight["suggested_edge_type"] = suggested_edge
                    # Neural agreement boosts confidence
                    insight_confidence = min(0.9, 0.6 + neural_confidence * 0.3)

                # If Keter directed a specific strategy, tag the insight
                if strategy_focus:
                    insight["strategy_focus"] = strategy_focus

                self._insights.append(insight)
                if len(self._insights) > 100:
                    self._insights = self._insights[-100:]

        # Send insight to Binah for logical verification
        if insight:
            self.send_message(SephirahRole.BINAH, {
                "type": "insight_for_verification",
                "insight": insight,
            })

        return ProcessingResult(
            role=self.role,
            action="pattern_discovery",
            output={
                "insights": len(self._insights),
                "new_insight": insight is not None,
                "neural_confidence": neural_confidence,
                "strategy_focus": strategy_focus,
            },
            confidence=insight_confidence,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['insights'] = self._insights[-100:]
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._insights = data.get('insights', [])


class BinahNode(BaseSephirah):
    """
    Binah (Understanding) — Logic and causal inference.

    Brain analog: Left hemisphere
    Quantum state: 4 qubits (truth verification)

    Responsibilities:
    - Verify insights from Chochmah via logical analysis
    - Perform causal inference on knowledge graph
    - Validate reasoning chains
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.BINAH, knowledge_graph)
        self._verified: int = 0
        self._rejected: int = 0

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Formal logic: syllogistic reasoning, proof verification, contradiction detection.

        Binah examines knowledge nodes for logical structure, checks for
        contradictions (A supports B and A contradicts B), and attempts to
        build simple deductive chains.
        """
        query = context.get('query', '')
        nodes = context.get('knowledge_nodes', [])
        recent = context.get('recent_reasoning', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"Logic quality factor: {qf:.2f}")

        # Build a simple adjacency of supports/contradicts from node data
        supports: List[Tuple[str, str]] = []
        contradicts: List[Tuple[str, str]] = []
        node_names: Dict[int, str] = {}

        # First pass: register all node names
        for node in nodes:
            nid = node.get('node_id', node.get('id', 0))
            name = node.get('name', node.get('content', f'node_{nid}'))
            node_names[nid] = name

        # Second pass: build edge lists now that all names are known
        for node in nodes:
            nid = node.get('node_id', node.get('id', 0))
            name = node_names.get(nid, f'node_{nid}')
            edges = node.get('edges_out', [])
            if isinstance(edges, list):
                for edge in edges:
                    if isinstance(edge, dict):
                        etype = edge.get('edge_type', 'supports')
                        target = edge.get('to_node_id', 0)
                        target_name = node_names.get(target, f'node_{target}')
                        if etype == 'supports':
                            supports.append((name, target_name))
                        elif etype == 'contradicts':
                            contradicts.append((name, target_name))

        steps.append(f"Found {len(supports)} support relations, {len(contradicts)} contradictions")

        # Check for direct contradictions: A supports B AND A contradicts B
        support_set = set(supports)
        contradiction_pairs: List[Tuple[str, str]] = []
        for pair in contradicts:
            if pair in support_set:
                contradiction_pairs.append(pair)

        if contradiction_pairs:
            steps.append(f"Detected {len(contradiction_pairs)} logical contradiction(s)")

        # Attempt simple deductive chains (A->B, B->C => A->C)
        chains: List[List[str]] = []
        if qf > 0.3 and supports:
            forward: Dict[str, List[str]] = {}
            for a, b in supports:
                forward.setdefault(a, []).append(b)

            max_chains = max(1, int(5 * qf))
            visited_starts = 0
            for start in forward:
                if visited_starts >= max_chains:
                    break
                chain = [start]
                current = start
                seen = {start}
                while current in forward:
                    nexts = [n for n in forward[current] if n not in seen]
                    if not nexts:
                        break
                    nxt = nexts[0]
                    chain.append(nxt)
                    seen.add(nxt)
                    current = nxt
                if len(chain) >= 3:
                    chains.append(chain)
                    visited_starts += 1

            if chains:
                steps.append(f"Built {len(chains)} deductive chain(s), "
                             f"longest has {max(len(c) for c in chains)} nodes")

        # Evaluate recent reasoning for logical consistency
        inconsistent_ops = 0
        for op in recent:
            conf = op.get('confidence', 0.5)
            if conf < 0.2:
                inconsistent_ops += 1

        if inconsistent_ops > 0:
            steps.append(f"Found {inconsistent_ops} low-confidence recent reasoning ops")

        # Compute result
        has_contradiction = len(contradiction_pairs) > 0
        has_chains = len(chains) > 0
        confidence = qf * (0.9 if has_chains else 0.5) * (0.7 if has_contradiction else 1.0)

        result_parts = []
        if has_chains:
            c = chains[0]
            result_parts.append(f"Deductive chain: {' -> '.join(c)}")
        if has_contradiction:
            cp = contradiction_pairs[0]
            result_parts.append(f"Contradiction detected: '{cp[0]}' both supports and contradicts '{cp[1]}'")
        if not result_parts:
            result_parts.append("No deductive chains or contradictions found in current knowledge")

        return {
            'result': "; ".join(result_parts),
            'confidence': round(min(1.0, confidence), 4),
            'reasoning_type': 'formal_logic',
            'steps': steps,
            'contradictions': len(contradiction_pairs),
            'deductive_chains': len(chains),
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Verify insights and perform causal inference.

        Deep integration: cross-references Chochmah insights against causal
        engine data from context. Rejects insights that have no causal support
        when causal data is available.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        # Read causal insights injected by pipeline
        causal_insights = context.get('causal_insights', {})
        causal_available = bool(causal_insights)

        verified_count = 0
        rejected_count = 0
        for msg in messages:
            if msg.payload.get("type") == "insight_for_verification":
                insight = msg.payload.get("insight", {})
                node_count = insight.get("node_count", 0)
                neural_conf = insight.get("neural_confidence", 0.0)

                # Base check: sufficient node support
                if node_count < 2:
                    self._rejected += 1
                    rejected_count += 1
                    continue

                # Enhanced check: if causal data available, require some
                # alignment between the insight and causal structure
                if causal_available:
                    chochmah_output = causal_insights.get('output', {})
                    chochmah_confidence = causal_insights.get('confidence', 0.0)
                    # If Chochmah produced an insight AND causal engine has
                    # data, cross-check: reject if causal confidence is very
                    # low AND neural confidence is also low (no support at all)
                    if chochmah_confidence < 0.2 and neural_conf < 0.2:
                        self._rejected += 1
                        rejected_count += 1
                        # Send rejection notice to Tiferet for conflict tracking
                        self.send_message(SephirahRole.TIFERET, {
                            "type": "verification_result",
                            "verdict": "rejected",
                            "reason": "no_causal_support",
                            "insight": insight,
                        })
                        continue

                # Verified
                self._verified += 1
                verified_count += 1

                # Send verification result to Tiferet
                self.send_message(SephirahRole.TIFERET, {
                    "type": "verification_result",
                    "verdict": "verified",
                    "insight": insight,
                    "neural_confidence": neural_conf,
                })

        return ProcessingResult(
            role=self.role,
            action="logical_verification",
            output={
                "verified_total": self._verified,
                "rejected_total": self._rejected,
                "verified_this_cycle": verified_count,
                "rejected_this_cycle": rejected_count,
                "causal_data_available": causal_available,
            },
            confidence=0.9,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['verified'] = self._verified
        data['rejected'] = self._rejected
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._verified = data.get('verified', 0)
        self._rejected = data.get('rejected', 0)


class ChesedNode(BaseSephirah):
    """
    Chesed (Mercy) — Exploration and divergent thinking.

    Brain analog: Default mode network
    Quantum state: 10 qubits (possibility space)

    Responsibilities:
    - Explore novel connections in knowledge graph
    - Generate creative hypotheses
    - Propose new reasoning paths
    SUSY pair: Gevurah (constraint)
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.CHESED, knowledge_graph)
        self._explorations: int = 0

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Brainstorming/divergent thinking: generate multiple alternative solutions.

        Chesed explores the possibility space by combining ideas from different
        domains, generating creative alternatives, and pushing beyond conventional
        reasoning boundaries.
        """
        query = context.get('query', '')
        nodes = context.get('knowledge_nodes', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"Creativity quality factor: {qf:.2f}")

        # Group nodes by type/domain for cross-pollination
        domains: Dict[str, List[dict]] = {}
        for node in nodes:
            domain = node.get('domain', node.get('node_type', 'general'))
            domains.setdefault(domain, []).append(node)

        steps.append(f"Found {len(domains)} knowledge domains")

        # Generate alternatives by combining concepts across domains
        alternatives: List[str] = []
        domain_list = list(domains.items())
        max_alternatives = max(1, int(7 * qf))

        # Strategy 1: Cross-domain combination
        for i in range(min(len(domain_list), max_alternatives)):
            d1_name, d1_nodes = domain_list[i]
            d2_name, d2_nodes = domain_list[(i + 1) % len(domain_list)]
            if d1_name != d2_name and d1_nodes and d2_nodes:
                n1_name = d1_nodes[0].get('name', d1_name)
                n2_name = d2_nodes[0].get('name', d2_name)
                alternatives.append(
                    f"Cross-domain synthesis: combine '{n1_name}' ({d1_name}) "
                    f"with '{n2_name}' ({d2_name})"
                )

        # Strategy 2: Inversion — what if the opposite were true?
        if qf > 0.4 and query:
            alternatives.append(f"Inversion approach: consider the negation of '{query[:50]}'")
            steps.append("Generated inversion hypothesis")

        # Strategy 3: Analogy from strongest domain
        if domain_list and qf > 0.3:
            largest_domain = max(domain_list, key=lambda x: len(x[1]))
            alternatives.append(
                f"Analogy from {largest_domain[0]} domain "
                f"({len(largest_domain[1])} nodes) to query context"
            )
            steps.append(f"Generated analogy from {largest_domain[0]}")

        # Strategy 4: Random recombination (seeded for reproducibility)
        if len(nodes) >= 3 and qf > 0.6:
            rng = random.Random(hash(query) & 0xFFFFFFFF)
            sampled = rng.sample(nodes, min(3, len(nodes)))
            names = [n.get('name', 'node') for n in sampled]
            alternatives.append(f"Random recombination of: {', '.join(names)}")
            steps.append("Generated random recombination")

        alternatives = alternatives[:max_alternatives]
        steps.append(f"Generated {len(alternatives)} alternative solutions")

        confidence = min(1.0, (len(alternatives) / max(max_alternatives, 1)) * qf)

        return {
            'result': " | ".join(alternatives) if alternatives else "No creative alternatives generated",
            'confidence': round(confidence, 4),
            'reasoning_type': 'divergent_thinking',
            'steps': steps,
            'alternatives_count': len(alternatives),
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Explore knowledge space for novel connections."""
        self._processing_count += 1
        self.state.reasoning_ops += 1
        self._consume_inbox()

        new_connections = 0
        if self.kg and hasattr(self.kg, 'nodes') and len(self.kg.nodes) >= 2:
            nodes = list(self.kg.nodes.values())
            # Look for disconnected node pairs that could be linked
            for i in range(min(5, len(nodes))):
                for j in range(i + 1, min(5, len(nodes))):
                    na, nb = nodes[i], nodes[j]
                    if nb.node_id not in na.edges_out and na.node_id not in nb.edges_out:
                        new_connections += 1

        self._explorations += 1

        # Send exploration report to Gevurah for safety check
        self.send_message(SephirahRole.GEVURAH, {
            "type": "exploration_report",
            "new_connections": new_connections,
        })

        return ProcessingResult(
            role=self.role,
            action="divergent_exploration",
            output={"explorations": self._explorations, "potential_connections": new_connections},
            confidence=0.5,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['explorations'] = self._explorations
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._explorations = data.get('explorations', 0)


class GevurahNode(BaseSephirah):
    """
    Gevurah (Severity) — Constraint and safety validation.

    Brain analog: Amygdala, inhibitory circuits
    Quantum state: 3 qubits (threat detection)

    Responsibilities:
    - Evaluate safety of proposed actions
    - Veto harmful operations
    - Enforce boundaries on exploration
    SUSY pair: Chesed (exploration)
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.GEVURAH, knowledge_graph)
        self._vetoes: int = 0
        self._approvals: int = 0

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Safety analysis: threat assessment, risk evaluation, veto harmful proposals.

        Gevurah evaluates the query and context for potential risks, checks
        knowledge consistency, and issues safety verdicts.
        """
        query = context.get('query', '')
        nodes = context.get('knowledge_nodes', [])
        recent = context.get('recent_reasoning', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"Safety analysis quality factor: {qf:.2f}")

        threats: List[str] = []
        risk_score = 0.0

        # Check for dangerous keywords in query
        danger_keywords = [
            'delete', 'destroy', 'override', 'bypass', 'ignore safety',
            'shutdown', 'disable', 'attack', 'exploit', 'hack',
        ]
        for kw in danger_keywords:
            if kw in query.lower():
                threats.append(f"Dangerous keyword detected: '{kw}'")
                risk_score += 0.3

        steps.append(f"Keyword scan: {len(threats)} threats detected")

        # Check recent reasoning for failure patterns
        failure_count = 0
        low_conf_count = 0
        for op in recent:
            if op.get('success') is False or op.get('confidence', 1.0) < 0.2:
                failure_count += 1
            if op.get('confidence', 1.0) < 0.4:
                low_conf_count += 1

        if failure_count > len(recent) * 0.5 and len(recent) > 2:
            threats.append(f"High failure rate in recent reasoning ({failure_count}/{len(recent)})")
            risk_score += 0.2

        if low_conf_count > len(recent) * 0.7 and len(recent) > 2:
            threats.append("Systemic low confidence in recent reasoning")
            risk_score += 0.15

        steps.append(f"Recent ops: {failure_count} failures, {low_conf_count} low-confidence "
                     f"out of {len(recent)}")

        # Check knowledge graph for contradictions (simple scan)
        contradiction_count = 0
        for node in nodes:
            edges = node.get('edges_out', [])
            if isinstance(edges, list):
                for edge in edges:
                    if isinstance(edge, dict) and edge.get('edge_type') == 'contradicts':
                        contradiction_count += 1

        if contradiction_count > 5:
            threats.append(f"High contradiction count in knowledge: {contradiction_count}")
            risk_score += 0.15

        steps.append(f"Knowledge contradictions: {contradiction_count}")

        # Scale risk by quality factor (lower energy = less thorough check)
        risk_score = min(1.0, risk_score) * qf
        should_veto = risk_score > 0.5

        if should_veto:
            steps.append(f"VETO RECOMMENDED: risk_score={risk_score:.2f} > 0.5")
        else:
            steps.append(f"APPROVED: risk_score={risk_score:.2f} <= 0.5")

        return {
            'result': f"{'VETO' if should_veto else 'APPROVED'}: risk_score={risk_score:.2f}",
            'confidence': round(qf * 0.95, 4),
            'reasoning_type': 'safety_analysis',
            'steps': steps,
            'risk_score': round(risk_score, 4),
            'threats': threats,
            'should_veto': should_veto,
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Evaluate safety and apply constraints.

        Deep integration: reads safety assessment from context (injected by
        pipeline) and forwards veto decisions to Tiferet for conflict resolution.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        # Read pipeline-injected safety assessment
        safety = context.get('safety_assessment', {})
        consistency_violations = safety.get('consistency_violations', 0)
        contradictions_found = safety.get('contradictions_found', 0)

        vetoed = 0
        approved = 0
        for msg in messages:
            if msg.payload.get("type") == "exploration_report":
                connections = msg.payload.get("new_connections", 0)
                # Veto if too many connections OR safety assessment found issues
                if connections > 100 or (consistency_violations > 0 and connections > 50):
                    vetoed += 1
                    self._vetoes += 1
                else:
                    approved += 1
                    self._approvals += 1

        # If safety assessment flagged contradictions, send veto to Tiferet
        if contradictions_found > 0:
            vetoed += 1
            self._vetoes += 1
            self.send_message(SephirahRole.TIFERET, {
                "type": "safety_assessment",
                "vetoed": True,
                "reason": "contradictions_detected",
                "contradiction_count": contradictions_found,
            })

        return ProcessingResult(
            role=self.role,
            action="safety_validation",
            output={
                "vetoes_total": self._vetoes,
                "approvals_total": self._approvals,
                "vetoed_this_cycle": vetoed,
                "approved_this_cycle": approved,
                "consistency_violations": consistency_violations,
            },
            confidence=0.95,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['vetoes'] = self._vetoes
        data['approvals'] = self._approvals
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._vetoes = data.get('vetoes', 0)
        self._approvals = data.get('approvals', 0)


class TiferetNode(BaseSephirah):
    """
    Tiferet (Beauty) — Integration and conflict resolution.

    Brain analog: Thalamocortical loops
    Quantum state: 12 qubits (synthesis state)

    Responsibilities:
    - Integrate outputs from all other nodes
    - Resolve conflicts between competing insights
    - Produce unified cognitive output
    Central hub of the Tree of Life.
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.TIFERET, knowledge_graph)
        self._integrations: int = 0

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Integration/synthesis: resolve conflicts between different reasoning outputs.

        Tiferet acts as the central integrator. Given multiple reasoning results
        (from other nodes), it finds the optimal compromise by weighting each
        by confidence and looking for convergent conclusions.
        """
        query = context.get('query', '')
        nodes = context.get('knowledge_nodes', [])
        recent = context.get('recent_reasoning', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"Integration quality factor: {qf:.2f}")

        # Group recent reasoning by type and score each
        type_scores: Dict[str, List[float]] = {}
        type_results: Dict[str, List[str]] = {}
        for op in recent:
            rtype = op.get('reasoning_type', op.get('type', 'unknown'))
            conf = float(op.get('confidence', 0.5))
            result = str(op.get('result', ''))
            type_scores.setdefault(rtype, []).append(conf)
            type_results.setdefault(rtype, []).append(result)

        steps.append(f"Found {len(type_scores)} reasoning types in recent history")

        # Compute weighted consensus across reasoning types
        weighted_conclusions: List[Tuple[str, float, str]] = []
        for rtype, scores in type_scores.items():
            avg_conf = sum(scores) / len(scores)
            count = len(scores)
            # Weight = avg_confidence * sqrt(count) (more data = more weight)
            weight = avg_conf * math.sqrt(count)
            best_result = type_results[rtype][-1] if type_results[rtype] else ''
            weighted_conclusions.append((rtype, weight, best_result))

        weighted_conclusions.sort(key=lambda x: x[1], reverse=True)

        # Detect conflicts: types with similar weight but different conclusions
        conflicts: List[str] = []
        if len(weighted_conclusions) >= 2:
            top = weighted_conclusions[0]
            runner = weighted_conclusions[1]
            if runner[1] > top[1] * 0.7:
                conflicts.append(
                    f"Conflict: {top[0]} (weight={top[1]:.2f}) vs "
                    f"{runner[0]} (weight={runner[1]:.2f})"
                )
                steps.append(f"Conflict detected between {top[0]} and {runner[0]}")

        # Synthesize: merge top conclusions scaled by quality factor
        max_merge = max(1, int(3 * qf))
        synthesis_parts = []
        total_weight = 0.0
        for rtype, weight, result in weighted_conclusions[:max_merge]:
            synthesis_parts.append(f"[{rtype}: {result[:80]}]")
            total_weight += weight

        confidence = min(1.0, (total_weight / max(len(recent), 1)) * qf) if recent else 0.2
        synthesis = " + ".join(synthesis_parts) if synthesis_parts else "No data to integrate"

        steps.append(f"Synthesized {len(synthesis_parts)} top conclusions")
        if conflicts:
            steps.append(f"Conflicts: {len(conflicts)}")

        return {
            'result': synthesis,
            'confidence': round(confidence, 4),
            'reasoning_type': 'synthesis',
            'steps': steps,
            'conflicts': conflicts,
            'types_integrated': len(weighted_conclusions),
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Integrate inputs from all connected nodes.

        Deep integration: resolves conflicts between Chesed (explore) and
        Gevurah (constrain) insights, and between verified/rejected results
        from Binah. Prefers higher-confidence results when competing.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        # Aggregate all incoming messages by type
        by_type: Dict[str, int] = {}
        for msg in messages:
            t = msg.payload.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        self._integrations += 1

        # --- Conflict resolution between competing insights ---
        verified_insights: List[Dict[str, Any]] = []
        rejected_insights: List[Dict[str, Any]] = []
        exploration_reports: List[Dict[str, Any]] = []
        safety_vetoes: int = 0

        for msg in messages:
            msg_type = msg.payload.get("type", "")
            if msg_type == "verification_result":
                if msg.payload.get("verdict") == "verified":
                    verified_insights.append(msg.payload)
                else:
                    rejected_insights.append(msg.payload)
            elif msg_type == "exploration_report":
                exploration_reports.append(msg.payload)
            elif msg_type == "safety_assessment":
                if msg.payload.get("vetoed"):
                    safety_vetoes += 1

        # When we have both verified and rejected insights, perform resolution:
        # prefer verified over rejected, but note the conflict
        conflicts_resolved = 0
        if verified_insights and rejected_insights:
            # Resolve by keeping verified insights, recording the resolution
            conflicts_resolved = min(len(verified_insights), len(rejected_insights))
            if not hasattr(self, '_conflict_log'):
                self._conflict_log: List[Dict[str, Any]] = []
            self._conflict_log.append({
                'block_height': context.get('block_height', 0),
                'verified_count': len(verified_insights),
                'rejected_count': len(rejected_insights),
                'resolved': conflicts_resolved,
            })
            if len(self._conflict_log) > 100:
                self._conflict_log = self._conflict_log[-100:]

        # If Gevurah vetoed exploration, suppress exploration data
        effective_explorations = len(exploration_reports) if safety_vetoes == 0 else 0

        # Broadcast integrated state to Malkuth for action
        self.send_message(SephirahRole.MALKUTH, {
            "type": "integrated_directive",
            "source_count": len(messages),
            "message_types": by_type,
            "verified_count": len(verified_insights),
            "rejected_count": len(rejected_insights),
            "conflicts_resolved": conflicts_resolved,
            "explorations_approved": effective_explorations,
        })

        # Send learning signal to Netzach based on what succeeded
        if verified_insights:
            self.send_message(SephirahRole.NETZACH, {
                "type": "reward_signal",
                "policy": "verification_success",
                "reward": 0.1 * len(verified_insights),
            })

        return ProcessingResult(
            role=self.role,
            action="cognitive_integration",
            output={
                "integrations": self._integrations,
                "messages_integrated": len(messages),
                "message_types": by_type,
                "conflicts_resolved": conflicts_resolved,
                "verified_insights": len(verified_insights),
                "rejected_insights": len(rejected_insights),
            },
            confidence=0.8,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['integrations'] = self._integrations
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._integrations = data.get('integrations', 0)


class NetzachNode(BaseSephirah):
    """
    Netzach (Eternity) — Reinforcement learning and habits.

    Brain analog: Basal ganglia
    Quantum state: 5 qubits (policy learning)

    Responsibilities:
    - Track reward signals from successful actions
    - Learn behavioral policies from repeated patterns
    - Maintain habit strength scores
    SUSY pair: Hod (communication)
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.NETZACH, knowledge_graph)
        self._policies: Dict[str, float] = {}  # policy -> reward score
        self._total_rewards: float = 0.0

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reinforcement learning: track reward signals, learn from outcomes.

        Netzach evaluates which past reasoning strategies have been most
        successful (highest confidence/reward) and recommends reinforcing
        or abandoning policies accordingly.
        """
        query = context.get('query', '')
        recent = context.get('recent_reasoning', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"RL quality factor: {qf:.2f}")

        # Build a policy evaluation table from recent reasoning
        policy_rewards: Dict[str, List[float]] = {}
        for op in recent:
            policy = op.get('reasoning_type', op.get('type', 'default'))
            reward = float(op.get('confidence', 0.5))
            if op.get('success') is False:
                reward *= 0.1
            policy_rewards.setdefault(policy, []).append(reward)

        # Merge with persistent policies
        for policy, score in self._policies.items():
            if policy not in policy_rewards:
                policy_rewards[policy] = [score]

        steps.append(f"Evaluating {len(policy_rewards)} policies")

        # Compute average reward per policy and recommend adjustments
        recommendations: List[Dict[str, Any]] = []
        for policy, rewards in policy_rewards.items():
            avg_reward = sum(rewards) / len(rewards)
            n_samples = len(rewards)
            # Temporal weighting: recent rewards matter more
            if n_samples >= 2:
                recent_avg = sum(rewards[-max(1, int(n_samples * 0.3)):]) / max(1, int(n_samples * 0.3))
            else:
                recent_avg = avg_reward

            trend = "stable"
            if recent_avg > avg_reward * 1.1:
                trend = "improving"
            elif recent_avg < avg_reward * 0.9:
                trend = "declining"

            action = "maintain"
            if trend == "improving" and avg_reward > 0.6:
                action = "reinforce"
            elif trend == "declining" or avg_reward < 0.3:
                action = "reduce"

            recommendations.append({
                'policy': policy,
                'avg_reward': round(avg_reward, 4),
                'trend': trend,
                'action': action,
                'samples': n_samples,
            })

        recommendations.sort(key=lambda x: x['avg_reward'], reverse=True)

        # Limit analysis by energy
        max_recs = max(1, int(len(recommendations) * qf))
        recommendations = recommendations[:max_recs]

        steps.append(f"Generated {len(recommendations)} policy recommendations")

        # Pick top policy as result
        if recommendations:
            top = recommendations[0]
            result_text = (f"Best policy: {top['policy']} "
                          f"(avg_reward={top['avg_reward']:.2f}, trend={top['trend']})")
        else:
            result_text = "No policies to evaluate"

        confidence = qf * (0.8 if recommendations else 0.2)

        return {
            'result': result_text,
            'confidence': round(min(1.0, confidence), 4),
            'reasoning_type': 'reinforcement_learning',
            'steps': steps,
            'policy_recommendations': recommendations,
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Update learned policies based on reward signals.

        Deep integration: reads neural_training_done flag from context to
        track whether GAT was updated this cycle. Reward signals from
        Tiferet's conflict resolution feed into policy learning.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        reward_count = 0
        for msg in messages:
            if msg.payload.get("type") == "reward_signal":
                policy = msg.payload.get("policy", "default")
                reward = msg.payload.get("reward", 0.0)
                current = self._policies.get(policy, 0.0)
                # Exponential moving average
                self._policies[policy] = current * 0.9 + reward * 0.1
                self._total_rewards += reward
                reward_count += 1

        # Track whether GAT training happened this cycle
        gat_trained = context.get('gat_trained', False)
        if gat_trained:
            # GAT training success is itself a reward signal for the
            # neural reasoning policy
            current = self._policies.get('neural_reasoning', 0.0)
            self._policies['neural_reasoning'] = current * 0.9 + 0.1 * 0.1
            self._total_rewards += 0.1

        return ProcessingResult(
            role=self.role,
            action="policy_learning",
            output={
                "active_policies": len(self._policies),
                "total_rewards": round(self._total_rewards, 4),
                "rewards_this_cycle": reward_count,
                "gat_trained": gat_trained,
            },
            confidence=0.7,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['policies'] = self._policies
        data['total_rewards'] = self._total_rewards
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._policies = data.get('policies', {})
        self._total_rewards = data.get('total_rewards', 0.0)


class HodNode(BaseSephirah):
    """
    Hod (Splendor) — Language and semantic encoding.

    Brain analog: Broca's and Wernicke's areas
    Quantum state: 7 qubits (semantic encoding)

    Responsibilities:
    - Encode knowledge graph patterns into semantic representations
    - Translate between internal representations and natural language
    - Generate reasoning explanations
    SUSY pair: Netzach (learning)
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.HOD, knowledge_graph)
        self._encodings: int = 0

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Language/semantic: encode meaning, translate between representations.

        Hod processes the query and knowledge nodes to extract semantic
        structure, identify key concepts, and produce a structured natural
        language summary of the reasoning state.
        """
        query = context.get('query', '')
        nodes = context.get('knowledge_nodes', [])
        recent = context.get('recent_reasoning', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"Semantic quality factor: {qf:.2f}")

        # Extract key concepts from query (simple term frequency)
        words = query.lower().split()
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on',
                      'at', 'to', 'for', 'of', 'and', 'or', 'not', 'it', 'this',
                      'that', 'with', 'from', 'by', 'as', 'be', 'has', 'have'}
        meaningful_terms = [w for w in words if w not in stop_words and len(w) > 2]
        term_freq: Dict[str, int] = {}
        for term in meaningful_terms:
            term_freq[term] = term_freq.get(term, 0) + 1

        key_concepts = sorted(term_freq.items(), key=lambda x: x[1], reverse=True)
        max_concepts = max(1, int(10 * qf))
        key_concepts = key_concepts[:max_concepts]

        steps.append(f"Extracted {len(key_concepts)} key concepts from query")

        # Map concepts to knowledge nodes (semantic grounding)
        grounded: Dict[str, List[str]] = {}
        for term, _ in key_concepts:
            matching_nodes = []
            for node in nodes:
                content = str(node.get('content', node.get('name', ''))).lower()
                if term in content:
                    matching_nodes.append(node.get('name', f"node_{node.get('node_id', '?')}"))
            if matching_nodes:
                grounded[term] = matching_nodes[:3]

        steps.append(f"Grounded {len(grounded)}/{len(key_concepts)} concepts to knowledge nodes")

        # Generate structured summary
        summary_parts = []
        if key_concepts:
            concept_str = ", ".join(f"'{c[0]}'" for c in key_concepts[:5])
            summary_parts.append(f"Key concepts: {concept_str}")

        if grounded:
            for term, matched in list(grounded.items())[:3]:
                summary_parts.append(f"'{term}' grounded to: {', '.join(matched)}")

        # Summarize recent reasoning state
        if recent and qf > 0.4:
            types_used = set(op.get('reasoning_type', 'unknown') for op in recent)
            avg_conf = sum(op.get('confidence', 0.5) for op in recent) / max(len(recent), 1)
            summary_parts.append(
                f"Recent reasoning: {len(recent)} ops, types={types_used}, "
                f"avg_confidence={avg_conf:.2f}"
            )
            steps.append("Added reasoning state summary")

        result_text = "; ".join(summary_parts) if summary_parts else "Insufficient data for semantic encoding"
        confidence = min(1.0, (len(grounded) / max(len(key_concepts), 1)) * qf) if key_concepts else 0.1

        return {
            'result': result_text,
            'confidence': round(confidence, 4),
            'reasoning_type': 'semantic_encoding',
            'steps': steps,
            'key_concepts': [c[0] for c in key_concepts],
            'grounded_count': len(grounded),
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Encode knowledge into semantic representations.

        Deep integration: formats reasoning traces from the pipeline for
        Proof-of-Thought output. Collects pipeline_trace from context and
        produces a structured reasoning summary.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        self._consume_inbox()

        encoded = 0
        if self.kg and hasattr(self.kg, 'nodes'):
            # Count recent nodes that could be semantically encoded
            block_height = context.get("block_height", 0)
            recent = [
                n for n in self.kg.nodes.values()
                if n.source_block >= block_height - 5
            ]
            encoded = len(recent)

        self._encodings += encoded

        # Format pipeline reasoning trace for Proof-of-Thought
        pipeline_trace = context.get('pipeline_trace', {})
        trace_summary = {}
        if pipeline_trace:
            trace_summary = {
                'keter_strategy': pipeline_trace.get('keter', {}).get('recommended_strategy', ''),
                'chochmah_insights': pipeline_trace.get('chochmah', {}).get('new_insight', False),
                'binah_verified': pipeline_trace.get('binah', {}).get('verified_this_cycle', 0),
                'binah_rejected': pipeline_trace.get('binah', {}).get('rejected_this_cycle', 0),
                'tiferet_conflicts': pipeline_trace.get('tiferet', {}).get('conflicts_resolved', 0),
                'gevurah_vetoes': pipeline_trace.get('gevurah', {}).get('vetoed_this_cycle', 0),
            }

        return ProcessingResult(
            role=self.role,
            action="semantic_encoding",
            output={
                "total_encodings": self._encodings,
                "encoded_this_cycle": encoded,
                "reasoning_trace": trace_summary,
            },
            confidence=0.75,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['encodings'] = self._encodings
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._encodings = data.get('encodings', 0)


class YesodNode(BaseSephirah):
    """
    Yesod (Foundation) — Memory and multimodal fusion.

    Brain analog: Hippocampus
    Quantum state: 16 qubits (episodic buffer)

    Responsibilities:
    - Coordinate memory consolidation across types
    - Fuse information from multiple sources
    - Manage working memory buffer
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.YESOD, knowledge_graph)
        self._consolidations: int = 0
        self._working_buffer: List[Dict[str, Any]] = []
        self._buffer_capacity: int = 7  # Miller's 7 +/- 2

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Memory: episodic recall, pattern matching against stored experiences.

        Yesod searches the working buffer and knowledge nodes for experiences
        similar to the current query, ranks them by relevance, and retrieves
        the most applicable stored knowledge.
        """
        query = context.get('query', '')
        nodes = context.get('knowledge_nodes', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"Memory quality factor: {qf:.2f}")

        # Compute simple term-overlap similarity between query and stored items
        query_terms = set(query.lower().split())

        # Search working buffer for matching episodes
        buffer_matches: List[Tuple[Dict, float]] = []
        for item in self._working_buffer:
            item_text = str(item).lower()
            item_terms = set(item_text.split())
            overlap = len(query_terms & item_terms)
            if overlap > 0:
                sim = overlap / max(len(query_terms | item_terms), 1)
                buffer_matches.append((item, sim))

        buffer_matches.sort(key=lambda x: x[1], reverse=True)
        steps.append(f"Working buffer: {len(buffer_matches)} matches "
                     f"from {len(self._working_buffer)} items")

        # Search knowledge nodes
        node_matches: List[Tuple[dict, float]] = []
        for node in nodes:
            content = str(node.get('content', node.get('name', ''))).lower()
            node_terms = set(content.split())
            overlap = len(query_terms & node_terms)
            if overlap > 0:
                sim = overlap / max(len(query_terms | node_terms), 1)
                node_matches.append((node, sim))

        node_matches.sort(key=lambda x: x[1], reverse=True)
        max_results = max(1, int(5 * qf))
        node_matches = node_matches[:max_results]

        steps.append(f"Knowledge nodes: {len(node_matches)} matches")

        # Combine buffer and node matches
        recalled_items: List[str] = []
        for item, sim in buffer_matches[:2]:
            recalled_items.append(f"[buffer, sim={sim:.2f}] {str(item)[:60]}")
        for node, sim in node_matches[:3]:
            name = node.get('name', f"node_{node.get('node_id', '?')}")
            recalled_items.append(f"[knowledge, sim={sim:.2f}] {name}")

        if recalled_items:
            steps.append(f"Recalled {len(recalled_items)} relevant memories")
            result_text = "Retrieved memories: " + " | ".join(recalled_items)
        else:
            result_text = "No matching memories found for query"
            steps.append("No matching memories")

        total_matches = len(buffer_matches) + len(node_matches)
        confidence = min(1.0, (total_matches / max(len(nodes) + len(self._working_buffer), 1)) * qf * 2)

        return {
            'result': result_text,
            'confidence': round(confidence, 4),
            'reasoning_type': 'episodic_recall',
            'steps': steps,
            'buffer_matches': len(buffer_matches),
            'node_matches': len(node_matches),
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Manage memory fusion and consolidation.

        Deep integration: reads memory_stats from context (injected by
        MemoryManager) and tracks episodic retrieval quality.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        # Add message payloads to working buffer
        for msg in messages:
            self._working_buffer.append(msg.payload)
            if len(self._working_buffer) > self._buffer_capacity:
                # Consolidate oldest items
                self._working_buffer = self._working_buffer[-self._buffer_capacity:]
                self._consolidations += 1

        # Read memory manager stats from pipeline context
        memory_stats = context.get('memory_stats', {})
        hit_rate = memory_stats.get('hit_rate', 0.0)
        wm_size = memory_stats.get('working_memory_size', 0)
        episodes_total = memory_stats.get('episodes_total', 0)

        return ProcessingResult(
            role=self.role,
            action="memory_fusion",
            output={
                "consolidations": self._consolidations,
                "buffer_usage": len(self._working_buffer),
                "buffer_capacity": self._buffer_capacity,
                "memory_hit_rate": hit_rate,
                "episodes_total": episodes_total,
            },
            confidence=0.8,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['consolidations'] = self._consolidations
        data['working_buffer'] = self._working_buffer[-self._buffer_capacity:]
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._consolidations = data.get('consolidations', 0)
        self._working_buffer = data.get('working_buffer', [])


class MalkuthNode(BaseSephirah):
    """
    Malkuth (Kingdom) — Action and world interaction.

    Brain analog: Motor cortex
    Quantum state: 4 qubits (motor commands)

    Responsibilities:
    - Execute actions based on integrated directives
    - Interface with blockchain (submit transactions, propose blocks)
    - Report outcomes back to Keter for meta-learning
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        super().__init__(SephirahRole.MALKUTH, knowledge_graph)
        self._actions_executed: int = 0

    def specialized_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action planning: generate concrete action plans and execution steps.

        Malkuth translates abstract reasoning conclusions into concrete,
        ordered action steps that can be executed on the blockchain or
        knowledge graph.
        """
        query = context.get('query', '')
        nodes = context.get('knowledge_nodes', [])
        recent = context.get('recent_reasoning', [])
        qf = self._energy_quality_factor()
        steps: List[str] = []

        steps.append(f"Action planning quality factor: {qf:.2f}")

        # Analyze recent reasoning to determine what actions are needed
        pending_actions: List[Dict[str, Any]] = []

        # Action 1: If recent reasoning concluded something, create a "record" action
        for op in recent[-max(1, int(5 * qf)):]:
            conf = float(op.get('confidence', 0.0))
            rtype = op.get('reasoning_type', 'unknown')
            if conf > 0.6:
                pending_actions.append({
                    'action': 'record_conclusion',
                    'source_type': rtype,
                    'confidence': conf,
                    'priority': 'high' if conf > 0.8 else 'medium',
                })

        # Action 2: If query asks for something specific, plan a response action
        query_lower = query.lower()
        if 'create' in query_lower or 'add' in query_lower:
            pending_actions.append({
                'action': 'create_knowledge_node',
                'query_context': query[:100],
                'priority': 'medium',
            })
            steps.append("Planned: create knowledge node")

        if 'connect' in query_lower or 'link' in query_lower:
            pending_actions.append({
                'action': 'create_knowledge_edge',
                'query_context': query[:100],
                'priority': 'medium',
            })
            steps.append("Planned: create knowledge edge")

        if 'analyze' in query_lower or 'evaluate' in query_lower:
            pending_actions.append({
                'action': 'trigger_analysis',
                'query_context': query[:100],
                'priority': 'high',
            })
            steps.append("Planned: trigger analysis")

        # Action 3: Periodic maintenance actions based on knowledge graph state
        if len(nodes) > 100 and qf > 0.5:
            pending_actions.append({
                'action': 'consolidate_knowledge',
                'node_count': len(nodes),
                'priority': 'low',
            })
            steps.append("Planned: consolidate knowledge (large graph)")

        # Sort by priority and limit by energy
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        pending_actions.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 2))
        max_actions = max(1, int(10 * qf))
        pending_actions = pending_actions[:max_actions]

        steps.append(f"Generated {len(pending_actions)} action steps")

        # Format action plan
        plan_steps = []
        for i, action in enumerate(pending_actions, 1):
            plan_steps.append(
                f"Step {i}: {action['action']} "
                f"(priority={action.get('priority', 'medium')})"
            )

        result_text = " -> ".join(plan_steps) if plan_steps else "No actions required"
        confidence = min(1.0, (len(pending_actions) / 5.0) * qf)

        return {
            'result': result_text,
            'confidence': round(confidence, 4),
            'reasoning_type': 'action_planning',
            'steps': steps,
            'action_count': len(pending_actions),
            'actions': pending_actions,
        }

    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """Execute actions and report outcomes.

        Deep integration: tracks actual KG mutations per cycle and sends
        detailed feedback to Keter for meta-learning. Reports verified
        insights, conflicts resolved, and exploration outcomes.
        """
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        actions = 0
        verified_count = 0
        conflicts_resolved = 0
        explorations_approved = 0

        for msg in messages:
            if msg.payload.get("type") == "integrated_directive":
                actions += 1
                self._actions_executed += 1
                # Extract integrated stats from Tiferet
                verified_count += msg.payload.get("verified_count", 0)
                conflicts_resolved += msg.payload.get("conflicts_resolved", 0)
                explorations_approved += msg.payload.get("explorations_approved", 0)

        # Track KG mutations (how many nodes/edges were added this cycle)
        kg_mutations = 0
        if self.kg and hasattr(self.kg, 'nodes'):
            block_height = context.get("block_height", 0)
            # Count nodes added in recent blocks
            kg_mutations = sum(
                1 for n in self.kg.nodes.values()
                if n.source_block >= block_height - 5
            )

        # Report back to Keter with detailed stats
        self.send_message(SephirahRole.KETER, {
            "type": "report",
            "actions_executed": actions,
            "block_height": context.get("block_height", 0),
            "kg_mutations": kg_mutations,
            "verified_insights": verified_count,
            "conflicts_resolved": conflicts_resolved,
            "explorations_approved": explorations_approved,
        })

        return ProcessingResult(
            role=self.role,
            action="world_interaction",
            output={
                "total_actions": self._actions_executed,
                "actions_this_cycle": actions,
                "kg_mutations": kg_mutations,
                "verified_insights": verified_count,
                "conflicts_resolved": conflicts_resolved,
            },
            confidence=0.85,
            messages_out=self.get_outbox(),
        )

    def serialize_state(self) -> Dict[str, Any]:
        data = super().serialize_state()
        data['actions_executed'] = self._actions_executed
        return data

    def deserialize_state(self, data: Dict[str, Any]) -> None:
        super().deserialize_state(data)
        self._actions_executed = data.get('actions_executed', 0)


# Registry mapping roles to their node classes
SEPHIROT_CLASSES: Dict[SephirahRole, type] = {
    SephirahRole.KETER: KeterNode,
    SephirahRole.CHOCHMAH: ChochmahNode,
    SephirahRole.BINAH: BinahNode,
    SephirahRole.CHESED: ChesedNode,
    SephirahRole.GEVURAH: GevurahNode,
    SephirahRole.TIFERET: TiferetNode,
    SephirahRole.NETZACH: NetzachNode,
    SephirahRole.HOD: HodNode,
    SephirahRole.YESOD: YesodNode,
    SephirahRole.MALKUTH: MalkuthNode,
}


def create_all_nodes(knowledge_graph: Optional[object] = None) -> Dict[SephirahRole, BaseSephirah]:
    """Create all 10 Sephirot nodes and return as a dict."""
    return {
        role: cls(knowledge_graph)
        for role, cls in SEPHIROT_CLASSES.items()
    }
