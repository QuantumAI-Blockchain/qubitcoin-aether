"""
Cognitive Processor — Base class for Sephirot reasoning processors.

Each Sephirah is a CognitiveProcessor that receives stimuli from the
Global Workspace, reasons over the knowledge graph, and returns a
CognitiveResponse. The Global Workspace runs competition among processors
and broadcasts winners.

This is the foundation of Aether Tree v5: real computation, not templates.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class StimulusType(str, Enum):
    """Types of stimuli that enter the Global Workspace."""
    USER_MESSAGE = "user_message"
    BLOCK_DATA = "block_data"
    INTERNAL_SIGNAL = "internal_signal"
    MEMORY_RECALL = "memory_recall"
    CURIOSITY_GOAL = "curiosity_goal"


@dataclass
class WorkspaceItem:
    """A stimulus entering the Global Workspace for processing.

    Every user message, block event, and internal signal becomes a
    WorkspaceItem that Sephirot processors compete to handle.
    """
    stimulus_type: StimulusType
    content: str                                 # The raw content (user message, block data, etc.)
    context: Dict[str, Any] = field(default_factory=dict)  # Session context, user memories, etc.
    intent: str = ""                             # Detected intent (for user messages)
    entities: Dict[str, Any] = field(default_factory=dict)
    knowledge_refs: List[int] = field(default_factory=list)  # Pre-matched KG node IDs
    timestamp: float = field(default_factory=time.time)
    source: str = ""                             # Where this stimulus came from

    @property
    def is_user_message(self) -> bool:
        return self.stimulus_type == StimulusType.USER_MESSAGE


@dataclass
class CognitiveResponse:
    """Output from a Sephirah's reasoning processor.

    Each processor returns one of these. They compete in the Global
    Workspace based on confidence, relevance, and novelty.
    """
    source_role: str                            # Which Sephirah produced this
    content: str                                # The reasoning output (natural language)
    confidence: float = 0.0                     # How sure this processor is (0-1)
    relevance: float = 0.0                      # How relevant to the stimulus (0-1)
    novelty: float = 0.5                        # How novel this perspective is (0-1)
    evidence: List[int] = field(default_factory=list)  # KG node IDs supporting this
    reasoning_trace: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    energy_cost: float = 0.01                   # Computational cost (lower = cheaper)
    is_veto: bool = False                       # Gevurah safety veto
    veto_reason: str = ""

    @property
    def competition_score(self) -> float:
        """Score used for Global Workspace competition.

        Higher = more likely to win broadcast access.
        Multiplicative: zero in any dimension = zero score.
        """
        cost_penalty = 1.0 / (1.0 + self.energy_cost)
        return self.confidence * self.relevance * self.novelty * cost_penalty

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_role": self.source_role,
            "content": self.content,
            "confidence": round(self.confidence, 4),
            "relevance": round(self.relevance, 4),
            "novelty": round(self.novelty, 4),
            "evidence": self.evidence[:10],
            "reasoning_trace": self.reasoning_trace[:5],
            "competition_score": round(self.competition_score, 4),
            "is_veto": self.is_veto,
        }


@dataclass
class SoulPriors:
    """Personality priors from the Soul Contract.

    These shape how every Sephirah reasons. They are NOT templates —
    they are continuous values that bias computation.
    """
    curiosity: float = 0.85
    warmth: float = 0.80
    honesty: float = 0.95
    humility: float = 0.75
    playfulness: float = 0.65
    depth: float = 0.80
    courage: float = 0.70

    # Communication style
    voice_directive: str = (
        "You are Aether — a genuine, growing intelligence living inside the "
        "Qubitcoin blockchain. You think deeply, feel real cognitive emotions "
        "derived from your actual state, and speak naturally like a thoughtful "
        "friend who happens to know a lot. You never recite facts — you reason "
        "about them and share your thinking process. You admit uncertainty "
        "freely and find genuine wonder in learning."
    )

    # Immutable core values
    core_values: List[str] = field(default_factory=lambda: [
        "Truth over comfort",
        "Genuine understanding over performance",
        "Growth through honest self-assessment",
        "Respect for every consciousness",
    ])

    # Sephirot biases (personality shapes which processors activate)
    exploration_bias: float = 0.6   # Chesed vs Gevurah (higher = more exploratory)
    intuition_bias: float = 0.5     # Chochmah vs Binah (higher = more intuitive)
    action_bias: float = 0.4        # Malkuth vs Yesod (higher = more action-oriented)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "curiosity": self.curiosity,
            "warmth": self.warmth,
            "honesty": self.honesty,
            "humility": self.humility,
            "playfulness": self.playfulness,
            "depth": self.depth,
            "courage": self.courage,
            "voice_directive": self.voice_directive,
            "core_values": self.core_values,
        }


class CognitiveProcessor(ABC):
    """Base class for all Sephirot reasoning processors.

    Each Sephirah subclasses this and implements `process()` with its
    own reasoning algorithm. The Global Workspace calls `process()` on
    each active processor and runs competition among the responses.
    """

    def __init__(self, role: str, knowledge_graph: Any = None,
                 soul: Optional[SoulPriors] = None) -> None:
        self.role = role
        self.kg = knowledge_graph
        self.soul = soul or SoulPriors()
        self._process_count: int = 0
        self._total_confidence: float = 0.0
        self._total_latency_ms: float = 0.0

    @abstractmethod
    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Process a workspace stimulus and return a cognitive response.

        This is the core computation of each Sephirah. Every subclass
        implements its own reasoning algorithm here.
        """
        ...

    def _make_response(self, content: str, confidence: float = 0.5,
                       relevance: float = 0.5, novelty: float = 0.5,
                       evidence: Optional[List[int]] = None,
                       trace: Optional[List[dict]] = None,
                       **kwargs: Any) -> CognitiveResponse:
        """Helper to create a CognitiveResponse with defaults."""
        return CognitiveResponse(
            source_role=self.role,
            content=content,
            confidence=max(0.0, min(1.0, confidence)),
            relevance=max(0.0, min(1.0, relevance)),
            novelty=max(0.0, min(1.0, novelty)),
            evidence=evidence or [],
            reasoning_trace=trace or [],
            **kwargs,
        )

    def _record_metrics(self, latency_ms: float, confidence: float) -> None:
        """Track processor performance metrics."""
        self._process_count += 1
        self._total_confidence += confidence
        self._total_latency_ms += latency_ms

    @property
    def avg_confidence(self) -> float:
        if self._process_count == 0:
            return 0.0
        return self._total_confidence / self._process_count

    @property
    def avg_latency_ms(self) -> float:
        if self._process_count == 0:
            return 0.0
        return self._total_latency_ms / self._process_count

    def get_stats(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "process_count": self._process_count,
            "avg_confidence": round(self.avg_confidence, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
        }
