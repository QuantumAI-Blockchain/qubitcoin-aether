// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IDebtLedger — Interface for QUSD Debt Ledger
/// @notice Allows QUSD token and Reserve contracts to record debt and payback events
interface IDebtLedger {
    /// @notice Record new debt when QUSD is minted (called by QUSD token)
    /// @param amount Amount of QUSD minted (8 decimals)
    function recordDebt(uint256 amount) external;

    /// @notice Record debt against a specific account (called by QUSD token on mint)
    /// @param account The account receiving the minted QUSD
    /// @param amount Amount of QUSD minted (8 decimals)
    function recordAccountDebt(address account, uint256 amount) external;

    /// @notice Record a reserve deposit as a payback event (called by Reserve)
    /// @param usdValue USD value of the deposit (8 decimals)
    function recordPayback(uint256 usdValue) external;
}
