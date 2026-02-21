// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title MessageBus — CSF Transport Layer for Inter-Node Messaging
/// @notice Routes messages between Sephirot nodes following Tree of Life topology.
///         Messages carry QBC fees for priority. Inspired by cerebrospinal fluid circulation.
contract MessageBus {
    // ─── Constants ───────────────────────────────────────────────────────
    bytes32 public constant MSG_REASONING  = keccak256("REASONING");
    bytes32 public constant MSG_DATA       = keccak256("DATA");
    bytes32 public constant MSG_SYNC       = keccak256("SYNC");
    bytes32 public constant MSG_EMERGENCY  = keccak256("EMERGENCY");

    uint256 public constant MAX_PAYLOAD_SIZE = 4096;  // 4 KB max payload
    uint256 public constant MAX_INBOX_SIZE   = 1000;  // max messages per node inbox

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    uint256 public messageCount;
    uint256 public baseFee; // minimum QBC fee per message

    struct Message {
        uint256 id;
        uint8   fromNodeId;
        uint8   toNodeId;
        bytes32 messageType;
        bytes   payload;
        uint256 fee;         // QBC attached for priority
        uint256 timestamp;
        bool    delivered;
    }

    /// @notice Message queue per node (nodeId → message ids)
    mapping(uint8 => uint256[]) public nodeInbox;
    mapping(uint256 => Message)  public messages;

    /// @notice Tree of Life adjacency (nodeId → allowed target nodes)
    mapping(uint8 => mapping(uint8 => bool)) public topology;

    // ─── Events ──────────────────────────────────────────────────────────
    event MessageSent(uint256 indexed id, uint8 indexed from, uint8 indexed to, bytes32 msgType, uint256 fee);
    event MessageDelivered(uint256 indexed id, uint8 indexed toNodeId, uint256 timestamp);
    event MessageFailed(uint256 indexed id, string reason);
    event TopologyUpdated(uint8 indexed from, uint8 indexed to, bool connected);
    event BaseFeeUpdated(uint256 oldFee, uint256 newFee);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "MessageBus: not owner");
        _;
    }

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "MessageBus: not authorized");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _kernel, uint256 _baseFee) {
        owner   = msg.sender;
        kernel  = _kernel;
        baseFee = _baseFee;
    }

    // ─── Topology Setup ──────────────────────────────────────────────────
    /// @notice Set Tree of Life routing topology
    function setTopology(uint8 from, uint8 to, bool connected) external onlyOwner {
        topology[from][to] = connected;
        emit TopologyUpdated(from, to, connected);
    }

    /// @notice Initialize default Tree of Life topology (Keter → Malkuth)
    function initializeDefaultTopology() external onlyOwner {
        // Keter(0) → Chochmah(1), Binah(2)
        topology[0][1] = true; topology[0][2] = true;
        // Chochmah(1) → Chesed(3), Tiferet(5)
        topology[1][3] = true; topology[1][5] = true;
        // Binah(2) → Gevurah(4), Tiferet(5)
        topology[2][4] = true; topology[2][5] = true;
        // Chesed(3) → Netzach(6), Tiferet(5)
        topology[3][6] = true; topology[3][5] = true;
        // Gevurah(4) → Hod(7), Tiferet(5)
        topology[4][7] = true; topology[4][5] = true;
        // Tiferet(5) → Netzach(6), Hod(7), Yesod(8)
        topology[5][6] = true; topology[5][7] = true; topology[5][8] = true;
        // Netzach(6) → Yesod(8)
        topology[6][8] = true;
        // Hod(7) → Yesod(8)
        topology[7][8] = true;
        // Yesod(8) → Malkuth(9)
        topology[8][9] = true;
        // Bidirectional (messages can flow up too)
        topology[1][0] = true; topology[2][0] = true;
        topology[5][0] = true; topology[9][8] = true;
        topology[8][5] = true;
    }

    // ─── Messaging ───────────────────────────────────────────────────────
    /// @notice Send a message between Sephirot nodes
    function sendMessage(
        uint8   fromNodeId,
        uint8   toNodeId,
        bytes32 messageType,
        bytes   calldata payload,
        uint256 fee
    ) external onlyKernel returns (uint256 msgId) {
        require(fromNodeId < 10 && toNodeId < 10, "MessageBus: invalid node");
        require(fee >= baseFee || messageType == MSG_EMERGENCY, "MessageBus: fee too low");
        require(payload.length <= MAX_PAYLOAD_SIZE, "MessageBus: payload too large");
        require(nodeInbox[toNodeId].length < MAX_INBOX_SIZE, "MessageBus: inbox full");

        msgId = ++messageCount;
        messages[msgId] = Message({
            id:          msgId,
            fromNodeId:  fromNodeId,
            toNodeId:    toNodeId,
            messageType: messageType,
            payload:     payload,
            fee:         fee,
            timestamp:   block.timestamp,
            delivered:   false
        });

        nodeInbox[toNodeId].push(msgId);
        emit MessageSent(msgId, fromNodeId, toNodeId, messageType, fee);
    }

    /// @notice Mark a message as delivered
    function markDelivered(uint256 msgId) external onlyKernel {
        require(messages[msgId].id == msgId, "MessageBus: not found");
        require(!messages[msgId].delivered, "MessageBus: already delivered");
        messages[msgId].delivered = true;
        emit MessageDelivered(msgId, messages[msgId].toNodeId, block.timestamp);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getInboxSize(uint8 nodeId) external view returns (uint256) {
        return nodeInbox[nodeId].length;
    }

    function getMessage(uint256 msgId) external view returns (
        uint8   fromNodeId,
        uint8   toNodeId,
        bytes32 messageType,
        uint256 fee,
        uint256 timestamp,
        bool    delivered
    ) {
        Message storage m = messages[msgId];
        return (m.fromNodeId, m.toNodeId, m.messageType, m.fee, m.timestamp, m.delivered);
    }

    function isRouteAllowed(uint8 from, uint8 to) external view returns (bool) {
        return topology[from][to];
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setBaseFee(uint256 newFee) external onlyOwner {
        emit BaseFeeUpdated(baseFee, newFee);
        baseFee = newFee;
    }
}
