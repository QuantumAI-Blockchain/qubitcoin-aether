// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title BridgeMinter — Wrapped Token Minting/Burning Hub for Quantum Bridge
/// @notice Deployed on the QBC chain. Mints wrapped tokens (wETH, wBNB, wMATIC, wAVAX)
///         when ZK proofs of lock events are verified by ZKBridgeVerifier.
///         Burns wrapped tokens when users want to unlock on external chains.
/// @dev    Flow:
///         Lock on ETH → ZK Proof → ZKBridgeVerifier.submitProof() → BridgeMinter.mintFromProof() → wETH minted
///         User burns wETH → BridgeMinter.burn() → ZK Proof → ZKBridgeVerifier on ETH → QuantumBridgeVault.unlock()
contract BridgeMinter is Initializable {
    // ── State ──────────────────────────────────────────────────────────
    address public owner;
    bool    public paused;
    bool    private _locked;

    uint256 public constant QBC_CHAIN_ID = 3303;

    // ZK Verifier — only this contract can trigger mints
    address public zkVerifier;

    // Wrapped token contracts per source chain
    // chainId => wToken address
    mapping(uint256 => address) public wrappedTokens;
    uint256[] public supportedChainIds;

    // Burn tracking for reverse bridge
    uint256 public burnNonce;

    struct BurnRecord {
        address burner;
        uint256 amount;
        uint256 destChainId;
        string  destRecipient;     // Address on destination chain
        bytes32 commitment;        // Poseidon2 commitment for ZK proof
        uint256 timestamp;
    }

    mapping(bytes32 => BurnRecord) public burns;

    // Replay protection
    mapping(bytes32 => bool) public processedMintProofs;

    // Stats
    uint256 public totalMinted;
    uint256 public totalBurned;

    // ── Events ─────────────────────────────────────────────────────────
    event Minted(
        bytes32 indexed proofHash,
        address indexed recipient,
        uint256 amount,
        uint256 indexed sourceChainId,
        address wrappedToken
    );

    event Burned(
        bytes32 indexed burnId,
        address indexed burner,
        uint256 amount,
        uint256 indexed destChainId,
        string  destRecipient,
        bytes32 commitment
    );

    event WrappedTokenRegistered(uint256 indexed chainId, address indexed token);
    event WrappedTokenUpdated(uint256 indexed chainId, address indexed oldToken, address indexed newToken);
    event ZKVerifierUpdated(address indexed oldVerifier, address indexed newVerifier);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ── Modifiers ──────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "BM: not owner");
        _;
    }

    modifier onlyZKVerifier() {
        require(msg.sender == zkVerifier, "BM: not verifier");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "BM: paused");
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "BM: reentrant");
        _locked = true;
        _;
        _locked = false;
    }

    // ── Constructor — disables direct initialization of implementation ─
    /// @dev Prevents attackers from initializing the bare implementation contract.
    ///      The proxy's storage is separate; this only affects the implementation address.
    constructor() { _disableInitializers(); }

    // ── Initializer ───────────────────────────────────────────────────
    function initialize(address _zkVerifier) external initializer {
        require(_zkVerifier != address(0), "BM: zero verifier");
        owner = msg.sender;
        zkVerifier = _zkVerifier;
    }

    // ── Mint (called by ZKBridgeVerifier after proof verification) ────

    /// @notice Mint wrapped tokens for a verified ZK proof of lock on external chain.
    ///         Only callable by the ZKBridgeVerifier contract.
    /// @param recipient     Address on QBC chain to receive wrapped tokens
    /// @param amount        Amount to mint (matches locked amount on source chain)
    /// @param sourceChainId Chain ID where native tokens are locked
    /// @param proofHash     Hash of the verified ZK proof (replay protection)
    function mintFromProof(
        address recipient,
        uint256 amount,
        uint256 sourceChainId,
        bytes32 proofHash
    ) external onlyZKVerifier whenNotPaused nonReentrant {
        require(recipient != address(0), "BM: zero recipient");
        require(amount > 0, "BM: zero amount");
        require(!processedMintProofs[proofHash], "BM: proof already processed");

        address wToken = wrappedTokens[sourceChainId];
        require(wToken != address(0), "BM: unsupported chain");

        processedMintProofs[proofHash] = true;
        totalMinted += amount;

        // Mint wrapped tokens
        IWrappedToken(wToken).mint(recipient, amount, proofHash);

        emit Minted(proofHash, recipient, amount, sourceChainId, wToken);
    }

    // ── Burn (user-initiated to bridge back to external chain) ────────

    /// @notice Burn wrapped tokens to initiate unlock on the external chain.
    ///         The burn event is picked up by the ZK prover to generate an
    ///         unlock proof for the QuantumBridgeVault on the destination chain.
    /// @param destChainId    Chain ID to unlock tokens on
    /// @param destRecipient  Address on destination chain to receive unlocked tokens
    /// @param amount         Amount of wrapped tokens to burn
    function burn(
        uint256 destChainId,
        string calldata destRecipient,
        uint256 amount
    ) external whenNotPaused nonReentrant {
        require(amount > 0, "BM: zero amount");
        require(bytes(destRecipient).length > 0, "BM: empty recipient");

        address wToken = wrappedTokens[destChainId];
        require(wToken != address(0), "BM: unsupported chain");

        burnNonce++;

        // Generate commitment for ZK proof
        bytes32 commitment = keccak256(abi.encodePacked(
            msg.sender,
            amount,
            burnNonce,
            QBC_CHAIN_ID,
            destChainId
        ));

        bytes32 burnId = keccak256(abi.encodePacked(
            commitment,
            block.number,
            block.timestamp
        ));

        burns[burnId] = BurnRecord({
            burner: msg.sender,
            amount: amount,
            destChainId: destChainId,
            destRecipient: destRecipient,
            commitment: commitment,
            timestamp: block.timestamp
        });

        totalBurned += amount;

        // Burn the wrapped tokens
        IWrappedToken(wToken).burn(msg.sender, amount);

        emit Burned(burnId, msg.sender, amount, destChainId, destRecipient, commitment);
    }

    // ── Admin ─────────────────────────────────────────────────────────

    /// @notice Register a wrapped token contract for a source chain
    function registerWrappedToken(uint256 chainId, address token) external onlyOwner {
        require(token != address(0), "BM: zero token");
        require(wrappedTokens[chainId] == address(0), "BM: already registered");

        wrappedTokens[chainId] = token;
        supportedChainIds.push(chainId);

        emit WrappedTokenRegistered(chainId, token);
    }

    /// @notice Update a wrapped token contract for a source chain
    function updateWrappedToken(uint256 chainId, address newToken) external onlyOwner {
        require(newToken != address(0), "BM: zero token");
        address old = wrappedTokens[chainId];
        require(old != address(0), "BM: not registered");

        wrappedTokens[chainId] = newToken;

        emit WrappedTokenUpdated(chainId, old, newToken);
    }

    // ── ZK Verifier change timelock (48 hours) ─────────────────────────
    uint256 public constant VERIFIER_CHANGE_DELAY = 48 hours;

    struct PendingVerifierChange {
        address newVerifier;
        uint256 scheduledAt;
        bool    exists;
    }
    PendingVerifierChange public pendingVerifier;

    event ZKVerifierChangeScheduled(address indexed newVerifier, uint256 executeAfter);

    /// @notice Schedule a ZK verifier change with a 48-hour delay.
    function scheduleZKVerifierChange(address _verifier) external onlyOwner {
        require(_verifier != address(0), "BM: zero verifier");
        pendingVerifier = PendingVerifierChange(_verifier, block.timestamp, true);
        emit ZKVerifierChangeScheduled(_verifier, block.timestamp + VERIFIER_CHANGE_DELAY);
    }

    /// @notice Execute a previously scheduled ZK verifier change after the 48-hour delay.
    function executeZKVerifierChange() external onlyOwner {
        require(pendingVerifier.exists, "BM: no pending change");
        require(block.timestamp >= pendingVerifier.scheduledAt + VERIFIER_CHANGE_DELAY, "BM: delay not elapsed");
        address old = zkVerifier;
        zkVerifier = pendingVerifier.newVerifier;
        delete pendingVerifier;
        emit ZKVerifierUpdated(old, zkVerifier);
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
        require(newOwner != address(0), "BM: zero owner");
        owner = newOwner;
    }

    // ── Views ─────────────────────────────────────────────────────────

    function getBurn(bytes32 burnId) external view returns (
        address burner, uint256 amount, uint256 destChainId,
        string memory destRecipient, bytes32 commitment, uint256 timestamp
    ) {
        BurnRecord storage b = burns[burnId];
        return (b.burner, b.amount, b.destChainId,
                b.destRecipient, b.commitment, b.timestamp);
    }

    function getWrappedToken(uint256 chainId) external view returns (address) {
        return wrappedTokens[chainId];
    }

    function getSupportedChains() external view returns (uint256[] memory) {
        return supportedChainIds;
    }

    function getStats() external view returns (
        uint256 minted, uint256 burned, uint256 nonces,
        uint256 numSupportedChains, bool isPaused
    ) {
        return (totalMinted, totalBurned, burnNonce,
                supportedChainIds.length, paused);
    }

    function isMintProofProcessed(bytes32 proofHash) external view returns (bool) {
        return processedMintProofs[proofHash];
    }
}

// ── Interface ─────────────────────────────────────────────────────────

interface IWrappedToken {
    function mint(address to, uint256 amount, bytes32 proofHash) external;
    function burn(address from, uint256 amount) external;
}
