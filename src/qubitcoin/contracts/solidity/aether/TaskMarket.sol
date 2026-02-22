// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title TaskMarket — Reasoning Task Marketplace
/// @notice Submit reasoning tasks with QBC bounties. Sephirot nodes claim and solve tasks.
///         Minimum bounty: 1 QBC. Solutions validated via ProofOfThought.
contract TaskMarket is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant MIN_BOUNTY = 1 * 10**8; // 1 QBC (8 decimals)

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

    // ─── Queries ─────────────────────────────────────────────────────────
    function getTask(uint256 taskId) external view returns (
        address    submitter,
        string     memory description,
        uint256    bounty,
        address    solver,
        TaskStatus status,
        uint256    createdAt,
        uint256    deadline
    ) {
        Task storage t = tasks[taskId];
        return (t.submitter, t.description, t.bounty, t.solver, t.status, t.createdAt, t.deadline);
    }

    function getMarketStats() external view returns (uint256 total, uint256 bounties) {
        return (taskCount, totalBounties);
    }
}
