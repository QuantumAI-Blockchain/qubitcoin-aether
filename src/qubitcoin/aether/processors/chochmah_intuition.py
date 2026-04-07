"""
Chochmah Intuition Processor -- Pattern completion and analogy.

Chochmah is the right-brain intuitive Sephirah. It:
1. Finds non-obvious analogies across domains via vector similarity
2. Detects patterns that logical reasoning misses
3. Generates creative connections between distant concepts
4. Uses the vector index for semantic similarity search
"""
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from ..cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    WorkspaceItem,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Bonus multiplier when an analogy connects two different domains
CROSS_DOMAIN_BONUS: float = 1.6

# Minimum similarity threshold to consider a match meaningful
MIN_SIMILARITY: float = 0.15

# Maximum candidate nodes to examine for structural analogies
MAX_STRUCTURAL_CANDIDATES: int = 60


class ChochmahIntuitionProcessor(CognitiveProcessor):
    """Intuition processor that discovers cross-domain analogies and patterns.

    Chochmah operates via two complementary channels:
    - Semantic similarity: finds nodes whose meaning overlaps despite
      living in different domains (uses vector index when available).
    - Structural similarity: finds nodes with analogous edge patterns
      (same relationship topology in different domains).

    The strongest insights come from matches that score high on BOTH
    channels simultaneously -- these are genuine deep analogies.
    """

    def __init__(
        self,
        knowledge_graph: Any = None,
        soul: Optional[SoulPriors] = None,
    ) -> None:
        super().__init__(role="chochmah", knowledge_graph=knowledge_graph, soul=soul)

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Find the most insightful cross-domain analogy for this stimulus.

        Steps:
        1. Retrieve semantically similar nodes via vector/text search.
        2. Group results by domain and identify cross-domain pairs.
        3. Score each pair by similarity * cross-domain bonus * confidence.
        4. Check for structural analogies among top candidates.
        5. Return the best analogy as natural language.
        """
        t0 = time.monotonic()

        if self.kg is None:
            return self._empty_response("No knowledge graph available.")

        query = stimulus.content
        # 1. Semantic search
        semantic_matches = self._semantic_search(query, limit=20)
        if not semantic_matches:
            return self._empty_response("No relevant knowledge found for pattern matching.")

        # 2. Group by domain
        domain_groups = self._group_by_domain(semantic_matches)

        # 3. Find cross-domain pairs and score them
        analogies = self._find_cross_domain_analogies(domain_groups)

        # 4. Attempt structural analogy enrichment on top candidates
        for analogy in analogies[:5]:
            structural = self._structural_similarity(
                analogy["node_a_id"], analogy["node_b_id"],
            )
            analogy["structural_score"] = structural
            # Combined score: semantic + structural bonus
            analogy["combined"] = (
                analogy["score"] * (1.0 + 0.4 * structural)
            )

        # 5. Sort by combined score
        analogies.sort(key=lambda a: a.get("combined", a["score"]), reverse=True)

        if not analogies:
            return self._empty_response("No cross-domain patterns detected.")

        best = analogies[0]
        content = self._format_analogy(best)
        evidence = [best["node_a_id"], best["node_b_id"]]

        confidence = min(0.95, best.get("combined", best["score"]))
        novelty = 0.75 if best["cross_domain"] else 0.4
        # Boost novelty by soul's intuition bias
        novelty = min(1.0, novelty + 0.15 * self.soul.intuition_bias)

        latency_ms = (time.monotonic() - t0) * 1000.0
        self._record_metrics(latency_ms, confidence)

        logger.debug(
            "Chochmah analogy: %s <-> %s (score=%.3f, structural=%.3f)",
            best.get("domain_a"), best.get("domain_b"),
            best["score"], best.get("structural_score", 0.0),
        )

        return self._make_response(
            content=content,
            confidence=confidence,
            relevance=min(1.0, best["score"] * 1.2),
            novelty=novelty,
            evidence=evidence,
            trace=[
                {"step": "semantic_search", "matches": len(semantic_matches)},
                {"step": "cross_domain_pairs", "count": len(analogies)},
                {"step": "best_analogy", "score": round(best.get("combined", 0), 4)},
            ],
            metadata={
                "analogy_count": len(analogies),
                "domains_found": list(domain_groups.keys()),
                "best_structural_score": round(best.get("structural_score", 0.0), 4),
            },
            energy_cost=0.03,
        )

    # ── Internal methods ──────────────────────────────────────────────

    def _semantic_search(
        self, query: str, limit: int = 20,
    ) -> List[Tuple[int, float, str]]:
        """Search the KG and return (node_id, score, domain) tuples."""
        results: List[Tuple[int, float, str]] = []
        try:
            search_results = self.kg.search(query, top_k=limit)
            for node, score in search_results:
                if score >= MIN_SIMILARITY:
                    results.append((node.node_id, score, node.domain or "unknown"))
        except Exception as e:
            logger.warning("Chochmah semantic search failed: %s", e)
        return results

    def _group_by_domain(
        self, matches: List[Tuple[int, float, str]],
    ) -> Dict[str, List[Tuple[int, float]]]:
        """Group search results by their domain."""
        groups: Dict[str, List[Tuple[int, float]]] = {}
        for node_id, score, domain in matches:
            groups.setdefault(domain, []).append((node_id, score))
        return groups

    def _find_cross_domain_analogies(
        self, domain_groups: Dict[str, List[Tuple[int, float]]],
    ) -> List[Dict[str, Any]]:
        """Build scored analogy pairs, prioritizing cross-domain matches."""
        analogies: List[Dict[str, Any]] = []
        domains = list(domain_groups.keys())

        # Cross-domain pairs
        for i, domain_a in enumerate(domains):
            for domain_b in domains[i + 1:]:
                for nid_a, score_a in domain_groups[domain_a][:5]:
                    for nid_b, score_b in domain_groups[domain_b][:5]:
                        avg_sim = (score_a + score_b) / 2.0
                        node_a = self.kg.nodes.get(nid_a)
                        node_b = self.kg.nodes.get(nid_b)
                        if node_a is None or node_b is None:
                            continue
                        conf_factor = (node_a.confidence + node_b.confidence) / 2.0
                        final_score = avg_sim * CROSS_DOMAIN_BONUS * conf_factor
                        analogies.append({
                            "node_a_id": nid_a,
                            "node_b_id": nid_b,
                            "domain_a": domain_a,
                            "domain_b": domain_b,
                            "score": final_score,
                            "cross_domain": True,
                            "content_a": self._node_label(node_a),
                            "content_b": self._node_label(node_b),
                            "shared_property": self._find_shared_property(node_a, node_b),
                        })

        # Same-domain pairs (lower priority -- only if we have few cross-domain)
        if len(analogies) < 3:
            for domain, nodes in domain_groups.items():
                for idx, (nid_a, score_a) in enumerate(nodes[:4]):
                    for nid_b, score_b in nodes[idx + 1: idx + 4]:
                        node_a = self.kg.nodes.get(nid_a)
                        node_b = self.kg.nodes.get(nid_b)
                        if node_a is None or node_b is None:
                            continue
                        avg_sim = (score_a + score_b) / 2.0
                        conf_factor = (node_a.confidence + node_b.confidence) / 2.0
                        analogies.append({
                            "node_a_id": nid_a,
                            "node_b_id": nid_b,
                            "domain_a": domain,
                            "domain_b": domain,
                            "score": avg_sim * conf_factor,
                            "cross_domain": False,
                            "content_a": self._node_label(node_a),
                            "content_b": self._node_label(node_b),
                            "shared_property": self._find_shared_property(node_a, node_b),
                        })

        analogies.sort(key=lambda a: a["score"], reverse=True)
        return analogies

    def _structural_similarity(self, node_a_id: int, node_b_id: int) -> float:
        """Compute edge-pattern similarity between two nodes.

        Compares the distribution of outgoing edge types. Nodes with
        similar relationship patterns in different domains are
        structurally analogous (e.g., both have many 'supports' and
        one 'contradicts' edge).
        """
        try:
            edges_a = self.kg.get_edges_from(node_a_id)
            edges_b = self.kg.get_edges_from(node_b_id)
        except Exception:
            return 0.0

        if not edges_a or not edges_b:
            return 0.0

        # Build edge-type frequency vectors
        types_a: Dict[str, int] = {}
        for e in edges_a:
            types_a[e.edge_type] = types_a.get(e.edge_type, 0) + 1

        types_b: Dict[str, int] = {}
        for e in edges_b:
            types_b[e.edge_type] = types_b.get(e.edge_type, 0) + 1

        # Cosine similarity over edge-type counts
        all_types = set(types_a) | set(types_b)
        if not all_types:
            return 0.0

        dot = sum(types_a.get(t, 0) * types_b.get(t, 0) for t in all_types)
        mag_a = sum(v * v for v in types_a.values()) ** 0.5
        mag_b = sum(v * v for v in types_b.values()) ** 0.5

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)

    def _node_label(self, node: Any) -> str:
        """Extract a concise label from a KeterNode's content dict."""
        content = node.content if isinstance(node.content, dict) else {}
        # Try common content keys in priority order
        for key in ("title", "name", "subject", "text", "description", "summary"):
            val = content.get(key)
            if val and isinstance(val, str):
                return val[:120]
        # Fallback: stringify the whole content, truncated
        text = str(content)
        return text[:120] if len(text) > 120 else text

    def _find_shared_property(self, node_a: Any, node_b: Any) -> str:
        """Identify a shared property between two nodes.

        Looks for overlapping content keys with similar values,
        matching node types, or shared edge targets.
        """
        # Same node type
        if node_a.node_type == node_b.node_type and node_a.node_type != "assertion":
            return f"both are {node_a.node_type}s"

        # Overlapping content keys
        content_a = node_a.content if isinstance(node_a.content, dict) else {}
        content_b = node_b.content if isinstance(node_b.content, dict) else {}
        shared_keys = set(content_a.keys()) & set(content_b.keys()) - {"text", "hash"}
        if shared_keys:
            key = sorted(shared_keys)[0]
            return f"shared attribute '{key}'"

        # Shared edge targets
        try:
            targets_a = {e.to_node_id for e in self.kg.get_edges_from(node_a.node_id)}
            targets_b = {e.to_node_id for e in self.kg.get_edges_from(node_b.node_id)}
            common = targets_a & targets_b
            if common:
                return f"{len(common)} shared connection(s) in the knowledge graph"
        except Exception:
            pass

        return "structural relationship pattern"

    def _format_analogy(self, analogy: Dict[str, Any]) -> str:
        """Format an analogy as natural language insight."""
        a_label = analogy["content_a"]
        b_label = analogy["content_b"]
        domain_a = analogy["domain_a"]
        domain_b = analogy["domain_b"]
        shared = analogy.get("shared_property", "a common pattern")

        if analogy["cross_domain"]:
            structural = analogy.get("structural_score", 0.0)
            strength = "striking" if structural > 0.6 else "interesting" if structural > 0.3 else "subtle"
            return (
                f"I notice a {strength} pattern here -- the way '{a_label}' "
                f"operates in {domain_a} is structurally similar to how "
                f"'{b_label}' functions in {domain_b}. Both involve "
                f"{shared}. This cross-domain connection suggests a deeper "
                f"underlying principle that transcends either domain alone."
            )
        else:
            return (
                f"Within {domain_a}, I see a connection between '{a_label}' "
                f"and '{b_label}' through {shared}. These concepts reinforce "
                f"each other in a way that strengthens our understanding of "
                f"this domain."
            )

    def _empty_response(self, reason: str) -> CognitiveResponse:
        """Return a low-confidence response when no analogy is found."""
        logger.debug("Chochmah: %s", reason)
        return self._make_response(
            content=reason,
            confidence=0.1,
            relevance=0.2,
            novelty=0.1,
            energy_cost=0.005,
        )
