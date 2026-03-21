"""
Sephirot Tree of Life — Cognitive Architecture for Aether Tree AGI

The 10 Sephirot nodes form the cognitive backbone of the AGI system,
each handling a distinct function analogous to brain regions.
They communicate via CSF transport (QBC transactions) and maintain
SUSY balance enforced by the golden ratio.

Each Sephirah is a QVM smart contract with its own quantum state.
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Deque, List, Optional, Tuple
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
    cognitive_mass: float = 0.0       # Mass from Higgs field
    yukawa_coupling: float = 0.0      # Yukawa coupling constant

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

    MAX_VIOLATIONS_HISTORY: int = 10000

    def __init__(self, db_manager: object, state_manager: Optional[object] = None) -> None:
        self.db = db_manager
        self.state_manager = state_manager
        self.nodes: Dict[SephirahRole, SephirahState] = {}
        self.violations: Deque[SUSYViolation] = deque(maxlen=self.MAX_VIOLATIONS_HISTORY)
        self._total_corrections: int = 0  # Total SUSY corrections applied
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
                "cognitive_mass": round(node.cognitive_mass, 4),
                "yukawa_coupling": round(node.yukawa_coupling, 6),
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
            self._total_corrections += 1

            # Increment Prometheus metric
            try:
                from ..utils.metrics import sephirot_susy_corrections_total
                sephirot_susy_corrections_total.inc()
            except Exception as e:
                logger.debug("Could not increment SUSY correction metric: %s", e)

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

        Special case: when all energies are equal (zero variance), coherence
        is reported as 0.0 because there is no meaningful synchronization
        signal — all phases collapse to the same value, which is trivially
        "in sync" but does not indicate genuine coordination.
        """
        import math
        n = len(self.nodes)
        if n == 0:
            return 0.0

        # Use energy as proxy for phase (normalized to [0, 2*pi])
        energies = [node.energy for node in self.nodes.values()]

        # If all energies are equal (e.g., genesis), report 0.0 — no
        # meaningful synchronization can be measured from identical values.
        if len(set(energies)) <= 1:
            return 0.0

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

    def route_query(self, query: str, query_type: str = 'general') -> List[SephirahRole]:
        """Route a query to the most relevant Sephirot nodes based on content.

        Each Sephirah has cognitive domains it handles. This method analyzes
        the query and returns an ordered list of nodes that should process it,
        weighted by relevance and current energy levels.

        Args:
            query: The input query string.
            query_type: Hint about query type (reasoning, safety, creative, etc.)

        Returns:
            Ordered list of SephirahRole for processing (most relevant first).
        """
        q = query.lower()

        # Domain keyword mappings for each Sephirah
        domain_map: Dict[SephirahRole, List[str]] = {
            SephirahRole.KETER: ['goal', 'plan', 'strategy', 'meta', 'priority', 'decide',
                                 'what should', 'objective', 'purpose', 'mission'],
            SephirahRole.CHOCHMAH: ['pattern', 'intuition', 'similar', 'trend', 'analogy',
                                    'insight', 'recognize', 'discover', 'correlat'],
            SephirahRole.BINAH: ['logic', 'reason', 'cause', 'because', 'therefore', 'prove',
                                 'deduc', 'infer', 'if then', 'implies', 'why'],
            SephirahRole.CHESED: ['creative', 'idea', 'brainstorm', 'imagine', 'what if',
                                  'innovate', 'novel', 'explore', 'possibilit'],
            SephirahRole.GEVURAH: ['safe', 'risk', 'danger', 'harm', 'limit', 'constrain',
                                   'vulnerab', 'threat', 'protect', 'security'],
            SephirahRole.TIFERET: ['balance', 'integrat', 'synthesize', 'combin', 'reconcile',
                                   'both', 'conflict', 'tradeoff', 'compromise'],
            SephirahRole.NETZACH: ['learn', 'train', 'reward', 'reinforce', 'habit',
                                   'practice', 'improve', 'optimize', 'performance'],
            SephirahRole.HOD: ['language', 'meaning', 'semantic', 'word', 'defin',
                               'explain', 'communicat', 'express', 'describe', 'what is'],
            SephirahRole.YESOD: ['remember', 'memory', 'recall', 'history', 'previous',
                                 'past', 'store', 'retrieve', 'context', 'before'],
            SephirahRole.MALKUTH: ['do', 'execute', 'action', 'implement', 'run', 'deploy',
                                   'send', 'transact', 'build', 'create', 'make'],
        }

        # Score each node
        scores: Dict[SephirahRole, float] = {}
        for role, keywords in domain_map.items():
            node = self.nodes[role]
            if not node.active:
                continue
            keyword_score = sum(1.0 for kw in keywords if kw in q)
            # Weight by energy (more energized nodes score higher)
            energy_weight = min(2.0, node.energy)
            scores[role] = keyword_score * energy_weight

        # Query type hints boost specific nodes
        type_boosts = {
            'reasoning': [SephirahRole.BINAH, SephirahRole.CHOCHMAH],
            'safety': [SephirahRole.GEVURAH, SephirahRole.TIFERET],
            'creative': [SephirahRole.CHESED, SephirahRole.CHOCHMAH],
            'memory': [SephirahRole.YESOD, SephirahRole.HOD],
            'action': [SephirahRole.MALKUTH, SephirahRole.KETER],
        }
        for role in type_boosts.get(query_type, []):
            scores[role] = scores.get(role, 0.0) + 2.0

        # Always include Tiferet (integration) and Hod (language) as fallbacks
        scores[SephirahRole.TIFERET] = scores.get(SephirahRole.TIFERET, 0.0) + 0.5
        scores[SephirahRole.HOD] = scores.get(SephirahRole.HOD, 0.0) + 0.5

        # Sort by score descending, return top nodes with score > 0
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        result = [role for role, score in ranked if score > 0]

        # Track routing for metrics
        for role in result[:3]:
            self.nodes[role].messages_processed += 1

        return result if result else [SephirahRole.TIFERET, SephirahRole.HOD]

    def get_dominant_cognitive_mode(self) -> str:
        """Determine which cognitive mode is dominant based on node energies.

        Returns a human-readable string like 'analytical' or 'creative'
        based on which SUSY pair is most active.
        """
        modes = {
            'analytical': (SephirahRole.BINAH, SephirahRole.CHOCHMAH),
            'creative': (SephirahRole.CHESED, SephirahRole.GEVURAH),
            'communicative': (SephirahRole.HOD, SephirahRole.NETZACH),
        }
        best_mode = 'balanced'
        best_energy = 0.0
        for mode_name, (a, b) in modes.items():
            combined = self.nodes[a].energy + self.nodes[b].energy
            if combined > best_energy:
                best_energy = combined
                best_mode = mode_name
        return best_mode

    def get_energy_distribution(self) -> Dict[str, float]:
        """Get normalized energy distribution across all nodes.

        Returns dict mapping role name to percentage of total energy.
        """
        total = sum(n.energy for n in self.nodes.values())
        if total <= 0:
            return {r.value: 10.0 for r in SephirahRole}
        return {
            role.value: round(node.energy / total * 100, 2)
            for role, node in self.nodes.items()
        }

    def stimulate_node(self, role: SephirahRole, amount: float = 0.1,
                       block_height: int = 0) -> None:
        """Stimulate a node's energy in response to a relevant query.

        Called when a query routes to this node — the act of being used
        increases the node's energy slightly (use-it-or-lose-it dynamics).

        Args:
            role: Node to stimulate.
            amount: Energy delta (default 0.1).
            block_height: Current block height.
        """
        node = self.nodes[role]
        node.energy = min(5.0, node.energy + amount)  # Cap at 5.0
        node.reasoning_ops += 1
        node.last_update_block = block_height

    def decay_unused_nodes(self, block_height: int, decay_rate: float = 0.001) -> int:
        """Apply small energy decay to nodes that haven't been used recently.

        Implements use-it-or-lose-it dynamics: nodes that aren't stimulated
        by query routing gradually lose energy, shifting the cognitive
        balance toward active domains.

        Args:
            block_height: Current block height.
            decay_rate: Energy decay per block of inactivity.

        Returns:
            Number of nodes decayed.
        """
        decayed = 0
        for role, node in self.nodes.items():
            if node.last_update_block > 0 and block_height - node.last_update_block > 100:
                old_energy = node.energy
                node.energy = max(0.1, node.energy - decay_rate)
                if node.energy < old_energy:
                    decayed += 1
        return decayed

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
            "dominant_mode": self.get_dominant_cognitive_mode(),
            "energy_distribution": self.get_energy_distribution(),
            "total_violations": len(self.violations),
            "total_corrections": self._total_corrections,
            "recent_violations": [
                {
                    "expansion": v.expansion_node.value,
                    "constraint": v.constraint_node.value,
                    "ratio": v.ratio,
                    "correction": v.correction_qbc,
                    "block": v.block_height,
                }
                for v in list(self.violations)[-10:]
            ],
        }
