// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @notice Minimal oracle interface — returns price in USD with 8 decimals
interface IPriceOracle {
    function getPrice() external view returns (uint256);
}

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

    /// @notice Per-asset price oracle addresses (asset → oracle)
    mapping(address => address) public assetOracles;

    /// @notice Total reserve value in USD (8 decimals, updated via oracle)
    uint256 public totalReserveValueUSD;
    bool public paused;

    // ─── Events ──────────────────────────────────────────────────────────
    event ReserveDeposit(address indexed asset, address indexed depositor, uint256 amount, uint256 usdValue);
    event ReserveWithdrawal(address indexed asset, address indexed recipient, uint256 amount);
    event ReserveRebalance(uint256 newTotalUSD);
    event AssetRegistered(address indexed asset, string symbol, uint8 decimals);
    event AssetDeactivated(address indexed asset);
    event GovernanceUpdated(address indexed prev, address indexed next);
    event OracleUpdated(address indexed prev, address indexed next);
    event AssetOracleSet(address indexed asset, address indexed oracle);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "QUSDReserve: not owner");
        _;
    }

    modifier onlyGovernance() {
        require(msg.sender == governance, "QUSDReserve: not governance");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "QUSDReserve: paused");
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
    function deposit(address asset, uint256 amount, uint256 usdValue) external whenNotPaused {
        require(assets[asset].active, "QUSDReserve: asset not registered");
        require(amount > 0, "QUSDReserve: zero amount");

        assets[asset].totalDeposited += amount;
        assets[asset].currentBalance += amount;
        totalReserveValueUSD         += usdValue;

        emit ReserveDeposit(asset, msg.sender, amount, usdValue);
    }

    // ─── Withdrawals (Governance Only) ───────────────────────────────────
    /// @notice Withdraw from reserves. Governance-only.
    function withdraw(address asset, address recipient, uint256 amount) external onlyGovernance whenNotPaused {
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

    // ─── Per-Asset Oracle Integration ───────────────────────────────────
    /// @notice Set the price oracle for a reserve asset (owner only)
    /// @param asset Token address of the reserve asset
    /// @param oracle Address of the IPriceOracle contract for this asset
    function setAssetOracle(address asset, address oracle) external onlyOwner {
        require(assets[asset].active, "QUSDReserve: asset not registered");
        require(oracle != address(0), "QUSDReserve: zero oracle address");
        assetOracles[asset] = oracle;
        emit AssetOracleSet(asset, oracle);
    }

    /// @notice Get the current USD price for a reserve asset (8 decimals)
    /// @param asset Token address of the reserve asset
    /// @return price USD price with 8 decimals from the asset's oracle
    function getAssetPrice(address asset) public view returns (uint256 price) {
        address oracle = assetOracles[asset];
        require(oracle != address(0), "QUSDReserve: no oracle for asset");
        price = IPriceOracle(oracle).getPrice();
        require(price > 0, "QUSDReserve: oracle returned zero price");
    }

    /// @notice Compute the USD value of a single reserve asset
    /// @dev    value = (currentBalance * price) / 10^decimals
    ///         Both price and result use 8 decimal places.
    /// @param asset Token address of the reserve asset
    /// @return value USD value of the reserve holdings of this asset (8 decimals)
    function getAssetValue(address asset) public view returns (uint256 value) {
        AssetInfo storage info = assets[asset];
        require(info.active, "QUSDReserve: asset not active");
        uint256 price = getAssetPrice(asset);
        // balance is in asset-native decimals; price is USD with 8 decimals.
        // value = balance * price / 10^decimals  (result in 8-decimal USD)
        value = (info.currentBalance * price) / (10 ** info.decimals);
    }

    /// @notice Recompute totalReserveValueUSD by summing all active assets with oracles
    /// @dev    Assets without an oracle are skipped (their value is treated as 0).
    ///         Call this periodically or after price changes for an accurate total.
    /// @return total The newly computed total reserve value in USD (8 decimals)
    function computeTotalReserveValueUSD() external returns (uint256 total) {
        total = 0;
        for (uint256 i = 0; i < assetList.length; i++) {
            address asset = assetList[i];
            if (!assets[asset].active) continue;
            if (assetOracles[asset] == address(0)) continue;
            // Use try-catch so a single failing oracle doesn't revert the whole sum
            try IPriceOracle(assetOracles[asset]).getPrice() returns (uint256 price) {
                if (price > 0) {
                    total += (assets[asset].currentBalance * price) / (10 ** assets[asset].decimals);
                }
            } catch {
                // Skip assets whose oracle reverts
            }
        }
        totalReserveValueUSD = total;
        emit ReserveRebalance(total);
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

    function pause() external onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }
}
