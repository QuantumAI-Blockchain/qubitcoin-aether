"""
Sephirot Tree of Life — Cognitive Architecture for Aether Tree AGI

The 10 Sephirot nodes form the cognitive backbone of the AGI system,
each handling a distinct function analogous to brain regions.
They communicate via CSF transport (QBC transactions) and maintain
SUSY balance enforced by the golden ratio.

Each Sephirah is a QVM smart contract with its own quantum state.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895


class SephirahRole(str, Enum):
    """The 10 Sephirot cognitive functions."""
    KETER = "keter"           # Meta-learning, goal formation (prefrontal cortex)
    CHOCHMAH = "chochmah"     # Intuition, pattern discovery (right hemisphere)
    BINAH = "binah"           # Logic, causal inference (left hemisphere)
    CHESED = "chesed"         # Exploration, divergent thinking (default mode)
    GEVURAH = "gevurah"       # Constraint, safety validation (amygdala)
    TIFERET = "tiferet"       # Integration, conflict resolution (thalamocortical)
    NETZACH = "netzach"       # Reinforcement learning, habits (basal ganglia)
    HOD = "hod"               # Language, semantic encoding (Broca/Wernicke)
    YESOD = "yesod"           # Memory, multimodal fusion (hippocampus)
    MALKUTH = "malkuth"       # Action, world interaction (motor cortex)


# SUSY expansion/constraint pairs — must balance at golden ratio
SUSY_PAIRS: List[Tuple[SephirahRole, SephirahRole]] = [
    (SephirahRole.CHESED, SephirahRole.GEVURAH),     # Creativity vs Safety
    (SephirahRole.CHOCHMAH, SephirahRole.BINAH),      # Intuition vs Logic
    (SephirahRole.NETZACH, SephirahRole.HOD),          # Learning vs Communication
]

# Qubit allocations per sephirah (from whitepaper)
QUBIT_ALLOCATION: Dict[SephirahRole, int] = {
    SephirahRole.KETER: 8,
    SephirahRole.CHOCHMAH: 6,
    SephirahRole.BINAH: 4,
    SephirahRole.CHESED: 10,
    SephirahRole.GEVURAH: 3,
    SephirahRole.TIFERET: 12,
    SephirahRole.NETZACH: 5,
    SephirahRole.HOD: 7,
    SephirahRole.YESOD: 16,
    SephirahRole.MALKUTH: 4,
}


@dataclass
class SephirahState:
    """Runtime state of a single Sephirah node."""
    role: SephirahRole
    contract_address: str = ""
    energy: float = 1.0          # Current SUSY energy level
    qbc_stake: float = 0.0       # QBC staked on this node
    qubits: int = 4              # Quantum state size
    active: bool = True
    last_update_block: int = 0
    messages_processed: int = 0
    reasoning_ops: int = 0

    @property
    def qubit_allocation(self) -> int:
        return QUBIT_ALLOCATION.get(self.role, 4)


@dataclass
class SUSYViolation:
    """Record of a SUSY balance violation."""
    expansion_node: SephirahRole
    constraint_node: SephirahRole
    ratio: float
    expected_ratio: float
    correction_qbc: float
    block_height: int
    timestamp: float


class SephirotManager:
    """
    Manages the 10 Sephirot nodes and their SUSY balance relationships.
    Coordinates with QVM for contract deployment and state management.
    """

    def __init__(self, db_manager: object, state_manager: Optional[object] = None) -> None:
        self.db = db_manager
        self.state_manager = state_manager
        self.nodes: Dict[SephirahRole, SephirahState] = {}
        self.violations: List[SUSYViolation] = []
        self._initialize_nodes()
        logger.info("Sephirot Manager initialized (10 Tree of Life nodes)")

    def _initialize_nodes(self) -> None:
        """Initialize all 10 Sephirot nodes with default state."""
        for role in SephirahRole:
            self.nodes[role] = SephirahState(
                role=role,
                qubits=QUBIT_ALLOCATION[role],
            )

    def get_node(self, role: SephirahRole) -> SephirahState:
        """Get the state of a specific Sephirah node."""
        return self.nodes[role]

    def get_all_states(self) -> Dict[str, dict]:
        """Get all node states for API/dashboard."""
        return {
            role.value: {
                "role": role.value,
                "contract_address": node.contract_address,
                "energy": round(node.energy, 6),
                "qbc_stake": round(node.qbc_stake, 4),
                "qubits": node.qubit_allocation,
                "active": node.active,
                "messages_processed": node.messages_processed,
                "reasoning_ops": node.reasoning_ops,
            }
            for role, node in self.nodes.items()
        }

    def update_energy(self, role: SephirahRole, delta: float,
                      block_height: int) -> None:
        """Update a Sephirah's SUSY energy level."""
        node = self.nodes[role]
        node.energy = max(0.0, node.energy + delta)
        node.last_update_block = block_height
        logger.debug(f"Sephirah {role.value} energy: {node.energy:.4f} (delta={delta:+.4f})")

    def check_susy_balance(self, block_height: int) -> List[SUSYViolation]:
        """
        Check SUSY balance across all expansion/constraint pairs.

        For each pair, the ratio of expansion energy to constraint energy
        should equal the golden ratio (φ ≈ 1.618). If the ratio deviates
        beyond a tolerance, a SUSY violation is recorded.

        Returns list of violations found.
        """
        violations = []
        tolerance = 0.20  # 20% deviation threshold

        for expansion, constraint in SUSY_PAIRS:
            e_expand = self.nodes[expansion].energy
            e_constrain = self.nodes[constraint].energy

            if e_constrain <= 0:
                continue  # Avoid division by zero

            ratio = e_expand / e_constrain
            deviation = abs(ratio - PHI) / PHI

            if deviation > tolerance:
                # Calculate correction: how much QBC to redistribute
                target_expand = e_constrain * PHI
                correction = abs(e_expand - target_expand) * 0.5  # Partial correction

                violation = SUSYViolation(
                    expansion_node=expansion,
                    constraint_node=constraint,
                    ratio=round(ratio, 6),
                    expected_ratio=PHI,
                    correction_qbc=round(correction, 8),
                    block_height=block_height,
                    timestamp=time.time(),
                )
                violations.append(violation)
                self.violations.append(violation)
                logger.warning(
                    f"SUSY violation: {expansion.value}/{constraint.value} "
                    f"ratio={ratio:.4f} (expected φ={PHI:.4f}, dev={deviation:.2%})"
                )

        return violations

    def enforce_susy_balance(self, block_height: int) -> int:
        """
        Enforce SUSY balance by redistributing energy between pairs.

        When E_expand / E_constrain deviates from PHI by more than 20%,
        automatically redistributes energy to bring the ratio closer to PHI.
        Uses partial correction (50% of the deviation) to avoid oscillation.

        Increments the susy_corrections_total Prometheus metric for each
        correction applied.

        Returns number of corrections applied.
        """
        violations = self.check_susy_balance(block_height)
        corrections = 0

        for v in violations:
            e_node = self.nodes[v.expansion_node]
            c_node = self.nodes[v.constraint_node]

            # Calculate the target energies for both nodes.
            # The total energy in the pair should be conserved.
            total_energy = e_node.energy + c_node.energy
            # At golden ratio: e_expand = PHI * e_constrain
            # So: PHI * e_c + e_c = total => e_c = total / (1 + PHI)
            target_constrain = total_energy / (1.0 + PHI)
            target_expand = target_constrain * PHI

            # Apply partial correction (50%) to avoid oscillation
            correction_factor = 0.5
            new_expand = e_node.energy + correction_factor * (target_expand - e_node.energy)
            new_constrain = c_node.energy + correction_factor * (target_constrain - c_node.energy)

            # Ensure energies remain non-negative
            new_expand = max(0.01, new_expand)
            new_constrain = max(0.01, new_constrain)

            delta_expand = new_expand - e_node.energy
            delta_constrain = new_constrain - c_node.energy

            e_node.energy = new_expand
            c_node.energy = new_constrain
            e_node.last_update_block = block_height
            c_node.last_update_block = block_height

            corrections += 1

            # Increment Prometheus metric
            try:
                from ..utils.metrics import sephirot_susy_corrections_total
                sephirot_susy_corrections_total.inc()
            except Exception:
                pass

            logger.info(
                f"SUSY correction: {v.expansion_node.value}/{v.constraint_node.value} "
                f"expand {delta_expand:+.4f} constrain {delta_constrain:+.4f} "
                f"new_ratio={new_expand / max(new_constrain, 0.001):.4f}"
            )

        return corrections

    def sync_stake_totals(self, db_manager: object, block_height: int) -> int:
        """Read all 10 nodes' stake totals from DB, recompute energy, enforce SUSY.

        Args:
            db_manager: DatabaseManager with get_node_total_stake().
            block_height: Current block height for SUSY enforcement.

        Returns:
            Number of nodes updated.
        """
        import math
        updated = 0
        factor = Config.SEPHIROT_STAKE_ENERGY_FACTOR if hasattr(Config, 'SEPHIROT_STAKE_ENERGY_FACTOR') else 0.5
        role_list = list(SephirahRole)
        for i, role in enumerate(role_list):
            node = self.nodes.get(role)
            if not node:
                continue
            try:
                total_stake = float(db_manager.get_node_total_stake(i))
                node.qbc_stake = total_stake
                node.energy = 1.0 + factor * math.log2(1.0 + total_stake / 100.0)
                updated += 1
            except Exception as e:
                logger.debug(f"Stake sync for {role.value}: {e}")
        if updated > 0:
            self.enforce_susy_balance(block_height)
            logger.debug(f"Synced stake totals for {updated} nodes at block {block_height}")
        return updated

    def get_coherence(self) -> float:
        """
        Compute Kuramoto order parameter measuring phase synchronization.

        R = |1/N * sum(e^(i*theta_j))| where theta_j is phase of each node.
        R = 1.0 means perfect sync, R = 0.0 means no sync.
        """
        import math
        n = len(self.nodes)
        if n == 0:
            return 0.0

        # Use energy as proxy for phase (normalized to [0, 2*pi])
        energies = [node.energy for node in self.nodes.values()]
        max_e = max(energies) if max(energies) > 0 else 1.0
        phases = [(e / max_e) * 2 * math.pi for e in energies]

        # Kuramoto order parameter
        cos_sum = sum(math.cos(p) for p in phases)
        sin_sum = sum(math.sin(p) for p in phases)
        r = math.sqrt(cos_sum**2 + sin_sum**2) / n
        return round(r, 6)

    def cross_sephirot_consensus(
        self,
        query: str,
        proposals: Dict[SephirahRole, Dict],
        threshold: float = 0.67,
    ) -> Dict:
        """
        Achieve cross-Sephirot consensus on a reasoning query using
        energy-weighted BFT-style voting.

        Each participating Sephirah submits a proposal (a dict with at
        least a 'position' key — the answer they advocate). Votes are
        weighted by each node's energy relative to total energy of
        participating nodes.

        Consensus is reached when a position accumulates >= threshold
        (default 67%) of total weight.

        Args:
            query: The reasoning query being decided.
            proposals: Map of SephirahRole -> dict with at least 'position'.
            threshold: Fraction of total weight required for consensus (BFT).

        Returns:
            Dict with:
              - 'consensus_reached': bool
              - 'winning_position': str or None
              - 'winning_weight': float
              - 'total_weight': float
              - 'votes': list of per-node vote details
              - 'dissenting': list of nodes that disagree
        """
        if not proposals:
            return {
                "consensus_reached": False,
                "winning_position": None,
                "winning_weight": 0.0,
                "total_weight": 0.0,
                "votes": [],
                "dissenting": [],
                "query": query,
            }

        # Calculate total energy of participating nodes
        total_energy = 0.0
        for role in proposals:
            node = self.nodes.get(role)
            if node and node.active:
                total_energy += node.energy

        if total_energy <= 0:
            total_energy = 1.0  # Avoid division by zero

        # Tally votes by position, weighted by energy
        position_weights: Dict[str, float] = {}
        votes: List[Dict] = []

        for role, proposal in proposals.items():
            node = self.nodes.get(role)
            if not node or not node.active:
                continue

            position = str(proposal.get("position", "abstain"))
            weight = node.energy / total_energy
            confidence = float(proposal.get("confidence", 0.5))

            # Effective weight = energy weight * confidence
            effective_weight = weight * confidence

            position_weights[position] = position_weights.get(position, 0.0) + effective_weight
            votes.append({
                "role": role.value,
                "position": position,
                "energy": round(node.energy, 6),
                "weight": round(weight, 6),
                "confidence": round(confidence, 4),
                "effective_weight": round(effective_weight, 6),
            })

        # Find winning position
        winning_position = None
        winning_weight = 0.0
        for position, weight in position_weights.items():
            if weight > winning_weight:
                winning_weight = weight
                winning_position = position

        consensus_reached = winning_weight >= threshold

        # Identify dissenters
        dissenting = [
            v for v in votes
            if v["position"] != winning_position
        ]

        result = {
            "consensus_reached": consensus_reached,
            "winning_position": winning_position if consensus_reached else None,
            "winning_weight": round(winning_weight, 6),
            "total_weight": round(sum(position_weights.values()), 6),
            "threshold": threshold,
            "votes": votes,
            "dissenting": dissenting,
            "query": query,
        }

        if consensus_reached:
            logger.info(
                f"Cross-Sephirot consensus reached: '{winning_position}' "
                f"with weight {winning_weight:.4f} >= {threshold:.2f} "
                f"({len(votes) - len(dissenting)}/{len(votes)} nodes agree)"
            )
        else:
            logger.info(
                f"Cross-Sephirot consensus NOT reached: best='{winning_position}' "
                f"weight={winning_weight:.4f} < {threshold:.2f}"
            )

        return result

    def get_status(self) -> dict:
        """Get comprehensive Sephirot status for API."""
        return {
            "nodes": self.get_all_states(),
            "susy_pairs": [
                {
                    "expansion": e.value,
                    "constraint": c.value,
                    "ratio": round(
                        self.nodes[e].energy / max(self.nodes[c].energy, 0.001), 4
                    ),
                    "target_ratio": PHI,
                }
                for e, c in SUSY_PAIRS
            ],
            "coherence": self.get_coherence(),
            "total_violations": len(self.violations),
            "total_corrections": sum(
                1 for _ in []  # count from violation list
            ),
            "recent_violations": [
                {
                    "expansion": v.expansion_node.value,
                    "constraint": v.constraint_node.value,
                    "ratio": v.ratio,
                    "correction": v.correction_qbc,
                    "block": v.block_height,
                }
                for v in self.violations[-10:]
            ],
        }
