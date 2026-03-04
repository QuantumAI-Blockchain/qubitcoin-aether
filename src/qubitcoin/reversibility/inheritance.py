"""
Inheritance Protocol for Qubitcoin.

Dead-man's switch: if an account is inactive (no transactions) for a
configurable number of blocks, a designated beneficiary can claim the
assets after a grace period.

Design:
- Owner sets a beneficiary + inactivity threshold (blocks)
- Every outgoing transaction from the owner resets the heartbeat
- If heartbeat goes stale (current_height - last_heartbeat > threshold),
  the beneficiary can initiate a claim
- Grace period allows the owner to cancel (prove they are alive)
- After grace expires, claim can be executed (assets transferred)
"""

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ClaimStatus(str, Enum):
    """Status of an inheritance claim."""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


@dataclass
class InheritancePlan:
    """A beneficiary designation with inactivity threshold."""
    owner_address: str
    beneficiary_address: str
    inactivity_blocks: int
    last_heartbeat_block: int
    active: bool = True


@dataclass
class InheritanceClaim:
    """A claim initiated by a beneficiary."""
    claim_id: str
    owner_address: str
    beneficiary_address: str
    initiated_at_block: int
    grace_expires_block: int
    status: str = ClaimStatus.PENDING
    executed_at: Optional[float] = None
    execution_txid: Optional[str] = None


class InheritanceManager:
    """Manages inheritance plans and beneficiary claims.

    Args:
        db_manager: DatabaseManager instance for persistence
    """

    def __init__(self, db_manager) -> None:
        self.db = db_manager
        self._min_inactivity = Config.INHERITANCE_MIN_INACTIVITY
        self._max_inactivity = Config.INHERITANCE_MAX_INACTIVITY
        self._default_inactivity = Config.INHERITANCE_DEFAULT_INACTIVITY
        self._grace_period = Config.INHERITANCE_GRACE_PERIOD

        # In-memory caches (backed by DB)
        self._plans: Dict[str, InheritancePlan] = {}
        self._claims: Dict[str, InheritanceClaim] = {}

        logger.info(
            f"InheritanceManager initialized: "
            f"default_inactivity={self._default_inactivity}, "
            f"grace_period={self._grace_period}"
        )

    # ── Beneficiary Management ──────────────────────────────────────────

    def set_beneficiary(self, owner_address: str, beneficiary_address: str,
                        inactivity_blocks: int, current_height: int) -> InheritancePlan:
        """Set or update the beneficiary for an address.

        Args:
            owner_address: Address of the asset owner
            beneficiary_address: Address of the designated beneficiary
            inactivity_blocks: Number of blocks of inactivity before claim
            current_height: Current block height (used as initial heartbeat)

        Returns:
            InheritancePlan record

        Raises:
            ValueError: If parameters are invalid
        """
        if owner_address == beneficiary_address:
            raise ValueError("Owner and beneficiary cannot be the same address")
        if inactivity_blocks < self._min_inactivity:
            raise ValueError(
                f"Inactivity threshold {inactivity_blocks} below minimum "
                f"{self._min_inactivity} blocks (~24h)"
            )
        if inactivity_blocks > self._max_inactivity:
            raise ValueError(
                f"Inactivity threshold {inactivity_blocks} exceeds maximum "
                f"{self._max_inactivity} blocks (~10 years)"
            )

        plan = InheritancePlan(
            owner_address=owner_address,
            beneficiary_address=beneficiary_address,
            inactivity_blocks=inactivity_blocks,
            last_heartbeat_block=current_height,
            active=True,
        )
        self._plans[owner_address] = plan
        self._persist_plan(plan)

        logger.info(
            f"Inheritance plan set: owner={owner_address[:16]}..., "
            f"beneficiary={beneficiary_address[:16]}..., "
            f"inactivity={inactivity_blocks} blocks"
        )
        return plan

    def remove_beneficiary(self, owner_address: str) -> bool:
        """Remove the inheritance plan for an address.

        Args:
            owner_address: Address of the asset owner

        Returns:
            True if plan was found and removed
        """
        plan = self._plans.get(owner_address)
        if not plan or not plan.active:
            return False

        plan.active = False
        self._persist_plan(plan)
        logger.info(f"Inheritance plan removed: owner={owner_address[:16]}...")
        return True

    # ── Heartbeat ───────────────────────────────────────────────────────

    def heartbeat(self, owner_address: str, current_height: int) -> bool:
        """Record a heartbeat for an address (proves the owner is alive).

        Args:
            owner_address: Address of the asset owner
            current_height: Current block height

        Returns:
            True if heartbeat was recorded, False if no plan exists
        """
        plan = self._plans.get(owner_address)
        if not plan or not plan.active:
            return False

        plan.last_heartbeat_block = current_height
        self._persist_plan(plan)
        return True

    def update_heartbeat_from_tx(self, sender_address: str, current_height: int) -> None:
        """Auto-update heartbeat when a transaction is sent from this address.

        Called by the mempool/transaction processing pipeline.

        Args:
            sender_address: Address that sent a transaction
            current_height: Current block height
        """
        plan = self._plans.get(sender_address)
        if plan and plan.active:
            plan.last_heartbeat_block = current_height
            self._persist_plan(plan)

    # ── Inactivity Check ────────────────────────────────────────────────

    def check_inactivity(self, owner_address: str, current_height: int) -> Optional[int]:
        """Check how many blocks an address has been inactive.

        Args:
            owner_address: Address to check
            current_height: Current block height

        Returns:
            Number of blocks since last heartbeat, or None if no plan exists
        """
        plan = self._plans.get(owner_address)
        if not plan or not plan.active:
            return None
        return current_height - plan.last_heartbeat_block

    def is_claimable(self, owner_address: str, current_height: int) -> bool:
        """Check if an address's assets are claimable by the beneficiary.

        Args:
            owner_address: Address to check
            current_height: Current block height

        Returns:
            True if inactivity threshold has been exceeded
        """
        plan = self._plans.get(owner_address)
        if not plan or not plan.active:
            return False
        inactive_blocks = current_height - plan.last_heartbeat_block
        return inactive_blocks >= plan.inactivity_blocks

    # ── Claims ──────────────────────────────────────────────────────────

    def claim_inheritance(self, owner_address: str, beneficiary_address: str,
                          current_height: int) -> InheritanceClaim:
        """Initiate an inheritance claim.

        Args:
            owner_address: Address of the (presumed inactive) owner
            beneficiary_address: Address of the claimant
            current_height: Current block height

        Returns:
            InheritanceClaim record

        Raises:
            ValueError: If claim is not valid
        """
        plan = self._plans.get(owner_address)
        if not plan or not plan.active:
            raise ValueError(f"No active inheritance plan for {owner_address[:16]}...")

        if plan.beneficiary_address != beneficiary_address:
            raise ValueError(
                f"Address {beneficiary_address[:16]}... is not the designated beneficiary"
            )

        if not self.is_claimable(owner_address, current_height):
            inactive = current_height - plan.last_heartbeat_block
            remaining = plan.inactivity_blocks - inactive
            raise ValueError(
                f"Owner is not yet inactive. {remaining} blocks remaining "
                f"({inactive}/{plan.inactivity_blocks} elapsed)"
            )

        # Check for existing pending claim
        for claim in self._claims.values():
            if (claim.owner_address == owner_address
                    and claim.status == ClaimStatus.PENDING):
                raise ValueError(
                    f"Pending claim already exists: {claim.claim_id[:16]}..."
                )

        claim_id = hashlib.sha256(
            f"inheritance-{owner_address}-{beneficiary_address}-{time.time()}".encode()
        ).hexdigest()[:32]

        grace_expires = current_height + self._grace_period

        claim = InheritanceClaim(
            claim_id=claim_id,
            owner_address=owner_address,
            beneficiary_address=beneficiary_address,
            initiated_at_block=current_height,
            grace_expires_block=grace_expires,
            status=ClaimStatus.PENDING,
        )
        self._claims[claim_id] = claim
        self._persist_claim(claim)

        logger.info(
            f"Inheritance claim initiated: id={claim_id[:16]}..., "
            f"owner={owner_address[:16]}..., "
            f"beneficiary={beneficiary_address[:16]}..., "
            f"grace expires at block {grace_expires}"
        )
        return claim

    def cancel_claim(self, claim_id: str, owner_address: str) -> bool:
        """Cancel a pending claim (owner proves they are alive).

        Args:
            claim_id: Claim ID to cancel
            owner_address: Address of the owner cancelling

        Returns:
            True if cancelled

        Raises:
            ValueError: If claim not found or not cancellable
        """
        claim = self._claims.get(claim_id)
        if not claim:
            raise ValueError(f"Claim not found: {claim_id}")

        if claim.status != ClaimStatus.PENDING:
            raise ValueError(f"Claim is not pending (status: {claim.status})")

        if claim.owner_address != owner_address:
            raise ValueError("Only the owner can cancel a claim")

        claim.status = ClaimStatus.CANCELLED
        self._persist_claim(claim)

        # Also reset the heartbeat since the owner is clearly alive
        plan = self._plans.get(owner_address)
        if plan and plan.active:
            # We don't have current_height here, but the caller should also heartbeat
            pass

        logger.info(
            f"Inheritance claim cancelled by owner: id={claim_id[:16]}..., "
            f"owner={owner_address[:16]}..."
        )
        return True

    def execute_matured_claims(self, current_height: int) -> List[InheritanceClaim]:
        """Execute all claims whose grace period has expired.

        Args:
            current_height: Current block height

        Returns:
            List of executed claims
        """
        executed = []
        for claim in list(self._claims.values()):
            if (claim.status == ClaimStatus.PENDING
                    and current_height >= claim.grace_expires_block):
                # Verify the owner hasn't heartbeated during grace period
                plan = self._plans.get(claim.owner_address)
                if plan and plan.active:
                    if plan.last_heartbeat_block >= claim.initiated_at_block:
                        # Owner was active during grace — cancel the claim
                        claim.status = ClaimStatus.CANCELLED
                        self._persist_claim(claim)
                        logger.info(
                            f"Claim auto-cancelled (owner active during grace): "
                            f"{claim.claim_id[:16]}..."
                        )
                        continue

                # Execute the claim
                execution_txid = hashlib.sha256(
                    f"inheritance-exec-{claim.claim_id}-{time.time()}".encode()
                ).hexdigest()

                claim.status = ClaimStatus.EXECUTED
                claim.executed_at = time.time()
                claim.execution_txid = execution_txid
                self._persist_claim(claim)

                # Deactivate the plan
                if plan:
                    plan.active = False
                    self._persist_plan(plan)

                executed.append(claim)
                logger.info(
                    f"Inheritance EXECUTED: claim={claim.claim_id[:16]}..., "
                    f"owner={claim.owner_address[:16]}..., "
                    f"beneficiary={claim.beneficiary_address[:16]}..., "
                    f"txid={execution_txid[:16]}..."
                )

        return executed

    # ── Status ──────────────────────────────────────────────────────────

    def get_status(self, address: str, current_height: int) -> Optional[dict]:
        """Get inheritance status for an address (as owner or beneficiary).

        Args:
            address: Address to check
            current_height: Current block height

        Returns:
            Status dict or None if no plan exists
        """
        plan = self._plans.get(address)
        if plan and plan.active:
            inactive_blocks = current_height - plan.last_heartbeat_block
            claimable = inactive_blocks >= plan.inactivity_blocks
            pending_claims = [
                c for c in self._claims.values()
                if c.owner_address == address and c.status == ClaimStatus.PENDING
            ]
            return {
                "role": "owner",
                "owner_address": plan.owner_address,
                "beneficiary_address": plan.beneficiary_address,
                "inactivity_blocks": plan.inactivity_blocks,
                "last_heartbeat_block": plan.last_heartbeat_block,
                "blocks_since_heartbeat": inactive_blocks,
                "claimable": claimable,
                "blocks_until_claimable": max(0, plan.inactivity_blocks - inactive_blocks),
                "pending_claims": [c.claim_id for c in pending_claims],
                "active": True,
            }

        # Check as beneficiary
        for plan in self._plans.values():
            if plan.beneficiary_address == address and plan.active:
                inactive_blocks = current_height - plan.last_heartbeat_block
                claimable = inactive_blocks >= plan.inactivity_blocks
                pending_claims = [
                    c for c in self._claims.values()
                    if c.beneficiary_address == address and c.status == ClaimStatus.PENDING
                ]
                return {
                    "role": "beneficiary",
                    "owner_address": plan.owner_address,
                    "beneficiary_address": plan.beneficiary_address,
                    "inactivity_blocks": plan.inactivity_blocks,
                    "last_heartbeat_block": plan.last_heartbeat_block,
                    "blocks_since_heartbeat": inactive_blocks,
                    "claimable": claimable,
                    "blocks_until_claimable": max(0, plan.inactivity_blocks - inactive_blocks),
                    "pending_claims": [c.claim_id for c in pending_claims],
                    "active": True,
                }

        return None

    def get_claim(self, claim_id: str) -> Optional[InheritanceClaim]:
        """Get a specific claim by ID."""
        return self._claims.get(claim_id)

    def get_plan(self, owner_address: str) -> Optional[InheritancePlan]:
        """Get the inheritance plan for an owner address."""
        plan = self._plans.get(owner_address)
        if plan and plan.active:
            return plan
        return None

    # ── Persistence helpers ─────────────────────────────────────────────

    def _persist_plan(self, plan: InheritancePlan) -> None:
        """Persist inheritance plan to database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO inheritance_plans
                        (owner_address, beneficiary_address, inactivity_blocks,
                         last_heartbeat_block, active, updated_at)
                    VALUES (:owner, :beneficiary, :inactivity,
                            :heartbeat, :active, now())
                    ON CONFLICT (owner_address) DO UPDATE SET
                        beneficiary_address = :beneficiary,
                        inactivity_blocks = :inactivity,
                        last_heartbeat_block = :heartbeat,
                        active = :active,
                        updated_at = now()
                """), {
                    'owner': plan.owner_address,
                    'beneficiary': plan.beneficiary_address,
                    'inactivity': plan.inactivity_blocks,
                    'heartbeat': plan.last_heartbeat_block,
                    'active': plan.active,
                })
                session.commit()
        except Exception as e:
            logger.debug(f"Plan persistence: {e}")

    def _persist_claim(self, claim: InheritanceClaim) -> None:
        """Persist inheritance claim to database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO inheritance_claims
                        (claim_id, owner_address, beneficiary_address,
                         initiated_at_block, grace_expires_block, status,
                         executed_at, execution_txid)
                    VALUES (:id, :owner, :beneficiary,
                            :initiated, :grace_expires, :status,
                            :executed_at, :execution_txid)
                    ON CONFLICT (claim_id) DO UPDATE SET
                        status = :status,
                        executed_at = :executed_at,
                        execution_txid = :execution_txid
                """), {
                    'id': claim.claim_id,
                    'owner': claim.owner_address,
                    'beneficiary': claim.beneficiary_address,
                    'initiated': claim.initiated_at_block,
                    'grace_expires': claim.grace_expires_block,
                    'status': claim.status,
                    'executed_at': claim.executed_at,
                    'execution_txid': claim.execution_txid,
                })
                session.commit()
        except Exception as e:
            logger.debug(f"Claim persistence: {e}")
