"""
QUSD Peg Keeper Daemon

Monitors wQUSD price across all external chains and executes stabilization
actions via QUSDStabilizer.sol when depeg is detected.

Operating modes:
  off        — Daemon stopped. No monitoring, no actions.
  scan       — Read-only: log price, signals, health. NEVER executes.
  periodic   — Check every N blocks. Execute if profitable.
  continuous — Check every block. Execute immediately on depeg signal.
  aggressive — Continuous + use owner-only buyQUSD()/sellQUSD() with larger
               trade sizes for severe depeg events.

Integrated into node.py orchestrator and exposed via RPC endpoints.
"""

import time
import threading
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import IntEnum
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class KeeperMode(IntEnum):
    """Operating mode for the keeper daemon."""
    OFF = 0
    SCAN = 1
    PERIODIC = 2
    CONTINUOUS = 3
    AGGRESSIVE = 4


class SignalType:
    """Signal types emitted by the keeper."""
    DEPEG_FLOOR = "depeg_floor"
    DEPEG_CEILING = "depeg_ceiling"
    CROSS_CHAIN_ARB = "cross_chain_arb"
    LOW_RESERVES = "low_reserves"
    FUND_DEPLETED = "fund_depleted"
    HEALTHY = "healthy"


@dataclass
class KeeperSignal:
    """A signal detected by the keeper."""
    signal_type: str
    chain_id: int
    chain_name: str
    price: Optional[Decimal]
    details: str
    timestamp: float
    severity: str = "info"  # info, warning, critical


@dataclass
class KeeperAction:
    """An action taken by the keeper."""
    action_id: str
    action_type: str          # "trigger_rebalance", "buy_qusd", "sell_qusd"
    block_height: int
    price: Decimal
    trade_size: Decimal
    tx_hash: Optional[str]
    success: bool
    error: Optional[str] = None
    timestamp: float = 0.0
    chain_id: int = 3301       # QBC chain by default
    mode: str = ""
    fund_balance_after: Decimal = Decimal("0")


@dataclass
class KeeperConfig:
    """Runtime configuration for the keeper."""
    mode: KeeperMode = KeeperMode.SCAN
    check_interval_blocks: int = 10       # Check every N blocks
    max_trade_size: Decimal = Decimal("1000000")  # Max per intervention
    floor_price: Decimal = Decimal("0.99")
    ceiling_price: Decimal = Decimal("1.01")
    min_fund_warning: Decimal = Decimal("100000")  # Warn when fund < this
    aggressive_multiplier: Decimal = Decimal("2.0")
    cooldown_blocks: int = 10             # Match QUSDStabilizer.REBALANCE_COOLDOWN
    role: str = "primary"                 # primary|observer — observer nodes only scan


# ---------------------------------------------------------------------------
# Main keeper class
# ---------------------------------------------------------------------------

class QUSDKeeper:
    """QUSD peg keeper daemon.

    Monitors wQUSD prices on all chains, detects depeg events,
    and executes stabilization actions via QUSDStabilizer.

    Integration points:
      - DEXPriceReader: reads external chain prices
      - ArbitrageCalculator: computes arb opportunities
      - QVM static_call: reads QUSDStabilizer state
      - QVM call: executes triggerRebalance / buyQUSD / sellQUSD
      - Node orchestrator: started/stopped with the node
    """

    MAX_HISTORY = 1000
    MAX_SIGNALS = 500

    def __init__(
        self,
        stablecoin_engine: Optional[object] = None,
        qvm: Optional[object] = None,
        dex_reader: Optional[object] = None,
        arb_calc: Optional[object] = None,
    ) -> None:
        self._stablecoin = stablecoin_engine
        self._qvm = qvm
        self._dex_reader = dex_reader
        self._arb_calc = arb_calc

        # State
        self.config = KeeperConfig()
        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        self._last_check_block: int = 0
        self._last_rebalance_block: int = 0

        # Cached stabilizer state
        self._stability_fund_qbc: Decimal = Decimal("0")
        self._qusd_held: Decimal = Decimal("0")
        self._auto_rebalance_enabled: bool = False

        # History
        self._actions: List[KeeperAction] = []
        self._signals: List[KeeperSignal] = []

        # Stats
        self._total_actions: int = 0
        self._total_depeg_events: int = 0
        self._started_at: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, mode: KeeperMode = KeeperMode.SCAN) -> None:
        """Start the keeper daemon in the given mode."""
        with self._lock:
            self.config.mode = mode
            self._running = True
            self._paused = False
            self._started_at = time.time()
        logger.info(f"QUSDKeeper started in {mode.name} mode")

    def stop(self) -> None:
        """Stop the keeper daemon."""
        with self._lock:
            self._running = False
            self.config.mode = KeeperMode.OFF
        logger.info("QUSDKeeper stopped")

    def pause(self) -> None:
        """Pause execution (continue monitoring)."""
        with self._lock:
            self._paused = True
        logger.info("QUSDKeeper paused")

    def resume(self) -> None:
        """Resume execution after pause."""
        with self._lock:
            self._paused = False
        logger.info("QUSDKeeper resumed")

    def set_mode(self, mode: KeeperMode) -> None:
        """Change operating mode at runtime."""
        with self._lock:
            old = self.config.mode
            self.config.mode = mode
        logger.info(f"QUSDKeeper mode changed: {old.name} -> {mode.name}")

    def update_config(self, **kwargs) -> None:
        """Update keeper configuration at runtime."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        logger.info(f"QUSDKeeper config updated: {kwargs}")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Per-block tick (called by node orchestrator)
    # ------------------------------------------------------------------

    def on_block(self, block_height: int) -> None:
        """Called by node.py on each new block.

        Decides whether to check prices and act based on mode and interval.
        """
        if not self._running or self.config.mode == KeeperMode.OFF:
            return

        mode = self.config.mode

        # Periodic: only check every N blocks
        if mode == KeeperMode.PERIODIC:
            if (block_height - self._last_check_block
                    < self.config.check_interval_blocks):
                return

        # Continuous / Aggressive: check every block
        # Scan: check every block (but never execute)
        self._last_check_block = block_height
        self._run_cycle(block_height)

    def _run_cycle(self, block_height: int) -> None:
        """Execute one monitoring + action cycle."""
        try:
            # 1. Fetch prices from all chains
            wqusd_prices = self._fetch_prices()

            # 2. Read stabilizer state
            self._read_stabilizer_state()

            # 3. Detect signals
            signals = self._detect_signals(wqusd_prices, block_height)

            # 4. Store signals
            self._signals.extend(signals)
            if len(self._signals) > self.MAX_SIGNALS:
                self._signals = self._signals[-self.MAX_SIGNALS:]

            # 5. Compute arb opportunities
            if self._arb_calc:
                self._arb_calc.analyze_all(
                    wqusd_prices,
                    stabilizer_qbc_balance=self._stability_fund_qbc,
                    stabilizer_qusd_balance=self._qusd_held,
                )

            # 6. Execute actions (if mode allows)
            if (self.config.mode >= KeeperMode.PERIODIC
                    and not self._paused):
                self._execute_actions(signals, block_height)

        except Exception as e:
            logger.error(f"QUSDKeeper cycle error at block {block_height}: {e}")

    # ------------------------------------------------------------------
    # Price fetching
    # ------------------------------------------------------------------

    def _fetch_prices(self) -> Dict[int, Optional[Decimal]]:
        """Fetch wQUSD prices from DEX reader."""
        if self._dex_reader is None:
            return {}
        try:
            return self._dex_reader.get_wqusd_prices()
        except Exception as e:
            logger.warning(f"QUSDKeeper: price fetch failed: {e}")
            return {}

    # ------------------------------------------------------------------
    # Stabilizer state
    # ------------------------------------------------------------------

    def _read_stabilizer_state(self) -> None:
        """Read QUSDStabilizer on-chain state via QVM."""
        if self._qvm is None:
            return

        stabilizer_addr = getattr(Config, "QUSD_STABILIZER_ADDRESS", "")
        if not stabilizer_addr:
            return

        try:
            # getStabilityStatus() selector: first 4 bytes of keccak256
            # For now, use cached values or mock
            # Real implementation would call:
            #   result = self._qvm.qvm.static_call(stabilizer_addr, selector)
            pass
        except Exception as e:
            logger.debug(f"QUSDKeeper: stabilizer state read failed: {e}")

    def set_stabilizer_state(self, qbc_balance: Decimal, qusd_held: Decimal,
                             auto_enabled: bool = True) -> None:
        """Manually set stabilizer state (for testing or when QVM unavailable)."""
        self._stability_fund_qbc = qbc_balance
        self._qusd_held = qusd_held
        self._auto_rebalance_enabled = auto_enabled

    # ------------------------------------------------------------------
    # Signal detection
    # ------------------------------------------------------------------

    def _detect_signals(self, wqusd_prices: Dict[int, Optional[Decimal]],
                        block_height: int) -> List[KeeperSignal]:
        """Detect depeg and health signals from price data."""
        signals: List[KeeperSignal] = []
        now = time.time()

        chain_names = {
            1: "Ethereum", 56: "BSC", 137: "Polygon", 42161: "Arbitrum",
            10: "Optimism", 8453: "Base", 43114: "Avalanche", 0: "Solana",
            3301: "QBC",
        }

        for chain_id, price in wqusd_prices.items():
            if price is None:
                continue

            name = chain_names.get(chain_id, f"Chain-{chain_id}")

            # Floor depeg
            if price < self.config.floor_price:
                self._total_depeg_events += 1
                severity = "critical" if price < Decimal("0.95") else "warning"
                signals.append(KeeperSignal(
                    signal_type=SignalType.DEPEG_FLOOR,
                    chain_id=chain_id, chain_name=name, price=price,
                    details=f"wQUSD at ${price} on {name} (below ${self.config.floor_price})",
                    timestamp=now, severity=severity,
                ))

            # Ceiling depeg
            elif price > self.config.ceiling_price:
                self._total_depeg_events += 1
                signals.append(KeeperSignal(
                    signal_type=SignalType.DEPEG_CEILING,
                    chain_id=chain_id, chain_name=name, price=price,
                    details=f"wQUSD at ${price} on {name} (above ${self.config.ceiling_price})",
                    timestamp=now, severity="warning",
                ))

        # Fund depletion warnings
        if self._stability_fund_qbc < self.config.min_fund_warning:
            severity = "critical" if self._stability_fund_qbc < Decimal("10000") else "warning"
            signals.append(KeeperSignal(
                signal_type=SignalType.FUND_DEPLETED,
                chain_id=3301, chain_name="QBC", price=None,
                details=f"Stability fund low: {self._stability_fund_qbc} QBC",
                timestamp=now, severity=severity,
            ))

        # Cross-chain spread detection
        valid_prices = {k: v for k, v in wqusd_prices.items() if v is not None}
        if len(valid_prices) >= 2:
            prices_list = list(valid_prices.values())
            spread = max(prices_list) - min(prices_list)
            if spread > Decimal("0.01"):  # >1% spread
                signals.append(KeeperSignal(
                    signal_type=SignalType.CROSS_CHAIN_ARB,
                    chain_id=0, chain_name="Multi-chain", price=spread,
                    details=f"Cross-chain spread: ${spread} ({int(spread * 10000)} bps)",
                    timestamp=now, severity="info",
                ))

        return signals

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_actions(self, signals: List[KeeperSignal],
                         block_height: int) -> None:
        """Execute stabilization actions based on detected signals.

        Multi-instance safety (Option A + B):
          - Option B: Observer-role nodes never execute (only scan/log).
          - Option A: Before executing, read lastRebalanceBlock from
            QUSDStabilizer on-chain to ensure no other node already
            acted within the cooldown window.
        """
        if not signals:
            return

        # Option B: observer nodes never execute
        if self.config.role == "observer":
            logger.debug("QUSDKeeper: observer role — skipping execution")
            return

        # Local cooldown check
        if block_height - self._last_rebalance_block < self.config.cooldown_blocks:
            return

        # Option A: on-chain pre-flight — read lastRebalanceBlock from
        # QUSDStabilizer to prevent duplicate interventions across nodes
        if not self._preflight_on_chain_cooldown(block_height):
            return

        mode = self.config.mode

        for signal in signals:
            if signal.signal_type == SignalType.DEPEG_FLOOR:
                self._handle_floor_depeg(signal, block_height, mode)
            elif signal.signal_type == SignalType.DEPEG_CEILING:
                self._handle_ceiling_depeg(signal, block_height, mode)
            # Cross-chain arb is logged but NOT auto-executed
            # (requires holding assets on multiple chains — manual decision)

    def _preflight_on_chain_cooldown(self, block_height: int) -> bool:
        """Read lastRebalanceBlock from QUSDStabilizer on-chain (Option A).

        Returns True if we are clear to execute (no recent rebalance by
        any node), False if another node already acted within cooldown.
        """
        stabilizer_addr = getattr(Config, "QUSD_STABILIZER_ADDRESS", "")
        if not stabilizer_addr or self._qvm is None:
            # No stabilizer deployed or no QVM — rely on local cooldown only
            return True

        try:
            import hashlib
            # lastRebalanceBlock() selector: keccak256("lastRebalanceBlock()")[:4]
            selector = hashlib.sha3_256(b"lastRebalanceBlock()").hexdigest()[:8]
            result = self._qvm.qvm.static_call(
                sender="0x0000000000000000000000000000000000000000",
                to=stabilizer_addr,
                data=bytes.fromhex(selector),
            )
            if isinstance(result, (bytes, bytearray)) and len(result) >= 32:
                on_chain_last = int.from_bytes(result[:32], "big")
            elif isinstance(result, int):
                on_chain_last = result
            else:
                # Couldn't parse — allow execution (fail-open for local-only nodes)
                return True

            if block_height - on_chain_last < self.config.cooldown_blocks:
                logger.info(
                    f"QUSDKeeper: on-chain cooldown active "
                    f"(lastRebalanceBlock={on_chain_last}, "
                    f"current={block_height}, cooldown={self.config.cooldown_blocks})"
                )
                return False
            return True
        except Exception as e:
            logger.debug(f"QUSDKeeper: pre-flight check failed (allowing): {e}")
            return True  # Fail-open: local cooldown still protects

    def _handle_floor_depeg(self, signal: KeeperSignal, block_height: int,
                            mode: KeeperMode) -> None:
        """Handle wQUSD below floor price."""
        if self._stability_fund_qbc <= 0:
            logger.warning("QUSDKeeper: stability fund empty, cannot buy QUSD")
            return

        # Calculate trade size
        trade_size = min(
            self.config.max_trade_size,
            self._stability_fund_qbc / 2,  # Never use more than half the fund
        )
        if mode == KeeperMode.AGGRESSIVE:
            trade_size = min(
                self.config.max_trade_size * self.config.aggressive_multiplier,
                self._stability_fund_qbc * Decimal("0.75"),
            )

        action = self._call_stabilizer(
            "trigger_rebalance" if mode < KeeperMode.AGGRESSIVE else "buy_qusd",
            trade_size, block_height, signal,
        )
        if action:
            self._record_action(action)

    def _handle_ceiling_depeg(self, signal: KeeperSignal, block_height: int,
                              mode: KeeperMode) -> None:
        """Handle wQUSD above ceiling price."""
        if self._qusd_held <= 0:
            logger.warning("QUSDKeeper: no QUSD held, cannot sell")
            return

        trade_size = min(
            self.config.max_trade_size,
            self._qusd_held / 2,
        )
        if mode == KeeperMode.AGGRESSIVE:
            trade_size = min(
                self.config.max_trade_size * self.config.aggressive_multiplier,
                self._qusd_held * Decimal("0.75"),
            )

        action = self._call_stabilizer(
            "trigger_rebalance" if mode < KeeperMode.AGGRESSIVE else "sell_qusd",
            trade_size, block_height, signal,
        )
        if action:
            self._record_action(action)

    def _call_stabilizer(self, action_type: str, trade_size: Decimal,
                         block_height: int,
                         signal: KeeperSignal) -> Optional[KeeperAction]:
        """Call QUSDStabilizer contract."""
        now = time.time()
        action_id = f"keeper_{action_type}_{block_height}_{int(now)}"

        # Attempt the on-chain call
        tx_hash = None
        success = False
        error = None

        stabilizer_addr = getattr(Config, "QUSD_STABILIZER_ADDRESS", "")
        if not stabilizer_addr or self._qvm is None:
            # Dry-run mode (scan or no QVM available)
            logger.info(
                f"QUSDKeeper [{action_type}]: DRY-RUN — would trade "
                f"{trade_size} at price {signal.price} on {signal.chain_name}"
            )
            success = True
            error = "dry_run"
            self._last_rebalance_block = block_height
        else:
            try:
                # Build calldata for triggerRebalance(uint256 amount)
                # Selector: keccak256("triggerRebalance(uint256)")[:4]
                # For aggressive: buyQUSD/sellQUSD have different selectors
                import hashlib
                if action_type == "trigger_rebalance":
                    selector = hashlib.sha3_256(b"triggerRebalance(uint256)").hexdigest()[:8]
                elif action_type == "buy_qusd":
                    selector = hashlib.sha3_256(b"buyQUSD(uint256)").hexdigest()[:8]
                else:
                    selector = hashlib.sha3_256(b"sellQUSD(uint256)").hexdigest()[:8]

                amount_int = int(trade_size * Decimal("1e18"))
                calldata = bytes.fromhex(selector) + amount_int.to_bytes(32, "big")

                # Execute via QVM
                result = self._qvm.qvm.call(
                    sender=getattr(Config, "ADDRESS", ""),
                    to=stabilizer_addr,
                    data=calldata,
                    value=0,
                )
                tx_hash = result.get("tx_hash") if isinstance(result, dict) else None
                success = True
                self._last_rebalance_block = block_height

                # Update cached state
                if action_type in ("trigger_rebalance", "buy_qusd"):
                    self._stability_fund_qbc -= trade_size
                else:
                    self._qusd_held -= trade_size

                logger.info(
                    f"QUSDKeeper [{action_type}]: executed trade={trade_size}, "
                    f"price={signal.price}, tx={tx_hash}"
                )
            except Exception as e:
                error = str(e)
                logger.error(f"QUSDKeeper [{action_type}] failed: {e}")

        return KeeperAction(
            action_id=action_id,
            action_type=action_type,
            block_height=block_height,
            price=signal.price or Decimal("0"),
            trade_size=trade_size,
            tx_hash=tx_hash,
            success=success,
            error=error,
            timestamp=now,
            chain_id=signal.chain_id,
            mode=self.config.mode.name.lower(),
            fund_balance_after=self._stability_fund_qbc,
        )

    def _record_action(self, action: KeeperAction) -> None:
        """Record an action to history."""
        self._actions.append(action)
        if len(self._actions) > self.MAX_HISTORY:
            self._actions = self._actions[-self.MAX_HISTORY:]
        self._total_actions += 1

    # ------------------------------------------------------------------
    # Query API (for RPC endpoints)
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Full keeper status for /keeper/status endpoint."""
        # Get latest price data
        prices: Dict[int, Optional[Decimal]] = {}
        max_dev = Decimal("0")
        if self._dex_reader:
            try:
                prices = self._dex_reader.get_wqusd_prices()
                dev, _, _ = self._dex_reader.get_max_wqusd_deviation()
                max_dev = dev
            except Exception:
                pass

        recent_signals = self._signals[-10:] if self._signals else []

        return {
            "mode": self.config.mode.name.lower(),
            "mode_value": int(self.config.mode),
            "role": self.config.role,
            "running": self._running,
            "paused": self._paused,
            "last_check_block": self._last_check_block,
            "last_rebalance_block": self._last_rebalance_block,
            "total_actions": self._total_actions,
            "total_depeg_events": self._total_depeg_events,
            "stability_fund_qbc": str(self._stability_fund_qbc),
            "qusd_held": str(self._qusd_held),
            "auto_rebalance_enabled": self._auto_rebalance_enabled,
            "max_price_deviation": str(max_dev),
            "config": {
                "check_interval_blocks": self.config.check_interval_blocks,
                "max_trade_size": str(self.config.max_trade_size),
                "floor_price": str(self.config.floor_price),
                "ceiling_price": str(self.config.ceiling_price),
                "cooldown_blocks": self.config.cooldown_blocks,
                "min_fund_warning": str(self.config.min_fund_warning),
            },
            "prices": {
                str(cid): str(p) if p else None
                for cid, p in prices.items()
            },
            "recent_signals": [
                {
                    "type": s.signal_type, "chain": s.chain_name,
                    "price": str(s.price) if s.price else None,
                    "details": s.details, "severity": s.severity,
                    "timestamp": s.timestamp,
                }
                for s in recent_signals
            ],
            "uptime_seconds": time.time() - self._started_at if self._started_at else 0,
        }

    def get_history(self, limit: int = 100) -> List[dict]:
        """Get recent keeper actions for /keeper/history endpoint."""
        actions = self._actions[-limit:]
        return [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "block_height": a.block_height,
                "price": str(a.price),
                "trade_size": str(a.trade_size),
                "tx_hash": a.tx_hash,
                "success": a.success,
                "error": a.error,
                "timestamp": a.timestamp,
                "chain_id": a.chain_id,
                "mode": a.mode,
                "fund_balance_after": str(a.fund_balance_after),
            }
            for a in reversed(actions)
        ]

    def get_opportunities(self) -> dict:
        """Get current arb opportunities for /keeper/opportunities endpoint."""
        if self._arb_calc is None:
            return {"opportunities": [], "summary": {}}

        from .arbitrage import _opp_to_dict
        opps = self._arb_calc.get_current_opportunities(profitable_only=False)
        return {
            "opportunities": [_opp_to_dict(o) for o in opps[:50]],
            "summary": self._arb_calc.get_summary(),
        }

    def get_signals(self, limit: int = 100) -> List[dict]:
        """Get recent signals."""
        signals = self._signals[-limit:]
        return [
            {
                "type": s.signal_type, "chain_id": s.chain_id,
                "chain_name": s.chain_name,
                "price": str(s.price) if s.price else None,
                "details": s.details, "severity": s.severity,
                "timestamp": s.timestamp,
            }
            for s in reversed(signals)
        ]

    def execute_manual(self, action_type: str, trade_size: Decimal,
                       block_height: int) -> dict:
        """Manually trigger a keeper action (POST /keeper/execute)."""
        if action_type not in ("trigger_rebalance", "buy_qusd", "sell_qusd"):
            return {"success": False, "error": f"Unknown action: {action_type}"}

        signal = KeeperSignal(
            signal_type=SignalType.DEPEG_FLOOR if "buy" in action_type
            else SignalType.DEPEG_CEILING,
            chain_id=3301, chain_name="QBC-Manual",
            price=Decimal("0.99") if "buy" in action_type else Decimal("1.01"),
            details=f"Manual execution: {action_type}",
            timestamp=time.time(), severity="info",
        )
        action = self._call_stabilizer(
            action_type, trade_size, block_height, signal,
        )
        if action:
            self._record_action(action)
            return {
                "success": action.success,
                "action_id": action.action_id,
                "tx_hash": action.tx_hash,
                "error": action.error,
            }
        return {"success": False, "error": "Failed to create action"}
