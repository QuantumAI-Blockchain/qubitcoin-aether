// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title QUSDAllocation — Vesting & Distribution for 3.3B QUSD
/// @notice Manages the initial QUSD allocation across 4 tiers:
///         50% Liquidity Providers (immediate), 30% Treasury (DAO),
///         15% Dev Fund (4yr vesting, 6mo cliff), 5% Team (4yr vesting, 1yr cliff).
///         All vesting is enforced on-chain and immutable once set.
contract QUSDAllocation {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant TOTAL_ALLOCATION = 3_300_000_000 * 10**8; // 3.3B (8 decimals)

    uint256 public constant LP_SHARE       = 1_650_000_000 * 10**8;  // 50% = 1.65B
    uint256 public constant TREASURY_SHARE = 990_000_000 * 10**8;    // 30% = 990M
    uint256 public constant DEV_SHARE      = 495_000_000 * 10**8;    // 15% = 495M
    uint256 public constant TEAM_SHARE     = 165_000_000 * 10**8;    // 5%  = 165M

    uint256 public constant DEV_CLIFF   = 180 days;  // 6-month cliff
    uint256 public constant TEAM_CLIFF  = 365 days;  // 1-year cliff
    uint256 public constant VESTING_DURATION = 1460 days; // 4 years

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public qusdToken;
    uint256 public vestingStart;
    bool    public initialized;

    /// @notice Per-beneficiary vesting info
    struct VestingSchedule {
        uint256 totalAmount;
        uint256 claimed;
        uint256 cliffDuration;
        uint256 vestingDuration;
        bool    immediate; // true = no vesting, fully available
    }

    mapping(address => VestingSchedule) public schedules;

    /// @notice Tier allocation tracking
    address public lpAddress;
    address public treasuryAddress;
    address[] public devBeneficiaries;
    address[] public teamBeneficiaries;

    uint256 public devAllocated;
    uint256 public teamAllocated;

    // ─── Events ──────────────────────────────────────────────────────────
    event AllocationInitialized(uint256 vestingStart);
    event BeneficiaryAdded(address indexed beneficiary, uint256 amount, string tier);
    event TokensClaimed(address indexed beneficiary, uint256 amount, uint256 totalClaimed);
    event VestingStarted(address indexed beneficiary, uint256 totalAmount, uint256 cliffEnd);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Allocation: not owner");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _qusdToken) {
        owner     = msg.sender;
        qusdToken = _qusdToken;
    }

    // ─── Initialization ──────────────────────────────────────────────────
    /// @notice Initialize the allocation. Sets vesting start and LP/Treasury recipients.
    function initialize(
        address _lpAddress,
        address _treasuryAddress
    ) external onlyOwner {
        require(!initialized, "Allocation: already initialized");
        require(_lpAddress != address(0) && _treasuryAddress != address(0), "Allocation: zero addr");

        initialized     = true;
        vestingStart    = block.timestamp;
        lpAddress       = _lpAddress;
        treasuryAddress = _treasuryAddress;

        // LP — immediate release (no vesting)
        schedules[_lpAddress] = VestingSchedule({
            totalAmount:     LP_SHARE,
            claimed:         0,
            cliffDuration:   0,
            vestingDuration: 0,
            immediate:       true
        });
        emit BeneficiaryAdded(_lpAddress, LP_SHARE, "liquidity");

        // Treasury — DAO-governed, immediate access
        schedules[_treasuryAddress] = VestingSchedule({
            totalAmount:     TREASURY_SHARE,
            claimed:         0,
            cliffDuration:   0,
            vestingDuration: 0,
            immediate:       true
        });
        emit BeneficiaryAdded(_treasuryAddress, TREASURY_SHARE, "treasury");

        emit AllocationInitialized(vestingStart);
    }

    /// @notice Add a dev fund beneficiary with 4yr vesting and 6mo cliff
    function addDevBeneficiary(address beneficiary, uint256 amount) external onlyOwner {
        require(initialized, "Allocation: not initialized");
        require(beneficiary != address(0), "Allocation: zero addr");
        require(devAllocated + amount <= DEV_SHARE, "Allocation: dev share exceeded");

        schedules[beneficiary] = VestingSchedule({
            totalAmount:     amount,
            claimed:         0,
            cliffDuration:   DEV_CLIFF,
            vestingDuration: VESTING_DURATION,
            immediate:       false
        });

        devBeneficiaries.push(beneficiary);
        devAllocated += amount;

        emit BeneficiaryAdded(beneficiary, amount, "dev");
        emit VestingStarted(beneficiary, amount, vestingStart + DEV_CLIFF);
    }

    /// @notice Add a team beneficiary with 4yr vesting and 1yr cliff
    function addTeamBeneficiary(address beneficiary, uint256 amount) external onlyOwner {
        require(initialized, "Allocation: not initialized");
        require(beneficiary != address(0), "Allocation: zero addr");
        require(teamAllocated + amount <= TEAM_SHARE, "Allocation: team share exceeded");

        schedules[beneficiary] = VestingSchedule({
            totalAmount:     amount,
            claimed:         0,
            cliffDuration:   TEAM_CLIFF,
            vestingDuration: VESTING_DURATION,
            immediate:       false
        });

        teamBeneficiaries.push(beneficiary);
        teamAllocated += amount;

        emit BeneficiaryAdded(beneficiary, amount, "team");
        emit VestingStarted(beneficiary, amount, vestingStart + TEAM_CLIFF);
    }

    // ─── Claiming ────────────────────────────────────────────────────────
    /// @notice Claim vested tokens
    function claim() external {
        VestingSchedule storage sched = schedules[msg.sender];
        require(sched.totalAmount > 0, "Allocation: no allocation");

        uint256 vested = _vestedAmount(msg.sender);
        uint256 claimable = vested - sched.claimed;
        require(claimable > 0, "Allocation: nothing to claim");

        sched.claimed += claimable;
        emit TokensClaimed(msg.sender, claimable, sched.claimed);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    /// @notice Returns vesting status for a beneficiary
    function getVestingStatus(address beneficiary) external view returns (
        uint256 total,
        uint256 vested,
        uint256 claimed,
        uint256 remaining
    ) {
        VestingSchedule storage sched = schedules[beneficiary];
        total     = sched.totalAmount;
        vested    = _vestedAmount(beneficiary);
        claimed   = sched.claimed;
        remaining = total - claimed;
    }

    /// @notice Amount currently claimable
    function claimable(address beneficiary) external view returns (uint256) {
        return _vestedAmount(beneficiary) - schedules[beneficiary].claimed;
    }

    // ─── Internal ────────────────────────────────────────────────────────
    function _vestedAmount(address beneficiary) internal view returns (uint256) {
        VestingSchedule storage sched = schedules[beneficiary];
        if (sched.totalAmount == 0) return 0;
        if (sched.immediate) return sched.totalAmount;

        uint256 elapsed = block.timestamp - vestingStart;
        if (elapsed < sched.cliffDuration) return 0;

        uint256 vestingElapsed = elapsed - sched.cliffDuration;
        if (vestingElapsed >= sched.vestingDuration) return sched.totalAmount;

        return (sched.totalAmount * vestingElapsed) / sched.vestingDuration;
    }
}
