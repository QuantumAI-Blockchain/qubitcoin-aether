// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/**
 * @title RevenueDistributor
 * @notice Perpetual revenue sharing using the Synthetix staking-rewards
 *         pattern (O(1) per claim). Fee revenue is deposited in QBC and
 *         distributed pro-rata to registered investors based on their
 *         USD-denominated share weight.
 *         Proxy-upgradeable via QBCProxy + ProxyAdmin.
 *         No OpenZeppelin dependencies -- all logic is custom.
 */

// Minimal QBC-20 interface (transfer, transferFrom, balanceOf)
interface IQBC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(
        address from,
        address to,
        uint256 amount
    ) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract RevenueDistributor is Initializable {
    // ---------------------------------------------------------------
    //  Custom ReentrancyGuard
    // ---------------------------------------------------------------
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _status;

    modifier nonReentrant() {
        require(_status != _ENTERED, "ReentrancyGuard: reentrant call");
        _status = _ENTERED;
        _;
        _status = _NOT_ENTERED;
    }

    // ---------------------------------------------------------------
    //  Pausable
    // ---------------------------------------------------------------
    bool public paused;

    modifier whenNotPaused() {
        require(!paused, "RevenueDistributor: paused");
        _;
    }

    // ---------------------------------------------------------------
    //  Access control
    // ---------------------------------------------------------------
    address public owner;

    modifier onlyOwner() {
        require(
            msg.sender == owner,
            "RevenueDistributor: caller is not the owner"
        );
        _;
    }

    // ---------------------------------------------------------------
    //  State
    // ---------------------------------------------------------------
    address public feeCollector;
    IQBC20 public qbcToken;

    /// @dev Accumulated reward per share, scaled by 1e18.
    uint256 public accRewardPerShare;

    /// @dev Sum of all investor shares (USD invested).
    uint256 public totalShares;

    /// @dev Total QBC distributed all-time.
    uint256 public totalDistributed;

    /// @dev Total registered investors.
    uint256 public totalRegistered;

    // ---------------------------------------------------------------
    //  Per-investor bookkeeping
    // ---------------------------------------------------------------
    struct InvestorInfo {
        uint256 shares;        // USD invested (weight)
        uint256 rewardDebt;    // snapshot of accRewardPerShare at last update
        uint256 totalClaimed;  // lifetime QBC claimed
        bool registered;
    }

    /// @dev keyed by bytes20 (QBC native address)
    mapping(bytes20 => InvestorInfo) public investors;

    // ---------------------------------------------------------------
    //  Events
    // ---------------------------------------------------------------
    event RevenueDeposited(uint256 amount, uint256 newAccPerShare);
    event RevenueClaimed(bytes20 indexed qbcAddress, uint256 amount);
    event InvestorRegistered(bytes20 indexed qbcAddress, uint256 shares);
    event FeeCollectorUpdated(address indexed oldCollector, address indexed newCollector);
    event PausedState(bool isPaused);

    // ---------------------------------------------------------------
    //  Initializer (replaces constructor for proxy pattern)
    // ---------------------------------------------------------------
    /**
     * @notice Initialize the revenue distributor. Called once via QBCProxy.
     * @param _qbcToken     QBC token address on QBC chain.
     * @param _feeCollector Address authorized to deposit revenue.
     */
    function initialize(address _qbcToken, address _feeCollector) external initializer {
        require(_qbcToken != address(0), "RevenueDistributor: zero token");
        require(
            _feeCollector != address(0),
            "RevenueDistributor: zero fee collector"
        );

        owner = msg.sender;
        qbcToken = IQBC20(_qbcToken);
        feeCollector = _feeCollector;
        _status = _NOT_ENTERED;
    }

    // ---------------------------------------------------------------
    //  Admin
    // ---------------------------------------------------------------
    function pause() external onlyOwner {
        paused = true;
        emit PausedState(true);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit PausedState(false);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "RevenueDistributor: zero owner");
        owner = newOwner;
    }

    function setFeeCollector(address _feeCollector) external onlyOwner {
        require(_feeCollector != address(0), "RevenueDistributor: zero fee collector");
        emit FeeCollectorUpdated(feeCollector, _feeCollector);
        feeCollector = _feeCollector;
    }

    // ---------------------------------------------------------------
    //  Fee collector: deposit revenue
    // ---------------------------------------------------------------
    /**
     * @notice Deposit QBC revenue to be distributed across all investors.
     *         Caller must have approved this contract for `amount` QBC.
     * @param amount QBC amount to distribute.
     */
    function depositRevenue(uint256 amount) external whenNotPaused {
        require(
            msg.sender == feeCollector,
            "RevenueDistributor: caller is not fee collector"
        );
        require(amount > 0, "RevenueDistributor: zero amount");
        require(totalShares > 0, "RevenueDistributor: no investors");

        // Pull tokens from fee collector
        require(
            qbcToken.transferFrom(msg.sender, address(this), amount),
            "RevenueDistributor: transfer failed"
        );

        // Update global accumulator
        accRewardPerShare += (amount * 1e18) / totalShares;
        totalDistributed += amount;

        emit RevenueDeposited(amount, accRewardPerShare);
    }

    // ---------------------------------------------------------------
    //  Owner: batch register investors
    // ---------------------------------------------------------------
    /**
     * @notice Register investors with their share weights (USD invested).
     *         Max 100 per call to bound gas usage.
     * @param addresses Array of investor QBC addresses (bytes20).
     * @param shares    Array of share weights (USD invested).
     */
    function registerInvestors(
        bytes20[] calldata addresses,
        uint256[] calldata shares
    ) external onlyOwner {
        require(
            addresses.length == shares.length,
            "RevenueDistributor: length mismatch"
        );
        require(
            addresses.length > 0 && addresses.length <= 100,
            "RevenueDistributor: batch size 1-100"
        );

        for (uint256 i = 0; i < addresses.length; i++) {
            bytes20 addr = addresses[i];
            uint256 share = shares[i];

            require(share > 0, "RevenueDistributor: zero shares");
            require(
                !investors[addr].registered,
                "RevenueDistributor: already registered"
            );

            investors[addr] = InvestorInfo({
                shares: share,
                rewardDebt: (share * accRewardPerShare) / 1e18,
                totalClaimed: 0,
                registered: true
            });

            totalShares += share;
            totalRegistered++;

            emit InvestorRegistered(addr, share);
        }
    }

    // ---------------------------------------------------------------
    //  Investor: claim accumulated revenue
    // ---------------------------------------------------------------
    /**
     * @notice Claim all pending QBC revenue. O(1) computation using the
     *         Synthetix accumulator pattern. CEI ordering.
     */
    function claimRevenue() external nonReentrant whenNotPaused {
        bytes20 qbcAddress = bytes20(msg.sender);
        InvestorInfo storage info = investors[qbcAddress];

        require(info.registered, "RevenueDistributor: not registered");

        uint256 pending = ((info.shares * accRewardPerShare) / 1e18) -
            info.rewardDebt;

        require(pending > 0, "RevenueDistributor: nothing to claim");

        // --- Effects ---
        info.rewardDebt = (info.shares * accRewardPerShare) / 1e18;
        info.totalClaimed += pending;

        // --- Interactions ---
        require(
            qbcToken.transfer(msg.sender, pending),
            "RevenueDistributor: transfer failed"
        );

        emit RevenueClaimed(qbcAddress, pending);
    }

    // ---------------------------------------------------------------
    //  View: pending revenue for an address
    // ---------------------------------------------------------------
    function pendingRevenue(bytes20 qbcAddress)
        external
        view
        returns (uint256)
    {
        InvestorInfo storage info = investors[qbcAddress];
        if (!info.registered) {
            return 0;
        }
        return
            ((info.shares * accRewardPerShare) / 1e18) - info.rewardDebt;
    }

    // ---------------------------------------------------------------
    //  View: full investor info
    // ---------------------------------------------------------------
    function getInvestorInfo(bytes20 qbcAddress)
        external
        view
        returns (
            uint256 shares,
            uint256 totalClaimed,
            uint256 pending
        )
    {
        InvestorInfo storage info = investors[qbcAddress];
        shares = info.shares;
        totalClaimed = info.totalClaimed;

        if (info.registered) {
            pending =
                ((info.shares * accRewardPerShare) / 1e18) -
                info.rewardDebt;
        }
    }

    // ---------------------------------------------------------------
    //  View: global info
    // ---------------------------------------------------------------
    function getGlobalInfo()
        external
        view
        returns (
            uint256 totalShares_,
            uint256 totalDistributed_,
            uint256 accPerShare,
            uint256 investorCount
        )
    {
        totalShares_ = totalShares;
        totalDistributed_ = totalDistributed;
        accPerShare = accRewardPerShare;
        investorCount = totalRegistered;
    }
}
