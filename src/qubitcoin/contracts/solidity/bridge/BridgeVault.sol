// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title BridgeVault — QBC Lock/Unlock Vault for Cross-Chain Bridges
/// @notice Deployed on QBC L1 chain. Locks QBC when bridging out,
///         unlocks QBC when bridging back. Bridge fee: 0.1% of transfer.
/// @dev Supports 8 target chains: ETH, SOL, MATIC, BNB, AVAX, ARB, OP, BASE
contract BridgeVault is Initializable {
    address public owner;
    bool    public paused;

    uint256 public constant FEE_BPS = 10;        // 0.1% = 10 basis points
    uint256 public constant BPS_DENOMINATOR = 10000;
    uint256 public constant MIN_DEPOSIT = 1e6;    // 0.01 QBC (8 decimals)
    uint256 public constant MAX_DEPOSIT = 1e16;   // 100M QBC daily limit

    uint256 public totalLocked;                   // Total QBC currently locked
    uint256 public totalFees;                     // Accumulated fees
    address public feeRecipient;                  // Treasury address for fees
    uint256 public dailyVolume;                   // Today's bridge volume
    uint256 public dailyVolumeDate;               // Date (block.timestamp / 1 day)

    // Supported target chains
    mapping(uint256 => bool) public supportedChains;
    uint256[] public chainIds;

    // Deposit tracking
    struct Deposit {
        address depositor;
        uint256 amount;           // QBC locked (after fee)
        uint256 fee;              // Fee deducted
        uint256 targetChain;      // Target chain ID
        string  targetAddress;    // Address on target chain
        uint256 timestamp;
        bool    processed;        // Bridge relayer has minted wQBC
    }

    mapping(bytes32 => Deposit) public deposits;
    uint256 public depositCount;

    // Withdrawal tracking (wQBC burn → QBC unlock)
    struct Withdrawal {
        address recipient;
        uint256 amount;
        uint256 sourceChain;
        bytes32 sourceTxHash;     // Tx on source chain that burned wQBC
        uint256 timestamp;
        bool    completed;
    }

    mapping(bytes32 => Withdrawal) public withdrawals;
    uint256 public withdrawalCount;

    // Authorized bridge relayers (multi-sig path)
    mapping(address => bool) public relayers;
    uint256 public requiredConfirmations;

    // ── Events ──────────────────────────────────────────────────────
    event DepositLocked(
        bytes32 indexed depositId,
        address indexed depositor,
        uint256 amount,
        uint256 fee,
        uint256 indexed targetChain,
        string targetAddress
    );
    event WithdrawalUnlocked(
        bytes32 indexed withdrawalId,
        address indexed recipient,
        uint256 amount,
        uint256 indexed sourceChain,
        bytes32 sourceTxHash
    );
    event DepositProcessed(bytes32 indexed depositId, bytes32 targetTxHash);
    event ChainAdded(uint256 indexed chainId);
    event ChainRemoved(uint256 indexed chainId);
    event RelayerAdded(address indexed relayer);
    event RelayerRemoved(address indexed relayer);
    event FeesWithdrawn(address indexed to, uint256 amount);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ── Modifiers ───────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Vault: not owner");
        _;
    }

    modifier onlyRelayer() {
        require(relayers[msg.sender], "Vault: not relayer");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "Vault: paused");
        _;
    }

    // ── Initializer ────────────────────────────────────────────────
    function initialize(address _feeRecipient, uint256 _requiredConfirmations) external initializer {
        owner = msg.sender;
        feeRecipient = _feeRecipient != address(0) ? _feeRecipient : msg.sender;
        requiredConfirmations = _requiredConfirmations > 0 ? _requiredConfirmations : 1;

        // Register default supported chains
        uint256[8] memory defaultChains = [
            uint256(1),     // Ethereum
            uint256(137),   // Polygon
            uint256(56),    // BSC
            uint256(42161), // Arbitrum
            uint256(10),    // Optimism
            uint256(43114), // Avalanche
            uint256(8453),  // Base
            uint256(0)      // Solana (represented as 0 — non-EVM)
        ];
        for (uint i = 0; i < defaultChains.length; i++) {
            supportedChains[defaultChains[i]] = true;
            chainIds.push(defaultChains[i]);
        }
    }

    // ── Lock QBC (Deposit) ──────────────────────────────────────────

    /// @notice Lock QBC to bridge to an external chain.
    /// @param targetChain   Chain ID of the target chain
    /// @param targetAddress Address on the target chain to receive wQBC
    function deposit(uint256 targetChain, string calldata targetAddress)
        external payable whenNotPaused
    {
        require(supportedChains[targetChain], "Vault: unsupported chain");
        require(msg.value >= MIN_DEPOSIT, "Vault: below minimum");
        require(bytes(targetAddress).length > 0, "Vault: empty target");

        // Daily limit check
        uint256 today = block.timestamp / 1 days;
        if (today != dailyVolumeDate) {
            dailyVolume = 0;
            dailyVolumeDate = today;
        }
        dailyVolume += msg.value;
        require(dailyVolume <= MAX_DEPOSIT, "Vault: daily limit exceeded");

        // Calculate fee
        uint256 fee = (msg.value * FEE_BPS) / BPS_DENOMINATOR;
        uint256 netAmount = msg.value - fee;

        // Generate deposit ID
        depositCount++;
        bytes32 depositId = keccak256(abi.encodePacked(
            msg.sender, targetChain, targetAddress, block.number, depositCount
        ));

        deposits[depositId] = Deposit({
            depositor: msg.sender,
            amount: netAmount,
            fee: fee,
            targetChain: targetChain,
            targetAddress: targetAddress,
            timestamp: block.timestamp,
            processed: false
        });

        totalLocked += netAmount;
        totalFees += fee;

        emit DepositLocked(
            depositId, msg.sender, netAmount, fee, targetChain, targetAddress
        );
    }

    /// @notice Mark a deposit as processed (wQBC minted on target chain).
    /// @param depositId    The deposit being confirmed
    /// @param targetTxHash Tx hash on target chain where wQBC was minted
    function confirmDeposit(bytes32 depositId, bytes32 targetTxHash)
        external onlyRelayer whenNotPaused
    {
        Deposit storage d = deposits[depositId];
        require(d.depositor != address(0), "Vault: deposit not found");
        require(!d.processed, "Vault: already processed");

        d.processed = true;
        emit DepositProcessed(depositId, targetTxHash);
    }

    // ── Unlock QBC (Withdrawal) ─────────────────────────────────────

    /// @notice Unlock QBC when wQBC is burned on an external chain.
    /// @param recipient    QBC address to receive unlocked funds
    /// @param amount       Amount of QBC to unlock
    /// @param sourceChain  Chain where wQBC was burned
    /// @param sourceTxHash Tx hash of the burn on the source chain
    function processWithdrawal(
        address recipient,
        uint256 amount,
        uint256 sourceChain,
        bytes32 sourceTxHash
    ) external onlyRelayer whenNotPaused {
        require(recipient != address(0), "Vault: zero recipient");
        require(amount > 0, "Vault: zero amount");
        require(amount <= totalLocked, "Vault: insufficient locked");

        bytes32 wId = keccak256(abi.encodePacked(
            recipient, amount, sourceChain, sourceTxHash
        ));
        require(!withdrawals[wId].completed, "Vault: already withdrawn");

        withdrawals[wId] = Withdrawal({
            recipient: recipient,
            amount: amount,
            sourceChain: sourceChain,
            sourceTxHash: sourceTxHash,
            timestamp: block.timestamp,
            completed: true
        });

        withdrawalCount++;
        totalLocked -= amount;

        // Transfer QBC to recipient
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "Vault: transfer failed");

        emit WithdrawalUnlocked(wId, recipient, amount, sourceChain, sourceTxHash);
    }

    // ── Admin ───────────────────────────────────────────────────────

    function addChain(uint256 chainId) external onlyOwner {
        require(!supportedChains[chainId], "Vault: chain exists");
        supportedChains[chainId] = true;
        chainIds.push(chainId);
        emit ChainAdded(chainId);
    }

    function removeChain(uint256 chainId) external onlyOwner {
        require(supportedChains[chainId], "Vault: chain not found");
        supportedChains[chainId] = false;
        emit ChainRemoved(chainId);
    }

    function addRelayer(address relayer) external onlyOwner {
        require(!relayers[relayer], "Vault: relayer exists");
        relayers[relayer] = true;
        emit RelayerAdded(relayer);
    }

    function removeRelayer(address relayer) external onlyOwner {
        require(relayers[relayer], "Vault: relayer not found");
        relayers[relayer] = false;
        emit RelayerRemoved(relayer);
    }

    function withdrawFees() external onlyOwner {
        uint256 amount = totalFees;
        require(amount > 0, "Vault: no fees");
        totalFees = 0;
        (bool ok,) = feeRecipient.call{value: amount}("");
        require(ok, "Vault: fee transfer failed");
        emit FeesWithdrawn(feeRecipient, amount);
    }

    function setFeeRecipient(address _recipient) external onlyOwner {
        require(_recipient != address(0), "Vault: zero recipient");
        feeRecipient = _recipient;
    }

    function pause() external onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }

    // ── Views ───────────────────────────────────────────────────────

    function getStats() external view returns (
        uint256 locked, uint256 fees, uint256 numDeposits,
        uint256 numWithdrawals, uint256 numChains
    ) {
        return (totalLocked, totalFees, depositCount, withdrawalCount, chainIds.length);
    }

    function getDeposit(bytes32 depositId) external view returns (
        address depositor, uint256 amount, uint256 fee,
        uint256 targetChain, string memory targetAddress,
        uint256 timestamp, bool processed
    ) {
        Deposit storage d = deposits[depositId];
        return (d.depositor, d.amount, d.fee, d.targetChain,
                d.targetAddress, d.timestamp, d.processed);
    }

    /// @notice Accept QBC transfers (required for lock-and-mint)
    receive() external payable {}
}
