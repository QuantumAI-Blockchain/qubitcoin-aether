// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title QUSDDebtLedger — On-Chain Fractional Payback Tracking
/// @notice Immutably tracks every QUSD mint as debt and every reserve deposit as payback.
///         Emits milestone events at 5%, 15%, 30%, 50%, and 100% backing.
///         The entire debt lifecycle is transparent and auditable on-chain.
contract QUSDDebtLedger {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant BPS_DENOM = 10000; // basis points denominator

    /// @notice Milestones in basis points (5%, 15%, 30%, 50%, 100%)
    uint16[5] public MILESTONES = [500, 1500, 3000, 5000, 10000];

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public qusdToken;     // authorized to record mints
    address public reservePool;   // authorized to record paybacks

    uint256 public totalMinted;         // total QUSD ever minted (8 decimals)
    uint256 public totalReserveValue;   // total USD value of reserves (8 decimals)
    uint256 public totalPaybackEvents;  // number of payback transactions

    /// @notice Tracks which milestones have been reached
    mapping(uint16 => bool) public milestoneReached;

    /// @notice Historical snapshots (block number → backing bps)
    struct Snapshot {
        uint256 blockNumber;
        uint256 totalMinted;
        uint256 totalReserveValue;
        uint16  backingBps;
    }
    Snapshot[] public snapshots;

    // ─── Events ──────────────────────────────────────────────────────────
    event DebtRecorded(uint256 amount, uint256 newTotalMinted, uint256 timestamp);
    event PaybackRecorded(uint256 usdValue, uint256 newReserveValue, uint16 backingBps, uint256 timestamp);
    event MilestoneReached(uint16 milestoneBps, uint256 totalMinted, uint256 totalReserveValue, uint256 blockNumber);
    event SnapshotTaken(uint256 indexed snapshotId, uint256 blockNumber, uint16 backingBps);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "DebtLedger: not owner");
        _;
    }

    modifier onlyQUSD() {
        require(msg.sender == qusdToken, "DebtLedger: not QUSD token");
        _;
    }

    modifier onlyReserve() {
        require(msg.sender == reservePool, "DebtLedger: not reserve");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _qusdToken, address _reservePool) {
        owner       = msg.sender;
        qusdToken   = _qusdToken;
        reservePool = _reservePool;
    }

    // ─── Debt Recording ──────────────────────────────────────────────────
    /// @notice Called when QUSD is minted. Every mint increases outstanding debt.
    function recordDebt(uint256 amount) external onlyQUSD {
        require(amount > 0, "DebtLedger: zero amount");
        totalMinted += amount;
        emit DebtRecorded(amount, totalMinted, block.timestamp);
    }

    /// @notice Called when reserves increase. Every deposit is a payback event.
    function recordPayback(uint256 usdValue) external onlyReserve {
        require(usdValue > 0, "DebtLedger: zero value");
        totalReserveValue += usdValue;
        totalPaybackEvents++;

        uint16 bps = _backingBps();
        emit PaybackRecorded(usdValue, totalReserveValue, bps, block.timestamp);

        // Check milestones
        for (uint256 i = 0; i < MILESTONES.length; i++) {
            if (!milestoneReached[MILESTONES[i]] && bps >= MILESTONES[i]) {
                milestoneReached[MILESTONES[i]] = true;
                emit MilestoneReached(MILESTONES[i], totalMinted, totalReserveValue, block.number);
            }
        }
    }

    // ─── Snapshots ───────────────────────────────────────────────────────
    /// @notice Take a point-in-time snapshot of the debt state
    function takeSnapshot() external returns (uint256 snapshotId) {
        uint16 bps = _backingBps();
        snapshotId = snapshots.length;
        snapshots.push(Snapshot({
            blockNumber:      block.number,
            totalMinted:      totalMinted,
            totalReserveValue: totalReserveValue,
            backingBps:       bps
        }));
        emit SnapshotTaken(snapshotId, block.number, bps);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    /// @notice Returns the full debt status
    function getDebtStatus() external view returns (
        uint256 minted,
        uint256 reserves,
        uint16  backingBps,
        uint256 outstandingDebt
    ) {
        minted          = totalMinted;
        reserves        = totalReserveValue;
        backingBps      = _backingBps();
        outstandingDebt = totalMinted > totalReserveValue
            ? totalMinted - totalReserveValue
            : 0;
    }

    /// @notice Returns the number of historical snapshots
    function snapshotCount() external view returns (uint256) {
        return snapshots.length;
    }

    /// @notice Check if a specific backing milestone has been reached
    function isMilestoneReached(uint16 bps) external view returns (bool) {
        return milestoneReached[bps];
    }

    // ─── Internal ────────────────────────────────────────────────────────
    function _backingBps() internal view returns (uint16) {
        if (totalMinted == 0) return 0;
        uint256 bps = (totalReserveValue * BPS_DENOM) / totalMinted;
        return bps > type(uint16).max ? type(uint16).max : uint16(bps);
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setQUSDToken(address _qusd) external onlyOwner {
        qusdToken = _qusd;
    }

    function setReservePool(address _reserve) external onlyOwner {
        reservePool = _reserve;
    }
}
