// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title NodeRegistry — Sephirot Node Registry for Aether Tree
/// @notice Stores all 10 Sephirot node contract addresses, types, quantum state hashes,
///         and SUSY pair mappings. Central directory for the Tree of Life architecture.
contract NodeRegistry is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint8 public constant MAX_NODES = 10;
    uint256 public constant PHI = 1618; // φ × 1000

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;

    enum NodeStatus { Inactive, Active, Suspended }

    struct NodeInfo {
        uint8       id;
        string      name;
        string      role;           // cognitive function
        address     contractAddr;
        uint8       qubitCount;
        bytes32     quantumStateHash;
        uint256     energyLevel;    // for SUSY balance
        uint256     cognitiveMass;  // from Higgs field (× 1000)
        uint256     yukawaCoupling; // Yukawa coupling constant (× 1000)
        NodeStatus  status;
        uint256     registeredAt;
    }

    /// @notice SUSY pair: expansion ↔ constraint node
    struct SUSYPair {
        uint8  expansionNodeId;
        uint8  constraintNodeId;
        string expansionName;
        string constraintName;
    }

    mapping(uint8 => NodeInfo) public nodes;
    SUSYPair[3] public susyPairs;
    uint8 public nodeCount;

    // ─── Events ──────────────────────────────────────────────────────────
    event NodeAdded(uint8 indexed id, string name, address contractAddr, uint8 qubitCount);
    event NodeRemoved(uint8 indexed id);
    event NodeStatusChanged(uint8 indexed id, NodeStatus oldStatus, NodeStatus newStatus);
    event QuantumStateUpdated(uint8 indexed id, bytes32 oldHash, bytes32 newHash);
    event EnergyUpdated(uint8 indexed id, uint256 oldEnergy, uint256 newEnergy);
    event SUSYPairRegistered(uint8 expansionId, uint8 constraintId);
    event MassUpdated(uint8 indexed id, uint256 oldMass, uint256 newMass);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Registry: not owner");
        _;
    }

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Registry: not authorized");
        _;
    }

    // ─── Initialization ─────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Node Management ─────────────────────────────────────────────────
    function addNode(
        uint8   id,
        string  calldata nodeName,
        string  calldata role,
        address contractAddr,
        uint8   qubitCount
    ) external onlyOwner {
        require(id < MAX_NODES, "Registry: invalid id");
        require(nodes[id].contractAddr == address(0), "Registry: already exists");
        require(contractAddr != address(0), "Registry: zero address");

        nodes[id] = NodeInfo({
            id:               id,
            name:             nodeName,
            role:             role,
            contractAddr:     contractAddr,
            qubitCount:       qubitCount,
            quantumStateHash: bytes32(0),
            energyLevel:      1000, // baseline energy
            cognitiveMass:    0,    // assigned by HiggsField
            yukawaCoupling:   0,    // assigned by HiggsField
            status:           NodeStatus.Active,
            registeredAt:     block.timestamp
        });
        nodeCount++;
        emit NodeAdded(id, nodeName, contractAddr, qubitCount);
    }

    function removeNode(uint8 id) external onlyOwner {
        require(nodes[id].contractAddr != address(0), "Registry: not found");
        delete nodes[id];
        nodeCount--;
        emit NodeRemoved(id);
    }

    /// @notice Allow a node contract to deregister itself
    function selfDeregister(uint8 id) external {
        require(nodes[id].contractAddr != address(0), "Registry: not found");
        require(nodes[id].contractAddr == msg.sender, "Registry: only node contract can self-deregister");
        delete nodes[id];
        nodeCount--;
        emit NodeRemoved(id);
    }

    function setNodeStatus(uint8 id, NodeStatus newStatus) external onlyKernel {
        require(nodes[id].contractAddr != address(0), "Registry: not found");
        NodeStatus old = nodes[id].status;
        nodes[id].status = newStatus;
        emit NodeStatusChanged(id, old, newStatus);
    }

    // ─── Quantum State ───────────────────────────────────────────────────
    function updateQuantumState(uint8 id, bytes32 newHash) external onlyKernel {
        require(nodes[id].contractAddr != address(0), "Registry: not found");
        bytes32 old = nodes[id].quantumStateHash;
        nodes[id].quantumStateHash = newHash;
        emit QuantumStateUpdated(id, old, newHash);
    }

    function updateEnergy(uint8 id, uint256 newEnergy) external onlyKernel {
        require(nodes[id].contractAddr != address(0), "Registry: not found");
        uint256 old = nodes[id].energyLevel;
        nodes[id].energyLevel = newEnergy;
        emit EnergyUpdated(id, old, newEnergy);
    }

    /// @notice Update cognitive mass and Yukawa coupling from HiggsField contract
    function updateMass(uint8 id, uint256 newMass, uint256 yukawa) external onlyKernel {
        require(nodes[id].contractAddr != address(0), "Registry: not found");
        uint256 oldMass = nodes[id].cognitiveMass;
        nodes[id].cognitiveMass = newMass;
        nodes[id].yukawaCoupling = yukawa;
        emit MassUpdated(id, oldMass, newMass);
    }

    // ─── SUSY Pairs ──────────────────────────────────────────────────────
    /// @notice Register the 3 SUSY pairs (expansion ↔ constraint)
    function registerSUSYPairs() external onlyOwner {
        // Chesed (3) ↔ Gevurah (4): Creativity vs Safety
        susyPairs[0] = SUSYPair(3, 4, "Chesed", "Gevurah");
        emit SUSYPairRegistered(3, 4);

        // Chochmah (1) ↔ Binah (2): Intuition vs Logic
        susyPairs[1] = SUSYPair(1, 2, "Chochmah", "Binah");
        emit SUSYPairRegistered(1, 2);

        // Netzach (6) ↔ Hod (7): Persistence vs Communication
        susyPairs[2] = SUSYPair(6, 7, "Netzach", "Hod");
        emit SUSYPairRegistered(6, 7);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getNode(uint8 id) external view returns (
        string memory nodeName,
        string memory role,
        address contractAddr,
        uint8   qubitCount,
        bytes32 quantumStateHash,
        uint256 energyLevel,
        uint256 cognitiveMass,
        uint256 yukawaCoupling,
        NodeStatus status
    ) {
        NodeInfo storage n = nodes[id];
        return (n.name, n.role, n.contractAddr, n.qubitCount, n.quantumStateHash,
                n.energyLevel, n.cognitiveMass, n.yukawaCoupling, n.status);
    }

    function getNodeAddress(uint8 id) external view returns (address) {
        return nodes[id].contractAddr;
    }

    function isNodeActive(uint8 id) external view returns (bool) {
        return nodes[id].status == NodeStatus.Active;
    }

    function getSUSYPair(uint8 pairIndex) external view returns (
        uint8  expansionId,
        uint8  constraintId,
        string memory expansionName,
        string memory constraintName
    ) {
        require(pairIndex < 3, "Registry: invalid pair");
        SUSYPair storage p = susyPairs[pairIndex];
        return (p.expansionNodeId, p.constraintNodeId, p.expansionName, p.constraintName);
    }
}
