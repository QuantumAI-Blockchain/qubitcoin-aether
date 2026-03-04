"""
Cross-Chain Arbitrage Calculator for wQUSD / wQBC

Computes arbitrage profitability between:
  1. External chain DEX price vs. QBC chain peg ($1.00)
  2. Cross-chain price spreads (chain A vs. chain B)

Used by the keeper daemon to:
  - Detect profitable arb opportunities
  - Estimate net profit after gas + bridge fees
  - Rank opportunities by ROI
  - Log opportunities for operator dashboards

This module is READ-ONLY — it never executes trades.
The keeper daemon decides whether to act on signals.
"""

import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class ArbType(Enum):
    """Type of arbitrage opportunity."""
    PEG_FLOOR = "peg_floor"       # wQUSD < $0.99 → buy cheap, redeem at $1
    PEG_CEILING = "peg_ceiling"   # wQUSD > $1.01 → mint at $1, sell expensive
    CROSS_CHAIN = "cross_chain"   # wQUSD price differs between chains


class ArbAction(Enum):
    """Recommended action for the arb."""
    BUY_WQUSD = "buy_wqusd"       # Buy wQUSD on DEX (floor defense)
    SELL_WQUSD = "sell_wqusd"     # Sell wQUSD on DEX (ceiling defense)
    BRIDGE_BUY = "bridge_buy"     # Bridge + buy on cheap chain
    BRIDGE_SELL = "bridge_sell"   # Bridge + sell on expensive chain
    STABILIZER = "stabilizer"     # Call QUSDStabilizer.triggerRebalance()


@dataclass
class GasEstimate:
    """Estimated gas cost for an operation on a specific chain."""
    chain_id: int
    chain_name: str
    gas_units: int
    gas_price_gwei: Decimal
    cost_native: Decimal       # Cost in native token (ETH, BNB, SOL, etc.)
    cost_usd: Decimal          # Estimated USD cost
    native_token: str          # "ETH", "BNB", "SOL", etc.


@dataclass
class ArbOpportunity:
    """A single arbitrage opportunity."""
    id: str                    # Unique identifier
    arb_type: ArbType
    action: ArbAction
    chain_id: int              # Primary chain
    chain_name: str
    current_price: Decimal     # wQUSD price on this chain
    target_price: Decimal      # Target price ($1.00 for peg arb)
    spread_bps: int            # Spread in basis points
    trade_size_usd: Decimal    # Recommended trade size
    gross_profit_usd: Decimal  # Profit before costs
    gas_cost_usd: Decimal      # Estimated gas cost
    bridge_fee_usd: Decimal    # Bridge fee (if cross-chain)
    net_profit_usd: Decimal    # Net profit after all costs
    roi_pct: Decimal           # Return on invested capital
    profitable: bool           # Net profit > 0
    confidence: float          # 0.0-1.0 (based on liquidity + data quality)
    timestamp: float
    # Cross-chain specific
    dest_chain_id: Optional[int] = None
    dest_chain_name: Optional[str] = None
    dest_price: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Gas cost database
# ---------------------------------------------------------------------------

# Approximate gas costs per chain (updated periodically)
_GAS_ESTIMATES: Dict[int, GasEstimate] = {
    1: GasEstimate(1, "Ethereum", 200_000, Decimal("30"), Decimal("0.006"),
                   Decimal("15.00"), "ETH"),
    56: GasEstimate(56, "BSC", 200_000, Decimal("3"), Decimal("0.0006"),
                    Decimal("0.30"), "BNB"),
    137: GasEstimate(137, "Polygon", 200_000, Decimal("50"), Decimal("0.01"),
                     Decimal("0.01"), "MATIC"),
    42161: GasEstimate(42161, "Arbitrum", 200_000, Decimal("0.1"),
                       Decimal("0.00002"), Decimal("0.05"), "ETH"),
    10: GasEstimate(10, "Optimism", 200_000, Decimal("0.1"),
                    Decimal("0.00002"), Decimal("0.05"), "ETH"),
    8453: GasEstimate(8453, "Base", 200_000, Decimal("0.1"),
                      Decimal("0.00002"), Decimal("0.05"), "ETH"),
    43114: GasEstimate(43114, "Avalanche", 200_000, Decimal("25"),
                       Decimal("0.005"), Decimal("0.15"), "AVAX"),
    0: GasEstimate(0, "Solana", 1, Decimal("0"), Decimal("0.000005"),
                   Decimal("0.001"), "SOL"),
}

# Bridge fee in basis points (from Config or default)
_DEFAULT_BRIDGE_FEE_BPS = 10  # 0.1% per bridge hop


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ArbitrageCalculator:
    """Calculates cross-chain arbitrage opportunities for wQUSD peg maintenance.

    This is a pure calculator — it reads prices and computes opportunities
    but never executes trades. The keeper daemon uses this to make decisions.
    """

    # Peg bands (from QUSDStabilizer.sol)
    PEG_TARGET: Decimal = Decimal("1.00")
    FLOOR_PRICE: Decimal = Decimal("0.99")
    CEILING_PRICE: Decimal = Decimal("1.01")

    # Minimum trade size (USD) to bother with
    MIN_TRADE_SIZE: Decimal = Decimal("100")
    # Default trade size when no liquidity info
    DEFAULT_TRADE_SIZE: Decimal = Decimal("10000")
    # Max trade size per opportunity
    MAX_TRADE_SIZE: Decimal = Decimal("1000000")

    # Minimum profit to flag as actionable
    MIN_PROFIT_USD: Decimal = Decimal("1.00")

    def __init__(self) -> None:
        self._opportunities: List[ArbOpportunity] = []
        self._history: List[ArbOpportunity] = []
        self._max_history: int = 1000
        self._bridge_fee_bps: int = getattr(
            Config, "BRIDGE_FEE_BPS", _DEFAULT_BRIDGE_FEE_BPS
        )

    # ------------------------------------------------------------------
    # Gas estimation
    # ------------------------------------------------------------------

    def _get_gas_cost(self, chain_id: int) -> GasEstimate:
        """Get estimated gas cost for a swap on the given chain."""
        return _GAS_ESTIMATES.get(chain_id, GasEstimate(
            chain_id, f"Chain-{chain_id}", 200_000, Decimal("10"),
            Decimal("0.01"), Decimal("5.00"), "UNKNOWN",
        ))

    def _bridge_fee(self, amount: Decimal, hops: int = 1) -> Decimal:
        """Calculate bridge fee for a given amount and number of hops.

        Each hop charges BRIDGE_FEE_BPS.
        """
        total_bps = self._bridge_fee_bps * hops
        return (amount * Decimal(total_bps) / Decimal("10000")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def update_gas_estimate(self, chain_id: int, gas_price_gwei: Decimal,
                            native_usd_price: Decimal) -> None:
        """Update gas estimate for a chain with real-time data."""
        if chain_id in _GAS_ESTIMATES:
            est = _GAS_ESTIMATES[chain_id]
            est.gas_price_gwei = gas_price_gwei
            est.cost_native = (
                Decimal(est.gas_units) * gas_price_gwei / Decimal("1e9")
            )
            est.cost_usd = (est.cost_native * native_usd_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

    # ------------------------------------------------------------------
    # Opportunity detection
    # ------------------------------------------------------------------

    def analyze_peg_opportunities(
        self,
        wqusd_prices: Dict[int, Optional[Decimal]],
        stabilizer_qbc_balance: Decimal = Decimal("0"),
        stabilizer_qusd_balance: Decimal = Decimal("0"),
    ) -> List[ArbOpportunity]:
        """Analyze wQUSD prices across chains for peg arb opportunities.

        Args:
            wqusd_prices: Dict of chain_id -> wQUSD USD price.
            stabilizer_qbc_balance: QBC in stabilizer fund (floor defense).
            stabilizer_qusd_balance: QUSD in stabilizer (ceiling defense).

        Returns:
            List of ArbOpportunity, sorted by net_profit descending.
        """
        opps: List[ArbOpportunity] = []
        now = time.time()

        for chain_id, price in wqusd_prices.items():
            if price is None:
                continue

            spread = price - self.PEG_TARGET
            spread_bps = int(abs(spread) * Decimal("10000"))

            # --- Floor arb: wQUSD < $0.99 ---
            if price < self.FLOOR_PRICE:
                gas = self._get_gas_cost(chain_id)
                trade_size = min(self.DEFAULT_TRADE_SIZE,
                                 stabilizer_qbc_balance * price)
                trade_size = max(trade_size, self.MIN_TRADE_SIZE)

                gross = trade_size * abs(spread)
                bridge_fee = self._bridge_fee(trade_size)
                net = gross - gas.cost_usd - bridge_fee
                roi = (net / trade_size * 100) if trade_size > 0 else Decimal("0")

                state = _GAS_ESTIMATES.get(chain_id)
                chain_name = state.chain_name if state else f"Chain-{chain_id}"

                opp = ArbOpportunity(
                    id=f"peg_floor_{chain_id}_{int(now)}",
                    arb_type=ArbType.PEG_FLOOR,
                    action=ArbAction.STABILIZER if chain_id == 3301 else ArbAction.BUY_WQUSD,
                    chain_id=chain_id, chain_name=chain_name,
                    current_price=price, target_price=self.PEG_TARGET,
                    spread_bps=spread_bps,
                    trade_size_usd=trade_size.quantize(Decimal("0.01")),
                    gross_profit_usd=gross.quantize(Decimal("0.01")),
                    gas_cost_usd=gas.cost_usd,
                    bridge_fee_usd=bridge_fee,
                    net_profit_usd=net.quantize(Decimal("0.01")),
                    roi_pct=roi.quantize(Decimal("0.01")),
                    profitable=net > self.MIN_PROFIT_USD,
                    confidence=0.9,
                    timestamp=now,
                )
                opps.append(opp)

            # --- Ceiling arb: wQUSD > $1.01 ---
            elif price > self.CEILING_PRICE:
                gas = self._get_gas_cost(chain_id)
                trade_size = min(self.DEFAULT_TRADE_SIZE,
                                 stabilizer_qusd_balance)
                trade_size = max(trade_size, self.MIN_TRADE_SIZE)

                gross = trade_size * abs(spread)
                bridge_fee = self._bridge_fee(trade_size)
                net = gross - gas.cost_usd - bridge_fee
                roi = (net / trade_size * 100) if trade_size > 0 else Decimal("0")

                state = _GAS_ESTIMATES.get(chain_id)
                chain_name = state.chain_name if state else f"Chain-{chain_id}"

                opp = ArbOpportunity(
                    id=f"peg_ceiling_{chain_id}_{int(now)}",
                    arb_type=ArbType.PEG_CEILING,
                    action=ArbAction.STABILIZER if chain_id == 3301 else ArbAction.SELL_WQUSD,
                    chain_id=chain_id, chain_name=chain_name,
                    current_price=price, target_price=self.PEG_TARGET,
                    spread_bps=spread_bps,
                    trade_size_usd=trade_size.quantize(Decimal("0.01")),
                    gross_profit_usd=gross.quantize(Decimal("0.01")),
                    gas_cost_usd=gas.cost_usd,
                    bridge_fee_usd=bridge_fee,
                    net_profit_usd=net.quantize(Decimal("0.01")),
                    roi_pct=roi.quantize(Decimal("0.01")),
                    profitable=net > self.MIN_PROFIT_USD,
                    confidence=0.9,
                    timestamp=now,
                )
                opps.append(opp)

        # Sort by net profit descending
        opps.sort(key=lambda o: o.net_profit_usd, reverse=True)
        return opps

    def analyze_cross_chain_opportunities(
        self,
        wqusd_prices: Dict[int, Optional[Decimal]],
    ) -> List[ArbOpportunity]:
        """Find cross-chain arb opportunities where wQUSD price differs.

        If wQUSD is $0.98 on BSC and $1.01 on Ethereum, an arbitrageur
        can buy on BSC, bridge to Ethereum, and sell for ~3% profit.
        """
        opps: List[ArbOpportunity] = []
        now = time.time()

        # Get all chains with valid prices
        valid = {cid: p for cid, p in wqusd_prices.items() if p is not None}
        chain_ids = list(valid.keys())

        for i in range(len(chain_ids)):
            for j in range(i + 1, len(chain_ids)):
                cid_a, cid_b = chain_ids[i], chain_ids[j]
                price_a, price_b = valid[cid_a], valid[cid_b]

                spread = abs(price_a - price_b)
                spread_bps = int(spread * Decimal("10000"))

                # Need at least 1% spread to cover 2x bridge fees + gas
                min_spread = Decimal("0.01")
                if spread < min_spread:
                    continue

                # Determine direction: buy cheap, sell expensive
                if price_a < price_b:
                    buy_chain, sell_chain = cid_a, cid_b
                    buy_price, sell_price = price_a, price_b
                else:
                    buy_chain, sell_chain = cid_b, cid_a
                    buy_price, sell_price = price_b, price_a

                gas_buy = self._get_gas_cost(buy_chain)
                gas_sell = self._get_gas_cost(sell_chain)
                total_gas = gas_buy.cost_usd + gas_sell.cost_usd

                trade_size = self.DEFAULT_TRADE_SIZE
                gross = trade_size * spread
                bridge_fee = self._bridge_fee(trade_size, hops=2)  # 2 bridge hops
                net = gross - total_gas - bridge_fee
                roi = (net / trade_size * 100) if trade_size > 0 else Decimal("0")

                buy_state = _GAS_ESTIMATES.get(buy_chain)
                sell_state = _GAS_ESTIMATES.get(sell_chain)
                buy_name = buy_state.chain_name if buy_state else f"Chain-{buy_chain}"
                sell_name = sell_state.chain_name if sell_state else f"Chain-{sell_chain}"

                opp = ArbOpportunity(
                    id=f"xchain_{buy_chain}_{sell_chain}_{int(now)}",
                    arb_type=ArbType.CROSS_CHAIN,
                    action=ArbAction.BRIDGE_BUY,
                    chain_id=buy_chain, chain_name=buy_name,
                    current_price=buy_price, target_price=sell_price,
                    spread_bps=spread_bps,
                    trade_size_usd=trade_size.quantize(Decimal("0.01")),
                    gross_profit_usd=gross.quantize(Decimal("0.01")),
                    gas_cost_usd=total_gas,
                    bridge_fee_usd=bridge_fee,
                    net_profit_usd=net.quantize(Decimal("0.01")),
                    roi_pct=roi.quantize(Decimal("0.01")),
                    profitable=net > self.MIN_PROFIT_USD,
                    confidence=0.7,  # Cross-chain arb has execution risk
                    timestamp=now,
                    dest_chain_id=sell_chain,
                    dest_chain_name=sell_name,
                    dest_price=sell_price,
                )
                opps.append(opp)

        opps.sort(key=lambda o: o.net_profit_usd, reverse=True)
        return opps

    def analyze_all(
        self,
        wqusd_prices: Dict[int, Optional[Decimal]],
        stabilizer_qbc_balance: Decimal = Decimal("0"),
        stabilizer_qusd_balance: Decimal = Decimal("0"),
    ) -> List[ArbOpportunity]:
        """Run all analyses and return combined opportunities.

        Returns:
            All opportunities sorted by net_profit descending.
        """
        peg_opps = self.analyze_peg_opportunities(
            wqusd_prices, stabilizer_qbc_balance, stabilizer_qusd_balance,
        )
        xchain_opps = self.analyze_cross_chain_opportunities(wqusd_prices)

        all_opps = peg_opps + xchain_opps
        all_opps.sort(key=lambda o: o.net_profit_usd, reverse=True)

        # Store and trim history
        self._opportunities = all_opps
        self._history.extend(all_opps)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return all_opps

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_current_opportunities(self, profitable_only: bool = True
                                  ) -> List[ArbOpportunity]:
        """Get current opportunities."""
        if profitable_only:
            return [o for o in self._opportunities if o.profitable]
        return list(self._opportunities)

    def get_history(self, limit: int = 100) -> List[ArbOpportunity]:
        """Get recent opportunity history."""
        return self._history[-limit:]

    def get_summary(self) -> Dict[str, object]:
        """Summary for RPC endpoint."""
        profitable = [o for o in self._opportunities if o.profitable]
        return {
            "total_opportunities": len(self._opportunities),
            "profitable_opportunities": len(profitable),
            "best_opportunity": _opp_to_dict(profitable[0]) if profitable else None,
            "total_net_profit_usd": str(sum(
                o.net_profit_usd for o in profitable
            )),
            "history_size": len(self._history),
        }


def _opp_to_dict(opp: ArbOpportunity) -> dict:
    """Convert ArbOpportunity to JSON-serializable dict."""
    return {
        "id": opp.id,
        "type": opp.arb_type.value,
        "action": opp.action.value,
        "chain_id": opp.chain_id,
        "chain_name": opp.chain_name,
        "current_price": str(opp.current_price),
        "target_price": str(opp.target_price),
        "spread_bps": opp.spread_bps,
        "trade_size_usd": str(opp.trade_size_usd),
        "gross_profit_usd": str(opp.gross_profit_usd),
        "gas_cost_usd": str(opp.gas_cost_usd),
        "bridge_fee_usd": str(opp.bridge_fee_usd),
        "net_profit_usd": str(opp.net_profit_usd),
        "roi_pct": str(opp.roi_pct),
        "profitable": opp.profitable,
        "confidence": opp.confidence,
        "timestamp": opp.timestamp,
        "dest_chain_id": opp.dest_chain_id,
        "dest_chain_name": opp.dest_chain_name,
        "dest_price": str(opp.dest_price) if opp.dest_price else None,
    }
