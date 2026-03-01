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
    uint256 public constant MIN_VALIDATOR_STAKE = 100 ether; // 100 QBC minimum stake
    uint256 public constant SLASH_PERCENTAGE = 50;           // 50% slash per CLAUDE.md spec
    uint256 public constant UNSTAKING_DELAY = 183927;        // 7 days at 3.3s blocks (7*24*3600/3.3)

    // ─── Reentrancy Guard ───────────────────────────────────────────────
    bool private _locked;

    // ─── State ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    address public validatorRegistry;
    uint256 public proofCount;

    /// @notice Validator stakes: address => staked amount
    mapping(address => uint256) public stakes;
    /// @notice Block at which unstake was requested (0 = no pending request)
    mapping(address => uint256) public unstakeRequestBlock;
    /// @notice Total staked across all validators
    uint256 public totalStaked;
    /// @notice Total slashed across all validators
    uint256 public totalSlashed;

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
    event ValidatorStaked(address indexed validator, uint256 amount, uint256 totalStake);
    event ValidatorSlashed(address indexed validator, uint256 slashAmount, uint256 remainingStake);
    event UnstakeRequested(address indexed validator, uint256 requestBlock, uint256 unlockBlock);
    event StakeWithdrawn(address indexed validator, uint256 amount);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "PoT: not owner");
        _;
    }

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "PoT: not authorized");
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "PoT: reentrant call");
        _locked = true;
        _;
        _locked = false;
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

    // ─── Validator Staking ────────────────────────────────────────────────

    /// @notice Stake QBC to become a validator. Must meet minimum stake requirement.
    function stake() external payable {
        require(msg.value > 0, "PoT: zero stake");
        require(stakes[msg.sender] + msg.value >= MIN_VALIDATOR_STAKE, "PoT: below minimum stake");

        stakes[msg.sender] += msg.value;
        totalStaked += msg.value;

        emit ValidatorStaked(msg.sender, msg.value, stakes[msg.sender]);
    }

    /// @notice Slash a validator for submitting an invalid proof (50% of stake).
    ///         Only callable by owner/kernel when a proof is rejected.
    /// @param validator Address of the validator to slash
    function slash(address validator) external onlyKernel {
        uint256 validatorStake = stakes[validator];
        require(validatorStake > 0, "PoT: no stake to slash");

        uint256 slashAmount = (validatorStake * SLASH_PERCENTAGE) / 100;
        stakes[validator] -= slashAmount;
        totalStaked -= slashAmount;
        totalSlashed += slashAmount;

        emit ValidatorSlashed(validator, slashAmount, stakes[validator]);
    }

    /// @notice Request to unstake. Starts the 7-day unstaking delay.
    ///         Must be called before withdrawStake().
    function requestUnstake() external {
        require(stakes[msg.sender] > 0, "PoT: no stake");
        require(unstakeRequestBlock[msg.sender] == 0, "PoT: already requested");

        unstakeRequestBlock[msg.sender] = block.number;
        emit UnstakeRequested(msg.sender, block.number, block.number + UNSTAKING_DELAY);
    }

    /// @notice Withdraw unstaked validator funds after the 7-day unstaking delay.
    ///         Requires prior call to requestUnstake() and waiting UNSTAKING_DELAY blocks.
    function withdrawStake(uint256 amount) external nonReentrant {
        require(amount > 0, "PoT: zero amount");
        require(stakes[msg.sender] >= amount, "PoT: insufficient stake");
        require(unstakeRequestBlock[msg.sender] > 0, "PoT: unstake not requested");
        require(
            block.number >= unstakeRequestBlock[msg.sender] + UNSTAKING_DELAY,
            "PoT: unstaking delay not met"
        );

        stakes[msg.sender] -= amount;
        totalStaked -= amount;

        // Reset unstake request if fully withdrawn
        if (stakes[msg.sender] == 0) {
            unstakeRequestBlock[msg.sender] = 0;
        }

        (bool success, ) = payable(msg.sender).call{value: amount}("");
        require(success, "PoT: transfer failed");

        emit StakeWithdrawn(msg.sender, amount);
    }

    /// @notice Check if an address meets minimum stake to be a validator
    function isValidValidator(address validator) external view returns (bool) {
        return stakes[validator] >= MIN_VALIDATOR_STAKE;
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
