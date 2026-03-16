"""
High-Security Account Manager for Qubitcoin.

Provides opt-in security policies for accounts:
- Daily spending limits (in QBC)
- Address whitelisting (only send to approved addresses)
- Time-lock delays on large transfers

Enforcement is at the mempool/RPC standardness level, not consensus.
This means non-compliant transactions are rejected by nodes running
with this feature enabled, but do not cause a consensus hard fork.
"""

import hashlib
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SecurityPolicy:
    """Security policy for an account."""
    address: str
    daily_limit_qbc: Decimal = Decimal("0")          # 0 = no limit
    require_whitelist: bool = False
    whitelist: List[str] = field(default_factory=list)
    time_lock_blocks: int = 0             # delay on large txs
    time_lock_threshold_qbc: Decimal = Decimal("0")  # amount triggering time-lock
    active: bool = True


@dataclass
class SpendingRecord:
    """Record of spending for daily limit tracking."""
    id: str
    address: str
    amount_qbc: Decimal
    recipient: str
    block_height: int
    timestamp: float = field(default_factory=time.time)


class HighSecurityManager:
    """Manages high-security account policies.

    Args:
        db_manager: DatabaseManager instance for persistence
    """

    def __init__(self, db_manager) -> None:
        self.db = db_manager
        self._daily_limit_window = Config.SECURITY_DAILY_LIMIT_WINDOW

        # In-memory caches
        self._policies: Dict[str, SecurityPolicy] = {}
        self._spending: Dict[str, List[SpendingRecord]] = {}

        logger.info(
            f"HighSecurityManager initialized: "
            f"daily_limit_window={self._daily_limit_window} blocks"
        )

    # ── Policy Management ───────────────────────────────────────────────

    def set_policy(self, address: str, daily_limit_qbc: Decimal = Decimal("0"),
                   require_whitelist: bool = False,
                   whitelist: Optional[List[str]] = None,
                   time_lock_blocks: int = 0,
                   time_lock_threshold_qbc: Decimal = Decimal("0")) -> SecurityPolicy:
        """Set or update a security policy for an address.

        Args:
            address: Account address
            daily_limit_qbc: Maximum daily spending (0 = no limit)
            require_whitelist: Only allow sends to whitelisted addresses
            whitelist: List of approved recipient addresses
            time_lock_blocks: Block delay for large transfers
            time_lock_threshold_qbc: Amount threshold for time-lock

        Returns:
            SecurityPolicy record

        Raises:
            ValueError: If parameters are invalid
        """
        daily_limit_qbc = Decimal(str(daily_limit_qbc))
        time_lock_threshold_qbc = Decimal(str(time_lock_threshold_qbc))
        if daily_limit_qbc < 0:
            raise ValueError("Daily limit cannot be negative")
        if time_lock_blocks < 0:
            raise ValueError("Time lock blocks cannot be negative")
        if time_lock_threshold_qbc < 0:
            raise ValueError("Time lock threshold cannot be negative")
        if time_lock_blocks > 0 and time_lock_threshold_qbc <= 0:
            raise ValueError("Time lock requires a positive threshold amount")

        policy = SecurityPolicy(
            address=address,
            daily_limit_qbc=daily_limit_qbc,
            require_whitelist=require_whitelist,
            whitelist=whitelist or [],
            time_lock_blocks=time_lock_blocks,
            time_lock_threshold_qbc=time_lock_threshold_qbc,
            active=True,
        )
        self._policies[address] = policy
        self._persist_policy(policy)

        logger.info(
            f"Security policy set: address={address[:16]}..., "
            f"daily_limit={daily_limit_qbc} QBC, "
            f"whitelist={'ON' if require_whitelist else 'OFF'}, "
            f"time_lock={time_lock_blocks} blocks"
        )
        return policy

    def get_policy(self, address: str) -> Optional[SecurityPolicy]:
        """Get the security policy for an address."""
        policy = self._policies.get(address)
        if policy and policy.active:
            return policy
        return None

    def remove_policy(self, address: str) -> bool:
        """Remove the security policy for an address.

        Returns:
            True if policy was found and removed
        """
        policy = self._policies.get(address)
        if not policy or not policy.active:
            return False

        policy.active = False
        self._persist_policy(policy)
        logger.info(f"Security policy removed: address={address[:16]}...")
        return True

    # ── Transaction Validation ──────────────────────────────────────────

    def validate_outgoing_tx(self, sender: str, recipient: str,
                              amount_qbc: Decimal,
                              current_height: int) -> dict:
        """Validate an outgoing transaction against security policy.

        Args:
            sender: Sender address
            recipient: Recipient address
            amount_qbc: Amount in QBC
            current_height: Current block height

        Returns:
            Dict with 'allowed' bool and 'reason' if rejected
        """
        amount_qbc = Decimal(str(amount_qbc))
        policy = self.get_policy(sender)
        if not policy:
            return {'allowed': True, 'reason': ''}

        # Check whitelist
        if policy.require_whitelist and recipient not in policy.whitelist:
            return {
                'allowed': False,
                'reason': f"Recipient {recipient[:16]}... not in whitelist"
            }

        # Check daily limit
        if policy.daily_limit_qbc > 0:
            daily_spent = self.get_daily_spent(sender, current_height)
            if daily_spent + amount_qbc > policy.daily_limit_qbc:
                remaining = max(0, policy.daily_limit_qbc - daily_spent)
                return {
                    'allowed': False,
                    'reason': (
                        f"Daily limit exceeded: "
                        f"spent={daily_spent:.4f}, "
                        f"requested={amount_qbc:.4f}, "
                        f"limit={policy.daily_limit_qbc:.4f}, "
                        f"remaining={remaining:.4f}"
                    )
                }

        # Check time-lock
        if (policy.time_lock_blocks > 0
                and amount_qbc >= policy.time_lock_threshold_qbc):
            return {
                'allowed': True,
                'reason': '',
                'time_lock_blocks': policy.time_lock_blocks,
                'time_locked': True,
            }

        return {'allowed': True, 'reason': ''}

    # ── Spending Tracking ───────────────────────────────────────────────

    def get_daily_spent(self, address: str, current_height: int) -> Decimal:
        """Get total spending within the daily limit window.

        Args:
            address: Account address
            current_height: Current block height

        Returns:
            Total QBC spent in the current window
        """
        records = self._spending.get(address, [])
        window_start = current_height - self._daily_limit_window
        return sum(
            (r.amount_qbc for r in records
             if r.block_height > window_start),
            Decimal("0"),
        )

    def record_spending(self, sender: str, recipient: str,
                         amount_qbc: Decimal, current_height: int) -> None:
        """Record a spending event for daily limit tracking.

        Args:
            sender: Sender address
            recipient: Recipient address
            amount_qbc: Amount spent
            current_height: Current block height
        """
        amount_qbc = Decimal(str(amount_qbc))
        record_id = hashlib.sha256(
            f"spend-{sender}-{recipient}-{amount_qbc}-{time.time()}".encode()
        ).hexdigest()[:32]

        record = SpendingRecord(
            id=record_id,
            address=sender,
            amount_qbc=amount_qbc,
            recipient=recipient,
            block_height=current_height,
        )

        if sender not in self._spending:
            self._spending[sender] = []
        self._spending[sender].append(record)
        self._persist_spending(record)

        # Prune old records beyond window
        window_start = current_height - self._daily_limit_window
        self._spending[sender] = [
            r for r in self._spending[sender]
            if r.block_height > window_start
        ]

    # ── Persistence helpers ─────────────────────────────────────────────

    def _persist_policy(self, policy: SecurityPolicy) -> None:
        """Persist security policy to database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO security_policies
                        (address, daily_limit_qbc, require_whitelist, whitelist,
                         time_lock_blocks, time_lock_threshold_qbc, active, updated_at)
                    VALUES (:address, :limit, :whitelist_on, :whitelist,
                            :time_lock, :threshold, :active, now())
                    ON CONFLICT (address) DO UPDATE SET
                        daily_limit_qbc = :limit,
                        require_whitelist = :whitelist_on,
                        whitelist = :whitelist,
                        time_lock_blocks = :time_lock,
                        time_lock_threshold_qbc = :threshold,
                        active = :active,
                        updated_at = now()
                """), {
                    'address': policy.address,
                    'limit': policy.daily_limit_qbc,
                    'whitelist_on': policy.require_whitelist,
                    'whitelist': policy.whitelist,
                    'time_lock': policy.time_lock_blocks,
                    'threshold': policy.time_lock_threshold_qbc,
                    'active': policy.active,
                })
                session.commit()
        except Exception as e:
            logger.debug(f"Policy persistence: {e}")

    def _persist_spending(self, record: SpendingRecord) -> None:
        """Persist spending record to database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO security_spending_log
                        (id, address, amount_qbc, recipient, block_height)
                    VALUES (:id, :address, :amount, :recipient, :height)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    'id': record.id,
                    'address': record.address,
                    'amount': record.amount_qbc,
                    'recipient': record.recipient,
                    'height': record.block_height,
                })
                session.commit()
        except Exception as e:
            logger.debug(f"Spending persistence: {e}")
