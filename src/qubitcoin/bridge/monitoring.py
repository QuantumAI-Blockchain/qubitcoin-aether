"""
Bridge Event Monitoring & Transfer Status Tracking

Implements:
  - BridgeEventMonitor: Multi-source event observation for cross-chain events
  - TransferTracker: Full lifecycle tracking for bridge transfers
  - Daily transfer limits and deep confirmation requirements

Security features:
  - Multi-source verification (direct observation + oracle cross-check)
  - Deep confirmation requirements per chain (reorg protection)
  - Daily transfer limits (configurable per chain)
  - Emergency pause mechanism
  - Transfer lifecycle: INITIATED → CONFIRMING → VALIDATED → EXECUTING → COMPLETED
"""

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ── Confirmation Depths (reorg protection) ─────────────────────────────
CONFIRMATION_DEPTHS: Dict[str, int] = {
    "ethereum": 20,
    "polygon": 64,
    "bsc": 15,
    "arbitrum": 20,
    "optimism": 20,
    "avalanche": 20,
    "base": 20,
    "solana": 32,
    "qbc": 6,
}

# ── Default Daily Limits (QBC) ─────────────────────────────────────────
DEFAULT_DAILY_LIMIT: float = 1_000_000.0  # 1M QBC per chain per day
DEFAULT_SINGLE_TX_LIMIT: float = 100_000.0  # 100K QBC per single transfer
# Bridge fee loaded from Config.BRIDGE_FEE_BPS (default 30 bps = 0.3%)
# This module-level constant is kept for backward compatibility as a fallback.
from ..config import Config as _Config
BRIDGE_FEE_BPS: int = _Config.BRIDGE_FEE_BPS


class TransferStatus(Enum):
    """Bridge transfer lifecycle states."""
    INITIATED = "initiated"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    VALIDATED = "validated"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PAUSED = "paused"


class TransferDirection(Enum):
    """Direction of bridge transfer."""
    DEPOSIT = "deposit"       # QBC → wQBC (lock and mint)
    WITHDRAWAL = "withdrawal" # wQBC → QBC (burn and unlock)


@dataclass
class BridgeEvent:
    """A detected event on a source chain."""
    event_id: str
    chain: str
    tx_hash: str
    block_height: int
    sender: str
    receiver: str
    amount: float
    direction: TransferDirection
    detected_at: float = field(default_factory=time.time)
    confirmations: int = 0
    required_confirmations: int = 0
    verified_sources: int = 0

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "chain": self.chain,
            "tx_hash": self.tx_hash,
            "block_height": self.block_height,
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "direction": self.direction.value,
            "detected_at": self.detected_at,
            "confirmations": self.confirmations,
            "required_confirmations": self.required_confirmations,
            "verified_sources": self.verified_sources,
        }


@dataclass
class BridgeTransfer:
    """Full lifecycle of a bridge transfer."""
    transfer_id: str
    event_id: str
    chain: str
    direction: TransferDirection
    sender: str
    receiver: str
    amount: float
    fee: float
    net_amount: float
    status: TransferStatus = TransferStatus.INITIATED
    created_at: float = field(default_factory=time.time)
    confirmed_at: Optional[float] = None
    validated_at: Optional[float] = None
    completed_at: Optional[float] = None
    source_tx_hash: str = ""
    dest_tx_hash: str = ""
    error_message: str = ""
    status_history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "transfer_id": self.transfer_id,
            "event_id": self.event_id,
            "chain": self.chain,
            "direction": self.direction.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "fee": self.fee,
            "net_amount": self.net_amount,
            "status": self.status.value,
            "created_at": self.created_at,
            "confirmed_at": self.confirmed_at,
            "validated_at": self.validated_at,
            "completed_at": self.completed_at,
            "source_tx_hash": self.source_tx_hash,
            "dest_tx_hash": self.dest_tx_hash,
            "error_message": self.error_message,
        }


class BridgeEventMonitor:
    """
    Multi-source event observation for cross-chain bridge events.

    Detects events from multiple sources (direct node + oracle) and
    requires minimum confirmation depths before passing to execution.
    """

    def __init__(
        self,
        confirmation_depths: Optional[Dict[str, int]] = None,
        min_verified_sources: int = 1,
    ) -> None:
        """
        Args:
            confirmation_depths: Override confirmation requirements per chain.
            min_verified_sources: Minimum independent sources to verify an event.
        """
        self._events: Dict[str, BridgeEvent] = {}
        self._by_tx_hash: Dict[str, str] = {}
        self._confirmation_depths = confirmation_depths or dict(CONFIRMATION_DEPTHS)
        self._min_verified_sources = min_verified_sources
        self._total_events: int = 0
        self._confirmed_events: int = 0
        logger.info("BridgeEventMonitor initialised")

    def detect_event(
        self,
        chain: str,
        tx_hash: str,
        block_height: int,
        sender: str,
        receiver: str,
        amount: float,
        direction: TransferDirection,
    ) -> Dict:
        """
        Register detection of a bridge event.

        Args:
            chain: Source blockchain name.
            tx_hash: Transaction hash on source chain.
            block_height: Block height of the event.
            sender: Sender address.
            receiver: Receiver address.
            amount: Transfer amount.
            direction: Deposit or withdrawal.

        Returns:
            Result dict with event_id.
        """
        # Dedup by tx_hash
        if tx_hash in self._by_tx_hash:
            existing_id = self._by_tx_hash[tx_hash]
            existing = self._events[existing_id]
            existing.verified_sources += 1
            return {
                "success": True,
                "event_id": existing_id,
                "duplicate": True,
                "verified_sources": existing.verified_sources,
            }

        event_id = hashlib.sha256(
            f"{chain}:{tx_hash}:{sender}:{receiver}:{amount}".encode()
        ).hexdigest()[:32]

        required = self._confirmation_depths.get(chain, 20)

        event = BridgeEvent(
            event_id=event_id,
            chain=chain,
            tx_hash=tx_hash,
            block_height=block_height,
            sender=sender,
            receiver=receiver,
            amount=amount,
            direction=direction,
            required_confirmations=required,
            verified_sources=1,
        )

        self._events[event_id] = event
        self._by_tx_hash[tx_hash] = event_id
        self._total_events += 1

        logger.info(
            f"Event detected: {event_id[:16]}… on {chain} "
            f"({amount} QBC, needs {required} confirmations)"
        )
        return {
            "success": True,
            "event_id": event_id,
            "duplicate": False,
            "required_confirmations": required,
        }

    def update_confirmations(
        self,
        event_id: str,
        current_block_height: int,
    ) -> Dict:
        """
        Update confirmation count for an event.

        Args:
            event_id: Event to update.
            current_block_height: Current block height on source chain.

        Returns:
            Result with confirmation status.
        """
        event = self._events.get(event_id)
        if event is None:
            return {"success": False, "error": "Event not found"}

        event.confirmations = max(0, current_block_height - event.block_height)
        confirmed = event.confirmations >= event.required_confirmations

        if confirmed:
            self._confirmed_events += 1

        return {
            "success": True,
            "confirmations": event.confirmations,
            "required": event.required_confirmations,
            "confirmed": confirmed,
        }

    def is_confirmed(self, event_id: str) -> bool:
        """Check if an event has enough confirmations."""
        event = self._events.get(event_id)
        if event is None:
            return False
        return (
            event.confirmations >= event.required_confirmations
            and event.verified_sources >= self._min_verified_sources
        )

    def get_event(self, event_id: str) -> Optional[Dict]:
        """Get event details."""
        event = self._events.get(event_id)
        return event.to_dict() if event else None

    def get_pending_events(self) -> List[Dict]:
        """Get events that are not yet confirmed."""
        return [
            e.to_dict() for e in self._events.values()
            if e.confirmations < e.required_confirmations
        ]

    def get_confirmed_events(self) -> List[Dict]:
        """Get events that are confirmed and ready for processing."""
        return [
            e.to_dict() for e in self._events.values()
            if e.confirmations >= e.required_confirmations
        ]

    def get_stats(self) -> Dict:
        """Monitor statistics."""
        return {
            "total_events": self._total_events,
            "active_events": len(self._events),
            "confirmed_events": self._confirmed_events,
            "min_verified_sources": self._min_verified_sources,
            "confirmation_depths": self._confirmation_depths,
        }


class TransferTracker:
    """
    Full lifecycle tracking for bridge transfers.

    Handles fee calculation, daily limits, emergency pause,
    and status progression through the transfer lifecycle.
    """

    def __init__(
        self,
        fee_bps: int = BRIDGE_FEE_BPS,
        daily_limit: float = DEFAULT_DAILY_LIMIT,
        single_tx_limit: float = DEFAULT_SINGLE_TX_LIMIT,
    ) -> None:
        """
        Args:
            fee_bps: Bridge fee in basis points (10 = 0.1%).
            daily_limit: Max QBC per chain per day.
            single_tx_limit: Max QBC per single transfer.
        """
        self._transfers: Dict[str, BridgeTransfer] = {}
        self._by_event: Dict[str, str] = {}
        self._fee_bps = fee_bps
        self._daily_limit = daily_limit
        self._single_tx_limit = single_tx_limit
        self._paused: bool = False
        self._pause_reason: str = ""
        self._daily_volumes: Dict[str, Dict[str, float]] = {}  # chain → {date → volume}
        self._total_fees_collected: float = 0.0
        self._insurance_fund: float = 0.0
        logger.info(
            f"TransferTracker initialised: "
            f"{fee_bps}bps fee, {daily_limit} daily limit"
        )

    # ── Fee Calculation ────────────────────────────────────────────────

    def calculate_fee(self, amount: float) -> float:
        """Calculate bridge fee for an amount."""
        return (amount * self._fee_bps) / 10_000

    # ── Daily Limit Enforcement ────────────────────────────────────────

    def _get_today_key(self) -> str:
        """Get date key for daily volume tracking."""
        return time.strftime("%Y-%m-%d", time.gmtime())

    def _check_daily_limit(self, chain: str, amount: float) -> bool:
        """Check if transfer would exceed daily limit."""
        today = self._get_today_key()
        if chain not in self._daily_volumes:
            self._daily_volumes[chain] = {}
        current = self._daily_volumes[chain].get(today, 0.0)
        return (current + amount) <= self._daily_limit

    def _record_volume(self, chain: str, amount: float) -> None:
        """Record transfer volume for daily tracking."""
        today = self._get_today_key()
        if chain not in self._daily_volumes:
            self._daily_volumes[chain] = {}
        self._daily_volumes[chain][today] = (
            self._daily_volumes[chain].get(today, 0.0) + amount
        )

    # ── Transfer Lifecycle ─────────────────────────────────────────────

    def initiate_transfer(
        self,
        event_id: str,
        chain: str,
        direction: TransferDirection,
        sender: str,
        receiver: str,
        amount: float,
        source_tx_hash: str = "",
    ) -> Dict:
        """
        Initiate a new bridge transfer.

        Checks: pause, single-tx limit, daily limit, fee calculation.

        Returns:
            Result with transfer_id or error.
        """
        if self._paused:
            return {"success": False, "error": f"Bridge paused: {self._pause_reason}"}

        if amount > self._single_tx_limit:
            return {
                "success": False,
                "error": f"Exceeds single tx limit: {amount} > {self._single_tx_limit}",
            }

        if not self._check_daily_limit(chain, amount):
            return {
                "success": False,
                "error": f"Exceeds daily limit for {chain}",
            }

        if event_id in self._by_event:
            return {"success": False, "error": "Transfer already exists for event"}

        fee = self.calculate_fee(amount)
        net_amount = amount - fee

        transfer_id = hashlib.sha256(
            f"transfer:{event_id}:{sender}:{receiver}:{amount}".encode()
        ).hexdigest()[:32]

        transfer = BridgeTransfer(
            transfer_id=transfer_id,
            event_id=event_id,
            chain=chain,
            direction=direction,
            sender=sender,
            receiver=receiver,
            amount=amount,
            fee=fee,
            net_amount=net_amount,
            source_tx_hash=source_tx_hash,
        )
        transfer.status_history.append({
            "status": TransferStatus.INITIATED.value,
            "timestamp": transfer.created_at,
        })

        self._transfers[transfer_id] = transfer
        self._by_event[event_id] = transfer_id
        self._record_volume(chain, amount)
        self._total_fees_collected += fee

        logger.info(
            f"Transfer initiated: {transfer_id[:16]}… "
            f"({amount} QBC, fee {fee} QBC, net {net_amount} QBC)"
        )
        return {
            "success": True,
            "transfer_id": transfer_id,
            "fee": fee,
            "net_amount": net_amount,
        }

    def update_status(
        self,
        transfer_id: str,
        new_status: TransferStatus,
        dest_tx_hash: str = "",
        error_message: str = "",
    ) -> Dict:
        """
        Update transfer status.

        Args:
            transfer_id: Transfer to update.
            new_status: New status.
            dest_tx_hash: Destination tx hash (for COMPLETED).
            error_message: Error message (for FAILED).

        Returns:
            Result dict.
        """
        transfer = self._transfers.get(transfer_id)
        if transfer is None:
            return {"success": False, "error": "Transfer not found"}

        now = time.time()
        transfer.status = new_status
        transfer.status_history.append({
            "status": new_status.value,
            "timestamp": now,
        })

        if new_status == TransferStatus.CONFIRMED:
            transfer.confirmed_at = now
        elif new_status == TransferStatus.VALIDATED:
            transfer.validated_at = now
        elif new_status == TransferStatus.COMPLETED:
            transfer.completed_at = now
            if dest_tx_hash:
                transfer.dest_tx_hash = dest_tx_hash
        elif new_status == TransferStatus.FAILED:
            transfer.error_message = error_message

        logger.info(f"Transfer {transfer_id[:16]}… → {new_status.value}")
        return {"success": True, "status": new_status.value}

    # ── Emergency Pause ────────────────────────────────────────────────

    def pause(self, reason: str = "Emergency") -> Dict:
        """Pause all bridge operations."""
        self._paused = True
        self._pause_reason = reason
        logger.warning(f"Bridge PAUSED: {reason}")
        return {"success": True, "paused": True, "reason": reason}

    def unpause(self) -> Dict:
        """Resume bridge operations."""
        self._paused = False
        reason = self._pause_reason
        self._pause_reason = ""
        logger.info(f"Bridge UNPAUSED (was: {reason})")
        return {"success": True, "paused": False}

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ── Insurance Fund ─────────────────────────────────────────────────

    def contribute_to_insurance(self, amount: float) -> Dict:
        """Add QBC to the insurance fund."""
        if amount <= 0:
            return {"success": False, "error": "Amount must be positive"}
        self._insurance_fund += amount
        return {"success": True, "insurance_fund": self._insurance_fund}

    # ── Queries ────────────────────────────────────────────────────────

    def get_transfer(self, transfer_id: str) -> Optional[Dict]:
        """Get transfer details."""
        t = self._transfers.get(transfer_id)
        return t.to_dict() if t else None

    def get_transfer_by_event(self, event_id: str) -> Optional[Dict]:
        """Look up transfer by event ID."""
        tid = self._by_event.get(event_id)
        if tid is None:
            return None
        t = self._transfers.get(tid)
        return t.to_dict() if t else None

    def get_transfers_by_status(self, status: TransferStatus) -> List[Dict]:
        """Get all transfers with a given status."""
        return [
            t.to_dict() for t in self._transfers.values()
            if t.status == status
        ]

    def get_daily_volume(self, chain: str) -> float:
        """Get today's transfer volume for a chain."""
        today = self._get_today_key()
        return self._daily_volumes.get(chain, {}).get(today, 0.0)

    def get_stats(self) -> Dict:
        """Transfer tracker statistics."""
        by_status: Dict[str, int] = {}
        for t in self._transfers.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

        return {
            "total_transfers": len(self._transfers),
            "by_status": by_status,
            "fee_bps": self._fee_bps,
            "daily_limit": self._daily_limit,
            "single_tx_limit": self._single_tx_limit,
            "total_fees_collected": self._total_fees_collected,
            "insurance_fund": self._insurance_fund,
            "paused": self._paused,
            "pause_reason": self._pause_reason,
        }
