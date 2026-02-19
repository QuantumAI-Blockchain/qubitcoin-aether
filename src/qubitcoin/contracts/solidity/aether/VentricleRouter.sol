// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title VentricleRouter — On-Chain CSF Routing with Backpressure and Entanglement
/// @notice Extends MessageBus with ventricle-style load balancing, backpressure detection,
///         and quantum-entangled shortcuts between SUSY-paired Sephirot nodes.
///         Biological model: CSF circulation through brain ventricles with pressure regulation.
contract VentricleRouter {
    // ─── Constants ───────────────────────────────────────────────────────
    uint8  public constant NUM_NODES = 10;
    uint256 public constant MAX_PRESSURE = 50;
    uint256 public constant BACKPRESSURE_THRESHOLD_BPS = 8000; // 80% in basis points
    uint256 public constant PRIORITY_HALVING_FACTOR = 2;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public messageBus;
    uint256 public totalRouted;
    uint256 public totalBackpressureEvents;
    uint256 public totalEntangledDeliveries;

    /// @notice Per-node queue pressure (pending message count)
    mapping(uint8 => uint256) public nodePressure;

    /// @notice SUSY entangled pairs (bidirectional lookup)
    mapping(uint8 => uint8)   public entangledPartner;
    mapping(uint8 => bool)    public hasEntangledPartner;

    /// @notice Routing heuristic: preferred next-hop per (source, destination)
    mapping(uint8 => mapping(uint8 => uint8)) public routingTable;
    mapping(uint8 => mapping(uint8 => bool))  public routeExists;

    struct RouteResult {
        uint8   nextHop;
        uint256 adjustedPriority;
        bool    entangled;
        bool    backpressureApplied;
    }

    // ─── Events ──────────────────────────────────────────────────────────
    event MessageRouted(uint8 indexed from, uint8 indexed to, uint8 nextHop, uint256 priority, bool entangled);
    event BackpressureApplied(uint8 indexed node, uint256 pressure, uint256 originalPriority, uint256 adjustedPriority);
    event EntangledDelivery(uint8 indexed nodeA, uint8 indexed nodeB, uint256 timestamp);
    event PressureUpdated(uint8 indexed node, uint256 pressure);
    event EntangledPairRegistered(uint8 indexed expansion, uint8 indexed constraint);
    event RoutingTableUpdated(uint8 indexed from, uint8 indexed to, uint8 nextHop);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "VentricleRouter: not owner");
        _;
    }

    modifier onlyAuthorized() {
        require(msg.sender == owner || msg.sender == messageBus, "VentricleRouter: not authorized");
        _;
    }

    modifier validNode(uint8 nodeId) {
        require(nodeId < NUM_NODES, "VentricleRouter: invalid node");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _messageBus) {
        owner = msg.sender;
        messageBus = _messageBus;
    }

    // ─── SUSY Entanglement Setup ─────────────────────────────────────────
    /// @notice Register a SUSY entangled pair (bidirectional instant messaging)
    /// @param expansion  The expansion node (e.g., Chesed=3)
    /// @param constraint The constraint node (e.g., Gevurah=4)
    function registerEntangledPair(uint8 expansion, uint8 constraint)
        external onlyOwner validNode(expansion) validNode(constraint)
    {
        require(expansion != constraint, "VentricleRouter: cannot pair with self");
        entangledPartner[expansion] = constraint;
        entangledPartner[constraint] = expansion;
        hasEntangledPartner[expansion] = true;
        hasEntangledPartner[constraint] = true;
        emit EntangledPairRegistered(expansion, constraint);
    }

    /// @notice Initialize default SUSY pairs from whitepaper
    function initializeDefaultPairs() external onlyOwner {
        // Chesed(3) / Gevurah(4) — Creativity vs Safety
        _setPair(3, 4);
        // Chochmah(1) / Binah(2) — Intuition vs Logic
        _setPair(1, 2);
        // Netzach(6) / Hod(7) — Learning vs Communication
        _setPair(6, 7);
    }

    function _setPair(uint8 a, uint8 b) internal {
        entangledPartner[a] = b;
        entangledPartner[b] = a;
        hasEntangledPartner[a] = true;
        hasEntangledPartner[b] = true;
        emit EntangledPairRegistered(a, b);
    }

    // ─── Routing Table Setup ─────────────────────────────────────────────
    /// @notice Set the preferred next-hop for routing from `from` to `to`
    function setRoute(uint8 from, uint8 to, uint8 nextHop)
        external onlyOwner validNode(from) validNode(to) validNode(nextHop)
    {
        routingTable[from][to] = nextHop;
        routeExists[from][to] = true;
        emit RoutingTableUpdated(from, to, nextHop);
    }

    /// @notice Initialize default shortest-path routing based on Tree of Life
    function initializeDefaultRoutes() external onlyOwner {
        // Keter(0) → paths
        _setRoute(0, 9, 5); // Keter→Malkuth via Tiferet
        _setRoute(0, 5, 1); // Keter→Tiferet via Chochmah
        _setRoute(0, 8, 1); // Keter→Yesod via Chochmah
        // Chochmah(1) → paths
        _setRoute(1, 9, 5); // Chochmah→Malkuth via Tiferet
        _setRoute(1, 8, 5); // Chochmah→Yesod via Tiferet
        // Binah(2) → paths
        _setRoute(2, 9, 5); // Binah→Malkuth via Tiferet
        _setRoute(2, 8, 5); // Binah→Yesod via Tiferet
        // Tiferet(5) → paths
        _setRoute(5, 0, 1); // Tiferet→Keter via Chochmah
        _setRoute(5, 9, 8); // Tiferet→Malkuth via Yesod
        // Yesod(8) → paths
        _setRoute(8, 0, 5); // Yesod→Keter via Tiferet
        _setRoute(8, 5, 5); // Yesod→Tiferet direct
        // Malkuth(9) → paths
        _setRoute(9, 0, 8); // Malkuth→Keter via Yesod
        _setRoute(9, 5, 8); // Malkuth→Tiferet via Yesod
    }

    function _setRoute(uint8 from, uint8 to, uint8 nextHop) internal {
        routingTable[from][to] = nextHop;
        routeExists[from][to] = true;
    }

    // ─── Core Routing ────────────────────────────────────────────────────
    /// @notice Route a message with backpressure and entanglement awareness
    /// @param from     Source Sephirah node ID (0-9)
    /// @param to       Destination Sephirah node ID (0-9)
    /// @param priority QBC fee attached (higher = faster processing)
    /// @return result  Routing decision with adjusted priority
    function route(uint8 from, uint8 to, uint256 priority)
        external onlyAuthorized validNode(from) validNode(to)
        returns (RouteResult memory result)
    {
        totalRouted++;

        // 1. Check quantum entanglement shortcut
        if (hasEntangledPartner[from] && entangledPartner[from] == to) {
            totalEntangledDeliveries++;
            emit EntangledDelivery(from, to, block.timestamp);
            emit MessageRouted(from, to, to, priority, true);
            return RouteResult({
                nextHop: to,
                adjustedPriority: priority,
                entangled: true,
                backpressureApplied: false
            });
        }

        // 2. Check backpressure on destination
        uint256 destPressure = nodePressure[to];
        uint256 adjustedPriority = priority;
        bool backpressure = false;

        if (destPressure >= (MAX_PRESSURE * BACKPRESSURE_THRESHOLD_BPS) / 10000) {
            adjustedPriority = priority / PRIORITY_HALVING_FACTOR;
            backpressure = true;
            totalBackpressureEvents++;
            emit BackpressureApplied(to, destPressure, priority, adjustedPriority);
        }

        // 3. Find next hop
        uint8 nextHop = to; // default: direct delivery
        if (routeExists[from][to]) {
            nextHop = routingTable[from][to];
        }

        emit MessageRouted(from, to, nextHop, adjustedPriority, false);

        return RouteResult({
            nextHop: nextHop,
            adjustedPriority: adjustedPriority,
            entangled: false,
            backpressureApplied: backpressure
        });
    }

    // ─── Pressure Management ─────────────────────────────────────────────
    /// @notice Record a message being enqueued for a node
    function recordEnqueue(uint8 nodeId) external onlyAuthorized validNode(nodeId) {
        nodePressure[nodeId]++;
        emit PressureUpdated(nodeId, nodePressure[nodeId]);
    }

    /// @notice Record a message being delivered/dropped for a node
    function recordDequeue(uint8 nodeId) external onlyAuthorized validNode(nodeId) {
        if (nodePressure[nodeId] > 0) {
            nodePressure[nodeId]--;
        }
        emit PressureUpdated(nodeId, nodePressure[nodeId]);
    }

    /// @notice Check if a node is congested
    function isCongested(uint8 nodeId) external view validNode(nodeId) returns (bool) {
        return nodePressure[nodeId] >= (MAX_PRESSURE * BACKPRESSURE_THRESHOLD_BPS) / 10000;
    }

    /// @notice Get normalized pressure for a node (0-10000 basis points)
    function getPressureBps(uint8 nodeId) external view validNode(nodeId) returns (uint256) {
        if (MAX_PRESSURE == 0) return 0;
        return (nodePressure[nodeId] * 10000) / MAX_PRESSURE;
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    /// @notice Check if two nodes are quantum-entangled SUSY partners
    function isEntangled(uint8 nodeA, uint8 nodeB) external view returns (bool) {
        return hasEntangledPartner[nodeA] && entangledPartner[nodeA] == nodeB;
    }

    /// @notice Get the entangled partner of a node (reverts if none)
    function getPartner(uint8 nodeId) external view validNode(nodeId) returns (uint8) {
        require(hasEntangledPartner[nodeId], "VentricleRouter: no partner");
        return entangledPartner[nodeId];
    }

    /// @notice Get all pressure readings for dashboard
    function getAllPressures() external view returns (uint256[10] memory pressures) {
        for (uint8 i = 0; i < NUM_NODES; i++) {
            pressures[i] = nodePressure[i];
        }
    }

    /// @notice Get routing statistics
    function getStats() external view returns (
        uint256 routed,
        uint256 backpressureEvents,
        uint256 entangledDeliveries
    ) {
        return (totalRouted, totalBackpressureEvents, totalEntangledDeliveries);
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setMessageBus(address _messageBus) external onlyOwner {
        messageBus = _messageBus;
    }
}
