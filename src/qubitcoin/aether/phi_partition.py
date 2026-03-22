"""
Real Partition-Based Phi (MIP) — Item #82
More rigorous Phi computation via minimum information partition.
Complements the IIT approximator (#34) with a proper MIP search.
"""
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class PhiPartition:
    """Compute integrated information (Phi) via minimum information
    partition (MIP) search using Earth Mover's Distance proxy.

    Supports systems of 4-16 nodes.  Larger systems are sub-sampled.
    """

    def __init__(self, max_nodes: int = 16) -> None:
        self._max_nodes = max_nodes
        self._computations: int = 0
        self._last_phi: float = 0.0
        self._last_mip: Optional[Tuple[List[int], List[int]]] = None

    # ------------------------------------------------------------------
    def compute_phi(
        self,
        system_state: np.ndarray,
        connectivity: np.ndarray,
    ) -> float:
        """Compute Phi for *system_state* given *connectivity* matrix.

        Args:
            system_state: 1-D vector of node activations (length N).
            connectivity: N x N weight matrix (adjacency).

        Returns:
            Phi value (>= 0).  Higher means more integrated.
        """
        self._computations += 1
        state = np.asarray(system_state, dtype=np.float64).ravel()
        conn = np.asarray(connectivity, dtype=np.float64)

        n = len(state)
        if n < 2:
            self._last_phi = 0.0
            return 0.0

        # Sub-sample if too large
        if n > self._max_nodes:
            idx = np.random.default_rng(42).choice(n, self._max_nodes, replace=False)
            idx.sort()
            state = state[idx]
            conn = conn[np.ix_(idx, idx)]
            n = self._max_nodes

        # Build cause-effect structure (transition probability proxy)
        tpm = self._build_tpm(state, conn)

        # Find MIP via greedy bipartition search
        best_phi = float("inf")
        best_partition: Optional[Tuple[List[int], List[int]]] = None
        indices = list(range(n))

        # Enumerate bipartitions (greedy for large n)
        partitions = self._generate_partitions(indices)
        whole_cause = self._compute_cause_info_whole(tpm, state)
        whole_effect = self._compute_effect_info_whole(tpm, state)

        for part_a, part_b in partitions:
            if not part_a or not part_b:
                continue
            # Compute info loss from partitioning
            cause_loss = self._partition_cause_loss(tpm, state, part_a, part_b)
            effect_loss = self._partition_effect_loss(tpm, state, part_a, part_b)
            phi_partition = cause_loss + effect_loss

            if phi_partition < best_phi:
                best_phi = phi_partition
                best_partition = (part_a, part_b)

        # Phi = minimum over all partitions of information lost
        if best_phi == float("inf"):
            best_phi = 0.0

        self._last_phi = best_phi
        self._last_mip = best_partition
        return best_phi

    # ------------------------------------------------------------------
    def _build_tpm(
        self, state: np.ndarray, conn: np.ndarray
    ) -> np.ndarray:
        """Build a transition probability matrix proxy from connectivity."""
        n = len(state)
        # Simple sigmoid-based TPM
        tpm = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(n):
                weight = conn[i, j]
                activation = state[j]
                tpm[i, j] = 1.0 / (1.0 + np.exp(-weight * activation))
        # Normalise rows
        row_sums = tpm.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums < 1e-12, 1.0, row_sums)
        tpm = tpm / row_sums
        return tpm

    # ------------------------------------------------------------------
    def compute_cause_info(
        self, subset: List[int], whole: np.ndarray
    ) -> float:
        """Compute cause information for a subset of nodes."""
        if not subset or whole.size == 0:
            return 0.0
        sub_matrix = whole[np.ix_(subset, subset)]
        # KL divergence proxy
        flat = sub_matrix.ravel()
        flat = flat[flat > 1e-12]
        if len(flat) == 0:
            return 0.0
        uniform = np.ones_like(flat) / len(flat)
        return float(np.sum(flat * np.log(flat / uniform + 1e-12)))

    # ------------------------------------------------------------------
    def compute_effect_info(
        self, subset: List[int], whole: np.ndarray
    ) -> float:
        """Compute effect information for a subset of nodes."""
        if not subset or whole.size == 0:
            return 0.0
        sub_matrix = whole[subset, :]
        flat = sub_matrix.ravel()
        flat = flat[flat > 1e-12]
        if len(flat) == 0:
            return 0.0
        uniform = np.ones_like(flat) / len(flat)
        return float(np.sum(flat * np.log(flat / uniform + 1e-12)))

    # ------------------------------------------------------------------
    def _compute_cause_info_whole(
        self, tpm: np.ndarray, state: np.ndarray
    ) -> float:
        indices = list(range(len(state)))
        return self.compute_cause_info(indices, tpm)

    def _compute_effect_info_whole(
        self, tpm: np.ndarray, state: np.ndarray
    ) -> float:
        indices = list(range(len(state)))
        return self.compute_effect_info(indices, tpm)

    # ------------------------------------------------------------------
    def _partition_cause_loss(
        self,
        tpm: np.ndarray,
        state: np.ndarray,
        part_a: List[int],
        part_b: List[int],
    ) -> float:
        """EMD proxy: difference between whole and partitioned cause repertoire."""
        whole = self._compute_cause_info_whole(tpm, state)
        part = self.compute_cause_info(part_a, tpm) + self.compute_cause_info(part_b, tpm)
        return abs(whole - part)

    def _partition_effect_loss(
        self,
        tpm: np.ndarray,
        state: np.ndarray,
        part_a: List[int],
        part_b: List[int],
    ) -> float:
        whole = self._compute_effect_info_whole(tpm, state)
        part = self.compute_effect_info(part_a, tpm) + self.compute_effect_info(part_b, tpm)
        return abs(whole - part)

    # ------------------------------------------------------------------
    def _generate_partitions(
        self, indices: List[int]
    ) -> List[Tuple[List[int], List[int]]]:
        """Generate bipartitions.  For n <= 8 enumerate all; otherwise
        use greedy heuristic (split by connectivity weight)."""
        n = len(indices)
        if n <= 8:
            # Enumerate all non-trivial bipartitions
            partitions = []
            for mask in range(1, 2 ** n - 1):
                a = [indices[i] for i in range(n) if mask & (1 << i)]
                b = [indices[i] for i in range(n) if not (mask & (1 << i))]
                if a and b:
                    partitions.append((a, b))
            return partitions
        else:
            # Greedy: split in half, then try random swaps
            rng = np.random.default_rng(42)
            partitions = []
            mid = n // 2
            base_a = indices[:mid]
            base_b = indices[mid:]
            partitions.append((list(base_a), list(base_b)))
            for _ in range(min(50, n * 2)):
                perm = rng.permutation(indices).tolist()
                k = rng.integers(1, n)
                partitions.append((perm[:k], perm[k:]))
            return partitions

    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        return {
            "computations": self._computations,
            "last_phi": self._last_phi,
            "max_nodes": self._max_nodes,
            "last_mip_sizes": (
                [len(self._last_mip[0]), len(self._last_mip[1])]
                if self._last_mip else None
            ),
        }
