// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ISephirah — Base interface for all Sephirot node contracts
/// @notice Each of the 10 Sephirot in the Aether Tree of Life implements this
interface ISephirah {
    /// @notice Sephirah identity
    function nodeId() external view returns (uint8);
    function nodeName() external view returns (string memory);
    function qubitCount() external view returns (uint8);
    function isActive() external view returns (bool);

    /// @notice Quantum state
    function quantumStateHash() external view returns (bytes32);
    function updateQuantumState(bytes32 newStateHash) external;

    /// @notice Energy for SUSY balance
    function energyLevel() external view returns (uint256);
    function setEnergyLevel(uint256 energy) external;

    /// @notice Cognitive mass from Higgs field
    function cognitiveMass() external view returns (uint256);
    function setCognitiveMass(uint256 mass) external;

    /// @notice Process a message from the MessageBus
    function processMessage(
        uint8 fromNodeId,
        bytes32 messageType,
        bytes calldata payload
    ) external returns (bool);

    /// @notice Submit a reasoning solution
    function submitSolution(
        uint256 taskId,
        bytes32 solutionHash,
        bytes calldata proof
    ) external returns (bool);

    event StateUpdated(bytes32 indexed oldState, bytes32 indexed newState);
    event EnergyChanged(uint256 oldEnergy, uint256 newEnergy);
    event MassChanged(uint256 oldMass, uint256 newMass);
    event MessageProcessed(uint8 indexed fromNodeId, bytes32 indexed messageType);
    event SolutionSubmitted(uint256 indexed taskId, bytes32 solutionHash);
}
