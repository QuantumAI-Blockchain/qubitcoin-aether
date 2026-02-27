// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IQUSD — Interface for the QUSD Stablecoin Token
/// @notice Allows authorized contracts (Stabilizer, Reserve) to mint and burn QUSD
interface IQUSD {
    /// @notice Mint new QUSD tokens (owner/authorized only)
    /// @param to Recipient address
    /// @param amount Amount to mint (8 decimals)
    function mint(address to, uint256 amount) external;

    /// @notice Burn QUSD tokens from the caller's balance
    /// @param amount Amount to burn (8 decimals)
    function burn(uint256 amount) external;

    /// @notice Get the balance of an account
    /// @param account Address to query
    /// @return Balance in 8 decimals
    function balanceOf(address account) external view returns (uint256);

    /// @notice Get the total supply
    /// @return Total QUSD supply in 8 decimals
    function totalSupply() external view returns (uint256);

    /// @notice Transfer tokens
    /// @param to Recipient
    /// @param amount Amount to transfer
    /// @return success
    function transfer(address to, uint256 amount) external returns (bool);

    /// @notice Transfer tokens on behalf of another address
    /// @param from Sender
    /// @param to Recipient
    /// @param amount Amount to transfer
    /// @return success
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}
