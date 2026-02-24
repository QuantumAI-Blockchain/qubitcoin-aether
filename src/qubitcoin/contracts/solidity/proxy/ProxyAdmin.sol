// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ProxyAdmin — Owner of all QBC proxies with timelock governance
/// @notice Centralized admin for upgrading proxy implementations.
///         Deployed directly (NOT behind a proxy). Ownership can be
///         transferred to UpgradeGovernor for decentralized governance.
///         Supports immediate upgrades (owner-only) and timelocked upgrades
///         for governance-scheduled changes.
contract ProxyAdmin {
    address public owner;

    // ─── Timelock State ──────────────────────────────────────────────────
    /// @notice Minimum delay before a scheduled upgrade can execute (default 0 = no timelock)
    uint256 public minimumDelay;

    /// @notice Maximum age after which a scheduled upgrade expires
    uint256 public constant MAX_SCHEDULE_AGE = 30 days;

    struct ScheduledUpgrade {
        address proxy;
        address newImplementation;
        bytes   callData;          // optional initializer data (empty = upgradeTo only)
        uint256 scheduledAt;
        uint256 executeAfter;      // timestamp when upgrade becomes executable
        bool    executed;
        bool    canceled;
    }

    /// @notice All scheduled upgrades (upgradeId => ScheduledUpgrade)
    mapping(bytes32 => ScheduledUpgrade) public scheduledUpgrades;

    /// @notice Ordered list of schedule IDs for enumeration
    bytes32[] public scheduleIds;
    uint256 public totalScheduled;
    uint256 public totalExecutedScheduled;

    // ─── Events ──────────────────────────────────────────────────────────
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event UpgradeScheduled(
        bytes32 indexed upgradeId,
        address indexed proxy,
        address indexed newImplementation,
        uint256 executeAfter,
        uint256 delay
    );
    event ScheduledUpgradeExecuted(bytes32 indexed upgradeId, address indexed proxy, address indexed newImplementation);
    event ScheduledUpgradeCanceled(bytes32 indexed upgradeId);
    event MinimumDelayUpdated(uint256 oldDelay, uint256 newDelay);

    // ─── Modifiers ───────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "ProxyAdmin: not owner");
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────────
    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    // ─── Immediate Upgrades (owner-only, no timelock) ────────────────────

    /// @notice Upgrade a proxy to a new implementation (immediate, no timelock)
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

    // ─── Timelocked Upgrades (governance-friendly) ──────────────────────

    /// @notice Schedule an upgrade for future execution. The upgrade can only be
    ///         executed after `delay` seconds have passed. Emits UpgradeScheduled
    ///         for off-chain monitoring and governance transparency.
    /// @param proxy              The proxy to upgrade
    /// @param newImplementation  The new implementation contract
    /// @param data               Optional initializer calldata (empty for simple upgrade)
    /// @param delay              Seconds to wait before the upgrade can execute
    ///                           (must be >= minimumDelay)
    /// @return upgradeId         Unique identifier for this scheduled upgrade
    function scheduleUpgrade(
        address proxy,
        address newImplementation,
        bytes   calldata data,
        uint256 delay
    ) external onlyOwner returns (bytes32 upgradeId) {
        require(proxy != address(0), "ProxyAdmin: zero proxy");
        require(newImplementation != address(0), "ProxyAdmin: zero implementation");
        require(delay >= minimumDelay, "ProxyAdmin: delay below minimum");

        upgradeId = keccak256(abi.encodePacked(
            proxy, newImplementation, data, block.timestamp, totalScheduled
        ));
        require(scheduledUpgrades[upgradeId].scheduledAt == 0, "ProxyAdmin: already scheduled");

        uint256 executeAfter = block.timestamp + delay;

        scheduledUpgrades[upgradeId] = ScheduledUpgrade({
            proxy:              proxy,
            newImplementation:  newImplementation,
            callData:           data,
            scheduledAt:        block.timestamp,
            executeAfter:       executeAfter,
            executed:           false,
            canceled:           false
        });
        scheduleIds.push(upgradeId);
        totalScheduled++;

        emit UpgradeScheduled(upgradeId, proxy, newImplementation, executeAfter, delay);
    }

    /// @notice Execute a previously scheduled upgrade after its delay has passed
    /// @param upgradeId The scheduled upgrade to execute
    function executeScheduledUpgrade(bytes32 upgradeId) external onlyOwner {
        ScheduledUpgrade storage su = scheduledUpgrades[upgradeId];
        require(su.scheduledAt > 0, "ProxyAdmin: not scheduled");
        require(!su.executed, "ProxyAdmin: already executed");
        require(!su.canceled, "ProxyAdmin: canceled");
        require(block.timestamp >= su.executeAfter, "ProxyAdmin: timelock active");
        require(
            block.timestamp <= su.scheduledAt + MAX_SCHEDULE_AGE,
            "ProxyAdmin: schedule expired"
        );

        su.executed = true;
        totalExecutedScheduled++;

        if (su.callData.length > 0) {
            (bool ok, bytes memory ret) = su.proxy.call(
                abi.encodeWithSignature(
                    "upgradeToAndCall(address,bytes)",
                    su.newImplementation,
                    su.callData
                )
            );
            require(ok, _getRevertMsg(ret));
        } else {
            (bool ok, bytes memory ret) = su.proxy.call(
                abi.encodeWithSignature("upgradeTo(address)", su.newImplementation)
            );
            require(ok, _getRevertMsg(ret));
        }

        emit ScheduledUpgradeExecuted(upgradeId, su.proxy, su.newImplementation);
    }

    /// @notice Cancel a scheduled upgrade before it executes
    /// @param upgradeId The scheduled upgrade to cancel
    function cancelScheduledUpgrade(bytes32 upgradeId) external onlyOwner {
        ScheduledUpgrade storage su = scheduledUpgrades[upgradeId];
        require(su.scheduledAt > 0, "ProxyAdmin: not scheduled");
        require(!su.executed, "ProxyAdmin: already executed");
        require(!su.canceled, "ProxyAdmin: already canceled");

        su.canceled = true;
        emit ScheduledUpgradeCanceled(upgradeId);
    }

    // ─── Configuration ──────────────────────────────────────────────────

    /// @notice Set the minimum timelock delay for scheduled upgrades
    /// @param newDelay New minimum delay in seconds
    function setMinimumDelay(uint256 newDelay) external onlyOwner {
        emit MinimumDelayUpdated(minimumDelay, newDelay);
        minimumDelay = newDelay;
    }

    // ─── Ownership ──────────────────────────────────────────────────────

    /// @notice Transfer ownership of this ProxyAdmin
    /// @param newOwner The new owner (e.g., UpgradeGovernor contract)
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "ProxyAdmin: zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    // ─── Queries ────────────────────────────────────────────────────────

    /// @notice Get the implementation address of a proxy
    function getProxyImplementation(address proxy) external view returns (address) {
        (bool ok, bytes memory ret) = proxy.staticcall(
            abi.encodeWithSignature("implementation()")
        );
        require(ok, "ProxyAdmin: call failed");
        return abi.decode(ret, (address));
    }

    /// @notice Get details of a scheduled upgrade
    function getScheduledUpgrade(bytes32 upgradeId) external view returns (
        address proxy,
        address newImplementation,
        uint256 scheduledAt,
        uint256 executeAfter,
        bool    executed,
        bool    canceled,
        bool    expired
    ) {
        ScheduledUpgrade storage su = scheduledUpgrades[upgradeId];
        bool isExpired = su.scheduledAt > 0
            && block.timestamp > su.scheduledAt + MAX_SCHEDULE_AGE;
        return (
            su.proxy,
            su.newImplementation,
            su.scheduledAt,
            su.executeAfter,
            su.executed,
            su.canceled,
            isExpired
        );
    }

    /// @notice Get the number of scheduled upgrades
    function getScheduleCount() external view returns (uint256) {
        return scheduleIds.length;
    }

    // ─── Internal ───────────────────────────────────────────────────────

    /// @dev Extract revert reason from failed call
    function _getRevertMsg(bytes memory returnData) internal pure returns (string memory) {
        if (returnData.length < 68) return "ProxyAdmin: call reverted";
        assembly {
            returnData := add(returnData, 0x04)
        }
        return abi.decode(returnData, (string));
    }
}
