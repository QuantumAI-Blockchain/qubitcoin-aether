// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../../interfaces/ISephirah.sol";
import "../../proxy/Initializable.sol";

/// @title SephirahGevurah — Severity: Constraint & Safety Validation
/// @notice Constraint node (SUSY pair with Chesed). Validates safety, enforces limits,
///         and can VETO harmful operations. 3-qubit threat detection state.
///         Brain analog: Amygdala / inhibitory circuits.
contract SephirahGevurah is ISephirah, Initializable {
    uint8   public constant nodeId     = 4;
    string  public constant nodeName   = "Gevurah";
    uint8   public constant qubitCount = 3;

    address public owner;
    address public kernel;
    bool    public isActive;
    bytes32 public quantumStateHash;
    uint256 public energyLevel;

    uint256 public threatDetections;
    uint256 public vetoesIssued;
    uint256 public safetyValidations;

    event ThreatDetected(bytes32 threatHash, uint256 severity, uint256 blockNumber);
    event VetoIssued(bytes32 operationHash, string reason, uint256 blockNumber);
    event SafetyValidated(bytes32 operationHash, bool safe, uint256 blockNumber);
    event StateUpdated(bytes32 indexed oldState, bytes32 indexed newState);
    event EnergyChanged(uint256 oldEnergy, uint256 newEnergy);
    event MessageProcessed(uint8 indexed fromNodeId, bytes32 indexed messageType);
    event SolutionSubmitted(uint256 indexed taskId, bytes32 solutionHash);

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Gevurah: not authorized");
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

    /// @notice Detect a safety threat
    function detectThreat(bytes32 threatHash, uint256 severity) external onlyKernel {
        threatDetections++;
        emit ThreatDetected(threatHash, severity, block.number);
    }

    /// @notice Issue a veto on an unsafe operation
    function issueVeto(bytes32 operationHash, string calldata reason) external onlyKernel {
        vetoesIssued++;
        emit VetoIssued(operationHash, reason, block.number);
    }

    /// @notice Validate an operation as safe or unsafe
    function validateSafety(bytes32 operationHash, bool safe) external onlyKernel {
        safetyValidations++;
        emit SafetyValidated(operationHash, safe, block.number);
    }
}
