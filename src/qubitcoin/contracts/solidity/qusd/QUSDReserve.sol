// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title QUSDReserve — Multi-Asset Reserve Pool for QUSD Backing
/// @notice Holds reserves (QBC, ETH, BTC, USDT, USDC, DAI) that back QUSD.
///         All deposits reduce QUSD outstanding debt. Governance-only withdrawal.
contract QUSDReserve is Initializable {
    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public governance;
    address public debtLedger;
    address public oracleAddress;

    /// @notice Supported reserve asset metadata
    struct AssetInfo {
        string  symbol;
        uint8   decimals;
        bool    active;
        uint256 totalDeposited;
        uint256 totalWithdrawn;
        uint256 currentBalance;
    }

    /// @notice All registered reserve assets (token address → info)
    mapping(address => AssetInfo) public assets;
    address[] public assetList;

    /// @notice Total reserve value in USD (8 decimals, updated via oracle)
    uint256 public totalReserveValueUSD;

    // ─── Events ──────────────────────────────────────────────────────────
    event ReserveDeposit(address indexed asset, address indexed depositor, uint256 amount, uint256 usdValue);
    event ReserveWithdrawal(address indexed asset, address indexed recipient, uint256 amount);
    event ReserveRebalance(uint256 newTotalUSD);
    event AssetRegistered(address indexed asset, string symbol, uint8 decimals);
    event AssetDeactivated(address indexed asset);
    event GovernanceUpdated(address indexed prev, address indexed next);
    event OracleUpdated(address indexed prev, address indexed next);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "QUSDReserve: not owner");
        _;
    }

    modifier onlyGovernance() {
        require(msg.sender == governance, "QUSDReserve: not governance");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _governance, address _oracle) external initializer {
        owner      = msg.sender;
        governance = _governance;
        oracleAddress = _oracle;
    }

    // ─── Asset Management ────────────────────────────────────────────────
    /// @notice Register a new reserve asset (owner only)
    function registerAsset(address asset, string calldata symbol, uint8 assetDecimals) external onlyOwner {
        require(!assets[asset].active, "QUSDReserve: already registered");
        assets[asset] = AssetInfo({
            symbol: symbol,
            decimals: assetDecimals,
            active: true,
            totalDeposited: 0,
            totalWithdrawn: 0,
            currentBalance: 0
        });
        assetList.push(asset);
        emit AssetRegistered(asset, symbol, assetDecimals);
    }

    function deactivateAsset(address asset) external onlyOwner {
        require(assets[asset].active, "QUSDReserve: not active");
        assets[asset].active = false;
        emit AssetDeactivated(asset);
    }

    // ─── Deposits ────────────────────────────────────────────────────────
    /// @notice Deposit reserve assets. Every deposit is a debt payback event.
    /// @param asset Token address (address(0) for native QBC)
    /// @param amount Amount deposited
    /// @param usdValue USD value of this deposit (8 decimals, provided by caller or oracle)
    function deposit(address asset, uint256 amount, uint256 usdValue) external {
        require(assets[asset].active, "QUSDReserve: asset not registered");
        require(amount > 0, "QUSDReserve: zero amount");

        assets[asset].totalDeposited += amount;
        assets[asset].currentBalance += amount;
        totalReserveValueUSD         += usdValue;

        emit ReserveDeposit(asset, msg.sender, amount, usdValue);
    }

    // ─── Withdrawals (Governance Only) ───────────────────────────────────
    /// @notice Withdraw from reserves. Governance-only.
    function withdraw(address asset, address recipient, uint256 amount) external onlyGovernance {
        require(assets[asset].currentBalance >= amount, "QUSDReserve: insufficient");
        require(recipient != address(0), "QUSDReserve: zero recipient");

        assets[asset].currentBalance -= amount;
        assets[asset].totalWithdrawn += amount;

        emit ReserveWithdrawal(asset, recipient, amount);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    /// @notice Returns the reserve composition
    function getAssetCount() external view returns (uint256) {
        return assetList.length;
    }

    /// @notice Full reserve breakdown for a specific asset
    function getAssetInfo(address asset) external view returns (
        string memory symbol,
        uint8   assetDecimals,
        bool    active,
        uint256 deposited,
        uint256 withdrawn,
        uint256 balance
    ) {
        AssetInfo storage info = assets[asset];
        return (info.symbol, info.decimals, info.active, info.totalDeposited, info.totalWithdrawn, info.currentBalance);
    }

    /// @notice Revalue total reserves (called by oracle or owner)
    function revalue(uint256 newTotalUSD) external onlyOwner {
        totalReserveValueUSD = newTotalUSD;
        emit ReserveRebalance(newTotalUSD);
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setGovernance(address newGov) external onlyOwner {
        emit GovernanceUpdated(governance, newGov);
        governance = newGov;
    }

    function setOracle(address newOracle) external onlyOwner {
        emit OracleUpdated(oracleAddress, newOracle);
        oracleAddress = newOracle;
    }

    function setDebtLedger(address _debtLedger) external onlyOwner {
        debtLedger = _debtLedger;
    }
}
