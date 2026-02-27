// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../interfaces/IQBC20.sol";
import "../interfaces/IDebtLedger.sol";
import "../proxy/Initializable.sol";

/// @title QUSD — Qubitcoin USD Stablecoin
/// @notice QBC-20 token pegged to $1 USD. 3.3 Billion initial mint.
///         Fractional reserve model with 0.05% transfer fee and full on-chain tracking.
/// @dev    Deployed on QVM (EVM-compatible). Fees route to reserve for debt payback.
contract QUSD is IQBC20, Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    string  public constant name     = "Qubitcoin USD";
    string  public constant symbol   = "QUSD";
    uint8   public constant decimals = 8;

    uint256 public constant INITIAL_SUPPLY = 3_300_000_000 * 10**8; // 3.3B
    uint256 public constant BPS_DENOM      = 10000;

    // ─── Configurable Fee ─────────────────────────────────────────────
    uint256 public feeBps;  // transfer fee in basis points (initialized to 5 = 0.05%)

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public reserveAddress;
    address public debtLedger;
    address public stabilizer;
    bool    public paused;

    uint256 public totalSupply;
    uint256 public totalMinted;
    uint256 public totalBurned;
    uint256 public totalFeesCollected;

    mapping(address => uint256)                     private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    // ─── Events ──────────────────────────────────────────────────────────
    event Mint(address indexed to, uint256 amount);
    event Burn(address indexed from, uint256 amount);
    event FeeCollected(address indexed from, address indexed to, uint256 fee);
    event Paused(address indexed by);
    event Unpaused(address indexed by);
    event OwnershipTransferred(address indexed prev, address indexed next);
    event ReserveAddressUpdated(address indexed prev, address indexed next);
    event FeeBpsUpdated(uint256 prev, uint256 next);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "QUSD: caller is not owner");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "QUSD: paused");
        _;
    }

    modifier onlyMinter() {
        require(
            msg.sender == owner || msg.sender == stabilizer,
            "QUSD: caller is not authorized minter"
        );
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    /// @param _reserveAddress Address that receives transfer fees
    function initialize(address _reserveAddress) external initializer {
        require(_reserveAddress != address(0), "QUSD: zero reserve");
        owner          = msg.sender;
        reserveAddress = _reserveAddress;

        feeBps = 5; // 0.05% default

        // 3.3B initial mint to deployer
        _balances[msg.sender] = INITIAL_SUPPLY;
        totalSupply           = INITIAL_SUPPLY;
        totalMinted           = INITIAL_SUPPLY;

        emit Transfer(address(0), msg.sender, INITIAL_SUPPLY);
        emit Mint(msg.sender, INITIAL_SUPPLY);
    }

    // ─── QBC-20 Core ─────────────────────────────────────────────────────
    function balanceOf(address account) external view returns (uint256) {
        return _balances[account];
    }

    function allowance(address _owner, address spender) external view returns (uint256) {
        return _allowances[_owner][spender];
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        _allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    /// @notice Transfer with 0.05% fee routed to reserve
    function transfer(address to, uint256 amount) external whenNotPaused returns (bool) {
        return _transferWithFee(msg.sender, to, amount);
    }

    function transferFrom(address from, address to, uint256 amount) external whenNotPaused returns (bool) {
        uint256 allowed = _allowances[from][msg.sender];
        require(allowed >= amount, "QUSD: allowance exceeded");
        _allowances[from][msg.sender] = allowed - amount;
        return _transferWithFee(from, to, amount);
    }

    // ─── Mint / Burn ─────────────────────────────────────────────────────
    /// @notice Mint new QUSD. Every mint increases outstanding debt.
    ///         Callable by owner or stabilizer. Automatically records debt in DebtLedger.
    function mint(address to, uint256 amount) external onlyMinter whenNotPaused {
        require(to != address(0), "QUSD: mint to zero");
        totalSupply   += amount;
        totalMinted   += amount;
        _balances[to] += amount;
        emit Transfer(address(0), to, amount);
        emit Mint(to, amount);

        // Cross-call: record debt in DebtLedger
        if (debtLedger != address(0)) {
            IDebtLedger(debtLedger).recordDebt(amount);
            IDebtLedger(debtLedger).recordAccountDebt(to, amount);
        }
    }

    /// @notice Anyone can burn their own QUSD. Reduces supply and records burn.
    function burn(uint256 amount) external whenNotPaused {
        require(_balances[msg.sender] >= amount, "QUSD: burn exceeds balance");
        _balances[msg.sender] -= amount;
        totalSupply           -= amount;
        totalBurned           += amount;
        emit Transfer(msg.sender, address(0), amount);
        emit Burn(msg.sender, amount);
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function pause() external onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "QUSD: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function setReserveAddress(address newReserve) external onlyOwner {
        require(newReserve != address(0), "QUSD: zero reserve");
        emit ReserveAddressUpdated(reserveAddress, newReserve);
        reserveAddress = newReserve;
    }

    /// @notice Set the DebtLedger contract address for cross-contract debt tracking
    function setDebtLedger(address _debtLedger) external onlyOwner {
        require(_debtLedger != address(0), "QUSD: zero debt ledger");
        debtLedger = _debtLedger;
    }

    /// @notice Set the Stabilizer contract address (authorized to mint/burn for peg maintenance)
    function setStabilizer(address _stabilizer) external onlyOwner {
        require(_stabilizer != address(0), "QUSD: zero stabilizer");
        stabilizer = _stabilizer;
    }

    /// @notice Update transfer fee (governance). Max 10% (1000 bps) safety cap.
    function setFeeBps(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= 1000, "QUSD: fee too high");
        emit FeeBpsUpdated(feeBps, newFeeBps);
        feeBps = newFeeBps;
    }

    // ─── Internal ────────────────────────────────────────────────────────
    function _transferWithFee(address from, address to, uint256 amount) internal returns (bool) {
        require(from != address(0), "QUSD: from zero");
        require(to   != address(0), "QUSD: to zero");
        require(_balances[from] >= amount, "QUSD: insufficient balance");

        uint256 fee       = (amount * feeBps) / BPS_DENOM;
        uint256 netAmount = amount - fee;

        _balances[from]           -= amount;
        _balances[to]             += netAmount;
        _balances[reserveAddress] += fee;
        totalFeesCollected        += fee;

        emit Transfer(from, to, netAmount);
        if (fee > 0) {
            emit Transfer(from, reserveAddress, fee);
            emit FeeCollected(from, reserveAddress, fee);
        }
        return true;
    }
}
