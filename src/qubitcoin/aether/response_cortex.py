"""
Response Cortex — Orchestrates Global Workspace → Language Generation

This is the bridge between the cognitive cycle (Global Workspace) and
the user-facing response. It:
1. Builds a WorkspaceItem from the user's message + context
2. Runs the cognitive cycle (Sephirot compete, Tiferet synthesizes)
3. Passes synthesis to Hod for natural language generation
4. Returns the final response

This module REPLACES the template-based _kg_only_synthesize in chat.py.
No templates. Real cognitive processing.
"""
import time
from typing import Any, Dict, List, Optional

from .cognitive_processor import (
    CognitiveResponse,
    SoulPriors,
    StimulusType,
    WorkspaceItem,
)
from .global_workspace import GlobalWorkspace
from .soul import AetherSoul
from .sephirot import SephirahRole
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ResponseCortex:
    """Orchestrates the full cognitive pipeline for generating responses.

    Replaces the template-based intent routing with:
    stimulus → Global Workspace competition → Tiferet synthesis → Hod language

    The LLM is used as Hod's LANGUAGE FACULTY (tongue), not as the brain.
    The thinking comes from the Sephirot processors.
    """

    def __init__(
        self,
        workspace: GlobalWorkspace,
        soul: Optional[AetherSoul] = None,
        llm_adapter: Any = None,
    ) -> None:
        self.workspace = workspace
        self.soul = soul or AetherSoul()
        self.llm_adapter = llm_adapter
        self._response_count: int = 0
        self._avg_latency_ms: float = 0.0
        self._fallback_count: int = 0

    def generate_response(
        self,
        message: str,
        intent: str = "",
        entities: Optional[Dict[str, Any]] = None,
        knowledge_refs: Optional[List[int]] = None,
        session_context: Optional[Dict[str, Any]] = None,
        user_memories: Optional[Dict[str, str]] = None,
        conversation_context: str = "",
        emotional_state: Optional[Dict[str, Any]] = None,
        phi_value: float = 0.0,
        kg_node_count: int = 0,
        gates_passed: int = 0,
        is_deep_query: bool = False,
    ) -> Dict[str, Any]:
        """Generate a response using the full cognitive pipeline.

        Args:
            message: The user's message.
            intent: Detected intent category.
            entities: Extracted entities.
            knowledge_refs: Pre-matched KG node IDs.
            session_context: Session state dict.
            user_memories: Persistent user memories.
            conversation_context: Recent conversation history string.
            emotional_state: Current emotional state dict.
            phi_value: Current Phi integration metric.
            kg_node_count: Knowledge graph node count.
            gates_passed: AGI gates passed.
            is_deep_query: Whether to use deep reasoning.

        Returns:
            Dict with 'response', 'reasoning_trace', 'cognitive_cycle' keys.
        """
        t0 = time.monotonic()
        self._response_count += 1

        # Build the stimulus
        stimulus = WorkspaceItem(
            stimulus_type=StimulusType.USER_MESSAGE,
            content=message,
            context={
                "user_memories": user_memories or {},
                "conversation_history": conversation_context,
                "emotional_state": emotional_state or {},
                "phi_value": phi_value,
                "kg_node_count": kg_node_count,
                "gates_passed": gates_passed,
                "is_deep_query": is_deep_query,
                "session": session_context or {},
            },
            intent=intent,
            entities=entities or {},
            knowledge_refs=knowledge_refs or [],
            source="user_chat",
        )

        # Run the cognitive cycle
        if not self.workspace.has_cognitive_processors:
            # Fallback: no processors registered yet
            self._fallback_count += 1
            return self._fallback_response(message, intent)

        synthesis = self.workspace.run_cognitive_cycle(stimulus)

        # Pass synthesis to Hod for language generation
        response_text = self._voice_through_hod(synthesis, stimulus)

        elapsed_ms = (time.monotonic() - t0) * 1000
        self._avg_latency_ms = (
            self._avg_latency_ms * 0.9 + elapsed_ms * 0.1
        )

        return {
            "response": response_text,
            "reasoning_trace": synthesis.reasoning_trace,
            "cognitive_cycle": {
                "source_role": synthesis.source_role,
                "confidence": synthesis.confidence,
                "relevance": synthesis.relevance,
                "novelty": synthesis.novelty,
                "evidence_count": len(synthesis.evidence),
                "elapsed_ms": round(elapsed_ms, 1),
            },
        }

    def _voice_through_hod(
        self,
        synthesis: CognitiveResponse,
        stimulus: WorkspaceItem,
    ) -> str:
        """Pass the cognitive synthesis to Hod for natural language generation.

        Hod uses the LLM as its language faculty — turning THOUGHTS into WORDS.
        If Hod is not available or the LLM fails, construct response from
        the synthesis content directly.
        """
        hod = self.workspace.get_processor("hod")

        if hod and hasattr(hod, "generate_from_synthesis"):
            try:
                result = hod.generate_from_synthesis(
                    synthesis.to_dict(), stimulus
                )
                if result and len(result) > 20:
                    return result
            except Exception as e:
                logger.debug(f"Hod language generation failed: {e}")

        # Direct fallback: use synthesis content as-is
        # This is NOT a template — it's the actual reasoning output
        return self._construct_from_synthesis(synthesis)

    def _construct_from_synthesis(self, synthesis: CognitiveResponse) -> str:
        """Construct a response directly from synthesis content.

        This is the fallback when Hod/LLM is unavailable. It uses the
        actual reasoning content, not templates.
        """
        content = synthesis.content
        if not content or len(content) < 10:
            return (
                "I'm processing this, but my thoughts haven't fully "
                "crystallized yet. Could you rephrase or give me more context?"
            )

        # If synthesis produced good content, use it directly
        if len(content) >= 50:
            return content

        # For short synthesis, add reasoning context
        trace = synthesis.reasoning_trace
        if trace:
            trace_summary = "; ".join(
                t.get("content", t.get("step_type", ""))[:80]
                for t in trace[:3]
                if isinstance(t, dict)
            )
            if trace_summary:
                return f"{content}\n\n{trace_summary}"

        return content

    def _fallback_response(
        self,
        message: str,
        intent: str,
    ) -> Dict[str, Any]:
        """Fallback when no cognitive processors are registered.

        This should only happen during initialization. Returns a minimal
        response acknowledging the system is starting up.
        """
        return {
            "response": (
                "My cognitive processors are still initializing. "
                "I'll be able to think more clearly in a moment."
            ),
            "reasoning_trace": [],
            "cognitive_cycle": {
                "source_role": "fallback",
                "confidence": 0.1,
                "relevance": 0.5,
                "novelty": 0.0,
                "evidence_count": 0,
                "elapsed_ms": 0.0,
            },
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "response_count": self._response_count,
            "avg_latency_ms": round(self._avg_latency_ms, 1),
            "fallback_count": self._fallback_count,
            "workspace_stats": self.workspace.get_stats(),
        }
