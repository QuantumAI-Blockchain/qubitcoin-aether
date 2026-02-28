// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IHiggsField — Interface for HiggsField contract queries
/// @notice Used by SUSYEngine for mass-aware gradient rebalancing.
///         Provides access to cognitive masses derived from the Higgs mechanism.
interface IHiggsField {
    /// @notice Get the cognitive mass of a Sephirot node
    /// @param nodeId The Sephirot node ID (0-9)
    /// @return yukawa The Yukawa coupling constant
    /// @return mass The computed cognitive mass (× PRECISION)
    /// @return isExpansion Whether this node is an expansion node
    function getNodeMass(uint8 nodeId) external view returns (uint256 yukawa, uint256 mass, bool isExpansion);

    /// @notice Compute acceleration for a node given an applied force
    /// @param nodeId The Sephirot node ID
    /// @param force The applied force (× PRECISION)
    /// @return acceleration The resulting acceleration (F/m, × PRECISION)
    function computeAcceleration(uint8 nodeId, uint256 force) external view returns (uint256);

    /// @notice Get the full Higgs field state
    /// @return vev Vacuum expectation value (× 1000)
    /// @return currentField Current field value φ_h (× 1000)
    /// @return mu Mass parameter (× 1000)
    /// @return lambda_ Self-coupling (× 1_000_000)
    /// @return tanBeta Tangent of beta angle (× 1000)
    /// @return avgMass Average cognitive mass (× 1000)
    /// @return totalMass Sum of all cognitive masses (× 1000)
    /// @return massGap Gap between heaviest and lightest (× 1000)
    /// @return totalExcitations Number of field excitation events
    function getFieldState() external view returns (
        uint256 vev,
        uint256 currentField,
        uint256 mu,
        uint256 lambda_,
        uint256 tanBeta,
        uint256 avgMass,
        uint256 totalMass,
        uint256 massGap,
        uint256 totalExcitations
    );
}
