"""
Proof-of-Thought Task Protocol — Reasoning Task Marketplace

Implements the economic protocol for Proof-of-Thought consensus:
  1. Task Submission: User/system submits reasoning task with QBC bounty
  2. Node Solution: Sephirah node uses reasoning engine to solve
  3. Proposal: Node submits solution + proof hash
  4. Validation: Multiple validators verify via consensus
  5. Reward/Slash: Correct solutions earn QBC bounty; incorrect lose stake

Economic parameters:
  - Min task bounty: 1 QBC
  - Min validator stake: 100 QBC
  - Slash penalty: 50% of stake
  - Unstaking delay: 7 days (2,100 blocks at 3.3s/block ≈ ~1.83 hours per 2000 blocks)
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Protocol constants
MIN_TASK_BOUNTY = 1.0            # QBC
MIN_VALIDATOR_STAKE = 100.0      # QBC
SLASH_PENALTY = 0.50             # 50% of stake
VALIDATION_THRESHOLD = 0.67      # 67% BFT
UNSTAKING_DELAY_BLOCKS = 183272  # ~7 days at 3.3s/block


class TaskStatus(str, Enum):
    """Lifecycle status of a reasoning task."""
    OPEN = "open"                # Awaiting solutions
    CLAIMED = "claimed"          # A node is working on it
    PROPOSED = "proposed"        # Solution submitted, awaiting validation
    VALIDATING = "validating"    # Validators are voting
    COMPLETED = "completed"      # Solution accepted, reward distributed
    REJECTED = "rejected"        # Solution rejected, solver slashed
    EXPIRED = "expired"          # No valid solution within timeout


@dataclass
class ReasoningTask:
    """A reasoning task in the Proof-of-Thought marketplace."""
    task_id: str = ""
    submitter: str = ""
    description: str = ""
    query_type: str = "general"   # general, deductive, inductive, abductive
    bounty_qbc: float = 1.0
    status: TaskStatus = TaskStatus.OPEN
    created_block: int = 0
    timeout_blocks: int = 1000    # Expires after this many blocks
    claimed_by: str = ""
    solution_hash: str = ""
    solution_data: dict = field(default_factory=dict)
    validation_votes: Dict[str, bool] = field(default_factory=dict)
    reward_distributed: bool = False
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.task_id:
            data = f"{self.submitter}:{self.description}:{time.time()}"
            self.task_id = hashlib.sha256(data.encode()).hexdigest()[:16]
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class Validator:
    """A registered Proof-of-Thought validator."""
    address: str
    stake_qbc: float = 0.0
    staked_block: int = 0
    unstaking_block: int = 0      # 0 = not unstaking
    is_active: bool = True
    tasks_validated: int = 0
    correct_validations: int = 0
    total_slashed: float = 0.0
    total_rewards: float = 0.0

    @property
    def accuracy(self) -> float:
        if self.tasks_validated == 0:
            return 0.0
        return self.correct_validations / self.tasks_validated

    @property
    def is_unstaking(self) -> bool:
        return self.unstaking_block > 0


class TaskMarket:
    """
    Reasoning task marketplace for Proof-of-Thought consensus.

    Manages the lifecycle of reasoning tasks: submission → claiming →
    solving → validation → reward/slash distribution.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, ReasoningTask] = {}
        self._max_tasks = 10000
        logger.info("Task Market initialized")

    def submit_task(self, submitter: str, description: str,
                    bounty_qbc: float, query_type: str = "general",
                    block_height: int = 0,
                    timeout_blocks: int = 1000) -> Optional[ReasoningTask]:
        """Submit a new reasoning task with a QBC bounty."""
        if bounty_qbc < MIN_TASK_BOUNTY:
            logger.warning(f"Task bounty {bounty_qbc} below minimum {MIN_TASK_BOUNTY}")
            return None

        task = ReasoningTask(
            submitter=submitter,
            description=description,
            query_type=query_type,
            bounty_qbc=bounty_qbc,
            created_block=block_height,
            timeout_blocks=timeout_blocks,
        )

        self._tasks[task.task_id] = task

        # Evict oldest completed/expired tasks if over capacity
        if len(self._tasks) > self._max_tasks:
            self._evict_old_tasks()

        logger.info(f"Task submitted: {task.task_id} bounty={bounty_qbc} QBC")
        return task

    def claim_task(self, task_id: str, solver_address: str) -> bool:
        """Claim an open task for solving."""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.OPEN:
            return False

        task.status = TaskStatus.CLAIMED
        task.claimed_by = solver_address
        logger.debug(f"Task {task_id} claimed by {solver_address[:12]}...")
        return True

    def submit_solution(self, task_id: str, solver_address: str,
                        solution_data: dict) -> bool:
        """Submit a solution for a claimed task."""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.CLAIMED:
            return False
        if task.claimed_by != solver_address:
            return False

        # Compute solution hash
        solution_str = hashlib.sha256(
            str(sorted(solution_data.items())).encode()
        ).hexdigest()

        task.solution_hash = solution_str
        task.solution_data = solution_data
        task.status = TaskStatus.PROPOSED
        logger.info(f"Solution proposed for task {task_id}: {solution_str[:16]}...")
        return True

    def get_open_tasks(self, limit: int = 20) -> List[ReasoningTask]:
        """Get tasks available for claiming."""
        return sorted(
            [t for t in self._tasks.values() if t.status == TaskStatus.OPEN],
            key=lambda t: -t.bounty_qbc,
        )[:limit]

    def get_task(self, task_id: str) -> Optional[ReasoningTask]:
        return self._tasks.get(task_id)

    def expire_tasks(self, current_block: int) -> int:
        """Expire tasks that have exceeded their timeout."""
        expired = 0
        for task in self._tasks.values():
            if task.status in (TaskStatus.OPEN, TaskStatus.CLAIMED):
                if current_block - task.created_block > task.timeout_blocks:
                    task.status = TaskStatus.EXPIRED
                    expired += 1
        return expired

    def _evict_old_tasks(self) -> None:
        """Remove oldest completed/expired tasks to bound memory."""
        removable = [
            tid for tid, t in self._tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.REJECTED, TaskStatus.EXPIRED)
        ]
        removable.sort(key=lambda tid: self._tasks[tid].timestamp)
        for tid in removable[:len(removable) // 2]:
            del self._tasks[tid]

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def open_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.OPEN)

    def get_stats(self) -> dict:
        status_counts: Dict[str, int] = {}
        for t in self._tasks.values():
            status_counts[t.status.value] = status_counts.get(t.status.value, 0) + 1
        total_bounty = sum(t.bounty_qbc for t in self._tasks.values()
                           if t.status == TaskStatus.OPEN)
        return {
            "total_tasks": self.task_count,
            "status_counts": status_counts,
            "total_open_bounty": round(total_bounty, 4),
        }


class ValidatorRegistry:
    """
    Manages Proof-of-Thought validators: staking, unstaking, and performance tracking.
    """

    def __init__(self) -> None:
        self._validators: Dict[str, Validator] = {}
        logger.info("Validator Registry initialized")

    def stake(self, address: str, amount: float, block_height: int) -> bool:
        """Register or increase stake for a validator."""
        if amount < MIN_VALIDATOR_STAKE:
            logger.warning(f"Stake {amount} below minimum {MIN_VALIDATOR_STAKE}")
            return False

        if address in self._validators:
            v = self._validators[address]
            v.stake_qbc += amount
            v.is_active = True
            v.unstaking_block = 0
        else:
            self._validators[address] = Validator(
                address=address,
                stake_qbc=amount,
                staked_block=block_height,
            )

        logger.info(f"Validator {address[:12]}... staked {amount} QBC")
        return True

    def request_unstake(self, address: str, block_height: int) -> bool:
        """Request to unstake — enters cooldown period."""
        v = self._validators.get(address)
        if not v or not v.is_active:
            return False

        v.unstaking_block = block_height + UNSTAKING_DELAY_BLOCKS
        v.is_active = False
        logger.info(f"Validator {address[:12]}... unstaking at block {v.unstaking_block}")
        return True

    def complete_unstake(self, address: str, block_height: int) -> float:
        """Complete unstaking after cooldown. Returns QBC to return."""
        v = self._validators.get(address)
        if not v or v.unstaking_block == 0:
            return 0.0
        if block_height < v.unstaking_block:
            return 0.0  # Cooldown not complete

        amount = v.stake_qbc
        del self._validators[address]
        logger.info(f"Validator {address[:12]}... unstaked {amount} QBC")
        return amount

    def slash(self, address: str, reason: str) -> float:
        """Slash a validator's stake. Returns the slashed amount."""
        v = self._validators.get(address)
        if not v:
            return 0.0

        slash_amount = v.stake_qbc * SLASH_PENALTY
        v.stake_qbc -= slash_amount
        v.total_slashed += slash_amount
        v.is_active = v.stake_qbc >= MIN_VALIDATOR_STAKE

        logger.warning(f"Validator {address[:12]}... slashed {slash_amount} QBC: {reason}")
        return slash_amount

    def reward(self, address: str, amount: float) -> bool:
        """Reward a validator for correct validation."""
        v = self._validators.get(address)
        if not v:
            return False
        v.total_rewards += amount
        v.correct_validations += 1
        return True

    def get_active_validators(self) -> List[Validator]:
        """Get all active validators sorted by stake."""
        return sorted(
            [v for v in self._validators.values() if v.is_active],
            key=lambda v: -v.stake_qbc,
        )

    def get_validator(self, address: str) -> Optional[Validator]:
        return self._validators.get(address)

    @property
    def validator_count(self) -> int:
        return len(self._validators)

    @property
    def active_count(self) -> int:
        return sum(1 for v in self._validators.values() if v.is_active)

    @property
    def total_stake(self) -> float:
        return sum(v.stake_qbc for v in self._validators.values())

    def get_stats(self) -> dict:
        active = self.get_active_validators()
        return {
            "total_validators": self.validator_count,
            "active_validators": self.active_count,
            "total_stake": round(self.total_stake, 4),
            "avg_accuracy": (
                round(sum(v.accuracy for v in active) / max(1, len(active)), 4)
                if active else 0.0
            ),
            "top_validators": [
                {
                    "address": v.address[:16] + "...",
                    "stake": round(v.stake_qbc, 4),
                    "accuracy": round(v.accuracy, 4),
                    "validations": v.tasks_validated,
                }
                for v in active[:5]
            ],
        }


class ProofOfThoughtProtocol:
    """
    Orchestrates the full Proof-of-Thought lifecycle:
    task submission → claiming → solving → validation → reward/slash.
    """

    def __init__(self) -> None:
        self.task_market = TaskMarket()
        self.validator_registry = ValidatorRegistry()
        logger.info("Proof-of-Thought Protocol initialized")

    def validate_solution(self, task_id: str, validator_address: str,
                          approve: bool) -> bool:
        """Submit a validation vote on a proposed solution."""
        task = self.task_market.get_task(task_id)
        if not task or task.status not in (TaskStatus.PROPOSED, TaskStatus.VALIDATING):
            return False

        validator = self.validator_registry.get_validator(validator_address)
        if not validator or not validator.is_active:
            return False

        task.status = TaskStatus.VALIDATING
        task.validation_votes[validator_address] = approve
        validator.tasks_validated += 1

        return True

    def finalize_task(self, task_id: str) -> Optional[dict]:
        """
        Finalize a task after validation voting.

        Checks consensus: if >=67% approve, reward solver.
        If rejected, slash solver's stake.
        """
        task = self.task_market.get_task(task_id)
        if not task or task.status != TaskStatus.VALIDATING:
            return None

        if not task.validation_votes:
            return None

        # Calculate stake-weighted approval
        total_stake = 0.0
        approve_stake = 0.0
        for addr, vote in task.validation_votes.items():
            v = self.validator_registry.get_validator(addr)
            if v:
                total_stake += v.stake_qbc
                if vote:
                    approve_stake += v.stake_qbc

        if total_stake == 0:
            return None

        approval_ratio = approve_stake / total_stake
        approved = approval_ratio >= VALIDATION_THRESHOLD

        if approved:
            task.status = TaskStatus.COMPLETED
            task.reward_distributed = True
            # Reward validators who voted correctly
            for addr, vote in task.validation_votes.items():
                if vote:
                    self.validator_registry.reward(
                        addr, task.bounty_qbc * 0.1 / max(1, len(task.validation_votes))
                    )
        else:
            task.status = TaskStatus.REJECTED
            # Slash the solver
            if task.claimed_by:
                self.validator_registry.slash(
                    task.claimed_by, "Solution rejected by validators"
                )

        result = {
            "task_id": task_id,
            "approved": approved,
            "approval_ratio": round(approval_ratio, 4),
            "votes": len(task.validation_votes),
            "bounty": task.bounty_qbc,
            "solver": task.claimed_by,
        }

        logger.info(
            f"Task {task_id} finalized: {'APPROVED' if approved else 'REJECTED'} "
            f"({approval_ratio:.0%})"
        )

        return result

    def process_block(self, block_height: int) -> dict:
        """Per-block maintenance: expire old tasks."""
        expired = self.task_market.expire_tasks(block_height)
        return {
            "expired_tasks": expired,
            "open_tasks": self.task_market.open_count,
            "active_validators": self.validator_registry.active_count,
        }

    def get_stats(self) -> dict:
        return {
            "task_market": self.task_market.get_stats(),
            "validators": self.validator_registry.get_stats(),
        }
