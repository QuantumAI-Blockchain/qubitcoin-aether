// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../interfaces/IQBC20.sol";
import "../proxy/Initializable.sol";

/// @title VestingSchedule — Team/Investor Token Vesting with Cliff + Linear Unlock
/// @notice Manages token vesting plans for team members and investors.
///         Each plan has a cliff period (no tokens released) followed by a
///         linear unlock period.  Plans may be revocable by the owner, in
///         which case unvested tokens are returned to the owner on revocation.
///
/// @dev Vesting formula:
///   - Before cliff:  vested = 0
///   - After cliff:   vested = totalAmount * (elapsed - cliff) / duration
///   - Capped at totalAmount once cliff + duration has passed.
contract VestingSchedule is Initializable {
    // ─── Types ─────────────────────────────────────────────────────────
    struct VestingPlan {
        address beneficiary;
        uint256 totalAmount;
        uint256 cliffDuration;   // seconds after startTime before any vesting
        uint256 vestingDuration; // seconds of linear unlock after cliff
        uint256 startTime;
        uint256 claimed;
        bool    revocable;
        bool    revoked;
    }

    // ─── State ─────────────────────────────────────────────────────────
    address public owner;
    IQBC20  public token;

    /// @notice All vesting plans keyed by beneficiary address.
    ///         One plan per beneficiary (simplifies lookups).
    mapping(address => VestingPlan) private _plans;

    /// @notice Track all beneficiaries for enumeration.
    address[] private _beneficiaries;

    /// @notice Total tokens reserved across all active (non-revoked) plans.
    uint256 public totalReserved;

    // ─── Events ────────────────────────────────────────────────────────
    event VestingCreated(
        address indexed beneficiary,
        uint256 amount,
        uint256 cliff,
        uint256 duration
    );

    event TokensClaimed(
        address indexed beneficiary,
        uint256 amount
    );

    event VestingRevoked(
        address indexed beneficiary,
        uint256 unvestedAmount
    );

    // ─── Modifiers ─────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "VestingSchedule: not owner");
        _;
    }

    // ─── Initializer ───────────────────────────────────────────────────

    /// @notice Initialize the vesting contract.
    /// @param _token Address of the QBC-20 token to vest.
    function initialize(address _token) external initializer {
        require(_token != address(0), "VestingSchedule: zero token");
        owner = msg.sender;
        token = IQBC20(_token);
    }

    // ─── Core Functions ────────────────────────────────────────────────

    /// @notice Create a new vesting plan for a beneficiary.
    ///         The caller (owner) must have already approved this contract
    ///         to transfer `amount` tokens via the token's `approve()`.
    /// @param beneficiary Address that will receive vested tokens.
    /// @param amount      Total number of tokens to vest.
    /// @param cliff       Cliff duration in seconds (no tokens vest before this).
    /// @param duration    Linear vesting duration in seconds (after cliff).
    /// @param revocable   Whether the owner can revoke unvested tokens.
    function createVesting(
        address beneficiary,
        uint256 amount,
        uint256 cliff,
        uint256 duration,
        bool    revocable
    ) external onlyOwner {
        require(beneficiary != address(0), "VestingSchedule: zero beneficiary");
        require(amount > 0, "VestingSchedule: zero amount");
        require(duration > 0, "VestingSchedule: zero duration");
        require(
            _plans[beneficiary].totalAmount == 0,
            "VestingSchedule: plan exists"
        );

        // Transfer tokens into this contract to escrow them
        bool ok = token.transferFrom(msg.sender, address(this), amount);
        require(ok, "VestingSchedule: transfer failed");

        _plans[beneficiary] = VestingPlan({
            beneficiary:     beneficiary,
            totalAmount:     amount,
            cliffDuration:   cliff,
            vestingDuration: duration,
            startTime:       block.timestamp,
            claimed:         0,
            revocable:       revocable,
            revoked:         false
        });

        _beneficiaries.push(beneficiary);
        totalReserved += amount;

        emit VestingCreated(beneficiary, amount, cliff, duration);
    }

    /// @notice Claim all currently claimable (vested but unclaimed) tokens.
    function claim() external {
        VestingPlan storage plan = _plans[msg.sender];
        require(plan.totalAmount > 0, "VestingSchedule: no plan");
        require(!plan.revoked, "VestingSchedule: revoked");

        uint256 vested = _vestedAmount(plan);
        uint256 amount = vested - plan.claimed;
        require(amount > 0, "VestingSchedule: nothing to claim");

        plan.claimed += amount;
        totalReserved -= amount;

        bool ok = token.transfer(msg.sender, amount);
        require(ok, "VestingSchedule: transfer failed");

        emit TokensClaimed(msg.sender, amount);
    }

    /// @notice Query how many tokens have vested in total for a beneficiary.
    /// @param beneficiary Address to query.
    /// @return Total vested amount (includes already claimed).
    function vestedAmount(address beneficiary) public view returns (uint256) {
        VestingPlan storage plan = _plans[beneficiary];
        if (plan.totalAmount == 0) return 0;
        return _vestedAmount(plan);
    }

    /// @notice Query how many tokens are currently claimable by a beneficiary.
    /// @param beneficiary Address to query.
    /// @return Claimable amount (vested minus already claimed).
    function claimable(address beneficiary) public view returns (uint256) {
        VestingPlan storage plan = _plans[beneficiary];
        if (plan.totalAmount == 0 || plan.revoked) return 0;
        uint256 vested = _vestedAmount(plan);
        if (vested <= plan.claimed) return 0;
        return vested - plan.claimed;
    }

    /// @notice Revoke a beneficiary's unvested tokens (owner only).
    ///         Already-vested tokens remain claimable by the beneficiary.
    ///         Unvested tokens are returned to the owner.
    /// @param beneficiary Address whose plan to revoke.
    function revoke(address beneficiary) external onlyOwner {
        VestingPlan storage plan = _plans[beneficiary];
        require(plan.totalAmount > 0, "VestingSchedule: no plan");
        require(plan.revocable, "VestingSchedule: not revocable");
        require(!plan.revoked, "VestingSchedule: already revoked");

        uint256 vested = _vestedAmount(plan);
        uint256 unvested = plan.totalAmount - vested;

        plan.revoked = true;

        // Allow beneficiary to still claim what has vested
        // Return unvested portion to owner
        if (unvested > 0) {
            totalReserved -= unvested;
            bool ok = token.transfer(owner, unvested);
            require(ok, "VestingSchedule: transfer failed");
        }

        emit VestingRevoked(beneficiary, unvested);
    }

    // ─── View Helpers ──────────────────────────────────────────────────

    /// @notice Get the full vesting plan details for a beneficiary.
    function getPlan(address beneficiary) external view returns (
        uint256 totalAmount_,
        uint256 cliffDuration_,
        uint256 vestingDuration_,
        uint256 startTime_,
        uint256 claimed_,
        bool    revocable_,
        bool    revoked_
    ) {
        VestingPlan storage plan = _plans[beneficiary];
        return (
            plan.totalAmount,
            plan.cliffDuration,
            plan.vestingDuration,
            plan.startTime,
            plan.claimed,
            plan.revocable,
            plan.revoked
        );
    }

    /// @notice Return the number of vesting plans created.
    function planCount() external view returns (uint256) {
        return _beneficiaries.length;
    }

    /// @notice Return beneficiary address by index (for enumeration).
    function beneficiaryAt(uint256 index) external view returns (address) {
        require(index < _beneficiaries.length, "VestingSchedule: out of bounds");
        return _beneficiaries[index];
    }

    // ─── Admin ─────────────────────────────────────────────────────────

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "VestingSchedule: zero owner");
        owner = newOwner;
    }

    // ─── Internal ──────────────────────────────────────────────────────

    /// @dev Calculate vested amount for a plan based on current timestamp.
    ///      Nothing before cliff, then linear from cliff to cliff+duration.
    function _vestedAmount(VestingPlan storage plan) internal view returns (uint256) {
        if (block.timestamp < plan.startTime + plan.cliffDuration) {
            // Still within cliff — nothing vested
            return 0;
        }

        uint256 elapsed = block.timestamp - plan.startTime - plan.cliffDuration;

        if (elapsed >= plan.vestingDuration) {
            // Fully vested
            return plan.totalAmount;
        }

        // Linear: totalAmount * elapsed / vestingDuration
        return (plan.totalAmount * elapsed) / plan.vestingDuration;
    }
}
