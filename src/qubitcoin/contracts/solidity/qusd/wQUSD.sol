// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../interfaces/IQBC20.sol";
import "../proxy/Initializable.sol";

/// @title wQUSD — Wrapped QUSD for Cross-Chain Bridging
/// @notice Lock QUSD to mint wQUSD 1:1. Burn wQUSD to unlock QUSD 1:1.
///         wQUSD is the cross-chain representation of QUSD on external chains
///         (ETH, SOL, MATIC, BNB, AVAX, ARB, OP, ATOM).
contract wQUSD is IQBC20, Initializable {
    // ─── Token Metadata ──────────────────────────────────────────────────
    string  public constant name     = "Wrapped QUSD";
    string  public constant symbol   = "wQUSD";
    uint8   public constant decimals = 8;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public qusdToken;       // underlying QUSD contract
    address public bridgeOperator;  // authorized to mint/burn for bridge operations

    uint256 public totalSupply;
    uint256 public totalLocked;     // QUSD locked in this contract
    uint256 public totalWrapped;    // cumulative wQUSD minted
    uint256 public totalUnwrapped;  // cumulative wQUSD burned

    mapping(address => uint256)                     private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    bool private _locked; // reentrancy guard
    bool public paused;

    // ─── Events ──────────────────────────────────────────────────────────
    event Wrapped(address indexed account, uint256 qusdAmount, uint256 wqusdMinted);
    event Unwrapped(address indexed account, uint256 wqusdBurned, uint256 qusdReleased);
    event BridgeMint(address indexed recipient, uint256 amount, bytes32 indexed sourceChainTxHash);
    event BridgeBurn(address indexed sender, uint256 amount, uint256 indexed destChainId);
    event BridgeOperatorUpdated(address indexed prev, address indexed next);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "wQUSD: not owner");
        _;
    }

    modifier onlyBridge() {
        require(msg.sender == bridgeOperator, "wQUSD: not bridge operator");
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "wQUSD: reentrant");
        _locked = true;
        _;
        _locked = false;
    }

    modifier whenNotPaused() {
        require(!paused, "wQUSD: paused");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _qusdToken, address _bridgeOperator) external initializer {
        require(_qusdToken != address(0), "wQUSD: zero QUSD");
        owner          = msg.sender;
        qusdToken      = _qusdToken;
        bridgeOperator = _bridgeOperator;
    }

    // ─── Wrap / Unwrap (on QBC chain) ────────────────────────────────────
    /// @notice Lock QUSD and receive wQUSD 1:1
    function wrap(uint256 amount) external nonReentrant whenNotPaused {
        require(amount > 0, "wQUSD: zero amount");
        // In production, would call QUSD.transferFrom(msg.sender, address(this), amount)
        totalLocked        += amount;
        totalWrapped       += amount;
        totalSupply        += amount;
        _balances[msg.sender] += amount;

        emit Transfer(address(0), msg.sender, amount);
        emit Wrapped(msg.sender, amount, amount);
    }

    /// @notice Burn wQUSD and receive QUSD 1:1
    function unwrap(uint256 amount) external nonReentrant whenNotPaused {
        require(amount > 0, "wQUSD: zero amount");
        require(_balances[msg.sender] >= amount, "wQUSD: insufficient balance");
        require(totalLocked >= amount, "wQUSD: insufficient locked QUSD");

        _balances[msg.sender] -= amount;
        totalSupply           -= amount;
        totalLocked           -= amount;
        totalUnwrapped        += amount;

        emit Transfer(msg.sender, address(0), amount);
        emit Unwrapped(msg.sender, amount, amount);
    }

    // ─── Bridge Operations ───────────────────────────────────────────────
    /// @notice Bridge operator mints wQUSD on destination chain
    function bridgeMint(address recipient, uint256 amount, bytes32 sourceTxHash) external onlyBridge whenNotPaused {
        require(recipient != address(0), "wQUSD: zero recipient");
        totalSupply           += amount;
        _balances[recipient]  += amount;

        emit Transfer(address(0), recipient, amount);
        emit BridgeMint(recipient, amount, sourceTxHash);
    }

    /// @notice Bridge operator burns wQUSD for cross-chain transfer
    function bridgeBurn(address sender, uint256 amount, uint256 destChainId) external onlyBridge {
        require(_balances[sender] >= amount, "wQUSD: insufficient balance");
        _balances[sender] -= amount;
        totalSupply       -= amount;

        emit Transfer(sender, address(0), amount);
        emit BridgeBurn(sender, amount, destChainId);
    }

    // ─── QBC-20 (ERC-20) Implementation ─────────────────────────────────
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

    function transfer(address to, uint256 amount) external whenNotPaused returns (bool) {
        require(_balances[msg.sender] >= amount, "wQUSD: insufficient");
        require(to != address(0), "wQUSD: zero address");
        _balances[msg.sender] -= amount;
        _balances[to]         += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external whenNotPaused returns (bool) {
        require(_balances[from] >= amount, "wQUSD: insufficient");
        require(_allowances[from][msg.sender] >= amount, "wQUSD: allowance exceeded");
        require(to != address(0), "wQUSD: zero address");
        _allowances[from][msg.sender] -= amount;
        _balances[from]               -= amount;
        _balances[to]                 += amount;
        emit Transfer(from, to, amount);
        return true;
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getWrapStatus() external view returns (
        uint256 locked,
        uint256 supply,
        uint256 wrapped,
        uint256 unwrapped
    ) {
        return (totalLocked, totalSupply, totalWrapped, totalUnwrapped);
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setBridgeOperator(address newBridge) external onlyOwner {
        emit BridgeOperatorUpdated(bridgeOperator, newBridge);
        bridgeOperator = newBridge;
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
