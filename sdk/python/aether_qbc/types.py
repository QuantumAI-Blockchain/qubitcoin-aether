"""Data types for the Aether Tree SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChatResponse:
    """Response from the Aether Tree chat endpoint."""

    text: str
    reasoning_trace: list[str] = field(default_factory=list)
    phi: float = 0.0
    pot_hash: str = ""
    fee_charged: str = "0"
    emotional_state: dict[str, float] = field(default_factory=dict)
    quality_score: float = 0.0
    session_id: str = ""
    knowledge_nodes_referenced: list[int] = field(default_factory=list)


@dataclass
class KnowledgeNode:
    """A node in the Aether Tree knowledge graph."""

    id: int
    content: str
    node_type: str
    confidence: float
    source_block: Optional[int] = None
    sephirot_name: Optional[str] = None


@dataclass
class KnowledgeEdge:
    """An edge in the Aether Tree knowledge graph."""

    source: int
    target: int
    edge_type: str
    weight: float


@dataclass
class PhiData:
    """Integration metric (Phi) data from the Aether Tree."""

    phi: float
    threshold: float
    above_threshold: bool
    integration: float = 0.0
    differentiation: float = 0.0
    knowledge_nodes: int = 0
    knowledge_edges: int = 0
    blocks_processed: int = 0
    phi_version: int = 4
    gates_passed: int = 0
    gates_total: int = 10
    gate_ceiling: float = 0.0
    phi_micro: Optional[float] = None
    phi_meso: Optional[float] = None
    phi_macro: Optional[float] = None


@dataclass
class AetherInfo:
    """High-level Aether Tree engine information."""

    knowledge_nodes: int = 0
    knowledge_edges: int = 0
    phi: float = 0.0
    phi_version: int = 4
    gates_passed: int = 0
    thought_proofs_generated: int = 0


@dataclass
class ConversationSession:
    """A conversation session with the Aether Tree."""

    session_id: str
    user_address: str = ""
    created_at: int = 0
    last_active: int = 0
    message_count: int = 0
    title: str = ""
    is_active: bool = True
