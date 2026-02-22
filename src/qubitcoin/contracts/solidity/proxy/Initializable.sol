// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title Initializable — Proxy-safe initialization guard
/// @notice Replaces constructors for contracts deployed behind QBCProxy.
///         Uses a dedicated storage slot to avoid collisions with implementation state.
abstract contract Initializable {
    /// @dev Storage slot: keccak256("qubitcoin.initializable.initialized") - 1
    bytes32 private constant _INITIALIZED_SLOT =
        0x4c943a984a6327bfee4b7014e4e1a7587ed3fee9271a34de34eb1a3a0b0c44c6;

    /// @dev Prevents a function from being called more than once
    modifier initializer() {
        require(!_isInitialized(), "Initializable: already initialized");
        _setInitialized(true);
        _;
    }

    function _isInitialized() internal view returns (bool initialized_) {
        bytes32 slot = _INITIALIZED_SLOT;
        assembly {
            initialized_ := sload(slot)
        }
    }

    function _setInitialized(bool value) private {
        bytes32 slot = _INITIALIZED_SLOT;
        assembly {
            sstore(slot, value)
        }
    }
}
