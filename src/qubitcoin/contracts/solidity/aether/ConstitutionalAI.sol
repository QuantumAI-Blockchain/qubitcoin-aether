// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title ConstitutionalAI — On-Chain Value Enforcement
/// @notice Stores constitutional principles as immutable rules. The Gevurah safety node
///         can veto any operation that violates these principles. Principles are append-only
///         and can never be removed, only deprecated.
contract ConstitutionalAI is Initializable {
    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    address public gevurahNode; // safety node with veto power

    struct Principle {
        uint256 id;
        string  text;
        string  category;    // "safety", "alignment", "ethics", "operational"
        uint256 addedAt;
        uint256 addedBlock;
        bool    active;      // can be deprecated but never deleted
    }

    Principle[] public principles;
    uint256 public activePrincipleCount;

    /// @notice Veto records
    struct Veto {
        uint256 id;
        address vetoedBy;
        uint256 principleId;   // which principle was violated
        bytes32 operationHash; // hash of the vetoed operation
        string  reason;
        uint256 blockNumber;
        uint256 timestamp;
        bool    overridden;    // can be overridden by 4-of-5 emergency signers
    }
    Veto[] public vetoes;
    uint256 public totalVetoes;

    /// @notice O(1) lookup: operationHash => vetoed (true if any non-overridden veto exists)
    mapping(bytes32 => bool) public operationVetoed;

    // ─── Events ──────────────────────────────────────────────────────────
    event PrincipleAdded(uint256 indexed id, string category, string text, uint256 blockNumber);
    event PrincipleDeprecated(uint256 indexed id, uint256 blockNumber);
    event OperationVetoed(uint256 indexed vetoId, uint256 indexed principleId, bytes32 operationHash, string reason);
    event VetoOverridden(uint256 indexed vetoId, address overriddenBy);
    event GevurahNodeUpdated(address indexed oldNode, address indexed newNode);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Constitution: not owner");
        _;
    }

    modifier onlyGevurah() {
        require(msg.sender == gevurahNode || msg.sender == owner, "Constitution: not Gevurah");
        _;
    }

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Constitution: not authorized");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _kernel) external initializer {
        owner  = msg.sender;
        kernel = _kernel;
    }

    // ─── Principles (Append-Only) ────────────────────────────────────────
    /// @notice Add a constitutional principle (immutable once added)
    function addPrinciple(string calldata text, string calldata category) external onlyOwner returns (uint256 id) {
        id = principles.length;
        principles.push(Principle({
            id:         id,
            text:       text,
            category:   category,
            addedAt:    block.timestamp,
            addedBlock: block.number,
            active:     true
        }));
        activePrincipleCount++;
        emit PrincipleAdded(id, category, text, block.number);
    }

    /// @notice Deprecate a principle (does NOT delete — immutable history)
    function deprecatePrinciple(uint256 id) external onlyOwner {
        require(id < principles.length, "Constitution: not found");
        require(principles[id].active, "Constitution: already deprecated");
        principles[id].active = false;
        activePrincipleCount--;
        emit PrincipleDeprecated(id, block.number);
    }

    // ─── Veto System ─────────────────────────────────────────────────────
    /// @notice Gevurah safety node vetoes an operation
    function vetoOperation(
        uint256 principleId,
        bytes32 operationHash,
        string  calldata reason
    ) external onlyGevurah returns (uint256 vetoId) {
        require(principleId < principles.length, "Constitution: invalid principle");
        require(principles[principleId].active, "Constitution: deprecated principle");

        vetoId = vetoes.length;
        vetoes.push(Veto({
            id:            vetoId,
            vetoedBy:      msg.sender,
            principleId:   principleId,
            operationHash: operationHash,
            reason:        reason,
            blockNumber:   block.number,
            timestamp:     block.timestamp,
            overridden:    false
        }));
        totalVetoes++;
        operationVetoed[operationHash] = true;

        emit OperationVetoed(vetoId, principleId, operationHash, reason);
    }

    /// @notice Override a veto (requires kernel authorization — emergency only)
    function overrideVeto(uint256 vetoId) external onlyKernel {
        require(vetoId < vetoes.length, "Constitution: invalid veto");
        require(!vetoes[vetoId].overridden, "Constitution: already overridden");
        vetoes[vetoId].overridden = true;

        // Check if any non-overridden veto remains for this operation
        bytes32 opHash = vetoes[vetoId].operationHash;
        bool stillVetoed = false;
        for (uint256 i = 0; i < vetoes.length; i++) {
            if (vetoes[i].operationHash == opHash && !vetoes[i].overridden) {
                stillVetoed = true;
                break;
            }
        }
        if (!stillVetoed) {
            operationVetoed[opHash] = false;
        }

        emit VetoOverridden(vetoId, msg.sender);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getPrincipleCount() external view returns (uint256 total, uint256 active) {
        return (principles.length, activePrincipleCount);
    }

    function isOperationVetoed(bytes32 operationHash) external view returns (bool) {
        return operationVetoed[operationHash];
    }

    function getVetoCount() external view returns (uint256) {
        return vetoes.length;
    }

    // ─── Admin ───────────────────────────────────────────────────────────
    function setGevurahNode(address newGevurah) external onlyOwner {
        require(newGevurah != address(0), "Constitution: zero address");
        emit GevurahNodeUpdated(gevurahNode, newGevurah);
        gevurahNode = newGevurah;
    }
}
