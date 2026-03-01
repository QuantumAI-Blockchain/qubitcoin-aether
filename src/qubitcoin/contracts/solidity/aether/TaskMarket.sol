// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title TaskMarket — Reasoning Task Marketplace
/// @notice Submit reasoning tasks with QBC bounties. Sephirot nodes claim and solve tasks.
///         Minimum bounty: 1 QBC. Solutions validated via ProofOfThought.
contract TaskMarket is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant MIN_BOUNTY  = 1 * 10**8;  // 1 QBC (8 decimals)
    uint256 public constant TASK_EXPIRY = 183927;      // 7 days at 3.3s blocks (7*24*3600/3.3)

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    uint256 public taskCount;
    uint256 public totalBounties;

    enum TaskStatus { Open, Claimed, SolutionSubmitted, Completed, Expired, Canceled }

    struct Task {
        uint256    id;
        address    submitter;
        string     description;
        bytes      problemData;
        uint256    bounty;        // QBC reward (8 decimals)
        address    solver;
        bytes32    solutionHash;
        uint256    createdAt;
        uint256    deadline;      // 0 = no deadline
        uint256    expiryBlock;   // Block at which task expires and bounty is reclaimable
        TaskStatus status;
    }

    mapping(uint256 => Task) public tasks;

    // ─── Events ──────────────────────────────────────────────────────────
    event TaskCreated(uint256 indexed id, address indexed submitter, uint256 bounty, string description);
    event TaskClaimed(uint256 indexed id, address indexed solver, uint256 timestamp);
    event SolutionSubmitted(uint256 indexed id, address indexed solver, bytes32 solutionHash);
    event TaskCompleted(uint256 indexed id, address indexed solver, uint256 bounty);
    event TaskExpired(uint256 indexed id);
    event TaskCanceled(uint256 indexed id, address indexed submitter);
    event BountyReclaimed(uint256 indexed id, address indexed submitter, uint256 bounty);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "TaskMarket: not authorized");
        _;
    }

    // ─── Initialization ─────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Task Management ─────────────────────────────────────────────────
    /// @notice Create a new reasoning task with QBC bounty
    function createTask(
        address    submitter,
        string     calldata description,
        bytes      calldata problemData,
        uint256    bounty,
        uint256    deadline
    ) external onlyKernel returns (uint256 taskId) {
        require(bounty >= MIN_BOUNTY, "TaskMarket: bounty below minimum (1 QBC)");

        taskId = ++taskCount;
        tasks[taskId] = Task({
            id:           taskId,
            submitter:    submitter,
            description:  description,
            problemData:  problemData,
            bounty:       bounty,
            solver:       address(0),
            solutionHash: bytes32(0),
            createdAt:    block.timestamp,
            deadline:     deadline,
            expiryBlock:  block.number + TASK_EXPIRY,
            status:       TaskStatus.Open
        });

        totalBounties += bounty;
        emit TaskCreated(taskId, submitter, bounty, description);
    }

    /// @notice Claim a task (lock to solver)
    function claimTask(uint256 taskId, address solver) external onlyKernel {
        Task storage task = tasks[taskId];
        require(task.status == TaskStatus.Open, "TaskMarket: not open");
        require(task.deadline == 0 || block.timestamp <= task.deadline, "TaskMarket: expired");

        task.solver = solver;
        task.status = TaskStatus.Claimed;
        emit TaskClaimed(taskId, solver, block.timestamp);
    }

    /// @notice Submit a solution
    function submitSolution(uint256 taskId, bytes32 solutionHash) external onlyKernel {
        Task storage task = tasks[taskId];
        require(task.status == TaskStatus.Claimed, "TaskMarket: not claimed");

        task.solutionHash = solutionHash;
        task.status       = TaskStatus.SolutionSubmitted;
        emit SolutionSubmitted(taskId, task.solver, solutionHash);
    }

    /// @notice Complete a task (after proof validation)
    function completeTask(uint256 taskId) external onlyKernel {
        Task storage task = tasks[taskId];
        require(task.status == TaskStatus.SolutionSubmitted, "TaskMarket: no solution");

        task.status = TaskStatus.Completed;
        emit TaskCompleted(taskId, task.solver, task.bounty);
    }

    /// @notice Cancel a task (submitter or owner)
    function cancelTask(uint256 taskId) external onlyKernel {
        Task storage task = tasks[taskId];
        require(task.status == TaskStatus.Open, "TaskMarket: not open");

        task.status = TaskStatus.Canceled;
        totalBounties -= task.bounty;
        emit TaskCanceled(taskId, task.submitter);
    }

    /// @notice Reclaim bounty for an expired, unclaimed task.
    ///         Only the original task submitter (or kernel/owner) can reclaim.
    ///         Task must be past its expiryBlock and still Open or Claimed (unsolved).
    function reclaimBounty(uint256 taskId) external {
        Task storage task = tasks[taskId];
        require(
            task.status == TaskStatus.Open || task.status == TaskStatus.Claimed,
            "TaskMarket: task not reclaimable"
        );
        require(block.number >= task.expiryBlock, "TaskMarket: task not yet expired");
        require(
            msg.sender == task.submitter || msg.sender == kernel || msg.sender == owner,
            "TaskMarket: not authorized"
        );

        task.status = TaskStatus.Expired;
        totalBounties -= task.bounty;

        emit TaskExpired(taskId);
        emit BountyReclaimed(taskId, task.submitter, task.bounty);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getTask(uint256 taskId) external view returns (
        address    submitter,
        string     memory description,
        uint256    bounty,
        address    solver,
        TaskStatus status,
        uint256    createdAt,
        uint256    deadline,
        uint256    expiryBlock
    ) {
        Task storage t = tasks[taskId];
        return (t.submitter, t.description, t.bounty, t.solver, t.status, t.createdAt, t.deadline, t.expiryBlock);
    }

    function getMarketStats() external view returns (uint256 total, uint256 bounties) {
        return (taskCount, totalBounties);
    }
}
