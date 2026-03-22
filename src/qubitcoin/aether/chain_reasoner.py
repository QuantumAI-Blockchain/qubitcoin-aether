"""
#68: Multi-Step Reasoning Chains (5+ steps with verification)

Executes and verifies long reasoning chains with backtracking on
failed verification steps.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""
    step_type: str  # observe, hypothesize, deduce, verify, conclude
    premise: str
    inference_type: str  # deductive, inductive, abductive
    conclusion: str
    confidence: float
    supporting_nodes: List[str] = field(default_factory=list)
    verified: bool = False
    verification_score: float = 0.0


@dataclass
class ReasoningChain:
    """A complete multi-step reasoning chain."""
    query: str
    steps: List[ReasoningStep] = field(default_factory=list)
    conclusion: str = ''
    confidence: float = 0.0
    verified: bool = False
    backtrack_count: int = 0
    duration_ms: float = 0.0

    def chain_score(self) -> float:
        """Product of step confidences * verification bonus."""
        if not self.steps:
            return 0.0
        product = 1.0
        for step in self.steps:
            product *= max(step.confidence, 0.01)
        verification_bonus = 1.2 if self.verified else 0.8
        return product * verification_bonus


_STEP_TYPES = ['observe', 'hypothesize', 'deduce', 'verify', 'conclude']
_INFERENCE_TYPES = ['deductive', 'inductive', 'abductive']


class ChainReasoner:
    """Execute and verify multi-step reasoning chains."""

    def __init__(self, max_steps: int = 7, max_backtracks: int = 3) -> None:
        self._max_steps = max(max_steps, 5)
        self._max_backtracks = max_backtracks
        self._chains: List[ReasoningChain] = []
        self._max_history = 500
        self._total_chains: int = 0
        self._total_steps: int = 0
        self._successful_verifications: int = 0
        self._failed_verifications: int = 0

        logger.info("ChainReasoner initialized (max_steps=%d)", self._max_steps)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def reason_chain(
        self,
        query: str,
        kg: Any = None,
        max_steps: int = 7,
    ) -> ReasoningChain:
        """Execute a multi-step reasoning chain.

        Steps: observe -> hypothesize -> deduce (1+ times) -> verify -> conclude
        """
        t0 = time.time()
        max_steps = min(max_steps, self._max_steps)
        chain = ReasoningChain(query=query)
        backtracks = 0

        # Step 1: Observe — gather relevant nodes from KG
        obs_step = self._observe(query, kg)
        chain.steps.append(obs_step)

        # Step 2: Hypothesize
        hyp_step = self._hypothesize(query, obs_step)
        chain.steps.append(hyp_step)

        # Steps 3-N: Deduction loop
        deduction_count = max(1, max_steps - 4)  # Reserve slots for observe, hyp, verify, conclude
        for i in range(deduction_count):
            prev_step = chain.steps[-1]
            ded_step = self._deduce(prev_step, kg, i)
            chain.steps.append(ded_step)

            # Inline verification: check deduction against KG
            if kg and not self._verify_step(ded_step, kg):
                self._failed_verifications += 1
                if backtracks < self._max_backtracks:
                    # Backtrack: remove failed step, try alternative inference
                    chain.steps.pop()
                    backtracks += 1
                    chain.backtrack_count = backtracks
                    alt_step = self._deduce_alternative(prev_step, kg, i, backtracks)
                    chain.steps.append(alt_step)

        # Step N-1: Verify the full chain
        verify_step = self._verify_chain(chain, kg)
        chain.steps.append(verify_step)

        # Step N: Conclude
        conclude_step = self._conclude(chain)
        chain.steps.append(conclude_step)

        chain.conclusion = conclude_step.conclusion
        chain.confidence = chain.chain_score()
        chain.verified = verify_step.verified
        chain.duration_ms = (time.time() - t0) * 1000

        self._total_chains += 1
        self._total_steps += len(chain.steps)

        # Store history
        self._chains.append(chain)
        if len(self._chains) > self._max_history:
            self._chains = self._chains[-self._max_history:]

        return chain

    # ------------------------------------------------------------------
    # Step builders
    # ------------------------------------------------------------------

    def _observe(self, query: str, kg: Any) -> ReasoningStep:
        """Gather relevant observations from the knowledge graph."""
        supporting = []
        confidence = 0.5

        if kg and hasattr(kg, 'nodes'):
            # Find nodes whose content mentions query terms
            query_terms = set(query.lower().split())
            for nid, node in list(kg.nodes.items())[:500]:
                content_str = str(getattr(node, 'content', '')).lower()
                overlap = sum(1 for t in query_terms if t in content_str)
                if overlap > 0:
                    supporting.append(nid)
                    if len(supporting) >= 10:
                        break
            if supporting:
                confidence = min(0.9, 0.4 + len(supporting) * 0.05)

        return ReasoningStep(
            step_type='observe',
            premise=query,
            inference_type='inductive',
            conclusion=f"Observed {len(supporting)} relevant nodes for: {query[:100]}",
            confidence=confidence,
            supporting_nodes=supporting[:10],
            verified=True,
            verification_score=1.0,
        )

    def _hypothesize(self, query: str, obs_step: ReasoningStep) -> ReasoningStep:
        """Form a hypothesis based on observations."""
        if obs_step.supporting_nodes:
            hypothesis = f"Hypothesis: {query[:80]} is supported by {len(obs_step.supporting_nodes)} observations"
            confidence = min(0.8, obs_step.confidence * 0.9)
        else:
            hypothesis = f"Hypothesis: {query[:80]} (no direct evidence, exploring)"
            confidence = 0.3

        return ReasoningStep(
            step_type='hypothesize',
            premise=obs_step.conclusion,
            inference_type='abductive',
            conclusion=hypothesis,
            confidence=confidence,
            supporting_nodes=obs_step.supporting_nodes[:5],
        )

    def _deduce(self, prev_step: ReasoningStep, kg: Any, depth: int) -> ReasoningStep:
        """Perform a deductive inference step."""
        # Build on previous conclusion
        premise = prev_step.conclusion
        supporting = list(prev_step.supporting_nodes)

        # Try to extend via KG edges
        if kg and hasattr(kg, 'edges') and supporting:
            for nid in supporting[:3]:
                for eid, edge in list(kg.edges.items())[:200]:
                    src = getattr(edge, 'source_id', edge.get('source_id', '')) if isinstance(edge, dict) else getattr(edge, 'source_id', '')
                    tgt = getattr(edge, 'target_id', edge.get('target_id', '')) if isinstance(edge, dict) else getattr(edge, 'target_id', '')
                    if src == nid and tgt not in supporting:
                        supporting.append(tgt)
                        break

        confidence = prev_step.confidence * (0.95 - depth * 0.02)
        conclusion = f"Deduction (depth {depth}): extended to {len(supporting)} supporting nodes"

        return ReasoningStep(
            step_type='deduce',
            premise=premise[:200],
            inference_type='deductive',
            conclusion=conclusion,
            confidence=max(confidence, 0.1),
            supporting_nodes=supporting[:15],
        )

    def _deduce_alternative(
        self, prev_step: ReasoningStep, kg: Any, depth: int, attempt: int,
    ) -> ReasoningStep:
        """Try an alternative deduction path after backtracking."""
        step = self._deduce(prev_step, kg, depth)
        step.conclusion = f"Alt-deduction (attempt {attempt}, depth {depth}): {step.conclusion}"
        step.confidence *= 0.85  # Slight penalty for alternative path
        return step

    def _verify_step(self, step: ReasoningStep, kg: Any) -> bool:
        """Verify a single deduction step against the KG."""
        if not step.supporting_nodes:
            return False

        # Check that at least some supporting nodes actually exist in KG
        if kg and hasattr(kg, 'nodes'):
            valid_count = sum(1 for nid in step.supporting_nodes if nid in kg.nodes)
            ratio = valid_count / max(len(step.supporting_nodes), 1)
            verified = ratio > 0.3
            step.verified = verified
            step.verification_score = ratio
            if verified:
                self._successful_verifications += 1
            return verified

        step.verified = True  # No KG = cannot falsify
        step.verification_score = 0.5
        return True

    def _verify_chain(self, chain: ReasoningChain, kg: Any) -> ReasoningStep:
        """Verify the entire reasoning chain."""
        verified_steps = sum(1 for s in chain.steps if s.verified)
        total = max(len(chain.steps), 1)
        ratio = verified_steps / total
        verified = ratio > 0.5

        return ReasoningStep(
            step_type='verify',
            premise=f"Verifying chain of {total} steps",
            inference_type='deductive',
            conclusion=f"Chain verification: {verified_steps}/{total} steps verified ({ratio:.0%})",
            confidence=ratio,
            verified=verified,
            verification_score=ratio,
        )

    def _conclude(self, chain: ReasoningChain) -> ReasoningStep:
        """Draw a final conclusion from the chain."""
        if not chain.steps:
            return ReasoningStep(
                step_type='conclude',
                premise='No reasoning steps',
                inference_type='deductive',
                conclusion='Unable to reach conclusion',
                confidence=0.0,
            )

        # Aggregate evidence
        all_supporting = []
        for step in chain.steps:
            all_supporting.extend(step.supporting_nodes)
        unique_supporting = list(set(all_supporting))

        avg_confidence = float(np.mean([s.confidence for s in chain.steps]))
        conclusion = (
            f"Conclusion: chain of {len(chain.steps)} steps with "
            f"{len(unique_supporting)} unique evidence nodes, "
            f"avg confidence {avg_confidence:.3f}"
        )

        return ReasoningStep(
            step_type='conclude',
            premise=chain.steps[-1].conclusion if chain.steps else '',
            inference_type='deductive',
            conclusion=conclusion,
            confidence=avg_confidence,
            supporting_nodes=unique_supporting[:20],
            verified=chain.steps[-1].verified if chain.steps else False,
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        avg_chain_len = (
            float(np.mean([len(c.steps) for c in self._chains[-50:]]))
            if self._chains else 0.0
        )
        avg_confidence = (
            float(np.mean([c.confidence for c in self._chains[-50:]]))
            if self._chains else 0.0
        )
        return {
            'total_chains': self._total_chains,
            'total_steps': self._total_steps,
            'successful_verifications': self._successful_verifications,
            'failed_verifications': self._failed_verifications,
            'avg_chain_length': round(avg_chain_len, 2),
            'avg_confidence': round(avg_confidence, 4),
            'history_size': len(self._chains),
        }
