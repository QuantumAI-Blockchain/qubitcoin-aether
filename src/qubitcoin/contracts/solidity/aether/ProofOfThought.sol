// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title ProofOfThought — Proof-of-Thought Validation Contract
/// @notice Validates reasoning proofs from Sephirot nodes. Requires 67% validator consensus.
///         Each proof is linked to a block height and contains the solution + quantum proof hash.
contract ProofOfThought is Initializable {
    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant CONSENSUS_THRESHOLD_BPS = 6700; // 67%
    uint256 public constant BPS_DENOM = 10000;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    address public validatorRegistry;
    uint256 public proofCount;

    enum ProofStatus { Submitted, Validating, Validated, Rejected }

    struct Proof {
        uint256     id;
        uint256     taskId;
        address     submitter;       // Sephirah node or solver
        bytes32     solutionHash;
        bytes32     quantumProofHash;
        uint256     blockHeight;     // linked block
        uint256     timestamp;
        uint256     votesFor;
        uint256     votesAgainst;
        uint256     totalValidators;
        ProofStatus status;
    }

    mapping(uint256 => Proof)                     public proofs;
    mapping(uint256 => mapping(address => bool))  public hasValidated;

    /// @notice Block height → proof id (one proof per block)
    mapping(uint256 => uint256) public blockProofs;

    // ─── Events ──────────────────────────────────────────────────────────
    event ProofSubmitted(uint256 indexed id, uint256 indexed taskId, address submitter, bytes32 solutionHash);
    event ProofValidated(uint256 indexed id, uint256 votesFor, uint256 totalValidators);
    event ProofRejected(uint256 indexed id, uint256 votesAgainst, uint256 totalValidators);
    event ValidationVote(uint256 indexed proofId, address indexed validator, bool support);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "PoT: not authorized");
        _;
    }

    // ─── Initialization ─────────────────────────────────────────────────
    function initialize(address _kernel, address _validatorRegistry) external initializer {
        owner             = msg.sender;
        kernel            = _kernel;
        validatorRegistry = _validatorRegistry;
    }

    // ─── Proof Submission ────────────────────────────────────────────────
    /// @notice Submit a reasoning proof for validation
    function submitProof(
        uint256 taskId,
        address submitter,
        bytes32 solutionHash,
        bytes32 quantumProofHash,
        uint256 blockHeight
    ) external onlyKernel returns (uint256 proofId) {
        proofId = ++proofCount;
        proofs[proofId] = Proof({
            id:                proofId,
            taskId:            taskId,
            submitter:         submitter,
            solutionHash:      solutionHash,
            quantumProofHash:  quantumProofHash,
            blockHeight:       blockHeight,
            timestamp:         block.timestamp,
            votesFor:          0,
            votesAgainst:      0,
            totalValidators:   0,
            status:            ProofStatus.Submitted
        });

        blockProofs[blockHeight] = proofId;
        emit ProofSubmitted(proofId, taskId, submitter, solutionHash);
    }

    // ─── Validation Voting ───────────────────────────────────────────────
    /// @notice Validator votes on a proof
    function validateProof(uint256 proofId, address validator, bool support) external onlyKernel {
        Proof storage proof = proofs[proofId];
        require(proof.id == proofId, "PoT: proof not found");
        require(!hasValidated[proofId][validator], "PoT: already validated");
        require(proof.status == ProofStatus.Submitted || proof.status == ProofStatus.Validating, "PoT: not validating");

        hasValidated[proofId][validator] = true;
        proof.totalValidators++;
        proof.status = ProofStatus.Validating;

        if (support) {
            proof.votesFor++;
        } else {
            proof.votesAgainst++;
        }

        emit ValidationVote(proofId, validator, support);
    }

    /// @notice Finalize proof validation (check consensus)
    function finalizeProof(uint256 proofId) external onlyKernel {
        Proof storage proof = proofs[proofId];
        require(proof.status == ProofStatus.Validating, "PoT: not in validation");
        require(proof.totalValidators > 0, "PoT: no validators");

        uint256 approvalBps = (proof.votesFor * BPS_DENOM) / proof.totalValidators;

        if (approvalBps >= CONSENSUS_THRESHOLD_BPS) {
            proof.status = ProofStatus.Validated;
            emit ProofValidated(proofId, proof.votesFor, proof.totalValidators);
        } else {
            proof.status = ProofStatus.Rejected;
            emit ProofRejected(proofId, proof.votesAgainst, proof.totalValidators);
        }
    }

    // ─── Queries ─────────────────────────────────────────────────────────
    function getProof(uint256 proofId) external view returns (
        uint256 taskId,
        address submitter,
        bytes32 solutionHash,
        uint256 blockHeight,
        uint256 votesFor,
        uint256 votesAgainst,
        ProofStatus status
    ) {
        Proof storage p = proofs[proofId];
        return (p.taskId, p.submitter, p.solutionHash, p.blockHeight, p.votesFor, p.votesAgainst, p.status);
    }

    function getProofByBlock(uint256 blockHeight) external view returns (uint256) {
        return blockProofs[blockHeight];
    }
}
