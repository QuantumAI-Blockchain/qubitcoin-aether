"""
Phi Calculator v3 — Phi Integration Metric

Computes Phi (Φ) as a graph-theoretic integration metric for the Aether Tree
knowledge graph. Inspired by Integrated Information Theory (IIT) principles
but implementing a computationally tractable graph-theoretic approximation
rather than the full IIT formalism.

v3 uses a weighted additive formula:
  - Integration: mutual information between spectral-bisection partitions
  - Differentiation: Shannon entropy over node types + edge types + confidence
  - MIP: Minimum Information Partition via Fiedler-vector spectral bisection
  - Redundancy penalty: duplicate content detected via near-duplicate cosine similarity
  - Milestone gates: 10 gates that cap Phi until genuine cognitive milestones are met

Formula:
    raw_phi = w_int * integration + w_diff * differentiation + w_mip * mip_score
    redundancy_factor = 1.0 - (duplicate_fraction * 0.5)
    phi = min(raw_phi * redundancy_factor, gate_ceiling)

Note: This is NOT a measure of phenomenal consciousness. It is an integration
metric that quantifies how well-connected and information-rich the knowledge
graph is, using principles inspired by (but not equivalent to) Tononi's IIT.
"""
import math
import os
import random
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config import Config
from ..utils.logger import get_logger

# Golden ratio for HMS-Phi formula
_PHI_RATIO: float = 1.618033988749895
# Exponents: 1/φ, 1/φ², 1/φ³
_HMS_EXP_MICRO: float = 1.0 / _PHI_RATIO          # ≈ 0.618
_HMS_EXP_MESO:  float = 1.0 / (_PHI_RATIO ** 2)   # ≈ 0.382
_HMS_EXP_MACRO: float = 1.0 / (_PHI_RATIO ** 3)   # ≈ 0.236
# Scale so perfect HMS integration (=1.0) exceeds max gate ceiling (5.0)
_HMS_SCALE: float = 8.0

logger = get_logger(__name__)

# Phi integration threshold for Proof-of-Thought validity (loaded from Config)
# This is an integration quality threshold, not a consciousness threshold
PHI_THRESHOLD = Config.PHI_THRESHOLD

# Maximum nodes to sample for spectral bisection (O(n^2) cap)
PHI_MAX_SAMPLE_NODES = Config.PHI_MAX_SAMPLE_NODES
# Deterministic seed for reproducible sampling
PHI_SAMPLE_SEED = Config.PHI_SAMPLE_SEED

# ============================================================================
# MILESTONE GATES (Peer-Reviewed Thresholds v4)
# Each passed gate unlocks +0.5 Phi ceiling (max 5.0).  Gates require genuine
# cognitive milestones emphasizing QUALITY over quantity.  Volume alone cannot
# pass higher gates — they require validated predictions, genuine cross-domain
# transfer, enacted self-improvement, and novel concept synthesis.
# ============================================================================
MILESTONE_GATES: List[dict] = [
    {
        'id': 1,
        'name': 'Knowledge Foundation',
        'description': 'Broad knowledge base with diverse domains',
        'nodes': 500,
        'check': lambda stats: (
            stats['n_nodes'] >= 500
            and stats.get('domain_count', 0) >= 5
            and stats.get('avg_confidence', 0) >= 0.5
        ),
        'requirement': '>=500 nodes, >=5 domains, avg confidence >= 0.5',
    },
    {
        'id': 2,
        'name': 'Structural Diversity',
        'description': 'Multiple reasoning types with real graph integration',
        'nodes': 2000,
        'check': lambda stats: (
            stats['n_nodes'] >= 2000
            and len([t for t, c in stats['node_type_counts'].items() if c >= 50]) >= 4
            and stats.get('integration_score', 0) > 0.3
        ),
        'requirement': '>=2K nodes, >=4 types with 50+ each, integration > 0.3',
    },
    {
        'id': 3,
        'name': 'Validated Predictions',
        'description': 'Predictions verified against actual outcomes — not self-reported',
        'nodes': 5000,
        'check': lambda stats: (
            stats['n_nodes'] >= 5000
            and stats.get('verified_predictions', 0) >= 50
            and stats.get('prediction_accuracy', 0) > 0.6
        ),
        'requirement': '>=5K nodes, >=50 verified predictions, accuracy > 60%',
    },
    {
        'id': 4,
        'name': 'Self-Correction',
        'description': 'Genuine adversarial debate with contradiction resolution',
        'nodes': 10000,
        'check': lambda stats: (
            stats['n_nodes'] >= 10000
            and stats.get('debate_verdicts', 0) >= 20
            and stats.get('contradiction_resolutions', 0) >= 10
            and stats.get('mip_phi', 0) > 0.3
        ),
        'requirement': '>=10K nodes, >=20 debates, >=10 contradictions resolved, MIP > 0.3',
    },
    {
        'id': 5,
        'name': 'Cross-Domain Transfer',
        'description': 'Genuine knowledge transfer: inferences using evidence from 2+ domains',
        'nodes': 15000,
        'check': lambda stats: (
            stats['n_nodes'] >= 15000
            and stats.get('cross_domain_inferences', 0) >= 30
            and stats.get('cross_domain_inference_confidence', 0) > 0.5
            and _count_cross_domain_edges(stats) >= 50
        ),
        'requirement': '>=15K nodes, >=30 cross-domain inferences with conf > 0.5, >=50 cross-edges',
    },
    {
        'id': 6,
        'name': 'Enacted Self-Improvement',
        'description': 'Self-improvement actions enacted AND producing measurable gains',
        'nodes': 20000,
        'check': lambda stats: (
            stats['n_nodes'] >= 20000
            and stats.get('improvement_cycles_enacted', 0) >= 10
            and stats.get('improvement_performance_delta', 0) > 0.0
        ),
        'requirement': '>=20K nodes, >=10 enacted improvement cycles, positive performance delta',
    },
    {
        'id': 7,
        'name': 'Calibrated Confidence',
        'description': 'System knows what it knows — calibration error below threshold',
        'nodes': 25000,
        'check': lambda stats: (
            stats['n_nodes'] >= 25000
            and stats.get('calibration_error', 1.0) < 0.15
            and stats.get('calibration_evaluations', 0) >= 200
            and stats.get('grounding_ratio', 0) > 0.05
        ),
        'requirement': '>=25K nodes, ECE < 0.15, >=200 evaluations, >5% grounded',
    },
    {
        'id': 8,
        'name': 'Autonomous Curiosity',
        'description': 'System generates its own research goals that produce novel knowledge',
        'nodes': 35000,
        'check': lambda stats: (
            stats['n_nodes'] >= 35000
            and stats.get('auto_goals_generated', 0) >= 50
            and stats.get('auto_goals_with_inferences', 0) >= 30
            and stats.get('curiosity_driven_discoveries', 0) >= 10
        ),
        'requirement': '>=35K nodes, >=50 auto-goals, >=30 producing inferences, >=10 curiosity discoveries',
    },
    {
        'id': 9,
        'name': 'Predictive Mastery',
        'description': 'Sustained high accuracy across domains with large inference volume',
        'nodes': 50000,
        'check': lambda stats: (
            stats['n_nodes'] >= 50000
            and stats.get('prediction_accuracy', 0) > 0.70
            and stats['node_type_counts'].get('inference', 0) >= 5000
            and stats.get('axiom_from_consolidation', 0) >= 20
        ),
        'requirement': '>=50K nodes, accuracy > 70%, >=5K inferences, >=20 consolidated axioms',
    },
    {
        'id': 10,
        'name': 'Novel Synthesis',
        'description': 'Genuine novel concepts not in training data — verified by embedding distance',
        'nodes': 75000,
        'check': lambda stats: (
            stats['n_nodes'] >= 75000
            and stats.get('novel_concept_count', 0) >= 50
            and stats.get('cross_domain_inferences', 0) >= 100
            and stats.get('improvement_performance_delta', 0) > 0.05
        ),
        'requirement': '>=75K nodes, >=50 novel concepts, >=100 cross-domain inferences, sustained self-improvement',
    },
]


def _count_cross_domain_edges(stats: dict) -> int:
    """Count cross-domain edges for gate evaluation.

    Looks at edge_type_counts for 'analogous_to' edges as a proxy
    for cross-domain connections.
    """
    return stats.get('edge_type_counts', {}).get('analogous_to', 0)


class PhiCalculator:
    """
    Computes Phi (Φ) integration metric for the Aether Tree knowledge graph.

    Inspired by IIT principles but implementing a computationally tractable
    graph-theoretic approximation. Uses a weighted additive formula:

        raw_phi = w_int * integration + w_diff * differentiation + w_mip * mip_score

    This avoids the multiplicative collapse problem (where any zero term
    kills the entire score) and honestly represents independent measurements.

    Milestone gates support adaptive thresholds via a configurable scale
    factor.  When ``gate_scale > 1.0``, node count thresholds increase
    (harder to pass); when ``gate_scale < 1.0`` they decrease (easier).
    """

    def __init__(self, db_manager, knowledge_graph=None):
        self.db = db_manager
        self.kg = knowledge_graph
        self._cache: Dict[int, float] = {}  # block_height -> phi
        self._last_full_result: Optional[dict] = None
        self._last_computed_block: int = -1
        self._last_mip_score: float = 0.0
        self._last_gate_stats: dict = {}
        self._compute_interval: int = int(
            os.getenv('PHI_COMPUTE_INTERVAL', '1')
        )
        # Adaptive gate scale factor: multiplier for node-count thresholds
        self._gate_scale: float = float(
            os.getenv('PHI_GATE_SCALE', '1.0')
        )
        # History of (block_height, phi_value) for adaptation
        self._phi_history: List[Tuple[int, float]] = []
        self._max_history: int = 1000
        # Subsystem stats injected by AetherEngine before each compute_phi call
        self._subsystem_stats: Dict[str, float] = {}
        # Cached Config values — avoids re-importing Config on every call
        self._phi_downsample_retain_days: int = Config.PHI_DOWNSAMPLE_RETAIN_DAYS
        # Phi formula weights (from Config) — used in additive fallback
        self._w_int: float = Config.PHI_INTEGRATION_WEIGHT
        self._w_diff: float = Config.PHI_DIFFERENTIATION_WEIGHT
        self._w_mip: float = Config.PHI_MIP_WEIGHT
        # Convergence tracking: stddev over last N measurements
        self._convergence_window: int = Config.PHI_CONVERGENCE_WINDOW
        self._recent_phi_values: deque = deque(maxlen=Config.PHI_CONVERGENCE_WINDOW)

        # ── HMS-Phi: IIT 3.0 micro-level ────────────────────────────────────
        # Lazy-imported to avoid numpy overhead on startup if not needed.
        self._iit_approximator: Optional[object] = None
        self._iit_phi_cache: float = 0.0          # cached phi_micro
        self._iit_last_time: float = 0.0           # wall-time of last IIT run
        # Recompute IIT every 15 seconds (expensive O(16^3) exhaustive search)
        self._IIT_CACHE_SECONDS: float = float(
            os.getenv('HMS_IIT_CACHE_SECONDS', '15')
        )
        # Minimum nodes before HMS-Phi is used (additive fallback below)
        self._HMS_MIN_NODES: int = 500

        # Restore last phi measurement from DB so get_cached() returns
        # non-zero values immediately after restart
        self._restore_from_db()

    def _restore_from_db(self) -> None:
        """Load the latest phi measurement from DB to warm the cache on startup.

        This ensures get_cached() returns the last known phi value instead of
        0.0 after a node restart. Gates are recomputed on the next compute_phi
        call using current KG state.
        """
        if not self.db:
            return
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                row = session.execute(
                    text("""
                        SELECT phi_value, phi_threshold, integration_score,
                               differentiation_score, num_nodes, num_edges,
                               block_height
                        FROM phi_measurements
                        ORDER BY block_height DESC
                        LIMIT 1
                    """)
                ).fetchone()
                if row and isinstance(row[0], (int, float)):
                    phi_val = float(row[0])
                    restored = {
                        'phi_value': phi_val,
                        'phi_raw': phi_val,
                        'phi_threshold': float(row[1]),
                        'above_threshold': phi_val >= float(row[1]),
                        'integration_score': float(row[2]),
                        'differentiation_score': float(row[3]),
                        'mip_score': 0.0,
                        'redundancy_factor': 1.0,
                        'phi_micro': 0.0,
                        'phi_meso': 0.0,
                        'phi_macro': 0.0,
                        'hms_phi_raw': 0.0,
                        'phi_formula': 'restored',
                        'num_nodes': int(row[4]),
                        'num_edges': int(row[5]),
                        'block_height': int(row[6]),
                        'timestamp': time.time(),
                        'phi_version': 4,
                        'gates_passed': 0,  # recomputed on next compute_phi
                        'gates_total': len(MILESTONE_GATES),
                        'gate_ceiling': 0.0,
                        'gates': [],
                        'convergence_stddev': 0.0,
                        'convergence_status': 'restored',
                        'formula_weights': {
                            'integration': self._w_int,
                            'differentiation': self._w_diff,
                            'mip': self._w_mip,
                        },
                    }
                    self._last_full_result = restored
                    self._last_computed_block = int(row[6])
                    self._recent_phi_values.append(phi_val)
                    logger.info(
                        f"Phi restored from DB: {phi_val:.4f} at block {int(row[6])} "
                        f"({int(row[4])} nodes, {int(row[5])} edges)"
                    )
        except Exception as e:
            logger.debug(f"Could not restore phi from DB: {e}")

    def set_subsystem_stats(self, stats: Dict[str, float]) -> None:
        """Inject subsystem stats for gate evaluation.

        Called by AetherEngine before compute_phi to provide live metrics
        from metacognition, memory, neural reasoner, etc.

        Args:
            stats: Dict with keys like working_memory_hit_rate,
                calibration_error, prediction_accuracy.
        """
        self._subsystem_stats = stats

    def compute_phi(self, block_height: int = 0) -> dict:
        """
        Compute Phi integration metric using HMS-Phi v4 (Hierarchical Multi-Scale Phi).

        HMS-Phi uses three independent levels of analysis, multiplicatively combined:
            phi_micro: IIT 3.0 approximation on elite 16-node subgraph samples
            phi_meso:  Spectral MIP (Fiedler bisection) on full knowledge graph
            phi_macro: Graph-theoretic integration (connectivity + mutual info)

            hms_raw   = phi_micro^(1/φ) × phi_meso^(1/φ²) × phi_macro^(1/φ³)
            raw_phi   = hms_raw × 8.0   (scale so hms_raw=1 > max gate ceiling)
            phi       = min(raw_phi × redundancy, gate_ceiling)

        Multiplicative structure means zero in any level → zero phi (ungameable).
        Falls back to weighted additive when n_nodes < 500 or IIT is unavailable.

        Returns:
            Dict with phi_value, hms components, gates breakdown.
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

        # Snapshot to avoid RuntimeError from concurrent node/edge modifications
        nodes = dict(self.kg.nodes)
        edges = list(self.kg.edges)
        n_nodes = len(nodes)
        n_edges = len(edges)

        # --- Level 2 (Macro): Graph-theoretic integration ---
        integration = self._compute_integration(nodes, edges, n_nodes)
        # _compute_integration also populates self._last_mip_score (Level 1 meso)

        # --- Differentiation (Shannon entropy — used in additive fallback) ---
        differentiation = self._compute_differentiation(nodes, edges)

        # --- Redundancy penalty ---
        redundancy_factor = self._compute_redundancy_factor()

        # --- Milestone gates ---
        extra = dict(self._subsystem_stats)
        extra['integration_score'] = integration
        extra['mip_phi'] = self._last_mip_score
        gates = self._check_gates(nodes, edges, extra_stats=extra)
        gates_passed = sum(1 for g in gates if g['passed'])
        gate_ceiling = gates_passed * 0.5

        # ── HMS-Phi v4 ────────────────────────────────────────────────────────
        phi_micro: float = 0.0
        phi_meso:  float = max(0.0, min(1.0, self._last_mip_score))
        # Normalize integration (structural max=5 + MI max=3 + flow max≈1 → cap 9)
        phi_macro: float = max(0.0, min(1.0, integration / 9.0))

        hms_raw: float = 0.0
        using_hms: bool = False

        if n_nodes >= self._HMS_MIN_NODES and phi_meso > 0 and phi_macro > 0:
            # Level 0 (Micro): IIT 3.0 on elite 16-node subgraphs (5 samples, median)
            phi_micro = self._compute_iit_micro()

            if phi_micro > 0:
                # True multiplicative HMS-Phi
                hms_raw = (
                    math.pow(phi_micro, _HMS_EXP_MICRO)
                    * math.pow(phi_meso,  _HMS_EXP_MESO)
                    * math.pow(phi_macro, _HMS_EXP_MACRO)
                )
                raw_phi = hms_raw * _HMS_SCALE
                using_hms = True

        if not using_hms:
            # Additive fallback: original v3 formula
            raw_phi = (
                self._w_int * integration
                + self._w_diff * differentiation
                + self._w_mip * self._last_mip_score
            )

        # --- Final Phi ---
        phi = min(raw_phi * redundancy_factor, gate_ceiling)

        # --- Convergence tracking ---
        self._recent_phi_values.append(phi)
        convergence_stddev = self._compute_convergence_stddev()

        result = {
            'phi_value': round(phi, 6),
            'phi_raw': round(raw_phi, 6),
            'phi_threshold': PHI_THRESHOLD,
            'above_threshold': phi >= PHI_THRESHOLD,
            'integration_score': round(integration, 6),
            'differentiation_score': round(differentiation, 6),
            'mip_score': round(self._last_mip_score, 6),
            'redundancy_factor': round(redundancy_factor, 4),
            # HMS-Phi components
            'phi_micro': round(phi_micro, 6),
            'phi_meso': round(phi_meso, 6),
            'phi_macro': round(phi_macro, 6),
            'hms_phi_raw': round(hms_raw, 6),
            'phi_formula': 'hms_v4' if using_hms else 'additive_v3',
            'num_nodes': n_nodes,
            'num_edges': n_edges,
            'block_height': block_height,
            'timestamp': time.time(),
            'phi_version': 4,
            'gates_passed': gates_passed,
            'gates_total': len(MILESTONE_GATES),
            'gate_ceiling': gate_ceiling,
            'gates': gates,
            'gate_stats': getattr(self, '_last_gate_stats', {}),
            'convergence_stddev': round(convergence_stddev, 6),
            'convergence_status': (
                'converged' if convergence_stddev < 0.01
                and len(self._recent_phi_values) >= self._convergence_window
                else 'converging' if len(self._recent_phi_values) >= 10
                else 'insufficient_data'
            ),
            'formula_weights': {
                'integration': self._w_int,
                'differentiation': self._w_diff,
                'mip': self._w_mip,
                'hms_scale': _HMS_SCALE if using_hms else None,
            },
        }

        self._last_full_result = result
        self._last_computed_block = block_height

        self._store_measurement(result)
        return result

    def _compute_iit_micro(self) -> float:
        """Compute IIT 3.0 micro-level Phi via 5 independent 16-node samples.

        Runs the IITApproximator on 5 randomly sampled elite subgraphs and
        returns the median. Result is normalized to [0, 1] and cached for
        _IIT_CACHE_SECONDS to avoid repeated O(16^3) computation.

        Returns:
            Normalized phi_micro in [0, 1], or cached value if within interval.
        """
        now = time.time()
        if now - self._iit_last_time < self._IIT_CACHE_SECONDS:
            return self._iit_phi_cache

        if not self.kg or len(self.kg.nodes) < 16:
            return 0.0

        # Lazy import — only pay for numpy when actually needed
        if self._iit_approximator is None:
            try:
                from .iit_approximator import IITApproximator
                self._iit_approximator = IITApproximator(max_nodes=16)
            except Exception as e:
                logger.warning(f"IITApproximator import failed: {e}")
                self._iit_last_time = now
                return 0.0

        # Build an adapter that maps KeterEdge (from_node_id/to_node_id) to
        # what IITApproximator expects (source_id/target_id, dict of edges).
        # KnowledgeGraph.edges is a list; IITApproximator.build_tpm_from_kg
        # calls edges.values() expecting a dict.
        class _KGAdapter:
            """Thin adapter: maps KeterEdge attrs to IITApproximator API."""
            __slots__ = ('nodes', 'edges')
            def __init__(self, nodes, edges_list):
                self.nodes = nodes
                self.edges = {
                    i: _EdgeAdapter(e) for i, e in enumerate(edges_list)
                }

        class _EdgeAdapter:
            __slots__ = ('source_id', 'target_id', 'weight')
            def __init__(self, e):
                # KeterEdge uses from_node_id / to_node_id
                self.source_id = getattr(e, 'from_node_id', None)
                self.target_id = getattr(e, 'to_node_id', None)
                self.weight = getattr(e, 'weight', 0.5)

        try:
            kg_nodes = dict(self.kg.nodes)
            kg_edges = list(self.kg.edges)
        except Exception as e:
            logger.debug(f"IIT KG snapshot failed: {e}")
            return self._iit_phi_cache

        # Sample 5 DIFFERENT 16-node subgraphs for diversity.
        # Each sample picks a random subset of nodes and their induced edges.
        all_node_ids = list(kg_nodes.keys())
        n_total = len(all_node_ids)

        phis: List[float] = []
        for sample_idx in range(5):
            try:
                # Random subgraph: sample 16-64 nodes (IITApproximator picks top 16)
                sample_size = min(n_total, max(16, min(64, n_total // 5)))
                rng = random.Random(sample_idx * 7919 + int(time.time()) % 10000)
                sampled_ids = set(rng.sample(all_node_ids, sample_size))
                sub_nodes = {nid: kg_nodes[nid] for nid in sampled_ids}
                sub_edges = [
                    e for e in kg_edges
                    if getattr(e, 'from_node_id', None) in sampled_ids
                    and getattr(e, 'to_node_id', None) in sampled_ids
                ]
                adapter = _KGAdapter(sub_nodes, sub_edges)
                tpm = self._iit_approximator.build_tpm_from_kg(adapter)
                phi_val = self._iit_approximator.compute_phi(tpm)
                if phi_val > 0:
                    phis.append(phi_val)
            except Exception as e:
                logger.debug(f"IIT sample {sample_idx} failed: {e}")

        if phis:
            # Median of samples (robust to outliers)
            phis.sort()
            n = len(phis)
            median_val = phis[n // 2] if n % 2 != 0 else (phis[n//2 - 1] + phis[n//2]) / 2.0
            # Normalize: IIT information-loss values can exceed 1.0; cap at 1.0
            self._iit_phi_cache = min(1.0, median_val)
            logger.info(
                f"HMS phi_micro={self._iit_phi_cache:.4f} "
                f"(5 IIT samples: {[round(p,3) for p in phis]}, median={median_val:.4f})"
            )
        else:
            # All samples failed — keep previous cache to avoid sudden drop
            logger.debug("IIT: all 5 samples failed, keeping cached phi_micro")

        self._iit_last_time = now
        return self._iit_phi_cache

    def get_cached(self) -> dict:
        """Return the last computed Phi result without triggering a recompute.

        Safe to call from latency-sensitive paths (e.g., chat, response synthesis).
        Returns sensible defaults if no cached result exists yet — never blocks.
        """
        if self._last_full_result is not None:
            result = dict(self._last_full_result)
            result['cached'] = True
            return result
        # No cache yet — return defaults rather than blocking on a full compute
        return {
            'phi_value': 0.0,
            'phi_raw': 0.0,
            'phi_threshold': PHI_THRESHOLD,
            'above_threshold': False,
            'integration_score': 0.0,
            'differentiation_score': 0.0,
            'mip_score': 0.0,
            'redundancy_factor': 1.0,
            'num_nodes': len(self.kg.nodes) if self.kg else 0,
            'num_edges': len(self.kg.edges) if self.kg else 0,
            'block_height': 0,
            'phi_version': 3,
            'gates_passed': 0,
            'gates_total': len(MILESTONE_GATES),
            'cached': True,
        }

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
        # Uses Fiedler-vector spectral bisection for meaningful partition
        # instead of arbitrary node-ID-order split
        mi_score = 0.0
        if (hasattr(self.kg, 'vector_index')
                and self.kg.vector_index
                and len(self.kg.vector_index.embeddings) >= 10
                and len(components) == 1):
            # Build weighted adjacency for spectral bisection
            node_list = list(nodes.keys())
            try:
                mi_adj, mi_degree = self._build_weighted_adj_for_mi(
                    node_list, nodes, edges, n_nodes
                )
                lambda_max = max(mi_degree) if mi_degree else 1.0
                if lambda_max <= 0.0:
                    lambda_max = 1.0
                fiedler = self._power_iteration_fiedler(
                    mi_adj, mi_degree, lambda_max + 0.1, n_nodes, max_iter=30
                )
                if fiedler is not None:
                    # Split by Fiedler vector sign
                    partition_a = [node_list[i] for i in range(n_nodes) if fiedler[i] <= 0]
                    partition_b = [node_list[i] for i in range(n_nodes) if fiedler[i] > 0]
                else:
                    mid = n_nodes // 2
                    partition_a = node_list[:mid]
                    partition_b = node_list[mid:]
            except Exception:
                mid = n_nodes // 2
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

        # Contradiction penalty: high contradiction ratio reduces integration
        contradiction_count = sum(1 for e in edges if e.edge_type == 'contradicts')
        if edges:
            contradiction_ratio = contradiction_count / len(edges)
            cross_flow *= (1.0 - contradiction_ratio * 0.5)  # Penalize contradictions

        # Minimum Information Partition (algebraic connectivity + spectral cut)
        mip_score = 0.0
        if n_nodes >= 10:
            try:
                mip_score = self._compute_mip(nodes, edges)
            except Exception as e:
                logger.warning(f"MIP error: {e}")
                mip_score = 0.0

        # Store MIP on instance for result dict access
        self._last_mip_score = mip_score

        return structural + mi_score + cross_flow

    # ========================================================================
    # Convergence Tracking
    # ========================================================================

    def _compute_convergence_stddev(self) -> float:
        """Compute standard deviation of recent Phi measurements.

        Used to report whether Phi has converged to a stable value.
        """
        values = list(self._recent_phi_values)
        if len(values) < 2:
            return 999.0  # sentinel for "not yet converged" — JSON-serializable
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance)

    # ========================================================================
    # Helper: Build weighted adjacency for MI spectral bisection
    # ========================================================================

    def _build_weighted_adj_for_mi(
        self,
        node_list: list,
        nodes: dict,
        edges: list,
        n_nodes: int,
    ) -> Tuple[Dict[int, Dict[int, float]], List[float]]:
        """Build weighted adjacency matrix and degree vector for MI partition.

        Samples nodes if graph is too large, then builds the dict-of-dicts
        adjacency needed by _power_iteration_fiedler.

        Returns:
            (adj, degree) where adj is Dict[idx, Dict[idx, float]] and
            degree is List[float].
        """
        # Sample for large graphs
        if n_nodes > PHI_MAX_SAMPLE_NODES:
            _rng = random.Random(PHI_SAMPLE_SEED)
            node_list = _rng.sample(node_list, PHI_MAX_SAMPLE_NODES)
            n_nodes = len(node_list)

        id_to_idx = {nid: i for i, nid in enumerate(node_list)}
        adj: Dict[int, Dict[int, float]] = {i: {} for i in range(n_nodes)}

        for edge in edges:
            fid, tid = edge.from_node_id, edge.to_node_id
            if fid not in id_to_idx or tid not in id_to_idx or fid == tid:
                continue
            fi, ti = id_to_idx[fid], id_to_idx[tid]
            w = edge.weight if hasattr(edge, 'weight') else 1.0
            adj[fi][ti] = adj[fi].get(ti, 0.0) + w
            adj[ti][fi] = adj[ti].get(fi, 0.0) + w

        degree = [sum(adj[i].values()) for i in range(n_nodes)]
        return adj, degree

    # ========================================================================
    # Minimum Information Partition (MIP) via Spectral Bisection
    # ========================================================================

    def _compute_mip(self, nodes: dict, edges: list) -> float:
        """
        Compute integration metric using algebraic connectivity + normalized cut.

        Uses the Fiedler value (second-smallest eigenvalue of graph Laplacian)
        as a direct measure of graph integration, supplemented by the
        normalized cut ratio from spectral bisection.

        For large graphs, samples PHI_MAX_SAMPLE_NODES nodes and their
        induced subgraph.

        Args:
            nodes: Dict[int, KeterNode] — knowledge graph nodes
            edges: List[KeterEdge] — knowledge graph edges

        Returns:
            MIP score (float >= 0).  Higher means more integrated.
        """
        n_nodes = len(nodes)
        if n_nodes < 10:
            return 0.0

        # --- Sample nodes for large graphs via BFS expansion ---
        # Random sampling destroys edge density. BFS preserves local structure.
        node_ids = list(nodes.keys())
        if n_nodes > PHI_MAX_SAMPLE_NODES:
            _phi_rng = random.Random(PHI_SAMPLE_SEED)
            # Pick a few random seeds and BFS-expand to get connected subgraph
            seeds = _phi_rng.sample(node_ids, min(10, n_nodes))
            sampled_ids: Set[int] = set()
            bfs_queue = deque(seeds)
            # Build quick adjacency from edges for BFS
            _adj_list: Dict[int, List[int]] = {}
            for edge in edges:
                _adj_list.setdefault(edge.from_node_id, []).append(edge.to_node_id)
                _adj_list.setdefault(edge.to_node_id, []).append(edge.from_node_id)
            while bfs_queue and len(sampled_ids) < PHI_MAX_SAMPLE_NODES:
                nid = bfs_queue.popleft()
                if nid in sampled_ids or nid not in nodes:
                    continue
                sampled_ids.add(nid)
                for neighbor in _adj_list.get(nid, []):
                    if neighbor not in sampled_ids:
                        bfs_queue.append(neighbor)
            node_ids = list(sampled_ids)
            n_nodes = len(node_ids)
        else:
            sampled_ids = set(node_ids)

        # Create index mapping
        id_to_idx: Dict[int, int] = {nid: i for i, nid in enumerate(node_ids)}

        # --- Build weighted adjacency ---
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
            adj[fi][ti] = adj[fi].get(ti, 0.0) + w
            adj[ti][fi] = adj[ti].get(fi, 0.0) + w

        # Count edges in sample
        n_sample_edges = sum(len(v) for v in adj.values()) // 2
        if n_sample_edges < 5:
            return 0.0

        # --- Degree vector ---
        degree: List[float] = [0.0] * n_nodes
        for i in range(n_nodes):
            degree[i] = sum(adj[i].values())

        # --- Algebraic connectivity via inverse power iteration ---
        # The Fiedler value (lambda_2 of Laplacian) directly measures integration.
        # Higher lambda_2 = harder to disconnect = more integrated.
        lambda_max = max(degree) if degree else 1.0
        if lambda_max <= 0.0:
            lambda_max = 1.0
        shift = 2.0 * lambda_max + 0.1

        fiedler = self._power_iteration_fiedler(adj, degree, shift, n_nodes, max_iter=50)

        if fiedler is None:
            # Graph likely disconnected — use connectivity ratio
            connected = sum(1 for d in degree if d > 0)
            return 0.1 * connected / n_nodes

        # Estimate Fiedler value (lambda_2) from the Rayleigh quotient:
        # lambda_2 = v^T L v / v^T v  (v is Fiedler vector, already normalized)
        # L*v[i] = degree[i]*v[i] - sum(adj[i][j]*v[j])
        lv = [0.0] * n_nodes
        for i in range(n_nodes):
            lv[i] = degree[i] * fiedler[i]
            for j, w in adj[i].items():
                lv[i] -= w * fiedler[j]
        rayleigh = sum(fiedler[i] * lv[i] for i in range(n_nodes))
        # rayleigh ≈ lambda_2 since fiedler is normalized

        # Also compute normalized cut for the spectral bisection
        sorted_indices = sorted(range(n_nodes), key=lambda i: fiedler[i])
        mid = n_nodes // 2
        part_a = set(sorted_indices[:mid])

        cut_weight = 0.0
        total_flow = 0.0
        for i in range(n_nodes):
            for j, w in adj[i].items():
                if j > i:
                    total_flow += w
                    if (i in part_a) != (j in part_a):
                        cut_weight += w

        # Normalized cut ratio: fraction of edge weight crossing the partition
        ncut = cut_weight / total_flow if total_flow > 0 else 0.0

        # Integration score: combine algebraic connectivity with normalized cut
        # Higher algebraic connectivity and higher cut ratio = more integrated
        # Scale algebraic connectivity to [0, 0.5] range
        avg_degree = sum(degree) / n_nodes if n_nodes > 0 else 1.0
        alg_conn_normalized = min(0.5, rayleigh / max(avg_degree, 0.01))

        # ncut in [0, 0.5] typically; scale to [0, 0.5]
        ncut_contribution = min(0.5, ncut)

        mip_score = alg_conn_normalized + ncut_contribution
        logger.info(f"MIP={mip_score:.3f} (ac={rayleigh:.3f} ncut={ncut:.3f})")
        return mip_score

    def _power_iteration_fiedler(
        self,
        adj: Dict[int, Dict[int, float]],
        degree: List[float],
        shift: float,
        n: int,
        max_iter: int = 20,
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
        _fiedler_rng = random.Random(123)  # local RNG for reproducibility
        v: List[float] = [
            (1.0 if i % 2 == 0 else -1.0) + _fiedler_rng.uniform(-0.01, 0.01)
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

        # Domain diversity: Shannon entropy over node domains
        domain_counts: Dict[str, int] = {}
        for node in nodes.values():
            domain = getattr(node, 'domain', None) or 'unknown'
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        domain_entropy = 0.0
        if len(domain_counts) > 1:
            for count in domain_counts.values():
                p = count / n
                if p > 0:
                    domain_entropy -= p * math.log2(p)

        # Semantic diversity: estimate from vector embedding variance
        semantic_diversity = 0.0
        if (hasattr(self, 'kg') and self.kg
                and hasattr(self.kg, 'vector_index')
                and self.kg.vector_index
                and len(self.kg.vector_index.embeddings) >= 10):
            try:
                embs = list(self.kg.vector_index.embeddings.values())[:500]
                if embs and embs[0]:
                    dim = len(embs[0])
                    n_emb = len(embs)
                    # Compute per-dimension variance as diversity proxy
                    total_var = 0.0
                    for d in range(min(dim, 32)):  # Sample first 32 dims for speed
                        vals = [e[d] for e in embs]
                        mean_v = sum(vals) / n_emb
                        var = sum((v - mean_v) ** 2 for v in vals) / n_emb
                        total_var += var
                    # Normalize to [0, 1] range
                    semantic_diversity = min(1.0, total_var / max(min(dim, 32), 1))
            except Exception:
                pass

        # Combined differentiation: node types + edge types + confidence + domain + semantic diversity
        return type_entropy + edge_entropy * 0.5 + conf_entropy * 0.3 + domain_entropy * 0.2 + semantic_diversity * 0.3

    # ========================================================================
    # Redundancy Penalty
    # ========================================================================

    def _compute_redundancy_factor(self) -> float:
        """
        Compute redundancy penalty using sampling-based duplicate detection.

        Returns a factor in [0.5, 1.0] — more duplicates = lower factor.
        """
        if not hasattr(self.kg, 'vector_index') or not self.kg.vector_index:
            return 1.0

        n_embeddings = len(self.kg.vector_index.embeddings)
        if n_embeddings < 10:
            return 1.0

        try:
            # Use sample-based approach to avoid O(n^2) full duplicate scan
            duplicates = self.kg.vector_index.find_near_duplicates(
                threshold=0.95
            )
            if not duplicates:
                return 1.0

            dup_nodes = set()
            for a, b, _ in duplicates[:100]:  # cap pairs examined
                dup_nodes.add(a)
                dup_nodes.add(b)

            dup_fraction = len(dup_nodes) / n_embeddings
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

        # Compute cross-domain inference confidence average
        cross_domain_conf_sum = 0.0
        for node in nodes.values():
            content = node.content if isinstance(node.content, dict) else {}
            if (node.node_type == 'inference'
                    and content.get('cross_domain', False)
                    and node.confidence > 0):
                cross_domain_conf_sum += node.confidence
        cross_domain_inference_confidence = (
            cross_domain_conf_sum / max(1, cross_domain_inferences)
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
            'cross_domain_inference_confidence': cross_domain_inference_confidence,
            'verified_predictions': verified_predictions,
            'debate_verdicts': debate_verdicts,
            'contradiction_resolutions': contradiction_resolutions,
            'auto_goals_generated': auto_goals_generated,
            'auto_goals_with_inferences': ext.get('auto_goals_with_inferences', 0),
            'grounding_ratio': grounding_ratio,
            'axiom_from_consolidation': axiom_from_consolidation,
            'novel_concept_count': novel_concept_count,
            # External stats with sensible defaults
            'integration_score': ext.get('integration_score', 0.0),
            'mip_phi': ext.get('mip_phi', 0.0),
            'working_memory_hit_rate': ext.get('working_memory_hit_rate', 0.0),
            'calibration_error': ext.get('calibration_error', 1.0),
            'calibration_evaluations': ext.get('calibration_evaluations', 0),
            'prediction_accuracy': ext.get('prediction_accuracy', 0.0),
            # v4 gate stats — self-improvement and curiosity
            'improvement_cycles_enacted': ext.get('improvement_cycles_enacted', 0),
            'improvement_performance_delta': ext.get('improvement_performance_delta', 0.0),
            'curiosity_driven_discoveries': ext.get('curiosity_driven_discoveries', 0),
        }

        # Log gate stat summary for diagnostics
        logger.debug(
            "Gate stats: nodes=%d debate_verdicts=%d contradiction_resolutions=%d "
            "verified_predictions=%d mip_phi=%.3f auto_goals=%d axioms=%d "
            "novel_concepts=%d cross_domain_inf=%d",
            stats['n_nodes'],
            debate_verdicts,
            contradiction_resolutions,
            verified_predictions,
            stats.get('mip_phi', 0.0),
            auto_goals_generated,
            axiom_from_consolidation,
            novel_concept_count,
            cross_domain_inferences,
        )

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

        # Store computed stats for external inspection (e.g., API debug)
        self._last_gate_stats = {
            'debate_verdicts': debate_verdicts,
            'contradiction_resolutions': contradiction_resolutions,
            'verified_predictions': verified_predictions,
            'auto_goals_generated': auto_goals_generated,
            'axiom_from_consolidation': axiom_from_consolidation,
            'novel_concept_count': novel_concept_count,
            'cross_domain_inferences': cross_domain_inferences,
            'grounding_ratio': round(grounding_ratio, 4),
            'mip_phi': stats.get('mip_phi', 0.0),
            'prediction_accuracy': stats.get('prediction_accuracy', 0.0),
            'calibration_error': stats.get('calibration_error', 1.0),
            'calibration_evaluations': stats.get('calibration_evaluations', 0),
            'auto_goals_with_inferences': stats.get('auto_goals_with_inferences', 0),
        }

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

    def log_gate_progress(self, block_height: int) -> Dict[str, Any]:
        """Log detailed gate progress: what's passed, what's next, what's needed.

        Called periodically (e.g., every 100 blocks) to track V4 gate re-earning.

        Args:
            block_height: Current block height.

        Returns:
            Dict with gate progress summary.
        """
        if not self._last_full_result:
            return {'block_height': block_height, 'gates_passed': 0, 'next_gate': None}

        gates = self._last_full_result.get('gates', [])
        gate_stats = self._last_gate_stats
        passed_ids = [g['id'] for g in gates if g.get('passed')]
        failed = [g for g in gates if not g.get('passed')]

        next_gate = failed[0] if failed else None
        n_nodes = self._last_full_result.get('num_nodes', 0)

        progress = {
            'block_height': block_height,
            'gates_passed': len(passed_ids),
            'gates_total': len(gates),
            'passed_gates': passed_ids,
            'phi_value': self._last_full_result.get('phi_value', 0.0),
            'phi_formula': self._last_full_result.get('phi_formula', 'unknown'),
            'phi_micro': self._last_full_result.get('phi_micro', 0.0),
        }

        if next_gate:
            gate_id = next_gate['id']
            gate_def = MILESTONE_GATES[gate_id - 1] if gate_id <= len(MILESTONE_GATES) else None
            needed_nodes = gate_def['nodes'] if gate_def else 0
            progress['next_gate'] = {
                'id': gate_id,
                'name': next_gate['name'],
                'requirement': next_gate['requirement'],
                'nodes_have': n_nodes,
                'nodes_need': needed_nodes,
                'nodes_remaining': max(0, needed_nodes - n_nodes),
            }
            # Add relevant metric gaps for the next gate
            if gate_id == 4:
                progress['next_gate']['debate_verdicts'] = gate_stats.get('debate_verdicts', 0)
                progress['next_gate']['contradiction_resolutions'] = gate_stats.get('contradiction_resolutions', 0)
                progress['next_gate']['mip_phi'] = gate_stats.get('mip_phi', 0)
            elif gate_id == 5:
                progress['next_gate']['cross_domain_inferences'] = gate_stats.get('cross_domain_inferences', 0)
            elif gate_id == 6:
                progress['next_gate']['improvement_cycles_enacted'] = gate_stats.get('improvement_cycles_enacted', 0)
            elif gate_id == 7:
                progress['next_gate']['calibration_error'] = gate_stats.get('calibration_error', 1.0)
                progress['next_gate']['calibration_evaluations'] = gate_stats.get('calibration_evaluations', 0)

            logger.info(
                "GATE PROGRESS [block %d] %d/%d passed | phi=%.4f (%s) | "
                "next: Gate %d '%s' — need %d more nodes + %s",
                block_height,
                len(passed_ids),
                len(gates),
                progress['phi_value'],
                progress['phi_formula'],
                gate_id,
                next_gate['name'],
                max(0, needed_nodes - n_nodes),
                next_gate['requirement'],
            )
        else:
            logger.info(
                "GATE PROGRESS [block %d] ALL %d GATES PASSED | phi=%.4f",
                block_height, len(gates), progress['phi_value'],
            )

        return progress

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
    # Phi Trend Tracking & Breakdown (Improvements 66-75)
    # ========================================================================

    _TREND_BUFFER_SIZE: int = 100

    def get_phi_trend(self) -> dict:
        """Get Phi trend analysis from recent history.

        Stores last 100 Phi values and computes whether Phi is rising,
        falling, or stable.

        Returns:
            Dict with trend direction, slope, recent_values count,
            min/max/avg of recent window.
        """
        history = self._phi_history
        if len(history) < 5:
            return {
                'direction': 'insufficient_data',
                'slope': 0.0,
                'sample_count': len(history),
            }

        recent = history[-min(self._TREND_BUFFER_SIZE, len(history)):]
        values = [v for _, v in recent]
        n = len(values)

        # Linear regression for trend
        mean_x = (n - 1) / 2.0
        mean_y = sum(values) / n
        ss_xx = sum((i - mean_x) ** 2 for i in range(n))
        ss_xy = sum((i - mean_x) * (values[i] - mean_y) for i in range(n))
        slope = ss_xy / ss_xx if ss_xx > 0 else 0.0

        if abs(slope) < 0.001:
            direction = 'stable'
        elif slope > 0:
            direction = 'rising'
        else:
            direction = 'falling'

        return {
            'direction': direction,
            'slope': round(slope, 6),
            'sample_count': n,
            'min_phi': round(min(values), 6),
            'max_phi': round(max(values), 6),
            'avg_phi': round(mean_y, 6),
            'latest_phi': round(values[-1], 6),
        }

    def get_phi_breakdown(self) -> dict:
        """Get structured breakdown of all Phi components.

        Returns:
            Dict with integration, differentiation, mip,
            redundancy, gates, convergence, and trend info.
        """
        if self._last_full_result is None:
            return {'status': 'no_computation_yet'}

        r = self._last_full_result
        return {
            'phi_value': r.get('phi_value', 0.0),
            'phi_raw': r.get('phi_raw', 0.0),
            'components': {
                'integration': r.get('integration_score', 0.0),
                'differentiation': r.get('differentiation_score', 0.0),
                'mip': r.get('mip_score', 0.0),
            },
            'formula_weights': r.get('formula_weights', {}),
            'penalties': {
                'redundancy_factor': r.get('redundancy_factor', 1.0),
                'gate_ceiling': r.get('gate_ceiling', 0.0),
            },
            'gates': {
                'passed': r.get('gates_passed', 0),
                'total': r.get('gates_total', 10),
            },
            'convergence': {
                'stddev': r.get('convergence_stddev', 0.0),
                'status': r.get('convergence_status', 'unknown'),
            },
            'trend': self.get_phi_trend(),
        }

    def predict_gate_progress(self, blocks_ahead: int = 10000) -> List[dict]:
        """Estimate when each unpassed gate might be reached.

        Uses current growth rate to extrapolate node count and predict
        when each gate's node threshold will be met.

        Args:
            blocks_ahead: How many blocks to project forward.

        Returns:
            List of dicts with gate_id, estimated_blocks_to_pass, and
            current progress percentage.
        """
        if len(self._phi_history) < 20 or not self.kg:
            return []

        # Estimate node growth rate from recent history
        n_nodes = len(self.kg.nodes)
        history = self._phi_history
        if len(history) >= 20:
            block_span = history[-1][0] - history[-20][0]
        else:
            block_span = 1

        # Use progress from get_gate_progress
        gate_progress = self.get_gate_progress()
        predictions: List[dict] = []

        # Gate node thresholds (reduced values)
        gate_thresholds = [g['nodes'] for g in MILESTONE_GATES]

        for gp in gate_progress:
            gid = gp['id']
            if gp['passed']:
                predictions.append({
                    'gate_id': gid,
                    'name': gp['name'],
                    'status': 'passed',
                    'progress_pct': 100.0,
                })
                continue

            threshold = gate_thresholds[gid - 1] if gid <= len(gate_thresholds) else 100000
            if n_nodes >= threshold:
                # Node threshold met but other criteria missing
                predictions.append({
                    'gate_id': gid,
                    'name': gp['name'],
                    'status': 'awaiting_quality_criteria',
                    'progress_pct': gp.get('progress_pct', 0),
                })
            else:
                # Estimate blocks until node threshold
                remaining_nodes = threshold - n_nodes
                # Rough estimate: ~1 node per block (from observation)
                est_blocks = remaining_nodes
                predictions.append({
                    'gate_id': gid,
                    'name': gp['name'],
                    'status': 'in_progress',
                    'progress_pct': gp.get('progress_pct', 0),
                    'nodes_needed': remaining_nodes,
                    'est_blocks': est_blocks,
                })

        return predictions

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
            'redundancy_factor': 1.0,
            'phi_micro': 0.0,
            'phi_meso': 0.0,
            'phi_macro': 0.0,
            'hms_phi_raw': 0.0,
            'phi_formula': 'additive_v3',
            'num_nodes': 0,
            'num_edges': 0,
            'block_height': block_height,
            'timestamp': time.time(),
            'phi_version': 4,
            'gates_passed': 0,
            'gates_total': len(MILESTONE_GATES),
            'gate_ceiling': 0.0,
            'gates': [],
            'convergence_stddev': 0.0,
            'convergence_status': 'insufficient_data',
            'formula_weights': {
                'integration': getattr(self, '_w_int', 1.0),
                'differentiation': getattr(self, '_w_diff', 0.5),
                'mip': getattr(self, '_w_mip', 1.5),
            },
        }

    def get_gate_progress(self) -> List[dict]:
        """Return detailed progress for each milestone gate.

        Shows how close each gate is to passing with specific metric
        values vs requirements, suitable for dashboard display.

        Returns:
            List of dicts with gate id, name, passed status, and
            individual metric progress indicators.
        """
        if not self.kg or not self.kg.nodes:
            return [
                {
                    'id': g['id'],
                    'name': g['name'],
                    'passed': False,
                    'progress': 'No knowledge graph data',
                }
                for g in MILESTONE_GATES
            ]

        nodes = self.kg.nodes
        edges = self.kg.edges
        n_nodes = len(nodes)
        n_edges = len(edges)

        # Compute stats (same as _check_gates)
        node_type_counts: Dict[str, int] = {}
        confidence_sum = 0.0
        domains: set = set()
        grounded_nodes = 0
        verified_predictions = 0
        debate_verdicts = 0
        contradiction_resolutions = 0
        auto_goals_generated = 0
        self_reflection_nodes = 0
        axiom_from_consolidation = 0
        cross_domain_inferences = 0
        novel_concept_count = 0

        for node in nodes.values():
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1
            confidence_sum += node.confidence
            if node.domain:
                domains.add(node.domain)
            if getattr(node, 'grounding_source', '') != '':
                grounded_nodes += 1
            content = node.content if isinstance(node.content, dict) else {}
            content_type = content.get('type', '')
            if content.get('source') == 'self-reflection':
                self_reflection_nodes += 1
            if node.node_type == 'inference' and content.get('cross_domain', False):
                cross_domain_inferences += 1
            if content_type == 'prediction_confirmed':
                verified_predictions += 1
            if content_type == 'debate_synthesis':
                debate_verdicts += 1
            if content_type == 'contradiction_resolution':
                contradiction_resolutions += 1
            if node.node_type == 'meta_observation':
                auto_goals_generated += 1
            if node.node_type == 'axiom' and content_type == 'consolidated_pattern':
                axiom_from_consolidation += 1
            if content_type in ('generalization', 'concept_cluster'):
                novel_concept_count += 1

        edge_type_counts: Dict[str, int] = {}
        for edge in edges:
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

        avg_confidence = confidence_sum / n_nodes if n_nodes > 0 else 0.0
        grounding_ratio = grounded_nodes / n_nodes if n_nodes > 0 else 0.0
        types_with_10 = len([t for t, c in node_type_counts.items() if c >= 10])
        causal_pct = (edge_type_counts.get('causes', 0) / n_edges * 100) if n_edges > 0 else 0.0
        inference_count = node_type_counts.get('inference', 0)

        progress: List[dict] = []

        # Build stats dict matching what _check_gates uses
        stats = {
            'n_nodes': n_nodes,
            'n_edges': n_edges,
            'avg_confidence': avg_confidence,
            'n_domains': len(domains),
            'n_node_types': len(node_type_counts),
            'types_with_50': len([t for t, c in node_type_counts.items() if c >= 50]),
            'verified_predictions': verified_predictions,
            'debate_verdicts': debate_verdicts,
            'contradiction_resolutions': contradiction_resolutions,
            'cross_domain_edges': self._count_cross_domain_edges(),
            'auto_goals_generated': auto_goals_generated,
            'self_reflection_nodes': self_reflection_nodes,
            'axiom_from_consolidation': axiom_from_consolidation,
            'cross_domain_inferences': cross_domain_inferences,
            'novel_concept_count': novel_concept_count,
            'inference_count': node_type_counts.get('inference', 0),
            'grounding_ratio': grounding_ratio,
            'mip_score': self._last_mip_score,
        }
        # Add stats from subsystem injection
        stats.update(self._subsystem_stats)

        # Evaluate gates using the canonical MILESTONE_GATES definitions
        for gate in MILESTONE_GATES:
            gate_id = gate['id']
            gate_name = gate['name']
            node_req = gate.get('nodes', 0)
            passed = gate['check'](stats)

            # Node progress as primary metric
            node_pct = min(1.0, n_nodes / node_req) * 100 if node_req > 0 else 100.0

            progress.append({
                'id': gate_id,
                'name': gate_name,
                'passed': passed,
                'metrics': {
                    'nodes': f'{n_nodes}/{node_req}',
                },
                'progress_pct': round(min(100, node_pct), 1),
            })

        return progress

    def downsample_phi_measurements(self, retain_days: int = None) -> dict:
        """
        Downsample old phi measurements to reduce DB bloat.

        - Rows within retain_days: kept as-is (per-block granularity)
        - Rows older than retain_days but < 30 days: collapsed to hourly averages
        - Rows older than 30 days: collapsed to daily averages
        """
        if retain_days is None:
            retain_days = self._phi_downsample_retain_days

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

    def _archive_history(self) -> int:
        """Archive old phi_history entries to DB when history exceeds max.

        Keeps the most recent 1000 entries in memory but persists all
        older entries to the phi_measurements table for long-term storage.

        Returns:
            Number of entries archived.
        """
        if len(self._phi_history) <= self._max_history:
            return 0

        # Entries to archive: everything except the most recent _max_history
        archive_count = len(self._phi_history) - self._max_history
        to_archive = self._phi_history[:archive_count]

        archived = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                for block_height, phi_value in to_archive:
                    session.execute(
                        text("""
                            INSERT INTO phi_measurements
                            (phi_value, phi_threshold, integration_score,
                             differentiation_score, num_nodes, num_edges, block_height)
                            VALUES (:phi, :threshold, 0.0, 0.0, 0, 0, :bh)
                        """),
                        {
                            'phi': phi_value,
                            'threshold': PHI_THRESHOLD,
                            'bh': block_height,
                        }
                    )
                    archived += 1
                session.commit()

            # Trim in-memory history to most recent entries
            self._phi_history = self._phi_history[archive_count:]
            logger.info(
                f"Phi history archived: {archived} entries written to DB, "
                f"{len(self._phi_history)} kept in memory"
            )
        except Exception as e:
            logger.debug(f"Failed to archive phi history: {e}")

        return archived

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
# NOTE: Rust PhiCalculator has different API (no kg/db args, compute_phi takes
# nodes/edges explicitly). Keep Python PhiCalculator for now; the expensive
# _compute_mip is optimized by reducing PHI_MAX_SAMPLE_NODES and caching.
try:
    import aether_core as _aether_core  # noqa: F401
    logger.info("PhiCalculator: using pure-Python with Rust KeterNode/KeterEdge")
except ImportError:
    logger.debug("aether_core not installed — using pure-Python PhiCalculator")
