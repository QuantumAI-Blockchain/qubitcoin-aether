// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title EmergencyShutdown — Kill Switch for Aether Tree
/// @notice Multi-sig emergency shutdown (3-of-5 to halt, 4-of-5 to resume).
///         Halts all Aether Tree operations when activated.
contract EmergencyShutdown is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant SHUTDOWN_THRESHOLD = 3;  // 3-of-5 to shutdown
    uint256 public constant RESUME_THRESHOLD   = 4;  // 4-of-5 to resume
    uint256 public constant RESUME_COOLDOWN    = 1 hours; // Minimum time before resume can execute

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    bool    public isShutdown;
    uint256 public shutdownTimestamp;

    address[5] public signers;
    uint256    public signerCount;

    /// @notice Shutdown / resume action tracking
    struct Action {
        bytes32 actionType; // "shutdown" or "resume"
        uint256 signCount;
        uint256 timestamp;
        bool    executed;
    }

    uint256 public currentActionId;
    mapping(uint256 => Action) public actions;
    mapping(uint256 => mapping(address => bool)) public hasSigned;

    // ─── Events ──────────────────────────────────────────────────────────
    event ShutdownInitiated(uint256 indexed actionId, address indexed initiator);
    event ShutdownSigned(uint256 indexed actionId, address indexed signer, uint256 signCount);
    event ShutdownExecuted(uint256 indexed actionId, uint256 timestamp, uint256 signerCount);
    event ResumeInitiated(uint256 indexed actionId, address indexed initiator);
    event ResumeSigned(uint256 indexed actionId, address indexed signer, uint256 signCount);
    event SystemResumed(uint256 indexed actionId, uint256 timestamp, uint256 signerCount);
    event SignerAdded(address indexed signer, uint256 index);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Shutdown: not owner");
        _;
    }

    modifier onlySigner() {
        require(_isSigner(msg.sender), "Shutdown: not signer");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Signer Management ───────────────────────────────────────────────
    function addSigner(address signer) external onlyOwner {
        require(signerCount < 5, "Shutdown: max signers reached");
        require(signer != address(0), "Shutdown: zero address");
        require(!_isSigner(signer), "Shutdown: duplicate signer");
        signers[signerCount] = signer;
        emit SignerAdded(signer, signerCount);
        signerCount++;
    }

    // ─── Shutdown (3-of-5) ───────────────────────────────────────────────
    function initiateShutdown() external onlySigner returns (uint256 actionId) {
        require(!isShutdown, "Shutdown: already shutdown");

        actionId = ++currentActionId;
        actions[actionId] = Action({
            actionType: keccak256("shutdown"),
            signCount:  1,
            timestamp:  block.timestamp,
            executed:   false
        });
        hasSigned[actionId][msg.sender] = true;

        emit ShutdownInitiated(actionId, msg.sender);
        emit ShutdownSigned(actionId, msg.sender, 1);

        if (1 >= SHUTDOWN_THRESHOLD) {
            _executeShutdown(actionId);
        }
    }

    function signShutdown(uint256 actionId) external onlySigner {
        require(!hasSigned[actionId][msg.sender], "Shutdown: already signed");
        require(!actions[actionId].executed, "Shutdown: already executed");
        require(actions[actionId].actionType == keccak256("shutdown"), "Shutdown: wrong action");

        hasSigned[actionId][msg.sender] = true;
        actions[actionId].signCount++;

        emit ShutdownSigned(actionId, msg.sender, actions[actionId].signCount);

        if (actions[actionId].signCount >= SHUTDOWN_THRESHOLD) {
            _executeShutdown(actionId);
        }
    }

    // ─── Resume (4-of-5) ─────────────────────────────────────────────────
    function initiateResume() external onlySigner returns (uint256 actionId) {
        require(isShutdown, "Shutdown: not shutdown");

        actionId = ++currentActionId;
        actions[actionId] = Action({
            actionType: keccak256("resume"),
            signCount:  1,
            timestamp:  block.timestamp,
            executed:   false
        });
        hasSigned[actionId][msg.sender] = true;

        emit ResumeInitiated(actionId, msg.sender);
        emit ResumeSigned(actionId, msg.sender, 1);
    }

    function signResume(uint256 actionId) external onlySigner {
        require(!hasSigned[actionId][msg.sender], "Shutdown: already signed");
        require(!actions[actionId].executed, "Shutdown: already executed");
        require(actions[actionId].actionType == keccak256("resume"), "Shutdown: wrong action");

        hasSigned[actionId][msg.sender] = true;
        actions[actionId].signCount++;

        emit ResumeSigned(actionId, msg.sender, actions[actionId].signCount);

        if (actions[actionId].signCount >= RESUME_THRESHOLD) {
            // Enforce cooldown — prevent hasty resume before investigation completes
            require(
                block.timestamp >= shutdownTimestamp + RESUME_COOLDOWN,
                "Shutdown: resume cooldown not elapsed"
            );
            actions[actionId].executed = true;
            isShutdown = false;
            emit SystemResumed(actionId, block.timestamp, actions[actionId].signCount);
        }
    }

    // ─── Internal ────────────────────────────────────────────────────────
    function _executeShutdown(uint256 actionId) internal {
        actions[actionId].executed = true;
        isShutdown = true;
        shutdownTimestamp = block.timestamp;
        emit ShutdownExecuted(actionId, block.timestamp, actions[actionId].signCount);
    }

    function _isSigner(address addr) internal view returns (bool) {
        for (uint256 i = 0; i < signerCount; i++) {
            if (signers[i] == addr) return true;
        }
        return false;
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getStatus() external view returns (bool shutdown_, uint256 shutdownAt, uint256 signers_) {
        return (isShutdown, shutdownTimestamp, signerCount);
    }
}
