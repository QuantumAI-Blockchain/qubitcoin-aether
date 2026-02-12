// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SUSYEngine — Supersymmetric Balance Enforcement
/// @notice Enforces the golden ratio (φ = 1.618) between SUSY expansion/constraint pairs.
///         Detects violations (>5% deviation) and auto-redistributes QBC to restore balance.
///         All violations are logged immutably on-chain.
contract SUSYEngine {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PHI         = 1618;   // φ × 1000 = 1.618
    uint256 public constant PRECISION   = 1000;
    uint256 public constant MAX_DEVIATION_BPS = 500; // 5% max deviation before violation

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    address public nodeRegistry;

    struct SUSYPair {
        uint8   expansionNodeId;
        uint8   constraintNodeId;
        string  pairName;
        uint256 expansionEnergy;
        uint256 constraintEnergy;
        uint256 currentRatio;      // × 1000
        uint256 lastCheckBlock;
        uint256 violationCount;
        bool    active;
    }

    SUSYPair[3] public pairs;
    uint256 public totalViolations;
    uint256 public totalRedistributions;

    /// @notice Violation history
    struct Violation {
        uint256 id;
        uint8   pairIndex;
        uint256 ratio;        // actual ratio × 1000
        uint256 deviation;    // deviation in basis points
        uint256 blockNumber;
        uint256 timestamp;
        uint256 redistributedAmount;
    }

    Violation[] public violations;

    // ─── Events ──────────────────────────────────────────────────────────
    event EnergyUpdated(uint8 indexed pairIndex, uint256 expansionEnergy, uint256 constraintEnergy, uint256 ratio);
    event SUSYViolation(uint8 indexed pairIndex, uint256 ratio, uint256 deviationBps, uint256 blockNumber);
    event BalanceRestored(uint8 indexed pairIndex, uint256 newRatio, uint256 redistributedAmount);
    event PairActivated(uint8 indexed pairIndex, uint8 expansionId, uint8 constraintId);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "SUSY: not owner");
        _;
    }

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "SUSY: not authorized");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _kernel, address _nodeRegistry) {
        owner        = msg.sender;
        kernel       = _kernel;
        nodeRegistry = _nodeRegistry;
    }

    // ─── Pair Setup ──────────────────────────────────────────────────────
    /// @notice Initialize the 3 SUSY pairs
    function initializePairs() external onlyOwner {
        // Pair 0: Chesed (3) / Gevurah (4) — Creativity vs Safety
        pairs[0] = SUSYPair(3, 4, "Chesed/Gevurah", 1618, 1000, PHI, 0, 0, true);
        emit PairActivated(0, 3, 4);

        // Pair 1: Chochmah (1) / Binah (2) — Intuition vs Logic
        pairs[1] = SUSYPair(1, 2, "Chochmah/Binah", 1618, 1000, PHI, 0, 0, true);
        emit PairActivated(1, 1, 2);

        // Pair 2: Netzach (6) / Hod (7) — Persistence vs Communication
        pairs[2] = SUSYPair(6, 7, "Netzach/Hod", 1618, 1000, PHI, 0, 0, true);
        emit PairActivated(2, 6, 7);
    }

    // ─── Energy Updates ──────────────────────────────────────────────────
    /// @notice Update energy levels for a SUSY pair and check for violations
    function updateEnergy(uint8 pairIndex, uint256 expansionEnergy, uint256 constraintEnergy) external onlyKernel {
        require(pairIndex < 3, "SUSY: invalid pair");
        require(pairs[pairIndex].active, "SUSY: pair inactive");
        require(constraintEnergy > 0, "SUSY: zero constraint energy");

        SUSYPair storage pair = pairs[pairIndex];
        pair.expansionEnergy  = expansionEnergy;
        pair.constraintEnergy = constraintEnergy;
        pair.currentRatio     = (expansionEnergy * PRECISION) / constraintEnergy;
        pair.lastCheckBlock   = block.number;

        emit EnergyUpdated(pairIndex, expansionEnergy, constraintEnergy, pair.currentRatio);

        // Check for violation
        uint256 deviation = _deviationBps(pair.currentRatio);
        if (deviation > MAX_DEVIATION_BPS) {
            pair.violationCount++;
            totalViolations++;

            violations.push(Violation({
                id:                   violations.length,
                pairIndex:            pairIndex,
                ratio:                pair.currentRatio,
                deviation:            deviation,
                blockNumber:          block.number,
                timestamp:            block.timestamp,
                redistributedAmount:  0
            }));

            emit SUSYViolation(pairIndex, pair.currentRatio, deviation, block.number);
        }
    }

    /// @notice Auto-redistribute QBC to restore golden ratio balance
    function restoreBalance(uint8 pairIndex) external onlyKernel returns (uint256 redistributed) {
        require(pairIndex < 3, "SUSY: invalid pair");
        SUSYPair storage pair = pairs[pairIndex];

        // Target: expansion / constraint = PHI / PRECISION
        // Target constraint = expansion * PRECISION / PHI
        uint256 targetConstraint = (pair.expansionEnergy * PRECISION) / PHI;
        if (targetConstraint > pair.constraintEnergy) {
            redistributed = targetConstraint - pair.constraintEnergy;
            pair.constraintEnergy = targetConstraint;
        } else {
            // Reduce expansion to match
            uint256 targetExpansion = (pair.constraintEnergy * PHI) / PRECISION;
            redistributed = pair.expansionEnergy - targetExpansion;
            pair.expansionEnergy = targetExpansion;
        }

        pair.currentRatio = (pair.expansionEnergy * PRECISION) / pair.constraintEnergy;
        totalRedistributions++;

        emit BalanceRestored(pairIndex, pair.currentRatio, redistributed);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getPairStatus(uint8 pairIndex) external view returns (
        string  memory pairName,
        uint256 expansionEnergy,
        uint256 constraintEnergy,
        uint256 currentRatio,
        uint256 deviationBps,
        uint256 violationCount_,
        bool    isViolating
    ) {
        SUSYPair storage p = pairs[pairIndex];
        uint256 dev = _deviationBps(p.currentRatio);
        return (p.pairName, p.expansionEnergy, p.constraintEnergy,
                p.currentRatio, dev, p.violationCount, dev > MAX_DEVIATION_BPS);
    }

    function getViolationCount() external view returns (uint256) {
        return violations.length;
    }

    // ─── Internal ────────────────────────────────────────────────────────
    /// @dev Calculate deviation from PHI in basis points
    function _deviationBps(uint256 ratio) internal pure returns (uint256) {
        if (ratio >= PHI) {
            return ((ratio - PHI) * 10000) / PHI;
        } else {
            return ((PHI - ratio) * 10000) / PHI;
        }
    }
}
