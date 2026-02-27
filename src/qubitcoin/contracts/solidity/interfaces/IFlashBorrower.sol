// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IFlashBorrower — Callback interface for QUSD flash loan receivers
/// @notice Contracts that borrow via QUSD flash loans must implement this interface
interface IFlashBorrower {
    /// @notice Called by QUSD flash loan contract after transferring the loan amount
    /// @param initiator The address that initiated the flash loan
    /// @param amount The amount of QUSD borrowed
    /// @param fee The fee that must be repaid on top of the principal
    /// @param data Arbitrary calldata passed by the initiator
    /// @return Must return keccak256("IFlashBorrower.onFlashLoan") to confirm success
    function onFlashLoan(
        address initiator,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external returns (bytes32);
}
