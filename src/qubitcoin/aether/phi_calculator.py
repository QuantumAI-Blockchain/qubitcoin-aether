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
import time
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Phi threshold for Proof-of-Thought validity
PHI_THRESHOLD = 3.0

# ============================================================================
# MILESTONE GATES
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
        'description': 'All 4+ node types with meaningful representation',
        'check': lambda stats: all(
            stats['node_type_counts'].get(t, 0) >= 50
            for t in ('observation', 'inference', 'axiom', 'assertion')
        ),
        'requirement': 'All 4 base node types >=50 each',
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
        'requirement': '>=50K nodes + >=5 edge types present',
    },
    {
        'id': 7,
        'name': 'Analogical Reasoning',
        'description': 'Cross-domain analogies discovered',
        'check': lambda stats: (
            stats['edge_type_counts'].get('analogous_to', 0) >= 100
            and stats.get('domain_count', 0) >= 5
        ),
        'requirement': '>=100 analogous_to edges across >=5 domains',
    },
    {
        'id': 8,
        'name': 'Self-Model',
        'description': 'System builds a model of its own cognitive state',
        'check': lambda stats: stats.get('self_reflection_nodes', 0) >= 50,
        'requirement': '>=50 nodes with source: self-reflection',
    },
    {
        'id': 9,
        'name': 'Predictive Accuracy',
        'description': 'High-confidence inferences validated by subsequent evidence',
        'check': lambda stats: (
            stats['node_type_counts'].get('inference', 0) >= 1000
            and stats['edge_type_counts'].get('supports', 0) >= 2000
        ),
        'requirement': '>=1000 inference nodes with >=2000 support edges',
    },
    {
        'id': 10,
        'name': 'Creative Synthesis',
        'description': 'Novel hypotheses combining knowledge from multiple domains',
        'check': lambda stats: (
            stats.get('cross_domain_inferences', 0) >= 20
        ),
        'requirement': '>=20 cross-domain inference nodes',
    },
]


class PhiCalculator:
    """
    Computes Phi (Φ) metric for the Aether Tree knowledge graph.

    v3 formula uses information-theoretic integration (mutual information
    between graph partitions via VectorIndex embeddings), Shannon entropy
    differentiation, and redundancy penalty from near-duplicate detection.
    """

    def __init__(self, db_manager, knowledge_graph=None):
        self.db = db_manager
        self.kg = knowledge_graph
        self._cache: Dict[int, float] = {}  # block_height -> phi
        self._last_full_result: Optional[dict] = None
        self._last_computed_block: int = -1
        self._compute_interval: int = int(
            __import__('os').getenv('PHI_COMPUTE_INTERVAL', '1')
        )

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
        gates = self._check_gates(nodes, edges)
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

        return structural + mi_score + cross_flow

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

    def _check_gates(self, nodes: dict, edges: list) -> List[dict]:
        """
        Evaluate all milestone gates against current graph state.
        Uses in-memory nodes/edges only — no DB queries.  O(n + e).
        """
        node_type_counts: Dict[str, int] = {}
        for node in nodes.values():
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1

        edge_type_counts: Dict[str, int] = {}
        for edge in edges:
            etype = edge.edge_type
            edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1

        # Extended stats for Gates 7-10
        domains: set = set()
        self_reflection_nodes = 0
        cross_domain_inferences = 0
        for node in nodes.values():
            if node.domain:
                domains.add(node.domain)
            content = node.content if isinstance(node.content, dict) else {}
            if content.get('source') == 'self-reflection':
                self_reflection_nodes += 1
            if (node.node_type == 'inference'
                    and content.get('cross_domain', False)):
                cross_domain_inferences += 1

        stats = {
            'n_nodes': len(nodes),
            'n_edges': len(edges),
            'node_type_counts': node_type_counts,
            'edge_type_counts': edge_type_counts,
            'domain_count': len(domains),
            'self_reflection_nodes': self_reflection_nodes,
            'cross_domain_inferences': cross_domain_inferences,
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
