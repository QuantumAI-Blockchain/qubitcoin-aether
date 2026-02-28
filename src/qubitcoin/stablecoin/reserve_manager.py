"""
QUSD Reserve Fee Router & Building Mechanisms

Routes fees from all protocol revenue streams into QUSD reserves:
  - Bridge fees (0.1% of all cross-chain transfers)
  - QUSD transaction fees (0.05% per transfer)
  - LP fee revenue (configurable % of DEX fees)
  - Treasury controlled sales (governance-approved)
  - Aether Tree chat fees (partial allocation)
  - Contract deployment fees (partial allocation)

Every inflow is tracked as a debt payback event, reducing the outstanding
debt ratio of the QUSD fractional reserve system.

See: docs/WHITEPAPER.md Section 11, CLAUDE.md Section 22
"""

import hashlib
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FeeSource(Enum):
    """Revenue stream that feeds QUSD reserves."""
    BRIDGE_FEE = "bridge_fee"
    QUSD_TX_FEE = "qusd_tx_fee"
    LP_FEE = "lp_fee"
    TREASURY_SALE = "treasury_sale"
    AETHER_CHAT_FEE = "aether_chat_fee"
    CONTRACT_DEPLOY_FEE = "contract_deploy_fee"
    DIRECT_DEPOSIT = "direct_deposit"


@dataclass
class ReserveInflow:
    """A single inflow event into the QUSD reserve."""
    inflow_id: str
    source: FeeSource
    amount_qbc: Decimal
    amount_usd: Decimal  # estimated USD value at time of inflow
    block_height: int
    tx_hash: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "inflow_id": self.inflow_id,
            "source": self.source.value,
            "amount_qbc": str(self.amount_qbc),
            "amount_usd": str(self.amount_usd),
            "block_height": self.block_height,
            "tx_hash": self.tx_hash,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ── Default allocation percentages for each fee source ─────────────────
# How much of each fee type goes to QUSD reserves (rest to treasury)
DEFAULT_RESERVE_ALLOCATIONS: Dict[str, float] = {
    FeeSource.BRIDGE_FEE.value: 1.0,           # 100% of bridge fees → reserves
    FeeSource.QUSD_TX_FEE.value: 1.0,          # 100% of QUSD tx fees → reserves
    FeeSource.LP_FEE.value: 0.50,              # 50% of LP fees → reserves
    FeeSource.TREASURY_SALE.value: 1.0,         # 100% of treasury sales → reserves
    FeeSource.AETHER_CHAT_FEE.value: 0.10,     # 10% of Aether fees → reserves
    FeeSource.CONTRACT_DEPLOY_FEE.value: 0.10,  # 10% of deploy fees → reserves
    FeeSource.DIRECT_DEPOSIT.value: 1.0,        # 100% of direct deposits → reserves
}


class ReserveFeeRouter:
    """
    Routes protocol fee revenue to QUSD reserves.

    Tracks every inflow as a debt payback event, reducing outstanding
    QUSD debt and increasing the backing ratio over time.
    """

    def __init__(
        self,
        reserve_allocations: Optional[Dict[str, float]] = None,
        qbc_usd_price: float = 1.0,
    ) -> None:
        """
        Args:
            reserve_allocations: Override allocation percentages per source.
            qbc_usd_price: Initial QBC/USD price for USD value estimation.
        """
        self._allocations = reserve_allocations or dict(DEFAULT_RESERVE_ALLOCATIONS)
        self._qbc_usd_price = Decimal(str(qbc_usd_price))
        self._inflows: List[ReserveInflow] = []
        self._total_inflow_qbc: Decimal = Decimal('0')
        self._total_inflow_usd: Decimal = Decimal('0')
        self._by_source: Dict[str, Decimal] = {}
        self._reserve_balance_qbc: Decimal = Decimal('0')
        logger.info("ReserveFeeRouter initialised")

    def set_qbc_price(self, price: float) -> None:
        """Update QBC/USD price for USD value estimation."""
        if price <= 0:
            return
        self._qbc_usd_price = Decimal(str(price))

    def get_allocation(self, source: FeeSource) -> float:
        """Get the reserve allocation percentage for a fee source."""
        return self._allocations.get(source.value, 0.0)

    def set_allocation(self, source: FeeSource, pct: float) -> Dict:
        """Update allocation percentage for a fee source (0.0-1.0)."""
        if not 0.0 <= pct <= 1.0:
            return {"success": False, "error": "Percentage must be 0.0 - 1.0"}
        self._allocations[source.value] = pct
        logger.info(f"Reserve allocation updated: {source.value} → {pct * 100:.1f}%")
        return {"success": True, "source": source.value, "allocation": pct}

    def route_fee(
        self,
        source: FeeSource,
        total_fee_qbc: float,
        block_height: int,
        tx_hash: str,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Route a fee payment, splitting between reserves and treasury.

        Args:
            source: Which revenue stream this comes from.
            total_fee_qbc: Total fee amount in QBC.
            block_height: Block height of the fee event.
            tx_hash: Transaction hash of the fee event.
            metadata: Optional extra data.

        Returns:
            Result with reserve_amount and treasury_amount.
        """
        if total_fee_qbc <= 0:
            return {"success": False, "error": "Fee must be positive"}

        fee_dec = Decimal(str(total_fee_qbc))
        alloc = Decimal(str(self._allocations.get(source.value, 0.0)))
        reserve_qbc = fee_dec * alloc
        treasury_qbc = fee_dec - reserve_qbc
        reserve_usd = reserve_qbc * self._qbc_usd_price

        if reserve_qbc > 0:
            inflow_id = hashlib.sha256(
                f"inflow:{source.value}:{tx_hash}:{block_height}:{total_fee_qbc}".encode()
            ).hexdigest()[:32]

            inflow = ReserveInflow(
                inflow_id=inflow_id,
                source=source,
                amount_qbc=reserve_qbc,
                amount_usd=reserve_usd,
                block_height=block_height,
                tx_hash=tx_hash,
                metadata=metadata or {},
            )
            self._inflows.append(inflow)
            self._total_inflow_qbc += reserve_qbc
            self._total_inflow_usd += reserve_usd
            self._reserve_balance_qbc += reserve_qbc
            self._by_source[source.value] = (
                self._by_source.get(source.value, Decimal('0')) + reserve_qbc
            )

            logger.info(
                f"Fee routed: {source.value} → {reserve_qbc:.4f} QBC to reserves, "
                f"{treasury_qbc:.4f} QBC to treasury"
            )

        return {
            "success": True,
            "source": source.value,
            "total_fee": str(fee_dec),
            "reserve_amount": str(reserve_qbc),
            "treasury_amount": str(treasury_qbc),
            "reserve_usd_value": str(reserve_usd),
            "allocation_pct": float(alloc),
        }

    def get_inflows(
        self,
        source: Optional[FeeSource] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get recent inflow records, optionally filtered by source."""
        results = []
        for inf in reversed(self._inflows):
            if source is not None and inf.source != source:
                continue
            results.append(inf.to_dict())
            if len(results) >= limit:
                break
        return results

    def get_reserve_balance(self) -> Decimal:
        """Get current reserve balance in QBC."""
        return self._reserve_balance_qbc

    def get_stats(self) -> Dict:
        """Reserve fee router statistics."""
        return {
            "total_inflows": len(self._inflows),
            "total_inflow_qbc": str(self._total_inflow_qbc),
            "total_inflow_usd": str(self._total_inflow_usd),
            "reserve_balance_qbc": str(self._reserve_balance_qbc),
            "qbc_usd_price": str(self._qbc_usd_price),
            "by_source": {k: str(v) for k, v in self._by_source.items()},
            "allocations": dict(self._allocations),
        }


# ── Reserve Milestone Schedule ──────────────────────────────────────────
# Year → minimum backing percentage
RESERVE_MILESTONES: List[Dict] = [
    {"year_start": 1, "year_end": 2, "min_backing_pct": 5.0},
    {"year_start": 3, "year_end": 4, "min_backing_pct": 15.0},
    {"year_start": 5, "year_end": 6, "min_backing_pct": 30.0},
    {"year_start": 7, "year_end": 9, "min_backing_pct": 50.0},
    {"year_start": 10, "year_end": 999, "min_backing_pct": 100.0},
]

# Blocks per year ≈ 365.25 * 24 * 3600 / 3.3 ≈ 9,565,090
BLOCKS_PER_YEAR: int = 9_565_090


class ReserveMilestoneEnforcer:
    """
    Enforces minimum reserve backing ratios based on chain age.

    Year 1-2: 5%, Year 3-4: 15%, Year 5-6: 30%, Year 7-9: 50%, Year 10+: 100%.
    Triggers emergency actions when backing falls below required minimum.
    """

    def __init__(
        self,
        genesis_block_height: int = 0,
        total_minted_qusd: float = 3_300_000_000.0,
        milestones: Optional[List[Dict]] = None,
    ) -> None:
        """
        Args:
            genesis_block_height: Block height of genesis block.
            total_minted_qusd: Total QUSD minted (default 3.3B).
            milestones: Override milestone schedule.
        """
        self._genesis_height = genesis_block_height
        self._total_minted = Decimal(str(total_minted_qusd))
        self._milestones = milestones or list(RESERVE_MILESTONES)
        self._reserve_value_usd: Decimal = Decimal('0')
        self._minting_halted: bool = False
        self._fee_increase_active: bool = False
        self._violation_history: List[Dict] = []
        self._milestone_events: List[Dict] = []
        logger.info("ReserveMilestoneEnforcer initialised")

    def set_reserve_value(self, usd_value: float) -> None:
        """Update the current total reserve value in USD."""
        self._reserve_value_usd = max(Decimal('0'), Decimal(str(usd_value)))

    def set_total_minted(self, qusd_amount: float) -> None:
        """Update total QUSD minted."""
        self._total_minted = max(Decimal('0'), Decimal(str(qusd_amount)))

    def get_chain_year(self, current_block: int) -> int:
        """Calculate the chain's current year from genesis."""
        blocks_elapsed = max(0, current_block - self._genesis_height)
        return max(1, (blocks_elapsed // BLOCKS_PER_YEAR) + 1)

    def get_required_backing(self, current_block: int) -> float:
        """Get the required backing percentage for the current chain year."""
        year = self.get_chain_year(current_block)
        for m in self._milestones:
            if m["year_start"] <= year <= m["year_end"]:
                return m["min_backing_pct"]
        return 100.0  # default: fully backed

    def get_current_backing(self) -> float:
        """Calculate current backing percentage."""
        if self._total_minted <= Decimal('0'):
            return 100.0
        return float((self._reserve_value_usd / self._total_minted) * Decimal('100'))

    def check_compliance(self, current_block: int) -> Dict:
        """
        Check if reserve backing meets the required minimum for this year.

        Returns compliance status and any required emergency actions.
        """
        year = self.get_chain_year(current_block)
        required = self.get_required_backing(current_block)
        actual = self.get_current_backing()
        compliant = actual >= required
        deficit = max(0.0, required - actual)
        deficit_usd = float((Decimal(str(deficit)) / Decimal('100')) * self._total_minted) if deficit > 0 else 0.0

        result = {
            "compliant": compliant,
            "chain_year": year,
            "required_backing_pct": required,
            "actual_backing_pct": round(actual, 4),
            "deficit_pct": round(deficit, 4),
            "deficit_usd": round(deficit_usd, 2),
            "reserve_value_usd": self._reserve_value_usd,
            "total_minted_qusd": self._total_minted,
            "minting_halted": self._minting_halted,
            "fee_increase_active": self._fee_increase_active,
        }

        if not compliant:
            self._record_violation(current_block, year, required, actual)
            result["emergency_actions"] = self._determine_emergency_actions(
                deficit, current_block
            )

        return result

    def _record_violation(
        self,
        block: int,
        year: int,
        required: float,
        actual: float,
    ) -> None:
        """Record a backing ratio violation."""
        self._violation_history.append({
            "block": block,
            "year": year,
            "required_pct": required,
            "actual_pct": round(actual, 4),
            "timestamp": time.time(),
        })
        logger.warning(
            f"Reserve violation: Year {year} requires {required}%, "
            f"actual is {actual:.2f}%"
        )

    def _determine_emergency_actions(
        self,
        deficit_pct: float,
        current_block: int,
    ) -> List[str]:
        """Determine emergency actions based on deficit severity.

        Thresholds are relative to the required backing so they scale
        across all chain years (Year 1 requires 5%, Year 10 requires 100%).
        """
        actions = []
        required = self.get_required_backing(current_block)
        # Fraction of required backing that is missing
        deficit_ratio = deficit_pct / required if required > 0 else 0.0

        if deficit_ratio >= 0.50:
            # Severe: actual is less than half the required -> halt minting
            self._minting_halted = True
            actions.append("HALT_MINTING")

        if deficit_ratio >= 0.20:
            # Moderate: missing >= 20% of required -> increase fees
            self._fee_increase_active = True
            actions.append("INCREASE_FEES")

        if deficit_ratio > 0:
            actions.append("WARN_LOW_BACKING")

        return actions

    def clear_emergency(self) -> Dict:
        """Clear emergency state (when backing is restored)."""
        self._minting_halted = False
        self._fee_increase_active = False
        logger.info("Emergency state cleared")
        return {"success": True, "minting_halted": False, "fee_increase_active": False}

    def record_milestone_event(self, backing_pct: float, block: int) -> Optional[Dict]:
        """
        Check and record if a backing milestone was crossed.

        Milestones: 5%, 15%, 30%, 50%, 100%.
        """
        milestone_thresholds = [5.0, 15.0, 30.0, 50.0, 100.0]
        crossed = set()
        already_crossed = {e["threshold"] for e in self._milestone_events}

        for threshold in milestone_thresholds:
            if backing_pct >= threshold and threshold not in already_crossed:
                crossed.add(threshold)

        if not crossed:
            return None

        for threshold in sorted(crossed):
            event = {
                "threshold": threshold,
                "actual_backing": round(backing_pct, 4),
                "block": block,
                "timestamp": time.time(),
            }
            self._milestone_events.append(event)
            logger.info(
                f"Milestone reached: {threshold}% backing at block {block}"
            )

        return {
            "milestones_crossed": sorted(crossed),
            "current_backing": round(backing_pct, 4),
        }

    def can_mint(self) -> bool:
        """Check if minting is allowed (not halted by emergency)."""
        return not self._minting_halted

    def get_stats(self) -> Dict:
        """Enforcer statistics."""
        return {
            "total_minted_qusd": str(self._total_minted),
            "reserve_value_usd": str(self._reserve_value_usd),
            "current_backing_pct": round(self.get_current_backing(), 4),
            "minting_halted": self._minting_halted,
            "fee_increase_active": self._fee_increase_active,
            "violation_count": len(self._violation_history),
            "milestone_events": len(self._milestone_events),
            "milestones": self._milestones,
        }


class CrossChainQUSDAggregator:
    """
    Aggregates QUSD and wQUSD supply across all chains.

    Tracks total circulating supply (QBC chain + all wrapped chains)
    to ensure accurate backing ratio calculation.
    """

    # wQUSD bridge fee: 0.05% (5 basis points)
    WQUSD_BRIDGE_FEE_BPS: int = 5

    def __init__(self) -> None:
        self._chain_supplies: Dict[str, Decimal] = {}
        self._bridge_fees_collected: Decimal = Decimal('0')
        self._bridge_transfers: int = 0
        logger.info("CrossChainQUSDAggregator initialised")

    def update_chain_supply(self, chain: str, supply: float) -> Dict:
        """
        Update the wQUSD supply on a given chain.

        Args:
            chain: Chain name (e.g. 'ethereum', 'solana', 'polygon').
            supply: Current wQUSD supply on that chain.

        Returns:
            Result with total supply.
        """
        self._chain_supplies[chain] = max(Decimal('0'), Decimal(str(supply)))
        return {
            "success": True,
            "chain": chain,
            "supply": str(Decimal(str(supply))),
            "total_supply": str(self.get_total_supply()),
        }

    def record_bridge_transfer(self, amount: float) -> Dict:
        """
        Record a wQUSD bridge transfer and collect fee.

        Fee: 0.05% routed to QUSD reserves.
        """
        amt = Decimal(str(amount))
        fee = (amt * self.WQUSD_BRIDGE_FEE_BPS) / Decimal('10000')
        net = amt - fee
        self._bridge_fees_collected += fee
        self._bridge_transfers += 1
        return {
            "success": True,
            "amount": str(amt),
            "fee": str(fee),
            "net_amount": str(net),
            "total_fees_collected": str(self._bridge_fees_collected),
        }

    def get_chain_supply(self, chain: str) -> Decimal:
        """Get wQUSD supply on a specific chain."""
        return self._chain_supplies.get(chain, Decimal('0'))

    def get_total_supply(self) -> Decimal:
        """Get total QUSD+wQUSD supply across all chains."""
        return sum(self._chain_supplies.values(), Decimal('0'))

    def get_all_chain_supplies(self) -> Dict[str, Decimal]:
        """Get supply breakdown by chain."""
        return dict(self._chain_supplies)

    def get_stats(self) -> Dict:
        """Aggregator statistics."""
        return {
            "chain_count": len(self._chain_supplies),
            "chain_supplies": {k: str(v) for k, v in self._chain_supplies.items()},
            "total_supply": str(self.get_total_supply()),
            "bridge_fee_bps": self.WQUSD_BRIDGE_FEE_BPS,
            "bridge_fees_collected": str(self._bridge_fees_collected),
            "bridge_transfers": self._bridge_transfers,
        }
