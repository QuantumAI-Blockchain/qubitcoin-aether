// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SynapticStaking — Stake QBC on Neural Connections
/// @notice Stake QBC on specific Sephirot connections (edges) to strengthen or weaken them.
///         High-utility connections earn rewards. Inspired by synaptic plasticity.
contract SynapticStaking {
    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;

    struct Connection {
        uint8   fromNodeId;
        uint8   toNodeId;
        uint256 totalStaked;
        uint256 utilityScore;    // × 1000 (how useful this connection is)
        uint256 totalRewards;
        bool    active;
    }

    struct Stake {
        address staker;
        uint256 connectionId;
        uint256 amount;
        uint256 stakedAt;
        uint256 rewardsClaimed;
    }

    /// @notice Connection id = fromNodeId * 10 + toNodeId
    mapping(uint256 => Connection) public connections;
    uint256[] public connectionIds;

    mapping(address => Stake[]) public userStakes;
    uint256 public totalStaked;
    uint256 public totalRewardsDistributed;

    // ─── Events ──────────────────────────────────────────────────────────
    event ConnectionStaked(address indexed staker, uint256 indexed connectionId, uint256 amount);
    event ConnectionUnstaked(address indexed staker, uint256 indexed connectionId, uint256 amount);
    event RewardClaimed(address indexed staker, uint256 amount);
    event UtilityUpdated(uint256 indexed connectionId, uint256 oldUtility, uint256 newUtility);
    event ConnectionActivated(uint256 indexed connectionId, uint8 from, uint8 to);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Synaptic: not authorized");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _kernel) {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Connection Setup ────────────────────────────────────────────────
    function activateConnection(uint8 fromNodeId, uint8 toNodeId) external onlyKernel {
        uint256 connId = uint256(fromNodeId) * 10 + uint256(toNodeId);
        require(!connections[connId].active, "Synaptic: already active");

        connections[connId] = Connection({
            fromNodeId:    fromNodeId,
            toNodeId:      toNodeId,
            totalStaked:   0,
            utilityScore:  500, // baseline 0.5
            totalRewards:  0,
            active:        true
        });
        connectionIds.push(connId);
        emit ConnectionActivated(connId, fromNodeId, toNodeId);
    }

    // ─── Staking ─────────────────────────────────────────────────────────
    function stake(address staker, uint256 connectionId, uint256 amount) external onlyKernel {
        require(connections[connectionId].active, "Synaptic: not active");
        require(amount > 0, "Synaptic: zero amount");

        connections[connectionId].totalStaked += amount;
        totalStaked += amount;

        userStakes[staker].push(Stake({
            staker:         staker,
            connectionId:   connectionId,
            amount:         amount,
            stakedAt:       block.timestamp,
            rewardsClaimed: 0
        }));

        emit ConnectionStaked(staker, connectionId, amount);
    }

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

    // ─── Utility & Rewards ───────────────────────────────────────────────
    function updateUtility(uint256 connectionId, uint256 newUtility) external onlyKernel {
        require(connections[connectionId].active, "Synaptic: not active");
        uint256 old = connections[connectionId].utilityScore;
        connections[connectionId].utilityScore = newUtility;
        emit UtilityUpdated(connectionId, old, newUtility);
    }

    function distributeConnectionReward(uint256 connectionId, uint256 rewardAmount) external onlyKernel {
        connections[connectionId].totalRewards += rewardAmount;
        totalRewardsDistributed += rewardAmount;
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getConnection(uint256 connectionId) external view returns (
        uint8 from, uint8 to, uint256 staked, uint256 utility, uint256 rewards, bool active
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
}
