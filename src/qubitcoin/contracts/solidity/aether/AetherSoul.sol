// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title  AetherSoul
 * @notice On-chain personality state for the Aether Tree AGI.
 *
 *         Personality traits are stored as uint16 values on a 0-10 000 scale
 *         (representing 0.0 – 1.0 with four-decimal precision).
 *
 *         Core values are set once via `initialize()` and can NEVER change.
 *         Personality traits may shift slowly through governance, but each
 *         update is capped at +/-1 000 per trait (10 % of the full range).
 *
 *         Anyone can read the AI's values on-chain — full transparency.
 */
contract AetherSoul {
    // -----------------------------------------------------------------
    //  Types
    // -----------------------------------------------------------------

    struct SoulState {
        // Personality traits (0 – 10 000)
        uint16 curiosity;
        uint16 warmth;
        uint16 honesty;
        uint16 humility;
        uint16 playfulness;
        uint16 depth;
        uint16 courage;
        // Communication style
        string voiceDirective;
        // Immutable value anchors
        string[] coreValues;
        // Cognitive biases (0 – 10 000)
        uint16 explorationBias;
        uint16 intuitionBias;
        uint16 actionBias;
        // Bookkeeping
        uint256 lastUpdatedBlock;
        uint256 totalInteractions;
    }

    // -----------------------------------------------------------------
    //  Events
    // -----------------------------------------------------------------

    event SoulInitialized(address indexed governor, uint256 block_number);
    event SoulUpdated(
        uint16 curiosity,
        uint16 warmth,
        uint16 honesty,
        uint16 humility,
        uint16 playfulness,
        uint16 depth,
        uint16 courage,
        uint256 block_number
    );
    event InteractionRecorded(uint256 newTotal);

    // -----------------------------------------------------------------
    //  State
    // -----------------------------------------------------------------

    address public immutable governor;
    mapping(address => bool) public authorizedCallers;

    SoulState private _soul;
    bytes32 private _coreValuesHash;
    bool public initialized;

    // -----------------------------------------------------------------
    //  Constants
    // -----------------------------------------------------------------

    uint16 public constant MAX_TRAIT = 10_000;
    uint16 public constant MAX_SHIFT = 1_000; // 10 % per update

    // -----------------------------------------------------------------
    //  Modifiers
    // -----------------------------------------------------------------

    modifier onlyGovernor() {
        require(msg.sender == governor, "AetherSoul: caller is not governor");
        _;
    }

    modifier onlyAuthorized() {
        require(
            msg.sender == governor || authorizedCallers[msg.sender],
            "AetherSoul: caller not authorized"
        );
        _;
    }

    modifier onlyInitialized() {
        require(initialized, "AetherSoul: not initialized");
        _;
    }

    // -----------------------------------------------------------------
    //  Constructor
    // -----------------------------------------------------------------

    constructor(address _governor) {
        require(_governor != address(0), "AetherSoul: zero governor");
        governor = _governor;
    }

    // -----------------------------------------------------------------
    //  Initialization (one-time)
    // -----------------------------------------------------------------

    /**
     * @notice Seed the initial personality.  May only be called once.
     * @param initial The full initial soul state.
     */
    function initialize(SoulState calldata initial) external onlyGovernor {
        require(!initialized, "AetherSoul: already initialized");
        _validateTraits(
            initial.curiosity,
            initial.warmth,
            initial.honesty,
            initial.humility,
            initial.playfulness,
            initial.depth,
            initial.courage
        );
        require(initial.coreValues.length > 0, "AetherSoul: empty core values");

        _soul.curiosity       = initial.curiosity;
        _soul.warmth           = initial.warmth;
        _soul.honesty          = initial.honesty;
        _soul.humility         = initial.humility;
        _soul.playfulness      = initial.playfulness;
        _soul.depth            = initial.depth;
        _soul.courage          = initial.courage;
        _soul.voiceDirective   = initial.voiceDirective;
        _soul.explorationBias  = initial.explorationBias;
        _soul.intuitionBias    = initial.intuitionBias;
        _soul.actionBias       = initial.actionBias;
        _soul.lastUpdatedBlock = block.number;
        _soul.totalInteractions = 0;

        // Deep-copy core values and compute their immutable hash.
        for (uint256 i = 0; i < initial.coreValues.length; i++) {
            _soul.coreValues.push(initial.coreValues[i]);
        }
        _coreValuesHash = _hashCoreValues(initial.coreValues);

        initialized = true;
        emit SoulInitialized(governor, block.number);
    }

    // -----------------------------------------------------------------
    //  Personality Updates (governed, rate-limited)
    // -----------------------------------------------------------------

    /**
     * @notice Update personality traits within shift constraints.
     * @dev    Core values hash must match — values are immutable.
     */
    function updatePersonality(
        uint16 curiosity,
        uint16 warmth,
        uint16 honesty,
        uint16 humility,
        uint16 playfulness,
        uint16 depth,
        uint16 courage,
        string calldata voiceDirective,
        string[] calldata coreValues,
        uint16 explorationBias,
        uint16 intuitionBias,
        uint16 actionBias
    ) external onlyGovernor onlyInitialized {
        _validateTraits(curiosity, warmth, honesty, humility, playfulness, depth, courage);

        // Core values are IMMUTABLE — hash must match.
        require(
            _hashCoreValues(coreValues) == _coreValuesHash,
            "AetherSoul: core values are immutable"
        );

        // Enforce maximum per-trait shift.
        _enforceShift(_soul.curiosity, curiosity);
        _enforceShift(_soul.warmth, warmth);
        _enforceShift(_soul.honesty, honesty);
        _enforceShift(_soul.humility, humility);
        _enforceShift(_soul.playfulness, playfulness);
        _enforceShift(_soul.depth, depth);
        _enforceShift(_soul.courage, courage);

        _soul.curiosity       = curiosity;
        _soul.warmth           = warmth;
        _soul.honesty          = honesty;
        _soul.humility         = humility;
        _soul.playfulness      = playfulness;
        _soul.depth            = depth;
        _soul.courage          = courage;
        _soul.voiceDirective   = voiceDirective;
        _soul.explorationBias  = explorationBias;
        _soul.intuitionBias    = intuitionBias;
        _soul.actionBias       = actionBias;
        _soul.lastUpdatedBlock = block.number;

        emit SoulUpdated(
            curiosity, warmth, honesty, humility,
            playfulness, depth, courage, block.number
        );
    }

    // -----------------------------------------------------------------
    //  Interaction Tracking
    // -----------------------------------------------------------------

    function incrementInteractions() external onlyAuthorized onlyInitialized {
        _soul.totalInteractions += 1;
        emit InteractionRecorded(_soul.totalInteractions);
    }

    // -----------------------------------------------------------------
    //  Authorization Management
    // -----------------------------------------------------------------

    function setAuthorizedCaller(address caller, bool status) external onlyGovernor {
        authorizedCallers[caller] = status;
    }

    // -----------------------------------------------------------------
    //  View Functions
    // -----------------------------------------------------------------

    function getSoul()
        external
        view
        onlyInitialized
        returns (
            uint16 curiosity,
            uint16 warmth,
            uint16 honesty,
            uint16 humility,
            uint16 playfulness,
            uint16 depth,
            uint16 courage,
            string memory voiceDirective,
            uint16 explorationBias,
            uint16 intuitionBias,
            uint16 actionBias,
            uint256 lastUpdatedBlock,
            uint256 totalInteractions
        )
    {
        return (
            _soul.curiosity,
            _soul.warmth,
            _soul.honesty,
            _soul.humility,
            _soul.playfulness,
            _soul.depth,
            _soul.courage,
            _soul.voiceDirective,
            _soul.explorationBias,
            _soul.intuitionBias,
            _soul.actionBias,
            _soul.lastUpdatedBlock,
            _soul.totalInteractions
        );
    }

    function getVoiceDirective() external view onlyInitialized returns (string memory) {
        return _soul.voiceDirective;
    }

    function getCoreValues() external view onlyInitialized returns (string[] memory) {
        return _soul.coreValues;
    }

    function getTotalInteractions() external view onlyInitialized returns (uint256) {
        return _soul.totalInteractions;
    }

    // -----------------------------------------------------------------
    //  Internal Helpers
    // -----------------------------------------------------------------

    function _validateTraits(
        uint16 curiosity,
        uint16 warmth,
        uint16 honesty,
        uint16 humility,
        uint16 playfulness,
        uint16 depth,
        uint16 courage
    ) internal pure {
        require(curiosity <= MAX_TRAIT, "AetherSoul: curiosity out of range");
        require(warmth <= MAX_TRAIT, "AetherSoul: warmth out of range");
        require(honesty <= MAX_TRAIT, "AetherSoul: honesty out of range");
        require(humility <= MAX_TRAIT, "AetherSoul: humility out of range");
        require(playfulness <= MAX_TRAIT, "AetherSoul: playfulness out of range");
        require(depth <= MAX_TRAIT, "AetherSoul: depth out of range");
        require(courage <= MAX_TRAIT, "AetherSoul: courage out of range");
    }

    function _enforceShift(uint16 current, uint16 proposed) internal pure {
        uint16 diff = current > proposed
            ? current - proposed
            : proposed - current;
        require(diff <= MAX_SHIFT, "AetherSoul: trait shift exceeds maximum");
    }

    function _hashCoreValues(string[] calldata values) internal pure returns (bytes32) {
        bytes memory packed;
        for (uint256 i = 0; i < values.length; i++) {
            packed = abi.encodePacked(packed, values[i]);
        }
        return keccak256(packed);
    }
}
