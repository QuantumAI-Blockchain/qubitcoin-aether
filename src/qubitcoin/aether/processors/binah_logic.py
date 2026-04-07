"""
Binah Logic Processor -- Formal deduction and causal reasoning.

Binah is the left-brain analytical Sephirah. It performs:
1. Deductive reasoning: Given premises, derive conclusions via graph traversal
2. Causal analysis: Find cause-effect chains in the KG
3. Contradiction detection: Find conflicting evidence
"""

import time
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from ..cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    WorkspaceItem,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Edge types Binah considers logically productive
DEDUCTIVE_EDGES: Set[str] = {"derives", "causes", "supports", "requires"}

# Edge type signaling conflict
CONTRADICTION_EDGE: str = "contradicts"

# Maximum BFS depth for reasoning chains
MAX_CHAIN_DEPTH: int = 3

# Confidence decay per hop in the chain
CONFIDENCE_DECAY_PER_HOP: float = 0.95


class BinahLogicProcessor(CognitiveProcessor):
    """Formal deduction and causal inference over the knowledge graph.

    Binah traverses 'derives', 'causes', and 'supports' edges to build
    logical chains from premises to conclusions. It also detects
    contradictions by looking for 'contradicts' edges among evidence nodes.
    """

    def __init__(self, knowledge_graph: Any = None,
                 soul: Optional[SoulPriors] = None) -> None:
        super().__init__(role="binah", knowledge_graph=knowledge_graph, soul=soul)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Reason deductively over the KG for the given stimulus.

        Steps:
            1. Search KG for premise nodes relevant to the stimulus.
            2. BFS along deductive edges up to depth 3.
            3. Build a natural-language reasoning chain.
            4. Detect contradictions among evidence.
            5. Score confidence, relevance, and novelty.
        """
        t0 = time.perf_counter()
        query = stimulus.content

        # ----- Step 1: Gather premise nodes -----
        premises = self._search_premises(query, limit=15)

        if not premises:
            resp = self._make_response(
                content="I found no relevant premises in my knowledge to reason from.",
                confidence=0.05,
                relevance=0.1,
                novelty=0.1,
            )
            self._record_metrics((time.perf_counter() - t0) * 1000, resp.confidence)
            return resp

        # ----- Step 2: BFS along deductive edges -----
        chains, all_evidence = self._build_reasoning_chains(premises)

        # ----- Step 3: Detect contradictions -----
        contradictions = self._detect_contradictions(all_evidence)

        # ----- Step 4: Build natural-language conclusion -----
        content = self._compose_narrative(query, chains, contradictions)

        # ----- Step 5: Score -----
        confidence = self._compute_confidence(chains)
        relevance = self._compute_relevance(query, all_evidence)
        seen_nodes: Set[int] = set(stimulus.context.get("seen_nodes", []))
        novelty = self._compute_novelty(all_evidence, seen_nodes)
        evidence_ids = [nid for nid in all_evidence]

        trace = self._build_trace(chains, contradictions)

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
            "binah processed stimulus in %.1fms  chains=%d  contradictions=%d",
            elapsed_ms, len(chains), len(contradictions),
        )
        return resp

    # ------------------------------------------------------------------
    # Internal: KG search
    # ------------------------------------------------------------------

    def _search_premises(self, query: str, limit: int = 15) -> Dict[int, float]:
        """Search KG for nodes relevant to the query.

        Returns {node_id: relevance_score}.
        """
        if self.kg is None:
            return {}

        premises: Dict[int, float] = {}
        try:
            results = self.kg.search(query, top_k=limit)
            for node, score in results:
                premises[node.node_id] = score
        except Exception:
            logger.warning("binah: KG search failed", exc_info=True)
        return premises

    # ------------------------------------------------------------------
    # Internal: BFS chain builder
    # ------------------------------------------------------------------

    def _build_reasoning_chains(
        self, premises: Dict[int, float]
    ) -> Tuple[List[List[Dict[str, Any]]], Set[int]]:
        """BFS from premises along deductive edges.

        Returns:
            chains: list of chains, each chain is a list of step dicts
                    [{"node_id", "content_summary", "confidence", "edge_type", "depth"}]
            all_evidence: set of all node IDs encountered
        """
        chains: List[List[Dict[str, Any]]] = []
        all_evidence: Set[int] = set(premises.keys())

        if self.kg is None:
            return chains, all_evidence

        for premise_id in premises:
            chain = self._bfs_from(premise_id)
            if chain:
                chains.append(chain)
                for step in chain:
                    all_evidence.add(step["node_id"])

        return chains, all_evidence

    def _bfs_from(self, start_id: int) -> List[Dict[str, Any]]:
        """BFS from a single node along deductive edges, up to MAX_CHAIN_DEPTH."""
        chain: List[Dict[str, Any]] = []
        visited: Set[int] = {start_id}

        start_node = self.kg.nodes.get(start_id)
        if start_node is None:
            return chain

        chain.append(self._node_step(start_node, edge_type="premise", depth=0))

        queue: deque[Tuple[int, int]] = deque()  # (node_id, depth)
        queue.append((start_id, 0))

        while queue:
            current_id, depth = queue.popleft()
            if depth >= MAX_CHAIN_DEPTH:
                continue

            try:
                edges = self.kg.get_edges_from(current_id)
            except Exception:
                continue

            for edge in edges:
                if edge.edge_type not in DEDUCTIVE_EDGES:
                    continue
                next_id = edge.to_node_id
                if next_id in visited:
                    continue
                visited.add(next_id)

                next_node = self.kg.nodes.get(next_id)
                if next_node is None:
                    continue

                chain.append(self._node_step(
                    next_node,
                    edge_type=edge.edge_type,
                    depth=depth + 1,
                ))
                queue.append((next_id, depth + 1))

        return chain if len(chain) > 1 else []

    @staticmethod
    def _node_step(node: Any, edge_type: str, depth: int) -> Dict[str, Any]:
        """Create a step dict from a KeterNode."""
        content = node.content
        summary = content.get("text", content.get("summary", str(content)))
        if len(summary) > 120:
            summary = summary[:117] + "..."
        return {
            "node_id": node.node_id,
            "content_summary": summary,
            "confidence": node.confidence,
            "edge_type": edge_type,
            "depth": depth,
            "domain": node.domain,
        }

    # ------------------------------------------------------------------
    # Internal: Contradiction detection
    # ------------------------------------------------------------------

    def _detect_contradictions(
        self, evidence_ids: Set[int]
    ) -> List[Tuple[int, int, str]]:
        """Find 'contradicts' edges among evidence nodes.

        Returns list of (node_a, node_b, description) tuples.
        """
        contradictions: List[Tuple[int, int, str]] = []
        if self.kg is None:
            return contradictions

        checked: Set[int] = set()
        for nid in evidence_ids:
            checked.add(nid)
            try:
                edges = self.kg.get_edges_from(nid)
            except Exception:
                continue
            for edge in edges:
                if edge.edge_type == CONTRADICTION_EDGE and edge.to_node_id in evidence_ids:
                    if edge.to_node_id not in checked:
                        node_a = self.kg.nodes.get(nid)
                        node_b = self.kg.nodes.get(edge.to_node_id)
                        desc_a = self._short_desc(node_a)
                        desc_b = self._short_desc(node_b)
                        contradictions.append((nid, edge.to_node_id,
                                               f"'{desc_a}' contradicts '{desc_b}'"))
        return contradictions

    @staticmethod
    def _short_desc(node: Any) -> str:
        if node is None:
            return "unknown"
        text = node.content.get("text", node.content.get("summary", ""))
        return text[:60] if text else f"node#{node.node_id}"

    # ------------------------------------------------------------------
    # Internal: Narrative composition
    # ------------------------------------------------------------------

    def _compose_narrative(
        self,
        query: str,
        chains: List[List[Dict[str, Any]]],
        contradictions: List[Tuple[int, int, str]],
    ) -> str:
        """Build a natural-language reasoning narrative from chain data."""
        if not chains:
            return "I could not build a deductive chain from the available evidence."

        parts: List[str] = []

        for i, chain in enumerate(chains[:3]):
            premise = chain[0]
            steps = chain[1:]
            if not steps:
                continue

            premise_text = premise["content_summary"]
            conclusion = steps[-1]

            path_verbs = {
                "derives": "it follows that",
                "causes": "which causes",
                "supports": "which supports",
                "requires": "which requires",
            }

            step_phrases: List[str] = []
            for s in steps:
                verb = path_verbs.get(s["edge_type"], "leading to")
                step_phrases.append(f"{verb} {s['content_summary']}")

            reasoning = ", ".join(step_phrases)
            chain_text = f"From '{premise_text}', {reasoning}."
            parts.append(chain_text)

        narrative = " ".join(parts)

        if contradictions:
            conflict_lines = [c[2] for c in contradictions[:3]]
            narrative += (
                f" However, I detected {len(contradictions)} contradiction(s): "
                + "; ".join(conflict_lines) + "."
            )

        return narrative

    # ------------------------------------------------------------------
    # Internal: Scoring
    # ------------------------------------------------------------------

    def _compute_confidence(self, chains: List[List[Dict[str, Any]]]) -> float:
        """Confidence = min(premise confidences) * decay^max_depth across chains."""
        if not chains:
            return 0.05
        chain_confidences: List[float] = []
        for chain in chains:
            if not chain:
                continue
            premise_conf = chain[0].get("confidence", 0.5)
            max_depth = max(s.get("depth", 0) for s in chain)
            chain_conf = premise_conf * (CONFIDENCE_DECAY_PER_HOP ** max_depth)
            chain_confidences.append(chain_conf)
        return max(chain_confidences) if chain_confidences else 0.05

    def _compute_relevance(self, query: str, evidence_ids: Set[int]) -> float:
        """Relevance = fraction of query terms found in evidence nodes."""
        if not evidence_ids or self.kg is None:
            return 0.1
        query_terms = set(query.lower().split())
        if not query_terms:
            return 0.1

        matched_terms: Set[str] = set()
        for nid in evidence_ids:
            node = self.kg.nodes.get(nid)
            if node is None:
                continue
            text = node.content.get("text", node.content.get("summary", "")).lower()
            for term in query_terms:
                if term in text:
                    matched_terms.add(term)

        return max(0.1, len(matched_terms) / len(query_terms))

    def _compute_novelty(self, evidence_ids: Set[int], seen_nodes: Set[int]) -> float:
        """Novelty = 1 - (seen evidence / total evidence)."""
        if not evidence_ids:
            return 0.5
        seen_count = len(evidence_ids & seen_nodes)
        return max(0.05, 1.0 - (seen_count / len(evidence_ids)))

    # ------------------------------------------------------------------
    # Internal: Trace
    # ------------------------------------------------------------------

    @staticmethod
    def _build_trace(
        chains: List[List[Dict[str, Any]]],
        contradictions: List[Tuple[int, int, str]],
    ) -> List[Dict[str, Any]]:
        """Build a reasoning trace for inspection."""
        trace: List[Dict[str, Any]] = []
        for i, chain in enumerate(chains[:5]):
            trace.append({
                "step": f"chain_{i}",
                "length": len(chain),
                "premise": chain[0]["content_summary"] if chain else "",
                "conclusion": chain[-1]["content_summary"] if chain else "",
                "max_depth": max((s["depth"] for s in chain), default=0),
            })
        if contradictions:
            trace.append({
                "step": "contradictions",
                "count": len(contradictions),
                "details": [c[2] for c in contradictions[:5]],
            })
        return trace
