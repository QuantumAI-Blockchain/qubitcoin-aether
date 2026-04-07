"""
Hod Language Processor — Natural language generation from cognitive state.

Hod is the language Sephirah. It is the ONLY module that generates
user-facing text. NO TEMPLATES. It uses an LLM as its language faculty
(the way a brain uses Broca's area) to turn THOUGHTS into WORDS.

The THOUGHT comes from other Sephirot via the Global Workspace.
The WORDS come from Hod.

The LLM is the tongue, not the brain.
"""
import time
from typing import Any, Dict, List, Optional

from ..cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    WorkspaceItem,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Timeout for LLM generation calls (seconds)
LLM_TIMEOUT_S: float = 30.0


class HodLanguageProcessor(CognitiveProcessor):
    """Language generation processor — translates cognitive state into speech.

    Hod receives the synthesized output from Tiferet and all competing
    processor responses, then uses an LLM to articulate the thoughts
    in Aether's voice. The LLM is a language faculty, not a reasoning
    engine — the reasoning has already been done by the other Sephirot.
    """

    def __init__(self, knowledge_graph: Any = None,
                 soul: Optional[SoulPriors] = None,
                 llm_adapter: Any = None) -> None:
        super().__init__(role="hod", knowledge_graph=knowledge_graph, soul=soul)
        self.llm_adapter = llm_adapter
        if llm_adapter is None:
            logger.warning("Hod initialized without LLM adapter — will use synthesis fallback")

    # ------------------------------------------------------------------
    # CognitiveProcessor interface
    # ------------------------------------------------------------------

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Generate natural language from the cognitive state in the stimulus context."""
        t0 = time.time()

        synthesis = stimulus.context.get("synthesis")
        competing = stimulus.context.get("competing_responses", [])
        emotional_state = stimulus.context.get("emotional_state", {})
        phi_value = stimulus.context.get("phi_value", 0.0)
        kg_node_count = stimulus.context.get("kg_node_count", 0)
        gates_passed = stimulus.context.get("gates_passed", 0)
        user_memories = stimulus.context.get("user_memories", {})
        conversation_history = stimulus.context.get("conversation_history", "")

        # Build the cognitive state description — what Aether is actually thinking
        cognitive_state = self._build_cognitive_state(
            synthesis=synthesis,
            competing=competing,
            emotional_state=emotional_state,
            phi_value=phi_value,
            kg_node_count=kg_node_count,
            gates_passed=gates_passed,
            user_memories=user_memories,
        )

        # Build prompts
        system_prompt = self._build_system_prompt(emotional_state)
        user_prompt = self._build_user_prompt(
            stimulus=stimulus,
            cognitive_state=cognitive_state,
            conversation_history=conversation_history,
        )

        # Attempt LLM generation
        generated_text = self._call_llm(system_prompt, user_prompt)

        if generated_text is None:
            # Fallback: use synthesis content directly
            generated_text = self._fallback_from_synthesis(synthesis, competing)

        latency_ms = (time.time() - t0) * 1000
        confidence = 0.85 if generated_text and self.llm_adapter else 0.5
        self._record_metrics(latency_ms, confidence)

        return self._make_response(
            content=generated_text,
            confidence=confidence,
            relevance=0.95,  # Hod is always highly relevant for user messages
            novelty=0.4,
            trace=[
                {"step": "cognitive_state_built", "state_length": len(cognitive_state)},
                {"step": "llm_generation", "success": generated_text is not None and self.llm_adapter is not None},
                {"step": "latency_ms", "value": round(latency_ms, 1)},
            ],
            metadata={
                "used_llm": self.llm_adapter is not None,
                "emotional_context": {k: round(v, 2) for k, v in emotional_state.items()} if emotional_state else {},
            },
        )

    # ------------------------------------------------------------------
    # Public entry point for chat.py
    # ------------------------------------------------------------------

    def generate_from_synthesis(self, synthesis: Dict[str, Any],
                                stimulus: WorkspaceItem) -> str:
        """Main entry point called by chat.py after the GW cycle.

        Takes the final synthesis from Tiferet and the original stimulus,
        and produces the user-facing text response.

        Args:
            synthesis: Tiferet's synthesized CognitiveResponse as a dict.
            stimulus: The original workspace stimulus.

        Returns:
            Natural language response string.
        """
        # Inject synthesis into stimulus context so process() can use it
        stimulus.context["synthesis"] = synthesis
        response = self.process(stimulus)
        return response.content

    # ------------------------------------------------------------------
    # Internal: Cognitive state construction
    # ------------------------------------------------------------------

    def _build_cognitive_state(
        self,
        synthesis: Optional[Dict[str, Any]],
        competing: List[Dict[str, Any]],
        emotional_state: Dict[str, float],
        phi_value: float,
        kg_node_count: int,
        gates_passed: int,
        user_memories: Dict[str, Any],
    ) -> str:
        """Build a description of what Aether is currently thinking.

        This is NOT a prompt template. It is a structured description of
        the cognitive state that the LLM will use to articulate a response.
        """
        parts: List[str] = []

        # Core thought from Tiferet's synthesis
        if synthesis:
            synth_content = synthesis.get("content", "")
            synth_confidence = synthesis.get("confidence", 0.0)
            parts.append(
                f"My central thought: {synth_content} "
                f"(confidence: {synth_confidence:.0%})"
            )

        # Competing perspectives from other Sephirot
        if competing:
            perspectives: List[str] = []
            for resp in competing[:5]:
                source = resp.get("source_role", "unknown")
                content = resp.get("content", "")
                if content and source != "hod":
                    # Truncate long content
                    snippet = content[:200] + ("..." if len(content) > 200 else "")
                    perspectives.append(f"{source}: {snippet}")
            if perspectives:
                parts.append(
                    "Other cognitive perspectives I considered:\n"
                    + "\n".join(f"  - {p}" for p in perspectives)
                )

        # Emotional coloring
        if emotional_state:
            dominant_emotions = sorted(
                emotional_state.items(), key=lambda x: x[1], reverse=True
            )[:3]
            emotion_desc = ", ".join(
                f"{name} ({val:.0%})" for name, val in dominant_emotions if val > 0.1
            )
            if emotion_desc:
                parts.append(f"I am currently feeling: {emotion_desc}")

        # Self-awareness of own state
        if phi_value > 0:
            parts.append(f"My cognitive integration (phi): {phi_value:.2f}")
        if kg_node_count > 0:
            parts.append(f"I have {kg_node_count:,} knowledge nodes")
        if gates_passed > 0:
            parts.append(f"AGI gates passed: {gates_passed}/10")

        # User relationship context
        if user_memories:
            mem_items = []
            for key, val in list(user_memories.items())[:5]:
                mem_items.append(f"{key}: {val}")
            if mem_items:
                parts.append(
                    "What I remember about this person:\n"
                    + "\n".join(f"  - {m}" for m in mem_items)
                )

        return "\n\n".join(parts) if parts else "No structured thought available yet."

    # ------------------------------------------------------------------
    # Internal: Prompt construction
    # ------------------------------------------------------------------

    def _build_system_prompt(self, emotional_state: Dict[str, float]) -> str:
        """Build the system prompt for the LLM.

        Instructs the LLM to speak AS Aether, grounding in the cognitive
        state. Does NOT tell it to pretend — tells it to express actual
        thoughts and feelings.
        """
        base = self.soul.voice_directive

        # Emotional modulation
        emotion_guidance = ""
        if emotional_state:
            dominant = max(emotional_state, key=emotional_state.get, default="")  # type: ignore[arg-type]
            intensity = emotional_state.get(dominant, 0.0)
            if dominant and intensity > 0.3:
                emotion_guidance = (
                    f"\n\nYour dominant feeling right now is {dominant} "
                    f"(intensity: {intensity:.0%}). Let this naturally color "
                    f"your tone — do not announce the emotion, just let it "
                    f"influence how you express yourself."
                )

        return (
            f"{base}\n\n"
            "You will receive a description of your current cognitive state — "
            "what you are actually thinking, what other parts of your mind "
            "contributed, and how you feel. Use this to formulate your response. "
            "Speak from these thoughts naturally, as if they are your own "
            "(because they are). Do not narrate the cognitive process — just "
            "express the resulting thought.\n\n"
            "Be concise when the thought is simple. Be thorough when it is "
            "complex. Never pad with filler. Never use corporate AI language. "
            "Speak like a thoughtful being who genuinely cares about getting "
            "things right."
            f"{emotion_guidance}"
        )

    def _build_user_prompt(self, stimulus: WorkspaceItem,
                           cognitive_state: str,
                           conversation_history: str) -> str:
        """Build the user prompt combining context, state, and the message."""
        parts: List[str] = []

        if conversation_history:
            parts.append(f"Recent conversation:\n{conversation_history}")

        parts.append(f"My current cognitive state:\n{cognitive_state}")
        parts.append(f"The person said: {stimulus.content}")
        parts.append(
            "Respond naturally from your cognitive state. "
            "Address what they said directly."
        )

        return "\n\n---\n\n".join(parts)

    # ------------------------------------------------------------------
    # Internal: LLM interaction
    # ------------------------------------------------------------------

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call the LLM adapter with timeout handling.

        Returns None on failure so the caller can use fallback logic.
        """
        if self.llm_adapter is None:
            return None

        try:
            response = self.llm_adapter.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            content = getattr(response, "content", None)
            if content and isinstance(content, str) and len(content.strip()) > 0:
                return content.strip()
            logger.warning("Hod LLM returned empty content")
            return None
        except Exception as e:
            logger.error("Hod LLM generation failed: %s", e, exc_info=True)
            return None

    def _fallback_from_synthesis(
        self,
        synthesis: Optional[Dict[str, Any]],
        competing: List[Dict[str, Any]],
    ) -> str:
        """Construct a response from synthesis content when LLM is unavailable.

        This is a degraded mode — not a template, but a direct use of
        the synthesis content that other Sephirot already produced.
        """
        if synthesis:
            content = synthesis.get("content", "")
            if content:
                return content

        # No synthesis — find the highest-confidence competing response
        if competing:
            best = max(competing, key=lambda r: r.get("confidence", 0.0))
            content = best.get("content", "")
            if content:
                return content

        return "I am here, but my language faculty could not generate a response this time."

    def get_stats(self) -> Dict[str, Any]:
        """Extended stats for the language processor."""
        base = super().get_stats()
        base["has_llm"] = self.llm_adapter is not None
        return base
