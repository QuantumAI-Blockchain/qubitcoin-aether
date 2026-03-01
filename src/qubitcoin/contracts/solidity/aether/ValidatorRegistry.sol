// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title ValidatorRegistry — Validator Staking for Proof-of-Thought
/// @notice Stake QBC to become a PoT validator. Minimum 100 QBC. 7-day unstaking delay.
///         Tracks validator performance (correct/incorrect votes).
contract ValidatorRegistry is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant MIN_STAKE        = 100 * 10**8;  // 100 QBC (8 decimals)
    uint256 public constant MAX_STAKE        = 1000000 * 10**8; // 1M QBC (8 decimals)
    uint256 public constant UNSTAKING_DELAY  = 7 days;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;

    struct Validator {
        address addr;
        uint256 stakeAmount;
        uint256 stakedAt;
        uint256 unstakeRequestedAt; // 0 = not unstaking
        uint256 correctVotes;
        uint256 incorrectVotes;
        bool    active;
    }

    mapping(address => Validator) public validators;
    address[] public validatorList;
    /// @notice Index of each validator in validatorList for O(1) removal (swap-and-pop)
    mapping(address => uint256) public validatorListIndex;
    uint256 public activeValidatorCount;
    uint256 public totalStaked;

    // ─── Events ──────────────────────────────────────────────────────────
    event ValidatorStaked(address indexed validator, uint256 amount, uint256 timestamp);
    event ValidatorUnstakeRequested(address indexed validator, uint256 unlockTime);
    event ValidatorUnstaked(address indexed validator, uint256 amount);
    event ValidatorSlashed(address indexed validator, uint256 slashAmount, uint256 remaining);
    event ValidatorPerformanceUpdated(address indexed validator, uint256 correct, uint256 incorrect);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "VReg: not authorized");
        _;
    }

    // ─── Initialization ─────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Staking ─────────────────────────────────────────────────────────
    /// @notice Stake QBC to become a validator
    function stake(address validator, uint256 amount) external onlyKernel {
        require(amount >= MIN_STAKE, "VReg: below minimum (100 QBC)");
        require(
            validators[validator].stakeAmount + amount <= MAX_STAKE,
            "VReg: exceeds max stake (1M QBC)"
        );

        if (!validators[validator].active) {
            validators[validator] = Validator({
                addr:               validator,
                stakeAmount:        amount,
                stakedAt:           block.timestamp,
                unstakeRequestedAt: 0,
                correctVotes:       0,
                incorrectVotes:     0,
                active:             true
            });
            validatorListIndex[validator] = validatorList.length;
            validatorList.push(validator);
            activeValidatorCount++;
        } else {
            validators[validator].stakeAmount += amount;
        }

        totalStaked += amount;
        emit ValidatorStaked(validator, amount, block.timestamp);
    }

    /// @notice Request unstaking (7-day delay)
    function requestUnstake(address validator) external onlyKernel {
        Validator storage v = validators[validator];
        require(v.active, "VReg: not active");
        require(v.unstakeRequestedAt == 0, "VReg: already unstaking");

        v.unstakeRequestedAt = block.timestamp;
        emit ValidatorUnstakeRequested(validator, block.timestamp + UNSTAKING_DELAY);
    }

    /// @notice Complete unstaking after delay. Removes validator from the list via swap-and-pop.
    function completeUnstake(address validator) external onlyKernel {
        Validator storage v = validators[validator];
        require(v.unstakeRequestedAt > 0, "VReg: not unstaking");
        require(block.timestamp >= v.unstakeRequestedAt + UNSTAKING_DELAY, "VReg: delay not met");

        uint256 amount = v.stakeAmount;
        totalStaked -= amount;
        activeValidatorCount--;
        v.active      = false;
        v.stakeAmount = 0;
        v.unstakeRequestedAt = 0;

        // Remove from validatorList using swap-and-pop for O(1) cleanup
        _removeFromList(validator);

        emit ValidatorUnstaked(validator, amount);
    }

    /// @notice Slash validator stake (called by RewardDistributor)
    function slash(address validator, uint256 amount) external onlyKernel {
        Validator storage v = validators[validator];
        require(v.active, "VReg: not active");

        uint256 actualSlash = amount > v.stakeAmount ? v.stakeAmount : amount;
        v.stakeAmount -= actualSlash;
        totalStaked   -= actualSlash;

        if (v.stakeAmount < MIN_STAKE) {
            v.active = false;
            activeValidatorCount--;
            _removeFromList(validator);
        }

        emit ValidatorSlashed(validator, actualSlash, v.stakeAmount);
    }

    /// @notice Record validator vote performance
    function recordVote(address validator, bool correct) external onlyKernel {
        Validator storage v = validators[validator];
        if (correct) {
            v.correctVotes++;
        } else {
            v.incorrectVotes++;
        }
        emit ValidatorPerformanceUpdated(validator, v.correctVotes, v.incorrectVotes);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function isValidator(address addr) external view returns (bool) {
        return validators[addr].active;
    }

    function getValidator(address addr) external view returns (
        uint256 stakeAmount,
        uint256 stakedAt,
        uint256 correctVotes,
        uint256 incorrectVotes,
        bool    active
    ) {
        Validator storage v = validators[addr];
        return (v.stakeAmount, v.stakedAt, v.correctVotes, v.incorrectVotes, v.active);
    }

    function getValidatorCount() external view returns (uint256 active, uint256 total) {
        return (activeValidatorCount, validatorList.length);
    }

    // ─── Internal ──────────────────────────────────────────────────────
    /// @dev Remove a validator from validatorList using swap-and-pop for O(1) removal.
    ///      Moves the last element into the removed slot to avoid shifting.
    function _removeFromList(address validator) internal {
        uint256 index = validatorListIndex[validator];
        uint256 lastIndex = validatorList.length - 1;

        if (index != lastIndex) {
            address lastValidator = validatorList[lastIndex];
            validatorList[index] = lastValidator;
            validatorListIndex[lastValidator] = index;
        }

        validatorList.pop();
        delete validatorListIndex[validator];
    }
}
