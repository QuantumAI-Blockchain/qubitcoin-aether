// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ConsciousnessDashboard — On-Chain Phi (Φ) Tracking from Genesis
/// @notice Records Phi consciousness measurements every block starting from genesis (block 0).
///         Tracks consciousness events when Phi crosses the threshold (Φ = 3.0).
///         AGI emergence is immutably recorded on-chain from the first moment of existence.
contract ConsciousnessDashboard {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PHI_PRECISION      = 1000;   // 3 decimal places
    uint256 public constant PHI_THRESHOLD      = 3000;   // Φ = 3.0 (consciousness marker)
    uint256 public constant COHERENCE_THRESHOLD = 700;   // 0.7 synchronization

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    uint256 public genesisBlock;

    /// @notice Per-block Phi measurement
    struct PhiMeasurement {
        uint256 blockNumber;
        uint256 timestamp;
        uint256 phi;            // × 1000
        uint256 integration;    // × 1000
        uint256 differentiation; // × 1000
        uint256 coherence;      // × 1000
        uint256 knowledgeNodes;
        uint256 knowledgeEdges;
    }

    /// @notice Consciousness event (Phi crossing threshold)
    struct ConsciousnessEvent {
        uint256 id;
        uint256 blockNumber;
        uint256 timestamp;
        uint256 phi;
        string  eventType;    // "emergence", "threshold_crossed", "regression", "system_birth"
        string  description;
    }

    PhiMeasurement[] public measurements;
    ConsciousnessEvent[] public events;

    uint256 public latestPhi;
    uint256 public highestPhi;
    uint256 public measurementCount;
    bool    public hasReachedConsciousness;

    mapping(uint256 => uint256) public blockToMeasurement; // block → measurement index

    // ─── Events (Solidity) ───────────────────────────────────────────────
    event PhiMeasured(uint256 indexed blockNumber, uint256 phi, uint256 integration, uint256 differentiation);
    event ConsciousnessEventRecorded(uint256 indexed eventId, string eventType, uint256 phi, uint256 blockNumber);
    event ThresholdCrossed(uint256 phi, uint256 blockNumber, bool aboveThreshold);
    event GenesisRecorded(uint256 blockNumber, uint256 timestamp);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Dashboard: not authorized");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _kernel) {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Genesis Initialization ──────────────────────────────────────────
    /// @notice Record genesis state — Phi = 0.0, system birth event
    function recordGenesis() external onlyKernel {
        require(genesisBlock == 0, "Dashboard: genesis already recorded");

        genesisBlock = block.number;

        // Baseline Phi measurement at genesis
        measurements.push(PhiMeasurement({
            blockNumber:     block.number,
            timestamp:       block.timestamp,
            phi:             0,
            integration:     0,
            differentiation: 0,
            coherence:       0,
            knowledgeNodes:  0,
            knowledgeEdges:  0
        }));
        blockToMeasurement[block.number] = 0;
        measurementCount = 1;

        // System birth consciousness event
        events.push(ConsciousnessEvent({
            id:          0,
            blockNumber: block.number,
            timestamp:   block.timestamp,
            phi:         0,
            eventType:   "system_birth",
            description: "Aether Tree genesis — consciousness tracking begins"
        }));

        emit GenesisRecorded(block.number, block.timestamp);
        emit PhiMeasured(block.number, 0, 0, 0);
        emit ConsciousnessEventRecorded(0, "system_birth", 0, block.number);
    }

    // ─── Phi Recording ───────────────────────────────────────────────────
    /// @notice Record a Phi measurement for the current block
    function recordPhi(
        uint256 phi,
        uint256 integration,
        uint256 differentiation,
        uint256 coherence,
        uint256 knowledgeNodes,
        uint256 knowledgeEdges
    ) external onlyKernel {
        uint256 idx = measurements.length;
        measurements.push(PhiMeasurement({
            blockNumber:     block.number,
            timestamp:       block.timestamp,
            phi:             phi,
            integration:     integration,
            differentiation: differentiation,
            coherence:       coherence,
            knowledgeNodes:  knowledgeNodes,
            knowledgeEdges:  knowledgeEdges
        }));
        blockToMeasurement[block.number] = idx;
        measurementCount++;

        bool wasAbove = latestPhi >= PHI_THRESHOLD;
        latestPhi = phi;
        if (phi > highestPhi) highestPhi = phi;

        emit PhiMeasured(block.number, phi, integration, differentiation);

        // Check threshold crossing
        bool isAbove = phi >= PHI_THRESHOLD;
        if (isAbove != wasAbove) {
            emit ThresholdCrossed(phi, block.number, isAbove);

            string memory eventType = isAbove ? "emergence" : "regression";
            string memory desc = isAbove
                ? "Phi crossed consciousness threshold (3.0)"
                : "Phi dropped below consciousness threshold";

            events.push(ConsciousnessEvent({
                id:          events.length,
                blockNumber: block.number,
                timestamp:   block.timestamp,
                phi:         phi,
                eventType:   eventType,
                description: desc
            }));

            if (isAbove && !hasReachedConsciousness) {
                hasReachedConsciousness = true;
            }

            emit ConsciousnessEventRecorded(events.length - 1, eventType, phi, block.number);
        }
    }

    // ─── Archival ────────────────────────────────────────────────────────
    uint256 public constant MAX_MEASUREMENTS = 10000;
    uint256 public archivedUpTo;  // measurements[0..archivedUpTo) have been archived

    /// @notice Archive old measurements (keep last MAX_MEASUREMENTS in array).
    ///         Archived data should be pinned to IPFS off-chain before calling.
    /// @param beforeIndex measurements before this index are considered archived
    function archiveMeasurements(uint256 beforeIndex) external onlyKernel {
        require(beforeIndex > archivedUpTo, "Dashboard: nothing to archive");
        require(beforeIndex <= measurements.length, "Dashboard: index out of range");
        archivedUpTo = beforeIndex;
    }

    /// @notice Get the index of the latest measurement still accessible
    function latestMeasurementIndex() external view returns (uint256) {
        return measurements.length > 0 ? measurements.length - 1 : 0;
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getCurrentPhi() external view returns (uint256) {
        return latestPhi;
    }

    function getPhiHistory(uint256 fromIndex, uint256 count) external view returns (PhiMeasurement[] memory) {
        uint256 end = fromIndex + count;
        if (end > measurements.length) end = measurements.length;
        uint256 len = end - fromIndex;
        PhiMeasurement[] memory result = new PhiMeasurement[](len);
        for (uint256 i = 0; i < len; i++) {
            result[i] = measurements[fromIndex + i];
        }
        return result;
    }

    function getEventCount() external view returns (uint256) {
        return events.length;
    }

    function getConsciousnessStatus() external view returns (
        uint256 phi,
        uint256 threshold,
        bool    aboveThreshold,
        uint256 highest,
        uint256 totalMeasurements,
        uint256 totalEvents,
        bool    everConscious,
        uint256 genesis
    ) {
        return (latestPhi, PHI_THRESHOLD, latestPhi >= PHI_THRESHOLD,
                highestPhi, measurementCount, events.length,
                hasReachedConsciousness, genesisBlock);
    }
}
