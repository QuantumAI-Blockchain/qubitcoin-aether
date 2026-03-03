"""
Aether service route definitions.

All endpoints are prefixed with /aether/ to match the API gateway routing.
The API gateway at :5000 proxies /aether/* to this service at :5001.
"""

import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("qubitcoin.aether-service")


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_address: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    reasoning_trace: list = []
    phi_at_response: float = 0.0
    knowledge_nodes_referenced: list = []
    proof_of_thought_hash: str = ""


def register_routes(app: FastAPI) -> None:
    """Register all Aether endpoints."""

    @app.get("/health")
    async def health():
        from app import _aether_engine

        return {
            "status": "healthy" if _aether_engine else "degraded",
            "service": "aether",
        }

    @app.get("/aether/info")
    async def aether_info():
        from app import _aether_engine

        if not _aether_engine:
            return {"status": "initializing", "phi": 0.0}

        return {
            "status": "active",
            "phi": getattr(_aether_engine, "phi", 0.0),
            "phi_threshold": 3.0,
            "knowledge_nodes": len(
                getattr(
                    getattr(_aether_engine, "kg", None), "nodes", []
                )
            ),
            "knowledge_edges": len(
                getattr(
                    getattr(_aether_engine, "kg", None), "edges", []
                )
            ),
        }

    @app.get("/aether/phi")
    async def aether_phi():
        from app import _aether_engine

        phi = getattr(_aether_engine, "phi", 0.0) if _aether_engine else 0.0

        return {
            "phi": phi,
            "threshold": 3.0,
            "above_threshold": phi >= 3.0,
        }

    @app.get("/aether/phi/history")
    async def aether_phi_history(limit: int = 100):
        """Phi history from the Aether engine's internal measurements."""
        from app import _aether_engine

        # Try to get from engine's measurement history
        history = []
        if _aether_engine:
            measurements = getattr(_aether_engine, "phi_measurements", [])
            for m in measurements[-limit:]:
                history.append(
                    {
                        "block": getattr(m, "block_height", 0),
                        "phi": getattr(m, "phi_value", 0.0),
                        "nodes": getattr(m, "num_nodes", 0),
                        "edges": getattr(m, "num_edges", 0),
                    }
                )

        return {"history": history}

    @app.get("/aether/knowledge")
    async def aether_knowledge():
        from app import _aether_engine

        if not _aether_engine:
            return {"total_nodes": 0, "total_edges": 0}

        kg = getattr(_aether_engine, "kg", None)
        nodes = len(getattr(kg, "nodes", [])) if kg else 0
        edges = len(getattr(kg, "edges", [])) if kg else 0

        return {
            "total_nodes": nodes,
            "total_edges": edges,
            "node_types": ["assertion", "observation", "inference", "axiom"],
            "edge_types": [
                "supports",
                "contradicts",
                "derives",
                "requires",
                "refines",
            ],
        }

    @app.get("/aether/consciousness")
    async def aether_consciousness():
        from app import _aether_engine

        if not _aether_engine:
            return {
                "phi": 0.0,
                "threshold": 3.0,
                "above_threshold": False,
                "knowledge_nodes": 0,
                "knowledge_edges": 0,
                "consciousness_events": 0,
                "blocks_processed": 0,
            }

        kg = getattr(_aether_engine, "kg", None)

        return {
            "phi": getattr(_aether_engine, "phi", 0.0),
            "threshold": 3.0,
            "above_threshold": getattr(_aether_engine, "phi", 0.0) >= 3.0,
            "integration": getattr(_aether_engine, "integration_score", 0.0),
            "differentiation": getattr(
                _aether_engine, "differentiation_score", 0.0
            ),
            "knowledge_nodes": len(getattr(kg, "nodes", [])) if kg else 0,
            "knowledge_edges": len(getattr(kg, "edges", [])) if kg else 0,
            "consciousness_events": getattr(
                _aether_engine, "consciousness_event_count", 0
            ),
            "blocks_processed": getattr(
                _aether_engine, "blocks_processed", 0
            ),
        }

    @app.post("/aether/chat/message")
    async def aether_chat(request: ChatRequest):
        from app import _aether_engine

        if not _aether_engine:
            return ChatResponse(
                response="Aether Tree is still initializing. Please try again shortly.",
                phi_at_response=0.0,
            ).model_dump()

        try:
            # Use the Aether chat interface
            chat = getattr(_aether_engine, "chat", None)
            if chat:
                result = chat.process_message(
                    request.message, session_id=request.session_id
                )
                return {
                    "response": result.get("response", ""),
                    "reasoning_trace": result.get("reasoning_trace", []),
                    "phi_at_response": getattr(_aether_engine, "phi", 0.0),
                    "knowledge_nodes_referenced": result.get(
                        "knowledge_nodes", []
                    ),
                    "proof_of_thought_hash": result.get("proof_hash", ""),
                }
            else:
                return {
                    "response": "Chat interface not available.",
                    "phi_at_response": getattr(_aether_engine, "phi", 0.0),
                }
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "response": f"Error processing message: {str(e)}",
                "phi_at_response": 0.0,
            }

    @app.get("/aether/chat/history/{session_id}")
    async def aether_chat_history(session_id: str):
        from app import _aether_engine

        chat = getattr(_aether_engine, "chat", None) if _aether_engine else None
        if chat:
            history = chat.get_history(session_id)
            return {"session_id": session_id, "messages": history}

        return {"session_id": session_id, "messages": []}

    @app.get("/aether/reasoning/stats")
    async def aether_reasoning_stats():
        from app import _aether_engine

        if not _aether_engine:
            return {"total_operations": 0}

        return {
            "total_operations": getattr(
                _aether_engine, "reasoning_count", 0
            ),
            "deductive": getattr(_aether_engine, "deductive_count", 0),
            "inductive": getattr(_aether_engine, "inductive_count", 0),
            "abductive": getattr(_aether_engine, "abductive_count", 0),
        }

    @app.get("/aether/sephirot")
    async def aether_sephirot():
        from app import _aether_engine

        sephirot = (
            getattr(_aether_engine, "sephirot", None)
            if _aether_engine
            else None
        )
        if not sephirot:
            return {"nodes": [], "susy_pairs": [], "coherence": 0.0}

        nodes = []
        for name, node in getattr(sephirot, "nodes", {}).items():
            nodes.append(
                {
                    "name": name,
                    "role": getattr(node, "role", ""),
                    "energy": getattr(node, "energy", 0.0),
                    "quantum_state": getattr(node, "n_qubits", 0),
                }
            )

        return {
            "nodes": nodes,
            "susy_pairs": [
                {"expansion": "Chesed", "constraint": "Gevurah"},
                {"expansion": "Chochmah", "constraint": "Binah"},
                {"expansion": "Netzach", "constraint": "Hod"},
            ],
            "coherence": getattr(sephirot, "coherence", 0.0),
            "total_violations": getattr(sephirot, "violation_count", 0),
        }
