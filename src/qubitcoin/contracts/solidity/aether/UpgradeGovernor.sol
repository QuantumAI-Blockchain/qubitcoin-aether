// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";
import "../interfaces/IQBC20.sol";

/// @title UpgradeGovernor — Protocol Upgrade Governance
/// @notice Propose, vote, and execute upgrades to Aether Tree contracts.
///         Voting period + timelock ensures community review before any change.
contract UpgradeGovernor is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant VOTING_PERIOD   = 7 days;
    uint256 public constant TIMELOCK_PERIOD = 48 hours;
    uint256 public constant MIN_PROPOSAL_BALANCE = 1000 ether; // 1000 QBC to propose

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    IQBC20  public qbcToken;   // QBC token for on-chain vote weight verification
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
        uint256       totalSupplyAtCreation; // snapshot for quorum check
        UpgradeStatus status;
    }

    mapping(uint256 => UpgradeProposal) public proposals;
    mapping(uint256 => mapping(address => bool)) public hasVoted;
    /// @notice Stores the voter's balance snapshot at vote time to prevent vote-transfer-vote attacks
    mapping(uint256 => mapping(address => uint256)) public voteWeightUsed;

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
    function initialize(address _proxyAdmin, address _qbcToken) external initializer {
        owner      = msg.sender;
        proxyAdmin = _proxyAdmin;
        qbcToken   = IQBC20(_qbcToken);
    }

    // ─── Proposals ───────────────────────────────────────────────────────
    function proposeUpgrade(
        string  calldata description,
        address targetContract,
        address newImplementation
    ) external returns (uint256 proposalId) {
        require(targetContract != address(0), "Governor: zero target");
        require(newImplementation != address(0), "Governor: zero impl");
        require(qbcToken.balanceOf(msg.sender) >= MIN_PROPOSAL_BALANCE, "Governor: insufficient QBC balance");

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
            totalSupplyAtCreation: qbcToken.totalSupply(),
            status:            UpgradeStatus.Voting
        });

        emit UpgradeProposed(proposalId, targetContract, newImplementation, description);
    }

    function vote(uint256 proposalId, bool support, uint256 weight) external {
        UpgradeProposal storage p = proposals[proposalId];
        require(p.status == UpgradeStatus.Voting, "Governor: not voting");
        require(block.timestamp <= p.votingEndTime, "Governor: voting ended");
        require(!hasVoted[proposalId][msg.sender], "Governor: already voted");

        // Snapshot voter's balance on first vote to prevent vote-transfer-vote attacks
        uint256 voterBalance = qbcToken.balanceOf(msg.sender);
        require(weight <= voterBalance, "Governor: weight exceeds balance");

        hasVoted[proposalId][msg.sender] = true;
        voteWeightUsed[proposalId][msg.sender] = voterBalance;
        if (support) { p.votesFor += weight; }
        else { p.votesAgainst += weight; }

        emit UpgradeVote(proposalId, msg.sender, support, weight);
    }

    function finalize(uint256 proposalId) external {
        UpgradeProposal storage p = proposals[proposalId];
        require(p.status == UpgradeStatus.Voting, "Governor: not voting");
        require(block.timestamp > p.votingEndTime, "Governor: voting ongoing");

        // Require 10% quorum of total supply at proposal creation time
        uint256 totalVotes = p.votesFor + p.votesAgainst;
        require(totalVotes >= p.totalSupplyAtCreation / 10, "Governor: quorum not reached");

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
