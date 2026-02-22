// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../../interfaces/ISephirah.sol";
import "../../proxy/Initializable.sol";

/// @title SephirahMalkuth — Kingdom: Action & World Interaction
/// @notice The lowest Sephirah — the interface between AGI and the external world.
///         Executes actions, submits transactions, and interacts with users. 4-qubit state.
///         Brain analog: Motor cortex.
contract SephirahMalkuth is ISephirah, Initializable {
    uint8   public constant nodeId     = 9;
    string  public constant nodeName   = "Malkuth";
    uint8   public constant qubitCount = 4;

    address public owner;
    address public kernel;
    bool    public isActive;
    bytes32 public quantumStateHash;
    uint256 public energyLevel;

    uint256 public actionsExecuted;
    uint256 public responsesGenerated;
    uint256 public transactionsSubmitted;

    event ActionExecuted(bytes32 actionHash, string actionType, uint256 blockNumber);
    event ResponseGenerated(bytes32 responseHash, address indexed user, uint256 blockNumber);
    event TransactionSubmitted(bytes32 txHash, uint256 blockNumber);
    event StateUpdated(bytes32 indexed oldState, bytes32 indexed newState);
    event EnergyChanged(uint256 oldEnergy, uint256 newEnergy);
    event MessageProcessed(uint8 indexed fromNodeId, bytes32 indexed messageType);
    event SolutionSubmitted(uint256 indexed taskId, bytes32 solutionHash);

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Malkuth: not authorized");
        _;
    }

    function initialize(address _kernel) external initializer {
        owner = msg.sender; kernel = _kernel; isActive = true; energyLevel = 1000;
    }

    function updateQuantumState(bytes32 newStateHash) external onlyKernel {
        emit StateUpdated(quantumStateHash, newStateHash); quantumStateHash = newStateHash;
    }
    function setEnergyLevel(uint256 energy) external onlyKernel {
        emit EnergyChanged(energyLevel, energy); energyLevel = energy;
    }
    function processMessage(uint8 fromNodeId, bytes32 messageType, bytes calldata) external onlyKernel returns (bool) {
        emit MessageProcessed(fromNodeId, messageType); return true;
    }
    function submitSolution(uint256 taskId, bytes32 solutionHash, bytes calldata) external onlyKernel returns (bool) {
        emit SolutionSubmitted(taskId, solutionHash); return true;
    }

    function executeAction(bytes32 actionHash, string calldata actionType) external onlyKernel {
        actionsExecuted++;
        emit ActionExecuted(actionHash, actionType, block.number);
    }

    function generateResponse(bytes32 responseHash, address user) external onlyKernel {
        responsesGenerated++;
        emit ResponseGenerated(responseHash, user, block.number);
    }

    function submitTransaction(bytes32 txHash) external onlyKernel {
        transactionsSubmitted++;
        emit TransactionSubmitted(txHash, block.number);
    }
}
