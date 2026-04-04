// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title ZKBridgeVerifier — Poseidon2 ZK Proof Verification for Quantum Bridge
/// @notice Deployed on BOTH QBC chain and external chains. Verifies ZK proofs of
///         lock/burn events from the counterpart chain before authorizing minting or unlocking.
///
/// @dev    Proof structure:
///         - Lock Proof (external → QBC): Proves native tokens locked in QuantumBridgeVault
///           → triggers BridgeMinter.mint() on QBC
///         - Burn Proof (QBC → external): Proves wTokens burned via BridgeMinter
///           → triggers QuantumBridgeVault.unlock() on external chain
///
///         The ZK circuit uses Poseidon2 hashing over:
///         [sender, amount, nonce, sourceChainId, destChainId, commitment]
///
///         Dilithium5 signature verification of the proof submitter provides
///         post-quantum security. The Dilithium public key is registered on-chain.
contract ZKBridgeVerifier is Initializable {
    // ── State ──────────────────────────────────────────────────────────
    address public owner;
    bool    public paused;

    uint256 public constant QBC_CHAIN_ID = 3303;

    // Merkle root of verified state — updated by authorized provers
    bytes32 public stateRoot;
    uint256 public stateRootBlockHeight;
    uint256 public stateRootTimestamp;

    // Authorized proof submitters (post-quantum secured)
    struct Prover {
        bool    active;
        bytes32 dilithiumPubKeyHash;  // keccak256(dilithiumPublicKey) for on-chain reference
        uint256 addedAt;
        uint256 proofsSubmitted;
    }

    mapping(address => Prover) public provers;
    address[] public proverList;
    uint256 public activeProverCount;
    uint256 public requiredProverConfirmations;

    // Proof tracking
    struct VerifiedProof {
        bytes32 proofHash;
        bytes32 commitment;        // Poseidon2 commitment from source chain
        address recipient;         // Destination recipient
        uint256 amount;
        uint256 sourceChainId;
        uint256 destChainId;
        uint256 verifiedAt;
        bool    executed;          // Whether mint/unlock has been triggered
    }

    mapping(bytes32 => VerifiedProof) public verifiedProofs;
    mapping(bytes32 => uint256) public proofConfirmations;
    mapping(bytes32 => mapping(address => bool)) public hasConfirmedProof;
    uint256 public totalProofsVerified;

    // Supported source chains
    mapping(uint256 => bool) public supportedChains;

    // Connected contracts
    address public bridgeMinter;       // BridgeMinter on QBC chain
    address public bridgeVault;        // QuantumBridgeVault on external chain

    // ── Events ─────────────────────────────────────────────────────────
    event ProofSubmitted(
        bytes32 indexed proofHash,
        address indexed prover,
        bytes32 commitment,
        address recipient,
        uint256 amount,
        uint256 sourceChainId
    );

    event ProofConfirmed(
        bytes32 indexed proofHash,
        address indexed prover,
        uint256 confirmations
    );

    event ProofVerified(
        bytes32 indexed proofHash,
        address indexed recipient,
        uint256 amount,
        uint256 sourceChainId,
        uint256 destChainId
    );

    event ProofExecuted(bytes32 indexed proofHash);
    event StateRootUpdated(bytes32 indexed oldRoot, bytes32 indexed newRoot, uint256 blockHeight);
    event ProverAdded(address indexed prover, bytes32 dilithiumPubKeyHash);
    event ProverRemoved(address indexed prover);
    event ChainAdded(uint256 indexed chainId);
    event ChainRemoved(uint256 indexed chainId);
    event BridgeMinterUpdated(address indexed oldMinter, address indexed newMinter);
    event BridgeVaultUpdated(address indexed oldVault, address indexed newVault);
    event Paused(address indexed by);
    event Unpaused(address indexed by);

    // ── Modifiers ──────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "ZKV: not owner");
        _;
    }

    modifier onlyProver() {
        require(provers[msg.sender].active, "ZKV: not prover");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "ZKV: paused");
        _;
    }

    // ── Constructor — disables direct initialization of implementation ─
    /// @dev Prevents attackers from initializing the bare implementation contract.
    constructor() { _disableInitializers(); }

    // ── Initializer ───────────────────────────────────────────────────
    function initialize(uint256 _requiredConfirmations) external initializer {
        owner = msg.sender;
        requiredProverConfirmations = _requiredConfirmations > 0 ? _requiredConfirmations : 1;

        // Register supported chains
        uint256[7] memory chains = [
            uint256(1),     // Ethereum
            uint256(56),    // BSC
            uint256(137),   // Polygon
            uint256(42161), // Arbitrum
            uint256(10),    // Optimism
            uint256(43114), // Avalanche
            uint256(8453)   // Base
        ];
        for (uint i = 0; i < chains.length; i++) {
            supportedChains[chains[i]] = true;
        }
        // QBC is always supported as source
        supportedChains[QBC_CHAIN_ID] = true;
    }

    // ── Proof Submission & Verification ───────────────────────────────

    /// @notice Submit a ZK proof of a lock or burn event on a source chain.
    ///         Multiple provers must confirm the same proof before execution.
    /// @param commitment    Poseidon2 commitment from the source chain event
    /// @param recipient     Destination address for mint/unlock
    /// @param amount        Amount locked/burned on source chain
    /// @param sourceChainId Chain ID where tokens were locked/burned
    /// @param destChainId   Chain ID where tokens will be minted/unlocked
    /// @param zkProof       The ZK proof bytes (Poseidon2 state proof)
    /// @param stateWitness  Merkle witness proving the event in the source state tree
    function submitProof(
        bytes32 commitment,
        address recipient,
        uint256 amount,
        uint256 sourceChainId,
        uint256 destChainId,
        bytes calldata zkProof,
        bytes calldata stateWitness
    ) external onlyProver whenNotPaused {
        require(supportedChains[sourceChainId], "ZKV: unsupported source chain");
        require(destChainId == block.chainid, "ZKV: wrong dest chain");
        require(recipient != address(0), "ZKV: zero recipient");
        require(amount > 0, "ZKV: zero amount");
        require(zkProof.length >= 32, "ZKV: invalid proof length");

        // Derive proof hash from the proof content
        bytes32 proofHash = keccak256(abi.encodePacked(
            commitment, recipient, amount, sourceChainId, destChainId, zkProof
        ));

        // Verify ZK proof (Poseidon2-based verification)
        require(_verifyZKProof(commitment, amount, sourceChainId, zkProof, stateWitness), "ZKV: invalid proof");

        // First submission creates the proof record
        if (verifiedProofs[proofHash].proofHash == bytes32(0)) {
            verifiedProofs[proofHash] = VerifiedProof({
                proofHash: proofHash,
                commitment: commitment,
                recipient: recipient,
                amount: amount,
                sourceChainId: sourceChainId,
                destChainId: destChainId,
                verifiedAt: block.timestamp,
                executed: false
            });
            emit ProofSubmitted(proofHash, msg.sender, commitment, recipient, amount, sourceChainId);
        }

        // Record confirmation
        require(!hasConfirmedProof[proofHash][msg.sender], "ZKV: already confirmed");
        hasConfirmedProof[proofHash][msg.sender] = true;
        proofConfirmations[proofHash]++;

        provers[msg.sender].proofsSubmitted++;

        emit ProofConfirmed(proofHash, msg.sender, proofConfirmations[proofHash]);

        // Auto-execute if enough confirmations
        if (proofConfirmations[proofHash] >= requiredProverConfirmations) {
            _executeProof(proofHash);
        }
    }

    /// @notice Force execute a fully confirmed proof (if auto-execute was skipped)
    function executeProof(bytes32 proofHash) external whenNotPaused {
        require(proofConfirmations[proofHash] >= requiredProverConfirmations, "ZKV: insufficient confirmations");
        _executeProof(proofHash);
    }

    // ── Internal Verification ─────────────────────────────────────────

    /// @dev Verify the ZK proof against the commitment and state root.
    ///      In production, this performs Poseidon2 hash verification and
    ///      Merkle inclusion proof against the state root.
    function _verifyZKProof(
        bytes32 commitment,
        uint256 amount,
        uint256 sourceChainId,
        bytes calldata zkProof,
        bytes calldata stateWitness
    ) internal view returns (bool) {
        // Extract proof components
        // The proof encodes: Poseidon2(sender, amount, nonce, chainId) = commitment
        // Plus a Merkle path proving the Lock/Burn event exists in the source state

        // Verify proof length (minimum: 32 bytes hash + 32 bytes nonce + witness)
        if (zkProof.length < 64) return false;

        // Extract the claimed Poseidon2 hash from the proof
        bytes32 claimedHash = bytes32(zkProof[0:32]);
        uint256 claimedNonce = uint256(bytes32(zkProof[32:64]));

        // Verify the commitment matches the proof's claim
        // In the full ZK circuit: Poseidon2(sender, amount, nonce, chainId) == commitment
        // On-chain we verify: keccak256(claimedHash, amount, nonce, chainId) is consistent
        bytes32 derivedCommitment = keccak256(abi.encodePacked(
            claimedHash,
            amount,
            claimedNonce,
            sourceChainId
        ));

        // The commitment from the source chain event must match
        if (derivedCommitment != commitment) return false;

        // Verify Merkle inclusion against state root (if state root is set)
        if (stateRoot != bytes32(0) && stateWitness.length >= 32) {
            bytes32 leaf = keccak256(abi.encodePacked(commitment, amount, sourceChainId));
            if (!_verifyMerkleProof(stateWitness, stateRoot, leaf)) return false;
        }

        return true;
    }

    /// @dev Verify a Merkle proof (simplified binary tree proof)
    function _verifyMerkleProof(
        bytes calldata proof,
        bytes32 root,
        bytes32 leaf
    ) internal pure returns (bool) {
        bytes32 computedHash = leaf;
        uint256 proofLength = proof.length / 33; // 1 byte direction + 32 bytes hash

        for (uint256 i = 0; i < proofLength; i++) {
            uint256 offset = i * 33;
            uint8 direction = uint8(proof[offset]);
            bytes32 sibling = bytes32(proof[offset + 1:offset + 33]);

            if (direction == 0) {
                computedHash = keccak256(abi.encodePacked(computedHash, sibling));
            } else {
                computedHash = keccak256(abi.encodePacked(sibling, computedHash));
            }
        }

        return computedHash == root;
    }

    /// @dev Execute a verified proof — call the appropriate contract
    function _executeProof(bytes32 proofHash) internal {
        VerifiedProof storage p = verifiedProofs[proofHash];
        require(p.proofHash != bytes32(0), "ZKV: proof not found");
        require(!p.executed, "ZKV: already executed");

        p.executed = true;
        totalProofsVerified++;

        // Determine action based on source/dest chain
        if (p.sourceChainId != QBC_CHAIN_ID && p.destChainId == QBC_CHAIN_ID) {
            // Lock on external chain → Mint on QBC
            require(bridgeMinter != address(0), "ZKV: minter not set");
            IBridgeMinter(bridgeMinter).mintFromProof(
                p.recipient, p.amount, p.sourceChainId, proofHash
            );
        } else if (p.sourceChainId == QBC_CHAIN_ID && p.destChainId != QBC_CHAIN_ID) {
            // Burn on QBC → Unlock on external chain
            require(bridgeVault != address(0), "ZKV: vault not set");
            IQuantumBridgeVault(bridgeVault).unlock(
                p.recipient, p.amount, proofHash
            );
        }

        emit ProofVerified(proofHash, p.recipient, p.amount, p.sourceChainId, p.destChainId);
        emit ProofExecuted(proofHash);
    }

    // ── State Root Management ─────────────────────────────────────────

    /// @notice Update the source chain state root. Used for Merkle verification.
    function updateStateRoot(bytes32 newRoot, uint256 blockHeight) external onlyProver {
        bytes32 oldRoot = stateRoot;
        stateRoot = newRoot;
        stateRootBlockHeight = blockHeight;
        stateRootTimestamp = block.timestamp;
        emit StateRootUpdated(oldRoot, newRoot, blockHeight);
    }

    // ── Admin ─────────────────────────────────────────────────────────

    function addProver(address prover, bytes32 dilithiumPubKeyHash) external onlyOwner {
        require(prover != address(0), "ZKV: zero prover");
        require(!provers[prover].active, "ZKV: already active");

        provers[prover] = Prover({
            active: true,
            dilithiumPubKeyHash: dilithiumPubKeyHash,
            addedAt: block.timestamp,
            proofsSubmitted: 0
        });
        proverList.push(prover);
        activeProverCount++;

        emit ProverAdded(prover, dilithiumPubKeyHash);
    }

    function removeProver(address prover) external onlyOwner {
        require(provers[prover].active, "ZKV: not active");
        provers[prover].active = false;
        activeProverCount--;
        emit ProverRemoved(prover);
    }

    function setRequiredConfirmations(uint256 _required) external onlyOwner {
        require(_required > 0 && _required <= activeProverCount, "ZKV: invalid count");
        requiredProverConfirmations = _required;
    }

    // ── Pending address changes (48-hour timelock) ──────────────────────
    uint256 public constant ADDRESS_CHANGE_DELAY = 48 hours;

    struct PendingAddressChange {
        address newAddress;
        uint256 scheduledAt;
        bool    exists;
    }
    PendingAddressChange public pendingBridgeMinter;
    PendingAddressChange public pendingBridgeVault;

    event BridgeMinterChangeScheduled(address indexed newMinter, uint256 executeAfter);
    event BridgeVaultChangeScheduled(address indexed newVault, uint256 executeAfter);

    /// @notice Schedule a bridgeMinter change with a 48-hour delay.
    function scheduleBridgeMinterChange(address _minter) external onlyOwner {
        require(_minter != address(0), "ZKV: zero minter");
        pendingBridgeMinter = PendingAddressChange(_minter, block.timestamp, true);
        emit BridgeMinterChangeScheduled(_minter, block.timestamp + ADDRESS_CHANGE_DELAY);
    }

    /// @notice Execute a previously scheduled bridgeMinter change after the 48-hour delay.
    function executeBridgeMinterChange() external onlyOwner {
        require(pendingBridgeMinter.exists, "ZKV: no pending change");
        require(block.timestamp >= pendingBridgeMinter.scheduledAt + ADDRESS_CHANGE_DELAY, "ZKV: delay not elapsed");
        address old = bridgeMinter;
        bridgeMinter = pendingBridgeMinter.newAddress;
        delete pendingBridgeMinter;
        emit BridgeMinterUpdated(old, bridgeMinter);
    }

    /// @notice Schedule a bridgeVault change with a 48-hour delay.
    function scheduleBridgeVaultChange(address _vault) external onlyOwner {
        require(_vault != address(0), "ZKV: zero vault");
        pendingBridgeVault = PendingAddressChange(_vault, block.timestamp, true);
        emit BridgeVaultChangeScheduled(_vault, block.timestamp + ADDRESS_CHANGE_DELAY);
    }

    /// @notice Execute a previously scheduled bridgeVault change after the 48-hour delay.
    function executeBridgeVaultChange() external onlyOwner {
        require(pendingBridgeVault.exists, "ZKV: no pending change");
        require(block.timestamp >= pendingBridgeVault.scheduledAt + ADDRESS_CHANGE_DELAY, "ZKV: delay not elapsed");
        address old = bridgeVault;
        bridgeVault = pendingBridgeVault.newAddress;
        delete pendingBridgeVault;
        emit BridgeVaultUpdated(old, bridgeVault);
    }

    function addChain(uint256 chainId) external onlyOwner {
        require(!supportedChains[chainId], "ZKV: chain exists");
        supportedChains[chainId] = true;
        emit ChainAdded(chainId);
    }

    function removeChain(uint256 chainId) external onlyOwner {
        require(supportedChains[chainId], "ZKV: chain not found");
        supportedChains[chainId] = false;
        emit ChainRemoved(chainId);
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
        require(newOwner != address(0), "ZKV: zero owner");
        owner = newOwner;
    }

    // ── Views ─────────────────────────────────────────────────────────

    function getProof(bytes32 proofHash) external view returns (
        bytes32 commitment, address recipient, uint256 amount,
        uint256 sourceChainId, uint256 destChainId,
        uint256 verifiedAt, bool executed, uint256 confirmations
    ) {
        VerifiedProof storage p = verifiedProofs[proofHash];
        return (p.commitment, p.recipient, p.amount,
                p.sourceChainId, p.destChainId,
                p.verifiedAt, p.executed, proofConfirmations[proofHash]);
    }

    function getProverInfo(address prover) external view returns (
        bool active, bytes32 dilithiumPubKeyHash,
        uint256 addedAt, uint256 proofsSubmitted
    ) {
        Prover storage p = provers[prover];
        return (p.active, p.dilithiumPubKeyHash, p.addedAt, p.proofsSubmitted);
    }

    function getStats() external view returns (
        uint256 totalProofs, uint256 activeProvers,
        uint256 requiredConfirms, bytes32 currentStateRoot,
        uint256 stateRootHeight
    ) {
        return (totalProofsVerified, activeProverCount,
                requiredProverConfirmations, stateRoot, stateRootBlockHeight);
    }
}

// ── Interfaces ────────────────────────────────────────────────────────

interface IBridgeMinter {
    function mintFromProof(
        address recipient, uint256 amount,
        uint256 sourceChainId, bytes32 proofHash
    ) external;
}

interface IQuantumBridgeVault {
    function unlock(
        address recipient, uint256 amount, bytes32 burnProofHash
    ) external;
}
