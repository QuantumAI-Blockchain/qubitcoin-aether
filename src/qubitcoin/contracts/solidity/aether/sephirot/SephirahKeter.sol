// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../../interfaces/ISephirah.sol";

/// @title SephirahKeter — Crown: Meta-Learning & Goal Formation
/// @notice The highest Sephirah. Oversees the entire Tree of Life, sets goals,
///         and directs meta-learning across all nodes. 8-qubit quantum state.
///         Brain analog: Prefrontal cortex.
contract SephirahKeter is ISephirah {
    uint8   public constant nodeId     = 0;
    string  public constant nodeName   = "Keter";
    uint8   public constant qubitCount = 8;

    address public owner;
    address public kernel;
    bool    public isActive;
    bytes32 public quantumStateHash;
    uint256 public energyLevel;

    /// @notice Current goals set by Keter
    struct Goal {
        uint256 id;
        string  description;
        uint256 priority;     // 0 = highest
        uint256 setAt;
        bool    achieved;
    }
    Goal[] public goals;

    /// @notice Meta-learning metrics
    uint256 public learningCyclesCompleted;
    uint256 public goalsAchieved;

    event GoalSet(uint256 indexed id, string description, uint256 priority);
    event GoalAchieved(uint256 indexed id, uint256 blockNumber);
    event MetaLearningCycleCompleted(uint256 cycleCount, uint256 blockNumber);
    event StateUpdated(bytes32 indexed oldState, bytes32 indexed newState);
    event EnergyChanged(uint256 oldEnergy, uint256 newEnergy);
    event MessageProcessed(uint8 indexed fromNodeId, bytes32 indexed messageType);
    event SolutionSubmitted(uint256 indexed taskId, bytes32 solutionHash);

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Keter: not authorized");
        _;
    }

    constructor(address _kernel) {
        owner    = msg.sender;
        kernel   = _kernel;
        isActive = true;
        energyLevel = 1000;
    }

    function updateQuantumState(bytes32 newStateHash) external onlyKernel {
        bytes32 old = quantumStateHash;
        quantumStateHash = newStateHash;
        emit StateUpdated(old, newStateHash);
    }

    function setEnergyLevel(uint256 energy) external onlyKernel {
        uint256 old = energyLevel;
        energyLevel = energy;
        emit EnergyChanged(old, energy);
    }

    function processMessage(uint8 fromNodeId, bytes32 messageType, bytes calldata) external onlyKernel returns (bool) {
        emit MessageProcessed(fromNodeId, messageType);
        return true;
    }

    function submitSolution(uint256 taskId, bytes32 solutionHash, bytes calldata) external onlyKernel returns (bool) {
        emit SolutionSubmitted(taskId, solutionHash);
        return true;
    }

    /// @notice Set a goal for the Aether Tree
    function setGoal(string calldata description, uint256 priority) external onlyKernel returns (uint256 goalId) {
        goalId = goals.length;
        goals.push(Goal(goalId, description, priority, block.timestamp, false));
        emit GoalSet(goalId, description, priority);
    }

    function achieveGoal(uint256 goalId) external onlyKernel {
        require(goalId < goals.length, "Keter: invalid goal");
        goals[goalId].achieved = true;
        goalsAchieved++;
        emit GoalAchieved(goalId, block.number);
    }

    function completeMetaLearningCycle() external onlyKernel {
        learningCyclesCompleted++;
        emit MetaLearningCycleCompleted(learningCyclesCompleted, block.number);
    }

    function getGoalCount() external view returns (uint256) { return goals.length; }
}
