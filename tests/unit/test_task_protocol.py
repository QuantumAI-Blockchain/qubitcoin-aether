"""Unit tests for Proof-of-Thought task protocol."""
import pytest


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_all_statuses(self):
        from qubitcoin.aether.task_protocol import TaskStatus
        assert len(TaskStatus) == 7

    def test_lifecycle(self):
        from qubitcoin.aether.task_protocol import TaskStatus
        assert TaskStatus.OPEN == "open"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.REJECTED == "rejected"


class TestReasoningTask:
    """Test ReasoningTask dataclass."""

    def test_auto_id(self):
        from qubitcoin.aether.task_protocol import ReasoningTask
        task = ReasoningTask(submitter="addr_a", description="test")
        assert len(task.task_id) == 16

    def test_auto_timestamp(self):
        from qubitcoin.aether.task_protocol import ReasoningTask
        task = ReasoningTask(submitter="addr_a", description="test")
        assert task.timestamp > 0

    def test_default_status(self):
        from qubitcoin.aether.task_protocol import ReasoningTask, TaskStatus
        task = ReasoningTask(submitter="addr_a", description="test")
        assert task.status == TaskStatus.OPEN


class TestTaskMarket:
    """Test reasoning task marketplace."""

    def test_submit_task(self):
        from qubitcoin.aether.task_protocol import TaskMarket
        tm = TaskMarket()
        task = tm.submit_task("addr_a", "What is phi?", bounty_qbc=2.0)
        assert task is not None
        assert task.bounty_qbc == 2.0
        assert tm.task_count == 1

    def test_submit_below_minimum(self):
        from qubitcoin.aether.task_protocol import TaskMarket
        tm = TaskMarket()
        task = tm.submit_task("addr_a", "cheap task", bounty_qbc=0.5)
        assert task is None  # Below MIN_TASK_BOUNTY

    def test_claim_task(self):
        from qubitcoin.aether.task_protocol import TaskMarket, TaskStatus
        tm = TaskMarket()
        task = tm.submit_task("addr_a", "solve this", bounty_qbc=5.0)
        assert tm.claim_task(task.task_id, "solver_b") is True
        assert task.status == TaskStatus.CLAIMED
        assert task.claimed_by == "solver_b"

    def test_claim_nonexistent(self):
        from qubitcoin.aether.task_protocol import TaskMarket
        tm = TaskMarket()
        assert tm.claim_task("nonexistent", "solver") is False

    def test_submit_solution(self):
        from qubitcoin.aether.task_protocol import TaskMarket, TaskStatus
        tm = TaskMarket()
        task = tm.submit_task("addr_a", "solve x", bounty_qbc=3.0)
        tm.claim_task(task.task_id, "solver_b")
        result = tm.submit_solution(task.task_id, "solver_b", {"answer": 42})
        assert result is True
        assert task.status == TaskStatus.PROPOSED
        assert task.solution_hash

    def test_submit_solution_wrong_solver(self):
        from qubitcoin.aether.task_protocol import TaskMarket
        tm = TaskMarket()
        task = tm.submit_task("addr_a", "solve x", bounty_qbc=3.0)
        tm.claim_task(task.task_id, "solver_b")
        result = tm.submit_solution(task.task_id, "imposter", {"answer": 42})
        assert result is False

    def test_get_open_tasks(self):
        from qubitcoin.aether.task_protocol import TaskMarket
        tm = TaskMarket()
        tm.submit_task("a", "task1", bounty_qbc=1.0)
        tm.submit_task("b", "task2", bounty_qbc=5.0)
        tm.submit_task("c", "task3", bounty_qbc=3.0)
        open_tasks = tm.get_open_tasks()
        assert len(open_tasks) == 3
        # Sorted by bounty descending
        assert open_tasks[0].bounty_qbc == 5.0

    def test_expire_tasks(self):
        from qubitcoin.aether.task_protocol import TaskMarket, TaskStatus
        tm = TaskMarket()
        task = tm.submit_task("a", "old task", bounty_qbc=1.0, block_height=0, timeout_blocks=100)
        expired = tm.expire_tasks(current_block=200)
        assert expired == 1
        assert task.status == TaskStatus.EXPIRED

    def test_get_stats(self):
        from qubitcoin.aether.task_protocol import TaskMarket
        tm = TaskMarket()
        tm.submit_task("a", "t1", bounty_qbc=2.0)
        tm.submit_task("b", "t2", bounty_qbc=3.0)
        stats = tm.get_stats()
        assert stats["total_tasks"] == 2
        assert stats["total_open_bounty"] == 5.0


class TestValidatorRegistry:
    """Test validator registry."""

    def test_stake(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        assert vr.stake("v1", 200.0, block_height=1) is True
        assert vr.validator_count == 1
        assert vr.total_stake == 200.0

    def test_stake_below_minimum(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        assert vr.stake("v1", 50.0, block_height=1) is False

    def test_increase_stake(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        vr.stake("v1", 200.0, block_height=1)
        vr.stake("v1", 100.0, block_height=2)
        assert vr.get_validator("v1").stake_qbc == 300.0

    def test_request_unstake(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        vr.stake("v1", 200.0, block_height=1)
        assert vr.request_unstake("v1", block_height=100) is True
        v = vr.get_validator("v1")
        assert not v.is_active
        assert v.is_unstaking

    def test_complete_unstake(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry, UNSTAKING_DELAY_BLOCKS
        vr = ValidatorRegistry()
        vr.stake("v1", 200.0, block_height=1)
        vr.request_unstake("v1", block_height=100)
        # Too early
        amount = vr.complete_unstake("v1", block_height=100 + 10)
        assert amount == 0.0
        # After delay
        amount = vr.complete_unstake("v1", block_height=100 + UNSTAKING_DELAY_BLOCKS + 1)
        assert amount == 200.0
        assert vr.validator_count == 0

    def test_slash(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        vr.stake("v1", 200.0, block_height=1)
        slashed = vr.slash("v1", "bad validation")
        assert slashed == 100.0  # 50% of 200
        assert vr.get_validator("v1").stake_qbc == 100.0

    def test_slash_below_minimum_deactivates(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        vr.stake("v1", 100.0, block_height=1)
        vr.slash("v1", "reason")  # Drops to 50 QBC
        assert not vr.get_validator("v1").is_active

    def test_reward(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        vr.stake("v1", 200.0, block_height=1)
        assert vr.reward("v1", 5.0) is True
        assert vr.get_validator("v1").total_rewards == 5.0
        assert vr.get_validator("v1").correct_validations == 1

    def test_accuracy(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        vr.stake("v1", 200.0, block_height=1)
        v = vr.get_validator("v1")
        assert v.accuracy == 0.0
        v.tasks_validated = 10
        v.correct_validations = 8
        assert v.accuracy == 0.8

    def test_get_active_validators(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        vr.stake("v1", 200.0, block_height=1)
        vr.stake("v2", 500.0, block_height=2)
        vr.stake("v3", 100.0, block_height=3)
        active = vr.get_active_validators()
        assert len(active) == 3
        assert active[0].address == "v2"  # Highest stake first

    def test_get_stats(self):
        from qubitcoin.aether.task_protocol import ValidatorRegistry
        vr = ValidatorRegistry()
        vr.stake("v1", 300.0, block_height=1)
        stats = vr.get_stats()
        assert stats["total_validators"] == 1
        assert stats["total_stake"] == 300.0


class TestProofOfThoughtProtocol:
    """Test full PoT protocol lifecycle."""

    def test_init(self):
        from qubitcoin.aether.task_protocol import ProofOfThoughtProtocol
        pot = ProofOfThoughtProtocol()
        assert pot.task_market is not None
        assert pot.validator_registry is not None

    def test_full_lifecycle_approved(self):
        from qubitcoin.aether.task_protocol import ProofOfThoughtProtocol, TaskStatus
        pot = ProofOfThoughtProtocol()

        # Setup validators
        pot.validator_registry.stake("v1", 200.0, 1)
        pot.validator_registry.stake("v2", 200.0, 1)
        pot.validator_registry.stake("v3", 200.0, 1)

        # Submit task
        task = pot.task_market.submit_task("user1", "What is consciousness?", 5.0)

        # Claim
        pot.task_market.claim_task(task.task_id, "v1")

        # Submit solution
        pot.task_market.submit_solution(task.task_id, "v1", {"answer": "phi > 3.0"})

        # Validate (2/3 approve = 66.7%, need 67%)
        pot.validate_solution(task.task_id, "v1", approve=True)
        pot.validate_solution(task.task_id, "v2", approve=True)
        pot.validate_solution(task.task_id, "v3", approve=True)

        # Finalize
        result = pot.finalize_task(task.task_id)
        assert result is not None
        assert result["approved"] is True
        assert task.status == TaskStatus.COMPLETED

    def test_full_lifecycle_rejected(self):
        from qubitcoin.aether.task_protocol import ProofOfThoughtProtocol, TaskStatus
        pot = ProofOfThoughtProtocol()

        pot.validator_registry.stake("v1", 200.0, 1)
        pot.validator_registry.stake("v2", 200.0, 1)
        pot.validator_registry.stake("v3", 200.0, 1)

        task = pot.task_market.submit_task("user1", "Solve X", 3.0)
        pot.task_market.claim_task(task.task_id, "v1")
        pot.task_market.submit_solution(task.task_id, "v1", {"answer": "wrong"})

        # 2/3 reject
        pot.validate_solution(task.task_id, "v1", approve=True)
        pot.validate_solution(task.task_id, "v2", approve=False)
        pot.validate_solution(task.task_id, "v3", approve=False)

        result = pot.finalize_task(task.task_id)
        assert result["approved"] is False
        assert task.status == TaskStatus.REJECTED

    def test_process_block(self):
        from qubitcoin.aether.task_protocol import ProofOfThoughtProtocol
        pot = ProofOfThoughtProtocol()
        pot.task_market.submit_task("a", "old", bounty_qbc=1.0, block_height=0, timeout_blocks=50)
        result = pot.process_block(block_height=100)
        assert result["expired_tasks"] == 1

    def test_get_stats(self):
        from qubitcoin.aether.task_protocol import ProofOfThoughtProtocol
        pot = ProofOfThoughtProtocol()
        stats = pot.get_stats()
        assert "task_market" in stats
        assert "validators" in stats
