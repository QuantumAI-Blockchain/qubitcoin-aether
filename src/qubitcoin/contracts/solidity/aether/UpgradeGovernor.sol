// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title UpgradeGovernor — Protocol Upgrade Governance
/// @notice Propose, vote, and execute upgrades to Aether Tree contracts.
///         Voting period + timelock ensures community review before any change.
contract UpgradeGovernor is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant VOTING_PERIOD   = 7 days;
    uint256 public constant TIMELOCK_PERIOD = 48 hours;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    uint256 public proposalCount;
    address public proxyAdmin;

    enum UpgradeStatus { Proposed, Voting, Approved, Rejected, Executed, Canceled }

    struct UpgradeProposal {
        uint256       id;
        address       proposer;
        string        description;
        address       targetContract;    // contract to upgrade
        address       newImplementation; // new implementation address
        uint256       votesFor;
        uint256       votesAgainst;
        uint256       votingEndTime;
        uint256       executeAfter;
        UpgradeStatus status;
    }

    mapping(uint256 => UpgradeProposal) public proposals;
    mapping(uint256 => mapping(address => bool)) public hasVoted;

    // ─── Events ──────────────────────────────────────────────────────────
    event UpgradeProposed(uint256 indexed id, address targetContract, address newImpl, string description);
    event UpgradeVote(uint256 indexed id, address voter, bool support, uint256 weight);
    event UpgradeApproved(uint256 indexed id, uint256 executeAfter);
    event UpgradeRejected(uint256 indexed id);
    event UpgradeExecuted(uint256 indexed id, address targetContract, address newImpl);
    event UpgradeCanceled(uint256 indexed id);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Governor: not owner");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _proxyAdmin) external initializer {
        owner = msg.sender;
        proxyAdmin = _proxyAdmin;
    }

    // ─── Proposals ───────────────────────────────────────────────────────
    function proposeUpgrade(
        string  calldata description,
        address targetContract,
        address newImplementation
    ) external returns (uint256 proposalId) {
        require(targetContract != address(0), "Governor: zero target");
        require(newImplementation != address(0), "Governor: zero impl");

        proposalId = ++proposalCount;
        proposals[proposalId] = UpgradeProposal({
            id:                proposalId,
            proposer:          msg.sender,
            description:       description,
            targetContract:    targetContract,
            newImplementation: newImplementation,
            votesFor:          0,
            votesAgainst:      0,
            votingEndTime:     block.timestamp + VOTING_PERIOD,
            executeAfter:      0,
            status:            UpgradeStatus.Voting
        });

        emit UpgradeProposed(proposalId, targetContract, newImplementation, description);
    }

    function vote(uint256 proposalId, bool support, uint256 weight) external {
        UpgradeProposal storage p = proposals[proposalId];
        require(p.status == UpgradeStatus.Voting, "Governor: not voting");
        require(block.timestamp <= p.votingEndTime, "Governor: voting ended");
        require(!hasVoted[proposalId][msg.sender], "Governor: already voted");

        hasVoted[proposalId][msg.sender] = true;
        if (support) { p.votesFor += weight; }
        else { p.votesAgainst += weight; }

        emit UpgradeVote(proposalId, msg.sender, support, weight);
    }

    function finalize(uint256 proposalId) external {
        UpgradeProposal storage p = proposals[proposalId];
        require(p.status == UpgradeStatus.Voting, "Governor: not voting");
        require(block.timestamp > p.votingEndTime, "Governor: voting ongoing");

        if (p.votesFor > p.votesAgainst) {
            p.status = UpgradeStatus.Approved;
            p.executeAfter = block.timestamp + TIMELOCK_PERIOD;
            emit UpgradeApproved(proposalId, p.executeAfter);
        } else {
            p.status = UpgradeStatus.Rejected;
            emit UpgradeRejected(proposalId);
        }
    }

    function execute(uint256 proposalId) external onlyOwner {
        UpgradeProposal storage p = proposals[proposalId];
        require(p.status == UpgradeStatus.Approved, "Governor: not approved");
        require(block.timestamp >= p.executeAfter, "Governor: timelock active");

        p.status = UpgradeStatus.Executed;

        // Wire upgrade to ProxyAdmin
        if (proxyAdmin != address(0)) {
            (bool ok,) = proxyAdmin.call(
                abi.encodeWithSignature("upgrade(address,address)", p.targetContract, p.newImplementation)
            );
            require(ok, "Governor: upgrade failed");
        }

        emit UpgradeExecuted(proposalId, p.targetContract, p.newImplementation);
    }

    function cancel(uint256 proposalId) external {
        UpgradeProposal storage p = proposals[proposalId];
        require(msg.sender == p.proposer || msg.sender == owner, "Governor: not authorized");
        require(p.status == UpgradeStatus.Voting || p.status == UpgradeStatus.Approved, "Governor: cannot cancel");

        p.status = UpgradeStatus.Canceled;
        emit UpgradeCanceled(proposalId);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getProposal(uint256 proposalId) external view returns (
        address proposer, address target, address newImpl,
        uint256 votesFor, uint256 votesAgainst, UpgradeStatus status
    ) {
        UpgradeProposal storage p = proposals[proposalId];
        return (p.proposer, p.targetContract, p.newImplementation, p.votesFor, p.votesAgainst, p.status);
    }
}
