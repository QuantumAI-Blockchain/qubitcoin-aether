// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title QUSDOracle — Multi-Source Price Feed for QUSD Fee Pegging
/// @notice Aggregates QBC/USD price from multiple authorized feeders using median.
///         Staleness detection reverts if price is older than maxAge blocks.
///         Used by Aether fee system, contract deployment fees, and bridge pricing.
contract QUSDOracle is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PRICE_DECIMALS = 8; // prices in 8 decimal USD

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;

    /// @notice Maximum blocks before a price is considered stale
    uint256 public maxAge;

    /// @notice Authorized price feeders
    mapping(address => bool) public isFeedAuthorized;
    address[] public feeders;

    /// @notice Price data from each feeder
    struct PriceData {
        uint256 price;       // QBC/USD price (8 decimals)
        uint256 blockNumber; // block when price was set
        uint256 timestamp;   // timestamp when price was set
    }
    mapping(address => PriceData) public feederPrices;

    /// @notice Aggregated price (median of all feeders)
    uint256 public aggregatedPrice;
    uint256 public aggregatedBlock;
    uint256 public aggregatedTimestamp;

    /// @notice QUSD/USD peg deviation (basis points from $1.00)
    int256 public pegDeviation; // positive = above peg, negative = below

    // ─── Events ──────────────────────────────────────────────────────────
    event PriceUpdated(address indexed feeder, uint256 price, uint256 blockNumber);
    event AggregatedPriceUpdated(uint256 price, uint256 feedCount, uint256 blockNumber);
    event FeederAdded(address indexed feeder);
    event FeederRemoved(address indexed feeder);
    event StalePriceDetected(address indexed feeder, uint256 lastBlock, uint256 currentBlock);
    event PegDeviationUpdated(int256 deviationBps);
    event MaxAgeUpdated(uint256 oldAge, uint256 newAge);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Oracle: not owner");
        _;
    }

    modifier onlyFeeder() {
        require(isFeedAuthorized[msg.sender], "Oracle: not authorized");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    /// @param _maxAge Maximum block age before price is stale
    function initialize(uint256 _maxAge) external initializer {
        owner  = msg.sender;
        maxAge = _maxAge;
    }

    // ─── Feeder Management ───────────────────────────────────────────────
    function addFeeder(address feeder) external onlyOwner {
        require(!isFeedAuthorized[feeder], "Oracle: already feeder");
        isFeedAuthorized[feeder] = true;
        feeders.push(feeder);
        emit FeederAdded(feeder);
    }

    function removeFeeder(address feeder) external onlyOwner {
        require(isFeedAuthorized[feeder], "Oracle: not feeder");
        isFeedAuthorized[feeder] = false;
        emit FeederRemoved(feeder);
    }

    // ─── Price Submission ────────────────────────────────────────────────
    /// @notice Submit a QBC/USD price (authorized feeders only)
    function submitPrice(uint256 price) external onlyFeeder {
        require(price > 0, "Oracle: zero price");

        feederPrices[msg.sender] = PriceData({
            price:       price,
            blockNumber: block.number,
            timestamp:   block.timestamp
        });

        emit PriceUpdated(msg.sender, price, block.number);
        _aggregate();
    }

    /// @notice Submit QUSD/USD peg deviation in basis points
    function submitPegDeviation(int256 deviationBps) external onlyFeeder {
        pegDeviation = deviationBps;
        emit PegDeviationUpdated(deviationBps);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    /// @notice Get the current aggregated price. Reverts if stale.
    function getPrice() external view returns (uint256 price, uint256 timestamp, uint256 feedCount) {
        require(aggregatedPrice > 0, "Oracle: no price");
        require(block.number - aggregatedBlock <= maxAge, "Oracle: stale price");
        return (aggregatedPrice, aggregatedTimestamp, _activeFeedCount());
    }

    /// @notice Get price without staleness check (for fallback scenarios)
    function getPriceUnsafe() external view returns (uint256 price, uint256 timestamp, bool isStale) {
        isStale = aggregatedPrice == 0 || (block.number - aggregatedBlock > maxAge);
        return (aggregatedPrice, aggregatedTimestamp, isStale);
    }

    /// @notice Number of active feeders
    function feederCount() external view returns (uint256) {
        return feeders.length;
    }

    // ─── Internal ────────────────────────────────────────────────────────
    /// @dev Aggregate prices using median of non-stale feeders
    function _aggregate() internal {
        uint256[] memory prices = new uint256[](feeders.length);
        uint256 count = 0;

        for (uint256 i = 0; i < feeders.length; i++) {
            address f = feeders[i];
            if (!isFeedAuthorized[f]) continue;
            PriceData storage pd = feederPrices[f];
            if (pd.price == 0) continue;

            // Check staleness per feeder
            if (block.number - pd.blockNumber > maxAge) {
                emit StalePriceDetected(f, pd.blockNumber, block.number);
                continue;
            }
            prices[count] = pd.price;
            count++;
        }

        if (count == 0) return;

        // Sort for median (simple insertion sort — small array)
        for (uint256 i = 1; i < count; i++) {
            uint256 key = prices[i];
            uint256 j = i;
            while (j > 0 && prices[j - 1] > key) {
                prices[j] = prices[j - 1];
                j--;
            }
            prices[j] = key;
        }

        // Median
        aggregatedPrice     = count % 2 == 1
            ? prices[count / 2]
            : (prices[count / 2 - 1] + prices[count / 2]) / 2;
        aggregatedBlock     = block.number;
        aggregatedTimestamp  = block.timestamp;

        emit AggregatedPriceUpdated(aggregatedPrice, count, block.number);
    }

    function _activeFeedCount() internal view returns (uint256 count) {
        for (uint256 i = 0; i < feeders.length; i++) {
            if (isFeedAuthorized[feeders[i]] && feederPrices[feeders[i]].price > 0) {
                count++;
            }
        }
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setMaxAge(uint256 newMaxAge) external onlyOwner {
        emit MaxAgeUpdated(maxAge, newMaxAge);
        maxAge = newMaxAge;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Oracle: zero owner");
        owner = newOwner;
    }
}
