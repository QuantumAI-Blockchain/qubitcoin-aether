// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title Initializable — Proxy-safe initialization guard
/// @notice Replaces constructors for contracts deployed behind QBCProxy.
///         Uses a dedicated storage slot to avoid collisions with implementation state.
///
/// @dev    Security: implementation contracts MUST call `_disableInitializers()` in
///         their constructor to prevent an attacker from initializing the bare
///         implementation (bypassing the proxy) and taking ownership.
///         Pattern:
///           constructor() { _disableInitializers(); }
abstract contract Initializable {
    /// @dev Storage slot: keccak256("qubitcoin.initializable.initialized") - 1
    bytes32 private constant _INITIALIZED_SLOT =
        0x4c943a984a6327bfee4b7014e4e1a7587ed3fee9271a34de34eb1a3a0b0c44c6;

    /// @dev Storage slot: keccak256("qubitcoin.initializable.disabled") - 1
    bytes32 private constant _DISABLED_SLOT =
        0x3e3d8fe2e22e8e16ac8e5a3a0e5b1c4e9d7d6f5a4b3c2d1e0f9a8b7c6d5e4f3a;

    /// @dev Prevents a function from being called more than once
    modifier initializer() {
        require(!_isDisabled(), "Initializable: disabled on implementation");
        require(!_isInitialized(), "Initializable: already initialized");
        _setInitialized(true);
        _;
    }

    /// @notice Called in the constructor of implementation contracts to permanently
    ///         block direct initialization of the implementation (not the proxy).
    function _disableInitializers() internal {
        bytes32 slot = _DISABLED_SLOT;
        assembly {
            sstore(slot, 1)
        }
        // Also mark as initialized so initializer() reverts on implementation
        _setInitialized(true);
    }

    function _isInitialized() internal view returns (bool initialized_) {
        bytes32 slot = _INITIALIZED_SLOT;
        assembly {
            initialized_ := sload(slot)
        }
    }

    function _isDisabled() internal view returns (bool disabled_) {
        bytes32 slot = _DISABLED_SLOT;
        assembly {
            disabled_ := sload(slot)
        }
    }

    function _setInitialized(bool value) private {
        bytes32 slot = _INITIALIZED_SLOT;
        assembly {
            sstore(slot, value)
        }
    }
}
