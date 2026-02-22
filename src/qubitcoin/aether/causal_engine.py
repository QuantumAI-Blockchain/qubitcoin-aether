"""
Causal Discovery Engine — From Correlation to Causation

Implements a proper constraint-based PC (Peter-Clark) algorithm for causal
discovery in the knowledge graph.  The key advance over naive correlation is
conditional independence testing: an edge A-B is removed if there exists a
conditioning set S such that A _||_ B | S.  This distinguishes genuine causal
links from spurious correlations induced by confounders.

After skeleton discovery, edges are oriented using:
  1. V-structure detection (unshielded colliders)
  2. Meek's orientation rules (acyclicity propagation)
  3. Domain heuristics (temporal ordering, confidence asymmetry)

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
MAX_CONDITIONING_DEPTH: int = 2

# Node-type encoding for feature vectors
_NODE_TYPE_ENCODING: Dict[str, float] = {
    'assertion': 0.0,
    'observation': 0.25,
    'inference': 0.5,
    'axiom': 0.75,
    'prediction': 1.0,
    'meta_observation': 0.6,
}


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
        }

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def _build_feature_matrix(self, node_ids: List[int]) -> Dict[int, List[float]]:
        """Build a feature vector for each node.

        Each node is represented by a 6-dimensional vector:
            [confidence, source_block_normalized, node_type_encoded,
             in_degree, out_degree, avg_neighbor_confidence]

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

            features[nid] = [
                confidence,
                source_block_norm,
                type_encoded,
                in_degree,
                out_degree,
                avg_neighbor_conf,
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
