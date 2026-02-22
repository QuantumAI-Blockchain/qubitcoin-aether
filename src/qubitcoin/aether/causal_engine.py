"""
Causal Discovery Engine — From Correlation to Causation

Implements a constraint-based causal discovery algorithm (simplified PC algorithm)
to distinguish causal relationships from mere correlations in the knowledge graph.

'supports' means correlation.  'causes' means the system has evidence that
intervening on the source node would change the target node.  This is Judea
Pearl's ladder of causation — the defining gap between correlation machines
and true intelligence.

Improvement #3 in the AGI stack.
"""
import math
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CausalDiscovery:
    """
    Discovers causal relationships in the knowledge graph using
    a simplified PC (Peter-Clark) algorithm.

    For each domain, builds a causal DAG:
    1. Start with a fully connected undirected graph over nodes in the domain
    2. Remove edges where conditional independence holds
    3. Orient edges using v-structures and heuristics
    4. Store causal edges as 'causes' edge type
    """

    def __init__(self, knowledge_graph=None) -> None:
        self.kg = knowledge_graph
        self._causal_edges_found: int = 0
        self._runs: int = 0
        self._last_run_block: int = 0

    def discover(self, domain: Optional[str] = None,
                 max_nodes: int = 200,
                 significance: float = 0.05) -> dict:
        """
        Run causal discovery on nodes in a specific domain.

        Args:
            domain: Domain to analyze (None = all domains)
            max_nodes: Max nodes to include (most recent first)
            significance: Threshold for conditional independence test

        Returns:
            Dict with causal_edges found and stats.
        """
        if not self.kg or not self.kg.nodes:
            return {'causal_edges': 0, 'nodes_analyzed': 0}

        self._runs += 1

        # Select nodes
        candidates = [
            n for n in self.kg.nodes.values()
            if (not domain or n.domain == domain)
            and n.node_type in ('observation', 'inference', 'assertion')
        ]
        candidates.sort(key=lambda n: n.source_block, reverse=True)
        candidates = candidates[:max_nodes]

        if len(candidates) < 3:
            return {'causal_edges': 0, 'nodes_analyzed': len(candidates)}

        node_ids = [n.node_id for n in candidates]
        node_set = set(node_ids)

        # Step 1: Build correlation matrix from existing edges
        corr = self._build_correlation_matrix(node_ids, node_set)

        # Step 2: PC skeleton — remove conditionally independent pairs
        skeleton = self._pc_skeleton(node_ids, corr, significance)

        # Step 3: Orient edges using v-structures
        directed = self._orient_edges(node_ids, skeleton, corr)

        # Step 4: Create 'causes' edges in the knowledge graph
        created = 0
        for from_id, to_id in directed:
            if from_id in self.kg.nodes and to_id in self.kg.nodes:
                # Check if this causal edge already exists
                exists = any(
                    e.from_node_id == from_id and e.to_node_id == to_id
                    and e.edge_type == 'causes'
                    for e in self.kg.edges
                )
                if not exists:
                    edge = self.kg.add_edge(from_id, to_id, 'causes', weight=0.8)
                    if edge:
                        created += 1

        self._causal_edges_found += created

        if created > 0:
            logger.info(
                f"Causal discovery ({domain or 'all'}): "
                f"found {created} causal edges from {len(candidates)} nodes"
            )

        return {
            'causal_edges': created,
            'nodes_analyzed': len(candidates),
            'skeleton_edges': len(skeleton),
            'directed_edges': len(directed),
            'domain': domain,
        }

    def discover_all_domains(self, block_height: int = 0,
                             min_domain_nodes: int = 10) -> int:
        """Run causal discovery across all domains with enough nodes.

        Args:
            block_height: Current block height for logging.
            min_domain_nodes: Minimum nodes for a domain to qualify.

        Returns:
            Total causal edges created.
        """
        if not self.kg:
            return 0

        self._last_run_block = block_height
        total = 0

        # Get domain stats
        domain_stats = self.kg.get_domain_stats()
        for domain, info in domain_stats.items():
            if info['count'] >= min_domain_nodes:
                result = self.discover(domain=domain)
                total += result['causal_edges']

        if total > 0:
            logger.info(f"Causal discovery sweep at block {block_height}: {total} total causal edges")

        return total

    def _build_correlation_matrix(self, node_ids: List[int],
                                   node_set: Set[int]) -> Dict[Tuple[int, int], float]:
        """Build pairwise correlation scores from edge connectivity and confidence."""
        corr: Dict[Tuple[int, int], float] = {}

        # Direct edge correlation
        for edge in self.kg.edges:
            if edge.from_node_id in node_set and edge.to_node_id in node_set:
                pair = (edge.from_node_id, edge.to_node_id)
                rev_pair = (edge.to_node_id, edge.from_node_id)
                # Weight based on edge type and confidence
                w = edge.weight
                if edge.edge_type == 'supports':
                    w *= 0.8
                elif edge.edge_type == 'derives':
                    w *= 0.9
                elif edge.edge_type == 'contradicts':
                    w *= -0.5
                corr[pair] = corr.get(pair, 0) + w
                corr[rev_pair] = corr.get(rev_pair, 0) + w * 0.5  # Weaker reverse

        # Confidence-based correlation (similar confidence = potential link)
        for i, nid_a in enumerate(node_ids):
            for nid_b in node_ids[i + 1:]:
                pair = (nid_a, nid_b)
                if pair not in corr:
                    na = self.kg.nodes[nid_a]
                    nb = self.kg.nodes[nid_b]
                    conf_sim = 1.0 - abs(na.confidence - nb.confidence)
                    # Temporal proximity
                    block_dist = abs(na.source_block - nb.source_block)
                    temporal_weight = 1.0 / (1.0 + block_dist / 100.0)
                    corr[pair] = conf_sim * temporal_weight * 0.3

        return corr

    def _pc_skeleton(self, node_ids: List[int],
                     corr: Dict[Tuple[int, int], float],
                     significance: float) -> List[Tuple[int, int]]:
        """Build skeleton by removing conditionally independent pairs.

        Simplified PC: remove pairs with correlation below significance threshold.
        """
        skeleton = []
        n = len(node_ids)

        for i in range(n):
            for j in range(i + 1, n):
                pair = (node_ids[i], node_ids[j])
                rev_pair = (node_ids[j], node_ids[i])
                score = max(corr.get(pair, 0), corr.get(rev_pair, 0))

                # Keep edge if correlation is significant
                if score > significance:
                    skeleton.append(pair)

        return skeleton

    def _orient_edges(self, node_ids: List[int],
                      skeleton: List[Tuple[int, int]],
                      corr: Dict[Tuple[int, int], float]) -> List[Tuple[int, int]]:
        """Orient undirected skeleton edges into directed causal edges.

        Uses heuristics:
        1. V-structures: if A-B and B-C exist but not A-C, orient A→B←C
        2. Temporal ordering: earlier blocks more likely to be causes
        3. Confidence asymmetry: higher-confidence nodes more likely to be causes
        """
        adj: Dict[int, Set[int]] = {nid: set() for nid in node_ids}
        for a, b in skeleton:
            adj[a].add(b)
            adj[b].add(a)

        directed: List[Tuple[int, int]] = []

        for a, b in skeleton:
            node_a = self.kg.nodes.get(a)
            node_b = self.kg.nodes.get(b)
            if not node_a or not node_b:
                continue

            # Temporal heuristic: earlier block → likely cause
            if node_a.source_block < node_b.source_block:
                score_a_to_b = 1.0
            elif node_b.source_block < node_a.source_block:
                score_a_to_b = -1.0
            else:
                score_a_to_b = 0.0

            # Confidence heuristic: higher confidence → likely cause
            conf_diff = node_a.confidence - node_b.confidence
            score_a_to_b += conf_diff * 0.5

            # V-structure detection: check for B-C where A and C not connected
            for c in adj.get(b, set()):
                if c != a and c not in adj.get(a, set()):
                    # V-structure A→B←C: both A and C cause B
                    score_a_to_b += 0.3

            # Asymmetric correlation
            fwd = corr.get((a, b), 0)
            rev = corr.get((b, a), 0)
            if fwd > rev:
                score_a_to_b += 0.2

            if score_a_to_b > 0:
                directed.append((a, b))
            elif score_a_to_b < 0:
                directed.append((b, a))
            # If score == 0, skip (ambiguous)

        return directed

    def get_stats(self) -> dict:
        return {
            'total_causal_edges_found': self._causal_edges_found,
            'total_runs': self._runs,
            'last_run_block': self._last_run_block,
        }
