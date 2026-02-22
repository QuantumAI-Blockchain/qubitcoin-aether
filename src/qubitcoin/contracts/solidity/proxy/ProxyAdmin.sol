// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ProxyAdmin — Owner of all QBC proxies
/// @notice Centralized admin for upgrading proxy implementations.
///         Deployed directly (NOT behind a proxy). Ownership can be
///         transferred to UpgradeGovernor for decentralized governance.
contract ProxyAdmin {
    address public owner;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "ProxyAdmin: not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    /// @notice Upgrade a proxy to a new implementation
    /// @param proxy The proxy contract address
    /// @param newImplementation The new implementation address
    function upgrade(address proxy, address newImplementation) external onlyOwner {
        // Call proxy.upgradeTo(newImplementation) — dispatched via fallback
        (bool ok, bytes memory ret) = proxy.call(
            abi.encodeWithSignature("upgradeTo(address)", newImplementation)
        );
        require(ok, _getRevertMsg(ret));
    }

    /// @notice Upgrade a proxy and call an initialization function on the new implementation
    /// @param proxy The proxy contract address
    /// @param newImplementation The new implementation address
    /// @param data Encoded function call for the new implementation
    function upgradeAndCall(address proxy, address newImplementation, bytes calldata data) external onlyOwner {
        (bool ok, bytes memory ret) = proxy.call(
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", newImplementation, data)
        );
        require(ok, _getRevertMsg(ret));
    }

    /// @notice Transfer ownership of this ProxyAdmin
    /// @param newOwner The new owner (e.g., UpgradeGovernor contract)
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "ProxyAdmin: zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /// @notice Get the implementation address of a proxy
    function getProxyImplementation(address proxy) external view returns (address) {
        (bool ok, bytes memory ret) = proxy.staticcall(
            abi.encodeWithSignature("implementation()")
        );
        require(ok, "ProxyAdmin: call failed");
        return abi.decode(ret, (address));
    }

    /// @dev Extract revert reason from failed call
    function _getRevertMsg(bytes memory returnData) internal pure returns (string memory) {
        if (returnData.length < 68) return "ProxyAdmin: call reverted";
        assembly {
            returnData := add(returnData, 0x04)
        }
        return abi.decode(returnData, (string));
    }
}
