"""
Phi Calculator v5 — HMS-Phi with IIT 3.0 Micro-Level Integration

Computes Phi (Φ) as a multi-scale integration metric for the Aether Tree
knowledge graph. Uses IIT 3.0 approximation (TPM-based MIP search) as
the micro-level phi computation for honest, non-inflated measurements.

HMS-Phi formula:
    phi_micro: IIT 3.0 approximation via TPM bipartition search (Level 0)
               Uses IITApproximator on elite node subsample from KG.
    phi_meso:  Intra/cross-domain edge ratio (Level 1)
    phi_macro: Graph density integration (Level 2)

    hms_raw = phi_micro^(1/φ) × phi_meso^(1/φ²) × phi_macro^(1/φ³)
    raw_phi = hms_raw  (NO artificial scaling)
    phi = min(raw_phi, gate_ceiling)

Phi values are intentionally low (0-1 range) until the system earns
higher values through genuine cognitive integration. The 10-gate
milestone system controls the ceiling.

Note: This is NOT a measure of phenomenal consciousness. It is an integration
metric that quantifies how well-connected and information-rich the knowledge
graph is, using principles inspired by (but not equivalent to) Tononi's IIT.
"""
import math
import os
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger
from .iit_approximator import IITApproximator

# Rust acceleration — REQUIRED for phi computation
_RUST_AVAILABLE = False
try:
    from .rust_bridge import RUST_AVAILABLE, RustPhiCalculator
    _RUST_AVAILABLE = RUST_AVAILABLE and RustPhiCalculator is not None
except ImportError:
    pass

logger = get_logger(__name__)

# Phi integration threshold for Proof-of-Thought validity (loaded from Config)
# This is an integration quality threshold, not a consciousness threshold
PHI_THRESHOLD = Config.PHI_THRESHOLD

# ============================================================================
# MILESTONE GATES (Peer-Reviewed Thresholds v4)
# Each passed gate unlocks +0.5 Phi ceiling (max 5.0).  Gates require genuine
# cognitive milestones emphasizing QUALITY over quantity.  Volume alone cannot
# pass higher gates — they require validated predictions, genuine cross-domain
# transfer, enacted self-improvement, and novel concept synthesis.
#
# NOTE: Gate evaluation happens in Rust (aether-phi crate). These Python
# definitions are kept for get_gate_progress() dashboard and diagnostic APIs.
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
        'description': 'Self-improvement actions enacted AND producing measurable gains with FEP convergence',
        'nodes': 20000,
        'check': lambda stats: (
            stats['n_nodes'] >= 20000
            and stats.get('improvement_cycles_enacted', 0) >= 10
            and stats.get('improvement_performance_delta', 0) > 0.0
            and stats.get('fep_free_energy_decreasing', False)
        ),
        'requirement': '>=20K nodes, >=10 enacted improvement cycles, positive performance delta, FEP free energy decreasing',
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
        'description': 'System generates its own research goals with FEP-guided exploration across domains',
        'nodes': 35000,
        'check': lambda stats: (
            stats['n_nodes'] >= 35000
            and stats.get('auto_goals_generated', 0) >= 50
            and stats.get('auto_goals_with_inferences', 0) >= 30
            and stats.get('curiosity_driven_discoveries', 0) >= 10
            and stats.get('fep_domain_precisions', 0) >= 3
        ),
        'requirement': '>=35K nodes, >=50 auto-goals, >=30 producing inferences, >=10 curiosity discoveries, FEP precision in >=3 domains',
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
        'description': 'Genuine novel concepts with diverse Sephirot cognitive participation',
        'nodes': 75000,
        'check': lambda stats: (
            stats['n_nodes'] >= 75000
            and stats.get('novel_concept_count', 0) >= 50
            and stats.get('cross_domain_inferences', 0) >= 100
            and stats.get('improvement_performance_delta', 0) > 0.05
            and stats.get('sephirot_winner_diversity', 0) >= 0.5
        ),
        'requirement': '>=75K nodes, >=50 novel concepts, >=100 cross-domain inferences, sustained self-improvement, Sephirot winner diversity >=0.5',
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

    v5: Integrates IIT 3.0 approximation (IITApproximator) as the micro-level
    phi computation. No artificial scaling -- phi values are honest and will
    be low until the system earns higher integration through genuine
    cognitive milestones.

    Computation paths:
      - Rust (primary): Delegates to aether-phi crate via PyO3, supplements
        with IIT micro phi when Rust MIP is zero.
      - Python fallback: Uses IITApproximator for phi_micro, graph stats for
        phi_meso and phi_macro. No inflation factor.

    Python handles:
      - Stats collection from live subsystems
      - DB storage/retrieval
      - Caching and trend tracking
      - Dashboard/diagnostic APIs
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

        # IIT 3.0 Approximator for honest micro-level phi
        self._iit = IITApproximator(max_nodes=12)

        # Rust PhiCalculator — sole computation engine
        self._rust_phi = None
        if _RUST_AVAILABLE and RustPhiCalculator is not None:
            try:
                self._rust_phi = RustPhiCalculator(self._compute_interval)
                logger.info("PhiCalculator: Rust acceleration ACTIVE (sole compute path)")
            except Exception as exc:
                logger.error("PhiCalculator: Rust init failed (%s) — using Python fallback", exc)
        else:
            logger.warning("PhiCalculator: Rust extension NOT available — using Python fallback")

        # Adaptive gate scale factor: multiplier for node-count thresholds
        self._gate_scale: float = float(
            os.getenv('PHI_GATE_SCALE', '1.0')
        )
        # History of (block_height, phi_value) for adaptation
        self._phi_history: List[Tuple[int, float]] = []
        self._max_history: int = 1000
        # Subsystem stats injected by AetherEngine before each compute_phi call
        self._subsystem_stats: Dict[str, float] = {}
        self._restore_subsystem_stats()
        # Cached Config values
        self._phi_downsample_retain_days: int = Config.PHI_DOWNSAMPLE_RETAIN_DAYS
        # Convergence tracking: stddev over last N measurements
        self._convergence_window: int = Config.PHI_CONVERGENCE_WINDOW
        self._recent_phi_values: deque = deque(maxlen=Config.PHI_CONVERGENCE_WINDOW)

        # Restore last phi measurement from DB so get_cached() returns
        # non-zero values immediately after restart
        self._restore_from_db()

    def _restore_from_db(self) -> None:
        """Load the latest phi measurement from DB to warm the cache on startup."""
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
                        'phi_version': 5,
                        'gates_passed': 0,  # recomputed on next compute_phi
                        'gates_total': len(MILESTONE_GATES),
                        'gate_ceiling': 0.0,
                        'gates': [],
                        'convergence_stddev': 0.0,
                        'convergence_status': 'restored',
                    }
                    self._last_full_result = restored
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
        Persists to file so stats survive container restarts.

        Args:
            stats: Dict with keys like working_memory_hit_rate,
                calibration_error, prediction_accuracy.
        """
        self._subsystem_stats = stats
        # Persist for restart recovery
        try:
            import json as _json
            with open('/app/data/subsystem_stats.json', 'w') as f:
                _json.dump(stats, f)
        except Exception:
            pass

    def _restore_subsystem_stats(self) -> None:
        """Restore persisted subsystem stats from file."""
        try:
            import json as _json
            with open('/app/data/subsystem_stats.json', 'r') as f:
                self._subsystem_stats = _json.load(f)
                logger.info("Restored subsystem stats from file: %d keys",
                            len(self._subsystem_stats))
        except Exception:
            pass

    def compute_phi(self, block_height: int = 0) -> dict:
        """
        Compute Phi integration metric using Rust HMS-Phi v4.

        ALL computation is performed in Rust. Python provides:
        - Subsystem stats (via extra_stats dict)
        - Caching and DB storage

        Returns:
            Dict with phi_value, HMS components, gates breakdown.
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

        # ── Rust-only phi computation ─────────────────────────────────────
        if (self._rust_phi is not None
                and hasattr(self.kg, 'rust_kg')
                and self.kg.rust_kg is not None):
            try:
                extra_stats = dict(self._subsystem_stats) if self._subsystem_stats else None
                result = self._rust_phi.compute_phi(self.kg.rust_kg, block_height, extra_stats)
                if result and isinstance(result, dict) and 'phi_value' in result:
                    logger.info(
                        "Rust compute_phi OK: phi_value=%.4f, gates_passed=%s, mip=%.4f",
                        float(result.get('phi_value', 0)),
                        result.get('gates_passed', '?'),
                        float(result.get('mip_score', 0)),
                    )
                    # ── V5: De-inflate Rust HMS_SCALE=8.0 ──────────────
                    # Rust bakes in ×8.0 scaling (HMS_SCALE constant).
                    # V5 removes this inflation — phi should be honest.
                    hms_raw = float(result.get('hms_phi_raw', 0.0))
                    if hms_raw > 0:
                        # Rust computed: raw_phi = hms_raw × 8.0
                        # We want: raw_phi = hms_raw (no inflation)
                        result['phi_raw'] = hms_raw
                    else:
                        result['phi_raw'] = float(result.get('phi_raw', 0.0)) / 8.0

                    # V5: Re-evaluate gates using Python (authoritative).
                    # Rust gates don't have the mip_phi fallback, so they
                    # under-count passed gates (e.g. Gate 4 stays blocked).
                    # Track MIP early so get_gate_progress can use it.
                    rust_mip = float(result.get('mip_score', 0.0))
                    self._last_mip_score = max(self._last_mip_score, rust_mip)
                    try:
                        py_gates = self.get_gate_progress()
                        gates_passed = sum(1 for g in py_gates if g.get('passed'))
                        result['gates'] = py_gates
                        logger.info("Python gate eval: %d/10 passed", gates_passed)
                    except Exception as gate_exc:
                        logger.warning("Python gate eval failed, using Rust: %s", gate_exc)
                        gates_passed = int(result.get('gates_passed', 0))
                    result['gates_passed'] = gates_passed
                    result['gates_total'] = 10
                    gate_ceiling = gates_passed * 0.5
                    honest_phi = min(result['phi_raw'], gate_ceiling) if gate_ceiling > 0 else 0.0
                    result['phi_value'] = honest_phi
                    result['phi_version'] = 5
                    result['phi_formula'] = 'hms_v5_iit'

                    phi_val = honest_phi
                    self._cache[block_height] = phi_val
                    self._last_full_result = result
                    self._last_computed_block = block_height
                    # ── V5: Run IIT approximator as micro-level phi ────
                    if self.kg and self.kg.nodes:
                        try:
                            tpm = self._iit.build_tpm_from_kg(self.kg, window=200)
                            iit_phi = self._iit.compute_phi(tpm)
                            result['iit_micro_phi'] = min(1.0, iit_phi)
                            result['iit_computations'] = self._iit._computations
                            result['iit_last_phi'] = self._iit._last_phi
                            # Replace phi_micro with real IIT value
                            result['phi_micro'] = min(1.0, iit_phi)
                        except Exception as iit_exc:
                            logger.warning("IIT micro-phi failed: %s", iit_exc)
                            result['iit_micro_phi'] = 0.0
                    self._recent_phi_values.append(phi_val)
                    self._phi_history.append((block_height, phi_val))
                    if len(self._phi_history) > self._max_history:
                        self._phi_history = self._phi_history[-self._max_history:]
                    # Store to DB
                    self._store_measurement(result)
                    return result
            except Exception as exc:
                logger.warning("Rust compute_phi failed: %s", exc)

        # No Rust available — use Python fallback
        return self._python_fallback_phi(block_height)

    # ========================================================================
    # Python fallback — less accurate than Rust HMS-Phi
    # ========================================================================
    # Used when the Rust aether_core PyO3 extension is not available.
    # Computes a simplified, conservative Phi approximation using only
    # basic graph statistics. Values will be lower than Rust HMS-Phi.
    # ========================================================================

    def _python_fallback_phi(self, block_height: int) -> dict:
        """Compute simplified Phi when Rust extension is unavailable.

        Python fallback — less accurate than Rust HMS-Phi.
        Uses graph density and degree distribution as proxies for
        integration metrics. Conservative by design.
        """
        if not self.kg or not self.kg.nodes:
            return self._empty_result(block_height)

        logger.info("Using Python phi fallback (Rust aether_core not available)")

        _PHI = 1.618033988749895
        nodes = self.kg.nodes
        edges = self.kg.edges
        num_nodes = len(nodes)
        num_edges = len(edges)

        # ── phi_macro: Graph-theoretic integration ──────────────────────
        # Algebraic connectivity approximated as graph density
        if num_nodes > 1:
            max_possible_edges = num_nodes * (num_nodes - 1)
            phi_macro = (2.0 * num_edges) / max_possible_edges if max_possible_edges > 0 else 0.0
        else:
            phi_macro = 0.0

        # ── phi_meso: Intra-domain edge ratio (fraction of edges within domains)
        # Build node-to-domain map, then count intra-domain vs total edges.
        # Using edge ratio instead of density (which → 0 for large domains).
        node_domain: Dict[str, str] = {}
        for node_id, node in nodes.items():
            domain = getattr(node, 'domain', None) or 'unknown'
            node_domain[node_id] = domain

        intra_domain_edges = 0
        total_counted = 0
        for edge in edges:
            src = edge.source_id if hasattr(edge, 'source_id') else (edge[0] if isinstance(edge, (list, tuple)) else None)
            tgt = edge.target_id if hasattr(edge, 'target_id') else (edge[1] if isinstance(edge, (list, tuple)) else None)
            if src in node_domain and tgt in node_domain:
                total_counted += 1
                if node_domain[src] == node_domain[tgt]:
                    intra_domain_edges += 1

        # phi_meso = ratio of intra-domain edges (measures domain cohesion)
        # Balanced by cross-domain ratio to avoid trivial 1.0 when all edges
        # are intra-domain (which would mean no cross-domain integration).
        if total_counted > 0:
            intra_ratio = intra_domain_edges / total_counted
            cross_ratio = 1.0 - intra_ratio
            # Geometric mean of cohesion and cross-domain connectivity
            # Max at 0.5/0.5 split, zero if either is zero
            phi_meso = 2.0 * (intra_ratio * cross_ratio) ** 0.5
            phi_meso = max(0.0, min(1.0, phi_meso))
        else:
            phi_meso = 0.0

        # ── phi_micro: IIT 3.0 approximation on elite node subsample ────
        try:
            tpm = self._iit.build_tpm_from_kg(self.kg, window=200)
            iit_phi = self._iit.compute_phi(tpm)
            phi_micro = min(1.0, iit_phi)  # Normalize to [0, 1]
        except Exception as e:
            logger.debug(f"IIT micro-phi failed: {e}")
            phi_micro = 0.0  # Honest zero if IIT fails

        # ── Final HMS-Phi combination ───────────────────────────────────
        # phi = phi_micro^(1/PHI) * phi_meso^(1/PHI^2) * phi_macro^(1/PHI^3)
        # Multiplicative: any zero component zeros the whole thing
        if phi_micro > 0 and phi_meso > 0 and phi_macro > 0:
            hms_raw = (
                phi_micro ** (1.0 / _PHI)
                * phi_meso ** (1.0 / (_PHI ** 2))
                * phi_macro ** (1.0 / (_PHI ** 3))
            )
        else:
            hms_raw = 0.0

        # No artificial scaling — honest phi value
        raw_phi = hms_raw

        # ── Gate evaluation (same thresholds as Rust) ───────────────────
        gate_progress = self.get_gate_progress()
        gates_passed = sum(1 for g in gate_progress if g.get('passed'))
        gate_ceiling = gates_passed * 0.5  # +0.5 per gate

        phi_value = min(raw_phi, gate_ceiling) if gate_ceiling > 0 else 0.0

        # Integration/differentiation scores (simplified)
        integration_score = phi_macro
        differentiation_score = phi_micro

        result = {
            'phi_value': phi_value,
            'phi_raw': raw_phi,
            'phi_threshold': PHI_THRESHOLD,
            'above_threshold': phi_value >= PHI_THRESHOLD,
            'integration_score': integration_score,
            'differentiation_score': differentiation_score,
            'mip_score': 0.0,
            'redundancy_factor': 1.0,
            'phi_micro': phi_micro,
            'phi_meso': phi_meso,
            'phi_macro': phi_macro,
            'hms_phi_raw': hms_raw,
            'phi_formula': 'hms_v5_iit',
            'num_nodes': num_nodes,
            'num_edges': num_edges,
            'block_height': block_height,
            'timestamp': time.time(),
            'phi_version': 5,
            'iit_computations': self._iit._computations,
            'iit_last_phi': self._iit._last_phi,
            'gates_passed': gates_passed,
            'gates_total': len(MILESTONE_GATES),
            'gate_ceiling': gate_ceiling,
            'gates': gate_progress,
            'convergence_stddev': 0.0,
            'convergence_status': 'hms_v5_iit',
        }

        # Update caches
        self._cache[block_height] = phi_value
        self._last_full_result = result
        self._last_computed_block = block_height
        self._recent_phi_values.append(phi_value)
        self._phi_history.append((block_height, phi_value))
        if len(self._phi_history) > self._max_history:
            self._phi_history = self._phi_history[-self._max_history:]

        # Store to DB
        self._store_measurement(result)

        return result

    def get_cached(self) -> dict:
        """Return the last computed Phi result without triggering a recompute.

        Safe to call from latency-sensitive paths (e.g., chat, response synthesis).
        Returns sensible defaults if no cached result exists yet — never blocks.
        If gates are empty (e.g. restored from DB), evaluates them dynamically.
        """
        if self._last_full_result is not None:
            result = dict(self._last_full_result)
            result['cached'] = True
            # Always re-evaluate gates using Python (authoritative).
            # Rust gates and early-session evaluations can be stale.
            if self.kg and self.kg.nodes:
                try:
                    gate_progress = self.get_gate_progress()
                    gates_passed = sum(1 for g in gate_progress if g.get('passed'))
                    gate_ceiling = gates_passed * 0.5
                    result['gates'] = gate_progress
                    result['gates_passed'] = gates_passed
                    result['gate_ceiling'] = gate_ceiling
                    # Update cached result
                    self._last_full_result['gates'] = gate_progress
                    self._last_full_result['gates_passed'] = gates_passed
                    self._last_full_result['gate_ceiling'] = gate_ceiling
                    # Apply gate ceiling to phi_value
                    if gate_ceiling > 0:
                        result['phi_value'] = min(result.get('phi_raw', 0.0), gate_ceiling)
                        self._last_full_result['phi_value'] = result['phi_value']
                except Exception as gc_exc:
                    logger.warning("get_cached gate re-eval failed: %s", gc_exc)
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
            'phi_version': 5,
            'gates_passed': 0,
            'gates_total': len(MILESTONE_GATES),
            'cached': True,
        }

    # ========================================================================
    # Gate Progress & Diagnostics (Python-side, for dashboard APIs)
    # ========================================================================

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
        """Record Phi progression and adapt gate scale based on growth rate."""
        self._phi_history.append((block_height, phi_value))
        if len(self._phi_history) > self._max_history:
            self._phi_history = self._phi_history[-self._max_history:]

        if len(self._phi_history) < 100:
            return

        recent = self._phi_history[-20:]
        older = self._phi_history[-40:-20]
        recent_delta = recent[-1][1] - recent[0][1]
        older_delta = older[-1][1] - older[0][1]

        if older_delta <= 0:
            return

        growth_ratio = recent_delta / older_delta
        if growth_ratio > 3.0:
            self._gate_scale = min(2.0, self._gate_scale * 1.05)
            logger.info(f"Phi growth anomaly (ratio={growth_ratio:.1f}), "
                        f"tightening gates: scale={self._gate_scale:.3f}")
        elif growth_ratio < 0.2 and self._gate_scale > 0.5:
            self._gate_scale = max(0.5, self._gate_scale * 0.98)
            logger.info(f"Phi growth stagnation (ratio={growth_ratio:.1f}), "
                        f"relaxing gates: scale={self._gate_scale:.3f}")

    # ========================================================================
    # Phi Trend Tracking & Breakdown
    # ========================================================================

    _TREND_BUFFER_SIZE: int = 100

    def get_phi_trend(self) -> dict:
        """Get Phi trend analysis from recent history."""
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
        """Get structured breakdown of all Phi components."""
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
        """Estimate when each unpassed gate might be reached."""
        if len(self._phi_history) < 20 or not self.kg:
            return []

        n_nodes = len(self.kg.nodes)
        gate_progress = self.get_gate_progress()
        predictions: List[dict] = []
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
                predictions.append({
                    'gate_id': gid,
                    'name': gp['name'],
                    'status': 'awaiting_quality_criteria',
                    'progress_pct': gp.get('progress_pct', 0),
                })
            else:
                remaining_nodes = threshold - n_nodes
                predictions.append({
                    'gate_id': gid,
                    'name': gp['name'],
                    'status': 'in_progress',
                    'progress_pct': gp.get('progress_pct', 0),
                    'nodes_needed': remaining_nodes,
                    'est_blocks': remaining_nodes,
                })

        return predictions

    # ========================================================================
    # Storage & History
    # ========================================================================

    def _store_measurement(self, result: dict) -> None:
        """Store phi measurement in database."""
        if not self.db:
            return
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
            'phi_formula': 'rust_unavailable',
            'num_nodes': len(self.kg.nodes) if self.kg and self.kg.nodes else 0,
            'num_edges': len(self.kg.edges) if self.kg and self.kg.edges else 0,
            'block_height': block_height,
            'timestamp': time.time(),
            'phi_version': 5,
            'gates_passed': 0,
            'gates_total': len(MILESTONE_GATES),
            'gate_ceiling': 0.0,
            'gates': [],
            'convergence_stddev': 0.0,
            'convergence_status': 'insufficient_data',
        }

    def get_gate_progress(self) -> List[dict]:
        """Return detailed progress for each milestone gate.

        V5: Always uses Python-side gate evaluation (get_gate_stats) as the
        authoritative source.  The Rust code doesn't have the
        `mip_phi = max(rust_mip, integration_score * 0.6)` fallback,
        doesn't count debate_synthesis or contradiction_resolution KG nodes,
        and doesn't track subsystem stats.  Using Rust gates caused Gate 4
        to remain blocked even when Python stats showed it should pass.
        """
        # No Rust result — scan KG nodes for basic progress
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

        # Use DB total if in-memory is a subset
        db_total = getattr(self.kg, '_db_node_count', 0)
        if db_total > n_nodes:
            n_nodes = db_total

        # Snapshot node values to avoid OrderedDict mutation during iteration
        try:
            node_values = list(nodes.values())
        except RuntimeError:
            # Dict changed during list() — use empty fallback
            node_values = []
            logger.warning("KG nodes mutated during snapshot, using empty list")

        node_type_counts: Dict[str, int] = {}
        confidence_sum = 0.0
        domains: set = set()
        grounded_nodes = 0
        verified_predictions = 0
        debate_verdicts = 0
        contradiction_resolutions = 0
        auto_goals_generated = 0
        axiom_from_consolidation = 0
        cross_domain_inferences = 0
        cross_domain_conf_sum = 0.0
        novel_concept_count = 0

        for node in node_values:
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1
            confidence_sum += node.confidence
            if node.domain:
                domains.add(node.domain)
            if getattr(node, 'grounding_source', '') != '':
                grounded_nodes += 1
            content = node.content
            if isinstance(content, str):
                try:
                    import json as _json
                    content = _json.loads(content)
                except Exception:
                    content = {}
            elif not isinstance(content, dict):
                content = {}
            content_type = content.get('type', '')
            if node.node_type == 'inference' and content.get('cross_domain', False):
                cross_domain_inferences += 1
                cross_domain_conf_sum += node.confidence
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

        # Supplement gate-critical counts from DB if in-memory is a subset
        if self.db and (debate_verdicts < 20 or contradiction_resolutions < 10
                        or novel_concept_count < 50):
            try:
                from sqlalchemy import text
                with self.db.get_session() as session:
                    row = session.execute(text(
                        "SELECT "
                        "COUNT(*) FILTER (WHERE content::STRING LIKE '%debate_synthesis%'), "
                        "COUNT(*) FILTER (WHERE content::STRING LIKE '%contradiction_resolution%'), "
                        "COUNT(*) FILTER (WHERE content::STRING LIKE '%generalization%' "
                        "OR content::STRING LIKE '%concept_cluster%') "
                        "FROM knowledge_nodes"
                    )).fetchone()
                    if row:
                        debate_verdicts = max(debate_verdicts, int(row[0] or 0))
                        contradiction_resolutions = max(
                            contradiction_resolutions, int(row[1] or 0))
                        novel_concept_count = max(novel_concept_count, int(row[2] or 0))
            except Exception as db_exc:
                logger.warning("DB gate count fallback failed: %s", db_exc)

        edge_type_counts: Dict[str, int] = {}
        try:
            edge_list = list(edges)
        except RuntimeError:
            edge_list = []
        for edge in edge_list:
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

        avg_confidence = confidence_sum / len(node_values) if len(node_values) > 0 else 0.0
        grounding_ratio = grounded_nodes / n_nodes if n_nodes > 0 else 0.0

        # Compute integration_score from graph connectivity:
        # ratio of edges to nodes × domain diversity, capped at 1.0
        if n_nodes > 0:
            edge_ratio = min(1.0, n_edges / n_nodes)
            domain_ratio = min(1.0, len(domains) / 10.0)  # 10 = max sephirot domains
            integration_score = edge_ratio * 0.7 + domain_ratio * 0.3
        else:
            integration_score = 0.0

        # Cross-domain inference average confidence
        cross_domain_inference_confidence = (
            cross_domain_conf_sum / cross_domain_inferences
            if cross_domain_inferences > 0 else 0.0
        )

        stats = {
            'n_nodes': n_nodes,
            'n_edges': n_edges,
            'avg_confidence': avg_confidence,
            'node_type_counts': node_type_counts,
            'edge_type_counts': edge_type_counts,
            'domain_count': len(domains),
            'cross_domain_inferences': cross_domain_inferences,
            'cross_domain_inference_confidence': cross_domain_inference_confidence,
            'verified_predictions': verified_predictions,
            'debate_verdicts': debate_verdicts,
            'contradiction_resolutions': contradiction_resolutions,
            'auto_goals_generated': auto_goals_generated,
            'auto_goals_with_inferences': self._subsystem_stats.get('auto_goals_with_inferences', 0),
            'grounding_ratio': grounding_ratio,
            'axiom_from_consolidation': axiom_from_consolidation,
            'novel_concept_count': novel_concept_count,
            'integration_score': integration_score,
            'mip_phi': max(self._last_mip_score, integration_score * 0.6),
            'calibration_error': self._subsystem_stats.get('calibration_error', 1.0),
            'calibration_evaluations': self._subsystem_stats.get('calibration_evaluations', 0),
            'prediction_accuracy': self._subsystem_stats.get('prediction_accuracy', 0.0),
            'improvement_cycles_enacted': self._subsystem_stats.get('improvement_cycles_enacted', 0),
            'improvement_performance_delta': self._subsystem_stats.get('improvement_performance_delta', 0.0),
            'curiosity_driven_discoveries': self._subsystem_stats.get('curiosity_driven_discoveries', 0),
            'sephirot_winner_diversity': self._subsystem_stats.get('sephirot_winner_diversity', 0.0),
            'fep_free_energy_decreasing': self._subsystem_stats.get('fep_free_energy_decreasing', False),
            'fep_domain_precisions': self._subsystem_stats.get('fep_domain_precisions', 0),
        }

        # Log Gate 4 diagnostics (the hardest gate to debug)
        logger.info(
            "Gate 4 stats: n_nodes=%d, debate_verdicts=%d, "
            "contradiction_resolutions=%d, mip_phi=%.4f, "
            "mip_score=%.4f, integration_score=%.4f",
            n_nodes, stats['debate_verdicts'],
            stats['contradiction_resolutions'],
            stats['mip_phi'], self._last_mip_score,
            stats['integration_score'],
        )

        progress: List[dict] = []
        for gate in MILESTONE_GATES:
            gate_id = gate['id']
            node_req = gate.get('nodes', 0)
            try:
                passed = bool(gate['check'](stats))
            except Exception:
                passed = False
            node_pct = min(1.0, n_nodes / node_req) * 100 if node_req > 0 else 100.0
            details = {'nodes': f'{n_nodes}/{node_req}'}
            if gate_id == 4:
                details.update({
                    'debate_verdicts': stats['debate_verdicts'],
                    'contradiction_resolutions': stats['contradiction_resolutions'],
                    'mip_phi': round(stats['mip_phi'], 4),
                })
            progress.append({
                'id': gate_id,
                'name': gate['name'],
                'passed': passed,
                'metrics': details,
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
        """Archive old phi_history entries to DB when history exceeds max."""
        if len(self._phi_history) <= self._max_history:
            return 0

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

            self._phi_history = self._phi_history[archive_count:]
            logger.info(
                f"Phi history archived: {archived} entries written to DB, "
                f"{len(self._phi_history)} kept in memory"
            )
        except Exception as e:
            logger.debug(f"Failed to archive phi history: {e}")

        return archived

    def get_history(self, limit: int = 50) -> List[dict]:
        """Get recent phi measurement history."""
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
