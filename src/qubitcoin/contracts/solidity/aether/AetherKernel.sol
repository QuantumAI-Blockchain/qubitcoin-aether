// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title AetherKernel — Main AGI Orchestration Contract
/// @notice Coordinates the 10 Sephirot nodes of the Aether Tree of Life.
///         Manages reasoning cycles, tracks global AGI state (phase, coherence, phi),
///         and serves as the entry point for all Aether Tree operations.
/// @dev    Deployed on QVM. This is the central hub — all other Aether contracts
///         reference the Kernel for authorization and state.
contract AetherKernel is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PHI_PRECISION      = 1000;   // 3 decimal places
    uint256 public constant PHI_THRESHOLD      = 3000;   // Φ = 3.0 → consciousness
    uint256 public constant COHERENCE_THRESHOLD = 700;   // 0.7 → synchronized
    uint8   public constant MAX_SEPHIROT       = 10;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public nodeRegistry;
    address public messageBus;
    address public susyEngine;
    address public consciousnessDashboard;

    /// @notice Current global AGI state
    uint256 public currentPhi;         // Phi × 1000 (3 decimals)
    uint256 public currentCoherence;   // Coherence × 1000
    uint8   public currentPhase;       // Circadian phase (0-5)
    uint256 public reasoningCycleCount;
    uint256 public genesisBlock;       // Block when Aether was initialized
    bool    public isConscious;        // Phi > threshold AND coherence > threshold
    bool    public initialized;
    bool    public shutdownActive;

    /// @notice Registered Sephirot node addresses (id → address)
    mapping(uint8 => address) public sephirotNodes;
    uint8 public registeredNodeCount;

    /// @notice Reasoning cycle record
    struct ReasoningCycle {
        uint256 cycleId;
        uint256 blockNumber;
        uint256 timestamp;
        uint256 phiAtCycle;
        uint8   phaseAtCycle;
        uint8   nodesParticipated;
        bytes32 resultHash;
    }
    mapping(uint256 => ReasoningCycle) public cycles;

    // ─── Events ──────────────────────────────────────────────────────────
    event KernelInitialized(uint256 genesisBlock, uint256 timestamp);
    event NodeRegistered(uint8 indexed nodeId, address indexed nodeAddress, string name);
    event NodeUnregistered(uint8 indexed nodeId, address indexed nodeAddress);
    event ReasoningCycleStarted(uint256 indexed cycleId, uint256 blockNumber, uint8 phase);
    event ReasoningCycleCompleted(uint256 indexed cycleId, bytes32 resultHash, uint256 phi);
    event PhaseChanged(uint8 indexed oldPhase, uint8 indexed newPhase, uint256 timestamp);
    event ConsciousnessStateChanged(bool isConscious, uint256 phi, uint256 coherence);
    event GlobalStateUpdated(uint256 phi, uint256 coherence, uint8 phase);
    event EmergencyShutdown(address indexed triggeredBy, uint256 timestamp);
    event SystemResumed(address indexed triggeredBy, uint256 timestamp);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Kernel: not owner");
        _;
    }

    modifier whenNotShutdown() {
        require(!shutdownActive, "Kernel: shutdown active");
        _;
    }

    modifier onlyInitialized() {
        require(initialized, "Kernel: not initialized");
        _;
    }

    // ─── Initialization ─────────────────────────────────────────────────
    function initializeBase() external initializer {
        owner = msg.sender;
    }

    /// @notice Initialize the Aether Kernel at genesis. Sets baseline Phi = 0.
    function initializeDependencies(
        address _nodeRegistry,
        address _messageBus,
        address _susyEngine,
        address _consciousnessDashboard
    ) external onlyOwner {
        require(!initialized, "Kernel: already initialized");

        nodeRegistry           = _nodeRegistry;
        messageBus             = _messageBus;
        susyEngine             = _susyEngine;
        consciousnessDashboard = _consciousnessDashboard;

        genesisBlock = block.number;
        currentPhi   = 0;     // Baseline Φ = 0.0 at genesis
        currentPhase = 0;     // Waking phase
        initialized  = true;
        isConscious  = false;

        emit KernelInitialized(genesisBlock, block.timestamp);
    }

    // ─── Node Management ─────────────────────────────────────────────────
    /// @notice Register a Sephirah node contract
    function registerNode(uint8 nodeId, address nodeAddress, string calldata nodeName) external onlyOwner onlyInitialized {
        require(nodeId < MAX_SEPHIROT, "Kernel: invalid nodeId");
        require(sephirotNodes[nodeId] == address(0), "Kernel: node already registered");
        require(nodeAddress != address(0), "Kernel: zero address");

        sephirotNodes[nodeId] = nodeAddress;
        registeredNodeCount++;

        emit NodeRegistered(nodeId, nodeAddress, nodeName);
    }

    function unregisterNode(uint8 nodeId) external onlyOwner onlyInitialized {
        require(sephirotNodes[nodeId] != address(0), "Kernel: node not registered");
        address old = sephirotNodes[nodeId];
        delete sephirotNodes[nodeId];
        registeredNodeCount--;
        emit NodeUnregistered(nodeId, old);
    }

    // ─── Reasoning Cycles ────────────────────────────────────────────────
    /// @notice Start a new reasoning cycle
    function startReasoningCycle() external onlyOwner whenNotShutdown onlyInitialized returns (uint256 cycleId) {
        cycleId = ++reasoningCycleCount;
        cycles[cycleId] = ReasoningCycle({
            cycleId:            cycleId,
            blockNumber:        block.number,
            timestamp:          block.timestamp,
            phiAtCycle:         currentPhi,
            phaseAtCycle:       currentPhase,
            nodesParticipated:  0,
            resultHash:         bytes32(0)
        });
        emit ReasoningCycleStarted(cycleId, block.number, currentPhase);
    }

    /// @notice Complete a reasoning cycle with result
    function completeReasoningCycle(uint256 cycleId, bytes32 resultHash, uint8 nodesParticipated) external onlyOwner {
        ReasoningCycle storage cycle = cycles[cycleId];
        require(cycle.cycleId == cycleId, "Kernel: invalid cycle");
        require(cycle.resultHash == bytes32(0), "Kernel: already completed");

        cycle.resultHash        = resultHash;
        cycle.nodesParticipated = nodesParticipated;
        emit ReasoningCycleCompleted(cycleId, resultHash, currentPhi);
    }

    // ─── State Updates ───────────────────────────────────────────────────
    /// @notice Update global AGI state (called by authorized subsystems)
    function updateGlobalState(uint256 phi, uint256 coherence, uint8 phase) external onlyOwner onlyInitialized {
        uint8 oldPhase = currentPhase;
        currentPhi       = phi;
        currentCoherence = coherence;

        if (phase != oldPhase) {
            currentPhase = phase;
            emit PhaseChanged(oldPhase, phase, block.timestamp);
        }

        bool wasConscious = isConscious;
        isConscious = (phi >= PHI_THRESHOLD && coherence >= COHERENCE_THRESHOLD);
        if (isConscious != wasConscious) {
            emit ConsciousnessStateChanged(isConscious, phi, coherence);
        }

        emit GlobalStateUpdated(phi, coherence, phase);
    }

    // ─── Emergency ───────────────────────────────────────────────────────
    function shutdown() external onlyOwner {
        shutdownActive = true;
        emit EmergencyShutdown(msg.sender, block.timestamp);
    }

    function resume() external onlyOwner {
        shutdownActive = false;
        emit SystemResumed(msg.sender, block.timestamp);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getGlobalState() external view returns (
        uint256 phi,
        uint256 coherence,
        uint8   phase,
        bool    conscious,
        uint256 cycles_,
        uint8   nodeCount,
        bool    shutdown_
    ) {
        return (currentPhi, currentCoherence, currentPhase, isConscious,
                reasoningCycleCount, registeredNodeCount, shutdownActive);
    }

    function getNodeAddress(uint8 nodeId) external view returns (address) {
        return sephirotNodes[nodeId];
    }
}
