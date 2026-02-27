// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title SynapticStaking — Stake QBC on Neural Connections
/// @notice Stake QBC on specific Sephirot connections (edges) to strengthen or weaken them.
///         High-utility connections earn rewards. Inspired by synaptic plasticity.
///         Users can stake/unstake directly; admin functions remain kernel-only.
contract SynapticStaking is Initializable {
    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;

    uint256 public constant MIN_STAKE = 100 ether;           // 100 QBC minimum
    uint256 public constant MAX_STAKE_PER_CONNECTION = 1000000 ether; // 1M QBC max per connection
    uint256 public constant UNSTAKING_DELAY = 183272;        // ~7 days at 3.3s blocks

    struct Connection {
        uint8   fromNodeId;
        uint8   toNodeId;
        uint256 totalStaked;
        uint256 utilityScore;    // × 1000 (how useful this connection is)
        uint256 totalRewards;
        uint256 rewardsPerToken; // accumulated rewards per staked token (scaled 1e18)
        bool    active;
    }

    struct Stake {
        address staker;
        uint256 connectionId;
        uint256 amount;
        uint256 stakedAt;
        uint256 rewardsClaimed;
        uint256 rewardsPerTokenPaid; // snapshot of rewardsPerToken at stake time
    }

    struct UnstakeRequest {
        uint256 stakeIndex;
        uint256 connectionId;
        uint256 amount;
        uint256 unlockBlock;
    }

    /// @notice Connection id = fromNodeId * 10 + toNodeId
    mapping(uint256 => Connection) public connections;
    uint256[] public connectionIds;

    mapping(address => Stake[]) public userStakes;
    mapping(address => UnstakeRequest[]) public unstakeRequests;
    mapping(address => uint256) public pendingRewards;

    uint256 public totalStaked;
    uint256 public totalRewardsDistributed;

    // ─── Events ──────────────────────────────────────────────────────────
    event ConnectionStaked(address indexed staker, uint256 indexed connectionId, uint256 amount);
    event ConnectionUnstaked(address indexed staker, uint256 indexed connectionId, uint256 amount);
    event UnstakeRequested(address indexed staker, uint256 indexed connectionId, uint256 amount, uint256 unlockBlock);
    event UnstakeCompleted(address indexed staker, uint256 indexed connectionId, uint256 amount);
    event RewardClaimed(address indexed staker, uint256 amount);
    event UtilityUpdated(uint256 indexed connectionId, uint256 oldUtility, uint256 newUtility);
    event ConnectionActivated(uint256 indexed connectionId, uint8 from, uint8 to);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Synaptic: not authorized");
        _;
    }

    // ─── Initialization ─────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Connection Setup (admin only) ───────────────────────────────────
    function activateConnection(uint8 fromNodeId, uint8 toNodeId) external onlyKernel {
        uint256 connId = uint256(fromNodeId) * 10 + uint256(toNodeId);
        require(!connections[connId].active, "Synaptic: already active");

        connections[connId] = Connection({
            fromNodeId:      fromNodeId,
            toNodeId:        toNodeId,
            totalStaked:     0,
            utilityScore:    500, // baseline 0.5
            totalRewards:    0,
            rewardsPerToken: 0,
            active:          true
        });
        connectionIds.push(connId);
        emit ConnectionActivated(connId, fromNodeId, toNodeId);
    }

    // ─── Public User Staking ─────────────────────────────────────────────

    /// @notice Stake QBC on a Sephirot connection. Payable — send QBC with the call.
    /// @param connectionId The connection ID (fromNodeId * 10 + toNodeId)
    function userStake(uint256 connectionId) external payable {
        require(connections[connectionId].active, "Synaptic: not active");
        require(msg.value >= MIN_STAKE, "Synaptic: below minimum stake");
        require(
            connections[connectionId].totalStaked + msg.value <= MAX_STAKE_PER_CONNECTION,
            "Synaptic: exceeds max stake per connection"
        );

        connections[connectionId].totalStaked += msg.value;
        totalStaked += msg.value;

        userStakes[msg.sender].push(Stake({
            staker:               msg.sender,
            connectionId:         connectionId,
            amount:               msg.value,
            stakedAt:             block.timestamp,
            rewardsClaimed:       0,
            rewardsPerTokenPaid:  connections[connectionId].rewardsPerToken
        }));

        emit ConnectionStaked(msg.sender, connectionId, msg.value);
    }

    /// @notice Request unstaking. Funds unlock after UNSTAKING_DELAY blocks.
    /// @param stakeIndex Index in the caller's userStakes array
    function userRequestUnstake(uint256 stakeIndex) external {
        require(stakeIndex < userStakes[msg.sender].length, "Synaptic: invalid index");
        Stake storage s = userStakes[msg.sender][stakeIndex];
        require(s.amount > 0, "Synaptic: already unstaking");

        uint256 amount = s.amount;
        uint256 connId = s.connectionId;
        uint256 unlockBlock = block.number + UNSTAKING_DELAY;

        // Accrue pending rewards before unstaking
        _accrueRewards(msg.sender, stakeIndex);

        connections[connId].totalStaked -= amount;
        totalStaked -= amount;

        // Record unstake request
        unstakeRequests[msg.sender].push(UnstakeRequest({
            stakeIndex:   stakeIndex,
            connectionId: connId,
            amount:       amount,
            unlockBlock:  unlockBlock
        }));

        // Zero out the stake (don't remove — index stability for unstake requests)
        s.amount = 0;

        emit UnstakeRequested(msg.sender, connId, amount, unlockBlock);
    }

    /// @notice Complete unstaking after the delay has passed.
    /// @param requestIndex Index in the caller's unstakeRequests array
    function userCompleteUnstake(uint256 requestIndex) external {
        require(requestIndex < unstakeRequests[msg.sender].length, "Synaptic: invalid request");
        UnstakeRequest storage req = unstakeRequests[msg.sender][requestIndex];
        require(req.amount > 0, "Synaptic: already completed");
        require(block.number >= req.unlockBlock, "Synaptic: still locked");

        uint256 amount = req.amount;
        uint256 connId = req.connectionId;
        req.amount = 0;

        (bool success, ) = payable(msg.sender).call{value: amount}("");
        require(success, "Synaptic: transfer failed");
        emit UnstakeCompleted(msg.sender, connId, amount);
    }

    /// @notice Claim accumulated staking rewards.
    function claimRewards() external {
        // Accrue rewards across all active stakes
        for (uint256 i = 0; i < userStakes[msg.sender].length; i++) {
            if (userStakes[msg.sender][i].amount > 0) {
                _accrueRewards(msg.sender, i);
            }
        }

        uint256 reward = pendingRewards[msg.sender];
        require(reward > 0, "Synaptic: no rewards");

        pendingRewards[msg.sender] = 0;
        (bool success, ) = payable(msg.sender).call{value: reward}("");
        require(success, "Synaptic: transfer failed");
        emit RewardClaimed(msg.sender, reward);
    }

    /// @notice View pending rewards for a staker.
    function viewPendingRewards(address staker) external view returns (uint256) {
        uint256 total = pendingRewards[staker];
        for (uint256 i = 0; i < userStakes[staker].length; i++) {
            Stake storage s = userStakes[staker][i];
            if (s.amount > 0) {
                Connection storage conn = connections[s.connectionId];
                uint256 earned = (s.amount * (conn.rewardsPerToken - s.rewardsPerTokenPaid)) / 1e18;
                total += earned;
            }
        }
        return total;
    }

    // ─── Internal reward accrual ─────────────────────────────────────────

    function _accrueRewards(address staker, uint256 stakeIndex) internal {
        Stake storage s = userStakes[staker][stakeIndex];
        Connection storage conn = connections[s.connectionId];
        uint256 earned = (s.amount * (conn.rewardsPerToken - s.rewardsPerTokenPaid)) / 1e18;
        pendingRewards[staker] += earned;
        s.rewardsPerTokenPaid = conn.rewardsPerToken;
        s.rewardsClaimed += earned;
    }

    // ─── Kernel-Only Admin Functions ─────────────────────────────────────

    /// @notice Admin: stake on behalf of a user (kernel-managed staking)
    function stake(address staker, uint256 connectionId, uint256 amount) external onlyKernel {
        require(connections[connectionId].active, "Synaptic: not active");
        require(amount > 0, "Synaptic: zero amount");

        connections[connectionId].totalStaked += amount;
        totalStaked += amount;

        userStakes[staker].push(Stake({
            staker:               staker,
            connectionId:         connectionId,
            amount:               amount,
            stakedAt:             block.timestamp,
            rewardsClaimed:       0,
            rewardsPerTokenPaid:  connections[connectionId].rewardsPerToken
        }));

        emit ConnectionStaked(staker, connectionId, amount);
    }

    /// @notice Admin: unstake on behalf of a user (kernel-managed)
    function unstake(address staker, uint256 stakeIndex) external onlyKernel {
        require(stakeIndex < userStakes[staker].length, "Synaptic: invalid index");
        Stake storage s = userStakes[staker][stakeIndex];
        uint256 amount = s.amount;
        uint256 connId = s.connectionId;

        connections[connId].totalStaked -= amount;
        totalStaked -= amount;

        // Remove stake by swapping with last
        userStakes[staker][stakeIndex] = userStakes[staker][userStakes[staker].length - 1];
        userStakes[staker].pop();

        emit ConnectionUnstaked(staker, connId, amount);
    }

    // ─── Utility & Rewards (admin only) ──────────────────────────────────
    function updateUtility(uint256 connectionId, uint256 newUtility) external onlyKernel {
        require(connections[connectionId].active, "Synaptic: not active");
        uint256 old = connections[connectionId].utilityScore;
        connections[connectionId].utilityScore = newUtility;
        emit UtilityUpdated(connectionId, old, newUtility);
    }

    /// @notice Distribute rewards to a connection — updates rewardsPerToken for proportional distribution.
    function distributeConnectionReward(uint256 connectionId, uint256 rewardAmount) external onlyKernel {
        Connection storage conn = connections[connectionId];
        conn.totalRewards += rewardAmount;
        totalRewardsDistributed += rewardAmount;

        // Update rewards per token for proportional distribution
        if (conn.totalStaked > 0) {
            conn.rewardsPerToken += (rewardAmount * 1e18) / conn.totalStaked;
        }
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getConnection(uint256 connectionId) external view returns (
        uint8 from_, uint8 to_, uint256 staked, uint256 utility, uint256 rewards, bool active
    ) {
        Connection storage c = connections[connectionId];
        return (c.fromNodeId, c.toNodeId, c.totalStaked, c.utilityScore, c.totalRewards, c.active);
    }

    function getUserStakeCount(address staker) external view returns (uint256) {
        return userStakes[staker].length;
    }

    function getConnectionCount() external view returns (uint256) {
        return connectionIds.length;
    }

    function getUnstakeRequestCount(address staker) external view returns (uint256) {
        return unstakeRequests[staker].length;
    }

    /// @notice Allow contract to receive QBC for reward distribution.
    receive() external payable {}
}
