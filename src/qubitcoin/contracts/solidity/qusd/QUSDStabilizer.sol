// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title QUSDStabilizer — Peg Maintenance for QUSD
/// @notice Maintains the $1 USD peg by buying QUSD below $0.99 and selling above $1.01.
///         Stability fund is funded by governance and depleted by market operations.
contract QUSDStabilizer is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PRICE_DECIMALS = 8;
    uint256 public constant PEG_TARGET     = 1_00000000;  // $1.00 (8 decimals)
    uint256 public constant FLOOR_PRICE    = 99000000;    // $0.99
    uint256 public constant CEILING_PRICE  = 101000000;   // $1.01

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public governance;
    address public oracleAddress;
    address public qusdToken;

    uint256 public stabilityFundBalance;   // QBC held for stability operations
    uint256 public qusdHeld;               // QUSD held for ceiling defense
    uint256 public totalBuyInterventions;
    uint256 public totalSellInterventions;

    bool public autoRebalanceEnabled;

    // ─── Events ──────────────────────────────────────────────────────────
    event StabilityBuy(uint256 qusdAmount, uint256 qbcSpent, uint256 price, uint256 timestamp);
    event StabilitySell(uint256 qusdAmount, uint256 qbcReceived, uint256 price, uint256 timestamp);
    event FundDeposit(address indexed depositor, uint256 amount, bool isQBC);
    event FundWithdrawal(address indexed recipient, uint256 amount, bool isQBC);
    event AutoRebalanceTriggered(uint256 price, bool isBuy, uint256 amount);
    event AutoRebalanceToggled(bool enabled);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Stabilizer: not owner");
        _;
    }

    modifier onlyGovernance() {
        require(msg.sender == governance, "Stabilizer: not governance");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _governance, address _oracle, address _qusdToken) external initializer {
        owner         = msg.sender;
        governance    = _governance;
        oracleAddress = _oracle;
        qusdToken     = _qusdToken;
        autoRebalanceEnabled = true;
    }

    // ─── Stability Operations ────────────────────────────────────────────
    /// @notice Buy QUSD when price is below floor ($0.99) — floor defense
    /// @param qusdAmount Amount of QUSD to buy
    /// @param currentPrice Current QUSD price from oracle (8 decimals)
    function buyQUSD(uint256 qusdAmount, uint256 currentPrice) external onlyOwner {
        require(currentPrice < FLOOR_PRICE, "Stabilizer: price above floor");
        require(qusdAmount > 0, "Stabilizer: zero amount");

        // Calculate QBC cost at current price
        uint256 qbcCost = (qusdAmount * PEG_TARGET) / currentPrice;
        require(stabilityFundBalance >= qbcCost, "Stabilizer: insufficient QBC fund");

        stabilityFundBalance -= qbcCost;
        qusdHeld             += qusdAmount;
        totalBuyInterventions++;

        emit StabilityBuy(qusdAmount, qbcCost, currentPrice, block.timestamp);
    }

    /// @notice Sell QUSD when price is above ceiling ($1.01) — ceiling defense
    /// @param qusdAmount Amount of QUSD to sell
    /// @param currentPrice Current QUSD price from oracle (8 decimals)
    function sellQUSD(uint256 qusdAmount, uint256 currentPrice) external onlyOwner {
        require(currentPrice > CEILING_PRICE, "Stabilizer: price below ceiling");
        require(qusdHeld >= qusdAmount, "Stabilizer: insufficient QUSD");

        uint256 qbcReceived = (qusdAmount * currentPrice) / PEG_TARGET;

        qusdHeld              -= qusdAmount;
        stabilityFundBalance  += qbcReceived;
        totalSellInterventions++;

        emit StabilitySell(qusdAmount, qbcReceived, currentPrice, block.timestamp);
    }

    /// @notice Auto-rebalance check — can be called by anyone (e.g., keeper bot)
    /// @param currentPrice Current QUSD price from oracle
    /// @param amount Amount to buy or sell
    function triggerRebalance(uint256 currentPrice, uint256 amount) external {
        require(autoRebalanceEnabled, "Stabilizer: auto-rebalance disabled");
        require(amount > 0, "Stabilizer: zero amount");

        if (currentPrice < FLOOR_PRICE && stabilityFundBalance > 0) {
            uint256 qbcCost = (amount * PEG_TARGET) / currentPrice;
            uint256 actual = qbcCost > stabilityFundBalance ? stabilityFundBalance : qbcCost;
            uint256 actualQUSD = (actual * currentPrice) / PEG_TARGET;
            stabilityFundBalance -= actual;
            qusdHeld             += actualQUSD;
            totalBuyInterventions++;
            emit AutoRebalanceTriggered(currentPrice, true, actualQUSD);
        } else if (currentPrice > CEILING_PRICE && qusdHeld > 0) {
            uint256 sellAmount = amount > qusdHeld ? qusdHeld : amount;
            uint256 qbcReceived = (sellAmount * currentPrice) / PEG_TARGET;
            qusdHeld              -= sellAmount;
            stabilityFundBalance  += qbcReceived;
            totalSellInterventions++;
            emit AutoRebalanceTriggered(currentPrice, false, sellAmount);
        }
    }

    // ─── Fund Management ─────────────────────────────────────────────────
    /// @notice Deposit QBC into stability fund
    function depositQBC(uint256 amount) external onlyGovernance {
        require(amount > 0, "Stabilizer: zero deposit");
        stabilityFundBalance += amount;
        emit FundDeposit(msg.sender, amount, true);
    }

    /// @notice Deposit QUSD for ceiling defense
    function depositQUSD(uint256 amount) external onlyGovernance {
        require(amount > 0, "Stabilizer: zero deposit");
        qusdHeld += amount;
        emit FundDeposit(msg.sender, amount, false);
    }

    /// @notice Withdraw QBC from stability fund
    function withdrawQBC(address recipient, uint256 amount) external onlyGovernance {
        require(stabilityFundBalance >= amount, "Stabilizer: insufficient");
        stabilityFundBalance -= amount;
        emit FundWithdrawal(recipient, amount, true);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getStabilityStatus() external view returns (
        uint256 qbcFund,
        uint256 qusdReserve,
        uint256 buyCount,
        uint256 sellCount,
        bool    autoEnabled
    ) {
        return (stabilityFundBalance, qusdHeld, totalBuyInterventions, totalSellInterventions, autoRebalanceEnabled);
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setAutoRebalance(bool enabled) external onlyOwner {
        autoRebalanceEnabled = enabled;
        emit AutoRebalanceToggled(enabled);
    }

    function setGovernance(address newGov) external onlyOwner {
        governance = newGov;
    }

    function setOracle(address newOracle) external onlyOwner {
        oracleAddress = newOracle;
    }
}
