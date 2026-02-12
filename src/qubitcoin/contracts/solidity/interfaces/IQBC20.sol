// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IQBC20 — QBC-20 Fungible Token Standard (ERC-20 Compatible)
/// @notice Standard interface for fungible tokens on the Qubitcoin QVM
interface IQBC20 {
    /// @notice Returns the total token supply
    function totalSupply() external view returns (uint256);

    /// @notice Returns the balance of `account`
    function balanceOf(address account) external view returns (uint256);

    /// @notice Transfers `amount` tokens to `to`
    function transfer(address to, uint256 amount) external returns (bool);

    /// @notice Returns the remaining allowance `spender` can spend on behalf of `owner`
    function allowance(address owner, address spender) external view returns (uint256);

    /// @notice Approves `spender` to spend `amount` on behalf of caller
    function approve(address spender, uint256 amount) external returns (bool);

    /// @notice Transfers `amount` from `from` to `to` using allowance
    function transferFrom(address from, address to, uint256 amount) external returns (bool);

    /// @notice Returns the token name
    function name() external view returns (string memory);

    /// @notice Returns the token symbol
    function symbol() external view returns (string memory);

    /// @notice Returns the number of decimals
    function decimals() external view returns (uint8);

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
}
