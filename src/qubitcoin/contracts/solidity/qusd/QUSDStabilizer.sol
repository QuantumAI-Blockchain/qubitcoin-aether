// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";
import "../interfaces/IQUSD.sol";
import "../interfaces/IQBC20.sol";

/// @notice Minimal oracle interface for reading QUSD price
interface IStabilizerOracle {
    function getPrice() external view returns (uint256);
}

/// @title QUSDStabilizer — Peg Maintenance for QUSD
/// @notice Maintains the $1 USD peg by buying QUSD below $0.99 and selling above $1.01.
///         Stability fund is funded by governance and depleted by market operations.
contract QUSDStabilizer is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PRICE_DECIMALS = 8;

    // ─── Configurable Peg Bands ──────────────────────────────────────
    uint256 public pegTarget;     // $1.00 (8 decimals)
    uint256 public floorPrice;    // $0.99
    uint256 public ceilingPrice;  // $1.01

    // ─── Reentrancy Guard ──────────────────────────────────────────────
    bool private _locked;
    modifier nonReentrant() {
        require(!_locked, "QUSDStabilizer: reentrant call");
        _locked = true;
        _;
        _locked = false;
    }

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public governance;
    address public oracleAddress;
    address public qusdToken;
    IQBC20  public qbcToken;       // QBC ERC-20 token for actual transfers
    IQBC20  public qusdTokenERC20; // QUSD as ERC-20 for transferFrom in deposits

    /// @notice Maximum trade size per stabilization operation
    uint256 public maxTradeSize = 1_000_000e18;

    uint256 public stabilityFundBalance;   // QBC held for stability operations
    uint256 public qusdHeld;               // QUSD held for ceiling defense
    uint256 public totalBuyInterventions;
    uint256 public totalSellInterventions;

    bool public autoRebalanceEnabled;
    bool public paused;
    uint256 public lastRebalanceBlock;
    uint256 public constant REBALANCE_COOLDOWN = 10; // min blocks between rebalances

    // ─── Events ──────────────────────────────────────────────────────────
    event StabilityBuy(uint256 qusdAmount, uint256 qbcSpent, uint256 price, uint256 timestamp);
    event StabilitySell(uint256 qusdAmount, uint256 qbcReceived, uint256 price, uint256 timestamp);
    event FundDeposit(address indexed depositor, uint256 amount, bool isQBC);
    event FundWithdrawal(address indexed recipient, uint256 amount, bool isQBC);
    event AutoRebalanceTriggered(uint256 price, bool isBuy, uint256 amount);
    event AutoRebalanceToggled(bool enabled);
    event PegBandsUpdated(uint256 newFloor, uint256 newCeiling);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Stabilizer: not owner");
        _;
    }

    modifier onlyGovernance() {
        require(msg.sender == governance, "Stabilizer: not governance");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "Stabilizer: paused");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(
        address _governance,
        address _oracle,
        address _qusdToken,
        address _qbcToken
    ) external initializer {
        owner         = msg.sender;
        governance    = _governance;
        oracleAddress = _oracle;
        qusdToken     = _qusdToken;
        qbcToken      = IQBC20(_qbcToken);
        qusdTokenERC20 = IQBC20(_qusdToken);  // QUSD implements ERC-20 (IQBC20-compatible)
        pegTarget    = 1_00000000;  // $1.00
        floorPrice   = 99000000;    // $0.99
        ceilingPrice = 101000000;   // $1.01
        autoRebalanceEnabled = true;
    }

    // ─── Oracle Price Reading ────────────────────────────────────────────
    /// @notice Read the current QUSD price from the oracle contract
    /// @return price Current QUSD price with 8 decimals
    function getOraclePrice() public view returns (uint256 price) {
        require(oracleAddress != address(0), "Stabilizer: oracle not set");
        price = IStabilizerOracle(oracleAddress).getPrice();
        require(price > 0, "Stabilizer: oracle returned zero price");
    }

    // ─── Stability Operations ────────────────────────────────────────────
    /// @notice Buy QUSD when price is below floor ($0.99) — floor defense.
    ///         Mints QUSD to the stabilizer's holdings via the QUSD token contract.
    /// @param qusdAmount Amount of QUSD to buy
    function buyQUSD(uint256 qusdAmount) external onlyOwner whenNotPaused nonReentrant {
        uint256 currentPrice = getOraclePrice();
        require(currentPrice < floorPrice, "Stabilizer: price above floor");
        require(qusdAmount > 0, "Stabilizer: zero amount");
        require(qusdAmount <= maxTradeSize, "Stabilizer: exceeds max trade size");

        // Calculate QBC cost at current price
        uint256 qbcCost = (qusdAmount * pegTarget) / currentPrice;
        require(stabilityFundBalance >= qbcCost, "Stabilizer: insufficient QBC fund");

        stabilityFundBalance -= qbcCost;
        qusdHeld             += qusdAmount;
        totalBuyInterventions++;

        // Cross-call: mint QUSD to stabilizer for floor defense
        if (qusdToken != address(0)) {
            IQUSD(qusdToken).mint(address(this), qusdAmount);
        }

        emit StabilityBuy(qusdAmount, qbcCost, currentPrice, block.timestamp);
    }

    /// @notice Sell QUSD when price is above ceiling ($1.01) — ceiling defense.
    ///         Burns QUSD from the stabilizer's holdings via the QUSD token contract.
    /// @param qusdAmount Amount of QUSD to sell
    function sellQUSD(uint256 qusdAmount) external onlyOwner whenNotPaused nonReentrant {
        uint256 currentPrice = getOraclePrice();
        require(currentPrice > ceilingPrice, "Stabilizer: price below ceiling");
        require(qusdHeld >= qusdAmount, "Stabilizer: insufficient QUSD");
        require(qusdAmount <= maxTradeSize, "Stabilizer: exceeds max trade size");

        uint256 qbcReceived = (qusdAmount * currentPrice) / pegTarget;

        qusdHeld              -= qusdAmount;
        stabilityFundBalance  += qbcReceived;
        totalSellInterventions++;

        // Cross-call: burn QUSD from stabilizer for ceiling defense
        if (qusdToken != address(0)) {
            IQUSD(qusdToken).burn(qusdAmount);
        }

        emit StabilitySell(qusdAmount, qbcReceived, currentPrice, block.timestamp);
    }

    /// @notice Auto-rebalance check — can be called by anyone (e.g., keeper bot)
    /// @param amount Amount to buy or sell
    function triggerRebalance(uint256 amount) external whenNotPaused nonReentrant {
        require(autoRebalanceEnabled, "Stabilizer: auto-rebalance disabled");
        uint256 currentPrice = getOraclePrice();
        require(amount > 0, "Stabilizer: zero amount");
        require(amount <= maxTradeSize, "Stabilizer: exceeds max trade size");
        require(block.number >= lastRebalanceBlock + REBALANCE_COOLDOWN, "Stabilizer: cooldown active");
        lastRebalanceBlock = block.number;

        if (currentPrice < floorPrice && stabilityFundBalance > 0) {
            uint256 qbcCost = (amount * pegTarget) / currentPrice;
            uint256 actual = qbcCost > stabilityFundBalance ? stabilityFundBalance : qbcCost;
            uint256 actualQUSD = (actual * currentPrice) / pegTarget;
            stabilityFundBalance -= actual;
            qusdHeld             += actualQUSD;
            totalBuyInterventions++;
            emit AutoRebalanceTriggered(currentPrice, true, actualQUSD);
        } else if (currentPrice > ceilingPrice && qusdHeld > 0) {
            uint256 sellAmount = amount > qusdHeld ? qusdHeld : amount;
            uint256 qbcReceived = (sellAmount * currentPrice) / pegTarget;
            qusdHeld              -= sellAmount;
            stabilityFundBalance  += qbcReceived;
            totalSellInterventions++;
            emit AutoRebalanceTriggered(currentPrice, false, sellAmount);
        }
    }

    // ─── Fund Management ─────────────────────────────────────────────────
    /// @notice Deposit QBC into stability fund. Caller must approve this contract first.
    function depositQBC(uint256 amount) external onlyGovernance {
        require(amount > 0, "Stabilizer: zero deposit");
        require(qbcToken.transferFrom(msg.sender, address(this), amount), "Stabilizer: QBC transfer failed");
        stabilityFundBalance += amount;
        emit FundDeposit(msg.sender, amount, true);
    }

    /// @notice Deposit QUSD for ceiling defense. Caller must approve this contract first.
    function depositQUSD(uint256 amount) external onlyGovernance {
        require(amount > 0, "Stabilizer: zero deposit");
        require(qusdTokenERC20.transferFrom(msg.sender, address(this), amount), "Stabilizer: QUSD transfer failed");
        qusdHeld += amount;
        emit FundDeposit(msg.sender, amount, false);
    }

    /// @notice Withdraw QBC from stability fund
    function withdrawQBC(address recipient, uint256 amount) external onlyGovernance {
        require(stabilityFundBalance >= amount, "Stabilizer: insufficient");
        stabilityFundBalance -= amount;
        require(qbcToken.transfer(recipient, amount), "Stabilizer: QBC transfer failed");
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
        require(newGov != address(0), "Stabilizer: zero address");
        governance = newGov;
    }

    function setOracle(address newOracle) external onlyOwner {
        require(newOracle != address(0), "Stabilizer: zero address");
        oracleAddress = newOracle;
    }

    /// @notice Update max trade size per stabilization operation
    function setMaxTradeSize(uint256 _maxTradeSize) external onlyOwner {
        require(_maxTradeSize > 0, "Stabilizer: zero max trade size");
        maxTradeSize = _maxTradeSize;
    }

    /// @notice Update peg bands (governance). Min 0.01 spread.
    function setPegBands(uint256 _floor, uint256 _ceiling) external onlyOwner {
        require(_floor < pegTarget, "Stabilizer: floor >= target");
        require(_ceiling > pegTarget, "Stabilizer: ceiling <= target");
        require(_ceiling - _floor >= 1000000, "Stabilizer: bands too narrow");
        floorPrice   = _floor;
        ceilingPrice = _ceiling;
        emit PegBandsUpdated(_floor, _ceiling);
    }

    function pause() external onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }
}
