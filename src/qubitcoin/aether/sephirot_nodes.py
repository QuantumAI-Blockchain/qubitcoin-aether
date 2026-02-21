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
        """Evaluate goals and form meta-level objectives."""
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        # Aggregate reports from other nodes
        reports = [m.payload for m in messages if m.payload.get("type") == "report"]

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

        # Form goals based on context
        goal = {
            "type": "goal",
            "priority": context.get("priority", "normal"),
            "block_height": context.get("block_height", 0),
        }
        self._goals.append(goal)
        if len(self._goals) > 50:
            self._goals = self._goals[-50:]

        # Broadcast goal to Tiferet (integration hub)
        self.send_message(SephirahRole.TIFERET, {
            "type": "goal_directive",
            "goal": goal,
        })

        return ProcessingResult(
            role=self.role,
            action="goal_formation",
            output={"goals": len(self._goals), "meta_patterns": len(self._meta_patterns)},
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
        """Discover patterns and generate intuitive insights."""
        self._processing_count += 1
        self.state.reasoning_ops += 1
        self._consume_inbox()

        insight = None
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
            output={"insights": len(self._insights), "new_insight": insight is not None},
            confidence=0.6,
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
        """Verify insights and perform causal inference."""
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        verified_count = 0
        for msg in messages:
            if msg.payload.get("type") == "insight_for_verification":
                # Simple verification: check if insight has sufficient support
                if msg.payload.get("insight", {}).get("node_count", 0) >= 2:
                    self._verified += 1
                    verified_count += 1
                else:
                    self._rejected += 1

        return ProcessingResult(
            role=self.role,
            action="logical_verification",
            output={
                "verified_total": self._verified,
                "rejected_total": self._rejected,
                "verified_this_cycle": verified_count,
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
        """Evaluate safety and apply constraints."""
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        vetoed = 0
        approved = 0
        for msg in messages:
            if msg.payload.get("type") == "exploration_report":
                connections = msg.payload.get("new_connections", 0)
                if connections > 100:
                    vetoed += 1
                    self._vetoes += 1
                else:
                    approved += 1
                    self._approvals += 1

        return ProcessingResult(
            role=self.role,
            action="safety_validation",
            output={
                "vetoes_total": self._vetoes,
                "approvals_total": self._approvals,
                "vetoed_this_cycle": vetoed,
                "approved_this_cycle": approved,
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
        """Integrate inputs from all connected nodes."""
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        # Aggregate all incoming messages by type
        by_type: Dict[str, int] = {}
        for msg in messages:
            t = msg.payload.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        self._integrations += 1

        # Broadcast integrated state to Malkuth for action
        self.send_message(SephirahRole.MALKUTH, {
            "type": "integrated_directive",
            "source_count": len(messages),
            "message_types": by_type,
        })

        return ProcessingResult(
            role=self.role,
            action="cognitive_integration",
            output={
                "integrations": self._integrations,
                "messages_integrated": len(messages),
                "message_types": by_type,
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
        """Update learned policies based on reward signals."""
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

        return ProcessingResult(
            role=self.role,
            action="policy_learning",
            output={
                "active_policies": len(self._policies),
                "total_rewards": round(self._total_rewards, 4),
                "rewards_this_cycle": reward_count,
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
        """Encode knowledge into semantic representations."""
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

        return ProcessingResult(
            role=self.role,
            action="semantic_encoding",
            output={"total_encodings": self._encodings, "encoded_this_cycle": encoded},
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
        """Manage memory fusion and consolidation."""
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

        return ProcessingResult(
            role=self.role,
            action="memory_fusion",
            output={
                "consolidations": self._consolidations,
                "buffer_usage": len(self._working_buffer),
                "buffer_capacity": self._buffer_capacity,
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
        """Execute actions and report outcomes."""
        self._processing_count += 1
        self.state.reasoning_ops += 1
        messages = self._consume_inbox()

        actions = 0
        for msg in messages:
            if msg.payload.get("type") == "integrated_directive":
                actions += 1
                self._actions_executed += 1

        # Report back to Keter
        if actions > 0:
            self.send_message(SephirahRole.KETER, {
                "type": "report",
                "actions_executed": actions,
                "block_height": context.get("block_height", 0),
            })

        return ProcessingResult(
            role=self.role,
            action="world_interaction",
            output={"total_actions": self._actions_executed, "actions_this_cycle": actions},
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
