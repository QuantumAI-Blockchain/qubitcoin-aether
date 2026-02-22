// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title QBCProxy — ERC-1967 Transparent Upgradeable Proxy
/// @notice Delegates all calls to an implementation contract. Admin can upgrade
///         the implementation without losing state. Non-admin callers are
///         transparently forwarded to the implementation.
/// @dev    Storage slots follow EIP-1967 for tool compatibility (block explorers, etc.).
contract QBCProxy {
    // ─── ERC-1967 Storage Slots ────────────────────────────────────────
    /// bytes32(uint256(keccak256("eip1967.proxy.implementation")) - 1)
    bytes32 private constant _IMPLEMENTATION_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    /// bytes32(uint256(keccak256("eip1967.proxy.admin")) - 1)
    bytes32 private constant _ADMIN_SLOT =
        0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

    // ─── Events ────────────────────────────────────────────────────────
    event Upgraded(address indexed implementation);
    event AdminChanged(address indexed previousAdmin, address indexed newAdmin);

    // ─── Constructor ───────────────────────────────────────────────────
    /// @param impl    Address of the initial implementation contract
    /// @param admin   Address that can upgrade the proxy (typically ProxyAdmin)
    /// @param initData Encoded initializer call (e.g., abi.encodeCall(Contract.initialize, (args)))
    constructor(address impl, address admin, bytes memory initData) {
        require(impl != address(0), "QBCProxy: zero implementation");
        require(admin != address(0), "QBCProxy: zero admin");

        _setImplementation(impl);
        _setAdmin(admin);

        if (initData.length > 0) {
            (bool ok, bytes memory ret) = impl.delegatecall(initData);
            if (!ok) {
                // Bubble up revert reason
                if (ret.length > 0) {
                    assembly {
                        revert(add(ret, 0x20), mload(ret))
                    }
                }
                revert("QBCProxy: init failed");
            }
        }

        emit Upgraded(impl);
        emit AdminChanged(address(0), admin);
    }

    // ─── Fallback ──────────────────────────────────────────────────────
    /// @dev Transparent proxy pattern: admin calls hit admin functions,
    ///      all other callers are forwarded to the implementation.
    fallback() external payable {
        if (msg.sender == _getAdmin()) {
            // Admin dispatch — decode selector for admin functions
            bytes4 sel = msg.sig;

            if (sel == this.upgradeTo.selector) {
                address newImpl = abi.decode(msg.data[4:], (address));
                _upgradeTo(newImpl);
            } else if (sel == this.upgradeToAndCall.selector) {
                (address newImpl, bytes memory data) = abi.decode(msg.data[4:], (address, bytes));
                _upgradeToAndCall(newImpl, data);
            } else if (sel == this.changeAdmin.selector) {
                address newAdmin = abi.decode(msg.data[4:], (address));
                _changeAdmin(newAdmin);
            } else if (sel == this.implementation.selector) {
                address impl = _getImplementation();
                assembly {
                    mstore(0x00, impl)
                    return(0x00, 0x20)
                }
            } else if (sel == this.admin.selector) {
                address adm = _getAdmin();
                assembly {
                    mstore(0x00, adm)
                    return(0x00, 0x20)
                }
            } else {
                revert("QBCProxy: unknown admin function");
            }
        } else {
            // Non-admin — delegate to implementation
            _delegate(_getImplementation());
        }
    }

    receive() external payable {
        _delegate(_getImplementation());
    }

    // ─── Admin Interface (selectors only, dispatched via fallback) ────
    function upgradeTo(address) external { revert("QBCProxy: use fallback"); }
    function upgradeToAndCall(address, bytes calldata) external { revert("QBCProxy: use fallback"); }
    function changeAdmin(address) external { revert("QBCProxy: use fallback"); }
    function implementation() external view returns (address) { revert("QBCProxy: use fallback"); }
    function admin() external view returns (address) { revert("QBCProxy: use fallback"); }

    // ─── Internal ──────────────────────────────────────────────────────
    function _delegate(address impl) internal {
        assembly {
            calldatacopy(0, 0, calldatasize())
            let result := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch result
            case 0 { revert(0, returndatasize()) }
            default { return(0, returndatasize()) }
        }
    }

    function _upgradeTo(address newImpl) internal {
        require(newImpl != address(0), "QBCProxy: zero implementation");
        _setImplementation(newImpl);
        emit Upgraded(newImpl);
    }

    function _upgradeToAndCall(address newImpl, bytes memory data) internal {
        _upgradeTo(newImpl);
        if (data.length > 0) {
            (bool ok, bytes memory ret) = newImpl.delegatecall(data);
            if (!ok) {
                if (ret.length > 0) {
                    assembly {
                        revert(add(ret, 0x20), mload(ret))
                    }
                }
                revert("QBCProxy: call failed");
            }
        }
    }

    function _changeAdmin(address newAdmin) internal {
        require(newAdmin != address(0), "QBCProxy: zero admin");
        address prev = _getAdmin();
        _setAdmin(newAdmin);
        emit AdminChanged(prev, newAdmin);
    }

    function _getImplementation() internal view returns (address impl) {
        bytes32 slot = _IMPLEMENTATION_SLOT;
        assembly {
            impl := sload(slot)
        }
    }

    function _setImplementation(address impl) internal {
        bytes32 slot = _IMPLEMENTATION_SLOT;
        assembly {
            sstore(slot, impl)
        }
    }

    function _getAdmin() internal view returns (address adm) {
        bytes32 slot = _ADMIN_SLOT;
        assembly {
            adm := sload(slot)
        }
    }

    function _setAdmin(address adm) internal {
        bytes32 slot = _ADMIN_SLOT;
        assembly {
            sstore(slot, adm)
        }
    }
}
