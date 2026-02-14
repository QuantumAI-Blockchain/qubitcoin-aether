"""
AML Monitoring Module — Transaction pattern detection

Tracks per-address transaction activity and flags suspicious patterns:
  - Rapid small transactions (structuring / smurfing)
  - Volume spikes vs historical average
  - Round-number clustering (money-laundering indicator)
  - Fan-out patterns (single address to many recipients quickly)
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ── Alert types ───────────────────────────────────────────────────────
class AlertType:
    STRUCTURING = 'structuring'           # Many small txs to avoid threshold
    VOLUME_SPIKE = 'volume_spike'         # Sudden increase vs baseline
    ROUND_AMOUNTS = 'round_amounts'       # Cluster of round-number txs
    FAN_OUT = 'fan_out'                   # 1 address → many recipients quickly
    RAPID_MOVEMENT = 'rapid_movement'     # Funds moved out very quickly after deposit


@dataclass
class AMLAlert:
    """A single AML alert raised by the monitor."""
    alert_type: str
    address: str
    score: float           # 0-100 severity
    details: str
    timestamp: float = field(default_factory=time.time)
    block_height: int = 0

    def to_dict(self) -> dict:
        return {
            'alert_type': self.alert_type,
            'address': self.address,
            'score': self.score,
            'details': self.details,
            'timestamp': self.timestamp,
            'block_height': self.block_height,
        }


@dataclass
class _TxRecord:
    """Internal transaction record for pattern analysis."""
    amount: float
    recipient: str
    timestamp: float
    block_height: int


class AMLMonitor:
    """In-memory AML monitoring engine.

    Accumulates transaction records per-address and evaluates
    configurable heuristic rules to produce ``AMLAlert`` objects.
    """

    # Configurable thresholds
    STRUCTURING_WINDOW: float = 600.0        # seconds (10 min)
    STRUCTURING_MIN_COUNT: int = 5           # min txs in window
    STRUCTURING_MAX_AMOUNT: float = 1000.0   # each tx below this

    VOLUME_SPIKE_MULTIPLIER: float = 5.0     # x times average = spike
    VOLUME_BASELINE_WINDOW: int = 100        # blocks for baseline calc

    ROUND_AMOUNT_TOLERANCE: float = 0.01     # < 1% of nearest round = round
    ROUND_MIN_COUNT: int = 3                 # min round-amount txs to flag

    FAN_OUT_WINDOW: float = 300.0            # seconds (5 min)
    FAN_OUT_MIN_RECIPIENTS: int = 5          # unique recipients

    def __init__(self) -> None:
        self._address_txs: Dict[str, List[_TxRecord]] = defaultdict(list)
        self._alerts: List[AMLAlert] = []

    def record_transaction(self, sender: str, recipient: str,
                           amount: float, timestamp: float,
                           block_height: int = 0) -> List[AMLAlert]:
        """Record a transaction and return any new alerts."""
        rec = _TxRecord(
            amount=amount,
            recipient=recipient,
            timestamp=timestamp,
            block_height=block_height,
        )
        self._address_txs[sender].append(rec)

        new_alerts: List[AMLAlert] = []
        new_alerts.extend(self._check_structuring(sender))
        new_alerts.extend(self._check_volume_spike(sender, block_height))
        new_alerts.extend(self._check_round_amounts(sender))
        new_alerts.extend(self._check_fan_out(sender))

        self._alerts.extend(new_alerts)
        return new_alerts

    def get_alerts(self, address: Optional[str] = None) -> List[AMLAlert]:
        """Return alerts, optionally filtered by address."""
        if address:
            return [a for a in self._alerts if a.address == address]
        return list(self._alerts)

    def get_risk_score(self, address: str) -> float:
        """Compute aggregate risk score for an address (0-100)."""
        addr_alerts = self.get_alerts(address)
        if not addr_alerts:
            return 0.0
        # Sum alert scores, capped at 100
        total = sum(a.score for a in addr_alerts)
        return min(total, 100.0)

    def clear_alerts(self, address: Optional[str] = None) -> int:
        """Clear alerts. Returns count removed."""
        if address:
            before = len(self._alerts)
            self._alerts = [a for a in self._alerts if a.address != address]
            return before - len(self._alerts)
        count = len(self._alerts)
        self._alerts.clear()
        return count

    # ── Pattern detectors ─────────────────────────────────────────────

    def _check_structuring(self, address: str) -> List[AMLAlert]:
        """Detect rapid small transactions (structuring)."""
        txs = self._address_txs[address]
        if len(txs) < self.STRUCTURING_MIN_COUNT:
            return []
        now = txs[-1].timestamp
        window_txs = [
            t for t in txs
            if now - t.timestamp <= self.STRUCTURING_WINDOW
            and t.amount < self.STRUCTURING_MAX_AMOUNT
        ]
        if len(window_txs) >= self.STRUCTURING_MIN_COUNT:
            return [AMLAlert(
                alert_type=AlertType.STRUCTURING,
                address=address,
                score=30.0,
                details=f"{len(window_txs)} small txs in {self.STRUCTURING_WINDOW}s window",
            )]
        return []

    def _check_volume_spike(self, address: str, current_block: int) -> List[AMLAlert]:
        """Detect sudden volume increase vs baseline."""
        txs = self._address_txs[address]
        if len(txs) < 2:
            return []
        baseline_txs = [
            t for t in txs
            if current_block - t.block_height <= self.VOLUME_BASELINE_WINDOW
        ]
        if len(baseline_txs) < 2:
            return []
        total_amount = sum(t.amount for t in baseline_txs)
        avg = total_amount / len(baseline_txs)
        latest = txs[-1].amount
        if avg > 0 and latest > avg * self.VOLUME_SPIKE_MULTIPLIER:
            return [AMLAlert(
                alert_type=AlertType.VOLUME_SPIKE,
                address=address,
                score=25.0,
                details=f"Tx amount {latest:.2f} is {latest/avg:.1f}x the average {avg:.2f}",
                block_height=current_block,
            )]
        return []

    def _check_round_amounts(self, address: str) -> List[AMLAlert]:
        """Detect cluster of round-number transactions."""
        txs = self._address_txs[address]
        round_count = 0
        for t in txs[-20:]:  # Check last 20 txs
            if t.amount > 0 and self._is_round(t.amount):
                round_count += 1
        if round_count >= self.ROUND_MIN_COUNT:
            return [AMLAlert(
                alert_type=AlertType.ROUND_AMOUNTS,
                address=address,
                score=15.0,
                details=f"{round_count} round-amount transactions detected",
            )]
        return []

    def _check_fan_out(self, address: str) -> List[AMLAlert]:
        """Detect 1→many fan-out pattern."""
        txs = self._address_txs[address]
        if len(txs) < self.FAN_OUT_MIN_RECIPIENTS:
            return []
        now = txs[-1].timestamp
        recent = [
            t for t in txs
            if now - t.timestamp <= self.FAN_OUT_WINDOW
        ]
        unique_recipients = len(set(t.recipient for t in recent))
        if unique_recipients >= self.FAN_OUT_MIN_RECIPIENTS:
            return [AMLAlert(
                alert_type=AlertType.FAN_OUT,
                address=address,
                score=20.0,
                details=f"{unique_recipients} unique recipients in {self.FAN_OUT_WINDOW}s",
            )]
        return []

    @staticmethod
    def _is_round(amount: float) -> bool:
        """Check if amount is a 'round' number (e.g. 100, 500, 1000)."""
        if amount <= 0:
            return False
        # Check if it's a multiple of 100 within tolerance
        remainder = amount % 100
        return remainder < 1.0 or remainder > 99.0
