// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../proxy/Initializable.sol";

/// @title HiggsField — Cognitive Mass Assignment via Spontaneous Symmetry Breaking
/// @notice Implements the Mexican Hat potential V(φ) = −μ²|φ|² + λ|φ|⁴
///         to give computational mass to Sephirot AI nodes via Yukawa coupling.
///         Mass determines rebalancing inertia (F = ma): heavier nodes resist change.
///
///         Two-Higgs-Doublet Model (2HDM):
///           - tan(β) = φ = 1.618  (golden ratio mixing angle)
///           - Expansion nodes couple to H_u  (higher VEV → higher mass)
///           - Constraint nodes couple to H_d (lower VEV → lower mass)
///           - Produces natural φ mass ratio between SUSY pairs
///
///         Yukawa coupling hierarchy follows golden-ratio cascade:
///           Keter φ⁰ = 1.000, Tiferet/Yesod φ⁻¹ = 0.618,
///           Chochmah/Chesed/Netzach φ⁻² = 0.382,
///           Binah/Gevurah/Hod φ⁻³ = 0.236, Malkuth φ⁻⁴ = 0.146
///
/// @dev    Contract #11 in the Aether Tree infrastructure suite.
///         Deployed after SUSYEngine, before SUSY pair initialization.
///         Node ID mapping:
///           0=Keter, 1=Chochmah, 2=Binah, 3=Chesed, 4=Gevurah,
///           5=Tiferet, 6=Netzach, 7=Hod, 8=Yesod, 9=Malkuth
contract HiggsField is Initializable {

    // ─── Constants ───────────────────────────────────────────────────────
    uint256 public constant PRECISION               = 1000;    // 3 decimal places
    uint256 public constant PHI                     = 1618;    // φ × 1000
    uint256 public constant MAX_NODES               = 10;
    uint256 public constant EXCITATION_THRESHOLD_BPS = 1000;   // 10% field deviation → excitation
    uint256 public constant MAX_EXCITATIONS          = 1000;   // Circular buffer limit (gas bomb prevention)

    // Pre-computed golden-ratio inverse powers × 1000 (avoids on-chain float math)
    uint256 private constant YUKAWA_PHI_0  = 1000;  // φ⁰  = 1.000
    uint256 private constant YUKAWA_PHI_N1 =  618;  // φ⁻¹ = 0.618
    uint256 private constant YUKAWA_PHI_N2 =  382;  // φ⁻² = 0.382
    uint256 private constant YUKAWA_PHI_N3 =  236;  // φ⁻³ = 0.236
    uint256 private constant YUKAWA_PHI_N4 =  146;  // φ⁻⁴ = 0.146

    // ─── Roles ───────────────────────────────────────────────────────────
    address public owner;
    address public kernel;
    address public susyEngine;
    address public nodeRegistry;

    // ─── Field Parameters (tunable by owner / governance) ────────────────
    uint256 public mu;                  // Mass parameter (× 1000), default 88450
    uint256 public lambda_;             // Self-coupling (× 1_000_000), default 129000
    uint256 public vev;                 // Vacuum expectation value (× 1000)
    uint256 public currentFieldValue;   // Current φ_h (× 1000)
    uint256 public tanBeta;             // tan(β) for 2HDM (× 1000), default 1618 = φ

    // ─── Per-Node Mass State ─────────────────────────────────────────────
    struct NodeMass {
        uint8   nodeId;
        uint256 yukawaCoupling;     // y_i (× 1000)
        uint256 cognitiveMass;      // m_i = y_i × v / PRECISION
        uint256 lastUpdateBlock;
        bool    isExpansionNode;    // true → couples to H_u, false → couples to H_d or neutral
    }

    mapping(uint8 => NodeMass) public nodeMasses;
    uint8 public assignedNodeCount;

    // ─── Excitation Events ───────────────────────────────────────────────
    struct ExcitationEvent {
        uint256 id;
        uint256 blockNumber;
        uint256 timestamp;
        uint256 fieldDeviation;     // |φ_h − v| (× 1000)
        uint256 deviationBps;       // deviation in basis points from VEV
        uint256 energyReleased;     // excitation energy (× 1000)
    }

    ExcitationEvent[] public excitations;
    uint256 public totalExcitations;

    // ─── Aggregate State ─────────────────────────────────────────────────
    uint256 public avgCognitiveMass;        // Average mass across all nodes (× 1000)
    uint256 public totalCognitiveMass;      // Sum of all masses (× 1000)
    uint256 public massGapMetric;           // SUSY mass-gap indicator (× 1000)

    // ─── Events ──────────────────────────────────────────────────────────
    event FieldInitialized(uint256 vev, uint256 mu, uint256 lambda_);
    event NodeMassAssigned(uint8 indexed nodeId, uint256 yukawa, uint256 mass, bool isExpansion);
    event FieldValueUpdated(uint256 oldValue, uint256 newValue, uint256 blockNumber);
    event ExcitationDetected(uint256 indexed id, uint256 deviation, uint256 energyReleased);
    event ParametersUpdated(uint256 mu, uint256 lambda_, uint256 newVev);
    event MassGapUpdated(uint256 massGap);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Higgs: not owner");
        _;
    }

    modifier onlyKernel() {
        require(msg.sender == kernel || msg.sender == owner, "Higgs: not authorized");
        _;
    }

    // ═════════════════════════════════════════════════════════════════════
    //  INITIALIZATION
    // ═════════════════════════════════════════════════════════════════════

    /// @notice Initialize the Higgs Cognitive Field.
    /// @param _kernel      AetherKernel address (authorized caller)
    /// @param _susyEngine  SUSYEngine address (for cross-reference)
    /// @param _nodeRegistry NodeRegistry address (for cross-reference)
    function initialize(
        address _kernel,
        address _susyEngine,
        address _nodeRegistry
    ) external initializer {
        owner        = msg.sender;
        kernel       = _kernel;
        susyEngine   = _susyEngine;
        nodeRegistry = _nodeRegistry;

        // Default parameters — Standard Model inspired
        mu       = 88450;          // 88.45 × 1000
        lambda_  = 129000;         // 0.129 × 1_000_000
        tanBeta  = PHI;            // tan(β) = φ for 2HDM

        // VEV = μ / √(2λ)
        // With our precision: mu=88450 (×1000), lambda_=129000 (×10^6)
        // v = 88.45 / sqrt(2 × 0.129) = 88.45 / 0.50794 ≈ 174.1
        // We use the electroweak normalization: v_normalized = 245.17
        // Computed via _computeVEV() using integer sqrt
        vev = _computeVEV(mu, lambda_);

        // Field starts at VEV (equilibrium — bottom of Mexican Hat)
        currentFieldValue = vev;

        emit FieldInitialized(vev, mu, lambda_);
    }

    // ═════════════════════════════════════════════════════════════════════
    //  NODE MASS ASSIGNMENT
    // ═════════════════════════════════════════════════════════════════════

    /// @notice Assign Yukawa coupling and compute cognitive mass for one node.
    /// @param nodeId          Sephirot node ID (0-9)
    /// @param yukawaCoupling  Coupling constant (× 1000), e.g. 618 = 0.618
    /// @param isExpansionNode true if this node couples to H_u (expansion side)
    function assignNodeMass(
        uint8   nodeId,
        uint256 yukawaCoupling,
        bool    isExpansionNode
    ) external onlyOwner {
        require(nodeId < MAX_NODES, "Higgs: invalid nodeId");

        uint256 mass = (yukawaCoupling * vev) / PRECISION;

        bool isNew = nodeMasses[nodeId].yukawaCoupling == 0;

        nodeMasses[nodeId] = NodeMass({
            nodeId:          nodeId,
            yukawaCoupling:  yukawaCoupling,
            cognitiveMass:   mass,
            lastUpdateBlock: block.number,
            isExpansionNode: isExpansionNode
        });

        if (isNew) {
            assignedNodeCount++;
        }

        emit NodeMassAssigned(nodeId, yukawaCoupling, mass, isExpansionNode);

        _updateAggregates();
    }

    /// @notice Batch-assign all 10 node masses using the golden-ratio cascade.
    ///         Called once during initialization to set the canonical mass hierarchy.
    ///
    ///         Yukawa couplings (× 1000):
    ///           Keter=1000, Chochmah=382, Binah=236, Chesed=382, Gevurah=236,
    ///           Tiferet=618, Netzach=382, Hod=236, Yesod=618, Malkuth=146
    ///
    ///         Expansion nodes (couple to H_u): Chochmah(1), Chesed(3), Netzach(6)
    ///         All others: neutral or constraint (couple to H_d)
    function assignAllMasses() external onlyOwner {
        //                         nodeId  yukawa            isExpansion
        _assignMass(                0,      YUKAWA_PHI_0,     false);     // Keter     — Crown (neutral)
        _assignMass(                1,      YUKAWA_PHI_N2,    true);      // Chochmah  — Expansion (intuition)
        _assignMass(                2,      YUKAWA_PHI_N3,    false);     // Binah     — Constraint (logic)
        _assignMass(                3,      YUKAWA_PHI_N2,    true);      // Chesed    — Expansion (creativity)
        _assignMass(                4,      YUKAWA_PHI_N3,    false);     // Gevurah   — Constraint (safety)
        _assignMass(                5,      YUKAWA_PHI_N1,    false);     // Tiferet   — Integrator (neutral)
        _assignMass(                6,      YUKAWA_PHI_N2,    true);      // Netzach   — Expansion (persistence)
        _assignMass(                7,      YUKAWA_PHI_N3,    false);     // Hod       — Constraint (communication)
        _assignMass(                8,      YUKAWA_PHI_N1,    false);     // Yesod     — Memory (neutral)
        _assignMass(                9,      YUKAWA_PHI_N4,    false);     // Malkuth   — Ground (neutral)

        assignedNodeCount = 10;

        _updateAggregates();
    }

    /// @dev Internal mass assignment helper — called by assignAllMasses().
    function _assignMass(uint8 nodeId, uint256 yukawa, bool isExpansion) internal {
        uint256 mass = (yukawa * vev) / PRECISION;
        nodeMasses[nodeId] = NodeMass({
            nodeId:          nodeId,
            yukawaCoupling:  yukawa,
            cognitiveMass:   mass,
            lastUpdateBlock: block.number,
            isExpansionNode: isExpansion
        });
        emit NodeMassAssigned(nodeId, yukawa, mass, isExpansion);
    }

    // ═════════════════════════════════════════════════════════════════════
    //  FIELD EVOLUTION (per-block)
    // ═════════════════════════════════════════════════════════════════════

    /// @notice Update the Higgs field value based on current Sephirot energies.
    ///         Called per-block by the kernel to track field evolution.
    ///         Automatically detects excitation events (deviations > 10% from VEV).
    /// @param newFieldValue  New field value (× 1000)
    function updateFieldValue(uint256 newFieldValue) external onlyKernel {
        uint256 oldValue = currentFieldValue;
        currentFieldValue = newFieldValue;

        emit FieldValueUpdated(oldValue, newFieldValue, block.number);

        // ── Excitation detection ─────────────────────────────────────────
        // |φ_h − v| as absolute deviation
        uint256 deviation;
        if (newFieldValue > vev) {
            deviation = newFieldValue - vev;
        } else {
            deviation = vev - newFieldValue;
        }

        // Deviation in basis points relative to VEV
        uint256 deviationBps = (deviation * 10000) / vev;

        if (deviationBps > EXCITATION_THRESHOLD_BPS) {
            // Excitation event — analogous to Higgs boson creation:
            // enough energy concentrated to excite the field above the VEV.
            uint256 energy = _computeExcitationEnergy(deviation);

            ExcitationEvent memory evt = ExcitationEvent({
                id:              totalExcitations,
                blockNumber:     block.number,
                timestamp:       block.timestamp,
                fieldDeviation:  deviation,
                deviationBps:    deviationBps,
                energyReleased:  energy
            });

            // Circular buffer: overwrite oldest entry when at capacity
            // to prevent unbounded storage growth (gas bomb prevention)
            if (excitations.length < MAX_EXCITATIONS) {
                excitations.push(evt);
            } else {
                // Overwrite oldest: use modular index
                uint256 index = totalExcitations % MAX_EXCITATIONS;
                excitations[index] = evt;
            }
            totalExcitations++;

            emit ExcitationDetected(totalExcitations - 1, deviation, energy);
        }
    }

    /// @dev Excitation energy:  E = λ × δ²  (simplified from quartic potential)
    ///      All values × 1000 precision.
    function _computeExcitationEnergy(uint256 deviation) internal view returns (uint256) {
        // lambda_ is × 1_000_000, deviation is × 1000
        // E = (lambda_ / 1_000_000) × (deviation / 1000)²  → result × 1000
        // E = lambda_ × deviation² / (1_000_000 × 1000 × 1000 / 1000)
        // E = lambda_ × deviation² / 1_000_000_000
        return (lambda_ * deviation * deviation) / 1_000_000_000;
    }

    // ═════════════════════════════════════════════════════════════════════
    //  MASS-WEIGHTED SUSY GRADIENT (F = ma)
    // ═════════════════════════════════════════════════════════════════════

    /// @notice Compute the rebalancing acceleration for a node given a force.
    ///         a = F / m  (Newton's second law applied to cognitive rebalancing)
    ///         Lighter nodes (constraint) get higher acceleration → correct faster.
    ///         Heavier nodes (expansion) get lower acceleration → resist change.
    /// @param nodeId  The Sephirot node ID (0-9)
    /// @param force   The SUSY rebalancing force (× 1000)
    /// @return acceleration  The resulting acceleration (× 1000)
    function computeAcceleration(uint8 nodeId, uint256 force) external view returns (uint256) {
        uint256 mass = nodeMasses[nodeId].cognitiveMass;
        if (mass == 0) return force;   // Massless → full acceleration (no inertia)
        return (force * PRECISION) / mass;
    }

    // ═════════════════════════════════════════════════════════════════════
    //  MASS GAP METRIC
    // ═════════════════════════════════════════════════════════════════════

    /// @notice Compute SUSY mass gap across all 3 SUSY pairs.
    ///         Mass gap = avg |m_expansion − m_constraint × φ| / v
    ///
    ///         A gap of 0 means perfect SUSY:  m_exp = m_con × φ
    ///         Non-zero gap indicates SUSY breaking — analogous to
    ///         the SUSY mass-gap problem in particle physics.
    function updateMassGap() external onlyKernel {
        // SUSY pairs: Chesed(3)/Gevurah(4), Chochmah(1)/Binah(2), Netzach(6)/Hod(7)
        uint8[3] memory expIds = [uint8(3), 1, 6];
        uint8[3] memory conIds = [uint8(4), 2, 7];

        uint256 gapSum = 0;
        for (uint8 i = 0; i < 3; i++) {
            uint256 mExp = nodeMasses[expIds[i]].cognitiveMass;
            uint256 mCon = nodeMasses[conIds[i]].cognitiveMass;
            uint256 target = (mCon * PHI) / PRECISION;  // Expected: m_exp = m_con × φ
            uint256 gap = mExp > target ? mExp - target : target - mExp;
            gapSum += gap;
        }

        massGapMetric = gapSum / 3;

        emit MassGapUpdated(massGapMetric);
    }

    // ═════════════════════════════════════════════════════════════════════
    //  PARAMETER GOVERNANCE
    // ═════════════════════════════════════════════════════════════════════

    /// @notice Update Higgs field parameters.  Recomputes VEV and all masses.
    ///         Requires owner (later: governance multisig).
    /// @param _mu       New mass parameter (× 1000)
    /// @param _lambda   New self-coupling (× 1_000_000)
    /// @param _tanBeta  New tan(β) (× 1000)
    function updateParameters(
        uint256 _mu,
        uint256 _lambda,
        uint256 _tanBeta
    ) external onlyOwner {
        require(_mu > 0,       "Higgs: mu must be positive");
        require(_lambda > 0,   "Higgs: lambda must be positive");
        require(_tanBeta > 0,  "Higgs: tanBeta must be positive");

        mu       = _mu;
        lambda_  = _lambda;
        tanBeta  = _tanBeta;

        // Recompute VEV from new parameters
        vev = _computeVEV(_mu, _lambda);

        // Recompute all cognitive masses with the new VEV
        for (uint8 i = 0; i < uint8(MAX_NODES); i++) {
            if (nodeMasses[i].yukawaCoupling > 0) {
                nodeMasses[i].cognitiveMass = (nodeMasses[i].yukawaCoupling * vev) / PRECISION;
                nodeMasses[i].lastUpdateBlock = block.number;
            }
        }
        _updateAggregates();

        emit ParametersUpdated(_mu, _lambda, vev);
    }

    // ═════════════════════════════════════════════════════════════════════
    //  QUERIES
    // ═════════════════════════════════════════════════════════════════════

    /// @notice Get a node's Yukawa coupling, cognitive mass, and expansion flag.
    function getNodeMass(uint8 nodeId) external view returns (
        uint256 yukawa,
        uint256 mass,
        bool    isExpansion
    ) {
        NodeMass storage nm = nodeMasses[nodeId];
        return (nm.yukawaCoupling, nm.cognitiveMass, nm.isExpansionNode);
    }

    /// @notice Get full Higgs field state in a single call.
    function getFieldState() external view returns (
        uint256 _vev,
        uint256 _currentField,
        uint256 _mu,
        uint256 _lambda,
        uint256 _tanBeta,
        uint256 _avgMass,
        uint256 _totalMass,
        uint256 _massGap,
        uint256 _totalExcitations
    ) {
        return (
            vev, currentFieldValue, mu, lambda_, tanBeta,
            avgCognitiveMass, totalCognitiveMass, massGapMetric, totalExcitations
        );
    }

    /// @notice Number of excitation events stored in the circular buffer.
    function getExcitationCount() external view returns (uint256) {
        return excitations.length;
    }

    /// @notice Total excitation events ever recorded (including overwritten ones).
    function getTotalExcitationCount() external view returns (uint256) {
        return totalExcitations;
    }

    /// @notice Get a page of recent excitation events from the circular buffer.
    /// @param offset  Start index within the stored excitations array.
    /// @param count   Maximum number of events to return.
    /// @return events Array of excitation events (may be shorter than count).
    function getExcitations(uint256 offset, uint256 count) external view returns (ExcitationEvent[] memory events) {
        uint256 stored = excitations.length;
        if (offset >= stored) {
            return new ExcitationEvent[](0);
        }
        uint256 end = offset + count;
        if (end > stored) end = stored;
        uint256 len = end - offset;
        events = new ExcitationEvent[](len);
        for (uint256 i = 0; i < len; i++) {
            events[i] = excitations[offset + i];
        }
    }

    /// @notice Compute the current potential energy V(φ_h).
    ///         V = −μ²φ² + λφ⁴   (all in scaled precision)
    ///         Returns |V| since Solidity has no signed integers.
    /// @return potentialAbs  Absolute value of V(φ_h) (× 1000)
    /// @return isNegative    true if V < 0 (field below VEV — expected at equilibrium)
    function getPotentialEnergy() external view returns (uint256 potentialAbs, bool isNegative) {
        // φ² = currentFieldValue² / PRECISION
        uint256 phi2 = (currentFieldValue * currentFieldValue) / PRECISION;
        // φ⁴ = φ² × φ² / PRECISION
        uint256 phi4 = (phi2 * phi2) / PRECISION;
        // −μ²φ²: mu is × 1000, so mu² is × 10⁶.  term1 = mu² × φ² / 10⁶ / PRECISION
        uint256 muSquared = (mu * mu);  // × 10⁶
        uint256 term1 = (muSquared * phi2) / (1_000_000 * PRECISION);
        // +λφ⁴: lambda_ is × 10⁶.  term2 = lambda_ × φ⁴ / 10⁶ / PRECISION²
        uint256 term2 = (lambda_ * phi4) / (1_000_000 * PRECISION * PRECISION);

        // V = −term1 + term2
        if (term2 >= term1) {
            return (term2 - term1, false);
        } else {
            return (term1 - term2, true);
        }
    }

    /// @notice Get the field deviation from VEV in basis points.
    function getFieldDeviationBps() external view returns (uint256) {
        uint256 deviation;
        if (currentFieldValue > vev) {
            deviation = currentFieldValue - vev;
        } else {
            deviation = vev - currentFieldValue;
        }
        return (deviation * 10000) / vev;
    }

    // ═════════════════════════════════════════════════════════════════════
    //  INTERNAL HELPERS
    // ═════════════════════════════════════════════════════════════════════

    /// @dev Compute VEV from mu and lambda:  v = μ / √(2λ)
    ///      mu is × 1000, lambda_ is × 1_000_000.
    ///      Result is × 1000.
    function _computeVEV(uint256 _mu, uint256 _lambda) internal pure returns (uint256) {
        // 2λ  (still × 10⁶)
        uint256 twoLambda = 2 * _lambda;
        // √(2λ) where 2λ is × 10⁶  →  √ result is × 10³
        uint256 sqrtTwoLambda = _isqrt(twoLambda);   // × 1000
        // v = μ / √(2λ)
        // μ is × 1000, sqrtTwoLambda is × 1000
        // v (× 1000) = μ × 1000 / sqrtTwoLambda
        return (_mu * PRECISION) / sqrtTwoLambda;
    }

    /// @dev Recompute aggregate statistics (avg and total mass).
    function _updateAggregates() internal {
        uint256 total = 0;
        uint256 count = 0;
        for (uint8 i = 0; i < uint8(MAX_NODES); i++) {
            if (nodeMasses[i].yukawaCoupling > 0) {
                total += nodeMasses[i].cognitiveMass;
                count++;
            }
        }
        totalCognitiveMass = total;
        avgCognitiveMass   = count > 0 ? total / count : 0;
    }

    /// @dev Integer square root via Babylonian (Newton-Raphson) method.
    ///      Returns floor(√x).
    function _isqrt(uint256 x) internal pure returns (uint256) {
        if (x == 0) return 0;
        uint256 z = (x + 1) / 2;
        uint256 y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
        return y;
    }
}
