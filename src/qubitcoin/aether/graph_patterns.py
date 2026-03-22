"""
Multimodal Understanding — Transaction Graph Pattern Recognition (#51)

Recognize structural patterns in transaction/knowledge graph adjacency matrices:
- Hub detection (high degree centrality)
- Bridge detection (high betweenness centrality approximation)
- Cluster detection (dense subgraph identification)
- Chain detection (linear sequences)
- Star detection (central node with many leaves)
- Ring detection (cyclic structures)
- Power-law degree distribution detection
- Community detection via label propagation
- Graph-level feature extraction
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GraphPattern:
    """A detected structural pattern in a graph."""
    type: str           # hub, bridge, cluster, chain, star, ring
    nodes: List[int]    # Node indices involved in the pattern
    confidence: float   # 0.0 – 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'type': self.type,
            'nodes': self.nodes,
            'confidence': round(self.confidence, 4),
            'metadata': self.metadata,
        }


class GraphPatternDetector:
    """Detect structural patterns in adjacency matrices."""

    def __init__(self, hub_percentile: float = 90.0,
                 cluster_density_threshold: float = 0.5,
                 max_communities: int = 50) -> None:
        self._hub_percentile = hub_percentile
        self._cluster_density_threshold = cluster_density_threshold
        self._max_communities = max_communities

        # Stats
        self._calls: int = 0
        self._patterns_found: int = 0
        self._last_call: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_graph_patterns(self, adj_matrix: np.ndarray) -> List[GraphPattern]:
        """Detect all structural patterns in an adjacency matrix.

        Args:
            adj_matrix: Square numpy array (n x n). Non-zero = edge.

        Returns:
            List of GraphPattern objects.
        """
        self._calls += 1
        self._last_call = time.time()

        if adj_matrix.ndim != 2 or adj_matrix.shape[0] != adj_matrix.shape[1]:
            return []

        n = adj_matrix.shape[0]
        if n < 3:
            return []

        adj = adj_matrix.astype(np.float64)
        # Make symmetric for undirected analysis
        adj_sym = np.maximum(adj, adj.T)
        np.fill_diagonal(adj_sym, 0)

        degrees = np.sum(adj_sym > 0, axis=1).astype(np.float64)

        patterns: List[GraphPattern] = []
        patterns.extend(self._detect_hubs(degrees))
        patterns.extend(self._detect_bridges(adj_sym, degrees))
        patterns.extend(self._detect_clusters(adj_sym, degrees))
        patterns.extend(self._detect_chains(adj_sym, degrees))
        patterns.extend(self._detect_stars(adj_sym, degrees))
        patterns.extend(self._detect_rings(adj_sym, degrees))

        self._patterns_found += len(patterns)
        return patterns

    def extract_features(self, adj_matrix: np.ndarray) -> np.ndarray:
        """Extract a graph-level feature vector.

        Features: density, avg_clustering_coeff, avg_degree, max_degree,
                  diameter_estimate, num_components, power_law_alpha, assortativity.

        Args:
            adj_matrix: Square numpy array (n x n).

        Returns:
            1-D numpy array of 8 features.
        """
        n = adj_matrix.shape[0]
        if n < 2:
            return np.zeros(8, dtype=np.float64)

        adj = np.maximum(adj_matrix, adj_matrix.T).astype(np.float64)
        np.fill_diagonal(adj, 0)
        binary = (adj > 0).astype(np.float64)

        degrees = binary.sum(axis=1)
        num_edges = binary.sum() / 2.0
        max_edges = n * (n - 1) / 2.0

        # Density
        density = num_edges / max_edges if max_edges > 0 else 0.0

        # Average degree
        avg_degree = degrees.mean()
        max_degree = degrees.max()

        # Average clustering coefficient
        avg_cc = self._avg_clustering_coefficient(binary, degrees)

        # Diameter estimate (longest shortest path via BFS from sample nodes)
        diameter = self._estimate_diameter(binary, sample_size=min(5, n))

        # Number of connected components
        num_components = self._count_components(binary)

        # Power-law exponent approximation (alpha)
        alpha = self._estimate_power_law_alpha(degrees)

        # Assortativity (degree-degree correlation)
        assortativity = self._compute_assortativity(binary, degrees)

        return np.array([
            density, avg_cc, avg_degree, max_degree,
            diameter, num_components, alpha, assortativity,
        ], dtype=np.float64)

    def detect_communities(self, adj_matrix: np.ndarray,
                           max_iter: int = 50) -> Dict[int, int]:
        """Simple label propagation community detection.

        Args:
            adj_matrix: Square adjacency matrix.
            max_iter: Maximum iterations.

        Returns:
            Dict mapping node index to community label.
        """
        n = adj_matrix.shape[0]
        if n < 2:
            return {i: 0 for i in range(n)}

        adj = np.maximum(adj_matrix, adj_matrix.T).astype(np.float64)
        np.fill_diagonal(adj, 0)

        labels = np.arange(n)

        for _ in range(max_iter):
            order = np.random.permutation(n)
            changed = False
            for node in order:
                neighbors = np.where(adj[node] > 0)[0]
                if len(neighbors) == 0:
                    continue
                # Most common label among neighbors
                neighbor_labels = labels[neighbors]
                unique, counts = np.unique(neighbor_labels, return_counts=True)
                best_label = unique[np.argmax(counts)]
                if labels[node] != best_label:
                    labels[node] = best_label
                    changed = True
            if not changed:
                break

        # Remap labels to 0..k-1
        unique_labels = np.unique(labels)
        label_map = {old: new for new, old in enumerate(unique_labels)}
        return {i: label_map[labels[i]] for i in range(n)}

    def get_stats(self) -> dict:
        """Return runtime statistics."""
        return {
            'calls': self._calls,
            'patterns_found': self._patterns_found,
            'hub_percentile': self._hub_percentile,
            'cluster_density_threshold': self._cluster_density_threshold,
            'last_call': self._last_call,
        }

    # ------------------------------------------------------------------
    # Internal pattern detectors
    # ------------------------------------------------------------------

    def _detect_hubs(self, degrees: np.ndarray) -> List[GraphPattern]:
        """Find hub nodes with degree above the percentile threshold."""
        if len(degrees) < 3:
            return []

        threshold = np.percentile(degrees, self._hub_percentile)
        if threshold < 2:
            threshold = 2.0

        hub_indices = np.where(degrees >= threshold)[0]
        patterns: List[GraphPattern] = []

        max_deg = degrees.max()
        for idx in hub_indices:
            confidence = float(degrees[idx]) / max_deg if max_deg > 0 else 0.5
            patterns.append(GraphPattern(
                type='hub',
                nodes=[int(idx)],
                confidence=min(1.0, confidence),
                metadata={'degree': int(degrees[idx]), 'threshold': float(threshold)},
            ))

        return patterns

    def _detect_bridges(self, adj: np.ndarray,
                        degrees: np.ndarray) -> List[GraphPattern]:
        """Approximate bridge nodes using simple betweenness heuristic.

        A node is a bridge if removing it increases the number of components.
        We sample a few nodes for efficiency.
        """
        n = len(degrees)
        if n < 5:
            return []

        base_components = self._count_components(adj)
        patterns: List[GraphPattern] = []

        # Test nodes with moderate degree (not hubs, not leaves)
        median_deg = np.median(degrees)
        candidates = np.where(
            (degrees >= max(2, median_deg * 0.5)) &
            (degrees <= median_deg * 2)
        )[0]

        for idx in candidates[:20]:  # Cap at 20 tests
            # Remove node and check components
            mask = np.ones(n, dtype=bool)
            mask[idx] = False
            sub_adj = adj[np.ix_(mask, mask)]
            if sub_adj.shape[0] < 2:
                continue
            new_components = self._count_components(sub_adj)
            if new_components > base_components:
                confidence = min(1.0, (new_components - base_components) * 0.5)
                patterns.append(GraphPattern(
                    type='bridge',
                    nodes=[int(idx)],
                    confidence=confidence,
                    metadata={'components_added': new_components - base_components,
                              'degree': int(degrees[idx])},
                ))

        return patterns

    def _detect_clusters(self, adj: np.ndarray,
                         degrees: np.ndarray) -> List[GraphPattern]:
        """Find dense subgraph clusters via community detection."""
        n = adj.shape[0]
        if n < 5:
            return []

        communities = self.detect_communities(adj, max_iter=30)
        # Group nodes by community
        comm_nodes: Dict[int, List[int]] = {}
        for node, comm in communities.items():
            comm_nodes.setdefault(comm, []).append(node)

        patterns: List[GraphPattern] = []
        for comm_id, nodes in comm_nodes.items():
            if len(nodes) < 3:
                continue
            # Compute internal density
            indices = np.array(nodes)
            sub_adj = adj[np.ix_(indices, indices)]
            internal_edges = np.sum(sub_adj > 0) / 2.0
            max_internal = len(nodes) * (len(nodes) - 1) / 2.0
            density = internal_edges / max_internal if max_internal > 0 else 0.0

            if density >= self._cluster_density_threshold:
                patterns.append(GraphPattern(
                    type='cluster',
                    nodes=[int(x) for x in nodes],
                    confidence=min(1.0, density),
                    metadata={'density': float(density),
                              'size': len(nodes),
                              'internal_edges': int(internal_edges)},
                ))

        return patterns[:self._max_communities]

    def _detect_chains(self, adj: np.ndarray,
                       degrees: np.ndarray) -> List[GraphPattern]:
        """Detect linear chain structures (sequences of degree-2 nodes)."""
        n = len(degrees)
        if n < 4:
            return []

        # Nodes with exactly degree 2 form chains
        chain_nodes = np.where(degrees == 2)[0]
        if len(chain_nodes) < 3:
            return []

        # BFS from chain nodes to find connected sequences
        visited = set()
        patterns: List[GraphPattern] = []
        chain_set = set(chain_nodes.tolist())

        for start in chain_nodes:
            if start in visited:
                continue
            chain: List[int] = [int(start)]
            visited.add(start)
            # Extend in both directions
            for _ in range(n):
                current = chain[-1]
                neighbors = np.where(adj[current] > 0)[0]
                extended = False
                for nb in neighbors:
                    if nb not in visited and int(nb) in chain_set:
                        chain.append(int(nb))
                        visited.add(nb)
                        extended = True
                        break
                if not extended:
                    break

            if len(chain) >= 3:
                confidence = min(1.0, len(chain) / 10.0)
                patterns.append(GraphPattern(
                    type='chain',
                    nodes=chain,
                    confidence=confidence,
                    metadata={'length': len(chain)},
                ))

        return patterns[:10]  # Max 10 chains

    def _detect_stars(self, adj: np.ndarray,
                      degrees: np.ndarray) -> List[GraphPattern]:
        """Detect star patterns (central node connected to many leaves)."""
        n = len(degrees)
        if n < 4:
            return []

        patterns: List[GraphPattern] = []
        # High-degree nodes whose neighbors are mostly leaves
        threshold = max(3, np.mean(degrees) + np.std(degrees))

        for idx in np.where(degrees >= threshold)[0]:
            neighbors = np.where(adj[idx] > 0)[0]
            leaf_count = sum(1 for nb in neighbors if degrees[nb] <= 2)
            leaf_ratio = leaf_count / len(neighbors) if len(neighbors) > 0 else 0.0

            if leaf_ratio >= 0.6 and len(neighbors) >= 3:
                all_nodes = [int(idx)] + [int(nb) for nb in neighbors]
                confidence = min(1.0, leaf_ratio * (len(neighbors) / 5.0))
                patterns.append(GraphPattern(
                    type='star',
                    nodes=all_nodes,
                    confidence=min(1.0, confidence),
                    metadata={'center': int(idx), 'leaves': leaf_count,
                              'leaf_ratio': float(leaf_ratio)},
                ))

        return patterns[:10]

    def _detect_rings(self, adj: np.ndarray,
                      degrees: np.ndarray) -> List[GraphPattern]:
        """Detect ring/cycle structures (closed loops of degree-2 nodes)."""
        n = len(degrees)
        if n < 4:
            return []

        # Look for small cycles using BFS from each node
        patterns: List[GraphPattern] = []
        found_cycles: set = set()

        for start in range(min(n, 50)):  # Cap exploration
            if degrees[start] < 2:
                continue
            # BFS looking for cycles back to start
            cycle = self._find_cycle_from(adj, start, max_len=8)
            if cycle and len(cycle) >= 3:
                key = tuple(sorted(cycle))
                if key not in found_cycles:
                    found_cycles.add(key)
                    confidence = min(1.0, 0.5 + 0.1 * len(cycle))
                    patterns.append(GraphPattern(
                        type='ring',
                        nodes=cycle,
                        confidence=confidence,
                        metadata={'length': len(cycle)},
                    ))

        return patterns[:10]

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def _find_cycle_from(self, adj: np.ndarray, start: int,
                         max_len: int = 8) -> Optional[List[int]]:
        """Find a simple cycle starting and ending at `start`."""
        n = adj.shape[0]
        # DFS with path tracking
        stack: List[Tuple[int, List[int]]] = [(start, [start])]

        while stack:
            current, path = stack.pop()
            if len(path) > max_len:
                continue
            neighbors = np.where(adj[current] > 0)[0]
            for nb in neighbors:
                nb_int = int(nb)
                if nb_int == start and len(path) >= 3:
                    return path
                if nb_int not in path and len(path) < max_len:
                    stack.append((nb_int, path + [nb_int]))

        return None

    @staticmethod
    def _count_components(adj: np.ndarray) -> int:
        """Count connected components via BFS."""
        n = adj.shape[0]
        visited = np.zeros(n, dtype=bool)
        components = 0

        for i in range(n):
            if visited[i]:
                continue
            components += 1
            # BFS
            queue = [i]
            visited[i] = True
            while queue:
                node = queue.pop(0)
                neighbors = np.where(adj[node] > 0)[0]
                for nb in neighbors:
                    if not visited[nb]:
                        visited[nb] = True
                        queue.append(nb)

        return components

    @staticmethod
    def _avg_clustering_coefficient(binary: np.ndarray,
                                    degrees: np.ndarray) -> float:
        """Compute average local clustering coefficient."""
        n = len(degrees)
        cc_sum = 0.0
        count = 0

        for i in range(n):
            k = int(degrees[i])
            if k < 2:
                continue
            neighbors = np.where(binary[i] > 0)[0]
            # Count edges among neighbors
            sub = binary[np.ix_(neighbors, neighbors)]
            triangles = np.sum(sub) / 2.0
            possible = k * (k - 1) / 2.0
            cc_sum += triangles / possible
            count += 1

        return cc_sum / count if count > 0 else 0.0

    @staticmethod
    def _estimate_diameter(binary: np.ndarray, sample_size: int = 5) -> float:
        """Estimate graph diameter via BFS from sample nodes."""
        n = binary.shape[0]
        if n < 2:
            return 0.0

        max_dist = 0
        sample = np.random.choice(n, size=min(sample_size, n), replace=False)

        for start in sample:
            dist = np.full(n, -1)
            dist[start] = 0
            queue = [start]
            while queue:
                node = queue.pop(0)
                neighbors = np.where(binary[node] > 0)[0]
                for nb in neighbors:
                    if dist[nb] == -1:
                        dist[nb] = dist[node] + 1
                        queue.append(nb)
            reachable = dist[dist >= 0]
            if len(reachable) > 0:
                max_dist = max(max_dist, int(reachable.max()))

        return float(max_dist)

    @staticmethod
    def _estimate_power_law_alpha(degrees: np.ndarray) -> float:
        """Estimate power-law exponent alpha via MLE."""
        pos = degrees[degrees > 0]
        if len(pos) < 5:
            return 0.0

        x_min = pos.min()
        if x_min < 1:
            x_min = 1.0

        # MLE: alpha = 1 + n / sum(ln(x/x_min))
        log_ratios = np.log(pos / x_min)
        log_sum = np.sum(log_ratios)
        if log_sum < 1e-12:
            return 0.0

        alpha = 1.0 + len(pos) / log_sum
        return float(alpha)

    @staticmethod
    def _compute_assortativity(binary: np.ndarray,
                               degrees: np.ndarray) -> float:
        """Compute degree assortativity coefficient."""
        edges_i, edges_j = np.where(np.triu(binary, k=1) > 0)
        m = len(edges_i)
        if m < 2:
            return 0.0

        di = degrees[edges_i]
        dj = degrees[edges_j]

        mean_d = (di.mean() + dj.mean()) / 2.0
        if mean_d < 1e-12:
            return 0.0

        num = np.sum((di - mean_d) * (dj - mean_d))
        denom = np.sqrt(np.sum((di - mean_d) ** 2) * np.sum((dj - mean_d) ** 2))

        if denom < 1e-12:
            return 0.0

        return float(num / denom)
