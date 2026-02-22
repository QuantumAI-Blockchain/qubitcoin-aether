// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../../interfaces/ISephirah.sol";
import "../../proxy/Initializable.sol";

/// @title SephirahYesod — Foundation: Memory & Multimodal Fusion
/// @notice Central memory hub. Fuses inputs from all other nodes, manages episodic
///         and semantic memory. Largest quantum state: 16-qubit buffer.
///         Brain analog: Hippocampus.
contract SephirahYesod is ISephirah, Initializable {
    uint8   public constant nodeId     = 8;
    string  public constant nodeName   = "Yesod";
    uint8   public constant qubitCount = 16;

    address public owner;
    address public kernel;
    bool    public isActive;
    bytes32 public quantumStateHash;
    uint256 public energyLevel;

    uint256 public memoriesStored;
    uint256 public memoriesRetrieved;
    uint256 public consolidationCycles;

    /// @notice Memory record
    struct Memory {
        bytes32 contentHash;
        bytes32 memoryType;  // "episodic", "semantic", "procedural"
        uint256 storedAt;
        uint256 accessCount;
        uint256 importance;  // × 1000
    }
    mapping(bytes32 => Memory) public memories;

    event MemoryStored(bytes32 indexed contentHash, bytes32 memoryType, uint256 importance);
    event MemoryRetrieved(bytes32 indexed contentHash, uint256 accessCount);
    event ConsolidationCompleted(uint256 memoriesConsolidated, uint256 blockNumber);
    event StateUpdated(bytes32 indexed oldState, bytes32 indexed newState);
    event EnergyChanged(uint256 oldEnergy, uint256 newEnergy);
    event MessageProcessed(uint8 indexed fromNodeId, bytes32 indexed messageType);
    event SolutionSubmitted(uint256 indexed taskId, bytes32 solutionHash);

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Yesod: not authorized");
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

    function storeMemory(bytes32 contentHash, bytes32 memoryType, uint256 importance) external onlyKernel {
        memories[contentHash] = Memory(contentHash, memoryType, block.timestamp, 0, importance);
        memoriesStored++;
        emit MemoryStored(contentHash, memoryType, importance);
    }

    function retrieveMemory(bytes32 contentHash) external onlyKernel returns (uint256 accessCount) {
        Memory storage m = memories[contentHash];
        require(m.storedAt > 0, "Yesod: memory not found");
        m.accessCount++;
        memoriesRetrieved++;
        emit MemoryRetrieved(contentHash, m.accessCount);
        return m.accessCount;
    }

    function consolidate(uint256 memoriesProcessed) external onlyKernel {
        consolidationCycles++;
        emit ConsolidationCompleted(memoriesProcessed, block.number);
    }
}
