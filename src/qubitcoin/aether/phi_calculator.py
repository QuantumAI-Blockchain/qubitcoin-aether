"""
Phi Calculator - Integrated Information Theory (IIT) Metric
Computes Phi (Φ) as a measure of consciousness/integration in the knowledge graph.

Based on Giulio Tononi's Integrated Information Theory:
- Φ measures how much information a system generates above and beyond its parts
- Higher Φ = more integrated/conscious system
- Used in Proof-of-Thought to validate that knowledge integration is meaningful

v2 (PHI_FORK_HEIGHT): Replaced sqrt(n/500) maturity with log2(1+n/50000),
removed confidence multiplier, added 6 milestone gates that cap Phi until
the system demonstrates genuine cognitive diversity.
"""
import math
import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Phi threshold for Proof-of-Thought validity
PHI_THRESHOLD = 3.0

# ============================================================================
# MILESTONE GATES (v2)
# Each passed gate unlocks +0.5 Phi ceiling.  Gates require genuine system
# evolution: diverse node types, diverse edge types, self-correction, and
# emergent scale.
# ============================================================================
MILESTONE_GATES: List[dict] = [
    {
        'id': 1,
        'name': 'Knowledge Foundation',
        'description': 'Build a substantial knowledge base',
        'check': lambda stats: stats['n_nodes'] >= 1000 and stats['n_edges'] >= 500,
        'requirement': '>=1000 nodes, >=500 edges',
    },
    {
        'id': 2,
        'name': 'Reasoning Activity',
        'description': 'Active inference and derivation in the graph',
        'check': lambda stats: (
            stats['node_type_counts'].get('inference', 0) >= 500
            and stats['edge_type_counts'].get('derives', 0) >= 200
        ),
        'requirement': '>=500 inference nodes, >=200 derives edges',
    },
    {
        'id': 3,
        'name': 'Node Type Diversity',
        'description': 'All 4 node types with meaningful representation',
        'check': lambda stats: all(
            stats['node_type_counts'].get(t, 0) >= 50
            for t in ('observation', 'inference', 'axiom', 'assertion')
        ),
        'requirement': 'All 4 node types (obs/inf/axiom/assertion) >=50 each',
    },
    {
        'id': 4,
        'name': 'Edge Type Diversity',
        'description': 'Multiple relationship types in use',
        'check': lambda stats: sum(
            1 for v in stats['edge_type_counts'].values() if v >= 10
        ) >= 3,
        'requirement': '>=3 edge types with >=10 each',
    },
    {
        'id': 5,
        'name': 'Self-Correction',
        'description': 'System can identify and record contradictions',
        'check': lambda stats: stats['edge_type_counts'].get('contradicts', 0) >= 10,
        'requirement': '>=10 contradicts edges',
    },
    {
        'id': 6,
        'name': 'Emergent Complexity',
        'description': 'Large-scale graph with full edge diversity',
        'check': lambda stats: (
            stats['n_nodes'] >= 50_000
            and sum(1 for v in stats['edge_type_counts'].values() if v >= 1) >= 5
        ),
        'requirement': '>=50K nodes + all 5 edge types present',
    },
]


class PhiCalculator:
    """
    Computes Phi (Φ) metric for the Aether Tree knowledge graph.
    Measures integration and differentiation of the knowledge structure.
    """

    def __init__(self, db_manager, knowledge_graph=None):
        self.db = db_manager
        self.kg = knowledge_graph
        self._cache: Dict[int, float] = {}  # block_height -> phi

    def compute_phi(self, block_height: int = 0) -> dict:
        """
        Compute Phi for the current state of the knowledge graph.

        Pre-fork (v1): original formula with sqrt(n/500) maturity + confidence.
        Post-fork (v2): log2(1+n/50000) maturity + milestone gate ceiling.

        Returns:
            Dict with phi_value, integration, differentiation, and breakdown
        """
        if not self.kg or not self.kg.nodes:
            return self._empty_result(block_height)

        # Branch on fork height
        if block_height >= Config.PHI_FORK_HEIGHT:
            return self._compute_phi_v2(block_height)

        return self._compute_phi_v1(block_height)

    # ========================================================================
    # v1 — original formula (pre-fork, unchanged)
    # ========================================================================

    def _compute_phi_v1(self, block_height: int) -> dict:
        """Original Phi formula preserved for pre-fork blocks."""
        nodes = self.kg.nodes
        edges = self.kg.edges
        n_nodes = len(nodes)
        n_edges = len(edges)

        integration = self._compute_integration(nodes, edges, n_nodes)
        differentiation = self._compute_differentiation(nodes)

        max_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
        connectivity = min(1.0, n_edges / max_edges) if max_edges > 0 else 0

        avg_conf = sum(n.confidence for n in nodes.values()) / n_nodes

        raw_phi = integration * differentiation * (1.0 + connectivity)
        phi = raw_phi * (0.5 + avg_conf)
        if n_nodes > 1:
            phi *= math.sqrt(n_nodes / 500.0)

        result = {
            'phi_value': round(phi, 6),
            'phi_threshold': PHI_THRESHOLD,
            'above_threshold': phi >= PHI_THRESHOLD,
            'integration_score': round(integration, 6),
            'differentiation_score': round(differentiation, 6),
            'connectivity': round(connectivity, 6),
            'avg_confidence': round(avg_conf, 4),
            'num_nodes': n_nodes,
            'num_edges': n_edges,
            'block_height': block_height,
            'timestamp': time.time(),
        }

        self._store_measurement(result)
        return result

    # ========================================================================
    # v2 — new formula (post-fork)
    # ========================================================================

    def _compute_phi_v2(self, block_height: int) -> dict:
        """
        Phi v2: stricter formula with milestone gate ceiling.

        Formula:
            maturity  = log2(1 + n_nodes / 50000)
            raw_phi   = integration * differentiation * (1 + connectivity) * maturity
            phi       = min(raw_phi, gate_ceiling)

        Gate ceiling starts at 0 and increases by 0.5 for each passed gate
        (6 gates = max ceiling of 3.0).
        """
        nodes = self.kg.nodes
        edges = self.kg.edges
        n_nodes = len(nodes)
        n_edges = len(edges)

        integration = self._compute_integration(nodes, edges, n_nodes)
        differentiation = self._compute_differentiation(nodes)

        max_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
        connectivity = min(1.0, n_edges / max_edges) if max_edges > 0 else 0

        # v2 maturity: much slower growth than v1
        maturity = math.log2(1.0 + n_nodes / 50_000.0)

        raw_phi = integration * differentiation * (1.0 + connectivity) * maturity

        # Check milestone gates
        gates = self._check_gates(nodes, edges)
        gates_passed = sum(1 for g in gates if g['passed'])
        gate_ceiling = gates_passed * 0.5

        phi = min(raw_phi, gate_ceiling)

        result = {
            'phi_value': round(phi, 6),
            'phi_raw': round(raw_phi, 6),
            'phi_threshold': PHI_THRESHOLD,
            'above_threshold': phi >= PHI_THRESHOLD,
            'integration_score': round(integration, 6),
            'differentiation_score': round(differentiation, 6),
            'connectivity': round(connectivity, 6),
            'maturity': round(maturity, 6),
            'num_nodes': n_nodes,
            'num_edges': n_edges,
            'block_height': block_height,
            'timestamp': time.time(),
            'phi_version': 2,
            'gates_passed': gates_passed,
            'gates_total': len(MILESTONE_GATES),
            'gate_ceiling': gate_ceiling,
            'gates': gates,
        }

        self._store_measurement(result)
        return result

    def _check_gates(self, nodes: dict, edges: list) -> List[dict]:
        """
        Evaluate all milestone gates against current graph state.
        Uses in-memory nodes/edges only — no DB queries.  O(n + e).
        """
        # Build stats dict in a single pass
        node_type_counts: Dict[str, int] = {}
        for node in nodes.values():
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1

        edge_type_counts: Dict[str, int] = {}
        for edge in edges:
            etype = edge.edge_type
            edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1

        stats = {
            'n_nodes': len(nodes),
            'n_edges': len(edges),
            'node_type_counts': node_type_counts,
            'edge_type_counts': edge_type_counts,
        }

        results = []
        for gate in MILESTONE_GATES:
            passed = gate['check'](stats)
            results.append({
                'id': gate['id'],
                'name': gate['name'],
                'description': gate['description'],
                'requirement': gate['requirement'],
                'passed': passed,
            })
        return results

    # ========================================================================
    # Shared helpers
    # ========================================================================

    def _compute_integration(self, nodes: dict, edges: list, n_nodes: int) -> float:
        """
        Compute integration score based on connected components and
        information flow across the minimum information partition (MIP).
        """
        if n_nodes <= 1:
            return 0.0

        # Build adjacency for connected component analysis
        adj: Dict[int, set] = {nid: set() for nid in nodes}
        for edge in edges:
            if edge.from_node_id in adj and edge.to_node_id in adj:
                adj[edge.from_node_id].add(edge.to_node_id)
                adj[edge.to_node_id].add(edge.from_node_id)

        # Find connected components
        visited = set()
        components = []

        def _bfs(start):
            comp = set()
            queue = [start]
            while queue:
                n = queue.pop(0)
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

        if len(components) == 1:
            # Fully connected: high integration
            # Score based on average path length (approximation)
            avg_degree = sum(len(adj[nid]) for nid in nodes) / n_nodes if n_nodes > 0 else 0
            integration = min(5.0, avg_degree)
        else:
            # Multiple components: integration is reduced
            largest = max(len(c) for c in components)
            integration = (largest / n_nodes) * 2.0

        # Cross-partition information flow
        # Approximate: edges between high-confidence nodes add integration
        cross_flow = 0.0
        for edge in edges:
            fn = nodes.get(edge.from_node_id)
            tn = nodes.get(edge.to_node_id)
            if fn and tn:
                cross_flow += fn.confidence * tn.confidence * edge.weight
        if edges:
            cross_flow /= len(edges)

        return integration + cross_flow

    def _compute_differentiation(self, nodes: dict) -> float:
        """
        Compute differentiation score using Shannon entropy over node types
        and confidence distribution bins.
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

        # Combined differentiation
        return type_entropy + conf_entropy * 0.5

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
            'phi_threshold': PHI_THRESHOLD,
            'above_threshold': False,
            'integration_score': 0.0,
            'differentiation_score': 0.0,
            'connectivity': 0.0,
            'avg_confidence': 0.0,
            'num_nodes': 0,
            'num_edges': 0,
            'block_height': block_height,
            'timestamp': time.time(),
        }

    def downsample_phi_measurements(self, retain_days: int = None) -> dict:
        """
        Downsample old phi measurements to reduce DB bloat.

        - Rows within retain_days: kept as-is (per-block granularity)
        - Rows older than retain_days but < 30 days: collapsed to hourly averages
        - Rows older than 30 days: collapsed to daily averages

        Returns:
            Dict with counts of rows downsampled and deleted.
        """
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
                # --- Phase 1: Collapse retain_days..30 days into hourly averages ---
                hourly_rows = session.execute(
                    text("""
                        SELECT
                            date_trunc('hour', created_at) AS hour_bucket,
                            AVG(phi_value) AS avg_phi,
                            AVG(phi_threshold) AS avg_threshold,
                            AVG(integration_score) AS avg_int,
                            AVG(differentiation_score) AS avg_diff,
                            AVG(num_nodes) AS avg_nodes,
                            AVG(num_edges) AS avg_edges,
                            MIN(block_height) AS min_block,
                            MAX(block_height) AS max_block,
                            COUNT(*) AS cnt
                        FROM phi_measurements
                        WHERE created_at < :retain_cutoff
                          AND created_at >= :daily_cutoff
                        GROUP BY date_trunc('hour', created_at)
                        HAVING COUNT(*) > 1
                        ORDER BY hour_bucket
                    """),
                    {'retain_cutoff': retain_cutoff, 'daily_cutoff': daily_cutoff}
                )
                hourly_data = list(hourly_rows)

                for row in hourly_data:
                    # Insert hourly summary row
                    session.execute(
                        text("""
                            INSERT INTO phi_measurements
                            (phi_value, phi_threshold, integration_score,
                             differentiation_score, num_nodes, num_edges, block_height)
                            VALUES (:phi, :threshold, :int_score, :diff_score,
                                    :nodes, :edges, :bh)
                        """),
                        {
                            'phi': float(row[1]),
                            'threshold': float(row[2]),
                            'int_score': float(row[3]),
                            'diff_score': float(row[4]),
                            'nodes': int(row[5]),
                            'edges': int(row[6]),
                            'bh': int(row[8]),  # max block_height as representative
                        }
                    )
                    stats['hourly_created'] += 1

                # Delete original per-block rows in the hourly window (keep the new summaries)
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

                # --- Phase 2: Collapse > 30 days into daily averages ---
                daily_rows = session.execute(
                    text("""
                        SELECT
                            date_trunc('day', created_at) AS day_bucket,
                            AVG(phi_value) AS avg_phi,
                            AVG(phi_threshold) AS avg_threshold,
                            AVG(integration_score) AS avg_int,
                            AVG(differentiation_score) AS avg_diff,
                            AVG(num_nodes) AS avg_nodes,
                            AVG(num_edges) AS avg_edges,
                            MIN(block_height) AS min_block,
                            MAX(block_height) AS max_block,
                            COUNT(*) AS cnt
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
                            'phi': float(row[1]),
                            'threshold': float(row[2]),
                            'int_score': float(row[3]),
                            'diff_score': float(row[4]),
                            'nodes': int(row[5]),
                            'edges': int(row[6]),
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
                    f"created {stats['hourly_created']} hourly + {stats['daily_created']} daily summaries"
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
