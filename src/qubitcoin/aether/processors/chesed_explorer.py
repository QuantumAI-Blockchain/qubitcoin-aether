"""
Chesed Exploration Processor -- Divergent hypothesis generation.

Chesed is the expansive, creative Sephirah. It:
1. Generates multiple hypotheses for any question
2. Performs random walks through the KG to find unexpected connections
3. Asks "what if?" questions
4. Explores low-confidence regions of the KG where understanding is weakest
"""
import random
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

# Confidence threshold -- nodes below this are "uncertain territory"
UNCERTAINTY_THRESHOLD: float = 0.5

# Maximum nodes to sample when scanning for low-confidence regions
MAX_DOMAIN_SCAN: int = 200

# Random walk parameters
WALK_STEPS: int = 3
WALK_RESTARTS: int = 4

# Number of hypotheses to generate
TARGET_HYPOTHESES: int = 3


class ChesedExplorerProcessor(CognitiveProcessor):
    """Divergent thinking processor that generates speculative hypotheses.

    Chesed operates by deliberately seeking out the EDGES of knowledge --
    low-confidence nodes, sparse graph regions, and unexpected random-walk
    destinations. Where Binah seeks certainty, Chesed seeks possibility.

    The processor performs multi-restart random walks from stimulus-relevant
    seed nodes, collecting "surprising" connections (nodes reached that are
    distant in topic or domain from the origin). It then assembles these
    into speculative hypotheses of the form:

        "What if [observation_1] is connected to [observation_2]?
         This would explain [gap in current knowledge]."

    Chesed's output is intentionally lower-confidence (0.3-0.6) and
    higher-novelty (0.8+), reflecting that divergent thinking produces
    speculative but creative material.
    """

    def __init__(
        self,
        knowledge_graph: Any = None,
        soul: Optional[SoulPriors] = None,
    ) -> None:
        super().__init__(role="chesed", knowledge_graph=knowledge_graph, soul=soul)
        # Track which hypotheses have been generated to avoid repetition
        self._recent_hypothesis_hashes: List[int] = []
        self._max_recent: int = 100

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Generate divergent hypotheses via random walks and uncertainty exploration.

        Steps:
        1. Find seed nodes relevant to the stimulus.
        2. Identify low-confidence nodes in the same domain (uncertainty zones).
        3. Perform random walks from seeds, collecting surprising destinations.
        4. Assemble walk results + uncertainty zones into hypotheses.
        5. Return the most novel hypothesis.
        """
        t0 = time.monotonic()

        if self.kg is None:
            return self._empty_response("No knowledge graph available for exploration.")

        query = stimulus.content

        # 1. Find seed nodes
        seeds = self._find_seeds(query, limit=8)
        if not seeds:
            return self._empty_response("No relevant seed nodes for divergent exploration.")

        seed_domains = {self.kg.nodes[nid].domain for nid in seeds if nid in self.kg.nodes}

        # 2. Find low-confidence (uncertain) nodes in these domains
        uncertain_nodes = self._find_uncertain_nodes(seed_domains)

        # 3. Random walks from seeds
        walk_discoveries = self._random_walks(seeds)

        # 4. Generate hypotheses
        hypotheses = self._generate_hypotheses(
            seeds, uncertain_nodes, walk_discoveries,
        )

        if not hypotheses:
            return self._empty_response(
                "Explored the knowledge graph but no novel hypotheses emerged. "
                "The territory around this topic is well-mapped."
            )

        # 5. Pick the best (most novel, non-repeated) hypothesis
        best = self._select_best_hypothesis(hypotheses)

        # Track to avoid repetition
        h_hash = hash(best["content"][:80])
        self._recent_hypothesis_hashes.append(h_hash)
        if len(self._recent_hypothesis_hashes) > self._max_recent:
            self._recent_hypothesis_hashes = self._recent_hypothesis_hashes[-self._max_recent:]

        content = best["content"]
        evidence = best.get("evidence", [])
        confidence = best.get("confidence", 0.4)
        # Chesed is intentionally high-novelty
        novelty = best.get("novelty", 0.85)
        # Boost by soul's exploration bias
        novelty = min(1.0, novelty + 0.1 * self.soul.exploration_bias)

        latency_ms = (time.monotonic() - t0) * 1000.0
        self._record_metrics(latency_ms, confidence)

        logger.debug(
            "Chesed generated %d hypotheses, selected: %.60s... (conf=%.2f)",
            len(hypotheses), content, confidence,
        )

        return self._make_response(
            content=content,
            confidence=confidence,
            relevance=best.get("relevance", 0.5),
            novelty=novelty,
            evidence=evidence,
            trace=[
                {"step": "seed_search", "count": len(seeds)},
                {"step": "uncertain_nodes", "count": len(uncertain_nodes)},
                {"step": "random_walks", "discoveries": len(walk_discoveries)},
                {"step": "hypotheses_generated", "count": len(hypotheses)},
            ],
            metadata={
                "seed_domains": list(seed_domains),
                "uncertain_node_count": len(uncertain_nodes),
                "walk_discoveries": len(walk_discoveries),
                "hypothesis_type": best.get("hyp_type", "walk"),
            },
            energy_cost=0.04,  # Walks are moderately expensive
        )

    # ── Seed discovery ────────────────────────────────────────────────

    def _find_seeds(self, query: str, limit: int = 8) -> List[int]:
        """Find stimulus-relevant nodes to use as random walk origins."""
        try:
            results = self.kg.search(query, top_k=limit)
            return [node.node_id for node, _score in results if node.node_id in self.kg.nodes]
        except Exception as e:
            logger.warning("Chesed seed search failed: %s", e)
            return []

    # ── Uncertainty zones ─────────────────────────────────────────────

    def _find_uncertain_nodes(
        self, domains: Set[str], max_per_domain: int = 15,
    ) -> List[Dict[str, Any]]:
        """Find low-confidence nodes in the given domains.

        These represent knowledge gaps -- areas where the Aether Tree is
        least certain. Chesed finds these interesting precisely because
        they are frontiers of understanding.
        """
        uncertain: List[Dict[str, Any]] = []
        nodes_dict = self.kg.nodes

        for domain in domains:
            if not domain:
                continue
            # Scan nodes in this domain for low confidence
            domain_nodes = []
            count = 0
            for node in nodes_dict.values():
                if node.domain == domain:
                    domain_nodes.append(node)
                    count += 1
                    if count >= MAX_DOMAIN_SCAN:
                        break

            # Filter to low-confidence
            low_conf = [
                n for n in domain_nodes
                if n.confidence < UNCERTAINTY_THRESHOLD
            ]
            # Sort by confidence ascending (most uncertain first)
            low_conf.sort(key=lambda n: n.confidence)

            for node in low_conf[:max_per_domain]:
                uncertain.append({
                    "node_id": node.node_id,
                    "domain": node.domain,
                    "confidence": node.confidence,
                    "label": self._node_label(node),
                    "node_type": node.node_type,
                })

        return uncertain

    # ── Random walks ──────────────────────────────────────────────────

    def _random_walks(
        self, seeds: List[int],
    ) -> List[Dict[str, Any]]:
        """Perform multi-restart random walks from seed nodes.

        Each walk takes WALK_STEPS hops along outgoing edges, choosing
        edges at random. We record every node visited and flag
        "surprises" -- destinations in a different domain than the origin.
        """
        discoveries: List[Dict[str, Any]] = []
        visited_globally: Set[int] = set(seeds)

        walk_seeds = seeds[:WALK_RESTARTS] if len(seeds) >= WALK_RESTARTS else seeds
        # If we have fewer seeds than restarts, reuse some
        while len(walk_seeds) < WALK_RESTARTS and seeds:
            walk_seeds.append(random.choice(seeds))

        for start_id in walk_seeds:
            start_node = self.kg.nodes.get(start_id)
            if start_node is None:
                continue
            origin_domain = start_node.domain

            current_id = start_id
            path: List[int] = [current_id]

            for step in range(WALK_STEPS):
                try:
                    edges = self.kg.get_edges_from(current_id)
                except Exception:
                    break
                if not edges:
                    break

                # Weighted random selection: prefer higher-weight edges
                weights = [max(0.01, e.weight) for e in edges]
                total_w = sum(weights)
                probs = [w / total_w for w in weights]

                chosen_idx = self._weighted_choice(probs)
                next_id = edges[chosen_idx].to_node_id
                edge_type = edges[chosen_idx].edge_type

                if next_id not in self.kg.nodes:
                    break

                path.append(next_id)
                current_id = next_id

                # Check if this is a "surprise" -- different domain or not yet seen
                dest_node = self.kg.nodes[next_id]
                if next_id not in visited_globally:
                    visited_globally.add(next_id)
                    is_cross_domain = (
                        dest_node.domain != origin_domain
                        and dest_node.domain
                        and origin_domain
                    )
                    discoveries.append({
                        "node_id": next_id,
                        "origin_id": start_id,
                        "origin_domain": origin_domain,
                        "dest_domain": dest_node.domain,
                        "label": self._node_label(dest_node),
                        "origin_label": self._node_label(start_node),
                        "confidence": dest_node.confidence,
                        "edge_type": edge_type,
                        "cross_domain": is_cross_domain,
                        "walk_depth": step + 1,
                        "path": list(path),
                    })

        # Prioritize cross-domain and deeper discoveries
        discoveries.sort(
            key=lambda d: (d["cross_domain"], d["walk_depth"], 1 - d["confidence"]),
            reverse=True,
        )
        return discoveries

    def _weighted_choice(self, probabilities: List[float]) -> int:
        """Select an index based on probability weights."""
        r = random.random()
        cumulative = 0.0
        for idx, p in enumerate(probabilities):
            cumulative += p
            if r <= cumulative:
                return idx
        return len(probabilities) - 1

    # ── Hypothesis generation ─────────────────────────────────────────

    def _generate_hypotheses(
        self,
        seeds: List[int],
        uncertain: List[Dict[str, Any]],
        discoveries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Assemble walk results and uncertainty zones into hypotheses."""
        hypotheses: List[Dict[str, Any]] = []

        # Type 1: Walk-based hypotheses (connections found via random walk)
        for disc in discoveries[:5]:
            if not disc["cross_domain"]:
                continue
            hyp = self._walk_hypothesis(disc)
            if hyp:
                hypotheses.append(hyp)

        # Type 2: Uncertainty-based hypotheses (gaps in knowledge)
        for unc in uncertain[:4]:
            hyp = self._uncertainty_hypothesis(unc, seeds)
            if hyp:
                hypotheses.append(hyp)

        # Type 3: Bridging hypothesis (connect two discoveries)
        if len(discoveries) >= 2:
            hyp = self._bridging_hypothesis(discoveries[0], discoveries[1])
            if hyp:
                hypotheses.append(hyp)

        return hypotheses[:TARGET_HYPOTHESES * 2]  # Keep extras for selection

    def _walk_hypothesis(self, discovery: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build a hypothesis from a cross-domain random walk discovery."""
        origin = discovery["origin_label"]
        dest = discovery["label"]
        origin_domain = discovery["origin_domain"]
        dest_domain = discovery["dest_domain"]
        edge = discovery["edge_type"]
        depth = discovery["walk_depth"]

        content = (
            f"What if '{origin}' in {origin_domain} is connected to "
            f"'{dest}' in {dest_domain}? The knowledge graph links them "
            f"through a {depth}-step chain (via '{edge}' relationships). "
            f"This would suggest a cross-domain mechanism that current "
            f"understanding hasn't fully mapped."
        )

        return {
            "content": content,
            "evidence": [discovery["origin_id"], discovery["node_id"]],
            "confidence": max(0.25, min(0.55, 0.3 + discovery["confidence"] * 0.3)),
            "relevance": 0.5 + 0.1 * discovery["walk_depth"],
            "novelty": 0.85 if discovery["cross_domain"] else 0.6,
            "hyp_type": "walk_cross_domain",
        }

    def _uncertainty_hypothesis(
        self, uncertain_node: Dict[str, Any], seeds: List[int],
    ) -> Optional[Dict[str, Any]]:
        """Build a hypothesis about why an uncertain area exists."""
        label = uncertain_node["label"]
        domain = uncertain_node["domain"]
        conf = uncertain_node["confidence"]
        nid = uncertain_node["node_id"]

        # Find what edges exist from this uncertain node
        try:
            edges = self.kg.get_edges_from(nid)
            edge_count = len(edges)
            edge_types = {e.edge_type for e in edges}
        except Exception:
            edge_count = 0
            edge_types = set()

        if edge_count == 0:
            content = (
                f"There is an isolated knowledge fragment about '{label}' in "
                f"{domain} with low confidence ({conf:.2f}). What if this "
                f"represents a genuinely novel concept that hasn't been "
                f"connected to existing knowledge yet? Investigating its "
                f"origins could reveal an unexplored research direction."
            )
        else:
            types_str = ", ".join(sorted(edge_types)[:3])
            content = (
                f"The concept '{label}' in {domain} has low confidence "
                f"({conf:.2f}) despite having {edge_count} connections "
                f"({types_str}). What if the uncertainty stems from "
                f"conflicting evidence? Resolving this could strengthen "
                f"our understanding of the entire {domain} domain."
            )

        # Collect evidence: the uncertain node + closest seed
        evidence = [nid]
        if seeds:
            evidence.append(seeds[0])

        return {
            "content": content,
            "evidence": evidence,
            "confidence": max(0.2, 0.45 - conf * 0.3),  # Lower conf node -> slightly higher hypothesis conf
            "relevance": 0.4,
            "novelty": 0.9,
            "hyp_type": "uncertainty_gap",
        }

    def _bridging_hypothesis(
        self,
        disc_a: Dict[str, Any],
        disc_b: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Build a hypothesis that bridges two separate discoveries."""
        if disc_a["node_id"] == disc_b["node_id"]:
            return None

        label_a = disc_a["label"]
        label_b = disc_b["label"]
        domain_a = disc_a.get("dest_domain") or disc_a.get("origin_domain", "unknown")
        domain_b = disc_b.get("dest_domain") or disc_b.get("origin_domain", "unknown")

        content = (
            f"Two separate exploration paths converged on interesting "
            f"findings: '{label_a}' (in {domain_a}) and '{label_b}' "
            f"(in {domain_b}). What if these represent two facets of the "
            f"same underlying phenomenon? If a direct connection exists "
            f"between them, it could unify disparate observations into "
            f"a more coherent theory."
        )

        return {
            "content": content,
            "evidence": [disc_a["node_id"], disc_b["node_id"]],
            "confidence": 0.3,
            "relevance": 0.45,
            "novelty": 0.92,
            "hyp_type": "bridging",
        }

    # ── Selection ─────────────────────────────────────────────────────

    def _select_best_hypothesis(
        self, hypotheses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Select the most novel, non-repeated hypothesis."""
        # Filter out recently generated hypotheses
        recent = set(self._recent_hypothesis_hashes)
        fresh = [
            h for h in hypotheses
            if hash(h["content"][:80]) not in recent
        ]

        candidates = fresh if fresh else hypotheses

        # Score: novelty-weighted (Chesed values novelty above all)
        def score(h: Dict[str, Any]) -> float:
            return (
                h.get("novelty", 0.5) * 0.5
                + h.get("confidence", 0.3) * 0.2
                + h.get("relevance", 0.3) * 0.3
            )

        candidates.sort(key=score, reverse=True)
        return candidates[0]

    # ── Utilities ─────────────────────────────────────────────────────

    def _node_label(self, node: Any) -> str:
        """Extract a concise label from a KeterNode."""
        content = node.content if isinstance(node.content, dict) else {}
        for key in ("title", "name", "subject", "text", "description", "summary"):
            val = content.get(key)
            if val and isinstance(val, str):
                return val[:100]
        text = str(content)
        return text[:100] if len(text) > 100 else text

    def _empty_response(self, reason: str) -> CognitiveResponse:
        """Return a low-confidence response when exploration yields nothing."""
        logger.debug("Chesed: %s", reason)
        return self._make_response(
            content=reason,
            confidence=0.1,
            relevance=0.15,
            novelty=0.2,
            energy_cost=0.005,
        )
