// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";
import "../interfaces/IQBC20.sol";

/// @title TreasuryDAO — Community Governance Treasury
/// @notice Holds QBC for community governance. Proposals + QBC-weighted voting
///         for fund allocation to development, research, and operations.
contract TreasuryDAO is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant VOTING_PERIOD = 5 days;
    uint256 public constant EXECUTION_DELAY = 24 hours;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    IQBC20  public qbcToken;          // QBC token for on-chain vote weight verification
    uint256 public quorum = 100e18;   // minimum total votes to execute (default 100 QBC)
    uint256 public treasuryBalance;
    uint256 public proposalCount;

    enum ProposalStatus { Active, Passed, Rejected, Executed, Canceled }

    struct Proposal {
        uint256        id;
        address        proposer;
        string         description;
        address        recipient;
        uint256        amount;
        uint256        votesFor;
        uint256        votesAgainst;
        uint256        endTime;
        uint256        executeAfter;
        ProposalStatus status;
    }

    mapping(uint256 => Proposal) public proposals;
    mapping(uint256 => mapping(address => bool)) public hasVoted;

    // ─── Events ──────────────────────────────────────────────────────────
    event FundsDeposited(address indexed from, uint256 amount, uint256 newBalance);
    event FundsAllocated(uint256 indexed proposalId, address indexed recipient, uint256 amount);
    event ProposalCreated(uint256 indexed id, address proposer, uint256 amount, string description);
    event VoteCast(uint256 indexed id, address voter, bool support, uint256 weight);
    event ProposalExecuted(uint256 indexed id, address recipient, uint256 amount);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Treasury: not owner");
        _;
    }

    // ─── Initializer ────────────────────────────────────────────────────
    function initialize(address _qbcToken) external initializer {
        owner    = msg.sender;
        qbcToken = IQBC20(_qbcToken);
    }

    // ─── Treasury Management ─────────────────────────────────────────────
    function deposit(uint256 amount) external {
        require(amount > 0, "Treasury: zero amount");
        treasuryBalance += amount;
        emit FundsDeposited(msg.sender, amount, treasuryBalance);
    }

    // ─── Proposals ───────────────────────────────────────────────────────
    function createProposal(
        string calldata description,
        address recipient,
        uint256 amount
    ) external returns (uint256 proposalId) {
        require(amount <= treasuryBalance, "Treasury: insufficient funds");
        require(recipient != address(0), "Treasury: zero recipient");

        proposalId = ++proposalCount;
        proposals[proposalId] = Proposal({
            id:           proposalId,
            proposer:     msg.sender,
            description:  description,
            recipient:    recipient,
            amount:       amount,
            votesFor:     0,
            votesAgainst: 0,
            endTime:      block.timestamp + VOTING_PERIOD,
            executeAfter: 0,
            status:       ProposalStatus.Active
        });

        emit ProposalCreated(proposalId, msg.sender, amount, description);
    }

    function vote(uint256 proposalId, bool support, uint256 weight) external {
        Proposal storage p = proposals[proposalId];
        require(p.status == ProposalStatus.Active, "Treasury: not active");
        require(block.timestamp <= p.endTime, "Treasury: voting ended");
        require(!hasVoted[proposalId][msg.sender], "Treasury: already voted");
        require(weight <= qbcToken.balanceOf(msg.sender), "Treasury: weight exceeds balance");

        hasVoted[proposalId][msg.sender] = true;
        if (support) { p.votesFor += weight; }
        else { p.votesAgainst += weight; }

        emit VoteCast(proposalId, msg.sender, support, weight);
    }

    function finalize(uint256 proposalId) external {
        Proposal storage p = proposals[proposalId];
        require(p.status == ProposalStatus.Active, "Treasury: not active");
        require(block.timestamp > p.endTime, "Treasury: voting ongoing");

        if (p.votesFor > p.votesAgainst) {
            p.status = ProposalStatus.Passed;
            p.executeAfter = block.timestamp + EXECUTION_DELAY;
        } else {
            p.status = ProposalStatus.Rejected;
        }
    }

    function execute(uint256 proposalId) external {
        Proposal storage p = proposals[proposalId];
        require(p.status == ProposalStatus.Passed, "Treasury: not passed");
        require(block.timestamp >= p.executeAfter, "Treasury: delay not met");
        require(p.votesFor + p.votesAgainst >= quorum, "Treasury: quorum not reached");
        require(treasuryBalance >= p.amount, "Treasury: insufficient funds");

        treasuryBalance -= p.amount;
        p.status = ProposalStatus.Executed;

        emit ProposalExecuted(proposalId, p.recipient, p.amount);
        emit FundsAllocated(proposalId, p.recipient, p.amount);
    }

    // ─── Admin ──────────────────────────────────────────────────────────
    /// @notice Update the quorum threshold (owner only)
    function setQuorum(uint256 newQuorum) external onlyOwner {
        quorum = newQuorum;
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getBalance() external view returns (uint256) {
        return treasuryBalance;
    }
}
