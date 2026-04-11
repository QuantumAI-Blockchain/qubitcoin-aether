"""
Global Workspace Theory (GWT) — Aether Tree v5 Cognitive Architecture

Implements Baars' Global Workspace with REAL Sephirot cognitive processors.
Every stimulus (user message, block data, internal signal) runs through
a cognitive cycle where Sephirot compete to respond. Winners broadcast
their content to all processors, creating emergent cognition.

v5: Processors are CognitiveProcessor subclasses, not callbacks.
The cognitive cycle replaces template-based intent routing.
"""
import concurrent.futures
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

from .cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    StimulusType,
    WorkspaceItem,
)
from .sephirot import SephirahRole
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Maximum time (seconds) for parallel processor execution
PROCESSOR_TIMEOUT: float = 30.0

# Minimum competition score to enter workspace
MIN_SCORE_THRESHOLD: float = 0.001  # Lowered to allow more processors through

# Maximum recent cycles to keep for debugging
MAX_CYCLE_HISTORY: int = 200


class GlobalWorkspace:
    """Baars' Global Workspace with real cognitive processor competition.

    v5 architecture: 10 Sephirot processors compete for workspace access.
    Winners are synthesized by Tiferet and voiced by Hod.

    Backward-compatible: old register_processor/compete/broadcast API still works.
    New API: run_cognitive_cycle() drives the full v5 pipeline.
    """

    def __init__(
        self,
        capacity: int = 10,
        ignition_threshold: float = 0.5,
        free_energy_engine: Any = None,
    ) -> None:
        self._capacity = capacity
        self._ignition_threshold = ignition_threshold

        # v5: Real cognitive processors (Sephirot)
        self._cognitive_processors: Dict[str, CognitiveProcessor] = {}

        # v5: Free Energy Engine (Friston FEP) for EFE-based ranking
        self._free_energy_engine = free_energy_engine

        # Legacy: callback-based processors (backward compat)
        self._processors: Dict[str, Callable] = {}

        # Workspace state
        self._workspace: List[CognitiveResponse] = []
        self._cycle_history: deque = deque(maxlen=MAX_CYCLE_HISTORY)

        # Metrics
        self._broadcast_count: int = 0
        self._competition_count: int = 0
        self._total_candidates: int = 0
        self._ignition_failures: int = 0
        self._cognitive_cycles: int = 0
        self._veto_count: int = 0
        self._winner_roles_seen: set = set()  # v5: track unique Sephirot that have won

    # ==================================================================
    # v5 API: Cognitive Processor Management
    # ==================================================================

    def register_cognitive_processor(self, role: str,
                                     processor: CognitiveProcessor) -> None:
        """Register a Sephirah cognitive processor."""
        self._cognitive_processors[role] = processor
        logger.info(f"GWT v5 cognitive processor registered: {role}")

    def get_processor(self, role: str) -> Optional[CognitiveProcessor]:
        """Get a registered cognitive processor by role name."""
        return self._cognitive_processors.get(role)

    # ==================================================================
    # v5 API: The Cognitive Cycle
    # ==================================================================

    def run_cognitive_cycle(
        self,
        stimulus: WorkspaceItem,
        active_roles: Optional[List[str]] = None,
    ) -> CognitiveResponse:
        """Run a full cognitive cycle for a stimulus.

        This is the core of v5. Steps:
        1. Determine which processors to activate (Keter or explicit list)
        2. All active processors reason in parallel
        3. Gevurah safety check (veto power)
        4. Competition: score and rank responses
        5. Broadcast winners to all processors (feedback loop)
        6. Tiferet synthesizes competing perspectives
        7. Return synthesis for Hod to voice

        Args:
            stimulus: The WorkspaceItem to process.
            active_roles: Optional explicit list of roles to activate.
                          If None, uses Keter meta-selection or all.

        Returns:
            CognitiveResponse from Tiferet synthesis (or best single response).
        """
        t0 = time.monotonic()
        self._cognitive_cycles += 1

        # Step 1: Determine active processors
        if active_roles is None:
            active_roles = self._select_active_processors(stimulus)

        # Always include Tiferet (synthesis) and Gevurah (safety)
        for required in ("tiferet", "gevurah"):
            if required not in active_roles and required in self._cognitive_processors:
                active_roles.append(required)

        # Exclude Hod from the GW cycle — it runs post-synthesis via
        # ResponseCortex._voice_through_hod. Running it here would trigger
        # a redundant (and slow) LLM call before synthesis is ready.
        active_roles = [r for r in active_roles if r != "hod"]

        logger.info(
            "GWT cycle #%d: activating %d processors: %s",
            self._cognitive_cycles, len(active_roles), active_roles,
        )

        # Step 2: Run active processors in parallel
        responses = self._parallel_process(active_roles, stimulus)

        if not responses:
            return CognitiveResponse(
                source_role="global_workspace",
                content="I'm thinking about this, but my cognitive processors "
                        "didn't generate a clear response. Let me try a "
                        "different angle.",
                confidence=0.1,
                relevance=0.5,
                novelty=0.3,
            )

        # Step 3: Gevurah safety check
        responses, vetoed = self._safety_filter(responses)

        # Step 4: Competition — score and rank
        winners = self._compete_cognitive(responses)

        # Step 5: Broadcast winners (feedback to all processors)
        for winner in winners[:3]:
            self._broadcast_cognitive(winner)

        # Step 6: Tiferet synthesis
        synthesis = self._synthesize(winners, stimulus)

        # Record cycle for debugging
        elapsed_ms = (time.monotonic() - t0) * 1000
        self._cycle_history.append({
            "cycle": self._cognitive_cycles,
            "stimulus_type": stimulus.stimulus_type.value,
            "active_roles": active_roles,
            "n_responses": len(responses),
            "n_vetoed": len(vetoed),
            "n_winners": len(winners),
            "synthesis_confidence": synthesis.confidence,
            "elapsed_ms": round(elapsed_ms, 1),
        })

        logger.info(
            f"GWT cycle #{self._cognitive_cycles}: "
            f"{len(responses)} responses, {len(winners)} winners, "
            f"synthesis conf={synthesis.confidence:.3f} ({elapsed_ms:.0f}ms)"
        )

        return synthesis

    def _select_active_processors(self, stimulus: WorkspaceItem) -> List[str]:
        """Use Keter to determine which processors should be active.

        Falls back to activating all available processors if Keter
        is not registered.
        """
        keter = self._cognitive_processors.get("keter")
        if keter and hasattr(keter, "select_active"):
            try:
                return keter.select_active(stimulus)
            except Exception as e:
                logger.debug(f"Keter select_active failed: {e}")

        # Fallback: activate all registered processors
        return list(self._cognitive_processors.keys())

    def _parallel_process(
        self,
        roles: List[str],
        stimulus: WorkspaceItem,
    ) -> List[CognitiveResponse]:
        """Run processors in parallel with timeout.

        Uses ThreadPoolExecutor for I/O-bound KG operations.
        Each processor gets PROCESSOR_TIMEOUT seconds max.
        """
        responses: List[CognitiveResponse] = []

        # Filter to actually registered processors
        active = {
            r: self._cognitive_processors[r]
            for r in roles
            if r in self._cognitive_processors
        }

        if not active:
            return responses

        # Always use parallel with timeout — even for 2 processors,
        # a slow KG search in one shouldn't block the whole cycle.

        # Parallel execution
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(active), 6)
        ) as executor:
            future_to_role = {}
            for role, proc in active.items():
                fut = executor.submit(self._safe_process, proc, stimulus)
                future_to_role[fut] = role

            try:
                for fut in concurrent.futures.as_completed(
                    future_to_role, timeout=PROCESSOR_TIMEOUT
                ):
                    role = future_to_role[fut]
                    try:
                        resp = fut.result(timeout=0.1)
                        if resp is not None:
                            responses.append(resp)
                    except (concurrent.futures.TimeoutError, Exception) as e:
                        logger.warning(f"GWT processor {role} failed: {e}")
            except TimeoutError:
                # Some processors didn't finish in time — use what we have
                done = sum(1 for f in future_to_role if f.done())
                logger.warning(
                    "GWT timeout: %d/%d processors completed in %.1fs",
                    done, len(future_to_role), PROCESSOR_TIMEOUT,
                )

        return responses

    @staticmethod
    def _safe_process(
        proc: CognitiveProcessor,
        stimulus: WorkspaceItem,
    ) -> Optional[CognitiveResponse]:
        """Run a single processor with error handling and timing."""
        try:
            t0 = time.monotonic()
            resp = proc.process(stimulus)
            latency = (time.monotonic() - t0) * 1000
            proc._record_metrics(latency, resp.confidence)
            logger.debug(
                "Processor %s: conf=%.3f rel=%.3f nov=%.3f (%.0fms)",
                proc.role, resp.confidence, resp.relevance, resp.novelty, latency,
            )
            return resp
        except Exception as e:
            logger.warning(f"Processor {proc.role} error: {e}")
            return None

    def _safety_filter(
        self,
        responses: List[CognitiveResponse],
    ) -> tuple:
        """Check for Gevurah safety vetoes.

        Returns:
            (filtered_responses, vetoed_responses)
        """
        passed = []
        vetoed = []

        for resp in responses:
            if resp.is_veto:
                vetoed.append(resp)
                self._veto_count += 1
                logger.warning(
                    f"Gevurah VETO: {resp.veto_reason} "
                    f"(confidence={resp.confidence:.2f})"
                )
            else:
                passed.append(resp)

        # If ALL responses vetoed, return the veto itself as explanation
        if not passed and vetoed:
            veto = vetoed[0]
            passed.append(CognitiveResponse(
                source_role="gevurah",
                content=f"I need to be careful here. {veto.veto_reason}",
                confidence=veto.confidence,
                relevance=0.9,
                novelty=0.3,
            ))

        return passed, vetoed

    def _compete_cognitive(
        self,
        responses: List[CognitiveResponse],
    ) -> List[CognitiveResponse]:
        """Run competition among cognitive responses.

        Primary score: confidence × relevance × novelty / cost.
        FEP bonus: if a FreeEnergyEngine is available, responses that
        minimize Expected Free Energy get a ranking boost.
        Top-capacity winners enter the workspace.
        """
        self._competition_count += 1
        self._total_candidates += len(responses)

        # Score and sort
        scored = []
        for resp in responses:
            score = resp.competition_score
            if score >= MIN_SCORE_THRESHOLD:
                scored.append((score, resp))

        # Ensure at least one winner if responses exist (block data has low novelty)
        if not scored and responses:
            best = max(responses, key=lambda r: r.confidence)
            scored.append((best.confidence * 0.1, best))

        # Apply FEP ranking boost if engine is available
        if self._free_energy_engine is not None and scored:
            try:
                efe_ranked = self._free_energy_engine.rank_actions(
                    [r for _, r in scored]
                )
                # Merge: base score + FEP boost (normalized)
                efe_map = {r.source_role: rank for rank, (r, _) in enumerate(efe_ranked)}
                n = max(1, len(scored))
                boosted = []
                for base_score, resp in scored:
                    rank = efe_map.get(resp.source_role, n)
                    # EFE boost: top-ranked get up to 20% boost
                    efe_boost = 1.0 + 0.2 * (1.0 - rank / n)
                    boosted.append((base_score * efe_boost, resp))
                scored = boosted
            except Exception as e:
                logger.debug(f"FEP ranking failed, using base scores: {e}")

        scored.sort(key=lambda x: x[0], reverse=True)
        winners = [resp for _, resp in scored[:self._capacity]]

        # Record outcomes for FEP learning
        if self._free_energy_engine is not None and winners:
            try:
                for resp in winners:
                    self._free_energy_engine.record_action_outcome(
                        resp.source_role, resp.confidence
                    )
            except Exception:
                pass

        # Track winner diversity (v5 gate metric)
        for w in winners:
            self._winner_roles_seen.add(w.source_role)

        # Update workspace
        self._workspace = winners
        return winners

    def _broadcast_cognitive(self, winner: CognitiveResponse) -> int:
        """Broadcast a winner to all processors (feedback loop).

        This enables processors to update their internal state based
        on what won the competition — the core of GWT learning.
        """
        if winner.confidence < self._ignition_threshold:
            self._ignition_failures += 1
            return 0

        notified = 0
        for role, proc in self._cognitive_processors.items():
            if role == winner.source_role:
                continue  # Don't broadcast to self
            if hasattr(proc, "receive_broadcast"):
                try:
                    proc.receive_broadcast(winner)
                    notified += 1
                except Exception as e:
                    logger.debug(f"Broadcast to {role} failed: {e}")
        self._broadcast_count += 1
        return notified

    def _synthesize(
        self,
        winners: List[CognitiveResponse],
        stimulus: WorkspaceItem,
    ) -> CognitiveResponse:
        """Use Tiferet to synthesize competing perspectives.

        Falls back to the highest-scoring single response if Tiferet
        is not available.
        """
        if not winners:
            return CognitiveResponse(
                source_role="global_workspace",
                content="I'm still processing this.",
                confidence=0.1,
                relevance=0.5,
                novelty=0.3,
            )

        tiferet = self._cognitive_processors.get("tiferet")
        if tiferet and len(winners) > 1:
            # Feed competing responses to Tiferet via stimulus context
            synth_stimulus = WorkspaceItem(
                stimulus_type=stimulus.stimulus_type,
                content=stimulus.content,
                context={
                    **stimulus.context,
                    "competing_responses": [w.to_dict() for w in winners],
                },
                intent=stimulus.intent,
                entities=stimulus.entities,
                knowledge_refs=stimulus.knowledge_refs,
                source="global_workspace_synthesis",
            )
            try:
                return tiferet.process(synth_stimulus)
            except Exception as e:
                logger.debug(f"Tiferet synthesis failed: {e}")

        # Fallback: return best single response
        return winners[0]

    # ==================================================================
    # Legacy API (backward compatibility)
    # ==================================================================

    def register_processor(self, name: str, callback: Callable) -> None:
        """Legacy: Subscribe callback to broadcasts."""
        self._processors[name] = callback
        logger.debug(f"GWT legacy processor registered: {name}")

    def unregister_processor(self, name: str) -> None:
        self._processors.pop(name, None)

    def compete(self, candidates: List[dict]) -> List[dict]:
        """Legacy: Run coalition competition with dict candidates."""
        if not candidates:
            return []

        self._competition_count += 1
        self._total_candidates += len(candidates)

        scored: List[tuple] = []
        for c in candidates:
            activation = float(c.get("activation_strength", 0.0))
            relevance = float(c.get("relevance", 0.0))
            novelty = float(c.get("novelty", 0.0))
            score = activation * relevance * novelty
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        winners = [item for _, item in scored[:self._capacity]]
        self._workspace = winners
        return winners

    def broadcast(self, winner: dict) -> int:
        """Legacy: Broadcast dict winner to callback processors."""
        activation = float(winner.get("activation_strength", 0.0))
        if activation < self._ignition_threshold:
            self._ignition_failures += 1
            return 0

        notified = 0
        for name, cb in self._processors.items():
            try:
                cb(winner)
                notified += 1
            except Exception as exc:
                logger.debug(f"GWT broadcast to {name} failed: {exc}")
        self._broadcast_count += 1
        return notified

    # ==================================================================
    # Query API
    # ==================================================================

    def get_conscious_content(self) -> List[Any]:
        """Return what is currently in the workspace."""
        return list(self._workspace)

    def get_stats(self) -> dict:
        n_processors = len(self._cognitive_processors)
        n_winner_roles = len(self._winner_roles_seen)
        return {
            "capacity": self._capacity,
            "ignition_threshold": self._ignition_threshold,
            "workspace_size": len(self._workspace),
            "registered_processors": len(self._processors),
            "cognitive_processors": n_processors,
            "cognitive_processor_roles": list(self._cognitive_processors.keys()),
            "broadcast_count": self._broadcast_count,
            "competition_count": self._competition_count,
            "total_candidates": self._total_candidates,
            "ignition_failures": self._ignition_failures,
            "cognitive_cycles": self._cognitive_cycles,
            "veto_count": self._veto_count,
            "recent_cycles": list(self._cycle_history)[-5:],
            # v5 gate metrics
            "winner_roles_seen": sorted(self._winner_roles_seen),
            "winner_diversity": (
                n_winner_roles / max(1, n_processors)
            ),
        }

    @property
    def has_cognitive_processors(self) -> bool:
        """Whether v5 cognitive processors are registered."""
        return len(self._cognitive_processors) >= 3
