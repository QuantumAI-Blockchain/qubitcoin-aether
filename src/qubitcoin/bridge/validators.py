"""
Federated Validator Set & Economic Bonding for Bridge Security

Implements:
  - FederatedValidatorSet: 7-of-11 multi-sig validator management
  - ValidatorBond: Economic bonding with slashable stake (10,000+ QBC)
  - Signature aggregation and quorum verification

Security model:
  - Validators must bond >= MIN_BOND_QBC (10,000 QBC) to participate
  - 7-of-11 threshold for bridge operations (configurable)
  - Slash conditions: double-signing, invalid proofs, prolonged offline
  - Unbonding delay: 7 days (181,818 blocks at 3.3s/block)
  - Path to 101+ validators via progressive decentralisation
"""

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from typing import Dict, List, Optional, Set

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────
MIN_BOND_QBC: Decimal = Decimal('10000')
DEFAULT_QUORUM_THRESHOLD: int = 7
DEFAULT_VALIDATOR_SET_SIZE: int = 11
UNBONDING_DELAY_BLOCKS: int = 181_818  # ~7 days at 3.3s/block
SLASH_DOUBLE_SIGN_PCT: Decimal = Decimal('0.50')    # 50% slash for double signing
SLASH_INVALID_PROOF_PCT: Decimal = Decimal('0.25')  # 25% slash for invalid proofs
SLASH_OFFLINE_PCT: Decimal = Decimal('0.05')         # 5% slash for prolonged offline
MAX_MISSED_ATTESTATIONS: int = 100     # before offline slash


class ValidatorStatus(Enum):
    """Validator lifecycle state."""
    ACTIVE = "active"
    UNBONDING = "unbonding"
    SLASHED = "slashed"
    REMOVED = "removed"


class SlashReason(Enum):
    """Reason for slashing a validator."""
    DOUBLE_SIGN = "double_sign"
    INVALID_PROOF = "invalid_proof"
    OFFLINE = "offline"


@dataclass
class ValidatorBond:
    """Economic bond for a bridge validator."""
    address: str
    bond_amount: Decimal
    bonded_at: float = field(default_factory=time.time)
    status: ValidatorStatus = ValidatorStatus.ACTIVE
    unbonding_started_at: Optional[float] = None
    unbonding_complete_block: Optional[int] = None
    slash_history: List[Dict] = field(default_factory=list)
    total_slashed: Decimal = field(default_factory=lambda: Decimal('0'))
    attestations: int = 0
    missed_attestations: int = 0

    @property
    def effective_bond(self) -> Decimal:
        """Bond minus accumulated slashing."""
        return max(Decimal('0'), self.bond_amount - self.total_slashed)

    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "bond_amount": self.bond_amount,
            "effective_bond": self.effective_bond,
            "status": self.status.value,
            "bonded_at": self.bonded_at,
            "unbonding_started_at": self.unbonding_started_at,
            "unbonding_complete_block": self.unbonding_complete_block,
            "slash_history": self.slash_history,
            "total_slashed": self.total_slashed,
            "attestations": self.attestations,
            "missed_attestations": self.missed_attestations,
        }


@dataclass
class BridgeAttestation:
    """A validator's attestation (signature) on a bridge event."""
    validator_address: str
    event_hash: str
    signature: str
    timestamp: float = field(default_factory=time.time)


class FederatedValidatorSet:
    """
    Federated validator set for bridge security.

    Manages validator registration, bonding, quorum verification,
    slashing, and unbonding lifecycle.
    """

    def __init__(
        self,
        quorum_threshold: int = DEFAULT_QUORUM_THRESHOLD,
        max_validators: int = DEFAULT_VALIDATOR_SET_SIZE,
    ) -> None:
        self._validators: Dict[str, ValidatorBond] = {}
        self._attestations: Dict[str, List[BridgeAttestation]] = {}
        self._quorum_threshold = quorum_threshold
        self._max_validators = max_validators
        self._total_slashed_qbc: Decimal = Decimal('0')
        self._quorum_reached_count: int = 0
        logger.info(
            f"FederatedValidatorSet initialised: "
            f"{quorum_threshold}-of-{max_validators} threshold"
        )

    # ── Registration & Bonding ─────────────────────────────────────────

    def register_validator(self, address: str, bond_amount: float | Decimal) -> Dict:
        """
        Register a new validator with economic bond.

        Args:
            address: Validator's QBC address.
            bond_amount: Amount of QBC to bond (must be >= MIN_BOND_QBC).

        Returns:
            Result dict with status.
        """
        bond_amount = Decimal(str(bond_amount))
        if address in self._validators:
            existing = self._validators[address]
            if existing.status == ValidatorStatus.ACTIVE:
                return {"success": False, "error": "Validator already registered"}
            if existing.status == ValidatorStatus.REMOVED:
                # Allow re-registration after removal
                pass
            else:
                return {"success": False, "error": f"Validator in {existing.status.value} state"}

        if bond_amount < MIN_BOND_QBC:
            return {
                "success": False,
                "error": f"Bond below minimum: {bond_amount} < {MIN_BOND_QBC} QBC",
            }

        active_count = sum(
            1 for v in self._validators.values()
            if v.status == ValidatorStatus.ACTIVE
        )
        if active_count >= self._max_validators:
            return {
                "success": False,
                "error": f"Validator set full ({self._max_validators})",
            }

        self._validators[address] = ValidatorBond(
            address=address,
            bond_amount=bond_amount,
        )
        logger.info(f"Validator registered: {address[:16]}… ({bond_amount} QBC)")
        return {"success": True, "address": address, "bond": bond_amount}

    def increase_bond(self, address: str, additional: float | Decimal) -> Dict:
        """Add more QBC to an existing validator's bond."""
        v = self._validators.get(address)
        if v is None or v.status != ValidatorStatus.ACTIVE:
            return {"success": False, "error": "Validator not active"}
        additional = Decimal(str(additional))
        if additional <= 0:
            return {"success": False, "error": "Amount must be positive"}
        v.bond_amount += additional
        logger.info(f"Bond increased for {address[:16]}… by {additional} QBC")
        return {"success": True, "new_bond": v.bond_amount}

    # ── Unbonding ──────────────────────────────────────────────────────

    def request_unbond(self, address: str, current_block: int) -> Dict:
        """
        Start unbonding process. Funds locked for UNBONDING_DELAY_BLOCKS.

        Args:
            address: Validator address.
            current_block: Current block height.

        Returns:
            Result with unbonding completion block.
        """
        v = self._validators.get(address)
        if v is None or v.status != ValidatorStatus.ACTIVE:
            return {"success": False, "error": "Validator not active"}

        v.status = ValidatorStatus.UNBONDING
        v.unbonding_started_at = time.time()
        v.unbonding_complete_block = current_block + UNBONDING_DELAY_BLOCKS
        logger.info(
            f"Unbonding started: {address[:16]}… "
            f"(completes at block {v.unbonding_complete_block})"
        )
        return {
            "success": True,
            "complete_block": v.unbonding_complete_block,
            "effective_bond": v.effective_bond,
        }

    def finalize_unbond(self, address: str, current_block: int) -> Dict:
        """
        Finalize unbonding and return funds.

        Args:
            address: Validator address.
            current_block: Current block height.

        Returns:
            Result with returned amount.
        """
        v = self._validators.get(address)
        if v is None or v.status != ValidatorStatus.UNBONDING:
            return {"success": False, "error": "Not unbonding"}
        if v.unbonding_complete_block is not None and current_block < v.unbonding_complete_block:
            return {
                "success": False,
                "error": f"Unbonding not complete (need block {v.unbonding_complete_block})",
            }

        returned = v.effective_bond
        v.status = ValidatorStatus.REMOVED
        logger.info(f"Unbond finalised: {address[:16]}… returned {returned} QBC")
        return {"success": True, "returned": returned}

    # ── Slashing ───────────────────────────────────────────────────────

    def slash_validator(
        self,
        address: str,
        reason: SlashReason,
        evidence: str = "",
    ) -> Dict:
        """
        Slash a validator for misbehaviour.

        Args:
            address: Validator to slash.
            reason: Why they're being slashed.
            evidence: Optional evidence hash/description.

        Returns:
            Result with slashed amount.
        """
        v = self._validators.get(address)
        if v is None or v.status not in (ValidatorStatus.ACTIVE, ValidatorStatus.UNBONDING):
            return {"success": False, "error": "Validator not slashable"}

        pct_map = {
            SlashReason.DOUBLE_SIGN: SLASH_DOUBLE_SIGN_PCT,
            SlashReason.INVALID_PROOF: SLASH_INVALID_PROOF_PCT,
            SlashReason.OFFLINE: SLASH_OFFLINE_PCT,
        }
        pct = pct_map[reason]
        slash_amount = v.bond_amount * pct

        v.total_slashed += slash_amount
        v.slash_history.append({
            "reason": reason.value,
            "amount": slash_amount,
            "evidence": evidence,
            "timestamp": time.time(),
        })
        self._total_slashed_qbc += slash_amount

        # If bond drops below minimum, force-remove
        if v.effective_bond < MIN_BOND_QBC:
            v.status = ValidatorStatus.SLASHED
            logger.warning(
                f"Validator slashed & removed: {address[:16]}… "
                f"({reason.value}, {slash_amount} QBC)"
            )
        else:
            logger.warning(
                f"Validator slashed: {address[:16]}… "
                f"({reason.value}, {slash_amount} QBC, remains active)"
            )

        return {
            "success": True,
            "slashed_amount": slash_amount,
            "remaining_bond": v.effective_bond,
            "status": v.status.value,
        }

    # ── Attestations & Quorum ──────────────────────────────────────────

    def submit_attestation(
        self,
        validator_address: str,
        event_hash: str,
        signature: str,
    ) -> Dict:
        """
        Submit a validator attestation for a bridge event.

        Args:
            validator_address: Attesting validator.
            event_hash: Hash of the bridge event being attested.
            signature: Validator's signature over the event.

        Returns:
            Result dict, including whether quorum is reached.
        """
        v = self._validators.get(validator_address)
        if v is None or v.status != ValidatorStatus.ACTIVE:
            return {"success": False, "error": "Validator not active"}

        if event_hash not in self._attestations:
            self._attestations[event_hash] = []

        # Prevent duplicate attestation
        existing = {a.validator_address for a in self._attestations[event_hash]}
        if validator_address in existing:
            return {"success": False, "error": "Already attested"}

        self._attestations[event_hash].append(
            BridgeAttestation(
                validator_address=validator_address,
                event_hash=event_hash,
                signature=signature,
            )
        )
        v.attestations += 1

        count = len(self._attestations[event_hash])
        quorum = count >= self._quorum_threshold

        if quorum:
            self._quorum_reached_count += 1

        logger.info(
            f"Attestation: {validator_address[:16]}… on {event_hash[:16]}… "
            f"({count}/{self._quorum_threshold})"
        )
        return {
            "success": True,
            "attestation_count": count,
            "quorum_reached": quorum,
            "threshold": self._quorum_threshold,
        }

    def check_quorum(self, event_hash: str) -> Dict:
        """
        Check if quorum has been reached for an event.

        Returns:
            Dict with quorum status and attestation details.
        """
        attestations = self._attestations.get(event_hash, [])
        count = len(attestations)
        quorum = count >= self._quorum_threshold
        return {
            "event_hash": event_hash,
            "attestation_count": count,
            "threshold": self._quorum_threshold,
            "quorum_reached": quorum,
            "validators": [a.validator_address for a in attestations],
        }

    def record_missed_attestation(self, address: str) -> Dict:
        """
        Record that a validator missed an attestation round.

        Auto-slashes if too many missed.
        """
        v = self._validators.get(address)
        if v is None or v.status != ValidatorStatus.ACTIVE:
            return {"success": False, "error": "Validator not active"}

        v.missed_attestations += 1

        if v.missed_attestations >= MAX_MISSED_ATTESTATIONS:
            result = self.slash_validator(
                address, SlashReason.OFFLINE,
                evidence=f"Missed {v.missed_attestations} attestations",
            )
            return {
                "success": True,
                "missed": v.missed_attestations,
                "auto_slashed": True,
                "slash_result": result,
            }

        return {
            "success": True,
            "missed": v.missed_attestations,
            "auto_slashed": False,
        }

    # ── Queries ────────────────────────────────────────────────────────

    def get_validator(self, address: str) -> Optional[Dict]:
        """Get validator info."""
        v = self._validators.get(address)
        return v.to_dict() if v else None

    def get_active_validators(self) -> List[Dict]:
        """Get all active validators."""
        return [
            v.to_dict()
            for v in self._validators.values()
            if v.status == ValidatorStatus.ACTIVE
        ]

    def get_all_validators(self) -> List[Dict]:
        """Get all validators regardless of status."""
        return [v.to_dict() for v in self._validators.values()]

    def get_stats(self) -> Dict:
        """Get validator set statistics."""
        active = sum(1 for v in self._validators.values() if v.status == ValidatorStatus.ACTIVE)
        unbonding = sum(1 for v in self._validators.values() if v.status == ValidatorStatus.UNBONDING)
        total_bonded = sum(
            v.effective_bond for v in self._validators.values()
            if v.status == ValidatorStatus.ACTIVE
        )
        return {
            "total_validators": len(self._validators),
            "active_validators": active,
            "unbonding_validators": unbonding,
            "max_validators": self._max_validators,
            "quorum_threshold": self._quorum_threshold,
            "total_bonded_qbc": total_bonded,
            "total_slashed_qbc": self._total_slashed_qbc,
            "total_attestation_events": len(self._attestations),
            "quorum_reached_count": self._quorum_reached_count,
        }
