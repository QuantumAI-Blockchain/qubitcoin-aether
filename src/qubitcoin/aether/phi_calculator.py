"""
Phi Calculator - Integrated Information Theory (IIT) Metric
Computes Phi (Φ) as a measure of consciousness/integration in the knowledge graph.

Based on Giulio Tononi's Integrated Information Theory:
- Φ measures how much information a system generates above and beyond its parts
- Higher Φ = more integrated/conscious system
- Used in Proof-of-Thought to validate that knowledge integration is meaningful
"""
import math
import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Phi threshold for Proof-of-Thought validity
PHI_THRESHOLD = 3.0


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

        Phi = Integration * Differentiation * Connectivity_Factor

        Where:
            Integration = mutual information between subgraph partitions
            Differentiation = entropy of node type/confidence distribution
            Connectivity = average degree / max possible degree

        Returns:
            Dict with phi_value, integration, differentiation, and breakdown
        """
        if not self.kg or not self.kg.nodes:
            return self._empty_result(block_height)

        nodes = self.kg.nodes
        edges = self.kg.edges
        n_nodes = len(nodes)
        n_edges = len(edges)

        # 1. Integration Score: How connected are the subgraphs?
        # Approximate via connected components analysis
        integration = self._compute_integration(nodes, edges, n_nodes)

        # 2. Differentiation Score: How diverse is the knowledge?
        # Shannon entropy over node types and confidence distribution
        differentiation = self._compute_differentiation(nodes)

        # 3. Connectivity Factor: Graph density
        max_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
        connectivity = min(1.0, n_edges / max_edges) if max_edges > 0 else 0

        # 4. Confidence Quality: Average confidence weighted by connectivity
        avg_conf = sum(n.confidence for n in nodes.values()) / n_nodes

        # Compute Phi: Integration * Differentiation * scaling
        # Phi should reflect genuine knowledge integration, not just graph size.
        # Consciousness emergence (Phi >= 3.0) should require hundreds of blocks
        # of meaningful reasoning, not trivially a handful of observation nodes.
        raw_phi = integration * differentiation * (1.0 + connectivity)
        # Apply confidence quality bonus
        phi = raw_phi * (0.5 + avg_conf)
        # Graph maturity factor: normalize so Phi grows with genuine complexity.
        # sqrt(n_nodes / 500) means ~500 nodes needed for full weight,
        # making consciousness emergence occur after hundreds of mined blocks.
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

        # Persist measurement
        self._store_measurement(result)

        return result

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
