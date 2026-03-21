// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title WrappedAsset — Universal Wrapped Token for Quantum Bridge
/// @notice Deployed on QBC chain for each bridged asset (wETH, wBNB, wMATIC, wAVAX).
///         Minted 1:1 when native tokens are locked in QuantumBridgeVault on external chains.
///         Burned to unlock native tokens back on the external chain.
/// @dev    Only the BridgeMinter contract can mint/burn. Follows ERC-20 standard with 18 decimals.
///         Deploy one instance per bridged chain:
///         - wETH  (sourceChainId: 1, 42161, 10, 8453)
///         - wBNB  (sourceChainId: 56)
///         - wMATIC (sourceChainId: 137)
///         - wAVAX (sourceChainId: 43114)
contract WrappedAsset is Initializable {
    string  public name;
    string  public symbol;
    uint8   public decimals;
    uint256 public totalSupply;

    address public minter;           // BridgeMinter contract
    address public owner;
    bool    public paused;

    uint256 public sourceChainId;    // Chain where native asset lives

    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    // Mint tracking for auditability
    mapping(bytes32 => bool) public mintedProofs;  // proofHash → minted

    // ── Events ──────────────────────────────────────────────────────
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event BridgeMint(address indexed to, uint256 amount, bytes32 indexed proofHash);
    event BridgeBurn(address indexed from, uint256 amount);
    event MinterUpdated(address indexed oldMinter, address indexed newMinter);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ── Modifiers ───────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "WA: not owner");
        _;
    }

    modifier onlyMinter() {
        require(msg.sender == minter, "WA: not minter");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "WA: paused");
        _;
    }

    // ── Initializer ────────────────────────────────────────────────
    /// @param _name         Token name (e.g., "Wrapped Ether")
    /// @param _symbol       Token symbol (e.g., "wETH")
    /// @param _decimals     Token decimals (18 for ETH/BNB/MATIC/AVAX)
    /// @param _minter       BridgeMinter contract address
    /// @param _sourceChainId Chain ID of the native asset
    function initialize(
        string calldata _name,
        string calldata _symbol,
        uint8 _decimals,
        address _minter,
        uint256 _sourceChainId
    ) external initializer {
        require(_minter != address(0), "WA: zero minter");
        require(_sourceChainId > 0, "WA: zero chain");

        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        minter = _minter;
        sourceChainId = _sourceChainId;
        owner = msg.sender;
    }

    // ── Bridge Operations ───────────────────────────────────────────

    /// @notice Mint wrapped tokens. Only callable by BridgeMinter.
    function mint(address to, uint256 amount, bytes32 proofHash)
        external onlyMinter whenNotPaused
    {
        require(to != address(0), "WA: mint to zero");
        require(amount > 0, "WA: zero amount");
        require(!mintedProofs[proofHash], "WA: proof already minted");

        mintedProofs[proofHash] = true;
        totalSupply += amount;
        _balances[to] += amount;

        emit Transfer(address(0), to, amount);
        emit BridgeMint(to, amount, proofHash);
    }

    /// @notice Burn wrapped tokens. Only callable by BridgeMinter.
    function burn(address from, uint256 amount)
        external onlyMinter whenNotPaused
    {
        require(amount > 0, "WA: zero amount");
        require(_balances[from] >= amount, "WA: insufficient balance");

        _balances[from] -= amount;
        totalSupply -= amount;

        emit Transfer(from, address(0), amount);
        emit BridgeBurn(from, amount);
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
        require(amount == 0 || _allowances[msg.sender][spender] == 0, "WA: reset allowance first");
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
        require(allowed >= amount, "WA: allowance exceeded");
        _allowances[from][msg.sender] = allowed - amount;
        _transfer(from, to, amount);
        return true;
    }

    // ── Admin ───────────────────────────────────────────────────────

    function setMinter(address newMinter) external onlyOwner {
        require(newMinter != address(0), "WA: zero minter");
        address old = minter;
        minter = newMinter;
        emit MinterUpdated(old, newMinter);
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
        require(newOwner != address(0), "WA: zero owner");
        owner = newOwner;
    }

    // ── Internal ────────────────────────────────────────────────────

    function _transfer(address from, address to, uint256 amount) internal {
        require(from != address(0), "WA: from zero");
        require(to != address(0), "WA: to zero");
        require(_balances[from] >= amount, "WA: insufficient balance");

        _balances[from] -= amount;
        _balances[to]   += amount;
        emit Transfer(from, to, amount);
    }
}
