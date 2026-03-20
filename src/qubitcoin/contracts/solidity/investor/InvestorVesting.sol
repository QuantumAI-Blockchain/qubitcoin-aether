// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/**
 * @title InvestorVesting
 * @notice Merkle-proof verified vesting distribution for QBC and QUSD tokens.
 *         6-month cliff, 24-month linear vesting (4.17%/month after cliff).
 *         Proxy-upgradeable via QBCProxy + ProxyAdmin.
 *         No OpenZeppelin dependencies -- all logic is custom.
 */

// Minimal QBC-20 interface (transfer + balanceOf)
interface IQBC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract InvestorVesting is Initializable {
    // ---------------------------------------------------------------
    //  Custom ReentrancyGuard
    // ---------------------------------------------------------------
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _status;

    modifier nonReentrant() {
        require(_status != _ENTERED, "ReentrancyGuard: reentrant call");
        _status = _ENTERED;
        _;
        _status = _NOT_ENTERED;
    }

    // ---------------------------------------------------------------
    //  Pausable
    // ---------------------------------------------------------------
    bool public paused;

    modifier whenNotPaused() {
        require(!paused, "InvestorVesting: paused");
        _;
    }

    // ---------------------------------------------------------------
    //  Access control
    // ---------------------------------------------------------------
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "InvestorVesting: caller is not the owner");
        _;
    }

    // ---------------------------------------------------------------
    //  Token references
    // ---------------------------------------------------------------
    IQBC20 public qbcToken;
    IQBC20 public qusdToken;

    // ---------------------------------------------------------------
    //  Merkle root (set-once)
    // ---------------------------------------------------------------
    bytes32 public merkleRoot;
    bool public merkleRootSet;

    // ---------------------------------------------------------------
    //  Vesting schedule constants
    // ---------------------------------------------------------------
    uint256 public constant CLIFF_DURATION = 180 days;   // 6 months
    uint256 public constant VESTING_DURATION = 720 days;  // 24 months

    // ---------------------------------------------------------------
    //  TGE timestamp (set by admin)
    // ---------------------------------------------------------------
    uint256 public tgeTimestamp;

    // ---------------------------------------------------------------
    //  Global tracking
    // ---------------------------------------------------------------
    uint256 public totalClaimedQBC;
    uint256 public totalClaimedQUSD;
    uint256 public totalInitialized;

    // ---------------------------------------------------------------
    //  Per-investor vesting state
    // ---------------------------------------------------------------
    struct VestingInfo {
        uint256 qbcTotal;
        uint256 qusdTotal;
        uint256 qbcClaimed;
        uint256 qusdClaimed;
        bool initialized;
    }

    /// @dev keyed by bytes20 (QBC native address)
    mapping(bytes20 => VestingInfo) public vestingInfo;

    // ---------------------------------------------------------------
    //  Events
    // ---------------------------------------------------------------
    event ClaimInitialized(
        bytes20 indexed qbcAddress,
        uint256 qbcAmount,
        uint256 qusdAmount
    );

    event TokensClaimed(
        bytes20 indexed qbcAddress,
        uint256 qbcAmount,
        uint256 qusdAmount
    );

    event PausedState(bool isPaused);

    // ---------------------------------------------------------------
    //  Initializer (replaces constructor for proxy pattern)
    // ---------------------------------------------------------------
    /**
     * @notice Initialize the vesting contract. Called once via QBCProxy.
     * @param _qbcToken  QBC token address on QBC chain.
     * @param _qusdToken QUSD token address on QBC chain.
     */
    function initialize(address _qbcToken, address _qusdToken) external initializer {
        require(_qbcToken != address(0), "InvestorVesting: zero QBC token");
        require(_qusdToken != address(0), "InvestorVesting: zero QUSD token");

        owner = msg.sender;
        qbcToken = IQBC20(_qbcToken);
        qusdToken = IQBC20(_qusdToken);
        _status = _NOT_ENTERED;
    }

    // ---------------------------------------------------------------
    //  Admin: set Merkle root (once only)
    // ---------------------------------------------------------------
    /**
     * @notice Set the Merkle root that encodes every investor's allocation.
     *         Can only be called once.
     * @param _root The Merkle root.
     */
    function setMerkleRoot(bytes32 _root) external onlyOwner {
        require(!merkleRootSet, "InvestorVesting: merkle root already set");
        require(_root != bytes32(0), "InvestorVesting: zero root");

        merkleRoot = _root;
        merkleRootSet = true;
    }

    // ---------------------------------------------------------------
    //  Admin: set TGE timestamp
    // ---------------------------------------------------------------
    /**
     * @notice Set or update the Token Generation Event timestamp.
     * @param _timestamp Unix timestamp of TGE.
     */
    function setTGETimestamp(uint256 _timestamp) external onlyOwner {
        require(_timestamp > 0, "InvestorVesting: zero timestamp");
        tgeTimestamp = _timestamp;
    }

    // ---------------------------------------------------------------
    //  Admin: pause / unpause
    // ---------------------------------------------------------------
    function pause() external onlyOwner {
        paused = true;
        emit PausedState(true);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit PausedState(false);
    }

    // ---------------------------------------------------------------
    //  Admin: transfer ownership
    // ---------------------------------------------------------------
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "InvestorVesting: zero owner");
        owner = newOwner;
    }

    // ---------------------------------------------------------------
    //  Admin: recover unclaimed tokens after full vesting + grace
    // ---------------------------------------------------------------
    /**
     * @notice Recover unclaimed tokens 1 year after vesting completes.
     * @param token Token address to recover.
     * @param amount Amount to recover.
     */
    function recoverUnclaimed(address token, uint256 amount) external onlyOwner {
        require(tgeTimestamp > 0, "InvestorVesting: TGE not set");
        require(
            block.timestamp > tgeTimestamp + CLIFF_DURATION + VESTING_DURATION + 365 days,
            "InvestorVesting: grace period active"
        );
        require(
            IQBC20(token).transfer(owner, amount),
            "InvestorVesting: recovery transfer failed"
        );
    }

    // ---------------------------------------------------------------
    //  Investor: initialize claim via Merkle proof
    // ---------------------------------------------------------------
    /**
     * @notice Prove your allocation via a Merkle proof and register your
     *         vesting schedule. Must be called before `claim()`.
     * @param qbcAmount  Total QBC allocation for the caller.
     * @param qusdAmount Total QUSD allocation for the caller.
     * @param proof      Merkle proof siblings.
     */
    function initializeClaim(
        uint256 qbcAmount,
        uint256 qusdAmount,
        bytes32[] calldata proof
    ) external whenNotPaused {
        require(merkleRootSet, "InvestorVesting: merkle root not set");

        bytes20 qbcAddress = bytes20(msg.sender);

        require(
            !vestingInfo[qbcAddress].initialized,
            "InvestorVesting: already initialized"
        );
        require(
            qbcAmount > 0 || qusdAmount > 0,
            "InvestorVesting: zero allocation"
        );

        // Compute leaf and verify proof
        bytes32 leaf = keccak256(
            abi.encodePacked(qbcAddress, qbcAmount, qusdAmount)
        );
        require(
            _verifyProof(proof, merkleRoot, leaf),
            "InvestorVesting: invalid merkle proof"
        );

        vestingInfo[qbcAddress] = VestingInfo({
            qbcTotal: qbcAmount,
            qusdTotal: qusdAmount,
            qbcClaimed: 0,
            qusdClaimed: 0,
            initialized: true
        });

        totalInitialized++;

        emit ClaimInitialized(qbcAddress, qbcAmount, qusdAmount);
    }

    // ---------------------------------------------------------------
    //  Investor: claim vested tokens
    // ---------------------------------------------------------------
    /**
     * @notice Claim all currently-vested-but-unclaimed QBC and QUSD.
     *         Uses Checks-Effects-Interactions (CEI) pattern.
     */
    function claim() external nonReentrant whenNotPaused {
        bytes20 qbcAddress = bytes20(msg.sender);
        VestingInfo storage info = vestingInfo[qbcAddress];

        require(info.initialized, "InvestorVesting: not initialized");
        require(tgeTimestamp > 0, "InvestorVesting: TGE not set");
        require(
            block.timestamp > tgeTimestamp + CLIFF_DURATION,
            "InvestorVesting: cliff not reached"
        );

        uint256 fraction = getVestedFraction(); // 18-decimal precision

        // Calculate claimable amounts
        uint256 qbcVested = (info.qbcTotal * fraction) / 1e18;
        uint256 qusdVested = (info.qusdTotal * fraction) / 1e18;

        uint256 qbcClaimable = qbcVested - info.qbcClaimed;
        uint256 qusdClaimable = qusdVested - info.qusdClaimed;

        require(
            qbcClaimable > 0 || qusdClaimable > 0,
            "InvestorVesting: nothing to claim"
        );

        // --- Effects (update state BEFORE transfers) ---
        info.qbcClaimed += qbcClaimable;
        info.qusdClaimed += qusdClaimable;
        totalClaimedQBC += qbcClaimable;
        totalClaimedQUSD += qusdClaimable;

        // --- Interactions ---
        if (qbcClaimable > 0) {
            require(
                qbcToken.transfer(msg.sender, qbcClaimable),
                "InvestorVesting: QBC transfer failed"
            );
        }
        if (qusdClaimable > 0) {
            require(
                qusdToken.transfer(msg.sender, qusdClaimable),
                "InvestorVesting: QUSD transfer failed"
            );
        }

        emit TokensClaimed(qbcAddress, qbcClaimable, qusdClaimable);
    }

    // ---------------------------------------------------------------
    //  View: full vesting info for an address
    // ---------------------------------------------------------------
    function getVestingInfo(bytes20 qbcAddress)
        external
        view
        returns (
            uint256 qbcTotal,
            uint256 qusdTotal,
            uint256 qbcClaimed,
            uint256 qusdClaimed,
            bool initialized,
            uint256 qbcClaimable,
            uint256 qusdClaimable
        )
    {
        VestingInfo storage info = vestingInfo[qbcAddress];

        qbcTotal = info.qbcTotal;
        qusdTotal = info.qusdTotal;
        qbcClaimed = info.qbcClaimed;
        qusdClaimed = info.qusdClaimed;
        initialized = info.initialized;

        if (
            initialized &&
            tgeTimestamp > 0 &&
            block.timestamp > tgeTimestamp + CLIFF_DURATION
        ) {
            uint256 fraction = getVestedFraction();
            uint256 qbcVested = (info.qbcTotal * fraction) / 1e18;
            uint256 qusdVested = (info.qusdTotal * fraction) / 1e18;
            qbcClaimable = qbcVested > info.qbcClaimed
                ? qbcVested - info.qbcClaimed
                : 0;
            qusdClaimable = qusdVested > info.qusdClaimed
                ? qusdVested - info.qusdClaimed
                : 0;
        }
    }

    // ---------------------------------------------------------------
    //  View: current vested fraction (18 decimals)
    // ---------------------------------------------------------------
    function getVestedFraction() public view returns (uint256) {
        if (tgeTimestamp == 0) {
            return 0;
        }
        if (block.timestamp <= tgeTimestamp + CLIFF_DURATION) {
            return 0;
        }

        uint256 elapsed = block.timestamp - tgeTimestamp - CLIFF_DURATION;

        if (elapsed >= VESTING_DURATION) {
            return 1e18; // fully vested
        }

        return (elapsed * 1e18) / VESTING_DURATION;
    }

    // ---------------------------------------------------------------
    //  View: global stats
    // ---------------------------------------------------------------
    function getGlobalInfo()
        external
        view
        returns (
            bytes32 root,
            uint256 cliff,
            uint256 duration,
            uint256 tge,
            uint256 claimedQBC,
            uint256 claimedQUSD,
            uint256 investorsInitialized
        )
    {
        root = merkleRoot;
        cliff = CLIFF_DURATION;
        duration = VESTING_DURATION;
        tge = tgeTimestamp;
        claimedQBC = totalClaimedQBC;
        claimedQUSD = totalClaimedQUSD;
        investorsInitialized = totalInitialized;
    }

    // ---------------------------------------------------------------
    //  Internal: custom Merkle proof verification
    // ---------------------------------------------------------------
    function _verifyProof(
        bytes32[] calldata proof,
        bytes32 root,
        bytes32 leaf
    ) internal pure returns (bool) {
        bytes32 hash = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 proofElement = proof[i];
            if (hash <= proofElement) {
                hash = keccak256(abi.encodePacked(hash, proofElement));
            } else {
                hash = keccak256(abi.encodePacked(proofElement, hash));
            }
        }
        return hash == root;
    }
}
