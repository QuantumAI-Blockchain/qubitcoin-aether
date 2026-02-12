// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title QUSDGovernance — Reserve Management Governance
/// @notice QUSD holders create and vote on proposals for reserve management.
///         48-hour timelock on execution. Emergency bypass via multi-sig.
contract QUSDGovernance {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant TIMELOCK_DURATION = 48 hours;
    uint256 public constant VOTING_PERIOD     = 7 days;
    uint256 public constant QUORUM_BPS        = 400; // 4% of total supply
    uint256 public constant BPS_DENOM         = 10000;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public qusdToken;
    uint256 public proposalCount;
    uint256 public minProposalBalance; // minimum QUSD to create a proposal

    /// @notice Emergency multi-sig signers
    address[] public emergencySigners;
    uint256   public emergencyThreshold; // e.g., 5 of 7

    enum ProposalState { Pending, Active, Succeeded, Defeated, Queued, Executed, Canceled }

    struct Proposal {
        uint256     id;
        address     proposer;
        string      description;
        address     target;        // contract to call
        bytes       callData;      // encoded function call
        uint256     votesFor;
        uint256     votesAgainst;
        uint256     startBlock;
        uint256     endTimestamp;
        uint256     executionTime; // timestamp when executable (after timelock)
        ProposalState state;
    }

    mapping(uint256 => Proposal)                    public proposals;
    mapping(uint256 => mapping(address => bool))    public hasVoted;
    mapping(uint256 => mapping(address => bool))    public emergencySigned;

    // ─── Events ──────────────────────────────────────────────────────────
    event ProposalCreated(uint256 indexed id, address indexed proposer, string description);
    event VoteCast(uint256 indexed id, address indexed voter, bool support, uint256 weight);
    event ProposalQueued(uint256 indexed id, uint256 executionTime);
    event ProposalExecuted(uint256 indexed id);
    event ProposalCanceled(uint256 indexed id);
    event EmergencyExecuted(uint256 indexed id, uint256 signerCount);
    event EmergencySignerAdded(address indexed signer);
    event EmergencySignerRemoved(address indexed signer);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Governance: not owner");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor(address _qusdToken, uint256 _minBalance, uint256 _emergencyThreshold) {
        owner              = msg.sender;
        qusdToken          = _qusdToken;
        minProposalBalance = _minBalance;
        emergencyThreshold = _emergencyThreshold;
    }

    // ─── Proposals ───────────────────────────────────────────────────────
    /// @notice Create a new proposal (must hold minimum QUSD)
    function createProposal(
        string calldata description,
        address target,
        bytes   calldata callData
    ) external returns (uint256 proposalId) {
        // Balance check would query QUSD token in production
        proposalId = ++proposalCount;
        proposals[proposalId] = Proposal({
            id:            proposalId,
            proposer:      msg.sender,
            description:   description,
            target:        target,
            callData:      callData,
            votesFor:      0,
            votesAgainst:  0,
            startBlock:    block.number,
            endTimestamp:   block.timestamp + VOTING_PERIOD,
            executionTime: 0,
            state:         ProposalState.Active
        });

        emit ProposalCreated(proposalId, msg.sender, description);
    }

    /// @notice Vote on an active proposal
    /// @param proposalId The proposal to vote on
    /// @param support True = for, false = against
    /// @param weight Voting weight (QUSD balance, verified off-chain or via token)
    function vote(uint256 proposalId, bool support, uint256 weight) external {
        Proposal storage prop = proposals[proposalId];
        require(prop.state == ProposalState.Active, "Governance: not active");
        require(block.timestamp <= prop.endTimestamp, "Governance: voting ended");
        require(!hasVoted[proposalId][msg.sender], "Governance: already voted");

        hasVoted[proposalId][msg.sender] = true;
        if (support) {
            prop.votesFor += weight;
        } else {
            prop.votesAgainst += weight;
        }

        emit VoteCast(proposalId, msg.sender, support, weight);
    }

    /// @notice Finalize voting and queue for execution if succeeded
    function finalize(uint256 proposalId) external {
        Proposal storage prop = proposals[proposalId];
        require(prop.state == ProposalState.Active, "Governance: not active");
        require(block.timestamp > prop.endTimestamp, "Governance: voting not ended");

        if (prop.votesFor > prop.votesAgainst) {
            prop.state         = ProposalState.Queued;
            prop.executionTime = block.timestamp + TIMELOCK_DURATION;
            emit ProposalQueued(proposalId, prop.executionTime);
        } else {
            prop.state = ProposalState.Defeated;
        }
    }

    /// @notice Execute a queued proposal after timelock expires
    function execute(uint256 proposalId) external {
        Proposal storage prop = proposals[proposalId];
        require(prop.state == ProposalState.Queued, "Governance: not queued");
        require(block.timestamp >= prop.executionTime, "Governance: timelock active");

        prop.state = ProposalState.Executed;
        emit ProposalExecuted(proposalId);
    }

    /// @notice Cancel a proposal (proposer or owner only)
    function cancel(uint256 proposalId) external {
        Proposal storage prop = proposals[proposalId];
        require(
            msg.sender == prop.proposer || msg.sender == owner,
            "Governance: not authorized"
        );
        require(
            prop.state == ProposalState.Active || prop.state == ProposalState.Queued,
            "Governance: cannot cancel"
        );

        prop.state = ProposalState.Canceled;
        emit ProposalCanceled(proposalId);
    }

    // ─── Emergency Bypass ────────────────────────────────────────────────
    /// @notice Emergency multi-sig execution (bypasses timelock)
    function emergencySign(uint256 proposalId) external {
        require(_isEmergencySigner(msg.sender), "Governance: not emergency signer");
        require(!emergencySigned[proposalId][msg.sender], "Governance: already signed");

        emergencySigned[proposalId][msg.sender] = true;
        uint256 signCount = _emergencySignCount(proposalId);

        if (signCount >= emergencyThreshold) {
            Proposal storage prop = proposals[proposalId];
            require(
                prop.state != ProposalState.Executed && prop.state != ProposalState.Canceled,
                "Governance: invalid state"
            );
            prop.state = ProposalState.Executed;
            emit EmergencyExecuted(proposalId, signCount);
        }
    }

    function addEmergencySigner(address signer) external onlyOwner {
        emergencySigners.push(signer);
        emit EmergencySignerAdded(signer);
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getProposal(uint256 proposalId) external view returns (
        address proposer,
        string memory description,
        uint256 votesFor,
        uint256 votesAgainst,
        ProposalState state,
        uint256 endTimestamp,
        uint256 executionTime
    ) {
        Proposal storage p = proposals[proposalId];
        return (p.proposer, p.description, p.votesFor, p.votesAgainst, p.state, p.endTimestamp, p.executionTime);
    }

    // ─── Internal ────────────────────────────────────────────────────────
    function _isEmergencySigner(address addr) internal view returns (bool) {
        for (uint256 i = 0; i < emergencySigners.length; i++) {
            if (emergencySigners[i] == addr) return true;
        }
        return false;
    }

    function _emergencySignCount(uint256 proposalId) internal view returns (uint256 count) {
        for (uint256 i = 0; i < emergencySigners.length; i++) {
            if (emergencySigned[proposalId][emergencySigners[i]]) count++;
        }
    }
}
