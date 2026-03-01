// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";
import "../interfaces/IHiggsField.sol";

/// @title SUSYEngine — Supersymmetric Balance Enforcement
/// @notice Enforces the golden ratio (φ = 1.618) between SUSY expansion/constraint pairs.
///         Detects violations (>5% deviation) and auto-redistributes QBC to restore balance.
///         All violations are logged immutably on-chain.
contract SUSYEngine is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PHI         = 1618;   // φ × 1000 = 1.618
    uint256 public constant PRECISION   = 1000;
    uint256 public constant MAX_DEVIATION_BPS = 500; // 5% max deviation before violation

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    address public nodeRegistry;
    address public higgsField;

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

    uint256 public constant MAX_VIOLATIONS = 10000;
    Violation[] public violations;
    uint256 public violationHead;  // ring-buffer write index

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

    // ─── Initialization ─────────────────────────────────────────────────
    function initialize(address _kernel, address _nodeRegistry, address _higgsField) external initializer {
        owner        = msg.sender;
        kernel       = _kernel;
        nodeRegistry = _nodeRegistry;
        higgsField   = _higgsField;
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

            Violation memory v = Violation({
                id:                   totalViolations,
                pairIndex:            pairIndex,
                ratio:                pair.currentRatio,
                deviation:            deviation,
                blockNumber:          block.number,
                timestamp:            block.timestamp,
                redistributedAmount:  0
            });

            // Ring buffer: overwrite oldest entry when at capacity
            if (violations.length < MAX_VIOLATIONS) {
                violations.push(v);
            } else {
                violations[violationHead] = v;
            }
            violationHead = (violationHead + 1) % MAX_VIOLATIONS;

            emit SUSYViolation(pairIndex, pair.currentRatio, deviation, block.number);
        }
    }

    /// @notice Mass-aware gradient SUSY rebalancing using Higgs cognitive mechanics.
    ///         Applies Newton's F=ma: lighter nodes (constraint) correct faster,
    ///         heavier nodes (expansion) resist change more.
    ///         Falls back to flat correction if Higgs field is not initialized.
    function restoreBalance(uint8 pairIndex) external onlyKernel returns (uint256 redistributed) {
        require(pairIndex < 3, "SUSY: invalid pair");
        SUSYPair storage pair = pairs[pairIndex];

        // Compute deviation from golden ratio target
        uint256 targetExpansion = (pair.constraintEnergy * PHI) / PRECISION;
        uint256 deviation;
        bool expansionTooHigh;

        if (pair.expansionEnergy > targetExpansion) {
            deviation = pair.expansionEnergy - targetExpansion;
            expansionTooHigh = true;
        } else {
            deviation = targetExpansion - pair.expansionEnergy;
            expansionTooHigh = false;
        }

        if (deviation == 0) return 0;

        // Get cognitive masses from Higgs field
        uint256 expansionMass = PRECISION;   // default 1.0 if Higgs not initialized
        uint256 constraintMass = PRECISION;

        if (higgsField != address(0)) {
            (, uint256 mE, ) = IHiggsField(higgsField).getNodeMass(pair.expansionNodeId);
            (, uint256 mC, ) = IHiggsField(higgsField).getNodeMass(pair.constraintNodeId);
            if (mE > 0) expansionMass = mE;
            if (mC > 0) constraintMass = mC;
        }

        // Gradient-based correction: quartic growth for large deviations
        // force = deviation + deviation³ / PRECISION² (quartic potential gradient)
        uint256 force = deviation + (deviation * deviation * deviation) / (PRECISION * PRECISION);

        // Apply F=ma: acceleration = force / mass (each node corrected independently)
        uint256 expansionCorrection = (force * PRECISION) / expansionMass;
        uint256 constraintCorrection = (force * PRECISION) / constraintMass;

        // Apply partial correction (50% to avoid oscillation)
        expansionCorrection = expansionCorrection / 2;
        constraintCorrection = constraintCorrection / 2;

        if (expansionTooHigh) {
            pair.expansionEnergy = pair.expansionEnergy > expansionCorrection
                ? pair.expansionEnergy - expansionCorrection
                : 1;   // floor at 1 to prevent zero-energy
            pair.constraintEnergy += constraintCorrection;
        } else {
            pair.expansionEnergy += expansionCorrection;
            pair.constraintEnergy = pair.constraintEnergy > constraintCorrection
                ? pair.constraintEnergy - constraintCorrection
                : 1;
        }

        pair.currentRatio = (pair.expansionEnergy * PRECISION) / pair.constraintEnergy;
        redistributed = expansionCorrection + constraintCorrection;
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
