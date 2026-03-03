// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../interfaces/IQBC20.sol";
import "../proxy/Initializable.sol";

/// @title wQBC — Wrapped QBC for Cross-Chain Bridging (QBC-Chain Deployment)
/// @notice This contract is deployed on the QBC L1 chain. It is the full-featured
///         wQBC implementation with 0.1% bridge fee (10 bps), replay protection via
///         processedTxHashes, reentrancy guard, and cumulative accounting (totalLocked,
///         totalMinted, totalBurned, totalFeesCollected).
///
///         A separate bridge/wQBC.sol exists for deployment on external chains
///         (ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE). That version is a simplified
///         bridge-only mint/burn contract without fees or replay tracking — the bridge
///         operator on the external chain handles those concerns.
///
/// @dev    Lock-and-mint on destination chains: QBC locked here -> wQBC minted on external.
///         Burn-and-unlock on return: wQBC burned on external -> QBC unlocked here.
contract wQBC is IQBC20, Initializable {
    // ─── Token Metadata ──────────────────────────────────────────────────
    string  public constant name     = "Wrapped Qubitcoin";
    string  public constant symbol   = "wQBC";
    uint8   public constant decimals = 8;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public bridgeOperator;  // authorized to mint/burn for bridge operations
    address public feeRecipient;    // receives bridge fees

    uint256 public totalSupply;
    uint256 public totalLocked;     // QBC locked on source chain (tracked)
    uint256 public totalMinted;     // cumulative wQBC minted
    uint256 public totalBurned;     // cumulative wQBC burned
    uint256 public totalFeesCollected;

    /// @notice Bridge fee in basis points (10 = 0.1%)
    uint256 public bridgeFeeBps = 10;
    uint256 public constant MAX_FEE_BPS = 100; // 1% max

    mapping(address => uint256)                     private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    /// @notice Processed cross-chain tx hashes to prevent replay
    mapping(bytes32 => bool) public processedTxHashes;

    bool private _locked; // reentrancy guard
    bool public paused;   // emergency pause

    // ─── Events ──────────────────────────────────────────────────────────
    event BridgeMint(address indexed recipient, uint256 amount, uint256 fee, bytes32 indexed sourceTxHash, uint256 indexed sourceChainId);
    event BridgeBurn(address indexed sender, uint256 amount, uint256 fee, uint256 indexed destChainId);
    event BridgeOperatorUpdated(address indexed prev, address indexed next);
    event FeeRecipientUpdated(address indexed prev, address indexed next);
    event FeeBpsUpdated(uint256 prev, uint256 next);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "wQBC: not owner");
        _;
    }

    modifier onlyBridge() {
        require(msg.sender == bridgeOperator, "wQBC: not bridge operator");
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "wQBC: reentrant");
        _locked = true;
        _;
        _locked = false;
    }

    modifier whenNotPaused() {
        require(!paused, "wQBC: paused");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _bridgeOperator, address _feeRecipient) external initializer {
        require(_bridgeOperator != address(0), "wQBC: zero bridge");
        require(_feeRecipient != address(0), "wQBC: zero fee recipient");
        owner          = msg.sender;
        bridgeOperator = _bridgeOperator;
        feeRecipient   = _feeRecipient;
    }

    // ─── Bridge Operations ───────────────────────────────────────────────

    /// @notice Mint wQBC on destination chain when QBC is locked on QBC chain.
    ///         Called by bridge operator after verifying lock on source chain.
    /// @param recipient Address to receive wQBC
    /// @param amount Gross amount (fee deducted from this)
    /// @param sourceTxHash Hash of the lock transaction on QBC chain
    /// @param sourceChainId Chain ID of the source chain (3301 for QBC mainnet)
    function bridgeMint(
        address recipient,
        uint256 amount,
        bytes32 sourceTxHash,
        uint256 sourceChainId
    ) external onlyBridge nonReentrant whenNotPaused {
        require(recipient != address(0), "wQBC: zero recipient");
        require(amount > 0, "wQBC: zero amount");
        require(!processedTxHashes[sourceTxHash], "wQBC: already processed");

        processedTxHashes[sourceTxHash] = true;

        uint256 fee = (amount * bridgeFeeBps) / 10000;
        uint256 netAmount = amount - fee;

        totalSupply          += amount;
        totalLocked          += amount;
        totalMinted          += amount;
        _balances[recipient] += netAmount;
        totalFeesCollected   += fee;

        if (fee > 0) {
            _balances[feeRecipient] += fee;
            emit Transfer(address(0), feeRecipient, fee);
        }

        emit Transfer(address(0), recipient, netAmount);
        emit BridgeMint(recipient, netAmount, fee, sourceTxHash, sourceChainId);
    }

    /// @notice Burn wQBC to redeem native QBC on QBC chain.
    ///         Bridge operator observes burn event and unlocks QBC on source chain.
    /// @param amount Amount of wQBC to burn
    /// @param destChainId Destination chain ID (3301 for QBC mainnet)
    function bridgeBurn(
        uint256 amount,
        uint256 destChainId
    ) external nonReentrant whenNotPaused {
        require(amount > 0, "wQBC: zero amount");
        require(_balances[msg.sender] >= amount, "wQBC: insufficient balance");

        uint256 fee = (amount * bridgeFeeBps) / 10000;
        uint256 netAmount = amount - fee;

        _balances[msg.sender] -= amount;
        totalSupply           -= netAmount;
        totalBurned           += netAmount;
        totalFeesCollected    += fee;

        if (fee > 0) {
            _balances[feeRecipient] += fee;
            emit Transfer(msg.sender, feeRecipient, fee);
        }

        emit Transfer(msg.sender, address(0), netAmount);
        emit BridgeBurn(msg.sender, netAmount, fee, destChainId);
    }

    // ─── QBC-20 (ERC-20) Implementation ─────────────────────────────────
    function balanceOf(address account) external view returns (uint256) {
        return _balances[account];
    }

    function allowance(address _owner, address spender) external view returns (uint256) {
        return _allowances[_owner][spender];
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        require(amount == 0 || _allowances[msg.sender][spender] == 0, "wQBC: set allowance to 0 first");
        _allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transfer(address to, uint256 amount) external whenNotPaused returns (bool) {
        require(_balances[msg.sender] >= amount, "wQBC: insufficient");
        require(to != address(0), "wQBC: zero address");
        _balances[msg.sender] -= amount;
        _balances[to]         += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external whenNotPaused returns (bool) {
        require(_balances[from] >= amount, "wQBC: insufficient");
        require(_allowances[from][msg.sender] >= amount, "wQBC: allowance exceeded");
        require(to != address(0), "wQBC: zero address");
        _allowances[from][msg.sender] -= amount;
        _balances[from]               -= amount;
        _balances[to]                 += amount;
        emit Transfer(from, to, amount);
        return true;
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getBridgeStatus() external view returns (
        uint256 supply,
        uint256 locked,
        uint256 minted,
        uint256 burned,
        uint256 fees
    ) {
        return (totalSupply, totalLocked, totalMinted, totalBurned, totalFeesCollected);
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setBridgeOperator(address newBridge) external onlyOwner {
        require(newBridge != address(0), "wQBC: zero address");
        emit BridgeOperatorUpdated(bridgeOperator, newBridge);
        bridgeOperator = newBridge;
    }

    function setFeeRecipient(address newRecipient) external onlyOwner {
        require(newRecipient != address(0), "wQBC: zero address");
        emit FeeRecipientUpdated(feeRecipient, newRecipient);
        feeRecipient = newRecipient;
    }

    function setBridgeFeeBps(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= MAX_FEE_BPS, "wQBC: fee too high");
        emit FeeBpsUpdated(bridgeFeeBps, newFeeBps);
        bridgeFeeBps = newFeeBps;
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
        require(newOwner != address(0), "wQBC: zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
}
