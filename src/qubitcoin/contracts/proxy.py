"""
Contract Upgrade Patterns — Transparent Proxy for Qubitcoin QVM

Implements EIP-1967 compatible proxy pattern for upgradeable smart contracts.
The proxy stores an implementation address and admin address in well-known
storage slots, then delegates all calls to the implementation contract.

Storage layout (EIP-1967 slots):
  IMPLEMENTATION_SLOT = keccak256("eip1967.proxy.implementation") - 1
  ADMIN_SLOT          = keccak256("eip1967.proxy.admin") - 1

Upgrade flow:
  1. Deploy implementation contract (pure logic, no constructor state)
  2. Deploy proxy pointing at implementation + set admin
  3. Users interact with proxy address (state lives here)
  4. Admin calls upgrade(new_impl) → proxy points at new logic, state preserved
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# EIP-1967 storage slots (deterministic, collision-resistant)
_IMPL_PREIMAGE = b"eip1967.proxy.implementation"
_ADMIN_PREIMAGE = b"eip1967.proxy.admin"

IMPLEMENTATION_SLOT: int = (
    int.from_bytes(hashlib.sha3_256(_IMPL_PREIMAGE).digest(), "big") - 1
)
ADMIN_SLOT: int = (
    int.from_bytes(hashlib.sha3_256(_ADMIN_PREIMAGE).digest(), "big") - 1
)


class UpgradeEventType(Enum):
    """Types of proxy upgrade events."""
    DEPLOYED = "deployed"
    UPGRADED = "upgraded"
    ADMIN_CHANGED = "admin_changed"
    UPGRADE_SCHEDULED = "upgrade_scheduled"
    SCHEDULED_EXECUTED = "scheduled_executed"
    SCHEDULED_CANCELED = "scheduled_canceled"


@dataclass
class UpgradeEvent:
    """Immutable record of a proxy lifecycle event."""
    proxy_address: str
    event_type: UpgradeEventType
    old_implementation: Optional[str]
    new_implementation: str
    admin: str
    block_height: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "proxy_address": self.proxy_address,
            "event_type": self.event_type.value,
            "old_implementation": self.old_implementation,
            "new_implementation": self.new_implementation,
            "admin": self.admin,
            "block_height": self.block_height,
            "timestamp": self.timestamp,
        }


@dataclass
class ProxyRecord:
    """Tracks a deployed proxy and its current implementation."""
    proxy_address: str
    implementation_address: str
    admin_address: str
    created_at: float
    block_height: int
    version: int = 1
    upgrade_history: List[UpgradeEvent] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "proxy_address": self.proxy_address,
            "implementation_address": self.implementation_address,
            "admin_address": self.admin_address,
            "created_at": self.created_at,
            "block_height": self.block_height,
            "version": self.version,
            "upgrade_count": len(self.upgrade_history),
            "history": [e.to_dict() for e in self.upgrade_history],
        }


@dataclass
class ScheduledUpgrade:
    """A timelocked upgrade waiting for execution."""
    upgrade_id: str
    proxy_address: str
    new_implementation: str
    call_data: Optional[bytes]
    scheduled_at: float
    execute_after: float
    admin: str
    block_height: int
    executed: bool = False
    canceled: bool = False

    def to_dict(self) -> Dict:
        return {
            "upgrade_id": self.upgrade_id,
            "proxy_address": self.proxy_address,
            "new_implementation": self.new_implementation,
            "has_call_data": self.call_data is not None and len(self.call_data) > 0,
            "scheduled_at": self.scheduled_at,
            "execute_after": self.execute_after,
            "admin": self.admin,
            "block_height": self.block_height,
            "executed": self.executed,
            "canceled": self.canceled,
        }


# Maximum age of a scheduled upgrade before it expires (30 days)
MAX_SCHEDULE_AGE: float = 30 * 24 * 3600.0


class ProxyRegistry:
    """
    Registry for transparent proxy contracts.

    Tracks proxy→implementation mappings, enforces admin-only upgrades,
    and maintains an immutable upgrade audit trail.
    """

    def __init__(self) -> None:
        self._proxies: Dict[str, ProxyRecord] = {}
        self._impl_to_proxies: Dict[str, List[str]] = {}
        self._scheduled_upgrades: Dict[str, ScheduledUpgrade] = {}
        self._minimum_delay: float = 0.0
        logger.info("ProxyRegistry initialised")

    # ------------------------------------------------------------------
    # Deploy
    # ------------------------------------------------------------------

    def deploy_proxy(
        self,
        proxy_address: str,
        implementation_address: str,
        admin_address: str,
        block_height: int = 0,
    ) -> ProxyRecord:
        """
        Register a new proxy contract.

        Args:
            proxy_address: Address where the proxy lives (users call this).
            implementation_address: Address of the logic contract.
            admin_address: Address authorised to upgrade.
            block_height: Block at which deployment occurs.

        Returns:
            The newly created ProxyRecord.

        Raises:
            ValueError: If proxy_address is already registered.
        """
        if proxy_address in self._proxies:
            raise ValueError(f"Proxy already exists: {proxy_address}")

        if not implementation_address:
            raise ValueError("Implementation address required")

        now = time.time()
        event = UpgradeEvent(
            proxy_address=proxy_address,
            event_type=UpgradeEventType.DEPLOYED,
            old_implementation=None,
            new_implementation=implementation_address,
            admin=admin_address,
            block_height=block_height,
            timestamp=now,
        )

        record = ProxyRecord(
            proxy_address=proxy_address,
            implementation_address=implementation_address,
            admin_address=admin_address,
            created_at=now,
            block_height=block_height,
            version=1,
            upgrade_history=[event],
        )
        self._proxies[proxy_address] = record
        self._impl_to_proxies.setdefault(implementation_address, []).append(
            proxy_address
        )

        logger.info(
            f"Proxy deployed: {proxy_address} → {implementation_address} "
            f"(admin={admin_address})"
        )
        return record

    # ------------------------------------------------------------------
    # Upgrade
    # ------------------------------------------------------------------

    def upgrade(
        self,
        proxy_address: str,
        new_implementation: str,
        caller: str,
        block_height: int = 0,
    ) -> bool:
        """
        Upgrade a proxy to a new implementation.

        Only the current admin may call this. The proxy address stays the
        same; all storage is preserved. Only the logic pointer changes.

        Args:
            proxy_address: Proxy to upgrade.
            new_implementation: New logic contract address.
            caller: Address requesting the upgrade.
            block_height: Block at which upgrade occurs.

        Returns:
            True on success, False if caller is not admin or proxy not found.
        """
        record = self._proxies.get(proxy_address)
        if record is None:
            logger.warning(f"Upgrade failed: proxy not found {proxy_address}")
            return False

        if record.admin_address != caller:
            logger.warning(
                f"Upgrade denied: {caller} is not admin of {proxy_address}"
            )
            return False

        if not new_implementation:
            logger.warning("Upgrade denied: empty implementation address")
            return False

        if record.implementation_address == new_implementation:
            logger.warning("Upgrade skipped: same implementation")
            return False

        old_impl = record.implementation_address
        event = UpgradeEvent(
            proxy_address=proxy_address,
            event_type=UpgradeEventType.UPGRADED,
            old_implementation=old_impl,
            new_implementation=new_implementation,
            admin=caller,
            block_height=block_height,
        )

        # Update mapping
        if old_impl in self._impl_to_proxies:
            refs = self._impl_to_proxies[old_impl]
            if proxy_address in refs:
                refs.remove(proxy_address)
        self._impl_to_proxies.setdefault(new_implementation, []).append(
            proxy_address
        )

        record.implementation_address = new_implementation
        record.version += 1
        record.upgrade_history.append(event)

        logger.info(
            f"Proxy upgraded: {proxy_address} v{record.version} "
            f"{old_impl} → {new_implementation}"
        )
        return True

    # ------------------------------------------------------------------
    # Upgrade and call
    # ------------------------------------------------------------------

    def upgrade_and_call(
        self,
        proxy_address: str,
        new_implementation: str,
        call_data: bytes,
        caller: str,
        block_height: int = 0,
    ) -> bool:
        """
        Upgrade a proxy to a new implementation and call an initializer.

        Combines upgrade + delegatecall to the new implementation with the
        provided call data. Used when the new implementation requires
        re-initialization (e.g., adding new state variables).

        Args:
            proxy_address: Proxy to upgrade.
            new_implementation: New logic contract address.
            call_data: Encoded initializer function call.
            caller: Address requesting the upgrade (must be admin).
            block_height: Block at which upgrade occurs.

        Returns:
            True on success, False if caller is not admin or proxy not found.
        """
        result = self.upgrade(proxy_address, new_implementation, caller, block_height)
        if result and call_data:
            logger.info(
                f"Proxy upgrade-and-call: {proxy_address} → "
                f"{new_implementation} with {len(call_data)} bytes calldata"
            )
        return result

    # ------------------------------------------------------------------
    # Scheduled (timelocked) upgrades
    # ------------------------------------------------------------------

    def set_minimum_delay(self, delay: float) -> None:
        """Set the minimum timelock delay for scheduled upgrades (seconds)."""
        self._minimum_delay = delay
        logger.info(f"Minimum upgrade delay set to {delay}s")

    def get_minimum_delay(self) -> float:
        """Return the current minimum upgrade delay."""
        return self._minimum_delay

    def schedule_upgrade(
        self,
        proxy_address: str,
        new_implementation: str,
        caller: str,
        delay: float,
        call_data: Optional[bytes] = None,
        block_height: int = 0,
    ) -> Optional[str]:
        """
        Schedule a timelocked upgrade for future execution.

        The upgrade cannot be executed until `delay` seconds have passed.
        Emits an UPGRADE_SCHEDULED event in the proxy's history.

        Args:
            proxy_address: Proxy to upgrade.
            new_implementation: New logic contract address.
            caller: Address requesting the schedule (must be admin).
            delay: Seconds to wait before execution is allowed.
            call_data: Optional initializer calldata.
            block_height: Block at which schedule occurs.

        Returns:
            The upgrade_id string on success, None on failure.
        """
        record = self._proxies.get(proxy_address)
        if record is None:
            logger.warning(f"Schedule failed: proxy not found {proxy_address}")
            return None

        if record.admin_address != caller:
            logger.warning(
                f"Schedule denied: {caller} is not admin of {proxy_address}"
            )
            return None

        if not new_implementation:
            logger.warning("Schedule denied: empty implementation address")
            return None

        if delay < self._minimum_delay:
            logger.warning(
                f"Schedule denied: delay {delay}s below minimum {self._minimum_delay}s"
            )
            return None

        now = time.time()
        execute_after = now + delay

        # Generate a unique upgrade ID
        raw = f"{proxy_address}:{new_implementation}:{now}:{block_height}"
        upgrade_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

        scheduled = ScheduledUpgrade(
            upgrade_id=upgrade_id,
            proxy_address=proxy_address,
            new_implementation=new_implementation,
            call_data=call_data,
            scheduled_at=now,
            execute_after=execute_after,
            admin=caller,
            block_height=block_height,
        )
        self._scheduled_upgrades[upgrade_id] = scheduled

        # Record in proxy history
        event = UpgradeEvent(
            proxy_address=proxy_address,
            event_type=UpgradeEventType.UPGRADE_SCHEDULED,
            old_implementation=record.implementation_address,
            new_implementation=new_implementation,
            admin=caller,
            block_height=block_height,
            timestamp=now,
        )
        record.upgrade_history.append(event)

        logger.info(
            f"Upgrade scheduled: {proxy_address} → {new_implementation} "
            f"(execute after {execute_after}, id={upgrade_id})"
        )
        return upgrade_id

    def execute_scheduled_upgrade(
        self,
        upgrade_id: str,
        caller: str,
        current_time: Optional[float] = None,
    ) -> bool:
        """
        Execute a previously scheduled upgrade after its delay has passed.

        Args:
            upgrade_id: The scheduled upgrade to execute.
            caller: Address executing (must be admin of the proxy).
            current_time: Override for current time (for testing). Defaults to time.time().

        Returns:
            True on success.
        """
        scheduled = self._scheduled_upgrades.get(upgrade_id)
        if scheduled is None:
            logger.warning(f"Execute failed: scheduled upgrade not found {upgrade_id}")
            return False

        if scheduled.executed:
            logger.warning(f"Execute failed: already executed {upgrade_id}")
            return False

        if scheduled.canceled:
            logger.warning(f"Execute failed: canceled {upgrade_id}")
            return False

        now = current_time if current_time is not None else time.time()

        if now < scheduled.execute_after:
            logger.warning(
                f"Execute failed: timelock active for {upgrade_id} "
                f"(now={now}, execute_after={scheduled.execute_after})"
            )
            return False

        if now > scheduled.scheduled_at + MAX_SCHEDULE_AGE:
            logger.warning(f"Execute failed: scheduled upgrade expired {upgrade_id}")
            return False

        record = self._proxies.get(scheduled.proxy_address)
        if record is None:
            return False

        if record.admin_address != caller:
            logger.warning(
                f"Execute denied: {caller} is not admin of {scheduled.proxy_address}"
            )
            return False

        # Perform the upgrade
        if scheduled.call_data:
            result = self.upgrade_and_call(
                scheduled.proxy_address,
                scheduled.new_implementation,
                scheduled.call_data,
                caller,
                scheduled.block_height,
            )
        else:
            result = self.upgrade(
                scheduled.proxy_address,
                scheduled.new_implementation,
                caller,
                scheduled.block_height,
            )

        if result:
            scheduled.executed = True
            logger.info(f"Scheduled upgrade executed: {upgrade_id}")
        return result

    def cancel_scheduled_upgrade(
        self,
        upgrade_id: str,
        caller: str,
    ) -> bool:
        """
        Cancel a scheduled upgrade before it executes.

        Args:
            upgrade_id: The scheduled upgrade to cancel.
            caller: Address requesting cancellation (must be admin).

        Returns:
            True on success.
        """
        scheduled = self._scheduled_upgrades.get(upgrade_id)
        if scheduled is None:
            return False

        if scheduled.executed:
            return False

        if scheduled.canceled:
            return False

        record = self._proxies.get(scheduled.proxy_address)
        if record is None:
            return False

        if record.admin_address != caller:
            return False

        scheduled.canceled = True

        event = UpgradeEvent(
            proxy_address=scheduled.proxy_address,
            event_type=UpgradeEventType.SCHEDULED_CANCELED,
            old_implementation=record.implementation_address,
            new_implementation=scheduled.new_implementation,
            admin=caller,
            block_height=scheduled.block_height,
        )
        record.upgrade_history.append(event)

        logger.info(f"Scheduled upgrade canceled: {upgrade_id}")
        return True

    def get_scheduled_upgrade(self, upgrade_id: str) -> Optional[ScheduledUpgrade]:
        """Get a scheduled upgrade by ID."""
        return self._scheduled_upgrades.get(upgrade_id)

    def list_scheduled_upgrades(
        self, proxy_address: Optional[str] = None
    ) -> List[Dict]:
        """List scheduled upgrades, optionally filtered by proxy."""
        results = []
        for su in self._scheduled_upgrades.values():
            if proxy_address and su.proxy_address != proxy_address:
                continue
            results.append(su.to_dict())
        return results

    # ------------------------------------------------------------------
    # Admin transfer
    # ------------------------------------------------------------------

    def change_admin(
        self,
        proxy_address: str,
        new_admin: str,
        caller: str,
        block_height: int = 0,
    ) -> bool:
        """
        Transfer admin rights to a new address.

        Args:
            proxy_address: Proxy whose admin is being changed.
            new_admin: New admin address.
            caller: Current admin requesting the change.
            block_height: Block at which change occurs.

        Returns:
            True on success.
        """
        record = self._proxies.get(proxy_address)
        if record is None:
            return False

        if record.admin_address != caller:
            logger.warning(
                f"Admin change denied: {caller} is not admin of {proxy_address}"
            )
            return False

        if not new_admin:
            return False

        event = UpgradeEvent(
            proxy_address=proxy_address,
            event_type=UpgradeEventType.ADMIN_CHANGED,
            old_implementation=record.implementation_address,
            new_implementation=record.implementation_address,
            admin=new_admin,
            block_height=block_height,
        )

        record.admin_address = new_admin
        record.upgrade_history.append(event)

        logger.info(
            f"Proxy admin changed: {proxy_address} → {new_admin}"
        )
        return True

    # ------------------------------------------------------------------
    # Resolution (used by StateManager / QVM)
    # ------------------------------------------------------------------

    def resolve_implementation(self, proxy_address: str) -> Optional[str]:
        """
        Resolve a proxy address to its current implementation.

        If the address is not a proxy, returns None so the caller can
        fall back to direct bytecode lookup.
        """
        record = self._proxies.get(proxy_address)
        if record is None:
            return None
        return record.implementation_address

    def is_proxy(self, address: str) -> bool:
        """Check whether an address is a registered proxy."""
        return address in self._proxies

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_proxy(self, proxy_address: str) -> Optional[ProxyRecord]:
        """Get full proxy record including upgrade history."""
        return self._proxies.get(proxy_address)

    def get_proxies_for_implementation(self, impl_address: str) -> List[str]:
        """List all proxy addresses pointing at a given implementation."""
        return list(self._impl_to_proxies.get(impl_address, []))

    def list_proxies(self) -> List[Dict]:
        """List all registered proxies."""
        return [r.to_dict() for r in self._proxies.values()]

    def get_upgrade_history(self, proxy_address: str) -> List[Dict]:
        """Get the full upgrade audit trail for a proxy."""
        record = self._proxies.get(proxy_address)
        if record is None:
            return []
        return [e.to_dict() for e in record.upgrade_history]

    def get_stats(self) -> Dict:
        """Registry statistics."""
        total_upgrades = sum(
            len(r.upgrade_history) - 1  # subtract initial deploy
            for r in self._proxies.values()
        )
        pending_scheduled = sum(
            1 for su in self._scheduled_upgrades.values()
            if not su.executed and not su.canceled
        )
        return {
            "total_proxies": len(self._proxies),
            "total_implementations": len(self._impl_to_proxies),
            "total_upgrades": total_upgrades,
            "total_scheduled": len(self._scheduled_upgrades),
            "pending_scheduled": pending_scheduled,
        }

    # ------------------------------------------------------------------
    # EIP-1967 helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_implementation_slot() -> int:
        """Return the EIP-1967 implementation storage slot."""
        return IMPLEMENTATION_SLOT

    @staticmethod
    def get_admin_slot() -> int:
        """Return the EIP-1967 admin storage slot."""
        return ADMIN_SLOT
