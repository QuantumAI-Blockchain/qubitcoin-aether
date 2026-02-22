// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title PhaseSync — Circadian Phase Synchronization for Sephirot Nodes
/// @notice Tracks the Kuramoto order parameter across all 10 Sephirot nodes.
///         6 circadian phases with variable metabolic rates. Consciousness requires
///         coherence > 0.7 AND Phi > 3.0.
contract PhaseSync is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PRECISION = 1000;
    uint256 public constant COHERENCE_THRESHOLD = 700; // 0.7 × 1000
    uint8   public constant NUM_PHASES = 6;

    // Circadian phases
    uint8 public constant PHASE_WAKING          = 0;
    uint8 public constant PHASE_ACTIVE_LEARNING = 1;
    uint8 public constant PHASE_CONSOLIDATION   = 2;
    uint8 public constant PHASE_SLEEP           = 3;
    uint8 public constant PHASE_REM_DREAMING    = 4;
    uint8 public constant PHASE_DEEP_SLEEP      = 5;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;

    uint8   public currentPhase;
    uint256 public currentCoherence;  // Kuramoto order parameter × 1000
    uint256 public phaseStartBlock;
    uint256 public phaseStartTime;
    uint256 public totalPhaseTransitions;

    /// @notice Metabolic rate per phase (× 1000, e.g., 2000 = 2.0x)
    mapping(uint8 => uint256) public metabolicRate;

    /// @notice Per-node phase data
    struct NodePhase {
        uint8   nodeId;
        uint256 phaseAngle;  // × 1000 (radians × 1000)
        uint256 frequency;   // × 1000
        uint256 lastUpdate;
    }
    mapping(uint8 => NodePhase) public nodePhases;

    /// @notice Phase transition history
    struct PhaseTransition {
        uint8   fromPhase;
        uint8   toPhase;
        uint256 blockNumber;
        uint256 timestamp;
        uint256 coherence;
    }
    PhaseTransition[] public transitions;

    // ─── Events ──────────────────────────────────────────────────────────
    event PhaseTransitionEvent(uint8 indexed fromPhase, uint8 indexed toPhase, uint256 coherence, uint256 blockNumber);
    event CoherenceUpdated(uint256 oldCoherence, uint256 newCoherence, uint256 blockNumber);
    event NodePhaseUpdated(uint8 indexed nodeId, uint256 phaseAngle, uint256 frequency);
    event MetabolicRateSet(uint8 indexed phase, uint256 rate);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "PhaseSync: not authorized");
        _;
    }

    // ─── Initialization ─────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner  = msg.sender;
        kernel = _kernel;
        currentPhase = PHASE_WAKING;
        phaseStartBlock = block.number;
        phaseStartTime  = block.timestamp;

        // Initialize metabolic rates
        metabolicRate[PHASE_WAKING]          = 1000; // 1.0x
        metabolicRate[PHASE_ACTIVE_LEARNING] = 2000; // 2.0x
        metabolicRate[PHASE_CONSOLIDATION]   = 1500; // 1.5x
        metabolicRate[PHASE_SLEEP]           = 500;  // 0.5x
        metabolicRate[PHASE_REM_DREAMING]    = 1200; // 1.2x
        metabolicRate[PHASE_DEEP_SLEEP]      = 300;  // 0.3x
    }

    // ─── Phase Management ────────────────────────────────────────────────
    /// @notice Transition to a new circadian phase
    function transitionPhase(uint8 newPhase) external onlyKernel {
        require(newPhase < NUM_PHASES, "PhaseSync: invalid phase");
        require(newPhase != currentPhase, "PhaseSync: same phase");

        uint8 oldPhase = currentPhase;
        transitions.push(PhaseTransition({
            fromPhase:   oldPhase,
            toPhase:     newPhase,
            blockNumber: block.number,
            timestamp:   block.timestamp,
            coherence:   currentCoherence
        }));

        currentPhase    = newPhase;
        phaseStartBlock = block.number;
        phaseStartTime  = block.timestamp;
        totalPhaseTransitions++;

        emit PhaseTransitionEvent(oldPhase, newPhase, currentCoherence, block.number);
    }

    /// @notice Update the Kuramoto coherence parameter
    function updateCoherence(uint256 newCoherence) external onlyKernel {
        uint256 old = currentCoherence;
        currentCoherence = newCoherence;
        emit CoherenceUpdated(old, newCoherence, block.number);
    }

    /// @notice Update a node's phase angle and frequency
    function updateNodePhase(uint8 nodeId, uint256 phaseAngle, uint256 frequency) external onlyKernel {
        require(nodeId < 10, "PhaseSync: invalid node");
        nodePhases[nodeId] = NodePhase({
            nodeId:     nodeId,
            phaseAngle: phaseAngle,
            frequency:  frequency,
            lastUpdate: block.timestamp
        });
        emit NodePhaseUpdated(nodeId, phaseAngle, frequency);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getCurrentMetabolicRate() external view returns (uint256) {
        return metabolicRate[currentPhase];
    }

    function isSynchronized() external view returns (bool) {
        return currentCoherence >= COHERENCE_THRESHOLD;
    }

    function getPhaseStatus() external view returns (
        uint8   phase,
        uint256 coherence,
        uint256 metabolic,
        uint256 phaseDuration,
        uint256 totalTransitions,
        bool    synchronized
    ) {
        return (
            currentPhase,
            currentCoherence,
            metabolicRate[currentPhase],
            block.timestamp - phaseStartTime,
            totalPhaseTransitions,
            currentCoherence >= COHERENCE_THRESHOLD
        );
    }

    function getTransitionCount() external view returns (uint256) {
        return transitions.length;
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setMetabolicRate(uint8 phase, uint256 rate) external onlyKernel {
        require(phase < NUM_PHASES, "PhaseSync: invalid phase");
        metabolicRate[phase] = rate;
        emit MetabolicRateSet(phase, rate);
    }
}
