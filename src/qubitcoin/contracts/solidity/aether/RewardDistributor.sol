// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title RewardDistributor — QBC Reward Distribution for Proof-of-Thought
/// @notice Distributes QBC rewards for correct reasoning solutions.
///         Slashes 50% of stake for incorrect proposals.
contract RewardDistributor is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant SLASH_BPS = 5000; // 50% slash
    uint256 public constant BPS_DENOM = 10000;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;

    /// @notice Maximum reward amount per single distribution (configurable by owner)
    uint256 public maxRewardPerDistribution;

    uint256 public totalDistributed;
    uint256 public totalSlashed;
    uint256 public distributionCount;

    struct RewardRecord {
        address recipient;
        uint256 amount;
        uint256 taskId;
        uint256 blockNumber;
        uint256 timestamp;
        bool    isSlash;
    }

    RewardRecord[] public rewards;
    mapping(address => uint256) public totalEarnedBy;
    mapping(address => uint256) public totalSlashedFrom;

    // ─── Events ──────────────────────────────────────────────────────────
    event RewardDistributed(address indexed recipient, uint256 amount, uint256 indexed taskId, uint256 blockNumber);
    event StakeSlashed(address indexed validator, uint256 slashAmount, uint256 indexed taskId, uint256 blockNumber);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Rewards: not owner");
        _;
    }

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Rewards: not authorized");
        _;
    }

    // ─── Initialization ─────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner  = msg.sender;
        kernel = _kernel;
        maxRewardPerDistribution = 10000 ether; // Default: 10,000 QBC max per distribution
    }

    /// @notice Update the maximum reward per distribution
    function setMaxRewardPerDistribution(uint256 _max) external onlyOwner {
        require(_max > 0, "Rewards: max must be > 0");
        maxRewardPerDistribution = _max;
    }

    // ─── Distribution ────────────────────────────────────────────────────
    /// @notice Distribute reward for a correct Proof-of-Thought solution
    function distributeReward(address recipient, uint256 amount, uint256 taskId) external onlyKernel {
        require(recipient != address(0), "Rewards: zero address");
        require(amount > 0, "Rewards: zero amount");
        require(amount <= maxRewardPerDistribution, "Rewards: exceeds max per distribution");

        totalDistributed += amount;
        totalEarnedBy[recipient] += amount;
        distributionCount++;

        rewards.push(RewardRecord({
            recipient:   recipient,
            amount:      amount,
            taskId:      taskId,
            blockNumber: block.number,
            timestamp:   block.timestamp,
            isSlash:     false
        }));

        emit RewardDistributed(recipient, amount, taskId, block.number);
    }

    /// @notice Slash validator stake for incorrect proposal (50%)
    function slashStake(address validator, uint256 stakeAmount, uint256 taskId) external onlyKernel {
        require(validator != address(0), "Rewards: zero address");
        uint256 slashAmount = (stakeAmount * SLASH_BPS) / BPS_DENOM;

        totalSlashed += slashAmount;
        totalSlashedFrom[validator] += slashAmount;

        rewards.push(RewardRecord({
            recipient:   validator,
            amount:      slashAmount,
            taskId:      taskId,
            blockNumber: block.number,
            timestamp:   block.timestamp,
            isSlash:     true
        }));

        emit StakeSlashed(validator, slashAmount, taskId, block.number);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getRewardHistory(uint256 fromIndex, uint256 count) external view returns (RewardRecord[] memory) {
        uint256 end = fromIndex + count;
        if (end > rewards.length) end = rewards.length;
        uint256 len = end - fromIndex;
        RewardRecord[] memory result = new RewardRecord[](len);
        for (uint256 i = 0; i < len; i++) {
            result[i] = rewards[fromIndex + i];
        }
        return result;
    }

    function getStats() external view returns (uint256 distributed, uint256 slashed, uint256 count) {
        return (totalDistributed, totalSlashed, distributionCount);
    }
}
