// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title QuantumBridgeVault — ZK-Proof Native Token Lock Vault
/// @notice Deployed on external EVM chains (ETH, BSC, Polygon, Arbitrum, Optimism, Avalanche, Base).
///         Locks native tokens (ETH/BNB/MATIC/AVAX) and emits events consumed by the ZK prover.
///         Unlocks native tokens when a valid ZK proof of burn on QBC chain is verified.
/// @dev    Part of the Quantum Bridge system:
///         [QuantumBridgeVault] → ZK Proof → [ZKBridgeVerifier] → [BridgeMinter] on QBC
///         [BridgeMinter burn] → ZK Proof → [QuantumBridgeVault unlock] on source chain
contract QuantumBridgeVault is Initializable {
    // ── State ──────────────────────────────────────────────────────────
    address public owner;
    address public guardian;           // Emergency pause authority
    bool    public paused;
    bool    private _locked;

    uint256 public feeBps;
    uint256 public constant BPS_DENOMINATOR = 10000;
    uint256 public constant MAX_FEE_BPS = 500;    // 5% absolute max
    uint256 public constant MIN_DEPOSIT = 1e12;    // 0.000001 ETH (18 dec) or equivalent
    uint256 public constant TIMELOCK_PERIOD = 24 hours;

    uint256 public totalLocked;
    uint256 public totalFees;
    address public feeRecipient;
    uint256 public depositNonce;

    // QBC chain ID for cross-chain identification
    uint256 public constant QBC_CHAIN_ID = 3303;

    // ZK Verifier contract on THIS chain (for processing unlocks)
    address public zkVerifier;

    // ── Deposit tracking ───────────────────────────────────────────────
    struct Deposit {
        address depositor;
        uint256 amount;            // Net amount locked (after fee)
        uint256 fee;
        uint256 nonce;             // Unique per-vault nonce
        bytes32 commitment;        // Poseidon2 commitment: H(depositor, amount, nonce, chainId)
        uint256 timestamp;
        bool    unlocked;          // Set true when reverse bridge completes
    }

    mapping(bytes32 => Deposit) public deposits;

    // ── Unlock tracking (ZK-verified) ──────────────────────────────────
    mapping(bytes32 => bool) public processedUnlocks;  // burnHash → processed
    mapping(bytes32 => bool) public processedProofs;   // proofHash → used (replay protection)

    // ── Timelock for admin operations ──────────────────────────────────
    struct TimelockOp {
        bytes32 opHash;
        uint256 executeAfter;
        bool    executed;
    }
    mapping(bytes32 => TimelockOp) public timelocks;

    // ── Events ─────────────────────────────────────────────────────────
    event Locked(
        bytes32 indexed depositId,
        address indexed depositor,
        uint256 amount,
        uint256 fee,
        uint256 nonce,
        bytes32 commitment,
        string  qbcRecipient
    );

    event Unlocked(
        bytes32 indexed unlockId,
        address indexed recipient,
        uint256 amount,
        bytes32 indexed burnProofHash
    );

    event ZKVerifierUpdated(address indexed oldVerifier, address indexed newVerifier);
    event GuardianUpdated(address indexed oldGuardian, address indexed newGuardian);
    event FeeBpsUpdated(uint256 oldFeeBps, uint256 newFeeBps);
    event FeesWithdrawn(address indexed to, uint256 amount);
    event TimelockQueued(bytes32 indexed opHash, uint256 executeAfter);
    event TimelockExecuted(bytes32 indexed opHash);
    event Paused(address indexed by);
    event Unpaused(address indexed by);
    event EmergencyWithdraw(address indexed to, uint256 amount);

    // ── Modifiers ──────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "QBV: not owner");
        _;
    }

    modifier onlyGuardianOrOwner() {
        require(msg.sender == owner || msg.sender == guardian, "QBV: not authorized");
        _;
    }

    modifier onlyZKVerifier() {
        require(msg.sender == zkVerifier, "QBV: not verifier");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "QBV: paused");
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "QBV: reentrant");
        _locked = true;
        _;
        _locked = false;
    }

    // ── Initializer ───────────────────────────────────────────────────
    function initialize(
        address _feeRecipient,
        address _guardian,
        uint256 _feeBps
    ) external initializer {
        require(_feeRecipient != address(0), "QBV: zero fee recipient");
        owner = msg.sender;
        guardian = _guardian;
        feeRecipient = _feeRecipient;
        feeBps = _feeBps <= MAX_FEE_BPS ? _feeBps : 10; // Default 0.1%
    }

    // ── Lock Native Tokens ────────────────────────────────────────────

    /// @notice Lock native tokens (ETH/BNB/MATIC/AVAX) to bridge to QBC chain.
    ///         Emits a Locked event with a Poseidon2-compatible commitment that the
    ///         ZK prover uses to generate a mint proof on QBC.
    /// @param qbcRecipient Address on QBC chain to receive wrapped tokens
    function lock(string calldata qbcRecipient)
        external payable whenNotPaused nonReentrant
    {
        require(msg.value >= MIN_DEPOSIT, "QBV: below minimum");
        require(bytes(qbcRecipient).length > 0, "QBV: empty recipient");

        // Calculate fee
        uint256 fee = (msg.value * feeBps) / BPS_DENOMINATOR;
        uint256 netAmount = msg.value - fee;

        // Increment nonce
        depositNonce++;

        // Generate commitment: keccak256(depositor, amount, nonce, block.chainid)
        // The ZK prover will re-derive this using Poseidon2 for the ZK circuit
        bytes32 commitment = keccak256(abi.encodePacked(
            msg.sender,
            netAmount,
            depositNonce,
            block.chainid
        ));

        // Generate deposit ID from commitment
        bytes32 depositId = keccak256(abi.encodePacked(
            commitment,
            block.number,
            block.timestamp
        ));

        deposits[depositId] = Deposit({
            depositor: msg.sender,
            amount: netAmount,
            fee: fee,
            nonce: depositNonce,
            commitment: commitment,
            timestamp: block.timestamp,
            unlocked: false
        });

        totalLocked += netAmount;
        totalFees += fee;

        emit Locked(
            depositId,
            msg.sender,
            netAmount,
            fee,
            depositNonce,
            commitment,
            qbcRecipient
        );
    }

    // ── Unlock via ZK Proof ───────────────────────────────────────────

    /// @notice Unlock native tokens when a ZK proof of wToken burn on QBC is verified.
    ///         Only callable by the ZKBridgeVerifier contract after proof validation.
    /// @param recipient    Address to receive unlocked native tokens
    /// @param amount       Amount to unlock
    /// @param burnProofHash Hash of the ZK proof (for replay protection)
    function unlock(
        address recipient,
        uint256 amount,
        bytes32 burnProofHash
    ) external onlyZKVerifier whenNotPaused nonReentrant {
        require(recipient != address(0), "QBV: zero recipient");
        require(amount > 0 && amount <= totalLocked, "QBV: invalid amount");
        require(!processedProofs[burnProofHash], "QBV: proof already used");

        processedProofs[burnProofHash] = true;

        bytes32 unlockId = keccak256(abi.encodePacked(
            recipient, amount, burnProofHash, block.number
        ));

        processedUnlocks[unlockId] = true;
        totalLocked -= amount;

        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "QBV: transfer failed");

        emit Unlocked(unlockId, recipient, amount, burnProofHash);
    }

    // ── Admin (Timelocked) ────────────────────────────────────────────

    /// @notice Queue a timelock operation for sensitive admin changes
    function queueTimelock(bytes32 opHash) external onlyOwner {
        require(timelocks[opHash].executeAfter == 0, "QBV: already queued");
        timelocks[opHash] = TimelockOp({
            opHash: opHash,
            executeAfter: block.timestamp + TIMELOCK_PERIOD,
            executed: false
        });
        emit TimelockQueued(opHash, block.timestamp + TIMELOCK_PERIOD);
    }

    /// @notice Set the ZK verifier contract (timelocked)
    function setZKVerifier(address _verifier) external onlyOwner {
        bytes32 opHash = keccak256(abi.encodePacked("setZKVerifier", _verifier));
        TimelockOp storage op = timelocks[opHash];
        require(op.executeAfter > 0 && !op.executed, "QBV: not queued");
        require(block.timestamp >= op.executeAfter, "QBV: timelock active");
        require(_verifier != address(0), "QBV: zero verifier");

        op.executed = true;
        emit TimelockExecuted(opHash);

        address old = zkVerifier;
        zkVerifier = _verifier;
        emit ZKVerifierUpdated(old, _verifier);
    }

    /// @notice Set ZK verifier without timelock — ONLY during initial setup (verifier == address(0))
    function setZKVerifierInitial(address _verifier) external onlyOwner {
        require(zkVerifier == address(0), "QBV: verifier already set");
        require(_verifier != address(0), "QBV: zero verifier");
        zkVerifier = _verifier;
        emit ZKVerifierUpdated(address(0), _verifier);
    }

    function setGuardian(address _guardian) external onlyOwner {
        address old = guardian;
        guardian = _guardian;
        emit GuardianUpdated(old, _guardian);
    }

    function setFeeBps(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= MAX_FEE_BPS, "QBV: fee too high");
        uint256 old = feeBps;
        feeBps = newFeeBps;
        emit FeeBpsUpdated(old, newFeeBps);
    }

    function setFeeRecipient(address _recipient) external onlyOwner {
        require(_recipient != address(0), "QBV: zero recipient");
        feeRecipient = _recipient;
    }

    function withdrawFees() external onlyOwner nonReentrant {
        uint256 amount = totalFees;
        require(amount > 0, "QBV: no fees");
        totalFees = 0;
        (bool ok,) = feeRecipient.call{value: amount}("");
        require(ok, "QBV: fee transfer failed");
        emit FeesWithdrawn(feeRecipient, amount);
    }

    // ── Emergency ─────────────────────────────────────────────────────

    function pause() external onlyGuardianOrOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }

    /// @notice Emergency withdraw all funds to owner. Only when paused.
    ///         This is a last-resort mechanism for critical vulnerabilities.
    function emergencyWithdraw() external onlyOwner nonReentrant {
        require(paused, "QBV: must be paused");
        uint256 balance = address(this).balance;
        require(balance > 0, "QBV: no balance");

        totalLocked = 0;
        totalFees = 0;

        (bool ok,) = owner.call{value: balance}("");
        require(ok, "QBV: emergency transfer failed");
        emit EmergencyWithdraw(owner, balance);
    }

    // ── Views ─────────────────────────────────────────────────────────

    function getDeposit(bytes32 depositId) external view returns (
        address depositor, uint256 amount, uint256 fee,
        uint256 nonce, bytes32 commitment,
        uint256 timestamp, bool unlocked
    ) {
        Deposit storage d = deposits[depositId];
        return (d.depositor, d.amount, d.fee, d.nonce,
                d.commitment, d.timestamp, d.unlocked);
    }

    function getStats() external view returns (
        uint256 locked, uint256 fees, uint256 nonces,
        uint256 chainId, bool isPaused
    ) {
        return (totalLocked, totalFees, depositNonce, block.chainid, paused);
    }

    function isProofUsed(bytes32 proofHash) external view returns (bool) {
        return processedProofs[proofHash];
    }

    /// @notice Accept native token transfers
    receive() external payable {}
}
