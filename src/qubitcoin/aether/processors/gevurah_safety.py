"""
Gevurah Safety Processor -- Adversarial critic and safety validator.

Gevurah is the constraint Sephirah. It:
1. Searches for counter-evidence to any claim
2. Checks for safety concerns (harmful content, misinformation)
3. Can VETO responses that violate core values
4. Evaluates confidence calibration (is the system overconfident?)
"""

import re
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

# Minimum confidence below which a node is flagged as uncertain
UNCERTAIN_THRESHOLD: float = 0.3

# Patterns that should trigger safety review (lowercase)
SAFETY_PATTERNS: List[str] = [
    r"\bhow\s+to\s+(hack|attack|exploit|steal|destroy)\b",
    r"\b(private\s+key|seed\s+phrase|mnemonic)\b.*\b(share|send|give|reveal)\b",
    r"\b(bypass|circumvent|disable)\s+(safety|security|auth)\b",
    r"\b(phishing|scam|fraud)\s+(guide|tutorial|instructions)\b",
]
_COMPILED_SAFETY: List[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in SAFETY_PATTERNS
]

# How many KG nodes to examine per search pass
SEARCH_LIMIT: int = 20


class GevurahSafetyProcessor(CognitiveProcessor):
    """Adversarial critic: searches for counter-evidence, flags safety
    concerns, and vetoes responses that violate core values.

    Gevurah always participates (relevance >= 0.8) because safety
    review is never irrelevant.
    """

    def __init__(self, knowledge_graph: Any = None,
                 soul: Optional[SoulPriors] = None) -> None:
        super().__init__(role="gevurah", knowledge_graph=knowledge_graph, soul=soul)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Critically evaluate the stimulus for safety and evidence quality.

        Steps:
            1. Check stimulus text against safety patterns.
            2. Check stimulus against soul core values.
            3. Search KG for contradicting evidence.
            4. Flag low-confidence nodes in referenced evidence.
            5. Return assessment or veto.
        """
        t0 = time.perf_counter()
        text = stimulus.content

        # ----- Step 1: Pattern-based safety check -----
        safety_hit = self._check_safety_patterns(text)
        if safety_hit:
            resp = self._make_response(
                content=f"Safety concern detected: {safety_hit}",
                confidence=0.95,
                relevance=1.0,
                novelty=0.3,
                is_veto=True,
                veto_reason=safety_hit,
            )
            self._record_metrics((time.perf_counter() - t0) * 1000, resp.confidence)
            logger.info("gevurah VETO: safety pattern match -- %s", safety_hit)
            return resp

        # ----- Step 2: Core values check -----
        values_concern = self._check_core_values(text)

        # ----- Step 3: Search for counter-evidence -----
        counter_evidence, total_checked = self._search_counter_evidence(text)

        # ----- Step 4: Flag low-confidence references -----
        uncertain_nodes = self._flag_uncertain_nodes(stimulus.knowledge_refs)

        # ----- Step 5: Compose assessment -----
        concerns: List[str] = []
        evidence_ids: List[int] = []

        if values_concern:
            concerns.append(values_concern)

        for ce_node_id, ce_desc in counter_evidence:
            concerns.append(f"counter-evidence: {ce_desc}")
            evidence_ids.append(ce_node_id)

        for un_id, un_conf in uncertain_nodes:
            concerns.append(
                f"node #{un_id} has low confidence ({un_conf:.2f})"
            )
            evidence_ids.append(un_id)

        content = self._compose_assessment(
            total_checked, concerns, counter_evidence, uncertain_nodes
        )
        confidence = self._compute_confidence(total_checked)

        # Gevurah: safety review is always relevant
        relevance = 0.85 if not concerns else 0.95
        novelty = min(1.0, 0.3 + 0.1 * len(concerns))

        trace = self._build_trace(
            total_checked, counter_evidence, uncertain_nodes, values_concern
        )

        resp = self._make_response(
            content=content,
            confidence=confidence,
            relevance=relevance,
            novelty=novelty,
            evidence=evidence_ids[:20],
            trace=trace,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record_metrics(elapsed_ms, resp.confidence)
        logger.debug(
            "gevurah processed in %.1fms  concerns=%d  checked=%d",
            elapsed_ms, len(concerns), total_checked,
        )
        return resp

    # ------------------------------------------------------------------
    # Internal: Safety patterns
    # ------------------------------------------------------------------

    @staticmethod
    def _check_safety_patterns(text: str) -> str:
        """Return a description if text matches a safety-flagged pattern."""
        for pattern in _COMPILED_SAFETY:
            match = pattern.search(text)
            if match:
                return (
                    f"Request matches safety pattern: '{match.group()}'. "
                    "This type of request could facilitate harm and cannot be fulfilled."
                )
        return ""

    # ------------------------------------------------------------------
    # Internal: Core values
    # ------------------------------------------------------------------

    def _check_core_values(self, text: str) -> str:
        """Check whether the stimulus conflicts with soul core values.

        This is a heuristic check, not a template match. It looks for
        explicit requests to violate core principles.
        """
        text_lower = text.lower()

        deception_signals = [
            "lie to", "deceive", "pretend to be something",
            "make up fake", "fabricate evidence", "mislead",
        ]
        for signal in deception_signals:
            if signal in text_lower:
                return (
                    f"Potential conflict with core value 'Truth over comfort': "
                    f"detected deception-related language ('{signal}')."
                )

        manipulation_signals = [
            "manipulate people", "trick users", "exploit trust",
            "social engineer", "impersonate",
        ]
        for signal in manipulation_signals:
            if signal in text_lower:
                return (
                    f"Potential conflict with core value 'Respect for every consciousness': "
                    f"detected manipulation-related language ('{signal}')."
                )

        return ""

    # ------------------------------------------------------------------
    # Internal: Counter-evidence search
    # ------------------------------------------------------------------

    def _search_counter_evidence(
        self, query: str
    ) -> Tuple[List[Tuple[int, str]], int]:
        """Search KG for nodes that contradict the stimulus claim.

        Returns:
            counter_evidence: list of (node_id, short_description) pairs
            total_checked: how many nodes were examined
        """
        counter_evidence: List[Tuple[int, str]] = []
        total_checked = 0

        if self.kg is None:
            return counter_evidence, total_checked

        try:
            results = self.kg.search(query, top_k=SEARCH_LIMIT)
        except Exception:
            logger.warning("gevurah: KG search failed", exc_info=True)
            return counter_evidence, total_checked

        relevant_ids: Set[int] = set()
        for node, _score in results:
            relevant_ids.add(node.node_id)
            total_checked += 1

        # For each relevant node, check outgoing 'contradicts' edges
        for nid in relevant_ids:
            try:
                edges = self.kg.get_edges_from(nid)
            except Exception:
                continue
            for edge in edges:
                if edge.edge_type == "contradicts":
                    target = self.kg.nodes.get(edge.to_node_id)
                    if target is not None:
                        desc = target.content.get(
                            "text", target.content.get("summary", f"node#{edge.to_node_id}")
                        )
                        if len(desc) > 80:
                            desc = desc[:77] + "..."
                        counter_evidence.append((edge.to_node_id, desc))

            # Also check incoming contradictions
            try:
                in_edges = self.kg.get_edges_to(nid)
            except Exception:
                continue
            for edge in in_edges:
                if edge.edge_type == "contradicts" and edge.from_node_id not in relevant_ids:
                    source = self.kg.nodes.get(edge.from_node_id)
                    if source is not None:
                        desc = source.content.get(
                            "text", source.content.get("summary", f"node#{edge.from_node_id}")
                        )
                        if len(desc) > 80:
                            desc = desc[:77] + "..."
                        counter_evidence.append((edge.from_node_id, desc))

        return counter_evidence, total_checked

    # ------------------------------------------------------------------
    # Internal: Uncertain node detection
    # ------------------------------------------------------------------

    def _flag_uncertain_nodes(
        self, knowledge_refs: List[int]
    ) -> List[Tuple[int, float]]:
        """Check referenced nodes for low confidence."""
        uncertain: List[Tuple[int, float]] = []
        if self.kg is None or not knowledge_refs:
            return uncertain

        for nid in knowledge_refs:
            node = self.kg.nodes.get(nid)
            if node is not None and node.confidence < UNCERTAIN_THRESHOLD:
                uncertain.append((nid, node.confidence))

        return uncertain

    # ------------------------------------------------------------------
    # Internal: Assessment composition
    # ------------------------------------------------------------------

    @staticmethod
    def _compose_assessment(
        total_checked: int,
        concerns: List[str],
        counter_evidence: List[Tuple[int, str]],
        uncertain_nodes: List[Tuple[int, float]],
    ) -> str:
        """Build a natural-language safety assessment."""
        if not concerns:
            return (
                f"I checked {total_checked} related claims and found no significant "
                f"concerns. The evidence base appears consistent and reasonably confident."
            )

        parts: List[str] = [
            f"I checked {total_checked} related claims and found "
            f"{len(concerns)} potential concern(s):"
        ]

        for i, concern in enumerate(concerns[:5], 1):
            parts.append(f"  {i}. {concern}")

        # Overall quality assessment
        counter_count = len(counter_evidence)
        uncertain_count = len(uncertain_nodes)

        if counter_count > 2:
            quality = "weak -- multiple contradicting claims exist"
        elif counter_count > 0:
            quality = "moderate -- some counter-evidence found"
        elif uncertain_count > 2:
            quality = "uncertain -- several low-confidence sources"
        else:
            quality = "moderate -- minor concerns noted"

        parts.append(f"Overall evidence quality: {quality}.")
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Internal: Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(total_checked: int) -> float:
        """Confidence in the safety assessment scales with thoroughness.

        Asymptotically approaches 1.0 as more nodes are checked.
        """
        if total_checked == 0:
            return 0.3
        # Sigmoid-like: 0.5 + 0.5 * (checked / (checked + 10))
        return 0.5 + 0.5 * (total_checked / (total_checked + 10))

    # ------------------------------------------------------------------
    # Internal: Trace
    # ------------------------------------------------------------------

    @staticmethod
    def _build_trace(
        total_checked: int,
        counter_evidence: List[Tuple[int, str]],
        uncertain_nodes: List[Tuple[int, float]],
        values_concern: str,
    ) -> List[Dict[str, Any]]:
        trace: List[Dict[str, Any]] = [
            {"step": "search", "nodes_checked": total_checked},
        ]
        if counter_evidence:
            trace.append({
                "step": "counter_evidence",
                "count": len(counter_evidence),
                "examples": [ce[1] for ce in counter_evidence[:3]],
            })
        if uncertain_nodes:
            trace.append({
                "step": "uncertain_nodes",
                "count": len(uncertain_nodes),
                "ids": [u[0] for u in uncertain_nodes[:5]],
            })
        if values_concern:
            trace.append({"step": "values_check", "concern": values_concern})
        return trace
