"""
QUSD Savings Rate — Earn yield on deposited QUSD

Inspired by MakerDAO's DAI Savings Rate (DSR).  Users deposit QUSD into the
savings pool and earn per-block interest funded by protocol revenue (fee
burns, QUSD stability fees).

Interest accrual:
    interest_per_block = total_deposits * annual_rate / blocks_per_year

Default rate: 3.3% APY (golden ratio theme).
Rate is adjustable via governance or the admin API.

Persistence: When a ``DatabaseManager`` is provided, balances and accrued
interest are persisted to the ``savings_balances`` table in CockroachDB.
Without a DB the module falls back to in-memory operation (useful for tests).
"""

import time
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Optional, TYPE_CHECKING

from ..config import Config
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..database.manager import DatabaseManager

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BLOCKS_PER_YEAR: int = Config.BLOCKS_PER_YEAR  # ~9,563,636


class QUSDSavingsRate:
    """Manages QUSD savings deposits and per-block interest accrual.

    When *db* is provided, balances are persisted to CockroachDB so they
    survive node restarts.  Without a DB the module is fully in-memory
    (convenient for unit tests).
    """

    def __init__(
        self,
        annual_rate: Optional[float] = None,
        min_deposit: Optional[Decimal] = None,
        max_rate: Optional[float] = None,
        db: Optional["DatabaseManager"] = None,
    ) -> None:
        """Initialise the savings rate engine.

        Args:
            annual_rate: Annual percentage yield (e.g. 0.033 for 3.3%).
                         Defaults to ``Config.QUSD_SAVINGS_RATE``.
            min_deposit: Minimum deposit amount in QUSD.
                         Defaults to ``Config.QUSD_SAVINGS_MIN_DEPOSIT``.
            max_rate:    Hard cap on the annual rate (governance safety).
                         Defaults to ``Config.QUSD_SAVINGS_MAX_RATE``.
            db:          Optional DatabaseManager for persistence.
        """
        self._annual_rate: float = annual_rate if annual_rate is not None else Config.QUSD_SAVINGS_RATE
        self._min_deposit: Decimal = min_deposit if min_deposit is not None else Config.QUSD_SAVINGS_MIN_DEPOSIT
        self._max_rate: float = max_rate if max_rate is not None else Config.QUSD_SAVINGS_MAX_RATE
        self._db = db

        # Clamp the initial rate to [0, max_rate]
        self._annual_rate = max(0.0, min(self._annual_rate, self._max_rate))

        # Per-user principal (what the user actually deposited / still owns)
        self._balances: Dict[str, Decimal] = {}

        # Aggregate bookkeeping
        self._total_deposits: Decimal = Decimal('0')
        self._total_interest_paid: Decimal = Decimal('0')

        # Track the last block at which interest was accrued so we can
        # calculate the correct delta on the next call.
        self._last_accrual_block: int = 0

        # Per-user accrued-but-not-yet-credited interest accumulator.
        # ``accrue_interest`` distributes pool-level interest to each user
        # proportionally; withdrawals flush this into ``_balances``.
        self._accrued_interest: Dict[str, Decimal] = {}

        # Audit trail
        self._rate_change_history: list = []
        self._created_at: float = time.time()

        # Load persisted state if DB is available
        if self._db is not None:
            self._load_from_db()

        logger.info(
            "QUSDSavingsRate initialised — rate=%.4f%%, min_deposit=%s, max_rate=%.2f%%",
            self._annual_rate * 100,
            self._min_deposit,
            self._max_rate * 100,
        )

    # ------------------------------------------------------------------
    # Database persistence helpers
    # ------------------------------------------------------------------

    def _ensure_table(self) -> None:
        """Create the savings_balances table if it does not exist."""
        if self._db is None:
            return
        try:
            from sqlalchemy import text
            with self._db.get_session() as session:
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS savings_balances (
                        user_address STRING PRIMARY KEY,
                        principal DECIMAL NOT NULL DEFAULT 0,
                        accrued_interest DECIMAL NOT NULL DEFAULT 0,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """))
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS savings_state (
                        key STRING PRIMARY KEY,
                        value STRING NOT NULL
                    )
                """))
                session.commit()
        except Exception as e:
            logger.warning(f"Could not create savings tables: {e}")

    def _load_from_db(self) -> None:
        """Load balances and state from CockroachDB."""
        if self._db is None:
            return
        self._ensure_table()
        try:
            from sqlalchemy import text
            with self._db.get_session() as session:
                # Load per-user balances
                rows = session.execute(text(
                    "SELECT user_address, principal, accrued_interest "
                    "FROM savings_balances WHERE principal > 0 OR accrued_interest > 0"
                )).fetchall()
                for row in rows:
                    user = row[0]
                    principal = Decimal(str(row[1]))
                    accrued = Decimal(str(row[2]))
                    if principal > 0:
                        self._balances[user] = principal
                    if accrued > 0:
                        self._accrued_interest[user] = accrued

                # Recompute total deposits from loaded balances
                self._total_deposits = sum(self._balances.values(), Decimal('0'))

                # Load aggregate state
                state_rows = session.execute(text(
                    "SELECT key, value FROM savings_state"
                )).fetchall()
                state = {r[0]: r[1] for r in state_rows}
                if 'total_interest_paid' in state:
                    self._total_interest_paid = Decimal(state['total_interest_paid'])
                if 'last_accrual_block' in state:
                    self._last_accrual_block = int(state['last_accrual_block'])
                if 'annual_rate' in state:
                    self._annual_rate = float(state['annual_rate'])

                if self._balances:
                    logger.info(
                        "Loaded %d savings accounts from DB (total=%s)",
                        len(self._balances), self._total_deposits,
                    )
        except Exception as e:
            logger.warning(f"Could not load savings state from DB: {e}")

    def _persist_user(self, user: str) -> None:
        """Persist a single user's balance to the database."""
        if self._db is None:
            return
        try:
            from sqlalchemy import text
            principal = self._balances.get(user, Decimal('0'))
            accrued = self._accrued_interest.get(user, Decimal('0'))
            with self._db.get_session() as session:
                session.execute(text(
                    "UPSERT INTO savings_balances (user_address, principal, accrued_interest, updated_at) "
                    "VALUES (:user, :principal, :accrued, now())"
                ), {'user': user, 'principal': str(principal), 'accrued': str(accrued)})
                session.commit()
        except Exception as e:
            logger.warning(f"Could not persist savings for {user}: {e}")

    def _persist_state(self) -> None:
        """Persist aggregate state to the database."""
        if self._db is None:
            return
        try:
            from sqlalchemy import text
            with self._db.get_session() as session:
                for key, value in [
                    ('total_interest_paid', str(self._total_interest_paid)),
                    ('last_accrual_block', str(self._last_accrual_block)),
                    ('annual_rate', str(self._annual_rate)),
                ]:
                    session.execute(text(
                        "UPSERT INTO savings_state (key, value) VALUES (:key, :value)"
                    ), {'key': key, 'value': value})
                session.commit()
        except Exception as e:
            logger.warning(f"Could not persist savings state: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deposit(self, user: str, amount: Decimal) -> Dict[str, object]:
        """Deposit QUSD into the savings pool.

        Args:
            user:   Address of the depositor.
            amount: QUSD amount to deposit.

        Returns:
            Dict with ``user``, ``deposited``, ``new_balance``, ``total_deposits``.

        Raises:
            ValueError: If *amount* is non-positive or below the minimum.
        """
        if not user:
            raise ValueError("user address must not be empty")
        if amount <= 0:
            raise ValueError("deposit amount must be positive")
        if amount < self._min_deposit:
            raise ValueError(
                f"deposit amount {amount} is below minimum {self._min_deposit}"
            )

        self._balances[user] = self._balances.get(user, Decimal('0')) + amount
        self._accrued_interest.setdefault(user, Decimal('0'))
        self._total_deposits += amount

        self._persist_user(user)

        logger.info("QUSD savings deposit — user=%s amount=%s", user, amount)
        return {
            'user': user,
            'deposited': amount,
            'new_balance': self.get_balance(user),
            'total_deposits': self._total_deposits,
        }

    def withdraw(self, user: str, amount: Decimal) -> Dict[str, object]:
        """Withdraw QUSD (principal + accrued interest) from the savings pool.

        The user's accrued interest is flushed into their balance first so
        they can withdraw the full earning.

        Args:
            user:   Address of the withdrawer.
            amount: QUSD amount to withdraw.

        Returns:
            Dict with ``user``, ``withdrawn``, ``remaining_balance``,
            ``total_deposits``.

        Raises:
            ValueError: If *amount* exceeds available balance or is
                        non-positive.
        """
        if not user:
            raise ValueError("user address must not be empty")
        if amount <= 0:
            raise ValueError("withdrawal amount must be positive")

        # Flush accrued interest into principal first
        accrued = self._accrued_interest.get(user, Decimal('0'))
        if accrued > 0:
            self._balances[user] = self._balances.get(user, Decimal('0')) + accrued
            self._accrued_interest[user] = Decimal('0')

        available = self._balances.get(user, Decimal('0'))
        if amount > available:
            raise ValueError(
                f"insufficient balance: requested {amount}, available {available}"
            )

        self._balances[user] -= amount
        # Total deposits tracks the *principal pool* used for interest calc.
        # When a user withdraws, we reduce the pool by at most the amount
        # withdrawn (interest component was already added via accrue).
        self._total_deposits = max(Decimal('0'), self._total_deposits - amount)

        remaining = self.get_balance(user)

        # Clean up zero-balance entries
        if self._balances.get(user, Decimal('0')) == 0 and self._accrued_interest.get(user, Decimal('0')) == 0:
            self._balances.pop(user, None)
            self._accrued_interest.pop(user, None)

        self._persist_user(user)

        logger.info("QUSD savings withdrawal — user=%s amount=%s", user, amount)
        return {
            'user': user,
            'withdrawn': amount,
            'remaining_balance': remaining,
            'total_deposits': self._total_deposits,
        }

    def accrue_interest(self, block_height: int) -> Decimal:
        """Distribute per-block interest to all depositors.

        Should be called once per block.  Computes interest for the
        blocks elapsed since the last accrual and distributes it
        proportionally among all depositors.

        Args:
            block_height: Current block height.

        Returns:
            Total interest distributed in this call.
        """
        if block_height <= self._last_accrual_block:
            return Decimal('0')
        if self._total_deposits <= 0:
            self._last_accrual_block = block_height
            return Decimal('0')
        if self._annual_rate <= 0:
            self._last_accrual_block = block_height
            return Decimal('0')

        blocks_elapsed = block_height - self._last_accrual_block

        # interest = total_deposits * annual_rate * blocks_elapsed / blocks_per_year
        rate_decimal = Decimal(str(self._annual_rate))
        interest_total = (
            self._total_deposits
            * rate_decimal
            * Decimal(str(blocks_elapsed))
            / Decimal(str(BLOCKS_PER_YEAR))
        ).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)

        if interest_total <= 0:
            self._last_accrual_block = block_height
            return Decimal('0')

        # Distribute proportionally to each depositor
        distributed = Decimal('0')
        for user, principal in list(self._balances.items()):
            if principal <= 0:
                continue
            share = (principal / self._total_deposits) * interest_total
            share = share.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
            self._accrued_interest[user] = self._accrued_interest.get(user, Decimal('0')) + share
            distributed += share

        self._total_deposits += distributed
        self._total_interest_paid += distributed
        self._last_accrual_block = block_height

        if distributed > 0:
            logger.debug(
                "QUSD savings interest accrued — blocks=%d interest=%s total_deposits=%s",
                blocks_elapsed,
                distributed,
                self._total_deposits,
            )

        # Persist updated state periodically (every accrual)
        self._persist_state()

        return distributed

    def get_balance(self, user: str) -> Decimal:
        """Return the user's balance including accrued interest.

        Args:
            user: Address to query.

        Returns:
            Total QUSD balance (principal + accrued interest).
        """
        principal = self._balances.get(user, Decimal('0'))
        accrued = self._accrued_interest.get(user, Decimal('0'))
        return principal + accrued

    def get_total_deposits(self) -> Decimal:
        """Return the total QUSD deposited across all users."""
        return self._total_deposits

    def get_current_rate(self) -> float:
        """Return the current annual savings rate (e.g. 0.033 for 3.3%)."""
        return self._annual_rate

    def set_rate(self, new_rate: float) -> Dict[str, object]:
        """Set a new annual savings rate.

        Args:
            new_rate: New annual rate (e.g. 0.05 for 5%).

        Returns:
            Dict with ``old_rate``, ``new_rate``, ``max_rate``.

        Raises:
            ValueError: If *new_rate* is negative or exceeds ``max_rate``.
        """
        if new_rate < 0:
            raise ValueError("savings rate cannot be negative")
        if new_rate > self._max_rate:
            raise ValueError(
                f"savings rate {new_rate} exceeds maximum {self._max_rate}"
            )

        old_rate = self._annual_rate
        self._annual_rate = new_rate
        self._rate_change_history.append({
            'old_rate': old_rate,
            'new_rate': new_rate,
            'timestamp': time.time(),
        })

        self._persist_state()

        logger.info(
            "QUSD savings rate changed — old=%.4f%% new=%.4f%%",
            old_rate * 100,
            new_rate * 100,
        )
        return {
            'old_rate': old_rate,
            'new_rate': new_rate,
            'max_rate': self._max_rate,
        }

    def get_stats(self) -> Dict[str, object]:
        """Return overall savings rate statistics.

        Returns:
            Dict with ``total_deposits``, ``total_interest_paid``,
            ``current_rate``, ``depositor_count``, ``last_accrual_block``,
            ``blocks_per_year``, ``rate_change_history``, ``created_at``.
        """
        return {
            'total_deposits': self._total_deposits,
            'total_interest_paid': self._total_interest_paid,
            'current_rate': self._annual_rate,
            'max_rate': self._max_rate,
            'min_deposit': self._min_deposit,
            'depositor_count': len(self._balances),
            'last_accrual_block': self._last_accrual_block,
            'blocks_per_year': BLOCKS_PER_YEAR,
            'rate_change_history': list(self._rate_change_history),
            'created_at': self._created_at,
        }
