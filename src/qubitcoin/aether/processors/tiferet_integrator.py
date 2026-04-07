"""
Tiferet Integration Processor -- Multi-perspective synthesis.

Tiferet is the heart of the cognitive architecture. It:
1. Receives competing responses from other Sephirot
2. Finds common ground and resolves conflicts
3. Synthesizes a unified perspective
4. This is where the "thinking" becomes coherent
"""

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    WorkspaceItem,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Minimum weight for a response to contribute to synthesis
MIN_WEIGHT: float = 0.05

# Bonus added to novelty when cross-perspective synthesis succeeds
CROSS_SYNTHESIS_NOVELTY_BONUS: float = 0.15


class TiferetIntegratorProcessor(CognitiveProcessor):
    """Multi-perspective integrator that synthesizes competing
    Sephirot responses into a coherent unified perspective.

    Tiferet resolves disagreements, highlights agreement, and
    produces a final synthesis weighted by each contributor's
    confidence and relevance.
    """

    def __init__(self, knowledge_graph: Any = None,
                 soul: Optional[SoulPriors] = None) -> None:
        super().__init__(role="tiferet", knowledge_graph=knowledge_graph, soul=soul)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Integrate competing cognitive responses into a unified synthesis.

        Expects stimulus.context['competing_responses'] to be a list of
        CognitiveResponse.to_dict() dicts from other processors.

        Steps:
            1. Parse and weight incoming responses.
            2. Find agreement, disagreement, and unique contributions.
            3. Build a synthesis narrative.
            4. Score the integration.
        """
        t0 = time.perf_counter()

        raw_responses: List[Dict[str, Any]] = stimulus.context.get(
            "competing_responses", []
        )
        responses = self._parse_responses(raw_responses)

        # ----- Handle edge cases -----
        if not responses:
            resp = self._make_response(
                content="No perspectives to integrate. I have nothing to synthesize.",
                confidence=0.05,
                relevance=0.1,
                novelty=0.1,
            )
            self._record_metrics((time.perf_counter() - t0) * 1000, resp.confidence)
            return resp

        if len(responses) == 1:
            return self._pass_through_single(responses[0], t0)

        # ----- Step 1: Weight responses -----
        weighted = self._weight_responses(responses)

        # ----- Step 2: Analyze agreement and disagreement -----
        agreements = self._find_agreements(weighted)
        disagreements = self._find_disagreements(weighted)
        unique_additions = self._find_unique_additions(weighted)

        # ----- Step 3: Check for vetoes -----
        vetoes = [r for r in responses if r.get("is_veto")]
        if vetoes:
            return self._handle_veto(vetoes, responses, t0)

        # ----- Step 4: Build synthesis narrative -----
        content = self._compose_synthesis(
            weighted, agreements, disagreements, unique_additions
        )

        # ----- Step 5: Score -----
        confidence = self._compute_confidence(weighted)
        relevance = self._compute_relevance(weighted)
        has_cross_synthesis = len(agreements) > 0 and len(unique_additions) > 0
        novelty = self._compute_novelty(weighted, has_cross_synthesis)

        all_evidence: List[int] = []
        for r in responses:
            all_evidence.extend(r.get("evidence", []))
        evidence = list(dict.fromkeys(all_evidence))[:20]  # deduplicate, preserve order

        trace = self._build_trace(
            weighted, agreements, disagreements, unique_additions
        )

        resp = self._make_response(
            content=content,
            confidence=confidence,
            relevance=relevance,
            novelty=novelty,
            evidence=evidence,
            trace=trace,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_metrics(elapsed_ms, resp.confidence)
        logger.debug(
            "tiferet integrated %d perspectives in %.1fms  "
            "agreements=%d  disagreements=%d  unique=%d",
            len(responses), elapsed_ms, len(agreements),
            len(disagreements), len(unique_additions),
        )
        return resp

    # ------------------------------------------------------------------
    # Internal: Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_responses(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and normalize incoming response dicts."""
        parsed: List[Dict[str, Any]] = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            if "content" not in r or "source_role" not in r:
                continue
            # Ensure numeric fields exist
            r.setdefault("confidence", 0.5)
            r.setdefault("relevance", 0.5)
            r.setdefault("novelty", 0.5)
            r.setdefault("evidence", [])
            r.setdefault("is_veto", False)
            r.setdefault("veto_reason", "")
            parsed.append(r)
        return parsed

    # ------------------------------------------------------------------
    # Internal: Weighting
    # ------------------------------------------------------------------

    @staticmethod
    def _weight_responses(
        responses: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Assign integration weight = confidence * relevance to each response."""
        weighted: List[Tuple[Dict[str, Any], float]] = []
        for r in responses:
            w = float(r["confidence"]) * float(r["relevance"])
            w = max(MIN_WEIGHT, w)
            weighted.append((r, w))
        # Sort descending by weight
        weighted.sort(key=lambda x: x[1], reverse=True)
        return weighted

    # ------------------------------------------------------------------
    # Internal: Agreement / Disagreement analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _find_agreements(
        weighted: List[Tuple[Dict[str, Any], float]]
    ) -> List[Dict[str, Any]]:
        """Find evidence IDs cited by more than one response (agreement)."""
        evidence_sources: Dict[int, List[str]] = {}
        for r, _w in weighted:
            role = r["source_role"]
            for eid in r.get("evidence", []):
                evidence_sources.setdefault(eid, []).append(role)

        agreements: List[Dict[str, Any]] = []
        for eid, roles in evidence_sources.items():
            if len(roles) > 1:
                agreements.append({
                    "evidence_id": eid,
                    "agreed_by": roles,
                    "strength": len(roles) / max(1, len(weighted)),
                })
        return agreements

    @staticmethod
    def _find_disagreements(
        weighted: List[Tuple[Dict[str, Any], float]]
    ) -> List[Dict[str, Any]]:
        """Detect disagreements: responses whose content explicitly differs.

        Heuristic: two responses disagree if their evidence sets are
        disjoint AND their weights are both above MIN_WEIGHT.
        """
        disagreements: List[Dict[str, Any]] = []
        items = [(r, w) for r, w in weighted if w > MIN_WEIGHT]

        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                r_a, w_a = items[i]
                r_b, w_b = items[j]
                ev_a: Set[int] = set(r_a.get("evidence", []))
                ev_b: Set[int] = set(r_b.get("evidence", []))

                if not ev_a or not ev_b:
                    continue

                overlap = ev_a & ev_b
                if len(overlap) == 0:
                    disagreements.append({
                        "between": [r_a["source_role"], r_b["source_role"]],
                        "type": "disjoint_evidence",
                        "weight_a": round(w_a, 3),
                        "weight_b": round(w_b, 3),
                    })
        return disagreements

    @staticmethod
    def _find_unique_additions(
        weighted: List[Tuple[Dict[str, Any], float]]
    ) -> List[Dict[str, Any]]:
        """Find evidence cited by exactly one response (unique perspectives)."""
        all_evidence: Dict[int, str] = {}
        evidence_count: Dict[int, int] = {}

        for r, _w in weighted:
            role = r["source_role"]
            for eid in r.get("evidence", []):
                evidence_count[eid] = evidence_count.get(eid, 0) + 1
                all_evidence[eid] = role

        unique: List[Dict[str, Any]] = []
        for eid, count in evidence_count.items():
            if count == 1:
                unique.append({
                    "evidence_id": eid,
                    "source": all_evidence[eid],
                })
        return unique

    # ------------------------------------------------------------------
    # Internal: Veto handling
    # ------------------------------------------------------------------

    def _handle_veto(
        self,
        vetoes: List[Dict[str, Any]],
        all_responses: List[Dict[str, Any]],
        t0: float,
    ) -> CognitiveResponse:
        """When any response is a veto, Tiferet propagates the veto."""
        strongest = max(vetoes, key=lambda v: float(v.get("confidence", 0)))
        reason = strongest.get("veto_reason", "Safety concern raised by Gevurah.")

        content = (
            f"Integration blocked by safety veto from {strongest['source_role']}: "
            f"{reason} "
            f"({len(vetoes)} veto(s) from {len(all_responses)} total perspectives.)"
        )

        resp = self._make_response(
            content=content,
            confidence=float(strongest["confidence"]),
            relevance=1.0,
            novelty=0.2,
            is_veto=True,
            veto_reason=reason,
        )
        self._record_metrics((time.perf_counter() - t0) * 1000, resp.confidence)
        logger.info("tiferet propagating veto: %s", reason)
        return resp

    # ------------------------------------------------------------------
    # Internal: Single-response pass-through
    # ------------------------------------------------------------------

    def _pass_through_single(
        self, response: Dict[str, Any], t0: float
    ) -> CognitiveResponse:
        """When only one perspective exists, pass through with slight
        confidence reduction (single viewpoint is less trustworthy)."""
        reduction = 0.9
        content = (
            f"Only one perspective available (from {response['source_role']}): "
            f"{response['content']}"
        )

        resp = self._make_response(
            content=content,
            confidence=float(response["confidence"]) * reduction,
            relevance=float(response["relevance"]),
            novelty=float(response["novelty"]) * 0.8,
            evidence=response.get("evidence", [])[:20],
        )
        self._record_metrics((time.perf_counter() - t0) * 1000, resp.confidence)
        return resp

    # ------------------------------------------------------------------
    # Internal: Synthesis composition
    # ------------------------------------------------------------------

    def _compose_synthesis(
        self,
        weighted: List[Tuple[Dict[str, Any], float]],
        agreements: List[Dict[str, Any]],
        disagreements: List[Dict[str, Any]],
        unique_additions: List[Dict[str, Any]],
    ) -> str:
        """Build a natural-language synthesis from the weighted perspectives."""
        parts: List[str] = ["Considering multiple angles:"]

        # Lead with the highest-weighted response
        for r, w in weighted[:3]:
            role = r["source_role"]
            snippet = r["content"]
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."
            parts.append(f"{role}'s analysis ({w:.2f} weight): {snippet}")

        # Highlight agreements
        if agreements:
            agreeing_roles: Set[str] = set()
            for a in agreements:
                for role in a["agreed_by"]:
                    agreeing_roles.add(role)
            parts.append(
                f"Points of agreement ({len(agreements)} shared evidence nodes "
                f"across {', '.join(sorted(agreeing_roles))}): these perspectives "
                f"converge on common ground."
            )

        # Note disagreements
        if disagreements:
            conflict_descriptions: List[str] = []
            for d in disagreements[:3]:
                pair = " vs ".join(d["between"])
                conflict_descriptions.append(pair)
            parts.append(
                f"Tensions: {', '.join(conflict_descriptions)} "
                f"draw on different evidence bases."
            )

        # Note unique contributions
        if unique_additions:
            source_counts: Dict[str, int] = {}
            for u in unique_additions:
                src = u["source"]
                source_counts[src] = source_counts.get(src, 0) + 1
            unique_desc = ", ".join(
                f"{role} adds {count} unique point(s)"
                for role, count in sorted(source_counts.items())
            )
            parts.append(f"Novel additions: {unique_desc}.")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Internal: Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(
        weighted: List[Tuple[Dict[str, Any], float]]
    ) -> float:
        """Weighted average of input confidences."""
        total_weight = sum(w for _, w in weighted)
        if total_weight == 0:
            return 0.1
        weighted_sum = sum(
            float(r["confidence"]) * w for r, w in weighted
        )
        return weighted_sum / total_weight

    @staticmethod
    def _compute_relevance(
        weighted: List[Tuple[Dict[str, Any], float]]
    ) -> float:
        """Weighted average of input relevances."""
        total_weight = sum(w for _, w in weighted)
        if total_weight == 0:
            return 0.1
        weighted_sum = sum(
            float(r["relevance"]) * w for r, w in weighted
        )
        return weighted_sum / total_weight

    @staticmethod
    def _compute_novelty(
        weighted: List[Tuple[Dict[str, Any], float]],
        has_cross_synthesis: bool,
    ) -> float:
        """Novelty from inputs + bonus for successful cross-synthesis."""
        if not weighted:
            return 0.1
        avg_novelty = sum(float(r["novelty"]) for r, _ in weighted) / len(weighted)
        bonus = CROSS_SYNTHESIS_NOVELTY_BONUS if has_cross_synthesis else 0.0
        return min(1.0, avg_novelty + bonus)

    # ------------------------------------------------------------------
    # Internal: Trace
    # ------------------------------------------------------------------

    @staticmethod
    def _build_trace(
        weighted: List[Tuple[Dict[str, Any], float]],
        agreements: List[Dict[str, Any]],
        disagreements: List[Dict[str, Any]],
        unique_additions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        trace: List[Dict[str, Any]] = [
            {
                "step": "weighting",
                "perspectives": [
                    {"role": r["source_role"], "weight": round(w, 3)}
                    for r, w in weighted
                ],
            },
        ]
        if agreements:
            trace.append({
                "step": "agreements",
                "count": len(agreements),
                "shared_evidence": [a["evidence_id"] for a in agreements[:10]],
            })
        if disagreements:
            trace.append({
                "step": "disagreements",
                "count": len(disagreements),
                "pairs": [d["between"] for d in disagreements[:5]],
            })
        if unique_additions:
            trace.append({
                "step": "unique_additions",
                "count": len(unique_additions),
                "by_source": list({u["source"] for u in unique_additions}),
            })
        return trace
