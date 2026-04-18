"""
IIT (Integrated Information Theory) Phi Approximation — Item #34

Proper IIT approximation using TPM-based partition search:
- Build Transition Probability Matrix from KG state transitions
- Greedy/heuristic bipartition search for Minimum Information Partition (MIP)
- Earth Mover's Distance approximation for cause/effect repertoire distance
- Supports systems of 4-16 nodes (subsamples larger systems)

V2 Changes:
- Node selection: BFS from highest-degree node to get connected subgraph
  (fixes near-zero phi_micro from sparse random selection)
- Multiple seed samples with median aggregation
- Influence weights normalized per-column with Laplace smoothing
"""
import time
from collections import deque
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Phi threshold constants
MAX_SYSTEM_SIZE = 16
MIN_SYSTEM_SIZE = 4
DEFAULT_WINDOW = 500
N_SAMPLES = 5  # Number of seed samples for median aggregation


class IITApproximator:
    """Computes IIT Phi via TPM bipartition search with EMD approximation."""

    def __init__(self, max_nodes: int = MAX_SYSTEM_SIZE,
                 window: int = DEFAULT_WINDOW) -> None:
        self._max_nodes = max_nodes
        self._window = window
        self._phi_history: List[float] = []
        self._mip_history: List[Tuple[float, Tuple]] = []
        self._computations: int = 0
        self._total_time: float = 0.0
        self._last_phi: float = 0.0
        self._last_tpm: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_tpm_from_kg(self, knowledge_graph: Any,
                          window: Optional[int] = None,
                          seed_idx: int = 0) -> np.ndarray:
        """Build a Transition Probability Matrix from a connected KG subgraph.

        Selects up to max_nodes by BFS from a high-degree seed node,
        ensuring the subsystem has real edge connections (not sparse randoms).

        Args:
            knowledge_graph: KnowledgeGraph instance with .nodes, ._adj_out, ._adj_in.
            window: How many recent source_blocks to consider for recency filter.
            seed_idx: Which seed rank to start BFS from (0=highest degree, 1=second, etc.)

        Returns:
            np.ndarray of shape (2^n, n) — conditional TPM in state-by-node format.
        """
        window = window or self._window

        # Get adjacency dicts for connectivity-based selection
        adj_out = getattr(knowledge_graph, '_adj_out', {})
        adj_in = getattr(knowledge_graph, '_adj_in', {})

        # Compute degree for each node that exists in the graph
        all_node_ids = set()
        try:
            all_node_ids = set(knowledge_graph.nodes.keys())
        except RuntimeError:
            try:
                all_node_ids = set(list(knowledge_graph.nodes.keys()))
            except Exception:
                return np.eye(2)[:, :1]

        if len(all_node_ids) < MIN_SYSTEM_SIZE:
            return np.eye(2)[:, :1]

        # Score nodes by degree (in + out)
        degree: Dict[int, int] = {}
        for nid in all_node_ids:
            d = len(adj_out.get(nid, [])) + len(adj_in.get(nid, []))
            if d > 0:
                degree[nid] = d

        if len(degree) < MIN_SYSTEM_SIZE:
            # Fallback: use any nodes
            for nid in all_node_ids:
                degree.setdefault(nid, 0)

        # Sort by degree descending, pick seed
        sorted_by_degree = sorted(degree.keys(), key=lambda x: degree[x], reverse=True)
        seed_rank = min(seed_idx, len(sorted_by_degree) - 1)
        seed_node = sorted_by_degree[seed_rank]

        # BFS from seed to get connected subgraph of max_nodes
        selected_ids: List[int] = []
        visited: set = set()
        queue: deque = deque([seed_node])
        visited.add(seed_node)

        while queue and len(selected_ids) < self._max_nodes:
            nid = queue.popleft()
            if nid in all_node_ids:
                selected_ids.append(nid)

            # Add neighbors (both directions) sorted by degree for quality
            neighbors = set()
            for edge in adj_out.get(nid, []):
                tid = getattr(edge, 'to_node_id', None)
                if tid and tid not in visited and tid in all_node_ids:
                    neighbors.add(tid)
            for edge in adj_in.get(nid, []):
                fid = getattr(edge, 'from_node_id', None)
                if fid and fid not in visited and fid in all_node_ids:
                    neighbors.add(fid)

            # Prioritize high-degree neighbors
            for nb in sorted(neighbors, key=lambda x: degree.get(x, 0), reverse=True):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)

        n = len(selected_ids)
        if n < MIN_SYSTEM_SIZE:
            # Pad with random nodes if BFS didn't find enough
            remaining = [nid for nid in all_node_ids if nid not in visited]
            for nid in remaining[:MIN_SYSTEM_SIZE - n]:
                selected_ids.append(nid)
            n = len(selected_ids)

        id_to_idx = {nid: i for i, nid in enumerate(selected_ids)}

        # Build influence matrix from actual edges
        influence = np.zeros((n, n))
        edge_count = 0
        for i, nid in enumerate(selected_ids):
            for edge in adj_out.get(nid, []):
                tid = getattr(edge, 'to_node_id', None)
                if tid in id_to_idx:
                    weight = getattr(edge, 'weight', 0.5)
                    j = id_to_idx[tid]
                    influence[i, j] += float(weight)
                    edge_count += 1

        # Also count incoming edges (bidirectional influence)
        for i, nid in enumerate(selected_ids):
            for edge in adj_in.get(nid, []):
                fid = getattr(edge, 'from_node_id', None)
                if fid in id_to_idx:
                    weight = getattr(edge, 'weight', 0.5)
                    j = id_to_idx[fid]
                    # Incoming edges have weaker influence (0.3x)
                    influence[j, i] += float(weight) * 0.3
                    edge_count += 1

        # Normalize influence per target column with Laplace smoothing
        # This prevents all-zero columns which make TPM trivial
        for j in range(n):
            col_sum = influence[:, j].sum()
            if col_sum > 0:
                influence[:, j] = influence[:, j] / col_sum
            else:
                # Self-influence if no connections
                influence[j, j] = 0.5

        # Build TPM: for each possible state, compute next-state probabilities
        n_states = 2 ** n
        tpm = np.full((n_states, n), 0.5)

        for state_idx in range(n_states):
            state = np.array([(state_idx >> i) & 1 for i in range(n)], dtype=np.float64)
            for j in range(n):
                # Probability node j is ON in next state given current state
                input_signal = np.dot(state, influence[:, j])
                # Sigmoid activation with steeper slope for better differentiation
                prob = 1.0 / (1.0 + np.exp(-6.0 * (input_signal - 0.4)))
                tpm[state_idx, j] = np.clip(prob, 0.01, 0.99)

        self._last_tpm = tpm
        return tpm

    def compute_phi_from_kg(self, knowledge_graph: Any) -> float:
        """Compute phi_micro using multiple seed samples and median aggregation.

        Takes N_SAMPLES different seed nodes, builds TPM from each connected
        subgraph, computes phi, and returns the median. This is more robust
        than a single sample.

        Args:
            knowledge_graph: KnowledgeGraph instance.

        Returns:
            Median phi value across samples.
        """
        start = time.monotonic()
        phi_values = []

        for seed_idx in range(N_SAMPLES):
            try:
                tpm = self.build_tpm_from_kg(knowledge_graph, seed_idx=seed_idx)
                if tpm.shape[1] < MIN_SYSTEM_SIZE:
                    continue
                phi = self._compute_phi_internal(tpm)
                phi_values.append(phi)
            except Exception as e:
                logger.debug(f"IIT sample {seed_idx} failed: {e}")
                continue

        self._total_time += time.monotonic() - start
        self._computations += 1

        if not phi_values:
            self._last_phi = 0.0
            return 0.0

        median_phi = float(np.median(phi_values))
        self._last_phi = median_phi
        self._phi_history.append(median_phi)
        return median_phi

    def compute_phi(self, tpm: np.ndarray) -> float:
        """Compute Phi (integrated information) for a given TPM.

        Uses greedy bipartition search to find the MIP and computes
        information loss across all bipartitions.

        Args:
            tpm: Transition Probability Matrix, shape (2^n, n).

        Returns:
            Phi value (float >= 0). Higher = more integrated.
        """
        start = time.monotonic()
        try:
            phi = self._compute_phi_internal(tpm)
            self._phi_history.append(phi)
            self._last_phi = phi
            self._computations += 1
            return phi
        finally:
            self._total_time += time.monotonic() - start

    def _compute_phi_internal(self, tpm: np.ndarray) -> float:
        """Internal phi computation without stats tracking."""
        phi, _ = self.find_mip(tpm)
        return phi

    def find_mip(self, tpm: np.ndarray) -> Tuple[float, Tuple]:
        """Find the Minimum Information Partition.

        Tries bipartitions of system nodes and returns the one with
        minimum information loss (= Phi).

        Args:
            tpm: Transition Probability Matrix, shape (2^n, n).

        Returns:
            (phi_value, (partition_A_indices, partition_B_indices))
        """
        n_states, n = tpm.shape
        if n < 2:
            return 0.0, (tuple(range(n)), ())

        # For small n (<=8), try all bipartitions; for larger, use greedy
        if n <= 8:
            return self._exhaustive_mip(tpm, n)
        else:
            return self._greedy_mip(tpm, n)

    def _exhaustive_mip(self, tpm: np.ndarray, n: int) -> Tuple[float, Tuple]:
        """Try all non-trivial bipartitions for small systems."""
        min_phi = float('inf')
        best_partition = (tuple(range(n)), ())

        indices = list(range(n))
        # All bipartitions: pick 1..n-1 elements for partition A
        for size_a in range(1, n):
            for combo in combinations(indices, size_a):
                part_a = combo
                part_b = tuple(i for i in indices if i not in combo)
                info_loss = self._compute_information_loss(tpm, part_a, part_b)
                if info_loss < min_phi:
                    min_phi = info_loss
                    best_partition = (part_a, part_b)

        self._mip_history.append((min_phi, best_partition))
        return min_phi, best_partition

    def _greedy_mip(self, tpm: np.ndarray, n: int) -> Tuple[float, Tuple]:
        """Greedy heuristic bipartition search for larger systems.

        Starts with a random bisection, then iteratively swaps nodes
        between partitions to minimize information loss.
        """
        indices = list(range(n))
        rng = np.random.default_rng()
        rng.shuffle(indices)
        half = n // 2

        best_a = tuple(sorted(indices[:half]))
        best_b = tuple(sorted(indices[half:]))
        best_loss = self._compute_information_loss(tpm, best_a, best_b)

        # Greedy swap: try moving each node to the other partition
        improved = True
        max_iters = n * 3
        iters = 0
        while improved and iters < max_iters:
            improved = False
            iters += 1
            for i in range(n):
                if i in best_a and len(best_a) > 1:
                    new_a = tuple(x for x in best_a if x != i)
                    new_b = tuple(sorted(best_b + (i,)))
                elif i in best_b and len(best_b) > 1:
                    new_b = tuple(x for x in best_b if x != i)
                    new_a = tuple(sorted(best_a + (i,)))
                else:
                    continue
                loss = self._compute_information_loss(tpm, new_a, new_b)
                if loss < best_loss:
                    best_loss = loss
                    best_a = new_a
                    best_b = new_b
                    improved = True

        self._mip_history.append((best_loss, (best_a, best_b)))
        return best_loss, (best_a, best_b)

    def _compute_information_loss(self, tpm: np.ndarray,
                                  part_a: Tuple[int, ...],
                                  part_b: Tuple[int, ...]) -> float:
        """Compute information loss when cutting the system at the partition.

        Approximates the EMD between the whole-system cause/effect
        repertoire and the product of the partitioned repertoires.

        Args:
            tpm: Full system TPM, shape (2^n, n).
            part_a: Indices of partition A.
            part_b: Indices of partition B.

        Returns:
            Information loss (float >= 0).
        """
        n = tpm.shape[1]
        if not part_a or not part_b:
            return float('inf')

        # Marginalize TPM for each partition
        tpm_a = tpm[:, list(part_a)]
        tpm_b = tpm[:, list(part_b)]

        # Compute unconstrained (whole system) cause repertoire
        # Uniform prior over states
        n_states = tpm.shape[0]
        prior = np.ones(n_states) / n_states

        # Whole-system average transition probabilities
        whole_avg = prior @ tpm  # shape (n,)

        # Partitioned average: independent product
        part_avg_a = prior @ tpm_a  # shape (len(part_a),)
        part_avg_b = prior @ tpm_b  # shape (len(part_b),)

        # Reconstruct full-system vector from independent partitions
        partitioned_avg = np.zeros(n)
        for i, idx in enumerate(part_a):
            partitioned_avg[idx] = part_avg_a[i]
        for i, idx in enumerate(part_b):
            partitioned_avg[idx] = part_avg_b[i]

        # EMD approximation: L1 distance between whole and partitioned repertoires
        cause_loss = np.sum(np.abs(whole_avg - partitioned_avg))

        # Effect repertoire: how well we can predict future given partition
        # Use conditional entropy approximation
        effect_loss = self._effect_repertoire_distance(tpm, part_a, part_b)

        return cause_loss + effect_loss

    def _effect_repertoire_distance(self, tpm: np.ndarray,
                                    part_a: Tuple[int, ...],
                                    part_b: Tuple[int, ...]) -> float:
        """Approximate effect repertoire distance using conditional entropy.

        Measures how much predicting the future of one partition depends
        on the other partition's current state.
        """
        n_states = tpm.shape[0]
        n = tpm.shape[1]

        # Sample representative states
        n_samples = min(n_states, 64)
        rng = np.random.default_rng(42)
        sample_indices = rng.choice(n_states, size=n_samples, replace=n_samples > n_states)

        total_divergence = 0.0
        for idx in sample_indices:
            state = np.array([(idx >> i) & 1 for i in range(n)], dtype=np.float64)

            # Full system transition for this state
            full_trans = tpm[idx]

            # Partition A marginal: average over all B states
            a_marginal = np.zeros(len(part_a))
            b_marginal = np.zeros(len(part_b))
            count = 0
            for s in range(min(n_states, 32)):
                a_marginal += tpm[s, list(part_a)]
                b_marginal += tpm[s, list(part_b)]
                count += 1
            a_marginal /= max(count, 1)
            b_marginal /= max(count, 1)

            # Product distribution
            product = np.zeros(n)
            for i, idx_a in enumerate(part_a):
                product[idx_a] = a_marginal[i]
            for i, idx_b in enumerate(part_b):
                product[idx_b] = b_marginal[i]

            # KL-divergence approximation (with epsilon for stability)
            eps = 1e-10
            p = np.clip(full_trans, eps, 1 - eps)
            q = np.clip(product, eps, 1 - eps)
            kl = np.sum(p * np.log(p / q))
            total_divergence += max(kl, 0.0)

        return total_divergence / n_samples

    def emd_approximation(self, p: np.ndarray, q: np.ndarray) -> float:
        """Approximate Earth Mover's Distance between two distributions.

        Uses the L1-Wasserstein distance approximation via sorted CDF
        difference (exact for 1D distributions).

        Args:
            p: First probability distribution.
            q: Second probability distribution.

        Returns:
            Approximate EMD value.
        """
        p = p / (np.sum(p) + 1e-12)
        q = q / (np.sum(q) + 1e-12)

        # Sort-based 1D Wasserstein
        p_sorted = np.sort(p)
        q_sorted = np.sort(q)
        cdf_diff = np.abs(np.cumsum(p_sorted) - np.cumsum(q_sorted))
        return float(np.sum(cdf_diff))

    def get_stats(self) -> Dict[str, Any]:
        """Return IIT approximator statistics."""
        return {
            'computations': self._computations,
            'last_phi': self._last_phi,
            'avg_phi': float(np.mean(self._phi_history)) if self._phi_history else 0.0,
            'max_phi': float(np.max(self._phi_history)) if self._phi_history else 0.0,
            'min_phi': float(np.min(self._phi_history)) if self._phi_history else 0.0,
            'total_time_s': round(self._total_time, 3),
            'avg_time_ms': round(self._total_time * 1000 / max(self._computations, 1), 1),
            'phi_history_len': len(self._phi_history),
            'max_system_size': self._max_nodes,
            'tpm_shape': list(self._last_tpm.shape) if self._last_tpm is not None else None,
        }
