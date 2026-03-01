// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title GasOracle — Dynamic Gas Pricing for QVM
/// @notice Adjusts QVM gas price based on network utilization.
///         Provides gas price queries for contract execution cost estimation.
contract GasOracle is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant MAX_STALENESS = 1 hours; // Gas price expires after 1 hour

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;

    uint256 public baseFee;              // base gas price in QBC (8 decimals)
    uint256 public utilizationBps;       // network utilization in basis points (0-10000)
    uint256 public lastUpdated;          // block number of last update
    uint256 public lastUpdateTimestamp;  // timestamp of last update

    /// @notice Price history
    struct PricePoint {
        uint256 blockNumber;
        uint256 baseFee;
        uint256 utilizationBps;
        uint256 timestamp;
    }
    uint256 public constant MAX_PRICE_HISTORY = 10000;
    PricePoint[] public priceHistory;
    uint256 public priceHistoryHead;  // ring-buffer write index

    // ─── Events ──────────────────────────────────────────────────────────
    event GasPriceUpdated(uint256 oldFee, uint256 newFee, uint256 utilization, uint256 blockNumber);
    event BaseFeeAdjusted(uint256 newBaseFee, uint256 blockNumber);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "GasOracle: not authorized");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _kernel, uint256 _initialBaseFee) external initializer {
        owner   = msg.sender;
        kernel  = _kernel;
        baseFee = _initialBaseFee;
        lastUpdateTimestamp = block.timestamp;
    }

    // ─── Price Updates ───────────────────────────────────────────────────
    /// @notice Update gas price based on network utilization
    function updateGasPrice(uint256 newUtilization) external onlyKernel {
        require(newUtilization <= 10000, "GasOracle: utilization > 100%");

        uint256 oldFee = baseFee;
        utilizationBps = newUtilization;

        // EIP-1559-like adjustment: increase if >50% utilized, decrease if <50%
        if (newUtilization > 5000) {
            // Increase by up to 12.5%
            uint256 increase = (baseFee * (newUtilization - 5000)) / 40000;
            baseFee += increase;
        } else if (newUtilization < 5000) {
            // Decrease by up to 12.5%
            uint256 decrease = (baseFee * (5000 - newUtilization)) / 40000;
            if (decrease < baseFee) {
                baseFee -= decrease;
            } else {
                baseFee = 1; // minimum 1 unit
            }
        }

        lastUpdated = block.number;
        lastUpdateTimestamp = block.timestamp;

        PricePoint memory pp = PricePoint({
            blockNumber:    block.number,
            baseFee:        baseFee,
            utilizationBps: newUtilization,
            timestamp:      block.timestamp
        });

        // Ring buffer: overwrite oldest entry when at capacity
        if (priceHistory.length < MAX_PRICE_HISTORY) {
            priceHistory.push(pp);
        } else {
            priceHistory[priceHistoryHead] = pp;
        }
        priceHistoryHead = (priceHistoryHead + 1) % MAX_PRICE_HISTORY;

        emit GasPriceUpdated(oldFee, baseFee, newUtilization, block.number);
    }

    /// @notice Manually set base fee (owner override)
    function setBaseFee(uint256 newFee) external onlyKernel {
        require(newFee > 0, "GasOracle: zero fee");
        baseFee = newFee;
        lastUpdated = block.number;
        lastUpdateTimestamp = block.timestamp;
        emit BaseFeeAdjusted(newFee, block.number);
    }

    // ─── Queries ─────────────────────────────────────────────────────────

    /// @notice Get current gas price. Reverts if the price data is stale (older than MAX_STALENESS).
    function getGasPrice() external view returns (uint256) {
        require(lastUpdateTimestamp > 0, "GasOracle: never updated");
        require(
            block.timestamp - lastUpdateTimestamp <= MAX_STALENESS,
            "GasOracle: gas price is stale"
        );
        return baseFee;
    }

    /// @notice Get gas price without staleness check (for monitoring/display)
    function getGasPriceUnchecked() external view returns (uint256) {
        return baseFee;
    }

    /// @notice Check if the gas price data is stale
    function isStale() external view returns (bool) {
        if (lastUpdateTimestamp == 0) return true;
        return block.timestamp - lastUpdateTimestamp > MAX_STALENESS;
    }

    function getBaseFee() external view returns (uint256 fee, uint256 utilization, uint256 updatedAt) {
        return (baseFee, utilizationBps, lastUpdated);
    }

    function getPriceHistoryLength() external view returns (uint256) {
        return priceHistory.length;
    }
}
