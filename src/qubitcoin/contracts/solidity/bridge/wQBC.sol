// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title wQBC — Wrapped Qubitcoin Token (External Chain Deployment)
/// @notice This contract is deployed on external chains (Ethereum, Polygon, BSC,
///         Avalanche, Arbitrum, Optimism, Base, etc.). It is a simplified bridge-only
///         mint/burn ERC-20 without bridge fees or replay protection — the bridge
///         operator on the external chain handles fee collection and replay tracking.
///
///         A separate tokens/wQBC.sol exists for deployment on the QBC L1 chain.
///         That version is the full-featured implementation with 0.1% bridge fee,
///         replay protection (processedTxHashes), reentrancy guard, and cumulative
///         accounting (totalLocked, totalMinted, totalBurned, totalFeesCollected).
///
/// @dev    Minted 1:1 when QBC is locked on the QBC L1 chain.
///         Burned to unlock QBC back to the native chain.
///         Only the authorized bridge contract can mint/burn.
contract wQBC is Initializable {
    string  public constant name     = "Wrapped Qubitcoin";
    string  public constant symbol   = "wQBC";
    uint8   public constant decimals = 8;  // Match QBC L1 precision
    uint256 public totalSupply;

    address public bridge;             // Authorized bridge contract
    address public owner;              // Admin (governance upgrade path)
    bool    public paused;

    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    // ── Events ──────────────────────────────────────────────────────
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event BridgeMint(address indexed to, uint256 amount, bytes32 indexed qbcTxId);
    event BridgeBurn(address indexed from, uint256 amount, string qbcAddress);
    event BridgeUpdated(address indexed oldBridge, address indexed newBridge);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ── Modifiers ───────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "wQBC: not owner");
        _;
    }

    modifier onlyBridge() {
        require(msg.sender == bridge, "wQBC: not bridge");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "wQBC: paused");
        _;
    }

    // ── Initializer ────────────────────────────────────────────────
    function initialize(address _bridge) external initializer {
        require(_bridge != address(0), "wQBC: zero bridge");
        owner  = msg.sender;
        bridge = _bridge;
    }

    // ── Bridge Operations ───────────────────────────────────────────

    /// @notice Mint wQBC when QBC is locked on L1. Only callable by bridge.
    /// @param to     Recipient on this chain
    /// @param amount Amount of wQBC to mint (8 decimals)
    /// @param qbcTxId Transaction ID on QBC L1 that locked the QBC
    function mint(address to, uint256 amount, bytes32 qbcTxId)
        external onlyBridge whenNotPaused
    {
        require(to != address(0), "wQBC: mint to zero");
        require(amount > 0, "wQBC: zero amount");

        totalSupply += amount;
        _balances[to] += amount;

        emit Transfer(address(0), to, amount);
        emit BridgeMint(to, amount, qbcTxId);
    }

    /// @notice Burn wQBC to unlock QBC on L1. Only callable by bridge.
    /// @param from       Holder burning wQBC
    /// @param amount     Amount to burn
    /// @param qbcAddress Destination address on QBC L1
    function burn(address from, uint256 amount, string calldata qbcAddress)
        external onlyBridge whenNotPaused
    {
        require(amount > 0, "wQBC: zero amount");
        require(_balances[from] >= amount, "wQBC: insufficient balance");
        require(bytes(qbcAddress).length > 0, "wQBC: empty qbc address");

        _balances[from] -= amount;
        totalSupply -= amount;

        emit Transfer(from, address(0), amount);
        emit BridgeBurn(from, amount, qbcAddress);
    }

    // ── ERC-20 Standard ─────────────────────────────────────────────

    function balanceOf(address account) external view returns (uint256) {
        return _balances[account];
    }

    function transfer(address to, uint256 amount)
        external whenNotPaused returns (bool)
    {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount)
        external returns (bool)
    {
        _allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function allowance(address _owner, address spender)
        external view returns (uint256)
    {
        return _allowances[_owner][spender];
    }

    function transferFrom(address from, address to, uint256 amount)
        external whenNotPaused returns (bool)
    {
        uint256 allowed = _allowances[from][msg.sender];
        require(allowed >= amount, "wQBC: allowance exceeded");
        _allowances[from][msg.sender] = allowed - amount;
        _transfer(from, to, amount);
        return true;
    }

    // ── Admin ───────────────────────────────────────────────────────

    function setBridge(address newBridge) external onlyOwner {
        require(newBridge != address(0), "wQBC: zero bridge");
        emit BridgeUpdated(bridge, newBridge);
        bridge = newBridge;
    }

    function pause() external onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "wQBC: zero owner");
        owner = newOwner;
    }

    // ── Internal ────────────────────────────────────────────────────

    function _transfer(address from, address to, uint256 amount) internal {
        require(from != address(0), "wQBC: from zero");
        require(to != address(0), "wQBC: to zero");
        require(_balances[from] >= amount, "wQBC: insufficient balance");

        _balances[from] -= amount;
        _balances[to]   += amount;
        emit Transfer(from, to, amount);
    }
}
