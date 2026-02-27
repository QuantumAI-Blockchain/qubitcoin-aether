"""
CDP (Collateralized Debt Position) Manager with Interest Rate Model and Liquidation Engine

Manages the lifecycle of CDPs: opening, borrowing, repaying, adding collateral,
interest accrual, and liquidation of under-collateralized positions.

Interest rate model: rate = base_rate + utilization_rate * slope
  - base_rate: minimum cost of borrowing (configurable via Config.CDP_BASE_INTEREST_RATE)
  - utilization_rate: total_debt / debt_ceiling
  - slope: how steeply rate rises with utilization (configurable via Config.CDP_INTEREST_SLOPE)

Liquidation:
  - CDPs below CDP_LIQUIDATION_RATIO are eligible for liquidation
  - Liquidator repays the debt and receives collateral at a discount (CDP_LIQUIDATION_PENALTY)
  - Surplus collateral (after debt + penalty) is returned to the CDP owner
"""

import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CDP:
    """Represents a single Collateralized Debt Position."""
    id: str
    owner: str
    collateral_qbc: Decimal
    debt_qusd: Decimal
    created_at: float
    last_interest_block: int
    accrued_interest: Decimal = Decimal('0')
    closed: bool = False
    closed_at: Optional[float] = None
    liquidated: bool = False
    liquidated_by: Optional[str] = None


@dataclass
class LiquidationResult:
    """Result of a liquidation operation."""
    cdp_id: str
    liquidator: str
    debt_repaid: Decimal
    collateral_seized: Decimal
    penalty_amount: Decimal
    surplus_returned: Decimal
    timestamp: float


class CDPManager:
    """Manages CDPs with interest accrual and liquidation.

    This is an in-memory implementation suitable for integration with
    the StablecoinEngine.  A production deployment would persist CDPs
    to CockroachDB via the DatabaseManager.

    Args:
        qbc_price_usd: Current QBC price in USD for collateral valuation.
                        Can be updated via ``set_qbc_price()``.
    """

    def __init__(self, qbc_price_usd: Decimal = Decimal('1.0')) -> None:
        self._cdps: Dict[str, CDP] = {}
        self._qbc_price_usd: Decimal = qbc_price_usd
        self._total_debt: Decimal = Decimal('0')
        self._liquidation_history: List[LiquidationResult] = []
        logger.info(
            "CDPManager initialized | min_collateral_ratio=%.2f "
            "liquidation_ratio=%.2f base_rate=%.4f slope=%.4f "
            "debt_ceiling=%s",
            Config.CDP_MIN_COLLATERAL_RATIO,
            Config.CDP_LIQUIDATION_RATIO,
            Config.CDP_BASE_INTEREST_RATE,
            Config.CDP_INTEREST_SLOPE,
            Config.CDP_MAX_DEBT_CEILING,
        )

    # ------------------------------------------------------------------
    # Price management
    # ------------------------------------------------------------------

    def set_qbc_price(self, price_usd: Decimal) -> None:
        """Update the QBC/USD price used for collateral valuation.

        Args:
            price_usd: QBC price in USD.  Must be positive.

        Raises:
            ValueError: If price is not positive.
        """
        if price_usd <= 0:
            raise ValueError("QBC price must be positive")
        self._qbc_price_usd = price_usd
        logger.debug("QBC price updated to %s USD", price_usd)

    # ------------------------------------------------------------------
    # Interest rate model
    # ------------------------------------------------------------------

    def get_utilization_rate(self) -> Decimal:
        """Calculate current utilization rate: total_debt / debt_ceiling.

        Returns:
            Utilization rate in [0, 1].  Returns 0 if debt ceiling is zero.
        """
        ceiling = Config.CDP_MAX_DEBT_CEILING
        if ceiling <= 0:
            return Decimal('0')
        return min(self._total_debt / ceiling, Decimal('1'))

    def get_current_interest_rate(self) -> Decimal:
        """Calculate current per-block interest rate.

        Formula: base_rate + utilization_rate * slope

        The returned value is an annualized rate.  Per-block accrual divides
        by BLOCKS_PER_YEAR.

        Returns:
            Annualized interest rate as a Decimal.
        """
        base = Decimal(str(Config.CDP_BASE_INTEREST_RATE))
        slope = Decimal(str(Config.CDP_INTEREST_SLOPE))
        utilization = self.get_utilization_rate()
        return base + utilization * slope

    # ------------------------------------------------------------------
    # CDP lifecycle
    # ------------------------------------------------------------------

    def open_cdp(
        self,
        owner: str,
        collateral_qbc: Decimal,
        borrow_qusd: Decimal,
        block_height: int = 0,
    ) -> CDP:
        """Open a new CDP by depositing collateral and borrowing QUSD.

        Args:
            owner: Address of the CDP owner.
            collateral_qbc: Amount of QBC deposited as collateral.
            borrow_qusd: Amount of QUSD to borrow.
            block_height: Current block height for interest tracking.

        Returns:
            The newly created CDP.

        Raises:
            ValueError: If collateral ratio is below minimum, borrow amount
                        is non-positive, collateral is non-positive, or
                        total debt would exceed debt ceiling.
        """
        if collateral_qbc <= 0:
            raise ValueError("Collateral must be positive")
        if borrow_qusd <= 0:
            raise ValueError("Borrow amount must be positive")

        # Check debt ceiling
        if self._total_debt + borrow_qusd > Config.CDP_MAX_DEBT_CEILING:
            raise ValueError(
                f"Borrow would exceed debt ceiling "
                f"({self._total_debt + borrow_qusd} > {Config.CDP_MAX_DEBT_CEILING})"
            )

        # Calculate and check collateral ratio
        collateral_value_usd = collateral_qbc * self._qbc_price_usd
        ratio = collateral_value_usd / borrow_qusd
        min_ratio = Decimal(str(Config.CDP_MIN_COLLATERAL_RATIO))

        if ratio < min_ratio:
            raise ValueError(
                f"Collateral ratio {ratio:.4f} below minimum {min_ratio} "
                f"(collateral_value={collateral_value_usd}, debt={borrow_qusd})"
            )

        cdp_id = str(uuid.uuid4())
        cdp = CDP(
            id=cdp_id,
            owner=owner,
            collateral_qbc=collateral_qbc,
            debt_qusd=borrow_qusd,
            created_at=time.time(),
            last_interest_block=block_height,
        )
        self._cdps[cdp_id] = cdp
        self._total_debt += borrow_qusd

        logger.info(
            "CDP opened | id=%s owner=%s collateral=%s QBC debt=%s QUSD ratio=%.4f",
            cdp_id[:8], owner[:16], collateral_qbc, borrow_qusd, float(ratio),
        )
        return cdp

    def close_cdp(self, cdp_id: str) -> CDP:
        """Close a CDP by repaying all debt and withdrawing collateral.

        The caller must ensure the owner has sufficient QUSD to repay
        debt + accrued interest before calling this method.

        Args:
            cdp_id: ID of the CDP to close.

        Returns:
            The closed CDP (with ``closed=True``).

        Raises:
            ValueError: If CDP does not exist or is already closed.
        """
        cdp = self._get_active_cdp(cdp_id)
        total_debt = cdp.debt_qusd + cdp.accrued_interest

        self._total_debt -= cdp.debt_qusd
        if self._total_debt < 0:
            self._total_debt = Decimal('0')

        cdp.debt_qusd = Decimal('0')
        cdp.accrued_interest = Decimal('0')
        cdp.collateral_qbc = Decimal('0')
        cdp.closed = True
        cdp.closed_at = time.time()

        logger.info(
            "CDP closed | id=%s debt_repaid=%s",
            cdp_id[:8], total_debt,
        )
        return cdp

    def add_collateral(self, cdp_id: str, amount: Decimal) -> CDP:
        """Add collateral to an existing CDP.

        Args:
            cdp_id: ID of the CDP.
            amount: Amount of QBC to add.

        Returns:
            The updated CDP.

        Raises:
            ValueError: If CDP does not exist, is closed, or amount is not positive.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        cdp = self._get_active_cdp(cdp_id)
        cdp.collateral_qbc += amount

        logger.info(
            "Collateral added | cdp=%s amount=%s new_total=%s",
            cdp_id[:8], amount, cdp.collateral_qbc,
        )
        return cdp

    def borrow_more(self, cdp_id: str, amount: Decimal) -> CDP:
        """Borrow additional QUSD against existing collateral.

        Args:
            cdp_id: ID of the CDP.
            amount: Additional QUSD to borrow.

        Returns:
            The updated CDP.

        Raises:
            ValueError: If the additional borrow would violate minimum
                        collateral ratio, amount is not positive, or
                        total debt would exceed debt ceiling.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        cdp = self._get_active_cdp(cdp_id)

        # Check debt ceiling
        if self._total_debt + amount > Config.CDP_MAX_DEBT_CEILING:
            raise ValueError(
                f"Borrow would exceed debt ceiling "
                f"({self._total_debt + amount} > {Config.CDP_MAX_DEBT_CEILING})"
            )

        new_debt = cdp.debt_qusd + cdp.accrued_interest + amount
        collateral_value_usd = cdp.collateral_qbc * self._qbc_price_usd
        ratio = collateral_value_usd / new_debt
        min_ratio = Decimal(str(Config.CDP_MIN_COLLATERAL_RATIO))

        if ratio < min_ratio:
            raise ValueError(
                f"Collateral ratio {ratio:.4f} would fall below minimum {min_ratio}"
            )

        cdp.debt_qusd += amount
        self._total_debt += amount

        logger.info(
            "Additional borrow | cdp=%s amount=%s new_debt=%s ratio=%.4f",
            cdp_id[:8], amount, cdp.debt_qusd + cdp.accrued_interest, float(ratio),
        )
        return cdp

    def accrue_interest(self, block_height: int) -> int:
        """Accrue interest on all active CDPs up to the given block height.

        Interest is calculated as:
            blocks_elapsed * (annual_rate / BLOCKS_PER_YEAR) * debt

        Args:
            block_height: Current block height.

        Returns:
            Number of CDPs that had interest accrued.
        """
        rate = self.get_current_interest_rate()
        blocks_per_year = Decimal(str(Config.BLOCKS_PER_YEAR))
        count = 0

        for cdp in self._cdps.values():
            if cdp.closed or cdp.liquidated:
                continue
            blocks_elapsed = block_height - cdp.last_interest_block
            if blocks_elapsed <= 0:
                continue

            interest = (
                cdp.debt_qusd
                * rate
                * Decimal(str(blocks_elapsed))
                / blocks_per_year
            )
            interest = interest.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
            cdp.accrued_interest += interest
            cdp.last_interest_block = block_height
            count += 1

        if count > 0:
            logger.debug(
                "Interest accrued | block=%d rate=%.6f cdps_updated=%d",
                block_height, float(rate), count,
            )
        return count

    def get_cdp(self, cdp_id: str) -> CDP:
        """Get CDP details including current debt with accrued interest.

        Args:
            cdp_id: CDP identifier.

        Returns:
            The CDP dataclass.

        Raises:
            ValueError: If CDP does not exist.
        """
        if cdp_id not in self._cdps:
            raise ValueError(f"CDP {cdp_id} not found")
        return self._cdps[cdp_id]

    def get_total_debt(self, cdp_id: str) -> Decimal:
        """Get total outstanding debt for a CDP (principal + accrued interest).

        Args:
            cdp_id: CDP identifier.

        Returns:
            Total debt in QUSD.
        """
        cdp = self.get_cdp(cdp_id)
        return cdp.debt_qusd + cdp.accrued_interest

    def get_collateral_ratio(self, cdp_id: str) -> Decimal:
        """Calculate the current collateral ratio for a CDP.

        Ratio = (collateral_qbc * qbc_price_usd) / total_debt

        Args:
            cdp_id: CDP identifier.

        Returns:
            Collateral ratio as a Decimal.  Returns Decimal('Infinity')
            if total debt is zero.

        Raises:
            ValueError: If CDP does not exist.
        """
        cdp = self.get_cdp(cdp_id)
        total_debt = cdp.debt_qusd + cdp.accrued_interest
        if total_debt <= 0:
            return Decimal('Infinity')
        collateral_value_usd = cdp.collateral_qbc * self._qbc_price_usd
        return collateral_value_usd / total_debt

    def get_all_cdps(self, owner: Optional[str] = None, active_only: bool = False) -> List[CDP]:
        """List CDPs, optionally filtered by owner and/or active status.

        Args:
            owner: If provided, only return CDPs for this owner.
            active_only: If True, exclude closed and liquidated CDPs.

        Returns:
            List of matching CDPs.
        """
        result = []
        for cdp in self._cdps.values():
            if owner and cdp.owner != owner:
                continue
            if active_only and (cdp.closed or cdp.liquidated):
                continue
            result.append(cdp)
        return result

    def get_stats(self) -> dict:
        """Get aggregate CDP statistics.

        Returns:
            Dict with total_cdps, active_cdps, total_debt, total_collateral,
            utilization_rate, current_interest_rate, and total_liquidations.
        """
        active = [c for c in self._cdps.values() if not c.closed and not c.liquidated]
        total_collateral = sum(c.collateral_qbc for c in active)
        total_interest = sum(c.accrued_interest for c in active)
        return {
            'total_cdps': len(self._cdps),
            'active_cdps': len(active),
            'total_debt': self._total_debt,
            'total_accrued_interest': total_interest,
            'total_collateral_qbc': total_collateral,
            'utilization_rate': float(self.get_utilization_rate()),
            'current_interest_rate': float(self.get_current_interest_rate()),
            'total_liquidations': len(self._liquidation_history),
        }

    # ------------------------------------------------------------------
    # Liquidation engine
    # ------------------------------------------------------------------

    def check_liquidatable(self, cdp_id: str) -> bool:
        """Check whether a CDP is below the liquidation ratio.

        Args:
            cdp_id: CDP identifier.

        Returns:
            True if the CDP's collateral ratio is below the liquidation
            threshold and the CDP is still active.

        Raises:
            ValueError: If CDP does not exist.
        """
        cdp = self.get_cdp(cdp_id)
        if cdp.closed or cdp.liquidated:
            return False
        total_debt = cdp.debt_qusd + cdp.accrued_interest
        if total_debt <= 0:
            return False
        collateral_value_usd = cdp.collateral_qbc * self._qbc_price_usd
        ratio = collateral_value_usd / total_debt
        return ratio < Decimal(str(Config.CDP_LIQUIDATION_RATIO))

    def get_liquidatable_cdps(self) -> List[CDP]:
        """Return all CDPs that are currently below the liquidation ratio.

        Returns:
            List of CDPs eligible for liquidation.
        """
        result = []
        for cdp in self._cdps.values():
            if cdp.closed or cdp.liquidated:
                continue
            total_debt = cdp.debt_qusd + cdp.accrued_interest
            if total_debt <= 0:
                continue
            collateral_value_usd = cdp.collateral_qbc * self._qbc_price_usd
            ratio = collateral_value_usd / total_debt
            if ratio < Decimal(str(Config.CDP_LIQUIDATION_RATIO)):
                result.append(cdp)
        return result

    def liquidate(self, cdp_id: str, liquidator: str) -> LiquidationResult:
        """Liquidate an under-collateralized CDP.

        The liquidator repays the CDP's total debt and receives the
        collateral at a discount determined by CDP_LIQUIDATION_PENALTY.

        Collateral seized by the liquidator:
            seized = (total_debt * (1 + penalty)) / qbc_price_usd

        If seized collateral exceeds available collateral, the liquidator
        gets all available collateral (partial liquidation scenario).

        Any surplus collateral is returned to the CDP owner.

        Args:
            cdp_id: CDP identifier.
            liquidator: Address of the liquidator.

        Returns:
            LiquidationResult with details of the liquidation.

        Raises:
            ValueError: If CDP is not liquidatable, does not exist,
                        or is already closed/liquidated.
        """
        cdp = self._get_active_cdp(cdp_id)

        if not self.check_liquidatable(cdp_id):
            raise ValueError(
                f"CDP {cdp_id} is not below liquidation ratio "
                f"(ratio={float(self.get_collateral_ratio(cdp_id)):.4f}, "
                f"threshold={Config.CDP_LIQUIDATION_RATIO})"
            )

        total_debt = cdp.debt_qusd + cdp.accrued_interest
        penalty_rate = Decimal(str(Config.CDP_LIQUIDATION_PENALTY))
        penalty_amount = total_debt * penalty_rate

        # Collateral the liquidator should receive (debt + penalty in QBC terms)
        debt_plus_penalty_usd = total_debt + penalty_amount
        collateral_to_seize = debt_plus_penalty_usd / self._qbc_price_usd

        # Cap at available collateral
        if collateral_to_seize > cdp.collateral_qbc:
            collateral_to_seize = cdp.collateral_qbc
            surplus = Decimal('0')
        else:
            surplus = cdp.collateral_qbc - collateral_to_seize

        # Update global debt tracking
        self._total_debt -= cdp.debt_qusd
        if self._total_debt < 0:
            self._total_debt = Decimal('0')

        # Mark CDP as liquidated
        cdp.liquidated = True
        cdp.liquidated_by = liquidator
        cdp.closed = True
        cdp.closed_at = time.time()
        cdp.debt_qusd = Decimal('0')
        cdp.accrued_interest = Decimal('0')
        cdp.collateral_qbc = Decimal('0')

        result = LiquidationResult(
            cdp_id=cdp_id,
            liquidator=liquidator,
            debt_repaid=total_debt,
            collateral_seized=collateral_to_seize,
            penalty_amount=penalty_amount,
            surplus_returned=surplus,
            timestamp=time.time(),
        )
        self._liquidation_history.append(result)

        logger.info(
            "CDP liquidated | id=%s liquidator=%s debt=%s seized=%s QBC "
            "penalty=%s surplus=%s QBC",
            cdp_id[:8], liquidator[:16], total_debt,
            collateral_to_seize, penalty_amount, surplus,
        )
        return result

    def get_liquidation_history(self, limit: int = 50) -> List[LiquidationResult]:
        """Return recent liquidation events.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of LiquidationResult, most recent first.
        """
        return list(reversed(self._liquidation_history[-limit:]))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_active_cdp(self, cdp_id: str) -> CDP:
        """Retrieve a CDP and verify it is active.

        Args:
            cdp_id: CDP identifier.

        Returns:
            The CDP.

        Raises:
            ValueError: If CDP does not exist or is already closed/liquidated.
        """
        if cdp_id not in self._cdps:
            raise ValueError(f"CDP {cdp_id} not found")
        cdp = self._cdps[cdp_id]
        if cdp.closed:
            raise ValueError(f"CDP {cdp_id} is already closed")
        if cdp.liquidated:
            raise ValueError(f"CDP {cdp_id} has been liquidated")
        return cdp
