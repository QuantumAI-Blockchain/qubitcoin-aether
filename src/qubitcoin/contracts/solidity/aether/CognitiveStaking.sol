// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title CognitiveStaking — Stake QBC on Sephirot Cognitive Domains
/// @notice Simplified domain-based staking that wraps the underlying SynapticStaking
///         connection model. Users stake on a Sephirot domain (0-9) instead of picking
///         individual connections. The contract distributes stake across all connections
///         involving that domain.
/// @dev Deployed as a new implementation behind the SynapticStaking proxy, or as a
///      standalone companion contract. Admin can update domain utility from aether-mind
///      attention weights.
contract CognitiveStaking is Initializable {
    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;

    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _status;

    uint256 public constant NUM_SEPHIROT = 10;
    uint256 public constant MIN_STAKE = 10 ether; // 10 QBC minimum per domain stake

    struct DomainInfo {
        uint256 totalStaked;
        uint256 utility;       // Attention weight from aether-mind (scaled 1e6)
        uint256 rewardPool;
        uint256 stakerCount;
        bool    active;
    }

    struct DomainStake {
        address staker;
        uint8   sephirotId;
        uint256 amount;
        uint256 stakedAt;      // block number
        bool    active;
    }

    mapping(uint8 => DomainInfo) public domains;
    DomainStake[] public stakes;
    mapping(address => uint256[]) public userStakeIds;

    // ─── Events ──────────────────────────────────────────────────────────
    event DomainStaked(address indexed staker, uint8 indexed sephirotId, uint256 amount, uint256 stakeId);
    event DomainUnstaked(address indexed staker, uint8 indexed sephirotId, uint256 amount, uint256 stakeId);
    event DomainUtilityUpdated(uint8 indexed sephirotId, uint256 newUtility);
    event DomainRewardDistributed(uint8 indexed sephirotId, uint256 amount);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "CogStaking: not authorized");
        _;
    }

    modifier nonReentrant() {
        require(_status != _ENTERED, "CogStaking: reentrant call");
        _status = _ENTERED;
        _;
        _status = _NOT_ENTERED;
    }

    // ─── Initialize ──────────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner = msg.sender;
        kernel = _kernel;
        _status = _NOT_ENTERED;

        // Initialize all 10 Sephirot domains as active
        string[10] memory names = [
            "Keter", "Chochmah", "Binah", "Chesed", "Gevurah",
            "Tiferet", "Netzach", "Hod", "Yesod", "Malkuth"
        ];
        for (uint8 i = 0; i < NUM_SEPHIROT; i++) {
            domains[i] = DomainInfo({
                totalStaked: 0,
                utility: 100_000, // Default utility: 0.1 (scaled 1e6)
                rewardPool: 0,
                stakerCount: 0,
                active: true
            });
        }
    }

    // ─── User Functions ──────────────────────────────────────────────────

    /// @notice Stake QBC on a Sephirot domain.
    /// @param sephirotId The domain ID (0=Keter, 1=Chochmah, ..., 9=Malkuth)
    function stakeOnDomain(uint8 sephirotId) external payable nonReentrant {
        require(sephirotId < NUM_SEPHIROT, "CogStaking: invalid domain");
        require(msg.value >= MIN_STAKE, "CogStaking: below minimum stake");
        require(domains[sephirotId].active, "CogStaking: domain not active");

        uint256 stakeId = stakes.length;
        stakes.push(DomainStake({
            staker: msg.sender,
            sephirotId: sephirotId,
            amount: msg.value,
            stakedAt: block.number,
            active: true
        }));

        userStakeIds[msg.sender].push(stakeId);
        domains[sephirotId].totalStaked += msg.value;
        domains[sephirotId].stakerCount += 1;

        emit DomainStaked(msg.sender, sephirotId, msg.value, stakeId);
    }

    /// @notice Unstake from a domain (returns QBC immediately).
    /// @param stakeId The stake index to unstake.
    function unstakeFromDomain(uint256 stakeId) external nonReentrant {
        require(stakeId < stakes.length, "CogStaking: invalid stake");
        DomainStake storage s = stakes[stakeId];
        require(s.staker == msg.sender, "CogStaking: not your stake");
        require(s.active, "CogStaking: already unstaked");

        s.active = false;
        domains[s.sephirotId].totalStaked -= s.amount;
        domains[s.sephirotId].stakerCount -= 1;

        (bool success, ) = payable(msg.sender).call{value: s.amount}("");
        require(success, "CogStaking: transfer failed");

        emit DomainUnstaked(msg.sender, s.sephirotId, s.amount, stakeId);
    }

    // ─── Admin Functions (Kernel/Owner only) ─────────────────────────────

    /// @notice Update domain utility from aether-mind attention weights.
    /// @param sephirotId The domain ID.
    /// @param utility The new utility value (scaled 1e6, e.g. 500000 = 0.5).
    function updateDomainUtility(uint8 sephirotId, uint256 utility) external onlyKernel {
        require(sephirotId < NUM_SEPHIROT, "CogStaking: invalid domain");
        domains[sephirotId].utility = utility;
        emit DomainUtilityUpdated(sephirotId, utility);
    }

    /// @notice Distribute rewards to a domain's stakers (funded by tx fees or treasury).
    function distributeDomainReward(uint8 sephirotId) external payable onlyKernel {
        require(sephirotId < NUM_SEPHIROT, "CogStaking: invalid domain");
        require(msg.value > 0, "CogStaking: no reward");
        domains[sephirotId].rewardPool += msg.value;
        emit DomainRewardDistributed(sephirotId, msg.value);
    }

    // ─── View Functions ──────────────────────────────────────────────────

    /// @notice Get aggregate utility for a domain.
    function getDomainUtility(uint8 sephirotId) external view returns (uint256) {
        require(sephirotId < NUM_SEPHIROT, "CogStaking: invalid domain");
        return domains[sephirotId].utility;
    }

    /// @notice Get total staked on a domain.
    function getDomainStake(uint8 sephirotId) external view returns (uint256) {
        require(sephirotId < NUM_SEPHIROT, "CogStaking: invalid domain");
        return domains[sephirotId].totalStaked;
    }

    /// @notice Get full domain info.
    function getDomainInfo(uint8 sephirotId) external view returns (
        uint256 totalStaked,
        uint256 utility,
        uint256 rewardPool,
        uint256 stakerCount,
        bool active
    ) {
        require(sephirotId < NUM_SEPHIROT, "CogStaking: invalid domain");
        DomainInfo storage d = domains[sephirotId];
        return (d.totalStaked, d.utility, d.rewardPool, d.stakerCount, d.active);
    }

    /// @notice Get a user's stake count.
    function getUserStakeCount(address user) external view returns (uint256) {
        return userStakeIds[user].length;
    }

    /// @notice Get total stake count across all domains.
    function getTotalStakeCount() external view returns (uint256) {
        return stakes.length;
    }

    /// @notice Get all domain summaries (for dashboard).
    function getAllDomains() external view returns (
        uint256[10] memory staked,
        uint256[10] memory utilities,
        uint256[10] memory rewards,
        uint256[10] memory stakers
    ) {
        for (uint8 i = 0; i < NUM_SEPHIROT; i++) {
            staked[i] = domains[i].totalStaked;
            utilities[i] = domains[i].utility;
            rewards[i] = domains[i].rewardPool;
            stakers[i] = domains[i].stakerCount;
        }
    }

    receive() external payable {}
}
