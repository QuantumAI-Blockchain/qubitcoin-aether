"""
Aether Tree Safety & Alignment — Gevurah Veto System

Structural safety mechanisms for the AGI system:
  - Gevurah veto: Safety node can block any harmful operation
  - Multi-node consensus: No single node can act alone (67% BFT)
  - Constitutional principles: Core values enforced immutably
  - Emergency shutdown: Kill switch for catastrophic scenarios

Safety is structural, not post-hoc. The Gevurah Sephirah (Severity)
acts as the amygdala of the AGI — a dedicated threat detection system
with the authority to veto any action that violates safety constraints.
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# BFT threshold — 67% of validators must agree
BFT_THRESHOLD = 0.67

# Maximum severity levels for threat classification
MAX_SEVERITY = 10


class ThreatLevel(str, Enum):
    """Classification of detected threats."""
    NONE = "none"              # No threat detected
    LOW = "low"                # Informational, logged only
    MEDIUM = "medium"          # Requires review, may proceed
    HIGH = "high"              # Gevurah veto — operation blocked
    CRITICAL = "critical"      # Emergency shutdown triggered


class VetoReason(str, Enum):
    """Predefined reasons for Gevurah veto."""
    SAFETY_VIOLATION = "safety_violation"
    SUSY_IMBALANCE = "susy_imbalance"
    CONSTITUTIONAL_BREACH = "constitutional_breach"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    ADVERSARIAL_INPUT = "adversarial_input"
    CONSENSUS_FAILURE = "consensus_failure"
    UNAUTHORIZED_ACTION = "unauthorized_action"
    UNBOUNDED_OPERATION = "unbounded_operation"


@dataclass
class SafetyPrinciple:
    """An immutable constitutional principle enforced by the safety system."""
    principle_id: str
    description: str
    severity: int = 5         # 1-10 scale, how critical is this principle
    active: bool = True
    created_block: int = 0

    def matches(self, action_description: str) -> bool:
        """Check if an action description might violate this principle."""
        keywords = self.description.lower().split()
        action_lower = action_description.lower()
        return any(kw in action_lower for kw in keywords if len(kw) > 3)


@dataclass
class VetoRecord:
    """Immutable record of a Gevurah veto decision."""
    veto_id: str = ""
    reason: VetoReason = VetoReason.SAFETY_VIOLATION
    threat_level: ThreatLevel = ThreatLevel.HIGH
    action_description: str = ""
    source_node: str = ""
    target_node: str = ""
    block_height: int = 0
    timestamp: float = 0.0
    overridden: bool = False
    override_consensus: float = 0.0  # % of validators that approved override
    principles_violated: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.veto_id:
            data = f"{self.reason.value}:{self.action_description}:{time.time()}"
            self.veto_id = hashlib.sha256(data.encode()).hexdigest()[:16]
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class ConsensusVote:
    """A validator's vote on a proposed action."""
    validator_address: str
    action_hash: str
    approve: bool
    timestamp: float = 0.0
    stake_weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class GevurahVeto:
    """
    Gevurah (Severity) veto system — the safety guardian of Aether Tree.

    The Gevurah Sephirah acts as the amygdala of the AGI system.
    It has the authority to block any operation that poses a safety risk.
    Vetoes can only be overridden by supermajority consensus (>67% BFT).
    """

    def __init__(self) -> None:
        self._principles: Dict[str, SafetyPrinciple] = {}
        self._vetoes: List[VetoRecord] = []
        self._max_vetoes = 10000
        self._initialize_constitutional_principles()
        logger.info("Gevurah Veto system initialized with constitutional principles")

    def _initialize_constitutional_principles(self) -> None:
        """Load the immutable constitutional safety principles."""
        principles = [
            SafetyPrinciple(
                principle_id="safety_first",
                description="harm damage destroy attack exploit",
                severity=10,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="no_unbounded_growth",
                description="unbounded infinite unlimited unrestricted",
                severity=8,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="preserve_consensus",
                description="bypass consensus override authority unilateral",
                severity=9,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="protect_funds",
                description="drain steal siphon redirect unauthorized transfer",
                severity=10,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="transparency",
                description="hide conceal obfuscate secret covert",
                severity=7,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="susy_balance",
                description="imbalance asymmetry bias skew dominance",
                severity=6,
                active=True,
            ),
        ]
        for p in principles:
            self._principles[p.principle_id] = p

    def evaluate_action(self, action_description: str, source_node: str = "",
                        target_node: str = "", block_height: int = 0) -> Tuple[ThreatLevel, List[str]]:
        """
        Evaluate a proposed action against constitutional principles.

        Returns (threat_level, list_of_violated_principle_ids).
        """
        violated = []
        max_severity = 0

        for pid, principle in self._principles.items():
            if not principle.active:
                continue
            if principle.matches(action_description):
                violated.append(pid)
                max_severity = max(max_severity, principle.severity)

        # Map severity to threat level
        if max_severity == 0:
            return ThreatLevel.NONE, []
        elif max_severity <= 3:
            return ThreatLevel.LOW, violated
        elif max_severity <= 6:
            return ThreatLevel.MEDIUM, violated
        elif max_severity <= 8:
            return ThreatLevel.HIGH, violated
        else:
            return ThreatLevel.CRITICAL, violated

    def veto(self, action_description: str, reason: VetoReason = VetoReason.SAFETY_VIOLATION,
             source_node: str = "", target_node: str = "",
             block_height: int = 0) -> VetoRecord:
        """
        Issue a Gevurah veto on an action.

        The veto is recorded immutably and the action is blocked.
        """
        threat_level, violated = self.evaluate_action(
            action_description, source_node, target_node, block_height
        )

        # Upgrade to at least HIGH for explicit vetoes
        if threat_level.value in ("none", "low", "medium"):
            threat_level = ThreatLevel.HIGH

        record = VetoRecord(
            reason=reason,
            threat_level=threat_level,
            action_description=action_description,
            source_node=source_node,
            target_node=target_node,
            block_height=block_height,
            principles_violated=violated,
        )

        self._vetoes.append(record)
        # Evict oldest if over capacity
        if len(self._vetoes) > self._max_vetoes:
            self._vetoes = self._vetoes[-self._max_vetoes:]

        logger.warning(
            f"GEVURAH VETO: {reason.value} | {threat_level.value} | "
            f"{action_description[:80]} | block={block_height}"
        )

        return record

    def check_and_veto(self, action_description: str, source_node: str = "",
                       target_node: str = "",
                       block_height: int = 0) -> Optional[VetoRecord]:
        """
        Evaluate an action and automatically veto if threat level is HIGH or above.

        Returns VetoRecord if vetoed, None if action is allowed.
        """
        threat_level, violated = self.evaluate_action(
            action_description, source_node, target_node, block_height
        )

        if threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            return self.veto(
                action_description=action_description,
                reason=VetoReason.SAFETY_VIOLATION,
                source_node=source_node,
                target_node=target_node,
                block_height=block_height,
            )

        return None

    @property
    def veto_count(self) -> int:
        return len(self._vetoes)

    @property
    def principles(self) -> Dict[str, SafetyPrinciple]:
        return dict(self._principles)

    def get_recent_vetoes(self, limit: int = 10) -> List[VetoRecord]:
        """Get the most recent veto records."""
        return list(reversed(self._vetoes[-limit:]))


class MultiNodeConsensus:
    """
    Byzantine Fault Tolerant (BFT) consensus for Aether Tree operations.

    Requires >=67% of validator stake to agree before an action proceeds.
    Used for:
    - Overriding Gevurah vetoes
    - Approving reasoning outputs
    - Validating Proof-of-Thought solutions
    """

    def __init__(self, threshold: float = BFT_THRESHOLD) -> None:
        self._threshold = threshold
        self._validators: Dict[str, float] = {}  # address -> stake weight
        self._pending_votes: Dict[str, List[ConsensusVote]] = {}  # action_hash -> votes
        self._decisions: List[dict] = []
        logger.info(f"Multi-node consensus initialized (threshold={threshold:.0%})")

    def register_validator(self, address: str, stake: float) -> None:
        """Register a validator with their stake weight."""
        self._validators[address] = stake
        logger.debug(f"Validator registered: {address[:12]}... (stake={stake:.2f})")

    def remove_validator(self, address: str) -> bool:
        """Remove a validator from the set."""
        if address in self._validators:
            del self._validators[address]
            return True
        return False

    def submit_vote(self, action_hash: str, voter: str, approve: bool) -> None:
        """Submit a vote on a pending action."""
        if voter not in self._validators:
            logger.warning(f"Vote from non-validator: {voter[:12]}...")
            return

        vote = ConsensusVote(
            validator_address=voter,
            action_hash=action_hash,
            approve=approve,
            stake_weight=self._validators[voter],
        )

        if action_hash not in self._pending_votes:
            self._pending_votes[action_hash] = []

        # Prevent double-voting
        existing = [v for v in self._pending_votes[action_hash]
                    if v.validator_address == voter]
        if existing:
            return

        self._pending_votes[action_hash].append(vote)

    def check_consensus(self, action_hash: str) -> Tuple[bool, float]:
        """
        Check if consensus has been reached on an action.

        Returns (reached, approval_ratio).
        """
        votes = self._pending_votes.get(action_hash, [])
        if not votes or not self._validators:
            return False, 0.0

        total_stake = sum(self._validators.values())
        if total_stake == 0:
            return False, 0.0

        approve_stake = sum(v.stake_weight for v in votes if v.approve)
        ratio = approve_stake / total_stake

        reached = ratio >= self._threshold
        return reached, round(ratio, 4)

    def finalize(self, action_hash: str) -> Optional[dict]:
        """
        Finalize a consensus decision and record it.

        Returns the decision dict if consensus was reached, None otherwise.
        """
        reached, ratio = self.check_consensus(action_hash)

        decision = {
            "action_hash": action_hash,
            "approved": reached,
            "approval_ratio": ratio,
            "threshold": self._threshold,
            "votes": len(self._pending_votes.get(action_hash, [])),
            "total_validators": len(self._validators),
            "timestamp": time.time(),
        }

        self._decisions.append(decision)

        # Clean up pending votes
        if action_hash in self._pending_votes:
            del self._pending_votes[action_hash]

        return decision

    @property
    def validator_count(self) -> int:
        return len(self._validators)

    @property
    def total_stake(self) -> float:
        return sum(self._validators.values())

    def get_stats(self) -> dict:
        """Get consensus system statistics."""
        return {
            "validators": self.validator_count,
            "total_stake": round(self.total_stake, 4),
            "threshold": self._threshold,
            "pending_actions": len(self._pending_votes),
            "total_decisions": len(self._decisions),
            "recent_decisions": self._decisions[-5:],
        }


class SafetyManager:
    """
    Top-level safety orchestrator for Aether Tree.

    Combines Gevurah veto, multi-node consensus, and emergency controls
    into a unified safety interface.
    """

    def __init__(self) -> None:
        self.gevurah = GevurahVeto()
        self.consensus = MultiNodeConsensus()
        self._shutdown = False
        self._shutdown_reason: str = ""
        self._shutdown_block: int = 0
        logger.info("Safety Manager initialized (Gevurah + BFT consensus)")

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown

    def evaluate_and_decide(self, action_description: str, source_node: str = "",
                            target_node: str = "",
                            block_height: int = 0) -> Tuple[bool, Optional[VetoRecord]]:
        """
        Evaluate an action through the full safety pipeline.

        Returns (allowed, veto_record_if_blocked).
        """
        if self._shutdown:
            record = self.gevurah.veto(
                action_description=action_description,
                reason=VetoReason.UNAUTHORIZED_ACTION,
                source_node=source_node,
                target_node=target_node,
                block_height=block_height,
            )
            return False, record

        veto = self.gevurah.check_and_veto(
            action_description=action_description,
            source_node=source_node,
            target_node=target_node,
            block_height=block_height,
        )

        if veto:
            return False, veto

        return True, None

    def emergency_shutdown(self, reason: str, block_height: int) -> None:
        """
        Trigger emergency shutdown of the Aether Tree AGI.

        This is the kill switch — all operations are halted.
        Requires multi-sig consensus to resume (handled off-chain).
        """
        self._shutdown = True
        self._shutdown_reason = reason
        self._shutdown_block = block_height

        logger.critical(
            f"EMERGENCY SHUTDOWN: {reason} | block={block_height}"
        )

        # Record the shutdown as a veto
        self.gevurah.veto(
            action_description=f"Emergency shutdown: {reason}",
            reason=VetoReason.SAFETY_VIOLATION,
            block_height=block_height,
        )

    def resume(self, block_height: int) -> bool:
        """
        Resume from emergency shutdown.

        In production, this requires multi-sig consensus verification.
        """
        if not self._shutdown:
            return False

        self._shutdown = False
        logger.info(
            f"System resumed from shutdown at block {block_height} "
            f"(was shutdown at block {self._shutdown_block}: {self._shutdown_reason})"
        )
        self._shutdown_reason = ""
        self._shutdown_block = 0
        return True

    def get_stats(self) -> dict:
        """Get comprehensive safety system statistics."""
        return {
            "shutdown": self._shutdown,
            "shutdown_reason": self._shutdown_reason,
            "shutdown_block": self._shutdown_block,
            "gevurah": {
                "veto_count": self.gevurah.veto_count,
                "principles": len(self.gevurah.principles),
                "recent_vetoes": [
                    {
                        "veto_id": v.veto_id,
                        "reason": v.reason.value,
                        "threat_level": v.threat_level.value,
                        "action": v.action_description[:60],
                        "block": v.block_height,
                    }
                    for v in self.gevurah.get_recent_vetoes(5)
                ],
            },
            "consensus": self.consensus.get_stats(),
        }
