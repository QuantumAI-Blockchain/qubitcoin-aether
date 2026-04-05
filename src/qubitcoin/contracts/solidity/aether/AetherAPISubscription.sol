// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title AetherAPISubscription — Prepaid QBC Balance for Aether API Access
/// @notice Users deposit QBC to a prepaid balance. The API gateway deducts per-call
///         fees based on the user's subscription tier. Owner can update tier pricing
///         and withdraw collected fees to the treasury.
/// @dev    All amounts use 8 decimals (QBC native). No NFTs — pure balance accounting.
contract AetherAPISubscription is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint8  public constant DECIMALS = 8;
    uint256 public constant MIN_DEPOSIT = 1 * 10**8;  // 1 QBC minimum deposit

    // ─── Tier Definitions ────────────────────────────────────────────────
    enum Tier { Free, Developer, Professional, Institutional }

    struct TierConfig {
        uint256 dailyRate;       // QBC per day (8 decimals), 0 = free
        uint256 chatLimit;       // max chat calls per day (0 = unlimited)
        uint256 queryLimit;      // max KG query calls per day (0 = unlimited)
        uint256 inferenceLimit;  // max inference calls per day (0 = unlimited)
    }

    // ─── User Account ────────────────────────────────────────────────────
    struct Account {
        uint256 balance;         // prepaid QBC balance (8 decimals)
        Tier    tier;            // current subscription tier
        uint256 lastDeduction;   // block number of last daily deduction
        uint256 totalDeposited;  // lifetime deposits
        uint256 totalSpent;      // lifetime spend (deductions + per-call fees)
    }

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public gateway;      // API gateway address authorized to deduct per-call fees
    uint256 public totalDeposits;
    uint256 public totalRevenue;
    uint256 public accountCount;
    bool private _locked;

    mapping(Tier => TierConfig) public tiers;
    mapping(address => Account)  public accounts;

    // ─── Per-call fee rates (set by owner, deducted by gateway) ──────────
    uint256 public chatFee;       // per chat call (default ~0.005 USD in QBC)
    uint256 public queryFee;      // per KG query
    uint256 public inferenceFee;  // per deep inference

    // ─── Events ──────────────────────────────────────────────────────────
    event Deposited(address indexed user, uint256 amount, uint256 newBalance);
    event TierChanged(address indexed user, Tier oldTier, Tier newTier);
    event FeesDeducted(address indexed user, uint256 amount, string callType);
    event DailyDeduction(address indexed user, uint256 amount, Tier tier);
    event Withdrawn(address indexed to, uint256 amount);
    event GatewayUpdated(address indexed oldGateway, address indexed newGateway);
    event TierConfigUpdated(Tier indexed tier, uint256 dailyRate, uint256 chatLimit);
    event FeeRatesUpdated(uint256 chatFee, uint256 queryFee, uint256 inferenceFee);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    modifier onlyGateway() {
        require(msg.sender == gateway, "not gateway");
        _;
    }

    modifier noReentrant() {
        require(!_locked, "reentrant");
        _locked = true;
        _;
        _locked = false;
    }

    // ─── Initialize ──────────────────────────────────────────────────────
    function initialize(address _owner, address _gateway) external initializer {
        require(_owner != address(0), "zero owner");
        owner = _owner;
        gateway = _gateway;

        // Default tier configs (QBC amounts with 8 decimals)
        // Free: 0 QBC/day, 5 chat, 10 queries, 0 inferences
        tiers[Tier.Free] = TierConfig({
            dailyRate: 0,
            chatLimit: 5,
            queryLimit: 10,
            inferenceLimit: 0
        });
        // Developer: ~1 QBC/day, 1000 chat, 500 queries, 100 inferences
        tiers[Tier.Developer] = TierConfig({
            dailyRate: 1 * 10**8,
            chatLimit: 1000,
            queryLimit: 500,
            inferenceLimit: 100
        });
        // Professional: ~10 QBC/day, 10000 chat, 5000 queries, 1000 inferences
        tiers[Tier.Professional] = TierConfig({
            dailyRate: 10 * 10**8,
            chatLimit: 10000,
            queryLimit: 5000,
            inferenceLimit: 1000
        });
        // Institutional: ~100 QBC/day, unlimited everything
        tiers[Tier.Institutional] = TierConfig({
            dailyRate: 100 * 10**8,
            chatLimit: 0,
            queryLimit: 0,
            inferenceLimit: 0
        });

        // Default per-call fees (~0.005 QBC per chat, 0.001 per query, 0.01 per inference)
        chatFee = 500000;       // 0.005 QBC
        queryFee = 100000;      // 0.001 QBC
        inferenceFee = 1000000; // 0.01 QBC
    }

    // ─── User Functions ──────────────────────────────────────────────────

    /// @notice Deposit QBC to prepaid balance (native QBC via msg.value)
    function deposit() external payable noReentrant {
        require(msg.value >= MIN_DEPOSIT, "below minimum deposit");

        Account storage acct = accounts[msg.sender];
        if (acct.totalDeposited == 0 && acct.balance == 0) {
            accountCount++;
            acct.lastDeduction = block.number;
        }

        acct.balance += msg.value;
        acct.totalDeposited += msg.value;
        totalDeposits += msg.value;

        emit Deposited(msg.sender, msg.value, acct.balance);
    }

    /// @notice Switch subscription tier (requires sufficient balance for daily rate)
    function setTier(Tier _tier) external {
        Account storage acct = accounts[msg.sender];
        TierConfig storage config = tiers[_tier];

        // Process any pending daily deduction before switching
        _processDailyDeduction(msg.sender);

        // Verify balance covers at least 1 day at new tier
        if (config.dailyRate > 0) {
            require(acct.balance >= config.dailyRate, "insufficient balance for tier");
        }

        Tier oldTier = acct.tier;
        acct.tier = _tier;
        emit TierChanged(msg.sender, oldTier, _tier);
    }

    /// @notice Withdraw unused balance back to caller
    function withdraw(uint256 amount) external noReentrant {
        Account storage acct = accounts[msg.sender];
        _processDailyDeduction(msg.sender);

        require(amount > 0 && amount <= acct.balance, "invalid amount");
        acct.balance -= amount;

        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
    }

    /// @notice Check remaining balance and tier info
    function getAccount(address user) external view returns (
        uint256 balance,
        Tier tier,
        uint256 dailyRate,
        uint256 chatLimit,
        uint256 queryLimit,
        uint256 inferenceLimit,
        uint256 totalDeposited_,
        uint256 totalSpent_
    ) {
        Account storage acct = accounts[user];
        TierConfig storage config = tiers[acct.tier];
        return (
            acct.balance,
            acct.tier,
            config.dailyRate,
            config.chatLimit,
            config.queryLimit,
            config.inferenceLimit,
            acct.totalDeposited,
            acct.totalSpent
        );
    }

    // ─── Gateway Functions (API server deducts per-call) ─────────────────

    /// @notice Deduct per-call fee from user balance. Called by API gateway.
    /// @param user The user whose balance to deduct from
    /// @param callType "chat", "query", or "inference"
    /// @return success True if deduction succeeded (user has balance)
    function deductFee(address user, string calldata callType) external onlyGateway returns (bool success) {
        Account storage acct = accounts[user];

        // Process pending daily deduction
        _processDailyDeduction(user);

        uint256 fee = _getFeeForType(callType);
        if (fee == 0 || acct.balance >= fee) {
            if (fee > 0) {
                acct.balance -= fee;
                acct.totalSpent += fee;
                totalRevenue += fee;
            }
            emit FeesDeducted(user, fee, callType);
            return true;
        }
        return false; // insufficient balance
    }

    /// @notice Batch deduct fees (for efficiency — multiple calls in one tx)
    function deductFeeBatch(
        address[] calldata users,
        string[] calldata callTypes
    ) external onlyGateway returns (uint256 successCount) {
        require(users.length == callTypes.length, "length mismatch");
        for (uint256 i = 0; i < users.length; i++) {
            Account storage acct = accounts[users[i]];
            uint256 fee = _getFeeForType(callTypes[i]);
            if (fee == 0 || acct.balance >= fee) {
                if (fee > 0) {
                    acct.balance -= fee;
                    acct.totalSpent += fee;
                    totalRevenue += fee;
                }
                successCount++;
            }
        }
    }

    // ─── Owner Functions ─────────────────────────────────────────────────

    /// @notice Withdraw collected revenue to treasury
    function withdrawRevenue(address payable to, uint256 amount) external onlyOwner noReentrant {
        require(to != address(0), "zero address");
        require(amount <= address(this).balance, "insufficient contract balance");

        (bool ok, ) = to.call{value: amount}("");
        require(ok, "transfer failed");
        emit Withdrawn(to, amount);
    }

    /// @notice Update tier configuration
    function setTierConfig(
        Tier _tier,
        uint256 _dailyRate,
        uint256 _chatLimit,
        uint256 _queryLimit,
        uint256 _inferenceLimit
    ) external onlyOwner {
        tiers[_tier] = TierConfig({
            dailyRate: _dailyRate,
            chatLimit: _chatLimit,
            queryLimit: _queryLimit,
            inferenceLimit: _inferenceLimit
        });
        emit TierConfigUpdated(_tier, _dailyRate, _chatLimit);
    }

    /// @notice Update per-call fee rates
    function setFeeRates(
        uint256 _chatFee,
        uint256 _queryFee,
        uint256 _inferenceFee
    ) external onlyOwner {
        chatFee = _chatFee;
        queryFee = _queryFee;
        inferenceFee = _inferenceFee;
        emit FeeRatesUpdated(_chatFee, _queryFee, _inferenceFee);
    }

    /// @notice Update API gateway address
    function setGateway(address _gateway) external onlyOwner {
        address old = gateway;
        gateway = _gateway;
        emit GatewayUpdated(old, _gateway);
    }

    /// @notice Transfer ownership
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "zero address");
        owner = newOwner;
    }

    // ─── Internal ────────────────────────────────────────────────────────

    /// @dev Process daily rate deduction based on blocks elapsed since last deduction.
    ///      ~26182 blocks/day at 3.3s block time.
    function _processDailyDeduction(address user) internal {
        Account storage acct = accounts[user];
        TierConfig storage config = tiers[acct.tier];

        if (config.dailyRate == 0 || acct.lastDeduction == 0) {
            acct.lastDeduction = block.number;
            return;
        }

        uint256 blocksElapsed = block.number - acct.lastDeduction;
        uint256 blocksPerDay = 26182; // ~24h at 3.3s blocks

        if (blocksElapsed < blocksPerDay) {
            return; // Not a full day yet
        }

        uint256 daysElapsed = blocksElapsed / blocksPerDay;
        uint256 totalDeduction = daysElapsed * config.dailyRate;

        if (totalDeduction > acct.balance) {
            // Insufficient balance — deduct what's available, downgrade to Free
            totalDeduction = acct.balance;
            acct.tier = Tier.Free;
            emit TierChanged(user, acct.tier, Tier.Free);
        }

        acct.balance -= totalDeduction;
        acct.totalSpent += totalDeduction;
        totalRevenue += totalDeduction;
        acct.lastDeduction = block.number;

        emit DailyDeduction(user, totalDeduction, acct.tier);
    }

    function _getFeeForType(string calldata callType) internal view returns (uint256) {
        bytes32 h = keccak256(bytes(callType));
        if (h == keccak256("chat")) return chatFee;
        if (h == keccak256("query")) return queryFee;
        if (h == keccak256("inference")) return inferenceFee;
        return 0;
    }

    /// @notice Fallback to accept native QBC deposits
    receive() external payable {
        Account storage acct = accounts[msg.sender];
        if (acct.totalDeposited == 0 && acct.balance == 0) {
            accountCount++;
            acct.lastDeduction = block.number;
        }
        acct.balance += msg.value;
        acct.totalDeposited += msg.value;
        totalDeposits += msg.value;
        emit Deposited(msg.sender, msg.value, acct.balance);
    }
}
