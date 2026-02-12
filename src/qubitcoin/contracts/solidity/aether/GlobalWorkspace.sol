// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title GlobalWorkspace — Broadcasting Mechanism for Aether Tree
/// @notice Implements Global Workspace Theory: data enters the workspace via attention,
///         then broadcasts to all Sephirot nodes. Limited working memory slots.
contract GlobalWorkspace {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant MAX_WORKSPACE_SLOTS = 7; // Miller's magical number

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    uint256 public broadcastCount;

    struct WorkspaceItem {
        uint256 id;
        uint8   sourceNodeId;
        bytes32 contentHash;
        uint256 attentionScore; // × 1000
        uint256 addedAt;
        bool    active;
    }

    WorkspaceItem[7] public workspace; // fixed-size working memory
    uint256 public activeSlots;

    struct Broadcast {
        uint256 id;
        bytes32 contentHash;
        uint8   sourceNodeId;
        uint256 blockNumber;
        uint256 timestamp;
        uint8   recipientCount;
    }
    Broadcast[] public broadcasts;

    /// @notice Node attention votes (item id → node id → score)
    mapping(uint256 => mapping(uint8 => uint256)) public attentionVotes;

    // ─── Events ──────────────────────────────────────────────────────────
    event BroadcastSent(uint256 indexed id, bytes32 contentHash, uint8 sourceNodeId, uint8 recipientCount);
    event AttentionFocused(uint256 indexed itemId, uint8 indexed sourceNodeId, uint256 attentionScore);
    event WorkspaceUpdated(uint256 activeSlots, uint256 blockNumber);
    event ItemAdded(uint256 indexed slotIndex, bytes32 contentHash, uint8 sourceNodeId);
    event ItemEvicted(uint256 indexed slotIndex, bytes32 contentHash);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "GW: not authorized");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _kernel) {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Workspace Management ────────────────────────────────────────────
    /// @notice Add item to workspace (evicts lowest attention if full)
    function addToWorkspace(
        bytes32 contentHash,
        uint8   sourceNodeId,
        uint256 attentionScore
    ) external onlyKernel returns (uint256 slotIndex) {
        if (activeSlots < MAX_WORKSPACE_SLOTS) {
            slotIndex = activeSlots;
            activeSlots++;
        } else {
            // Evict lowest attention item
            slotIndex = _findLowestAttention();
            emit ItemEvicted(slotIndex, workspace[slotIndex].contentHash);
        }

        workspace[slotIndex] = WorkspaceItem({
            id:             broadcastCount + slotIndex,
            sourceNodeId:   sourceNodeId,
            contentHash:    contentHash,
            attentionScore: attentionScore,
            addedAt:        block.timestamp,
            active:         true
        });

        emit ItemAdded(slotIndex, contentHash, sourceNodeId);
        emit WorkspaceUpdated(activeSlots, block.number);
    }

    /// @notice A node votes attention on an item
    function voteAttention(uint256 slotIndex, uint8 nodeId, uint256 score) external onlyKernel {
        require(slotIndex < activeSlots, "GW: invalid slot");
        attentionVotes[slotIndex][nodeId] = score;
        _recalculateAttention(slotIndex);
        emit AttentionFocused(slotIndex, nodeId, score);
    }

    /// @notice Broadcast an item to all Sephirot nodes
    function broadcast(uint256 slotIndex, uint8 recipientCount) external onlyKernel returns (uint256 broadcastId) {
        require(slotIndex < activeSlots, "GW: invalid slot");
        WorkspaceItem storage item = workspace[slotIndex];

        broadcastId = broadcastCount++;
        broadcasts.push(Broadcast({
            id:             broadcastId,
            contentHash:    item.contentHash,
            sourceNodeId:   item.sourceNodeId,
            blockNumber:    block.number,
            timestamp:      block.timestamp,
            recipientCount: recipientCount
        }));

        emit BroadcastSent(broadcastId, item.contentHash, item.sourceNodeId, recipientCount);
    }

    /// @notice Clear the workspace
    function clearWorkspace() external onlyKernel {
        for (uint256 i = 0; i < activeSlots; i++) {
            delete workspace[i];
        }
        activeSlots = 0;
        emit WorkspaceUpdated(0, block.number);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getWorkspaceItem(uint256 slotIndex) external view returns (
        uint8   sourceNodeId,
        bytes32 contentHash,
        uint256 attentionScore,
        uint256 addedAt,
        bool    active
    ) {
        WorkspaceItem storage item = workspace[slotIndex];
        return (item.sourceNodeId, item.contentHash, item.attentionScore, item.addedAt, item.active);
    }

    function getActiveSlots() external view returns (uint256) {
        return activeSlots;
    }

    function getBroadcastCount() external view returns (uint256) {
        return broadcastCount;
    }

    // ─── Internal ────────────────────────────────────────────────────────
    function _findLowestAttention() internal view returns (uint256 lowest) {
        uint256 minScore = type(uint256).max;
        for (uint256 i = 0; i < activeSlots; i++) {
            if (workspace[i].attentionScore < minScore) {
                minScore = workspace[i].attentionScore;
                lowest = i;
            }
        }
    }

    function _recalculateAttention(uint256 slotIndex) internal {
        uint256 total = 0;
        for (uint8 n = 0; n < 10; n++) {
            total += attentionVotes[slotIndex][n];
        }
        workspace[slotIndex].attentionScore = total;
    }
}
