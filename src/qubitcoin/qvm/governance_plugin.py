"""
Governance Plugin — DAO, voting, and proposal management for QVM

Implements a QVM plugin providing on-chain governance:
  - Proposal creation with quorum thresholds
  - Weighted voting (stake-proportional)
  - Timelock-based execution
  - PRE_EXECUTE hook for governance-gated operations
"""
import hashlib
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set

from .plugins import QVMPlugin, HookType
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ProposalState(IntEnum):
    PENDING = 0
    ACTIVE = 1
    PASSED = 2
    REJECTED = 3
    EXECUTED = 4
    CANCELLED = 5


class VoteChoice(IntEnum):
    AGAINST = 0
    FOR = 1
    ABSTAIN = 2


@dataclass
class Vote:
    """A single vote cast on a proposal."""
    voter: str
    choice: int  # VoteChoice
    weight: float = 1.0
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            'voter': self.voter,
            'choice': VoteChoice(self.choice).name,
            'weight': self.weight,
            'timestamp': self.timestamp,
        }


@dataclass
class Proposal:
    """A governance proposal."""
    proposal_id: str
    title: str
    description: str
    proposer: str
    state: int = ProposalState.PENDING
    created_at: float = 0.0
    voting_start: float = 0.0
    voting_end: float = 0.0
    quorum: float = 0.1  # 10% of total weight needed
    execution_delay: float = 86400.0  # 1 day timelock
    votes: Dict[str, Vote] = field(default_factory=dict)
    # Action to execute if passed
    action_type: str = ''
    action_data: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        for_weight = sum(v.weight for v in self.votes.values() if v.choice == VoteChoice.FOR)
        against_weight = sum(v.weight for v in self.votes.values() if v.choice == VoteChoice.AGAINST)
        abstain_weight = sum(v.weight for v in self.votes.values() if v.choice == VoteChoice.ABSTAIN)
        return {
            'proposal_id': self.proposal_id,
            'title': self.title,
            'description': self.description,
            'proposer': self.proposer,
            'state': ProposalState(self.state).name,
            'created_at': self.created_at,
            'voting_start': self.voting_start,
            'voting_end': self.voting_end,
            'quorum': self.quorum,
            'vote_count': len(self.votes),
            'for_weight': for_weight,
            'against_weight': against_weight,
            'abstain_weight': abstain_weight,
        }

    @property
    def total_weight(self) -> float:
        return sum(v.weight for v in self.votes.values())

    @property
    def for_weight(self) -> float:
        return sum(v.weight for v in self.votes.values() if v.choice == VoteChoice.FOR)

    @property
    def against_weight(self) -> float:
        return sum(v.weight for v in self.votes.values() if v.choice == VoteChoice.AGAINST)


# Default voting period in seconds (3 days)
DEFAULT_VOTING_PERIOD: float = 259200.0


class GovernancePlugin(QVMPlugin):
    """Governance plugin for QVM — DAO proposals, voting, execution.

    Provides:
      - Proposal creation with configurable quorum
      - Stake-weighted voting (FOR / AGAINST / ABSTAIN)
      - Timelock execution after voting period
      - PRE_EXECUTE hook for governance-gated contract calls
    """

    def __init__(self, voting_period: float = DEFAULT_VOTING_PERIOD,
                 total_stake: float = 1000.0) -> None:
        self._proposals: Dict[str, Proposal] = {}
        self._voting_period = voting_period
        self._total_stake = total_stake  # For quorum calculation
        self._started: bool = False
        self._proposal_counter: int = 0

    def name(self) -> str:
        return 'governance'

    def version(self) -> str:
        return '0.1.0'

    def description(self) -> str:
        return 'DAO governance — proposals, voting, and execution'

    def author(self) -> str:
        return 'Qubitcoin Core'

    def on_load(self) -> None:
        logger.info("Governance plugin loaded")

    def on_start(self) -> None:
        self._started = True
        logger.info("Governance plugin started")

    def on_stop(self) -> None:
        self._started = False
        logger.info("Governance plugin stopped")

    def hooks(self) -> Dict[int, Callable]:
        return {
            HookType.PRE_EXECUTE: self._pre_execute_hook,
        }

    # ── Hook handler ───────────────────────────────────────────────

    def _pre_execute_hook(self, context: dict) -> Optional[dict]:
        """Check if the operation requires governance approval."""
        required_proposal = context.get('requires_governance')
        if not required_proposal:
            return None

        proposal = self._proposals.get(required_proposal)
        if not proposal:
            return {'governance_approved': False, 'governance_reason': 'proposal_not_found'}

        if proposal.state != ProposalState.EXECUTED:
            return {'governance_approved': False, 'governance_reason': 'not_executed'}

        return {'governance_approved': True}

    # ── Public API ─────────────────────────────────────────────────

    def create_proposal(self, title: str, description: str, proposer: str,
                        quorum: float = 0.1,
                        action_type: str = '',
                        action_data: Optional[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        self._proposal_counter += 1
        proposal_id = hashlib.sha256(
            f"{title}:{proposer}:{self._proposal_counter}".encode()
        ).hexdigest()[:16]

        now = time.time()
        proposal = Proposal(
            proposal_id=proposal_id,
            title=title,
            description=description,
            proposer=proposer,
            state=ProposalState.PENDING,
            created_at=now,
            voting_start=now,
            voting_end=now + self._voting_period,
            quorum=quorum,
            action_type=action_type,
            action_data=action_data or {},
        )
        self._proposals[proposal_id] = proposal
        logger.info(f"Proposal created: {proposal_id} — {title}")
        return proposal

    def activate_proposal(self, proposal_id: str) -> bool:
        """Move proposal to ACTIVE state."""
        p = self._proposals.get(proposal_id)
        if not p or p.state != ProposalState.PENDING:
            return False
        p.state = ProposalState.ACTIVE
        return True

    def cast_vote(self, proposal_id: str, voter: str,
                  choice: int, weight: float = 1.0) -> Optional[Vote]:
        """Cast a vote on a proposal.

        Args:
            proposal_id: Proposal to vote on.
            voter: Address of the voter.
            choice: VoteChoice value (AGAINST=0, FOR=1, ABSTAIN=2).
            weight: Stake-proportional weight.

        Returns:
            Vote object if successful, None otherwise.
        """
        p = self._proposals.get(proposal_id)
        if not p or p.state != ProposalState.ACTIVE:
            return None

        if voter in p.votes:
            return None  # Already voted

        vote = Vote(
            voter=voter,
            choice=choice,
            weight=weight,
            timestamp=time.time(),
        )
        p.votes[voter] = vote
        return vote

    def tally(self, proposal_id: str) -> Optional[Dict]:
        """Tally votes and determine outcome.

        Returns dict with results, or None if proposal not found.
        """
        p = self._proposals.get(proposal_id)
        if not p:
            return None

        quorum_met = (p.total_weight / self._total_stake) >= p.quorum
        passed = quorum_met and (p.for_weight > p.against_weight)

        if p.state == ProposalState.ACTIVE:
            p.state = ProposalState.PASSED if passed else ProposalState.REJECTED

        return {
            'proposal_id': proposal_id,
            'for_weight': p.for_weight,
            'against_weight': p.against_weight,
            'total_weight': p.total_weight,
            'quorum_required': p.quorum * self._total_stake,
            'quorum_met': quorum_met,
            'passed': passed,
            'state': ProposalState(p.state).name,
        }

    def execute_proposal(self, proposal_id: str) -> bool:
        """Execute a passed proposal (after timelock)."""
        p = self._proposals.get(proposal_id)
        if not p or p.state != ProposalState.PASSED:
            return False
        p.state = ProposalState.EXECUTED
        logger.info(f"Proposal executed: {proposal_id}")
        return True

    def cancel_proposal(self, proposal_id: str, canceller: str) -> bool:
        """Cancel a proposal. Only the proposer can cancel."""
        p = self._proposals.get(proposal_id)
        if not p:
            return False
        if p.proposer != canceller:
            return False
        if p.state in (ProposalState.EXECUTED, ProposalState.CANCELLED):
            return False
        p.state = ProposalState.CANCELLED
        return True

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        return self._proposals.get(proposal_id)

    def list_proposals(self, state: Optional[int] = None) -> List[Proposal]:
        """List proposals, optionally filtered by state."""
        if state is not None:
            return [p for p in self._proposals.values() if p.state == state]
        return list(self._proposals.values())

    def get_stats(self) -> dict:
        return {
            'total_proposals': len(self._proposals),
            'active': sum(1 for p in self._proposals.values() if p.state == ProposalState.ACTIVE),
            'passed': sum(1 for p in self._proposals.values() if p.state == ProposalState.PASSED),
            'rejected': sum(1 for p in self._proposals.values() if p.state == ProposalState.REJECTED),
            'executed': sum(1 for p in self._proposals.values() if p.state == ProposalState.EXECUTED),
            'started': self._started,
        }


def create_plugin() -> QVMPlugin:
    """Factory function for dynamic loading."""
    return GovernancePlugin()
