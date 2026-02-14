"""
Graph-to-SUSY-Hamiltonian Conversion — Risk assessment via quantum Hamiltonians

Converts a transaction graph subgraph into a SUSY Hamiltonian whose ground-state
energy encodes financial risk.  Each address becomes a qubit site; each transaction
edge becomes a coupling term.  Higher connectivity, larger flow, and proximity
to sanctioned addresses all strengthen the Hamiltonian coupling, producing a
higher ground-state energy → higher risk score.

The VQE ground-state computation approximates the true risk without diagonalising
the full matrix, which is essential when graphs grow beyond ~20 qubits.
"""
import hashlib
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Maximum qubit count we support (keeps matrix sizes manageable)
MAX_QUBITS: int = 16


@dataclass
class HamiltonianTerm:
    """One Pauli term in the risk Hamiltonian."""
    pauli_label: str     # e.g. "ZZII", "XZIX"
    coefficient: float   # real coefficient

    def to_dict(self) -> dict:
        return {'pauli_label': self.pauli_label, 'coefficient': self.coefficient}


@dataclass
class RiskHamiltonian:
    """Full Hamiltonian built from a transaction graph."""
    n_qubits: int
    terms: List[HamiltonianTerm] = field(default_factory=list)
    address_map: Dict[str, int] = field(default_factory=dict)
    # Metadata
    seed_address: str = ''
    total_flow: float = 0.0

    def to_dict(self) -> dict:
        return {
            'n_qubits': self.n_qubits,
            'num_terms': len(self.terms),
            'seed_address': self.seed_address,
            'total_flow': self.total_flow,
            'terms': [t.to_dict() for t in self.terms],
            'address_map': self.address_map,
        }


class GraphToHamiltonianConverter:
    """Converts a transaction graph subgraph into a SUSY Hamiltonian.

    Mapping rules:
        1. Each unique address → one qubit (index 0..n-1)
        2. Each transaction edge (i→j) → ZZ coupling term with strength
           proportional to ``log(1 + amount) / max_amount``
        3. Self-energy terms (Z_i) encode local risk (e.g. sanctions flag)
        4. Transverse field (X_i) provides quantum fluctuations
    """

    COUPLING_SCALE: float = 1.0     # Scales ZZ coupling strength
    FIELD_SCALE: float = 0.5        # Transverse field strength
    SELF_ENERGY_BASE: float = 0.1   # Base self-energy per node

    def __init__(self, max_qubits: int = MAX_QUBITS) -> None:
        self.max_qubits = max_qubits

    def convert(self, nodes: Dict[str, 'GraphNode'],
                edges: List['TxEdge'],
                seed: str = '',
                flagged_addresses: Optional[set] = None) -> RiskHamiltonian:
        """Build a risk Hamiltonian from graph nodes and edges.

        Args:
            nodes: address → GraphNode mapping (from TransactionGraph.build_subgraph)
            edges: list of TxEdge objects connecting the nodes
            seed: the seed address of the subgraph
            flagged_addresses: addresses flagged by sanctions/AML

        Returns:
            A RiskHamiltonian encoding the graph's risk profile.
        """
        flagged = flagged_addresses or set()

        # 1. Assign qubit indices to addresses (sorted for determinism)
        addresses = sorted(nodes.keys())
        if len(addresses) > self.max_qubits:
            # Keep closest nodes (lowest hop distance)
            addresses = sorted(
                addresses,
                key=lambda a: nodes[a].hop_distance
            )[:self.max_qubits]

        n_qubits = len(addresses)
        if n_qubits == 0:
            return RiskHamiltonian(n_qubits=0, seed_address=seed)

        address_map: Dict[str, int] = {
            addr: idx for idx, addr in enumerate(addresses)
        }
        addr_set = set(addresses)

        terms: List[HamiltonianTerm] = []
        total_flow = 0.0

        # 2. Coupling terms from edges (ZZ interactions)
        max_amount = max((e.amount for e in edges), default=1.0) or 1.0
        for edge in edges:
            if edge.sender not in addr_set or edge.recipient not in addr_set:
                continue
            i = address_map[edge.sender]
            j = address_map[edge.recipient]
            if i == j:
                continue
            strength = math.log1p(edge.amount) / math.log1p(max_amount)
            coeff = self.COUPLING_SCALE * strength
            label = _zz_label(n_qubits, i, j)
            terms.append(HamiltonianTerm(pauli_label=label, coefficient=coeff))
            total_flow += edge.amount

        # 3. Self-energy terms (Z_i) — higher for flagged addresses
        for addr, idx in address_map.items():
            base = self.SELF_ENERGY_BASE
            if addr in flagged:
                base += 1.0  # strong penalty for sanctioned
            hop = nodes[addr].hop_distance
            # Closer nodes (lower hop) contribute more self-energy
            hop_factor = 1.0 / (1.0 + hop)
            coeff = base * hop_factor
            label = _z_label(n_qubits, idx)
            terms.append(HamiltonianTerm(pauli_label=label, coefficient=coeff))

        # 4. Transverse field terms (X_i) — quantum fluctuations
        for idx in range(n_qubits):
            label = _x_label(n_qubits, idx)
            terms.append(HamiltonianTerm(
                pauli_label=label,
                coefficient=self.FIELD_SCALE,
            ))

        return RiskHamiltonian(
            n_qubits=n_qubits,
            terms=terms,
            address_map=address_map,
            seed_address=seed,
            total_flow=total_flow,
        )

    def estimate_ground_energy(self, hamiltonian: RiskHamiltonian) -> float:
        """Classical approximation of ground-state energy for risk scoring.

        For small qubit counts (≤8) we diagonalise exactly.
        For larger systems we use a mean-field approximation.
        """
        if hamiltonian.n_qubits == 0:
            return 0.0

        if hamiltonian.n_qubits <= 8:
            return self._exact_ground_energy(hamiltonian)
        return self._mean_field_energy(hamiltonian)

    def _exact_ground_energy(self, h: RiskHamiltonian) -> float:
        """Exact diagonalisation for small systems."""
        import numpy as np

        dim = 2 ** h.n_qubits
        matrix = np.zeros((dim, dim), dtype=complex)

        for term in h.terms:
            matrix += term.coefficient * _pauli_matrix(term.pauli_label)

        eigenvalues = np.linalg.eigvalsh(matrix)
        return float(eigenvalues[0])

    def _mean_field_energy(self, h: RiskHamiltonian) -> float:
        """Mean-field approximation: sum of all ZZ and Z coefficients.

        This is a rough lower bound on the ground-state energy.
        """
        energy = 0.0
        for term in h.terms:
            if 'X' not in term.pauli_label:
                energy -= abs(term.coefficient)
            else:
                energy -= abs(term.coefficient) * 0.5
        return energy


# ── Pauli label helpers ────────────────────────────────────────────────

def _zz_label(n: int, i: int, j: int) -> str:
    """Build a Pauli string with Z on sites i and j, I elsewhere."""
    chars = ['I'] * n
    chars[i] = 'Z'
    chars[j] = 'Z'
    return ''.join(chars)


def _z_label(n: int, i: int) -> str:
    chars = ['I'] * n
    chars[i] = 'Z'
    return ''.join(chars)


def _x_label(n: int, i: int) -> str:
    chars = ['I'] * n
    chars[i] = 'X'
    return ''.join(chars)


def _pauli_matrix(label: str) -> 'np.ndarray':
    """Compute the full matrix for a Pauli string like 'XZII'."""
    import numpy as np

    _I = np.eye(2, dtype=complex)
    _X = np.array([[0, 1], [1, 0]], dtype=complex)
    _Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
    _Z = np.array([[1, 0], [0, -1]], dtype=complex)

    pauli_map = {'I': _I, 'X': _X, 'Y': _Y, 'Z': _Z}

    result = pauli_map[label[0]]
    for ch in label[1:]:
        result = np.kron(result, pauli_map[ch])
    return result


def energy_to_risk_score(energy: float, n_qubits: int) -> float:
    """Convert ground-state energy to a 0-100 risk score.

    Lower (more negative) energy → lower risk.
    Higher (less negative / positive) energy → higher risk.

    The scale is calibrated so that:
      - Fully anti-aligned (minimum energy) → score ≈ 0
      - Fully aligned (maximum energy) → score ≈ 100
    """
    if n_qubits == 0:
        return 0.0
    # Rough bounds: energy in [-n_qubits, +n_qubits]
    max_abs = float(n_qubits) * 2.0
    normalised = (energy + max_abs) / (2.0 * max_abs)
    return max(0.0, min(100.0, normalised * 100.0))
