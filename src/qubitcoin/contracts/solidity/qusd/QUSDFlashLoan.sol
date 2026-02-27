// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";
import "../interfaces/IFlashBorrower.sol";
import "../interfaces/IQUSD.sol";

/// @title QUSDFlashLoan — Flash Loan Provider for QUSD
/// @notice Enables uncollateralized flash loans of QUSD that must be repaid within
///         a single transaction. Fees are configurable (default: 9 bps = 0.09%) and
///         sent to a treasury address. Uses reentrancy protection.
/// @dev    Follows EIP-3156 flash loan pattern. The QUSD token contract must authorize
///         this contract as a minter (via setStabilizer) so it can mint-and-burn.
///         Alternatively, the contract can operate from a pre-funded QUSD pool.
contract QUSDFlashLoan is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant BPS_DENOM = 10000;

    /// @notice Expected return value from IFlashBorrower.onFlashLoan
    bytes32 public constant CALLBACK_SUCCESS = keccak256("IFlashBorrower.onFlashLoan");

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public qusdToken;
    address public treasury;

    /// @notice Flash loan fee in basis points (default 9 = 0.09%)
    uint256 public flashFeeBps;

    /// @notice Maximum flash loan amount (safety cap)
    uint256 public maxFlashLoan;

    /// @notice Total fees collected from flash loans
    uint256 public totalFeesCollected;

    /// @notice Total number of flash loans executed
    uint256 public totalFlashLoans;

    bool public paused;
    bool private _locked; // reentrancy guard

    // ─── Events ──────────────────────────────────────────────────────────
    event FlashLoan(
        address indexed receiver,
        address indexed initiator,
        uint256 amount,
        uint256 fee
    );
    event FlashFeeBpsUpdated(uint256 prev, uint256 next);
    event MaxFlashLoanUpdated(uint256 prev, uint256 next);
    event TreasuryUpdated(address indexed prev, address indexed next);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "QUSDFlashLoan: not owner");
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "QUSDFlashLoan: reentrant call");
        _locked = true;
        _;
        _locked = false;
    }

    modifier whenNotPaused() {
        require(!paused, "QUSDFlashLoan: paused");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    /// @param _qusdToken Address of the QUSD token contract
    /// @param _treasury Address to receive flash loan fees
    /// @param _flashFeeBps Flash loan fee in basis points (e.g., 9 = 0.09%)
    /// @param _maxFlashLoan Maximum flash loan amount (8 decimals)
    function initialize(
        address _qusdToken,
        address _treasury,
        uint256 _flashFeeBps,
        uint256 _maxFlashLoan
    ) external initializer {
        require(_qusdToken != address(0), "QUSDFlashLoan: zero qusd");
        require(_treasury != address(0), "QUSDFlashLoan: zero treasury");
        require(_flashFeeBps <= 1000, "QUSDFlashLoan: fee too high"); // max 10%

        owner = msg.sender;
        qusdToken = _qusdToken;
        treasury = _treasury;
        flashFeeBps = _flashFeeBps;
        maxFlashLoan = _maxFlashLoan;
    }

    // ─── Flash Loan ─────────────────────────────────────────────────────

    /// @notice Execute a flash loan of QUSD
    /// @dev The receiver must implement IFlashBorrower and return CALLBACK_SUCCESS.
    ///      The loan amount + fee must be returned to this contract by the end of
    ///      the callback. Fees are forwarded to the treasury.
    /// @param receiver The contract that will receive and repay the loan
    /// @param amount The amount of QUSD to borrow (8 decimals)
    /// @param data Arbitrary data passed to the receiver's onFlashLoan callback
    function flashLoan(
        address receiver,
        uint256 amount,
        bytes calldata data
    ) external nonReentrant whenNotPaused {
        require(amount > 0, "QUSDFlashLoan: zero amount");
        require(amount <= maxFlashLoan, "QUSDFlashLoan: exceeds max");
        require(receiver != address(0), "QUSDFlashLoan: zero receiver");

        uint256 fee = flashFee(amount);

        // Snapshot the contract's QUSD balance before the loan
        uint256 balBefore = IQUSD(qusdToken).balanceOf(address(this));
        require(balBefore >= amount, "QUSDFlashLoan: insufficient pool");

        // Transfer loan to receiver
        IQUSD(qusdToken).transfer(receiver, amount);

        // Call the borrower's callback
        bytes32 result = IFlashBorrower(receiver).onFlashLoan(
            msg.sender,
            amount,
            fee,
            data
        );
        require(result == CALLBACK_SUCCESS, "QUSDFlashLoan: callback failed");

        // Verify repayment: contract must have at least balBefore + fee
        uint256 balAfter = IQUSD(qusdToken).balanceOf(address(this));
        require(
            balAfter >= balBefore + fee,
            "QUSDFlashLoan: not repaid"
        );

        // Transfer fee to treasury
        if (fee > 0) {
            IQUSD(qusdToken).transfer(treasury, fee);
        }

        totalFeesCollected += fee;
        totalFlashLoans++;

        emit FlashLoan(receiver, msg.sender, amount, fee);
    }

    /// @notice Calculate the fee for a given flash loan amount
    /// @param amount The flash loan amount (8 decimals)
    /// @return The fee in QUSD (8 decimals)
    function flashFee(uint256 amount) public view returns (uint256) {
        return (amount * flashFeeBps) / BPS_DENOM;
    }

    /// @notice Returns the maximum amount available for a flash loan
    /// @return The maximum flash loan amount
    function maxFlashLoanAmount() external view returns (uint256) {
        uint256 poolBalance = IQUSD(qusdToken).balanceOf(address(this));
        return poolBalance < maxFlashLoan ? poolBalance : maxFlashLoan;
    }

    // ─── Pool Management ────────────────────────────────────────────────

    /// @notice Deposit QUSD into the flash loan pool (anyone can fund it)
    /// @dev The caller must have already approved this contract to spend their QUSD.
    ///      In practice, the treasury or governance funds the pool.
    /// @param amount Amount of QUSD to deposit
    function deposit(uint256 amount) external whenNotPaused {
        require(amount > 0, "QUSDFlashLoan: zero deposit");
        // Caller must have approved this contract; transfer pulls from caller
        IQUSD(qusdToken).transferFrom(msg.sender, address(this), amount);
    }

    /// @notice Withdraw QUSD from the flash loan pool (owner only)
    /// @param recipient Address to receive the withdrawn QUSD
    /// @param amount Amount to withdraw
    function withdraw(address recipient, uint256 amount) external onlyOwner {
        require(recipient != address(0), "QUSDFlashLoan: zero recipient");
        require(amount > 0, "QUSDFlashLoan: zero amount");
        IQUSD(qusdToken).transfer(recipient, amount);
    }

    // ─── Queries ────────────────────────────────────────────────────────

    /// @notice Get flash loan pool status
    function getStatus() external view returns (
        uint256 poolBalance,
        uint256 feeBps,
        uint256 maxLoan,
        uint256 feesCollected,
        uint256 loanCount
    ) {
        return (
            IQUSD(qusdToken).balanceOf(address(this)),
            flashFeeBps,
            maxFlashLoan,
            totalFeesCollected,
            totalFlashLoans
        );
    }

    // ─── Admin ──────────────────────────────────────────────────────────

    /// @notice Update flash loan fee (max 10% = 1000 bps)
    function setFlashFeeBps(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= 1000, "QUSDFlashLoan: fee too high");
        emit FlashFeeBpsUpdated(flashFeeBps, newFeeBps);
        flashFeeBps = newFeeBps;
    }

    /// @notice Update maximum flash loan amount
    function setMaxFlashLoan(uint256 newMax) external onlyOwner {
        emit MaxFlashLoanUpdated(maxFlashLoan, newMax);
        maxFlashLoan = newMax;
    }

    /// @notice Update treasury address
    function setTreasury(address newTreasury) external onlyOwner {
        require(newTreasury != address(0), "QUSDFlashLoan: zero treasury");
        emit TreasuryUpdated(treasury, newTreasury);
        treasury = newTreasury;
    }

    function pause() external onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }
}
