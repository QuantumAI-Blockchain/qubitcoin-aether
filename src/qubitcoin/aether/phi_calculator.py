"""
Phi Calculator v3 — Information-Theoretic Integration

Computes Phi (Φ) as a measure of consciousness/integration in the knowledge graph.
Based on Giulio Tononi's Integrated Information Theory with information-theoretic
extensions using dense embeddings from VectorIndex.

v3 replaces v1 and v2 with a single formula:
  - Integration: mutual information between graph partitions (via VectorIndex)
  - Differentiation: Shannon entropy over node types + edge types + confidence distribution
  - Redundancy penalty: duplicate content detected via near-duplicate cosine similarity
  - Milestone gates: 10 gates that cap Phi until genuine cognitive milestones are met
  - Maturity: log2(1 + n_nodes / 50000) — slow growth prevents trivial inflation

Formula:
    raw_phi = (integration + cross_flow) * differentiation * (1 + connectivity) * maturity
    redundancy_factor = 1.0 - (duplicate_fraction * 0.5)
    phi = min(raw_phi * redundancy_factor, gate_ceiling)
"""
import math
import random
import time
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Phi threshold for Proof-of-Thought validity
PHI_THRESHOLD = 3.0

# Maximum nodes to sample for spectral bisection (O(n^2) cap)
PHI_MAX_SAMPLE_NODES = 5000
# Deterministic seed for reproducible sampling
PHI_SAMPLE_SEED = 42

# ============================================================================
# MILESTONE GATES (Semantic Quality Hardened)
# Each passed gate unlocks +0.5 Phi ceiling.  Gates require BOTH quantity AND
# quality criteria to prevent gaming via junk node injection.
# ============================================================================
MILESTONE_GATES: List[dict] = [
    {
        'id': 1,
        'name': 'Knowledge Foundation',
        'description': 'Substantial knowledge base with quality nodes',
        'check': lambda stats: (
            stats['n_nodes'] >= 100
            and stats.get('avg_confidence', 0) >= 0.5
        ),
        'requirement': '>=100 nodes AND avg confidence >= 0.5',
    },
    {
        'id': 2,
        'name': 'Diverse Reasoning',
        'description': 'Multiple node types and active reasoning',
        'check': lambda stats: (
            stats['n_nodes'] >= 500
            and len([t for t, c in stats['node_type_counts'].items() if c >= 10]) >= 3
            and stats.get('integration_score', 0) > 0.3
        ),
        'requirement': '>=500 nodes, >=3 node types with 10+ each, integration > 0.3',
    },
    {
        'id': 3,
        'name': 'Predictive Power',
        'description': 'Verified predictions demonstrate real understanding',
        'check': lambda stats: (
            stats['n_nodes'] >= 1000
            and stats.get('verified_predictions', 0) >= 50
            and (
                stats['edge_type_counts'].get('causes', 0)
                >= stats['n_edges'] * 0.05
                if stats['n_edges'] > 0
                else False
            )
        ),
        'requirement': '>=1000 nodes, >=50 verified predictions, causal edges > 5% of total',
    },
    {
        'id': 4,
        'name': 'Self-Correction',
        'description': 'Demonstrates ability to identify and resolve contradictions',
        'check': lambda stats: (
            stats['n_nodes'] >= 2000
            and stats.get('debate_verdicts', 0) >= 10
            and stats.get('contradiction_resolutions', 0) >= 5
            and stats.get('mip_phi', 0) > 0.3
        ),
        'requirement': '>=2000 nodes, >=10 debate verdicts, >=5 contradictions resolved, MIP > 0.3',
    },
    {
        'id': 5,
        'name': 'Cross-Domain Transfer',
        'description': 'Knowledge transfer between domains demonstrates generalization',
        'check': lambda stats: (
            stats['n_nodes'] >= 5000
            and stats.get('domain_count', 0) >= 5
            and stats['edge_type_counts'].get('analogous_to', 0) >= 50
            and stats.get('working_memory_hit_rate', 0) > 0.3
        ),
        'requirement': '>=5000 nodes, >=5 domains, >=50 analogies, WM hit rate > 0.3',
    },
    {
        'id': 6,
        'name': 'Emergent Goals',
        'description': 'System generates and pursues its own goals',
        'check': lambda stats: (
            stats['n_nodes'] >= 10000
            and stats.get('auto_goals_generated', 0) >= 20
            and stats.get('self_reflection_nodes', 0) >= 20
        ),
        'requirement': '>=10K nodes, >=20 auto-goals, >=20 self-reflection nodes',
    },
    {
        'id': 7,
        'name': 'Metacognitive Calibration',
        'description': 'System accurately predicts its own reasoning quality',
        'check': lambda stats: (
            stats['n_nodes'] >= 20000
            and stats.get('calibration_error', 1.0) < 0.15
            and stats.get('grounding_ratio', 0) > 0.1
        ),
        'requirement': '>=20K nodes, calibration error < 0.15, >10% grounded nodes',
    },
    {
        'id': 8,
        'name': 'Consolidated Knowledge',
        'description': 'Episodic replay has produced durable semantic knowledge',
        'check': lambda stats: (
            stats['n_nodes'] >= 30000
            and stats.get('axiom_from_consolidation', 0) >= 10
            and stats.get('cross_domain_inferences', 0) >= 20
        ),
        'requirement': '>=30K nodes, >=10 consolidated axioms, >=20 cross-domain inferences',
    },
    {
        'id': 9,
        'name': 'Predictive Mastery',
        'description': 'High prediction accuracy demonstrates genuine understanding',
        'check': lambda stats: (
            stats['n_nodes'] >= 50000
            and stats.get('prediction_accuracy', 0) > 0.6
            and stats['node_type_counts'].get('inference', 0) >= 5000
        ),
        'requirement': '>=50K nodes, prediction accuracy > 60%, >=5K inferences',
    },
    {
        'id': 10,
        'name': 'Creative Synthesis',
        'description': 'Novel concepts combining multiple domains and modalities',
        'check': lambda stats: (
            stats['n_nodes'] >= 100000
            and stats.get('cross_domain_inferences', 0) >= 100
            and stats.get('novel_concept_count', 0) >= 50
        ),
        'requirement': '>=100K nodes, >=100 cross-domain inferences, >=50 novel concepts',
    },
]


class PhiCalculator:
    """
    Computes Phi (Φ) metric for the Aether Tree knowledge graph.

    v3 formula uses information-theoretic integration (mutual information
    between graph partitions via VectorIndex embeddings), Shannon entropy
    differentiation, and redundancy penalty from near-duplicate detection.

    Milestone gates support adaptive thresholds via a configurable scale
    factor.  When ``gate_scale > 1.0``, node count thresholds increase
    (harder to pass); when ``gate_scale < 1.0`` they decrease (easier).
    The scale factor can be adjusted at runtime based on historical Phi
    progression data.
    """

    def __init__(self, db_manager, knowledge_graph=None):
        self.db = db_manager
        self.kg = knowledge_graph
        self._cache: Dict[int, float] = {}  # block_height -> phi
        self._last_full_result: Optional[dict] = None
        self._last_computed_block: int = -1
        self._last_mip_score: float = 0.0
        self._compute_interval: int = int(
            __import__('os').getenv('PHI_COMPUTE_INTERVAL', '1')
        )
        # Adaptive gate scale factor: multiplier for node-count thresholds
        self._gate_scale: float = float(
            __import__('os').getenv('PHI_GATE_SCALE', '1.0')
        )
        # History of (block_height, phi_value) for adaptation
        self._phi_history: List[Tuple[int, float]] = []
        self._max_history: int = 1000

    def compute_phi(self, block_height: int = 0) -> dict:
        """
        Compute Phi for the current state of the knowledge graph.

        Uses v3 information-theoretic formula with:
        - Mutual information integration (via VectorIndex partitions)
        - Shannon entropy differentiation (node types + edge types + confidence)
        - Redundancy penalty (near-duplicate embedding detection)
        - Milestone gate ceiling

        Returns:
            Dict with phi_value, integration, differentiation, and breakdown
        """
        if not self.kg or not self.kg.nodes:
            return self._empty_result(block_height)

        # Return cached result if within compute interval
        if (self._compute_interval > 1
                and self._last_full_result is not None
                and block_height > 0
                and self._last_computed_block > 0
                and (block_height - self._last_computed_block) < self._compute_interval):
            cached = dict(self._last_full_result)
            cached['block_height'] = block_height
            cached['cached'] = True
            return cached

        nodes = self.kg.nodes
        edges = self.kg.edges
        n_nodes = len(nodes)
        n_edges = len(edges)

        # --- Integration (information-theoretic) ---
        integration = self._compute_integration(nodes, edges, n_nodes)

        # --- Differentiation (Shannon entropy) ---
        differentiation = self._compute_differentiation(nodes, edges)

        # --- Connectivity ---
        max_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
        connectivity = min(1.0, n_edges / max_edges) if max_edges > 0 else 0

        # --- Maturity (logarithmic growth) ---
        maturity = math.log2(1.0 + n_nodes / 50_000.0)

        # --- Raw Phi ---
        raw_phi = integration * differentiation * (1.0 + connectivity) * maturity

        # --- Redundancy penalty ---
        redundancy_factor = self._compute_redundancy_factor()

        # --- Milestone gates ---
        gates = self._check_gates(nodes, edges, extra_stats={
            'integration_score': integration,
            'mip_phi': self._last_mip_score,
        })
        gates_passed = sum(1 for g in gates if g['passed'])
        gate_ceiling = gates_passed * 0.5

        # --- Final Phi ---
        phi = min(raw_phi * redundancy_factor, gate_ceiling)

        result = {
            'phi_value': round(phi, 6),
            'phi_raw': round(raw_phi, 6),
            'phi_threshold': PHI_THRESHOLD,
            'above_threshold': phi >= PHI_THRESHOLD,
            'integration_score': round(integration, 6),
            'differentiation_score': round(differentiation, 6),
            'mip_score': round(self._last_mip_score, 6),
            'connectivity': round(connectivity, 6),
            'maturity': round(maturity, 6),
            'redundancy_factor': round(redundancy_factor, 4),
            'num_nodes': n_nodes,
            'num_edges': n_edges,
            'block_height': block_height,
            'timestamp': time.time(),
            'phi_version': 3,
            'gates_passed': gates_passed,
            'gates_total': len(MILESTONE_GATES),
            'gate_ceiling': gate_ceiling,
            'gates': gates,
        }

        self._last_full_result = result
        self._last_computed_block = block_height

        self._store_measurement(result)
        return result

    # ========================================================================
    # Integration: Mutual Information + Cross-flow
    # ========================================================================

    def _compute_integration(self, nodes: dict, edges: list, n_nodes: int) -> float:
        """
        Compute integration using:
        1. Connected component analysis (structural integration)
        2. Mutual information between graph partitions (via VectorIndex)
        3. Confidence-weighted cross-partition flow
        """
        if n_nodes <= 1:
            return 0.0

        # Build adjacency for connected component analysis
        adj: Dict[int, set] = {nid: set() for nid in nodes}
        for edge in edges:
            if edge.from_node_id in adj and edge.to_node_id in adj:
                adj[edge.from_node_id].add(edge.to_node_id)
                adj[edge.to_node_id].add(edge.from_node_id)

        # Find connected components via BFS
        visited = set()
        components = []

        def _bfs(start):
            comp = set()
            queue = deque([start])
            while queue:
                n = queue.popleft()
                if n in comp:
                    continue
                comp.add(n)
                visited.add(n)
                for neighbor in adj.get(n, set()):
                    if neighbor not in comp:
                        queue.append(neighbor)
            return comp

        for nid in nodes:
            if nid not in visited:
                comp = _bfs(nid)
                components.append(comp)

        # Structural integration from connectivity
        if len(components) == 1:
            avg_degree = sum(len(adj[nid]) for nid in nodes) / n_nodes if n_nodes > 0 else 0
            structural = min(5.0, avg_degree)
        else:
            largest = max(len(c) for c in components)
            structural = (largest / n_nodes) * 2.0

        # Mutual information between partitions (via VectorIndex)
        mi_score = 0.0
        if (hasattr(self.kg, 'vector_index')
                and self.kg.vector_index
                and len(self.kg.vector_index.embeddings) >= 10
                and len(components) == 1):
            # Partition the graph roughly in half for MI computation
            node_list = list(nodes.keys())
            mid = len(node_list) // 2
            partition_a = node_list[:mid]
            partition_b = node_list[mid:]
            if partition_a and partition_b:
                mi_score = self.kg.vector_index.compute_partition_mutual_info(
                    partition_a, partition_b
                )
                # Normalize MI to [0, 3] range
                mi_score = min(3.0, mi_score / max(1.0, math.log(n_nodes)))

        # Cross-partition information flow
        cross_flow = 0.0
        for edge in edges:
            fn = nodes.get(edge.from_node_id)
            tn = nodes.get(edge.to_node_id)
            if fn and tn:
                cross_flow += fn.confidence * tn.confidence * edge.weight
        if edges:
            cross_flow /= len(edges)

        # Minimum Information Partition (spectral bisection)
        # Only meaningful for graphs with >= 10 nodes
        mip_score = 0.0
        if n_nodes >= 10:
            mip_score = self._compute_mip(nodes, edges)

        # Store MIP on instance for result dict access
        self._last_mip_score = mip_score

        return structural + mi_score + cross_flow + mip_score

    # ========================================================================
    # Minimum Information Partition (MIP) via Spectral Bisection
    # ========================================================================

    def _compute_mip(self, nodes: dict, edges: list) -> float:
        """
        Compute Minimum Information Partition using spectral bisection.

        Real IIT requires finding the partition that *minimizes* integrated
        information — the cut where the system loses the least information
        when split.  This is the MIP.

        Algorithm:
        1. Build weighted adjacency matrix (sparse, dict-of-dicts).
        2. Compute graph Laplacian L = D - A.
        3. Find the Fiedler vector (second-smallest eigenvector of L) via
           power iteration on the shifted Laplacian.
        4. Try 3 spectral cuts (n/3, n/2, 2n/3) on nodes sorted by Fiedler
           value and pick the one that minimizes information loss.
        5. Return normalized phi_partition = (I_whole - I_A - I_B) / I_whole.

        Args:
            nodes: Dict[int, KeterNode] — knowledge graph nodes
            edges: List[KeterEdge] — knowledge graph edges

        Returns:
            MIP score (float >= 0).  Higher means more integrated.
        """
        n_nodes = len(nodes)
        if n_nodes < 10:
            return 0.0

        # --- Cap computation: sample nodes for large graphs ---
        node_ids = list(nodes.keys())
        sampled = False
        if n_nodes > PHI_MAX_SAMPLE_NODES:
            sampled = True
            random.seed(PHI_SAMPLE_SEED)  # deterministic sampling for reproducibility
            sampled_ids: Set[int] = set(random.sample(node_ids, PHI_MAX_SAMPLE_NODES))
            node_ids = list(sampled_ids)
            n_nodes = PHI_MAX_SAMPLE_NODES
        else:
            sampled_ids = set(node_ids)

        # Create index mapping: node_id -> matrix index
        id_to_idx: Dict[int, int] = {nid: i for i, nid in enumerate(node_ids)}

        # --- Step 1: Build weighted adjacency matrix (sparse dict-of-dicts) ---
        adj: Dict[int, Dict[int, float]] = {i: {} for i in range(n_nodes)}

        for edge in edges:
            fid = edge.from_node_id
            tid = edge.to_node_id
            if fid not in id_to_idx or tid not in id_to_idx:
                continue
            if fid == tid:
                continue

            fi = id_to_idx[fid]
            ti = id_to_idx[tid]

            fn = nodes.get(fid)
            tn = nodes.get(tid)
            if fn is None or tn is None:
                continue

            w = fn.confidence * tn.confidence * edge.weight
            if w <= 0.0:
                continue

            # Undirected: add both directions, accumulate if multiple edges
            adj[fi][ti] = adj[fi].get(ti, 0.0) + w
            adj[ti][fi] = adj[ti].get(fi, 0.0) + w

        # --- Step 2: Compute total information flow (sum of all edge weights) ---
        total_flow = 0.0
        for i in range(n_nodes):
            for j, w in adj[i].items():
                if j > i:  # count each edge once
                    total_flow += w

        if total_flow <= 0.0:
            return 0.0

        # --- Step 3: Compute degree vector for graph Laplacian ---
        # L = D - A.  We don't build L explicitly; we implement L*v as a function.
        degree: List[float] = [0.0] * n_nodes
        for i in range(n_nodes):
            degree[i] = sum(adj[i].values())

        # --- Step 4: Find Fiedler vector via power iteration ---
        # We want the second-smallest eigenvector of L.
        # Strategy: power iteration on (lambda_max * I - L) gives the largest
        # eigenvector of the complement.  We project out the trivial (constant)
        # eigenvector at each step to converge to the Fiedler vector.

        # Estimate lambda_max (Gershgorin bound: max degree is an upper bound)
        lambda_max = max(degree) if degree else 1.0
        if lambda_max <= 0.0:
            lambda_max = 1.0
        # Add small margin to ensure positive definite shift
        shift = lambda_max + 0.1

        fiedler = self._power_iteration_fiedler(adj, degree, shift, n_nodes)

        if fiedler is None:
            return 0.0

        # --- Step 5: Try top-3 spectral cuts for robustness ---
        # Sort nodes by Fiedler value
        sorted_indices: List[Tuple[float, int]] = sorted(
            (fiedler[i], i) for i in range(n_nodes)
        )
        sorted_node_indices: List[int] = [idx for _, idx in sorted_indices]

        # Try cuts at n/3, n/2, 2n/3
        cut_positions = [n_nodes // 3, n_nodes // 2, (2 * n_nodes) // 3]
        # Ensure valid and unique cut positions
        cut_positions = [
            c for c in cut_positions
            if 0 < c < n_nodes
        ]
        if not cut_positions:
            cut_positions = [n_nodes // 2]

        min_phi_partition = float('inf')

        for cut_pos in cut_positions:
            part_a: Set[int] = set(sorted_node_indices[:cut_pos])
            part_b: Set[int] = set(sorted_node_indices[cut_pos:])

            if not part_a or not part_b:
                continue

            # Compute information within each partition
            info_a = 0.0
            info_b = 0.0
            for i in range(n_nodes):
                for j, w in adj[i].items():
                    if j <= i:
                        continue  # count each edge once
                    if i in part_a and j in part_a:
                        info_a += w
                    elif i in part_b and j in part_b:
                        info_b += w

            # Information lost by partitioning
            phi_partition = total_flow - info_a - info_b

            if phi_partition < min_phi_partition:
                min_phi_partition = phi_partition

        if min_phi_partition == float('inf') or min_phi_partition < 0.0:
            return 0.0

        # Normalize by total flow so result is in [0, 1] range,
        # then scale to make it a meaningful contribution to integration score
        normalized = min_phi_partition / total_flow

        if sampled:
            logger.debug(
                f"MIP computed on 5000-node sample: normalized={normalized:.4f}"
            )

        return normalized

    def _power_iteration_fiedler(
        self,
        adj: Dict[int, Dict[int, float]],
        degree: List[float],
        shift: float,
        n: int,
        max_iter: int = 50,
    ) -> Optional[List[float]]:
        """
        Find the Fiedler vector (second-smallest eigenvector of graph Laplacian)
        using power iteration on the shifted matrix (shift*I - L).

        The largest eigenvector of (shift*I - L) corresponds to the smallest
        eigenvector of L.  By projecting out the trivial constant eigenvector
        at each iteration, we converge to the Fiedler vector instead.

        Args:
            adj: Sparse adjacency matrix (dict-of-dicts)
            degree: Degree vector
            shift: Shift value (>= lambda_max of L)
            n: Number of nodes
            max_iter: Maximum iterations for convergence

        Returns:
            Fiedler vector as List[float], or None if computation fails.
        """
        if n < 2:
            return None

        # Initialize with a non-constant vector
        # Use alternating +/- to break symmetry, with slight randomness
        random.seed(123)  # deterministic for reproducibility
        v: List[float] = [
            (1.0 if i % 2 == 0 else -1.0) + random.uniform(-0.01, 0.01)
            for i in range(n)
        ]

        # Project out the constant vector (all-ones direction)
        mean_v = sum(v) / n
        v = [v[i] - mean_v for i in range(n)]

        # Normalize
        norm = math.sqrt(sum(x * x for x in v))
        if norm < 1e-15:
            return None
        v = [x / norm for x in v]

        for iteration in range(max_iter):
            # Compute w = (shift * I - L) * v
            # (shift * I - L) * v = shift * v - L * v
            # L * v = D * v - A * v
            # So (shift * I - L) * v = (shift - degree[i]) * v[i] + sum(adj[i][j] * v[j])
            w: List[float] = [0.0] * n
            for i in range(n):
                # (shift - degree[i]) * v[i]
                w[i] = (shift - degree[i]) * v[i]
                # + sum(adj[i][j] * v[j])  (this is A*v contribution)
                for j, a_ij in adj[i].items():
                    w[i] += a_ij * v[j]

            # Project out the constant (trivial) eigenvector
            mean_w = sum(w) / n
            w = [w[i] - mean_w for i in range(n)]

            # Normalize
            norm = math.sqrt(sum(x * x for x in w))
            if norm < 1e-15:
                # Vector collapsed — graph may be disconnected or trivial
                logger.debug(
                    f"Fiedler iteration collapsed at step {iteration}"
                )
                return None

            v = [x / norm for x in w]

        return v

    # ========================================================================
    # Differentiation: Shannon Entropy
    # ========================================================================

    def _compute_differentiation(self, nodes: dict, edges: list) -> float:
        """
        Compute differentiation using Shannon entropy over:
        1. Node type distribution
        2. Edge type distribution
        3. Confidence distribution (10 bins)
        """
        if not nodes:
            return 0.0

        n = len(nodes)

        # Entropy over node types
        type_counts: Dict[str, int] = {}
        for node in nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        type_entropy = 0.0
        for count in type_counts.values():
            p = count / n
            if p > 0:
                type_entropy -= p * math.log2(p)

        # Entropy over edge types
        edge_type_counts: Dict[str, int] = {}
        for edge in edges:
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

        edge_entropy = 0.0
        n_edges = len(edges)
        if n_edges > 0:
            for count in edge_type_counts.values():
                p = count / n_edges
                if p > 0:
                    edge_entropy -= p * math.log2(p)

        # Entropy over confidence distribution (10 bins)
        bins = [0] * 10
        for node in nodes.values():
            bin_idx = min(9, int(node.confidence * 10))
            bins[bin_idx] += 1

        conf_entropy = 0.0
        for count in bins:
            if count > 0:
                p = count / n
                conf_entropy -= p * math.log2(p)

        # Combined differentiation: node types + edge types + confidence
        return type_entropy + edge_entropy * 0.5 + conf_entropy * 0.3

    # ========================================================================
    # Redundancy Penalty
    # ========================================================================

    def _compute_redundancy_factor(self) -> float:
        """
        Compute redundancy penalty using near-duplicate detection
        from VectorIndex.

        Returns a factor in [0.5, 1.0] — more duplicates = lower factor.
        """
        if not hasattr(self.kg, 'vector_index') or not self.kg.vector_index:
            return 1.0

        n_embeddings = len(self.kg.vector_index.embeddings)
        if n_embeddings < 10:
            return 1.0

        try:
            duplicates = self.kg.vector_index.find_near_duplicates(threshold=0.95)
            if not duplicates:
                return 1.0

            # Fraction of nodes involved in duplicate pairs
            dup_nodes = set()
            for a, b, _ in duplicates:
                dup_nodes.add(a)
                dup_nodes.add(b)

            dup_fraction = len(dup_nodes) / n_embeddings
            # Factor: 1.0 at 0% duplicates, 0.5 at 100% duplicates
            return max(0.5, 1.0 - dup_fraction * 0.5)
        except Exception:
            return 1.0

    # ========================================================================
    # Milestone Gates
    # ========================================================================

    def _check_gates(
        self,
        nodes: dict,
        edges: list,
        extra_stats: Optional[dict] = None,
    ) -> List[dict]:
        """
        Evaluate all semantic quality gates against current graph state.

        Gates require BOTH quantity AND quality criteria.  Extended stats are
        computed from in-memory nodes/edges (O(n + e)) and optionally
        supplemented by ``extra_stats`` for values that come from external
        subsystems (MIP score, working memory hit rate, calibration error,
        prediction accuracy, integration score).

        Args:
            nodes: Dict[int, KeterNode] — knowledge graph nodes
            edges: List[KeterEdge] — knowledge graph edges
            extra_stats: Optional dict with keys like ``mip_phi``,
                ``working_memory_hit_rate``, ``calibration_error``,
                ``prediction_accuracy``, ``integration_score``.

        Returns:
            List of gate result dicts with id, name, description,
            requirement, and passed (bool).
        """
        ext = extra_stats or {}

        # --- Base counts ---
        node_type_counts: Dict[str, int] = {}
        confidence_sum: float = 0.0
        for node in nodes.values():
            node_type_counts[node.node_type] = (
                node_type_counts.get(node.node_type, 0) + 1
            )
            confidence_sum += node.confidence

        edge_type_counts: Dict[str, int] = {}
        for edge in edges:
            etype = edge.edge_type
            edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1

        n_nodes = len(nodes)
        n_edges = len(edges)

        # Average confidence across all nodes
        avg_confidence: float = (confidence_sum / n_nodes) if n_nodes > 0 else 0.0

        # --- Extended semantic stats (single pass over nodes) ---
        domains: set = set()
        self_reflection_nodes: int = 0
        cross_domain_inferences: int = 0
        verified_predictions: int = 0
        debate_verdicts: int = 0
        contradiction_resolutions: int = 0
        auto_goals_generated: int = 0
        grounded_nodes: int = 0
        axiom_from_consolidation: int = 0
        novel_concept_count: int = 0

        for node in nodes.values():
            if node.domain:
                domains.add(node.domain)

            # Check grounding_source for grounding ratio
            if getattr(node, 'grounding_source', '') != '':
                grounded_nodes += 1

            content = node.content if isinstance(node.content, dict) else {}
            content_type = content.get('type', '')

            # Self-reflection nodes (source field in content)
            if content.get('source') == 'self-reflection':
                self_reflection_nodes += 1

            # Cross-domain inferences
            if (node.node_type == 'inference'
                    and content.get('cross_domain', False)):
                cross_domain_inferences += 1

            # Verified predictions (content type = 'prediction_confirmed')
            if content_type == 'prediction_confirmed':
                verified_predictions += 1

            # Debate verdicts (content type = 'debate_synthesis')
            if content_type == 'debate_synthesis':
                debate_verdicts += 1

            # Contradiction resolutions (content type = 'contradiction_resolution')
            if content_type == 'contradiction_resolution':
                contradiction_resolutions += 1

            # Auto-generated goals (meta_observation node type)
            if node.node_type == 'meta_observation':
                auto_goals_generated += 1

            # Consolidated axioms (axiom with content type = 'consolidated_pattern')
            if node.node_type == 'axiom' and content_type == 'consolidated_pattern':
                axiom_from_consolidation += 1

            # Novel concepts (generalization or concept_cluster content types)
            if content_type in ('generalization', 'concept_cluster'):
                novel_concept_count += 1

        # Grounding ratio: fraction of nodes with non-empty grounding_source
        grounding_ratio: float = (
            grounded_nodes / n_nodes if n_nodes > 0 else 0.0
        )

        stats: Dict = {
            'n_nodes': n_nodes,
            'n_edges': n_edges,
            'node_type_counts': node_type_counts,
            'edge_type_counts': edge_type_counts,
            'avg_confidence': avg_confidence,
            'domain_count': len(domains),
            'self_reflection_nodes': self_reflection_nodes,
            'cross_domain_inferences': cross_domain_inferences,
            'verified_predictions': verified_predictions,
            'debate_verdicts': debate_verdicts,
            'contradiction_resolutions': contradiction_resolutions,
            'auto_goals_generated': auto_goals_generated,
            'grounding_ratio': grounding_ratio,
            'axiom_from_consolidation': axiom_from_consolidation,
            'novel_concept_count': novel_concept_count,
            # External stats with sensible defaults
            'integration_score': ext.get('integration_score', 0.0),
            'mip_phi': ext.get('mip_phi', 0.0),
            'working_memory_hit_rate': ext.get('working_memory_hit_rate', 0.0),
            'calibration_error': ext.get('calibration_error', 1.0),
            'prediction_accuracy': ext.get('prediction_accuracy', 0.0),
        }

        # Apply adaptive gate scaling: multiply n_nodes threshold by _gate_scale.
        # This is achieved by dividing the actual n_nodes by _gate_scale before
        # passing to the gate check, so a scale of 1.5 makes gates 50% harder
        # and 0.8 makes them 20% easier.
        gate_scale = getattr(self, '_gate_scale', 1.0)
        if gate_scale != 1.0 and gate_scale > 0:
            scaled_stats = dict(stats)
            scaled_stats['n_nodes'] = int(stats['n_nodes'] / gate_scale)
        else:
            scaled_stats = stats

        results: List[dict] = []
        for gate in MILESTONE_GATES:
            try:
                passed = bool(gate['check'](scaled_stats))
            except Exception:
                passed = False
            results.append({
                'id': gate['id'],
                'name': gate['name'],
                'description': gate['description'],
                'requirement': gate['requirement'],
                'passed': passed,
            })
        return results

    def adapt_gate_scale(self, block_height: int, phi_value: float) -> None:
        """Record Phi progression and adapt gate scale based on growth rate.

        If Phi has been growing too quickly (potential gaming), tighten gates.
        If Phi is stagnant despite real knowledge growth, relax slightly.

        Args:
            block_height: Current block height.
            phi_value: Current computed Phi.
        """
        self._phi_history.append((block_height, phi_value))
        if len(self._phi_history) > self._max_history:
            self._phi_history = self._phi_history[-self._max_history:]

        # Need at least 100 measurements to adapt
        if len(self._phi_history) < 100:
            return

        # Compare recent (last 20) vs older (20 before that) growth rate
        recent = self._phi_history[-20:]
        older = self._phi_history[-40:-20]

        recent_delta = recent[-1][1] - recent[0][1]
        older_delta = older[-1][1] - older[0][1]

        if older_delta <= 0:
            return  # No previous growth to compare

        growth_ratio = recent_delta / older_delta

        # If Phi is growing >3x faster than before, tighten gates slightly
        if growth_ratio > 3.0:
            self._gate_scale = min(2.0, self._gate_scale * 1.05)
            logger.info(f"Phi growth anomaly (ratio={growth_ratio:.1f}), "
                        f"tightening gates: scale={self._gate_scale:.3f}")
        # If Phi is growing <0.2x the previous rate, relax slightly
        elif growth_ratio < 0.2 and self._gate_scale > 0.5:
            self._gate_scale = max(0.5, self._gate_scale * 0.98)
            logger.info(f"Phi growth stagnation (ratio={growth_ratio:.1f}), "
                        f"relaxing gates: scale={self._gate_scale:.3f}")

    # ========================================================================
    # Storage & History
    # ========================================================================

    def _store_measurement(self, result: dict):
        """Store phi measurement in database"""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO phi_measurements
                        (phi_value, phi_threshold, integration_score, differentiation_score,
                         num_nodes, num_edges, block_height)
                        VALUES (:phi, :threshold, :int_score, :diff_score, :nodes, :edges, :bh)
                    """),
                    {
                        'phi': result['phi_value'],
                        'threshold': result['phi_threshold'],
                        'int_score': result['integration_score'],
                        'diff_score': result['differentiation_score'],
                        'nodes': result['num_nodes'],
                        'edges': result['num_edges'],
                        'bh': result['block_height'],
                    }
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Failed to store phi measurement: {e}")

    def _empty_result(self, block_height: int) -> dict:
        return {
            'phi_value': 0.0,
            'phi_raw': 0.0,
            'phi_threshold': PHI_THRESHOLD,
            'above_threshold': False,
            'integration_score': 0.0,
            'differentiation_score': 0.0,
            'mip_score': 0.0,
            'connectivity': 0.0,
            'maturity': 0.0,
            'redundancy_factor': 1.0,
            'num_nodes': 0,
            'num_edges': 0,
            'block_height': block_height,
            'timestamp': time.time(),
            'phi_version': 3,
            'gates_passed': 0,
            'gates_total': len(MILESTONE_GATES),
            'gate_ceiling': 0.0,
            'gates': [],
        }

    def downsample_phi_measurements(self, retain_days: int = None) -> dict:
        """
        Downsample old phi measurements to reduce DB bloat.

        - Rows within retain_days: kept as-is (per-block granularity)
        - Rows older than retain_days but < 30 days: collapsed to hourly averages
        - Rows older than 30 days: collapsed to daily averages
        """
        from ..config import Config
        if retain_days is None:
            retain_days = Config.PHI_DOWNSAMPLE_RETAIN_DAYS

        stats = {'hourly_created': 0, 'daily_created': 0, 'rows_deleted': 0}

        try:
            from sqlalchemy import text
            import datetime

            now = datetime.datetime.now(datetime.timezone.utc)
            retain_cutoff = now - datetime.timedelta(days=retain_days)
            daily_cutoff = now - datetime.timedelta(days=30)

            with self.db.get_session() as session:
                # Phase 1: Collapse retain_days..30 days into hourly averages
                hourly_rows = session.execute(
                    text("""
                        SELECT
                            date_trunc('hour', created_at) AS hour_bucket,
                            AVG(phi_value), AVG(phi_threshold),
                            AVG(integration_score), AVG(differentiation_score),
                            AVG(num_nodes), AVG(num_edges),
                            MIN(block_height), MAX(block_height), COUNT(*)
                        FROM phi_measurements
                        WHERE created_at < :retain_cutoff AND created_at >= :daily_cutoff
                        GROUP BY date_trunc('hour', created_at)
                        HAVING COUNT(*) > 1
                        ORDER BY hour_bucket
                    """),
                    {'retain_cutoff': retain_cutoff, 'daily_cutoff': daily_cutoff}
                )
                hourly_data = list(hourly_rows)

                for row in hourly_data:
                    session.execute(
                        text("""
                            INSERT INTO phi_measurements
                            (phi_value, phi_threshold, integration_score,
                             differentiation_score, num_nodes, num_edges, block_height)
                            VALUES (:phi, :threshold, :int_score, :diff_score,
                                    :nodes, :edges, :bh)
                        """),
                        {
                            'phi': float(row[1]), 'threshold': float(row[2]),
                            'int_score': float(row[3]), 'diff_score': float(row[4]),
                            'nodes': int(row[5]), 'edges': int(row[6]),
                            'bh': int(row[8]),
                        }
                    )
                    stats['hourly_created'] += 1

                if hourly_data:
                    result = session.execute(
                        text("""
                            DELETE FROM phi_measurements
                            WHERE created_at < :retain_cutoff
                              AND created_at >= :daily_cutoff
                              AND id NOT IN (
                                  SELECT MAX(id) FROM phi_measurements
                                  WHERE created_at < :retain_cutoff
                                    AND created_at >= :daily_cutoff
                                  GROUP BY date_trunc('hour', created_at)
                              )
                        """),
                        {'retain_cutoff': retain_cutoff, 'daily_cutoff': daily_cutoff}
                    )
                    stats['rows_deleted'] += result.rowcount

                # Phase 2: Collapse > 30 days into daily averages
                daily_rows = session.execute(
                    text("""
                        SELECT
                            date_trunc('day', created_at) AS day_bucket,
                            AVG(phi_value), AVG(phi_threshold),
                            AVG(integration_score), AVG(differentiation_score),
                            AVG(num_nodes), AVG(num_edges),
                            MIN(block_height), MAX(block_height), COUNT(*)
                        FROM phi_measurements
                        WHERE created_at < :daily_cutoff
                        GROUP BY date_trunc('day', created_at)
                        HAVING COUNT(*) > 1
                        ORDER BY day_bucket
                    """),
                    {'daily_cutoff': daily_cutoff}
                )
                daily_data = list(daily_rows)

                for row in daily_data:
                    session.execute(
                        text("""
                            INSERT INTO phi_measurements
                            (phi_value, phi_threshold, integration_score,
                             differentiation_score, num_nodes, num_edges, block_height)
                            VALUES (:phi, :threshold, :int_score, :diff_score,
                                    :nodes, :edges, :bh)
                        """),
                        {
                            'phi': float(row[1]), 'threshold': float(row[2]),
                            'int_score': float(row[3]), 'diff_score': float(row[4]),
                            'nodes': int(row[5]), 'edges': int(row[6]),
                            'bh': int(row[8]),
                        }
                    )
                    stats['daily_created'] += 1

                if daily_data:
                    result = session.execute(
                        text("""
                            DELETE FROM phi_measurements
                            WHERE created_at < :daily_cutoff
                              AND id NOT IN (
                                  SELECT MAX(id) FROM phi_measurements
                                  WHERE created_at < :daily_cutoff
                                  GROUP BY date_trunc('day', created_at)
                              )
                        """),
                        {'daily_cutoff': daily_cutoff}
                    )
                    stats['rows_deleted'] += result.rowcount

                session.commit()

            if stats['rows_deleted'] > 0:
                logger.info(
                    f"Phi downsample: deleted {stats['rows_deleted']} rows, "
                    f"created {stats['hourly_created']} hourly + "
                    f"{stats['daily_created']} daily summaries"
                )
        except Exception as e:
            logger.debug(f"Phi downsample failed (table may not have created_at): {e}")

        return stats

    def get_history(self, limit: int = 50) -> List[dict]:
        """Get recent phi measurement history"""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                rows = session.execute(
                    text("""
                        SELECT phi_value, phi_threshold, integration_score,
                               differentiation_score, num_nodes, num_edges, block_height
                        FROM phi_measurements
                        ORDER BY block_height DESC LIMIT :limit
                    """),
                    {'limit': limit}
                )
                return [
                    {
                        'phi_value': float(r[0]),
                        'phi_threshold': float(r[1]),
                        'integration_score': float(r[2]),
                        'differentiation_score': float(r[3]),
                        'num_nodes': r[4],
                        'num_edges': r[5],
                        'block_height': r[6],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.debug(f"Failed to get phi history: {e}")
            return []


# --- Rust acceleration shim ---
try:
    from aether_core import PhiCalculator as _RustPhiCalculator  # noqa: F811
    PhiCalculator = _RustPhiCalculator  # type: ignore[misc]
    logger.info("PhiCalculator: using Rust-accelerated aether_core backend")
except ImportError:
    logger.debug("aether_core not installed — using pure-Python PhiCalculator")
