"""Aether Tree SDK client — talk to the on-chain AI."""

from __future__ import annotations

from typing import Optional

import httpx

from aether_qbc.types import (
    AetherInfo,
    ChatResponse,
    ConversationSession,
    KnowledgeEdge,
    KnowledgeNode,
    PhiData,
)

_DEFAULT_BASE_URL = "https://api.qbc.network"
_DEFAULT_TIMEOUT = 30.0


class AetherClient:
    """Client for the Aether Tree REST API.

    Usage::

        client = AetherClient()
        response = client.chat("What is quantum entanglement?")
        print(response.text)
        print(f"Phi: {response.phi}")
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        token: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )
        self._session_id: Optional[str] = None

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> "AetherClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ── Chat ─────────────────────────────────────────────────────────

    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        deep: bool = False,
    ) -> ChatResponse:
        """Send a message to the Aether Tree and get a response.

        Args:
            message: The user message.
            session_id: Existing session ID (auto-created if None).
            deep: Request a deep query (higher cost, more reasoning).

        Returns:
            ChatResponse with text, reasoning trace, phi, and PoT hash.
        """
        sid = session_id or self._session_id
        if not sid:
            sid = self.create_session()

        resp = self._http.post(
            "/aether/chat/message",
            json={
                "session_id": sid,
                "message": message,
                "is_deep_query": deep,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        return ChatResponse(
            text=data.get("response", ""),
            reasoning_trace=data.get("reasoning_trace", []),
            phi=data.get("phi_at_response", 0.0),
            pot_hash=data.get("proof_of_thought_hash", ""),
            fee_charged=data.get("fee_charged", "0"),
            emotional_state=data.get("emotional_state", {}),
            quality_score=data.get("quality_score", 0.0),
            session_id=sid,
            knowledge_nodes_referenced=data.get("knowledge_nodes_referenced", []),
        )

    def create_session(self, user_address: str = "") -> str:
        """Create a new chat session. Returns the session ID."""
        resp = self._http.post(
            "/aether/chat/session",
            json={"user_address": user_address},
        )
        resp.raise_for_status()
        sid = resp.json()["session_id"]
        self._session_id = sid
        return sid

    # ── Knowledge Graph ──────────────────────────────────────────────

    def search_knowledge(
        self, query: str, limit: int = 20
    ) -> list[KnowledgeNode]:
        """Search the Aether Tree knowledge graph."""
        resp = self._http.get(
            "/aether/knowledge/search",
            params={"q": query, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            KnowledgeNode(
                id=n["id"],
                content=n["content"],
                node_type=n.get("node_type", "assertion"),
                confidence=n.get("confidence", 0.0),
                source_block=n.get("source_block"),
                sephirot_name=n.get("sephirot_name"),
            )
            for n in data.get("results", data.get("nodes", []))
        ]

    def get_knowledge_graph(self, limit: int = 3300) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        """Retrieve a portion of the knowledge graph (nodes + edges)."""
        resp = self._http.get(
            "/aether/knowledge/graph",
            params={"limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()

        nodes = [
            KnowledgeNode(
                id=n["id"],
                content=n["content"],
                node_type=n.get("node_type", "assertion"),
                confidence=n.get("confidence", 0.0),
                source_block=n.get("source_block"),
                sephirot_name=n.get("sephirot_name"),
            )
            for n in data.get("nodes", [])
        ]
        edges = [
            KnowledgeEdge(
                source=e["source"],
                target=e["target"],
                edge_type=e.get("edge_type", "related"),
                weight=e.get("weight", 1.0),
            )
            for e in data.get("edges", [])
        ]
        return nodes, edges

    # ── Integration (Phi) ────────────────────────────────────────────

    def get_phi(self) -> PhiData:
        """Get the current Phi integration metric."""
        resp = self._http.get("/aether/consciousness")
        resp.raise_for_status()
        data = resp.json()
        return PhiData(
            phi=data.get("phi", 0.0),
            threshold=data.get("threshold", 3.0),
            above_threshold=data.get("above_threshold", False),
            integration=data.get("integration", 0.0),
            differentiation=data.get("differentiation", 0.0),
            knowledge_nodes=data.get("knowledge_nodes", 0),
            knowledge_edges=data.get("knowledge_edges", 0),
            blocks_processed=data.get("blocks_processed", 0),
            phi_version=data.get("phi_version", 4),
            gates_passed=data.get("gates_passed", 0),
            gates_total=data.get("gates_total", 10),
            gate_ceiling=data.get("gate_ceiling", 0.0),
            phi_micro=data.get("phi_micro"),
            phi_meso=data.get("phi_meso"),
            phi_macro=data.get("phi_macro"),
        )

    # ── Engine Info ──────────────────────────────────────────────────

    def get_info(self) -> AetherInfo:
        """Get high-level Aether Tree engine information."""
        resp = self._http.get("/aether/info")
        resp.raise_for_status()
        data = resp.json()
        kg = data.get("knowledge_graph", {})
        phi_data = data.get("phi", {})
        return AetherInfo(
            knowledge_nodes=kg.get("total_nodes", 0),
            knowledge_edges=kg.get("total_edges", 0),
            phi=phi_data.get("current_value", 0.0),
            phi_version=phi_data.get("version", 4),
            gates_passed=phi_data.get("gates_passed", 0),
            thought_proofs_generated=data.get("thought_proofs_generated", 0),
        )

    # ── Conversations ────────────────────────────────────────────────

    def get_conversations(
        self, user_id: str, limit: int = 20
    ) -> list[ConversationSession]:
        """Get conversation history for a user."""
        resp = self._http.get(
            f"/aether/conversations/{user_id}",
            params={"limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            ConversationSession(
                session_id=s["session_id"],
                user_address=s.get("user_address", ""),
                created_at=s.get("created_at", 0),
                last_active=s.get("last_active", 0),
                message_count=s.get("message_count", 0),
                title=s.get("title", ""),
                is_active=s.get("is_active", True),
            )
            for s in data.get("sessions", [])
        ]

    # ── Health ───────────────────────────────────────────────────────

    def health(self) -> dict:
        """Check the Aether Tree health."""
        resp = self._http.get("/health")
        resp.raise_for_status()
        return resp.json()
