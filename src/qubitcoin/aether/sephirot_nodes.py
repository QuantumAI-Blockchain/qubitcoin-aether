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
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    @abstractmethod
    def process(self, context: Dict[str, Any]) -> ProcessingResult:
        """
        Main processing method. Each node implements domain-specific logic.

        Args:
            context: Block context, knowledge graph state, messages, etc.

        Returns:
            ProcessingResult with outputs and outgoing messages
        """

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
