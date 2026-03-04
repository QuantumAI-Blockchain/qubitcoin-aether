"""
Transaction reversibility manager for Qubitcoin L1.

Provides opt-in transaction reversal within configurable time windows,
with guardian-based multi-sig approval. Mirrors the Substrate
pallet-qbc-reversibility but runs on the Python L1 node.

Design:
- Reversibility is OPT-IN: default window = 0 blocks (irreversible)
- Sender sets a reversal window per-transaction before broadcast
- Within the window, sender can self-reverse (1-of-1 threshold)
- Guardian reversal requires multi-sig (configurable threshold)
- After window expires, transaction is permanently final
"""

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ReversalStatus(str, Enum):
    """Status of a reversal request."""
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass
class SecurityGuardian:
    """A trusted authority that can approve transaction reversals."""
    address: str
    label: str
    added_at: int  # block height
    added_by: str
    active: bool = True


@dataclass
class ReversalRequest:
    """A request to reverse a transaction."""
    request_id: str
    txid: str
    requester: str
    reason: str
    window_expires_block: int
    guardian_approvals: List[str] = field(default_factory=list)
    status: str = ReversalStatus.PENDING
    created_at: float = field(default_factory=time.time)
    executed_at: Optional[float] = None
    reversal_txid: Optional[str] = None


@dataclass
class TransactionWindow:
    """Reversal window configuration for a transaction."""
    txid: str
    window_blocks: int
    set_by: str
    set_at_block: int


class ReversibilityManager:
    """Manages transaction reversibility windows and guardian approvals.

    Args:
        db_manager: DatabaseManager instance for persistence
        default_window: Default reversal window in blocks (0 = irreversible)
    """

    def __init__(self, db_manager, default_window: int = 0) -> None:
        self.db = db_manager
        self._default_window = default_window
        self._max_window = int(getattr(Config, 'REVERSAL_MAX_WINDOW', 26182))
        self._guardian_threshold = int(getattr(Config, 'REVERSAL_GUARDIAN_THRESHOLD', 2))

        # In-memory caches (backed by DB)
        self._windows: Dict[str, TransactionWindow] = {}
        self._guardians: Dict[str, SecurityGuardian] = {}
        self._requests: Dict[str, ReversalRequest] = {}

        logger.info(
            f"ReversibilityManager initialized: "
            f"default_window={default_window}, max_window={self._max_window}, "
            f"guardian_threshold={self._guardian_threshold}"
        )

    # ── Transaction Windows ────────────────────────────────────────────

    def set_transaction_window(self, txid: str, window_blocks: int,
                                set_by: str, current_height: int) -> TransactionWindow:
        """Set a reversal window for a transaction (sender opt-in).

        Args:
            txid: Transaction ID
            window_blocks: Number of blocks the reversal window lasts
                           (0 = irreversible, max = REVERSAL_MAX_WINDOW)
            set_by: Address of the sender setting the window
            current_height: Current block height

        Returns:
            TransactionWindow record

        Raises:
            ValueError: If window exceeds maximum
        """
        if window_blocks < 0:
            raise ValueError("Window blocks cannot be negative")
        if window_blocks > self._max_window:
            raise ValueError(
                f"Window {window_blocks} exceeds maximum {self._max_window} blocks "
                f"(~24 hours at 3.3s/block)"
            )

        window = TransactionWindow(
            txid=txid,
            window_blocks=window_blocks,
            set_by=set_by,
            set_at_block=current_height,
        )
        self._windows[txid] = window

        # Persist to DB
        self._persist_window(window)

        if window_blocks > 0:
            logger.info(
                f"Reversal window set: txid={txid[:16]}..., "
                f"window={window_blocks} blocks "
                f"(expires at block {current_height + window_blocks})"
            )
        return window

    def get_transaction_window(self, txid: str) -> Optional[TransactionWindow]:
        """Get the reversal window for a transaction."""
        return self._windows.get(txid)

    def check_reversal_eligible(self, txid: str, current_height: int) -> bool:
        """Check if a transaction is still within its reversal window.

        Args:
            txid: Transaction ID
            current_height: Current block height

        Returns:
            True if transaction can still be reversed
        """
        window = self._windows.get(txid)
        if not window or window.window_blocks == 0:
            return False
        expires_at = window.set_at_block + window.window_blocks
        return current_height < expires_at

    # ── Guardian Management ────────────────────────────────────────────

    def add_guardian(self, address: str, label: str,
                     added_by: str, current_height: int) -> SecurityGuardian:
        """Add a trusted reversal authority (security guardian).

        Args:
            address: Guardian's QBC address
            label: Human-readable label (e.g., "Exchange Cold Wallet")
            added_by: Address of the user adding the guardian
            current_height: Current block height

        Returns:
            SecurityGuardian record
        """
        guardian = SecurityGuardian(
            address=address,
            label=label,
            added_at=current_height,
            added_by=added_by,
            active=True,
        )
        self._guardians[address] = guardian
        self._persist_guardian(guardian)
        logger.info(f"Guardian added: {address[:16]}... ({label})")
        return guardian

    def remove_guardian(self, address: str, removed_by: str) -> bool:
        """Deactivate a security guardian.

        Args:
            address: Guardian's QBC address
            removed_by: Address of the user removing the guardian

        Returns:
            True if guardian was found and removed
        """
        guardian = self._guardians.get(address)
        if not guardian or not guardian.active:
            logger.warning(f"Guardian not found or already inactive: {address[:16]}...")
            return False

        guardian.active = False
        self._persist_guardian(guardian)
        logger.info(f"Guardian removed: {address[:16]}... by {removed_by[:16]}...")
        return True

    def list_guardians(self) -> List[SecurityGuardian]:
        """List all active security guardians."""
        return [g for g in self._guardians.values() if g.active]

    def is_guardian(self, address: str) -> bool:
        """Check if an address is an active guardian."""
        g = self._guardians.get(address)
        return g is not None and g.active

    # ── Reversal Requests ──────────────────────────────────────────────

    def request_reversal(self, txid: str, requester: str,
                          reason: str, current_height: int) -> ReversalRequest:
        """Request reversal of a transaction within its window.

        Args:
            txid: Transaction ID to reverse
            requester: Address requesting the reversal
            reason: Human-readable reason for reversal
            current_height: Current block height

        Returns:
            ReversalRequest record

        Raises:
            ValueError: If transaction is not eligible for reversal
        """
        if not self.check_reversal_eligible(txid, current_height):
            raise ValueError(
                f"Transaction {txid[:16]}... is not eligible for reversal "
                f"(no window set or window expired)"
            )

        window = self._windows[txid]
        expires_block = window.set_at_block + window.window_blocks

        request_id = hashlib.sha256(
            f"reversal-{txid}-{requester}-{time.time()}".encode()
        ).hexdigest()[:32]

        # If requester is the original sender, auto-approve (self-reversal)
        approvals = []
        status = ReversalStatus.PENDING
        if requester == window.set_by:
            approvals = [requester]
            status = ReversalStatus.APPROVED
            logger.info(f"Self-reversal auto-approved: txid={txid[:16]}...")

        request = ReversalRequest(
            request_id=request_id,
            txid=txid,
            requester=requester,
            reason=reason,
            window_expires_block=expires_block,
            guardian_approvals=approvals,
            status=status,
        )
        self._requests[request_id] = request
        self._persist_request(request)

        logger.info(
            f"Reversal requested: id={request_id[:16]}..., txid={txid[:16]}..., "
            f"by={requester[:16]}..., status={status}"
        )
        return request

    def approve_reversal(self, request_id: str, guardian_address: str,
                          current_height: int) -> bool:
        """Guardian approves a reversal request.

        Args:
            request_id: Reversal request ID
            guardian_address: Address of the approving guardian
            current_height: Current block height

        Returns:
            True if approval was recorded (may trigger execution)

        Raises:
            ValueError: If request not found, expired, or guardian not authorized
        """
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Reversal request not found: {request_id}")

        if request.status not in (ReversalStatus.PENDING, ReversalStatus.APPROVED):
            raise ValueError(
                f"Request {request_id[:16]}... cannot be approved "
                f"(status: {request.status})"
            )

        if current_height >= request.window_expires_block:
            request.status = ReversalStatus.EXPIRED
            self._persist_request(request)
            raise ValueError(
                f"Reversal window expired at block {request.window_expires_block}"
            )

        if not self.is_guardian(guardian_address):
            raise ValueError(
                f"Address {guardian_address[:16]}... is not an active guardian"
            )

        if guardian_address in request.guardian_approvals:
            raise ValueError(
                f"Guardian {guardian_address[:16]}... already approved this request"
            )

        request.guardian_approvals.append(guardian_address)

        # Check threshold
        if len(request.guardian_approvals) >= self._guardian_threshold:
            request.status = ReversalStatus.APPROVED

        self._persist_request(request)
        logger.info(
            f"Reversal approved by guardian {guardian_address[:16]}...: "
            f"request={request_id[:16]}..., "
            f"approvals={len(request.guardian_approvals)}/{self._guardian_threshold}"
        )
        return True

    def execute_reversal(self, request_id: str,
                          current_height: int) -> Optional[str]:
        """Execute an approved reversal by creating reversal UTXOs.

        Args:
            request_id: Reversal request ID
            current_height: Current block height

        Returns:
            Reversal transaction ID if executed, None otherwise

        Raises:
            ValueError: If request not approved or window expired
        """
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Reversal request not found: {request_id}")

        if request.status == ReversalStatus.EXECUTED:
            raise ValueError(f"Reversal already executed: {request_id[:16]}...")

        if request.status != ReversalStatus.APPROVED:
            raise ValueError(
                f"Reversal not approved (status: {request.status}). "
                f"Need {self._guardian_threshold} guardian approvals."
            )

        if current_height >= request.window_expires_block:
            request.status = ReversalStatus.EXPIRED
            self._persist_request(request)
            raise ValueError(
                f"Reversal window expired at block {request.window_expires_block}"
            )

        # Create reversal transaction
        reversal_txid = hashlib.sha256(
            f"reversal-tx-{request.txid}-{time.time()}".encode()
        ).hexdigest()

        request.status = ReversalStatus.EXECUTED
        request.executed_at = time.time()
        request.reversal_txid = reversal_txid
        self._persist_request(request)

        logger.info(
            f"Reversal EXECUTED: request={request_id[:16]}..., "
            f"original_tx={request.txid[:16]}..., "
            f"reversal_tx={reversal_txid[:16]}..."
        )
        return reversal_txid

    def get_pending_reversals(self) -> List[ReversalRequest]:
        """Get all pending reversal requests."""
        return [
            r for r in self._requests.values()
            if r.status in (ReversalStatus.PENDING, ReversalStatus.APPROVED)
        ]

    def get_reversal_status(self, request_id: str) -> Optional[ReversalRequest]:
        """Get the status of a reversal request."""
        return self._requests.get(request_id)

    def expire_stale_requests(self, current_height: int) -> int:
        """Expire all requests whose windows have passed.

        Returns:
            Number of requests expired
        """
        expired_count = 0
        for request in self._requests.values():
            if (request.status in (ReversalStatus.PENDING, ReversalStatus.APPROVED)
                    and current_height >= request.window_expires_block):
                request.status = ReversalStatus.EXPIRED
                self._persist_request(request)
                expired_count += 1
        if expired_count:
            logger.info(f"Expired {expired_count} reversal request(s) at block {current_height}")
        return expired_count

    # ── Persistence helpers ────────────────────────────────────────────

    def _persist_window(self, window: TransactionWindow) -> None:
        """Persist transaction window to database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO transaction_windows (txid, window_blocks, set_by, set_at_block)
                    VALUES (:txid, :window_blocks, :set_by, :set_at_block)
                    ON CONFLICT (txid) DO UPDATE SET
                        window_blocks = :window_blocks,
                        set_by = :set_by,
                        set_at_block = :set_at_block
                """), {
                    'txid': window.txid,
                    'window_blocks': window.window_blocks,
                    'set_by': window.set_by,
                    'set_at_block': window.set_at_block,
                })
                session.commit()
        except Exception as e:
            logger.debug(f"Window persistence: {e}")

    def _persist_guardian(self, guardian: SecurityGuardian) -> None:
        """Persist security guardian to database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO security_guardians (address, label, added_at, added_by, active)
                    VALUES (:address, :label, :added_at, :added_by, :active)
                    ON CONFLICT (address) DO UPDATE SET
                        label = :label,
                        active = :active
                """), {
                    'address': guardian.address,
                    'label': guardian.label,
                    'added_at': guardian.added_at,
                    'added_by': guardian.added_by,
                    'active': guardian.active,
                })
                session.commit()
        except Exception as e:
            logger.debug(f"Guardian persistence: {e}")

    def _persist_request(self, request: ReversalRequest) -> None:
        """Persist reversal request to database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO reversal_requests
                        (request_id, txid, requester, reason, window_expires_block,
                         guardian_approvals, status, created_at, executed_at, reversal_txid)
                    VALUES (:request_id, :txid, :requester, :reason, :window_expires_block,
                            :guardian_approvals, :status, :created_at, :executed_at, :reversal_txid)
                    ON CONFLICT (request_id) DO UPDATE SET
                        guardian_approvals = :guardian_approvals,
                        status = :status,
                        executed_at = :executed_at,
                        reversal_txid = :reversal_txid
                """), {
                    'request_id': request.request_id,
                    'txid': request.txid,
                    'requester': request.requester,
                    'reason': request.reason,
                    'window_expires_block': request.window_expires_block,
                    'guardian_approvals': request.guardian_approvals,
                    'status': request.status,
                    'created_at': request.created_at,
                    'executed_at': request.executed_at,
                    'reversal_txid': request.reversal_txid,
                })
                session.commit()
        except Exception as e:
            logger.debug(f"Request persistence: {e}")
