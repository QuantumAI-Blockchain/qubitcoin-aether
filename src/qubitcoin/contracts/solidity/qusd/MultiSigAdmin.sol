// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title MultiSigAdmin — Multi-Signature Admin for QUSD Critical Functions
/// @notice Requires M-of-N signer approval before executing admin actions.
///         Default: 3-of-5 signers, 7-day action expiry. Configurable threshold.
///         QUSD contracts inherit the `onlyMultiSig` modifier to gate admin functions.
/// @dev    Actions are proposed by any signer, approved by other signers, and executed
///         once the threshold is met. Expired actions cannot be executed.
contract MultiSigAdmin is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant MIN_SIGNERS   = 2;
    uint256 public constant MAX_SIGNERS   = 10;
    uint256 public constant MIN_THRESHOLD = 2;
    uint256 public constant MAX_EXPIRY    = 30 days;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner; // deployer, can bootstrap initial signers

    /// @notice Ordered list of authorized signers
    address[] public signers;
    mapping(address => bool) public isSigner;

    /// @notice Number of approvals required to execute an action
    uint256 public threshold;

    /// @notice Time after which a proposed action expires (default 7 days)
    uint256 public actionExpiry;

    /// @notice Action tracking
    struct Action {
        bytes32  actionHash;
        string   description;
        address  proposer;
        uint256  approvalCount;
        uint256  proposedAt;
        bool     executed;
        bool     canceled;
    }

    /// @notice All proposed actions (actionHash → Action)
    mapping(bytes32 => Action) public actions;
    /// @notice Track which signers have approved each action
    mapping(bytes32 => mapping(address => bool)) public approvals;
    /// @notice Ordered list of all action hashes for enumeration
    bytes32[] public actionHashes;

    uint256 public totalProposed;
    uint256 public totalExecuted;
    uint256 public totalCanceled;

    // ─── Events ──────────────────────────────────────────────────────────
    event ActionProposed(bytes32 indexed actionHash, address indexed proposer, string description);
    event ActionApproved(bytes32 indexed actionHash, address indexed signer, uint256 approvalCount, uint256 threshold);
    event ActionExecuted(bytes32 indexed actionHash, address indexed executor, uint256 approvalCount);
    event ActionCanceled(bytes32 indexed actionHash, address indexed canceledBy);
    event SignerAdded(address indexed signer, uint256 newSignerCount);
    event SignerRemoved(address indexed signer, uint256 newSignerCount);
    event ThresholdUpdated(uint256 oldThreshold, uint256 newThreshold);
    event ExpiryUpdated(uint256 oldExpiry, uint256 newExpiry);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "MultiSig: not owner");
        _;
    }

    modifier onlySigner() {
        require(isSigner[msg.sender], "MultiSig: not signer");
        _;
    }

    /// @notice Modifier for QUSD contracts to use — requires the caller to be this contract
    ///         (i.e., the action was executed through the multi-sig approval flow).
    ///         QUSD contracts should set their owner to this MultiSigAdmin address,
    ///         then use `require(msg.sender == multiSigAdmin)` in their admin functions.
    modifier onlyMultiSig() {
        require(msg.sender == address(this), "MultiSig: not executed via multisig");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    /// @param _signers       Initial list of signer addresses (2-10)
    /// @param _threshold     Number of approvals required (2 <= threshold <= signers.length)
    /// @param _actionExpiry  Seconds until a proposed action expires (default: 604800 = 7 days)
    function initialize(
        address[] calldata _signers,
        uint256 _threshold,
        uint256 _actionExpiry
    ) external initializer {
        require(_signers.length >= MIN_SIGNERS, "MultiSig: need >= 2 signers");
        require(_signers.length <= MAX_SIGNERS, "MultiSig: need <= 10 signers");
        require(_threshold >= MIN_THRESHOLD, "MultiSig: threshold >= 2");
        require(_threshold <= _signers.length, "MultiSig: threshold <= signers");
        require(_actionExpiry > 0 && _actionExpiry <= MAX_EXPIRY, "MultiSig: invalid expiry");

        owner       = msg.sender;
        threshold   = _threshold;
        actionExpiry = _actionExpiry;

        for (uint256 i = 0; i < _signers.length; i++) {
            address signer = _signers[i];
            require(signer != address(0), "MultiSig: zero signer");
            require(!isSigner[signer], "MultiSig: duplicate signer");
            signers.push(signer);
            isSigner[signer] = true;
        }
    }

    // ─── Action Lifecycle ───────────────────────────────────────────────

    /// @notice Propose a new action. Any signer can propose.
    /// @param actionHash   Unique hash identifying the action (e.g., keccak256 of function call)
    /// @param description  Human-readable description of what this action does
    function proposeAction(bytes32 actionHash, string calldata description) external onlySigner {
        require(actionHash != bytes32(0), "MultiSig: zero hash");
        require(actions[actionHash].proposedAt == 0, "MultiSig: action exists");

        actions[actionHash] = Action({
            actionHash:    actionHash,
            description:   description,
            proposer:      msg.sender,
            approvalCount: 1,
            proposedAt:    block.timestamp,
            executed:       false,
            canceled:       false
        });
        approvals[actionHash][msg.sender] = true;
        actionHashes.push(actionHash);
        totalProposed++;

        emit ActionProposed(actionHash, msg.sender, description);
        emit ActionApproved(actionHash, msg.sender, 1, threshold);
    }

    /// @notice Approve a pending action. Each signer can approve once.
    /// @param actionHash The action to approve
    function approveAction(bytes32 actionHash) external onlySigner {
        Action storage action = actions[actionHash];
        require(action.proposedAt > 0, "MultiSig: action not found");
        require(!action.executed, "MultiSig: already executed");
        require(!action.canceled, "MultiSig: action canceled");
        require(!_isExpired(action), "MultiSig: action expired");
        require(!approvals[actionHash][msg.sender], "MultiSig: already approved");

        approvals[actionHash][msg.sender] = true;
        action.approvalCount++;

        emit ActionApproved(actionHash, msg.sender, action.approvalCount, threshold);
    }

    /// @notice Execute an action once the approval threshold is met.
    ///         This marks the action as executed. The calling contract should check
    ///         the action hash to verify authorization.
    /// @param actionHash The action to execute
    function executeAction(bytes32 actionHash) external onlySigner {
        Action storage action = actions[actionHash];
        require(action.proposedAt > 0, "MultiSig: action not found");
        require(!action.executed, "MultiSig: already executed");
        require(!action.canceled, "MultiSig: action canceled");
        require(!_isExpired(action), "MultiSig: action expired");
        require(action.approvalCount >= threshold, "MultiSig: insufficient approvals");

        action.executed = true;
        totalExecuted++;

        emit ActionExecuted(actionHash, msg.sender, action.approvalCount);
    }

    /// @notice Cancel a pending action. Only the proposer or owner can cancel.
    /// @param actionHash The action to cancel
    function cancelAction(bytes32 actionHash) external {
        Action storage action = actions[actionHash];
        require(action.proposedAt > 0, "MultiSig: action not found");
        require(!action.executed, "MultiSig: already executed");
        require(!action.canceled, "MultiSig: already canceled");
        require(
            msg.sender == action.proposer || msg.sender == owner,
            "MultiSig: not proposer or owner"
        );

        action.canceled = true;
        totalCanceled++;

        emit ActionCanceled(actionHash, msg.sender);
    }

    // ─── Signer Management (requires multi-sig) ────────────────────────

    /// @notice Add a new signer. Must be called after multi-sig approval of the corresponding action.
    /// @param newSigner Address to add as a signer
    /// @param actionHash The pre-approved action hash for this signer addition
    function addSigner(address newSigner, bytes32 actionHash) external onlySigner {
        _requireExecuted(actionHash);
        require(newSigner != address(0), "MultiSig: zero address");
        require(!isSigner[newSigner], "MultiSig: already signer");
        require(signers.length < MAX_SIGNERS, "MultiSig: max signers reached");

        signers.push(newSigner);
        isSigner[newSigner] = true;

        emit SignerAdded(newSigner, signers.length);
    }

    /// @notice Remove an existing signer. Must be called after multi-sig approval.
    /// @param signer Address to remove
    /// @param actionHash The pre-approved action hash for this signer removal
    function removeSigner(address signer, bytes32 actionHash) external onlySigner {
        _requireExecuted(actionHash);
        require(isSigner[signer], "MultiSig: not a signer");
        require(signers.length - 1 >= threshold, "MultiSig: would break threshold");
        require(signers.length - 1 >= MIN_SIGNERS, "MultiSig: need >= 2 signers");

        isSigner[signer] = false;

        // Remove from array by swapping with last element
        for (uint256 i = 0; i < signers.length; i++) {
            if (signers[i] == signer) {
                signers[i] = signers[signers.length - 1];
                signers.pop();
                break;
            }
        }

        emit SignerRemoved(signer, signers.length);
    }

    /// @notice Update the approval threshold. Must be called after multi-sig approval.
    /// @param newThreshold New number of required approvals
    /// @param actionHash The pre-approved action hash for this threshold change
    function setThreshold(uint256 newThreshold, bytes32 actionHash) external onlySigner {
        _requireExecuted(actionHash);
        require(newThreshold >= MIN_THRESHOLD, "MultiSig: threshold >= 2");
        require(newThreshold <= signers.length, "MultiSig: threshold <= signers");

        uint256 oldThreshold = threshold;
        threshold = newThreshold;

        emit ThresholdUpdated(oldThreshold, newThreshold);
    }

    /// @notice Update the action expiry duration. Must be called after multi-sig approval.
    /// @param newExpiry New expiry duration in seconds
    /// @param actionHash The pre-approved action hash for this expiry change
    function setExpiry(uint256 newExpiry, bytes32 actionHash) external onlySigner {
        _requireExecuted(actionHash);
        require(newExpiry > 0 && newExpiry <= MAX_EXPIRY, "MultiSig: invalid expiry");

        uint256 oldExpiry = actionExpiry;
        actionExpiry = newExpiry;

        emit ExpiryUpdated(oldExpiry, newExpiry);
    }

    // ─── Queries ────────────────────────────────────────────────────────

    /// @notice Check if an action has been executed (for external contracts to verify)
    /// @param actionHash The action hash to check
    /// @return True if the action has been proposed, approved by threshold, and executed
    function isActionExecuted(bytes32 actionHash) external view returns (bool) {
        return actions[actionHash].executed;
    }

    /// @notice Check if an action is still pending (proposed, not expired, not executed/canceled)
    /// @param actionHash The action hash to check
    /// @return True if the action can still be approved/executed
    function isActionPending(bytes32 actionHash) external view returns (bool) {
        Action storage action = actions[actionHash];
        return action.proposedAt > 0
            && !action.executed
            && !action.canceled
            && !_isExpired(action);
    }

    /// @notice Get full action details
    function getAction(bytes32 actionHash) external view returns (
        address  proposer,
        string   memory description,
        uint256  approvalCount,
        uint256  proposedAt,
        bool     executed,
        bool     canceled,
        bool     expired
    ) {
        Action storage a = actions[actionHash];
        return (
            a.proposer,
            a.description,
            a.approvalCount,
            a.proposedAt,
            a.executed,
            a.canceled,
            _isExpired(a)
        );
    }

    /// @notice Check if a specific signer has approved an action
    function hasApproved(bytes32 actionHash, address signer) external view returns (bool) {
        return approvals[actionHash][signer];
    }

    /// @notice Get the current signer list
    function getSigners() external view returns (address[] memory) {
        return signers;
    }

    /// @notice Get the total number of proposed actions
    function getActionCount() external view returns (uint256) {
        return actionHashes.length;
    }

    /// @notice Get multi-sig status summary
    function getStatus() external view returns (
        uint256 signerCount,
        uint256 threshold_,
        uint256 expiry,
        uint256 proposed,
        uint256 executed,
        uint256 canceled
    ) {
        return (signers.length, threshold, actionExpiry, totalProposed, totalExecuted, totalCanceled);
    }

    // ─── Internal ───────────────────────────────────────────────────────

    /// @dev Check if an action has expired
    function _isExpired(Action storage action) internal view returns (bool) {
        if (action.proposedAt == 0) return false;
        return block.timestamp > action.proposedAt + actionExpiry;
    }

    /// @dev Require that an action has been executed (for signer/threshold changes)
    function _requireExecuted(bytes32 actionHash) internal view {
        require(actions[actionHash].executed, "MultiSig: action not executed");
    }
}
