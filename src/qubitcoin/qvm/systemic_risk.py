"""
QRISK_SYSTEMIC — Systemic risk and contagion prediction

Models financial contagion in the transaction graph using a simplified
susceptible-infected-recovered (SIR) model.  Each address is a node that can be:
  - Susceptible (healthy)
  - Infected (defaulting / high-risk)
  - Recovered (risk resolved)

The time-evolution operator propagates risk through the graph based on
edge weights (transaction volume), simulating how a default cascade
would spread.  The final systemic risk score measures the fraction of
the network that would be affected.
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Default SIR model parameters
DEFAULT_INFECTION_RATE: float = 0.3     # Probability of contagion per edge per step
DEFAULT_RECOVERY_RATE: float = 0.1      # Probability of recovery per step
DEFAULT_MAX_STEPS: int = 20             # Max simulation steps
CONTAGION_WEIGHT_SCALE: float = 1.0     # Scale edge weight influence


class NodeState:
    SUSCEPTIBLE = 0
    INFECTED = 1
    RECOVERED = 2


@dataclass
class ContagionResult:
    """Result of a contagion simulation."""
    initial_infected: List[str]
    total_infected: int       # Peak number of infected nodes
    total_recovered: int      # Nodes that recovered
    peak_infection_rate: float  # Max fraction infected at any step
    final_susceptible: int
    steps_to_peak: int
    systemic_risk_score: float  # 0-100 score
    affected_addresses: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'initial_infected': self.initial_infected,
            'total_infected': self.total_infected,
            'total_recovered': self.total_recovered,
            'peak_infection_rate': round(self.peak_infection_rate, 4),
            'final_susceptible': self.final_susceptible,
            'steps_to_peak': self.steps_to_peak,
            'systemic_risk_score': round(self.systemic_risk_score, 2),
            'affected_count': len(self.affected_addresses),
        }


@dataclass
class ContagionEdge:
    """A weighted edge for contagion modelling."""
    source: str
    target: str
    weight: float = 1.0  # Normalised transaction volume


class SystemicRiskModel:
    """SIR-based contagion model for systemic risk assessment.

    Given a transaction graph (as adjacency lists), simulates how
    a default at one or more addresses would cascade through the network.
    """

    def __init__(self, infection_rate: float = DEFAULT_INFECTION_RATE,
                 recovery_rate: float = DEFAULT_RECOVERY_RATE,
                 max_steps: int = DEFAULT_MAX_STEPS) -> None:
        self.infection_rate = infection_rate
        self.recovery_rate = recovery_rate
        self.max_steps = max_steps
        # Adjacency: address → list of (peer, weight)
        self._adjacency: Dict[str, List[Tuple[str, float]]] = {}
        self._addresses: Set[str] = set()

    def add_edge(self, source: str, target: str, weight: float = 1.0) -> None:
        """Add a directed edge to the contagion model."""
        if source not in self._adjacency:
            self._adjacency[source] = []
        self._adjacency[source].append((target, weight))
        self._addresses.add(source)
        self._addresses.add(target)

    def add_edges_from_graph(self, edges: list) -> None:
        """Bulk-add edges from TxEdge list (from TransactionGraph)."""
        max_amount = max((e.amount for e in edges), default=1.0) or 1.0
        for e in edges:
            normalised = e.amount / max_amount
            self.add_edge(e.sender, e.recipient, normalised)

    def simulate(self, initial_infected: List[str]) -> ContagionResult:
        """Run the SIR contagion simulation.

        Args:
            initial_infected: list of addresses that start as infected.

        Returns:
            ContagionResult with systemic risk metrics.
        """
        if not self._addresses:
            return ContagionResult(
                initial_infected=initial_infected,
                total_infected=0,
                total_recovered=0,
                peak_infection_rate=0.0,
                final_susceptible=0,
                steps_to_peak=0,
                systemic_risk_score=0.0,
            )

        n_total = len(self._addresses)
        state: Dict[str, int] = {
            addr: NodeState.SUSCEPTIBLE for addr in self._addresses
        }
        for addr in initial_infected:
            if addr in state:
                state[addr] = NodeState.INFECTED

        peak_infected = sum(1 for s in state.values() if s == NodeState.INFECTED)
        steps_to_peak = 0
        ever_infected: Set[str] = set(
            a for a in initial_infected if a in state
        )

        for step in range(1, self.max_steps + 1):
            new_state = dict(state)

            # Infection phase: infected nodes spread to susceptible neighbors
            for addr, s in state.items():
                if s != NodeState.INFECTED:
                    continue
                for neighbor, weight in self._adjacency.get(addr, []):
                    if state.get(neighbor) == NodeState.SUSCEPTIBLE:
                        # Infection probability scales with edge weight
                        prob = self.infection_rate * weight * CONTAGION_WEIGHT_SCALE
                        # Deterministic: infect if prob > threshold
                        # Use hash-based determinism for reproducibility
                        seed_val = _deterministic_hash(addr, neighbor, step)
                        if seed_val < prob:
                            new_state[neighbor] = NodeState.INFECTED
                            ever_infected.add(neighbor)

            # Recovery phase
            for addr, s in state.items():
                if s == NodeState.INFECTED:
                    seed_val = _deterministic_hash(addr, 'recover', step)
                    if seed_val < self.recovery_rate:
                        new_state[addr] = NodeState.RECOVERED

            state = new_state

            current_infected = sum(
                1 for s in state.values() if s == NodeState.INFECTED
            )
            if current_infected > peak_infected:
                peak_infected = current_infected
                steps_to_peak = step

            # Early termination if no more infected
            if current_infected == 0:
                break

        final_susceptible = sum(
            1 for s in state.values() if s == NodeState.SUSCEPTIBLE
        )
        total_recovered = sum(
            1 for s in state.values() if s == NodeState.RECOVERED
        )

        peak_rate = peak_infected / n_total if n_total > 0 else 0.0

        # Systemic risk score: based on peak infection rate and total affected
        affected_ratio = len(ever_infected) / n_total if n_total > 0 else 0.0
        systemic_score = _compute_systemic_score(peak_rate, affected_ratio, n_total)

        return ContagionResult(
            initial_infected=initial_infected,
            total_infected=len(ever_infected),
            total_recovered=total_recovered,
            peak_infection_rate=peak_rate,
            final_susceptible=final_susceptible,
            steps_to_peak=steps_to_peak,
            systemic_risk_score=systemic_score,
            affected_addresses=sorted(ever_infected),
        )

    def detect_high_risk_connections(self, address: str,
                                      sanctioned: Optional[Set[str]] = None,
                                      mixer_addresses: Optional[Set[str]] = None,
                                      ) -> List[Dict]:
        """Identify high-risk connections for an address.

        Checks for direct connections to:
          - Sanctioned entities
          - Known mixer addresses
          - Highly connected hubs (potential overleveraged entities)
        """
        sanctioned = sanctioned or set()
        mixers = mixer_addresses or set()
        results: List[Dict] = []

        neighbors = self._adjacency.get(address, [])
        for peer, weight in neighbors:
            risk_type = None
            if peer in sanctioned:
                risk_type = 'sanctioned'
            elif peer in mixers:
                risk_type = 'mixer'
            elif len(self._adjacency.get(peer, [])) > 50:
                risk_type = 'high_connectivity'

            if risk_type:
                results.append({
                    'address': peer,
                    'risk_type': risk_type,
                    'edge_weight': weight,
                })

        return results

    def get_node_count(self) -> int:
        return len(self._addresses)


def _deterministic_hash(a: str, b: str, step: int) -> float:
    """Deterministic pseudo-random value in [0,1) based on inputs."""
    import hashlib
    data = f"{a}:{b}:{step}".encode()
    h = hashlib.sha256(data).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _compute_systemic_score(peak_rate: float, affected_ratio: float,
                             n_total: int) -> float:
    """Compute systemic risk score on 0-100 scale.

    Weighted combination:
      - 50% from peak infection rate (how bad the worst moment is)
      - 30% from total affected ratio (how far it spreads)
      - 20% from network size factor (larger networks → higher systemic risk)
    """
    peak_component = peak_rate * 50.0
    affected_component = affected_ratio * 30.0
    # Size factor: log scale, saturates at ~1000 nodes
    size_factor = min(math.log1p(n_total) / math.log1p(1000), 1.0)
    size_component = size_factor * 20.0

    score = peak_component + affected_component + size_component
    return max(0.0, min(100.0, score))
