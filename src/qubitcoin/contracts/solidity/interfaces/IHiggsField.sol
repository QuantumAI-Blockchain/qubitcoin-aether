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
    /// @return vev Vacuum expectation value
    /// @return tanBeta Tangent of beta angle (× 1000)
    /// @return totalMass Sum of all cognitive masses
    /// @return heaviestNode ID of heaviest node
    /// @return lightestNode ID of lightest node
    /// @return heaviestMass Mass of heaviest node
    /// @return lightestMass Mass of lightest node
    /// @return massRatio Heaviest/lightest mass ratio (× 1000)
    /// @return lastUpdate Block number of last update
    function getFieldState() external view returns (
        uint256 vev,
        uint256 tanBeta,
        uint256 totalMass,
        uint256 heaviestNode,
        uint256 lightestNode,
        uint256 heaviestMass,
        uint256 lightestMass,
        uint256 massRatio,
        uint256 lastUpdate
    );
}
