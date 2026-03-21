"""
Causal Discovery Engine — From Correlation to Causation

Implements two constraint-based causal discovery algorithms:

1. **PC (Peter-Clark)** — Standard causal discovery assuming no latent
   confounders.  Produces a CPDAG (Completed Partially Directed Acyclic Graph).

2. **FCI (Fast Causal Inference)** — Extends PC to handle latent (hidden)
   variables and selection bias.  Produces a PAG (Partial Ancestral Graph)
   with four edge endpoint marks:
     - tail  (-)  : definite non-ancestor
     - arrow (>)  : definite ancestor
     - circle(o)  : ambiguous (could be tail or arrow)

   FCI edge notation:
     A --> B   : A causes B (no latent confounder)
     A <-> B   : Latent common cause (bidirected, hidden confounder)
     A o-> B   : A possibly causes B, or latent confounder present
     A o-o B   : Fully ambiguous endpoint

The key advance over naive correlation is conditional independence testing:
an edge A-B is removed if there exists a conditioning set S such that
A _||_ B | S.  This distinguishes genuine causal links from spurious
correlations induced by confounders.

After skeleton discovery, edges are oriented using:
  1. V-structure detection (unshielded colliders)
  2. Meek's orientation rules (acyclicity propagation)
  3. FCI discrimination rules (for latent variable detection)
  4. Domain heuristics (temporal ordering, confidence asymmetry)

'supports' means correlation.  'causes' means the system has evidence that
intervening on the source node would change the target node.  This is Judea
Pearl's ladder of causation — the defining gap between correlation machines
and true intelligence.

Improvement #3 in the AGI stack.
"""
import math
from itertools import combinations
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Maximum size of conditioning sets to test.  Higher values are more accurate
# but O(n^d) more expensive.  d=2 is tractable for <1000 nodes.
MAX_CONDITIONING_DEPTH: int = 3

# Node-type encoding for feature vectors
_NODE_TYPE_ENCODING: Dict[str, float] = {
    'assertion': 0.0,
    'observation': 0.25,
    'inference': 0.5,
    'axiom': 0.75,
    'prediction': 1.0,
    'meta_observation': 0.6,
}

# ---------------------------------------------------------------------------
# PAG (Partial Ancestral Graph) edge endpoint marks for FCI
# ---------------------------------------------------------------------------
# Each edge has two endpoints.  An endpoint mark can be:
#   TAIL   '-'  : definite non-ancestor
#   ARROW  '>'  : definite ancestor
#   CIRCLE 'o'  : ambiguous (could be tail or arrow)
TAIL: str = '-'
ARROW: str = '>'
CIRCLE: str = 'o'


class PAGEdge:
    """An edge in a Partial Ancestral Graph (PAG).

    Each edge has two endpoints, one for each node.  The mark at each endpoint
    indicates the causal relationship:
        mark_a='>' and mark_b='-'  means  A <-- B  (B causes A)
        mark_a='-' and mark_b='>'  means  A --> B  (A causes B)
        mark_a='>' and mark_b='>'  means  A <-> B  (bidirected / latent confounder)
        mark_a='o' and mark_b='>'  means  A o-> B  (A possibly causes B)
        mark_a='o' and mark_b='o'  means  A o-o B  (fully ambiguous)
    """
    __slots__ = ('node_a', 'node_b', 'mark_a', 'mark_b')

    def __init__(self, node_a: int, node_b: int,
                 mark_a: str = CIRCLE, mark_b: str = CIRCLE) -> None:
        self.node_a = node_a
        self.node_b = node_b
        self.mark_a = mark_a  # Mark at the node_a endpoint
        self.mark_b = mark_b  # Mark at the node_b endpoint

    def is_directed(self) -> bool:
        """True if A --> B (tail at A, arrow at B)."""
        return self.mark_a == TAIL and self.mark_b == ARROW

    def is_bidirected(self) -> bool:
        """True if A <-> B (arrow at both ends — latent confounder)."""
        return self.mark_a == ARROW and self.mark_b == ARROW

    def is_partially_directed(self) -> bool:
        """True if A o-> B (circle at A, arrow at B)."""
        return self.mark_a == CIRCLE and self.mark_b == ARROW

    def is_nondirected(self) -> bool:
        """True if A o-o B (circle at both ends)."""
        return self.mark_a == CIRCLE and self.mark_b == CIRCLE

    def has_arrowhead_at(self, node: int) -> bool:
        """Check if there is an arrowhead ('>') at the given node."""
        if node == self.node_a:
            return self.mark_a == ARROW
        if node == self.node_b:
            return self.mark_b == ARROW
        return False

    def has_tail_at(self, node: int) -> bool:
        """Check if there is a tail ('-') at the given node."""
        if node == self.node_a:
            return self.mark_a == TAIL
        if node == self.node_b:
            return self.mark_b == TAIL
        return False

    def has_circle_at(self, node: int) -> bool:
        """Check if there is a circle ('o') at the given node."""
        if node == self.node_a:
            return self.mark_a == CIRCLE
        if node == self.node_b:
            return self.mark_b == CIRCLE
        return False

    def get_mark_at(self, node: int) -> str:
        """Get the endpoint mark at the specified node."""
        if node == self.node_a:
            return self.mark_a
        if node == self.node_b:
            return self.mark_b
        raise ValueError(f"Node {node} not in edge ({self.node_a}, {self.node_b})")

    def set_mark_at(self, node: int, mark: str) -> None:
        """Set the endpoint mark at the specified node."""
        if node == self.node_a:
            self.mark_a = mark
        elif node == self.node_b:
            self.mark_b = mark
        else:
            raise ValueError(f"Node {node} not in edge ({self.node_a}, {self.node_b})")

    def other_node(self, node: int) -> int:
        """Return the other node in this edge."""
        if node == self.node_a:
            return self.node_b
        if node == self.node_b:
            return self.node_a
        raise ValueError(f"Node {node} not in edge ({self.node_a}, {self.node_b})")

    def to_dict(self) -> dict:
        """Serialize to a dictionary."""
        return {
            'node_a': self.node_a,
            'node_b': self.node_b,
            'mark_a': self.mark_a,
            'mark_b': self.mark_b,
            'type': self._edge_type_str(),
        }

    def _edge_type_str(self) -> str:
        """Human-readable edge type string."""
        if self.is_directed():
            return 'directed'
        if self.is_bidirected():
            return 'bidirected'
        if self.mark_a == ARROW and self.mark_b == TAIL:
            return 'directed_reverse'
        if self.is_partially_directed():
            return 'partially_directed'
        if self.mark_a == ARROW and self.mark_b == CIRCLE:
            return 'partially_directed_reverse'
        if self.is_nondirected():
            return 'nondirected'
        return 'other'

    def __repr__(self) -> str:
        left = '<' if self.mark_a == ARROW else ('o' if self.mark_a == CIRCLE else '-')
        right = '>' if self.mark_b == ARROW else ('o' if self.mark_b == CIRCLE else '-')
        return f"PAGEdge({self.node_a} {left}--{right} {self.node_b})"


class PAG:
    """Partial Ancestral Graph — the output of the FCI algorithm.

    A PAG represents an equivalence class of MAGs (Maximal Ancestral Graphs)
    that are Markov equivalent given the observed conditional independencies.
    It can express:
      - Definite causal relationships (-->)
      - Latent common causes (<->)
      - Ambiguous relationships (o->, o-o)
    """

    def __init__(self) -> None:
        self.edges: Dict[FrozenSet[int], PAGEdge] = {}
        self.nodes: Set[int] = set()

    def add_edge(self, node_a: int, node_b: int,
                 mark_a: str = CIRCLE, mark_b: str = CIRCLE) -> PAGEdge:
        """Add or update an edge in the PAG."""
        key = frozenset({node_a, node_b})
        self.nodes.add(node_a)
        self.nodes.add(node_b)
        edge = PAGEdge(node_a, node_b, mark_a, mark_b)
        self.edges[key] = edge
        return edge

    def get_edge(self, node_a: int, node_b: int) -> Optional[PAGEdge]:
        """Get edge between two nodes, or None if not present."""
        return self.edges.get(frozenset({node_a, node_b}))

    def has_edge(self, node_a: int, node_b: int) -> bool:
        """Check if an edge exists between two nodes."""
        return frozenset({node_a, node_b}) in self.edges

    def remove_edge(self, node_a: int, node_b: int) -> None:
        """Remove an edge from the PAG."""
        key = frozenset({node_a, node_b})
        self.edges.pop(key, None)

    def get_adjacent(self, node: int) -> List[int]:
        """Get all nodes adjacent to the given node."""
        neighbors: List[int] = []
        for key, edge in self.edges.items():
            if node in key:
                neighbors.append(edge.other_node(node))
        return neighbors

    def get_edges_with_arrowhead_at(self, node: int) -> List[PAGEdge]:
        """Get all edges that have an arrowhead pointing at the given node."""
        result: List[PAGEdge] = []
        for edge in self.edges.values():
            if edge.has_arrowhead_at(node):
                result.append(edge)
        return result

    def get_directed_edges(self) -> List[PAGEdge]:
        """Get all definitely directed edges (A --> B)."""
        return [e for e in self.edges.values()
                if e.is_directed() or (e.mark_a == ARROW and e.mark_b == TAIL)]

    def get_bidirected_edges(self) -> List[PAGEdge]:
        """Get all bidirected edges (A <-> B), indicating latent confounders."""
        return [e for e in self.edges.values() if e.is_bidirected()]

    def get_partially_directed_edges(self) -> List[PAGEdge]:
        """Get all partially directed edges (A o-> B or A <-o B)."""
        return [e for e in self.edges.values() if e.is_partially_directed()
                or (e.mark_a == ARROW and e.mark_b == CIRCLE)]

    def get_nondirected_edges(self) -> List[PAGEdge]:
        """Get all nondirected edges (A o-o B)."""
        return [e for e in self.edges.values() if e.is_nondirected()]

    def to_dict(self) -> dict:
        """Serialize the PAG to a dictionary."""
        return {
            'nodes': sorted(self.nodes),
            'edges': [e.to_dict() for e in self.edges.values()],
            'summary': {
                'total_edges': len(self.edges),
                'directed': len(self.get_directed_edges()),
                'bidirected': len(self.get_bidirected_edges()),
                'partially_directed': len(self.get_partially_directed_edges()),
                'nondirected': len(self.get_nondirected_edges()),
            },
        }

    def __repr__(self) -> str:
        return (f"PAG(nodes={len(self.nodes)}, edges={len(self.edges)}, "
                f"directed={len(self.get_directed_edges())}, "
                f"bidirected={len(self.get_bidirected_edges())})")


class CausalDiscovery:
    """
    Discovers causal relationships in the knowledge graph using the
    PC (Peter-Clark) algorithm with proper conditional independence testing.

    For each domain, builds a causal DAG:
    1. Build feature vectors for every candidate node
    2. Start with a fully connected undirected graph over candidate nodes
    3. Remove edges where conditional independence holds (PC skeleton)
    4. Orient edges using v-structures and Meek's rules
    5. Apply temporal + confidence heuristics for remaining undirected edges
    6. Store causal edges as 'causes' edge type in the knowledge graph
    """

    def __init__(self, knowledge_graph: Optional[object] = None) -> None:
        self.kg = knowledge_graph
        self._causal_edges_found: int = 0
        self._runs: int = 0
        self._last_run_block: int = 0
        # Separation sets: records the conditioning set that made (A, B)
        # conditionally independent — needed for v-structure detection
        self._sep_sets: Dict[FrozenSet[int], Set[int]] = {}

    # ------------------------------------------------------------------
    # Public API (signatures preserved for backward compatibility)
    # ------------------------------------------------------------------

    def discover(self, domain: Optional[str] = None,
                 max_nodes: int = 200,
                 significance: float = 0.05) -> dict:
        """
        Run causal discovery on nodes in a specific domain.

        Args:
            domain: Domain to analyze (None = all domains).
            max_nodes: Max nodes to include (most recent first).
            significance: p-value threshold for conditional independence.
                          Higher = more aggressive edge removal.

        Returns:
            Dict with causal_edges found and stats.
        """
        if not self.kg or not self.kg.nodes:
            return {'causal_edges': 0, 'nodes_analyzed': 0}

        self._runs += 1
        self._sep_sets.clear()

        # Select candidate nodes
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

        # Step 1: Build feature matrix
        features = self._build_feature_matrix(node_ids)

        # Step 2: PC skeleton with real conditional independence testing
        skeleton, adj = self._pc_skeleton_v2(node_ids, features, significance)

        # Step 3: Orient edges (v-structures + Meek's rules + heuristics)
        directed = self._orient_edges(node_ids, skeleton, adj, features)

        # Step 4: Create 'causes' edges in the knowledge graph
        created = 0
        for from_id, to_id in directed:
            if from_id in self.kg.nodes and to_id in self.kg.nodes:
                # O(degree) check via adjacency index instead of O(|E|) scan
                exists = any(
                    e.from_node_id == from_id and e.to_node_id == to_id
                    and e.edge_type == 'causes'
                    for e in self.kg.get_edges_from(from_id)
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

        domain_stats = self.kg.get_domain_stats()
        for domain, info in domain_stats.items():
            if info['count'] >= min_domain_nodes:
                result = self.discover(domain=domain)
                total += result['causal_edges']

        if total > 0:
            logger.info(
                f"Causal discovery sweep at block {block_height}: "
                f"{total} total causal edges"
            )

        return total

    def get_stats(self) -> dict:
        """Return summary statistics about causal discovery runs."""
        return {
            'total_causal_edges_found': self._causal_edges_found,
            'total_runs': self._runs,
            'last_run_block': self._last_run_block,
            'max_conditioning_depth': MAX_CONDITIONING_DEPTH,
        }

    def discover_temporal_causal(self, domain: Optional[str] = None,
                                  max_nodes: int = 200,
                                  time_lag: int = 10) -> dict:
        """Discover time-series causal relationships using temporal ordering.

        Nodes that consistently appear before other nodes (by source_block)
        and share features are candidate causes. This implements Granger-like
        causal inference using block height as the time dimension.

        Args:
            domain: Domain to analyze (None = all).
            max_nodes: Maximum nodes to include.
            time_lag: Maximum block distance for temporal causality.

        Returns:
            Dict with temporal causal edges found.
        """
        if not self.kg or not self.kg.nodes:
            return {'temporal_causal_edges': 0, 'nodes_analyzed': 0}

        # Select candidates
        candidates = [
            n for n in self.kg.nodes.values()
            if (not domain or n.domain == domain)
            and n.node_type in ('observation', 'inference', 'assertion')
            and n.source_block > 0
        ]
        candidates.sort(key=lambda n: n.source_block)
        candidates = candidates[-max_nodes:]

        if len(candidates) < 3:
            return {'temporal_causal_edges': 0, 'nodes_analyzed': len(candidates)}

        # Build feature matrix
        node_ids = [n.node_id for n in candidates]
        features = self._build_feature_matrix(node_ids)

        # For each pair (A, B) where A.source_block < B.source_block and
        # the difference is within time_lag, test if A's features predict B's
        temporal_edges: List[Tuple[int, int]] = []
        created = 0

        for i, node_a in enumerate(candidates):
            for j in range(i + 1, min(len(candidates), i + 20)):
                node_b = candidates[j]
                block_diff = node_b.source_block - node_a.source_block
                if block_diff <= 0 or block_diff > time_lag:
                    continue

                # Check feature correlation
                feat_a = features.get(node_a.node_id, [])
                feat_b = features.get(node_b.node_id, [])
                if not feat_a or not feat_b:
                    continue

                corr = abs(self._pearson(feat_a, feat_b))
                if corr > 0.6:
                    # Temporal ordering + correlation = candidate causality
                    # Check if edge already exists
                    existing = any(
                        e.from_node_id == node_a.node_id
                        and e.to_node_id == node_b.node_id
                        and e.edge_type == 'causes'
                        for e in self.kg.get_edges_from(node_a.node_id)
                    )
                    if not existing:
                        weight = corr * (1.0 - block_diff / (time_lag + 1))
                        edge = self.kg.add_edge(
                            node_a.node_id, node_b.node_id, 'causes',
                            weight=round(weight, 4)
                        )
                        if edge:
                            created += 1
                            temporal_edges.append((node_a.node_id, node_b.node_id))

                if created >= 20:
                    break
            if created >= 20:
                break

        self._causal_edges_found += created

        if created > 0:
            logger.info(
                f"Temporal causal discovery ({domain or 'all'}): "
                f"{created} temporal causal edges from {len(candidates)} nodes"
            )

        return {
            'temporal_causal_edges': created,
            'nodes_analyzed': len(candidates),
            'domain': domain,
            'time_lag': time_lag,
        }

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def _build_feature_matrix(self, node_ids: List[int]) -> Dict[int, List[float]]:
        """Build an enriched feature vector for each node.

        Each node is represented by a 10-dimensional vector:
            [confidence, source_block_normalized, node_type_encoded,
             in_degree, out_degree, avg_neighbor_confidence,
             content_length, has_numeric_data, edge_type_diversity,
             domain_encoded]

        Uses content semantics (not just node_type) for richer encoding.

        Args:
            node_ids: Node IDs to build features for.

        Returns:
            Mapping from node_id to its feature vector.
        """
        if not node_ids:
            return {}

        # Compute source_block normalization bounds
        min_block = min(self.kg.nodes[nid].source_block for nid in node_ids)
        max_block = max(self.kg.nodes[nid].source_block for nid in node_ids)
        block_range = max_block - min_block if max_block > min_block else 1.0

        # Collect all domains for encoding
        domain_set: List[str] = sorted(set(
            self.kg.nodes[nid].domain or 'general'
            for nid in node_ids if nid in self.kg.nodes
        ))
        domain_map = {d: i / max(len(domain_set), 1) for i, d in enumerate(domain_set)}

        features: Dict[int, List[float]] = {}
        for nid in node_ids:
            node = self.kg.nodes[nid]

            # Confidence [0, 1]
            confidence = node.confidence

            # Source block normalized to [0, 1]
            source_block_norm = (node.source_block - min_block) / block_range

            # Node type encoded to a float
            type_encoded = _NODE_TYPE_ENCODING.get(node.node_type, 0.5)

            # In-degree and out-degree (from adjacency index)
            out_edges = self.kg.get_edges_from(nid)
            in_edges = self.kg.get_edges_to(nid)
            out_degree = float(len(out_edges))
            in_degree = float(len(in_edges))

            # Normalize degrees by log(1 + d) to compress heavy tails
            out_degree = math.log1p(out_degree)
            in_degree = math.log1p(in_degree)

            # Average neighbor confidence
            neighbor_ids: Set[int] = set()
            for e in out_edges:
                neighbor_ids.add(e.to_node_id)
            for e in in_edges:
                neighbor_ids.add(e.from_node_id)
            if neighbor_ids:
                avg_neighbor_conf = sum(
                    self.kg.nodes[n].confidence
                    for n in neighbor_ids if n in self.kg.nodes
                ) / len(neighbor_ids)
            else:
                avg_neighbor_conf = confidence  # Self-fill if isolated

            # Content semantics: text length (proxy for information richness)
            content_text = str(node.content.get('text', ''))
            content_length = min(1.0, len(content_text) / 500.0)

            # Content semantics: presence of numeric data
            import re
            has_numeric = 1.0 if re.search(r'\d+\.?\d*', content_text) else 0.0

            # Edge type diversity (Shannon entropy of edge types)
            edge_types: Dict[str, int] = {}
            for e in out_edges:
                edge_types[e.edge_type] = edge_types.get(e.edge_type, 0) + 1
            for e in in_edges:
                edge_types[e.edge_type] = edge_types.get(e.edge_type, 0) + 1
            total_edges = sum(edge_types.values())
            edge_diversity = 0.0
            if total_edges > 0:
                for count in edge_types.values():
                    p = count / total_edges
                    if p > 0:
                        edge_diversity -= p * math.log2(p)
                # Normalize by log2(max possible types)
                edge_diversity = min(1.0, edge_diversity / 3.0)

            # Domain encoding
            domain_encoded = domain_map.get(node.domain or 'general', 0.5)

            features[nid] = [
                confidence,
                source_block_norm,
                type_encoded,
                in_degree,
                out_degree,
                avg_neighbor_conf,
                content_length,
                has_numeric,
                edge_diversity,
                domain_encoded,
            ]

        return features

    # ------------------------------------------------------------------
    # Partial correlation & conditional independence
    # ------------------------------------------------------------------

    @staticmethod
    def _partial_correlation(features: Dict[int, List[float]],
                             a_id: int, b_id: int,
                             conditioning_ids: List[int]) -> float:
        """Compute partial correlation between nodes a and b, controlling
        for the conditioning set.

        Uses recursive formula for partial correlation:
            r_{ab|S} = (r_{ab|S\\c} - r_{ac|S\\c} * r_{bc|S\\c}) /
                       sqrt((1 - r_{ac|S\\c}^2) * (1 - r_{bc|S\\c}^2))

        Base case (empty conditioning set): Pearson correlation between
        feature vectors of a and b.

        Args:
            features: Node-ID to feature-vector mapping.
            a_id: First node.
            b_id: Second node.
            conditioning_ids: IDs of nodes to condition on.

        Returns:
            Partial correlation coefficient in [-1, 1].  Returns 0.0 if
            computation is degenerate (zero variance, etc.).
        """
        if not conditioning_ids:
            # Base case: Pearson correlation between feature vectors
            return CausalDiscovery._pearson(features.get(a_id, []),
                                            features.get(b_id, []))

        # Recursive case: remove last conditioning variable
        rest = conditioning_ids[:-1]
        c_id = conditioning_ids[-1]

        r_ab = CausalDiscovery._partial_correlation(features, a_id, b_id, rest)
        r_ac = CausalDiscovery._partial_correlation(features, a_id, c_id, rest)
        r_bc = CausalDiscovery._partial_correlation(features, b_id, c_id, rest)

        denom_sq = (1.0 - r_ac * r_ac) * (1.0 - r_bc * r_bc)
        if denom_sq <= 1e-12:
            return 0.0

        return (r_ab - r_ac * r_bc) / math.sqrt(denom_sq)

    @staticmethod
    def _pearson(x: List[float], y: List[float]) -> float:
        """Pearson correlation between two vectors of equal length.

        Returns 0.0 if either vector is empty or has zero variance.
        """
        n = min(len(x), len(y))
        if n == 0:
            return 0.0

        mean_x = sum(x[:n]) / n
        mean_y = sum(y[:n]) / n

        cov = 0.0
        var_x = 0.0
        var_y = 0.0
        for i in range(n):
            dx = x[i] - mean_x
            dy = y[i] - mean_y
            cov += dx * dy
            var_x += dx * dx
            var_y += dy * dy

        if var_x < 1e-12 or var_y < 1e-12:
            return 0.0

        return cov / math.sqrt(var_x * var_y)

    def _test_conditional_independence(self, node_a_id: int,
                                       node_b_id: int,
                                       conditioning_set: List[int],
                                       features: Dict[int, List[float]]) -> float:
        """Test whether node_a and node_b are conditionally independent
        given the conditioning_set using Fisher's z-transform of the
        partial correlation.

        Args:
            node_a_id: First node.
            node_b_id: Second node.
            conditioning_set: Nodes to condition on.
            features: Feature matrix.

        Returns:
            A p-value-like score in [0, 1].  Higher values indicate stronger
            evidence of conditional independence.  The score is derived from
            Fisher's z-transform: z = 0.5 * ln((1+r)/(1-r)) * sqrt(n-|S|-3),
            converted to a p-value approximation via the standard normal CDF.
        """
        r = self._partial_correlation(features, node_a_id, node_b_id,
                                      conditioning_set)

        # Number of "samples" — use number of feature dimensions as proxy
        # since we don't have i.i.d. samples; clamp to avoid negative dof
        n = len(features)
        dof = n - len(conditioning_set) - 3
        if dof < 1:
            # Not enough effective degrees of freedom to test
            return 0.0

        # Fisher's z-transform
        r_clamped = max(-0.9999, min(0.9999, r))
        z = 0.5 * math.log((1.0 + r_clamped) / (1.0 - r_clamped))
        z_stat = abs(z) * math.sqrt(dof)

        # Approximate two-sided p-value using the error function
        # P(|Z| > z_stat) = 2 * (1 - Phi(z_stat)) = erfc(z_stat / sqrt(2))
        p_value = math.erfc(z_stat / math.sqrt(2.0))

        return p_value

    # ------------------------------------------------------------------
    # PC Skeleton (Phase 1 of PC algorithm)
    # ------------------------------------------------------------------

    def _pc_skeleton_v2(self, node_ids: List[int],
                        features: Dict[int, List[float]],
                        significance: float
                        ) -> Tuple[List[Tuple[int, int]], Dict[int, Set[int]]]:
        """Build the PC skeleton by iteratively testing conditional independence.

        Standard PC algorithm:
        1. Start with fully connected undirected graph.
        2. For conditioning set sizes d = 0, 1, 2, ..., MAX_CONDITIONING_DEPTH:
           a. For each adjacent pair (A, B):
              - Test CI given each subset S of size d from adj(A)\\{B}
              - If A _||_ B | S for any S, remove edge A-B and record S in sep_sets
        3. Return surviving edges.

        Args:
            node_ids: Candidate node IDs.
            features: Feature matrix from _build_feature_matrix.
            significance: p-value threshold; edges with p > significance
                          are removed (declared conditionally independent).

        Returns:
            (skeleton_edges, adjacency_dict)
        """
        n = len(node_ids)
        id_set = set(node_ids)

        # Initialize fully connected adjacency (undirected)
        adj: Dict[int, Set[int]] = {nid: set() for nid in node_ids}
        for i in range(n):
            for j in range(i + 1, n):
                adj[node_ids[i]].add(node_ids[j])
                adj[node_ids[j]].add(node_ids[i])

        self._sep_sets.clear()

        # Iterate over conditioning set sizes
        for d in range(MAX_CONDITIONING_DEPTH + 1):
            # Collect edges to test (snapshot before modification)
            edges_to_test: List[Tuple[int, int]] = []
            for a in node_ids:
                for b in list(adj[a]):
                    if a < b:  # Avoid testing both (a,b) and (b,a)
                        edges_to_test.append((a, b))

            for a, b in edges_to_test:
                if b not in adj.get(a, set()):
                    continue  # Already removed in this pass

                # Neighbors of a excluding b (potential conditioning variables)
                neighbors_a = adj[a] - {b}
                # Neighbors of b excluding a
                neighbors_b = adj[b] - {a}
                # Union of neighbors for conditioning candidates
                cond_candidates = list((neighbors_a | neighbors_b) & id_set)

                if len(cond_candidates) < d:
                    continue  # Not enough neighbors for this depth

                # Test all subsets of size d
                found_independent = False
                for subset in combinations(cond_candidates, d):
                    cond_list = list(subset)
                    p_value = self._test_conditional_independence(
                        a, b, cond_list, features
                    )
                    if p_value > significance:
                        # Conditionally independent — remove edge
                        adj[a].discard(b)
                        adj[b].discard(a)
                        self._sep_sets[frozenset({a, b})] = set(subset)
                        found_independent = True
                        break

                if found_independent:
                    continue

        # Collect surviving skeleton edges
        skeleton: List[Tuple[int, int]] = []
        seen: Set[FrozenSet[int]] = set()
        for a in node_ids:
            for b in adj[a]:
                pair = frozenset({a, b})
                if pair not in seen:
                    seen.add(pair)
                    skeleton.append((min(a, b), max(a, b)))

        return skeleton, adj

    # ------------------------------------------------------------------
    # Edge orientation (Phase 2 of PC algorithm)
    # ------------------------------------------------------------------

    def _orient_edges(self, node_ids: List[int],
                      skeleton: List[Tuple[int, int]],
                      adj: Dict[int, Set[int]],
                      features: Dict[int, List[float]]
                      ) -> List[Tuple[int, int]]:
        """Orient skeleton edges into a causal DAG.

        Three-phase orientation:
        1. V-structure detection: For unshielded triples A-B-C where A and C
           are not adjacent and B is NOT in sep(A, C), orient A -> B <- C.
        2. Meek's rules: Propagate orientations to avoid new v-structures
           and cycles.
        3. Domain heuristics: For any remaining undirected edges, use temporal
           ordering and confidence asymmetry.

        Args:
            node_ids: All candidate node IDs.
            skeleton: Undirected skeleton edges as (min_id, max_id) tuples.
            adj: Adjacency dict from _pc_skeleton_v2.
            features: Feature matrix.

        Returns:
            List of directed (from, to) causal edges.
        """
        # Orientation state: directed edges discovered so far
        # oriented[a] = set of nodes b such that a -> b
        oriented: Dict[int, Set[int]] = {nid: set() for nid in node_ids}
        # Track which undirected edges remain
        undirected: Set[FrozenSet[int]] = set()
        for a, b in skeleton:
            undirected.add(frozenset({a, b}))

        # ------ Phase 1: V-structure detection ------
        self._detect_v_structures(node_ids, adj, oriented, undirected)

        # ------ Phase 2: Meek's rules ------
        self._apply_meek_rules(node_ids, adj, oriented, undirected)

        # ------ Phase 3: Domain heuristics for remaining undirected edges ------
        self._apply_domain_heuristics(undirected, oriented)

        # Collect all directed edges
        directed: List[Tuple[int, int]] = []
        for a in node_ids:
            for b in oriented[a]:
                directed.append((a, b))

        return directed

    def _detect_v_structures(self, node_ids: List[int],
                             adj: Dict[int, Set[int]],
                             oriented: Dict[int, Set[int]],
                             undirected: Set[FrozenSet[int]]) -> None:
        """Detect and orient v-structures (unshielded colliders).

        For every unshielded triple A - B - C where:
          - A and B are adjacent (in skeleton)
          - B and C are adjacent (in skeleton)
          - A and C are NOT adjacent (not in skeleton)
          - B is NOT in sep(A, C)
        Orient as A -> B <- C.

        Modifies oriented and undirected in place.
        """
        for b in node_ids:
            neighbors_b = list(adj.get(b, set()))
            if len(neighbors_b) < 2:
                continue

            for i in range(len(neighbors_b)):
                for j in range(i + 1, len(neighbors_b)):
                    a = neighbors_b[i]
                    c = neighbors_b[j]

                    # Check unshielded: A and C must NOT be adjacent
                    if c in adj.get(a, set()):
                        continue

                    # Check if B is in the separation set of (A, C)
                    sep_key = frozenset({a, c})
                    sep_set = self._sep_sets.get(sep_key, set())

                    if b not in sep_set:
                        # V-structure: orient A -> B <- C
                        self._orient_edge(a, b, oriented, undirected)
                        self._orient_edge(c, b, oriented, undirected)

    def _apply_meek_rules(self, node_ids: List[int],
                          adj: Dict[int, Set[int]],
                          oriented: Dict[int, Set[int]],
                          undirected: Set[FrozenSet[int]]) -> None:
        """Apply Meek's three orientation rules until convergence.

        Rule 1 (Acyclicity): If A -> B and B - C (undirected) and A, C
                not adjacent, orient B -> C (to avoid new v-structure A -> B <- C).
        Rule 2 (Acyclicity): If A -> B -> C and A - C (undirected),
                orient A -> C (to avoid cycle).
        Rule 3 (No new v-structure): If A - B (undirected), and there exist
                C, D both adjacent to B with C -> A and D -> A, and C, D not
                adjacent, orient A -> B.

        Modifies oriented and undirected in place.
        """
        changed = True
        max_iterations = 20  # Safety bound
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1

            for edge_pair in list(undirected):
                pair_list = list(edge_pair)
                if len(pair_list) != 2:
                    continue
                x, y = pair_list[0], pair_list[1]

                # Try both orientations for each rule
                for a, b in [(x, y), (y, x)]:

                    # Rule 1: Exists C such that C -> A (directed), C not adj B
                    # => orient A -> B
                    rule1 = False
                    for c in node_ids:
                        if c == a or c == b:
                            continue
                        if a in oriented.get(c, set()):  # C -> A
                            if b not in adj.get(c, set()):  # C, B not adjacent
                                rule1 = True
                                break
                    if rule1:
                        self._orient_edge(a, b, oriented, undirected)
                        changed = True
                        break

                    # Rule 2: Exists C such that A -> C (directed) and C -> B (directed)
                    # => orient A -> B (to avoid creating a new collider or cycle)
                    rule2 = False
                    for c in oriented.get(a, set()):  # A -> C
                        if b in oriented.get(c, set()):  # C -> B
                            rule2 = True
                            break
                    if rule2:
                        self._orient_edge(a, b, oriented, undirected)
                        changed = True
                        break

                    # Rule 3: Two non-adjacent nodes C, D both adj to A and B,
                    # with C -> B and D -> B, and A - C (undirected), A - D (undirected)
                    # => orient A -> B
                    rule3 = False
                    adj_a = adj.get(a, set())
                    adj_b_set = adj.get(b, set())
                    common = list(adj_a & adj_b_set - {a, b})
                    for ci in range(len(common)):
                        for di in range(ci + 1, len(common)):
                            c_node = common[ci]
                            d_node = common[di]
                            # C and D not adjacent
                            if d_node in adj.get(c_node, set()):
                                continue
                            # C -> B and D -> B (directed)
                            if (b in oriented.get(c_node, set())
                                    and b in oriented.get(d_node, set())):
                                # A - C and A - D (undirected)
                                if (frozenset({a, c_node}) in undirected
                                        and frozenset({a, d_node}) in undirected):
                                    rule3 = True
                                    break
                        if rule3:
                            break

                    if rule3:
                        self._orient_edge(a, b, oriented, undirected)
                        changed = True
                        break

    def _apply_domain_heuristics(self, undirected: Set[FrozenSet[int]],
                                 oriented: Dict[int, Set[int]]) -> None:
        """Orient remaining undirected edges using domain-specific heuristics.

        For each remaining undirected edge:
          - Temporal: earlier source_block is more likely the cause
          - Confidence: higher confidence node is more likely the cause

        Modifies oriented and undirected in place.
        """
        for edge_pair in list(undirected):
            pair_list = list(edge_pair)
            if len(pair_list) != 2:
                continue
            a, b = pair_list[0], pair_list[1]

            node_a = self.kg.nodes.get(a)
            node_b = self.kg.nodes.get(b)
            if not node_a or not node_b:
                continue

            score_a_to_b = 0.0

            # Temporal heuristic: earlier block -> likely cause
            if node_a.source_block < node_b.source_block:
                score_a_to_b += 1.0
            elif node_b.source_block < node_a.source_block:
                score_a_to_b -= 1.0

            # Confidence heuristic: higher confidence -> likely cause
            conf_diff = node_a.confidence - node_b.confidence
            score_a_to_b += conf_diff * 0.5

            if score_a_to_b > 0:
                self._orient_edge(a, b, oriented, undirected)
            elif score_a_to_b < 0:
                self._orient_edge(b, a, oriented, undirected)
            # If score == 0, leave undirected (ambiguous) — don't add edge

    @staticmethod
    def _orient_edge(from_id: int, to_id: int,
                     oriented: Dict[int, Set[int]],
                     undirected: Set[FrozenSet[int]]) -> None:
        """Orient an undirected edge from -> to.

        Removes the undirected edge and records the direction.
        No-op if the edge is already oriented in the opposite direction
        (to avoid creating a cycle in the simple case).
        """
        pair = frozenset({from_id, to_id})

        # Don't reverse an already-oriented edge
        if from_id in oriented.get(to_id, set()):
            return

        undirected.discard(pair)
        oriented.setdefault(from_id, set()).add(to_id)

    # ------------------------------------------------------------------
    # Legacy compatibility shims (kept for any external callers)
    # ------------------------------------------------------------------

    def _build_correlation_matrix(self, node_ids: List[int],
                                  node_set: Set[int]) -> Dict[Tuple[int, int], float]:
        """Legacy shim — delegates to feature-based partial correlation.

        Builds a pairwise correlation dict from feature vectors for
        backward compatibility with any code that still calls this method.
        """
        features = self._build_feature_matrix(node_ids)
        corr: Dict[Tuple[int, int], float] = {}
        for i, a in enumerate(node_ids):
            for b in node_ids[i + 1:]:
                r = self._pearson(features.get(a, []), features.get(b, []))
                corr[(a, b)] = r
                corr[(b, a)] = r
        return corr

    def _pc_skeleton(self, node_ids: List[int],
                     corr: Dict[Tuple[int, int], float],
                     significance: float) -> List[Tuple[int, int]]:
        """Legacy shim — uses new PC skeleton under the hood."""
        features = self._build_feature_matrix(node_ids)
        skeleton, _ = self._pc_skeleton_v2(node_ids, features, significance)
        return skeleton

    # ==================================================================
    # FCI (Fast Causal Inference) Algorithm
    # ==================================================================
    # FCI extends PC to handle latent (hidden) confounders and selection
    # bias.  The output is a PAG (Partial Ancestral Graph) instead of a
    # CPDAG.  PAG edges use three endpoint marks: tail (-), arrow (>),
    # circle (o).
    #
    # Algorithm outline:
    #   1. Run PC skeleton (same as PC Phase 1)
    #   2. Orient v-structures (same as PC)
    #   3. Run "possible d-sep" removal pass (FCI-specific)
    #      - For each remaining edge A-B, test CI conditioning on
    #        possible d-separating sets (supersets of PC sep sets)
    #      - This can remove edges that PC missed due to latent variables
    #   4. Re-orient: v-structures on the refined skeleton
    #   5. Apply FCI orientation rules R1-R4 + discrimination paths
    #   6. Convert remaining circle marks where possible
    # ==================================================================

    def discover_with_fci(self, domain: Optional[str] = None,
                          max_nodes: int = 200,
                          significance: float = 0.05) -> dict:
        """Run FCI causal discovery and return a PAG.

        The FCI algorithm handles latent confounders that PC cannot detect.
        When a latent common cause exists between two observed variables,
        FCI will produce a bidirected edge (A <-> B) instead of incorrectly
        directing A -> B or B -> A.

        Args:
            domain: Domain to analyze (None = all domains).
            max_nodes: Max nodes to include (most recent first).
            significance: p-value threshold for conditional independence.

        Returns:
            Dict with PAG, causal edges, latent confounders detected, and stats.
        """
        if not self.kg or not self.kg.nodes:
            return {
                'causal_edges': 0,
                'latent_confounders': 0,
                'nodes_analyzed': 0,
                'pag': PAG(),
            }

        self._runs += 1
        self._sep_sets.clear()

        # Select candidate nodes
        candidates = [
            n for n in self.kg.nodes.values()
            if (not domain or n.domain == domain)
            and n.node_type in ('observation', 'inference', 'assertion')
        ]
        candidates.sort(key=lambda n: n.source_block, reverse=True)
        candidates = candidates[:max_nodes]

        if len(candidates) < 3:
            return {
                'causal_edges': 0,
                'latent_confounders': 0,
                'nodes_analyzed': len(candidates),
                'pag': PAG(),
            }

        node_ids = [n.node_id for n in candidates]

        # Step 1: Build feature matrix
        features = self._build_feature_matrix(node_ids)

        # Step 2: PC skeleton (shared with PC algorithm)
        skeleton, adj = self._pc_skeleton_v2(node_ids, features, significance)

        # Step 3: Initial v-structure orientation (shared with PC)
        oriented: Dict[int, Set[int]] = {nid: set() for nid in node_ids}
        undirected: Set[FrozenSet[int]] = set()
        for a, b in skeleton:
            undirected.add(frozenset({a, b}))
        self._detect_v_structures(node_ids, adj, oriented, undirected)

        # Step 4: FCI possible-d-sep removal pass
        adj_refined, sep_sets_refined = self._fci_possible_dsep_removal(
            node_ids, adj, oriented, features, significance
        )
        # Merge refined separation sets
        self._sep_sets.update(sep_sets_refined)

        # Step 5: Re-collect skeleton from refined adjacency
        refined_skeleton: List[Tuple[int, int]] = []
        seen: Set[FrozenSet[int]] = set()
        for a in node_ids:
            for b in adj_refined.get(a, set()):
                pair = frozenset({a, b})
                if pair not in seen:
                    seen.add(pair)
                    refined_skeleton.append((min(a, b), max(a, b)))

        # Step 6: Build PAG from refined skeleton
        pag = PAG()
        for nid in node_ids:
            pag.nodes.add(nid)

        # Initialize all edges as o-o (fully ambiguous)
        for a, b in refined_skeleton:
            pag.add_edge(a, b, CIRCLE, CIRCLE)

        # Step 7: Re-orient v-structures on refined skeleton
        self._fci_orient_v_structures(node_ids, adj_refined, pag)

        # Step 8: Apply FCI orientation rules R1-R4 + R8-R10
        self._fci_apply_rules(node_ids, adj_refined, pag)

        # Step 9: Create 'causes' edges in KG for directed PAG edges +
        #         store latent confounder info
        created = 0
        latent_count = len(pag.get_bidirected_edges())

        for edge in pag.edges.values():
            # Only add definitely directed edges to KG
            if edge.is_directed():
                from_id, to_id = edge.node_a, edge.node_b
            elif edge.mark_a == ARROW and edge.mark_b == TAIL:
                from_id, to_id = edge.node_b, edge.node_a
            else:
                continue

            if from_id in self.kg.nodes and to_id in self.kg.nodes:
                exists = any(
                    e.from_node_id == from_id and e.to_node_id == to_id
                    and e.edge_type == 'causes'
                    for e in self.kg.get_edges_from(from_id)
                )
                if not exists:
                    kg_edge = self.kg.add_edge(from_id, to_id, 'causes', weight=0.85)
                    if kg_edge:
                        created += 1

        self._causal_edges_found += created

        if created > 0 or latent_count > 0:
            logger.info(
                f"FCI discovery ({domain or 'all'}): "
                f"{created} causal edges, {latent_count} latent confounders "
                f"from {len(candidates)} nodes"
            )

        return {
            'causal_edges': created,
            'latent_confounders': latent_count,
            'nodes_analyzed': len(candidates),
            'skeleton_edges': len(refined_skeleton),
            'pag': pag,
            'pag_summary': pag.to_dict()['summary'],
            'domain': domain,
        }

    # ------------------------------------------------------------------
    # FCI Step 3: Possible-d-sep removal
    # ------------------------------------------------------------------

    def _fci_possible_dsep_removal(
        self,
        node_ids: List[int],
        adj: Dict[int, Set[int]],
        oriented: Dict[int, Set[int]],
        features: Dict[int, List[float]],
        significance: float,
    ) -> Tuple[Dict[int, Set[int]], Dict[FrozenSet[int], Set[int]]]:
        """Remove edges using possible d-separating sets.

        In FCI, after the initial skeleton and v-structure orientation, we
        revisit each edge and test conditional independence using "possible
        d-separating" sets — these are larger than the adjacency-based
        sets used in PC, and can catch independencies that PC misses when
        latent variables are present.

        A node C is in PossibleDSep(A, B) if there is an undirected path
        from A to C in the partially oriented graph such that every
        intermediate node is a collider on the path or is adjacent to A.

        For tractability, we limit possible-d-sep to nodes within distance 2
        in the adjacency graph.

        Args:
            node_ids: All candidate node IDs.
            adj: Current adjacency dict.
            oriented: Current directed edges.
            features: Feature matrix.
            significance: CI test threshold.

        Returns:
            (refined_adj, new_sep_sets) — refined adjacency and new separation sets.
        """
        # Deep copy adjacency
        refined_adj: Dict[int, Set[int]] = {
            nid: set(neighbors) for nid, neighbors in adj.items()
        }
        new_sep_sets: Dict[FrozenSet[int], Set[int]] = {}
        id_set = set(node_ids)

        # Collect edges to test
        edges_to_test: List[Tuple[int, int]] = []
        for a in node_ids:
            for b in list(refined_adj.get(a, set())):
                if a < b:
                    edges_to_test.append((a, b))

        for a, b in edges_to_test:
            if b not in refined_adj.get(a, set()):
                continue  # Already removed

            # Compute possible-d-sep set for this edge
            pds = self._compute_possible_dsep(a, b, refined_adj, oriented, id_set)

            # Test subsets of possible-d-sep up to MAX_CONDITIONING_DEPTH
            found_independent = False
            pds_list = list(pds)

            for d in range(min(len(pds_list) + 1, MAX_CONDITIONING_DEPTH + 1)):
                if found_independent:
                    break
                for subset in combinations(pds_list, d):
                    cond_list = list(subset)
                    p_value = self._test_conditional_independence(
                        a, b, cond_list, features
                    )
                    if p_value > significance:
                        refined_adj[a].discard(b)
                        refined_adj[b].discard(a)
                        new_sep_sets[frozenset({a, b})] = set(subset)
                        found_independent = True
                        break

        return refined_adj, new_sep_sets

    def _compute_possible_dsep(
        self,
        a: int,
        b: int,
        adj: Dict[int, Set[int]],
        oriented: Dict[int, Set[int]],
        id_set: Set[int],
    ) -> Set[int]:
        """Compute the possible d-separating set for edge (a, b).

        PossibleDSep(a, b) includes nodes reachable from a along paths where
        every node (except a) is either:
          - Adjacent to a, OR
          - A "possible collider" (has arrowheads pointing at it from both
            sides on the path)

        For tractability, we use a simplified version: all nodes within
        distance 2 from either a or b in the undirected skeleton, excluding
        a and b themselves.

        Args:
            a: First endpoint of the edge.
            b: Second endpoint of the edge.
            adj: Adjacency dictionary.
            oriented: Directed edges discovered so far.
            id_set: Set of all candidate node IDs.

        Returns:
            Set of node IDs that form the possible d-separating set.
        """
        pds: Set[int] = set()

        # Distance-1 neighbors of a and b
        neighbors_a = adj.get(a, set()) - {b}
        neighbors_b = adj.get(b, set()) - {a}
        pds.update(neighbors_a)
        pds.update(neighbors_b)

        # Distance-2 neighbors (neighbors of neighbors)
        for n in list(neighbors_a):
            pds.update(adj.get(n, set()) - {a, b})
        for n in list(neighbors_b):
            pds.update(adj.get(n, set()) - {a, b})

        # Remove a and b themselves
        pds.discard(a)
        pds.discard(b)

        # Keep only nodes in our candidate set
        return pds & id_set

    # ------------------------------------------------------------------
    # FCI Step 7: V-structure orientation on PAG
    # ------------------------------------------------------------------

    def _fci_orient_v_structures(
        self,
        node_ids: List[int],
        adj: Dict[int, Set[int]],
        pag: PAG,
    ) -> None:
        """Orient v-structures in the PAG.

        Same logic as PC v-structure detection, but using PAG edge marks:
        For unshielded triple A - B - C where B not in sep(A, C),
        orient as A *-> B <-* C (set arrowheads at B on both edges).

        Args:
            node_ids: All candidate node IDs.
            adj: Adjacency dictionary.
            pag: The PAG to modify in place.
        """
        for b in node_ids:
            neighbors_b = list(adj.get(b, set()))
            if len(neighbors_b) < 2:
                continue

            for i in range(len(neighbors_b)):
                for j in range(i + 1, len(neighbors_b)):
                    a = neighbors_b[i]
                    c = neighbors_b[j]

                    # Unshielded: A and C not adjacent
                    if c in adj.get(a, set()):
                        continue

                    # Check if B is in sep(A, C)
                    sep_key = frozenset({a, c})
                    sep_set = self._sep_sets.get(sep_key, set())

                    if b not in sep_set:
                        # Orient A *-> B <-* C
                        edge_ab = pag.get_edge(a, b)
                        edge_cb = pag.get_edge(c, b)
                        if edge_ab:
                            edge_ab.set_mark_at(b, ARROW)
                        if edge_cb:
                            edge_cb.set_mark_at(b, ARROW)

    # ------------------------------------------------------------------
    # FCI Step 8: Orientation rules R1-R4, R8-R10
    # ------------------------------------------------------------------

    def _fci_apply_rules(
        self,
        node_ids: List[int],
        adj: Dict[int, Set[int]],
        pag: PAG,
    ) -> None:
        """Apply FCI orientation rules until convergence.

        Rules from Zhang (2008) "On the completeness of orientation rules
        for causal discovery in the presence of latent confounders":

        R1:  A *-> B o-* C, A not adj C  =>  B *-> C  (orient B o-* C to B *-> C)
        R2:  A -> B *-> C, or A *-> B -> C, with A *-o C  =>  A *-> C
        R3:  A *-> B <-* C, A *-o D o-* C, D *-o B, A not adj C  =>  D *-> B
        R4:  Discriminating path orientation
        R8:  A -> B o-> C, or A o-> B -> C, with A o-o C  =>  A -> C  (tail at A)
        R9:  A o-> B, uncovered potentially directed path from A to B  =>  A -> B
        R10: A o-> B, A <-> C -> B, A o-> D -> B, C not adj D  =>  A -> B

        For tractability and robustness, we iterate until no changes occur
        or a maximum iteration count is reached.

        Args:
            node_ids: All candidate node IDs.
            adj: Adjacency dictionary.
            pag: PAG to modify in place.
        """
        max_iterations = 50
        for _ in range(max_iterations):
            changed = False
            changed |= self._fci_rule_1(node_ids, adj, pag)
            changed |= self._fci_rule_2(node_ids, adj, pag)
            changed |= self._fci_rule_3(node_ids, adj, pag)
            changed |= self._fci_rule_4(node_ids, adj, pag)
            changed |= self._fci_rule_8(node_ids, adj, pag)
            changed |= self._fci_rule_9(node_ids, adj, pag)
            changed |= self._fci_rule_10(node_ids, adj, pag)
            if not changed:
                break

    def _fci_rule_1(self, node_ids: List[int],
                    adj: Dict[int, Set[int]], pag: PAG) -> bool:
        """R1: If A *-> B o-* C and A is not adjacent to C, then B *-> C.

        Orients the circle mark at B on edge B-C to a tail, making it B *-> C.
        This prevents creating a new unshielded collider.

        Returns True if any change was made.
        """
        changed = False
        for b in node_ids:
            # Find edges where B has an arrowhead: A *-> B
            edges_into_b = pag.get_edges_with_arrowhead_at(b)
            for edge_ab in edges_into_b:
                a = edge_ab.other_node(b)

                # Look for B o-* C (circle at B endpoint on edge B-C)
                for c in pag.get_adjacent(b):
                    if c == a:
                        continue
                    edge_bc = pag.get_edge(b, c)
                    if not edge_bc:
                        continue

                    # Check B has circle mark on edge B-C
                    if not edge_bc.has_circle_at(b):
                        continue

                    # A and C must not be adjacent
                    if pag.has_edge(a, c):
                        continue

                    # Orient: change circle at B to tail, set arrowhead at C
                    edge_bc.set_mark_at(b, TAIL)
                    edge_bc.set_mark_at(c, ARROW)
                    changed = True

        return changed

    def _fci_rule_2(self, node_ids: List[int],
                    adj: Dict[int, Set[int]], pag: PAG) -> bool:
        """R2: If A -> B *-> C (or A *-> B -> C), and A *-o C, orient A *-> C.

        If there is a directed path A -> B *-> C, and A has a circle endpoint
        on edge A-C, change it to an arrowhead at C.

        Returns True if any change was made.
        """
        changed = False
        for b in node_ids:
            for a in pag.get_adjacent(b):
                edge_ab = pag.get_edge(a, b)
                if not edge_ab:
                    continue

                for c in pag.get_adjacent(b):
                    if c == a:
                        continue
                    edge_bc = pag.get_edge(b, c)
                    edge_ac = pag.get_edge(a, c)
                    if not edge_bc or not edge_ac:
                        continue

                    # Check if A *-o C (circle at C on edge A-C)
                    if not edge_ac.has_circle_at(c):
                        continue

                    # Case 1: A -> B *-> C
                    # A -> B means tail at A, arrow at B on edge A-B
                    a_to_b = (edge_ab.has_tail_at(a) and edge_ab.has_arrowhead_at(b))
                    b_to_c = edge_bc.has_arrowhead_at(c)

                    # Case 2: A *-> B -> C
                    a_arrow_b = edge_ab.has_arrowhead_at(b)
                    b_directed_c = (edge_bc.has_tail_at(b) and edge_bc.has_arrowhead_at(c))

                    if (a_to_b and b_to_c) or (a_arrow_b and b_directed_c):
                        edge_ac.set_mark_at(c, ARROW)
                        changed = True

        return changed

    def _fci_rule_3(self, node_ids: List[int],
                    adj: Dict[int, Set[int]], pag: PAG) -> bool:
        """R3: If A *-> B <-* C, A *-o D o-* C, D *-o B, A not adj C => D *-> B.

        Two non-adjacent parents of B with a common neighbor D that has circle
        marks toward B: orient D *-> B.

        Returns True if any change was made.
        """
        changed = False
        for b in node_ids:
            parents = []
            for n in pag.get_adjacent(b):
                edge = pag.get_edge(n, b)
                if edge and edge.has_arrowhead_at(b):
                    parents.append(n)

            if len(parents) < 2:
                continue

            for i in range(len(parents)):
                for j in range(i + 1, len(parents)):
                    a, c = parents[i], parents[j]

                    # A and C must not be adjacent
                    if pag.has_edge(a, c):
                        continue

                    # Find D adjacent to A, C, and B with circle marks
                    for d in pag.get_adjacent(a):
                        if d == b or d == c:
                            continue
                        if not pag.has_edge(d, c):
                            continue
                        if not pag.has_edge(d, b):
                            continue

                        edge_ad = pag.get_edge(a, d)
                        edge_cd = pag.get_edge(c, d)
                        edge_db = pag.get_edge(d, b)

                        if not edge_ad or not edge_cd or not edge_db:
                            continue

                        # D has circle at D on edges to A and C
                        # and circle at B on edge D-B
                        if (edge_db.has_circle_at(b)
                                and edge_ad.has_circle_at(d)
                                and edge_cd.has_circle_at(d)):
                            edge_db.set_mark_at(b, ARROW)
                            changed = True

        return changed

    def _fci_rule_4(self, node_ids: List[int],
                    adj: Dict[int, Set[int]], pag: PAG) -> bool:
        """R4: Discriminating path rule.

        A discriminating path for B is <A, ..., M, B, C> where:
        - A is not adjacent to C
        - Every node between A and B (exclusive) is a collider with arrowheads
          and is a parent of C
        - B is adjacent to C

        If B is in sep(A, C): orient B-C as B -> C (tail at B, arrow at C)
        If B not in sep(A, C): orient as B <-> C (arrowheads at both)

        For tractability, we check discriminating paths of length 3 only
        (A, M, B, C — minimal discriminating path).

        Returns True if any change was made.
        """
        changed = False
        for c in node_ids:
            neighbors_c = pag.get_adjacent(c)
            for b in neighbors_c:
                edge_bc = pag.get_edge(b, c)
                if not edge_bc or not edge_bc.has_circle_at(b):
                    continue

                # Look for M such that M *-> B (collider at B from M side)
                for m in pag.get_adjacent(b):
                    if m == c:
                        continue
                    edge_mb = pag.get_edge(m, b)
                    if not edge_mb or not edge_mb.has_arrowhead_at(b):
                        continue

                    # M must be a parent of C: M -> C or M *-> C
                    if not pag.has_edge(m, c):
                        continue
                    edge_mc = pag.get_edge(m, c)
                    if not edge_mc or not edge_mc.has_arrowhead_at(c):
                        continue

                    # Look for A not adjacent to C
                    for a in pag.get_adjacent(m):
                        if a == b or a == c:
                            continue
                        if pag.has_edge(a, c):
                            continue

                        edge_am = pag.get_edge(a, m)
                        if not edge_am or not edge_am.has_arrowhead_at(m):
                            continue

                        # We have a discriminating path A, M, B, C
                        sep_key = frozenset({a, c})
                        sep_set = self._sep_sets.get(sep_key, set())

                        if b in sep_set:
                            # B in sep(A,C) => orient B -> C
                            edge_bc.set_mark_at(b, TAIL)
                            edge_bc.set_mark_at(c, ARROW)
                        else:
                            # B not in sep(A,C) => orient B <-> C
                            edge_bc.set_mark_at(b, ARROW)
                            edge_bc.set_mark_at(c, ARROW)
                        changed = True

        return changed

    def _fci_rule_8(self, node_ids: List[int],
                    adj: Dict[int, Set[int]], pag: PAG) -> bool:
        """R8: If A -> B o-> C (with A o-o C), orient A -> C (tail at A).

        Returns True if any change was made.
        """
        changed = False
        for b in node_ids:
            for a in pag.get_adjacent(b):
                edge_ab = pag.get_edge(a, b)
                if not edge_ab:
                    continue

                # A -> B: tail at A, arrow at B
                if not (edge_ab.has_tail_at(a) and edge_ab.has_arrowhead_at(b)):
                    continue

                for c in pag.get_adjacent(b):
                    if c == a:
                        continue
                    edge_bc = pag.get_edge(b, c)
                    edge_ac = pag.get_edge(a, c)
                    if not edge_bc or not edge_ac:
                        continue

                    # B o-> C: circle at B, arrow at C
                    if not (edge_bc.has_circle_at(b) and edge_bc.has_arrowhead_at(c)):
                        continue

                    # A o-o C or A o-> C (circle at A on edge A-C)
                    if edge_ac.has_circle_at(a):
                        edge_ac.set_mark_at(a, TAIL)
                        changed = True

        return changed

    def _fci_rule_9(self, node_ids: List[int],
                    adj: Dict[int, Set[int]], pag: PAG) -> bool:
        """R9: If A o-> B and there is an uncovered potentially directed path
        from A to B through C, orient A -> B (tail at A).

        An uncovered potentially directed path is A - C - ... - B where each
        consecutive pair is adjacent, none are adjacent to non-consecutive
        nodes (uncovered), and no arrowhead points backward along the path.

        For tractability, we check length-2 paths: A - C -> B.

        Returns True if any change was made.
        """
        changed = False
        for edge_key in list(pag.edges.keys()):
            edge_ab = pag.edges.get(edge_key)
            if not edge_ab:
                continue

            a, b = edge_ab.node_a, edge_ab.node_b

            # Check A o-> B (circle at A, arrow at B)
            if edge_ab.has_circle_at(a) and edge_ab.has_arrowhead_at(b):
                # Find C: A adj C, C -> B
                for c in pag.get_adjacent(a):
                    if c == b:
                        continue
                    edge_cb = pag.get_edge(c, b)
                    if not edge_cb:
                        continue
                    # C -> B: tail at C, arrow at B
                    if edge_cb.has_tail_at(c) and edge_cb.has_arrowhead_at(b):
                        edge_ac = pag.get_edge(a, c)
                        if edge_ac and not edge_ac.has_arrowhead_at(a):
                            edge_ab.set_mark_at(a, TAIL)
                            changed = True
                            break

            # Check B o-> A (circle at B, arrow at A)
            elif edge_ab.has_circle_at(b) and edge_ab.has_arrowhead_at(a):
                for c in pag.get_adjacent(b):
                    if c == a:
                        continue
                    edge_ca = pag.get_edge(c, a)
                    if not edge_ca:
                        continue
                    if edge_ca.has_tail_at(c) and edge_ca.has_arrowhead_at(a):
                        edge_bc = pag.get_edge(b, c)
                        if edge_bc and not edge_bc.has_arrowhead_at(b):
                            edge_ab.set_mark_at(b, TAIL)
                            changed = True
                            break

        return changed

    def _fci_rule_10(self, node_ids: List[int],
                     adj: Dict[int, Set[int]], pag: PAG) -> bool:
        """R10: If A o-> B, and there exist C, D such that:
        A <-> C -> B and A o-> D -> B and C not adj D,
        orient A -> B (tail at A).

        Returns True if any change was made.
        """
        changed = False
        for edge_key in list(pag.edges.keys()):
            edge_ab = pag.edges.get(edge_key)
            if not edge_ab:
                continue

            # Try both directions
            for a_node, b_node in [(edge_ab.node_a, edge_ab.node_b),
                                    (edge_ab.node_b, edge_ab.node_a)]:
                # Check a_node o-> b_node
                if not (edge_ab.has_circle_at(a_node)
                        and edge_ab.has_arrowhead_at(b_node)):
                    continue

                # Find C: A <-> C -> B
                c_nodes: List[int] = []
                for c in pag.get_adjacent(a_node):
                    if c == b_node:
                        continue
                    edge_ac = pag.get_edge(a_node, c)
                    edge_cb = pag.get_edge(c, b_node)
                    if not edge_ac or not edge_cb:
                        continue
                    if (edge_ac.has_arrowhead_at(a_node)
                            and edge_ac.has_arrowhead_at(c)
                            and edge_cb.has_tail_at(c)
                            and edge_cb.has_arrowhead_at(b_node)):
                        c_nodes.append(c)

                # Find D: A o-> D -> B (or A -> D -> B)
                d_nodes: List[int] = []
                for d in pag.get_adjacent(a_node):
                    if d == b_node:
                        continue
                    edge_ad = pag.get_edge(a_node, d)
                    edge_db = pag.get_edge(d, b_node)
                    if not edge_ad or not edge_db:
                        continue
                    if (edge_ad.has_arrowhead_at(d)
                            and edge_db.has_tail_at(d)
                            and edge_db.has_arrowhead_at(b_node)):
                        d_nodes.append(d)

                # Check if any C, D pair is non-adjacent
                oriented_flag = False
                for c in c_nodes:
                    for d in d_nodes:
                        if c == d:
                            continue
                        if not pag.has_edge(c, d):
                            edge_ab.set_mark_at(a_node, TAIL)
                            oriented_flag = True
                            changed = True
                            break
                    if oriented_flag:
                        break

        return changed
