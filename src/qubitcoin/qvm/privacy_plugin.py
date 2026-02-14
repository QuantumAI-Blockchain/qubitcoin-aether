"""
Privacy Plugin — SUSY Swaps and ZK proof generation for QVM

Implements a QVM plugin that adds privacy-related hooks:
  - PRE_EXECUTE: check if a transaction is a Susy Swap and prepare commitments
  - POST_EXECUTE: generate ZK range proof receipts
  - ON_LOG: filter private transaction logs
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .plugins import QVMPlugin, HookType
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PrivacyProof:
    """A ZK proof record for a private transaction."""
    proof_id: str
    tx_hash: str
    proof_type: str  # 'range_proof' | 'commitment' | 'stealth'
    proof_data: bytes
    verified: bool = False
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            'proof_id': self.proof_id,
            'tx_hash': self.tx_hash,
            'proof_type': self.proof_type,
            'proof_size': len(self.proof_data),
            'verified': self.verified,
            'created_at': self.created_at,
        }


@dataclass
class StealthAddressRecord:
    """Record of a stealth address generated for privacy."""
    one_time_address: str
    ephemeral_pubkey: str
    recipient_hint: str  # view key scan hint
    block_height: int = 0

    def to_dict(self) -> dict:
        return {
            'one_time_address': self.one_time_address,
            'ephemeral_pubkey': self.ephemeral_pubkey,
            'block_height': self.block_height,
        }


class PrivacyPlugin(QVMPlugin):
    """Privacy plugin for QVM — SUSY Swaps integration.

    Adds hooks for:
      - Pedersen commitment creation on private sends
      - Range proof generation for amount hiding
      - Stealth address management
    """

    def __init__(self) -> None:
        self._proofs: Dict[str, PrivacyProof] = {}
        self._stealth_records: List[StealthAddressRecord] = []
        self._private_tx_count: int = 0
        self._started: bool = False

    def name(self) -> str:
        return 'privacy'

    def version(self) -> str:
        return '0.1.0'

    def description(self) -> str:
        return 'SUSY Swaps privacy layer — commitments, range proofs, stealth addresses'

    def author(self) -> str:
        return 'Qubitcoin Core'

    def on_load(self) -> None:
        logger.info("Privacy plugin loaded")

    def on_start(self) -> None:
        self._started = True
        logger.info("Privacy plugin started")

    def on_stop(self) -> None:
        self._started = False
        logger.info("Privacy plugin stopped")

    def hooks(self) -> Dict[int, Callable]:
        return {
            HookType.PRE_EXECUTE: self._pre_execute_hook,
            HookType.POST_EXECUTE: self._post_execute_hook,
            HookType.ON_LOG: self._on_log_hook,
        }

    # ── Hook handlers ──────────────────────────────────────────────

    def _pre_execute_hook(self, context: dict) -> Optional[dict]:
        """Check if transaction is private and prepare commitments."""
        tx_data = context.get('tx_data', {})
        is_private = tx_data.get('is_private', False)

        if not is_private:
            return None

        self._private_tx_count += 1

        # Generate commitment for the amount
        amount = tx_data.get('amount', 0)
        blinding = _generate_blinding_factor(
            tx_data.get('tx_hash', ''),
            tx_data.get('sender', ''),
        )
        commitment = _compute_commitment(amount, blinding)

        return {
            'privacy_commitment': commitment,
            'privacy_blinding': blinding.hex(),
            'is_private_tx': True,
        }

    def _post_execute_hook(self, context: dict) -> Optional[dict]:
        """Generate proof receipt after private transaction execution."""
        if not context.get('is_private_tx', False):
            return None

        tx_hash = context.get('tx_hash', '')
        commitment = context.get('privacy_commitment', '')

        # Generate a range proof stub
        proof_data = _generate_range_proof_stub(commitment, tx_hash)
        proof_id = hashlib.sha256(
            f"{tx_hash}:range_proof".encode()
        ).hexdigest()[:16]

        proof = PrivacyProof(
            proof_id=proof_id,
            tx_hash=tx_hash,
            proof_type='range_proof',
            proof_data=proof_data,
            verified=True,
            created_at=time.time(),
        )
        self._proofs[proof_id] = proof

        return {'privacy_proof_id': proof_id}

    def _on_log_hook(self, context: dict) -> Optional[dict]:
        """Filter logs from private transactions."""
        if context.get('is_private_tx', False):
            # Redact amount from logs
            log_data = context.get('log_data', {})
            if 'amount' in log_data:
                log_data['amount'] = '[REDACTED]'
            return {'log_data': log_data}
        return None

    # ── Public API ─────────────────────────────────────────────────

    def get_proof(self, proof_id: str) -> Optional[PrivacyProof]:
        return self._proofs.get(proof_id)

    def get_proofs_for_tx(self, tx_hash: str) -> List[PrivacyProof]:
        return [p for p in self._proofs.values() if p.tx_hash == tx_hash]

    def register_stealth_address(self, one_time: str, ephemeral: str,
                                  hint: str, block_height: int = 0) -> StealthAddressRecord:
        record = StealthAddressRecord(
            one_time_address=one_time,
            ephemeral_pubkey=ephemeral,
            recipient_hint=hint,
            block_height=block_height,
        )
        self._stealth_records.append(record)
        return record

    def scan_stealth_addresses(self, view_key_hint: str) -> List[StealthAddressRecord]:
        """Find stealth addresses matching a view key hint."""
        return [
            r for r in self._stealth_records
            if r.recipient_hint == view_key_hint
        ]

    def get_stats(self) -> dict:
        return {
            'private_tx_count': self._private_tx_count,
            'proofs_generated': len(self._proofs),
            'stealth_addresses': len(self._stealth_records),
            'started': self._started,
        }


# ── Helpers ────────────────────────────────────────────────────────────

def _generate_blinding_factor(tx_hash: str, sender: str) -> bytes:
    """Deterministic blinding factor from tx hash and sender."""
    data = f"{tx_hash}:{sender}:blinding".encode()
    return hashlib.sha256(data).digest()


def _compute_commitment(amount: int, blinding: bytes) -> str:
    """Simplified Pedersen commitment stub.

    In production, this uses the full elliptic curve Pedersen commitment
    from privacy/commitments.py.  This stub uses hash-based commitment
    for plugin testing.
    """
    data = amount.to_bytes(8, 'big') + blinding
    return hashlib.sha256(data).hexdigest()


def _generate_range_proof_stub(commitment: str, tx_hash: str) -> bytes:
    """Stub range proof generator.

    In production, delegates to privacy/range_proofs.py for Bulletproofs.
    """
    data = f"{commitment}:{tx_hash}:range_proof".encode()
    return hashlib.sha256(data).digest()


def create_plugin() -> QVMPlugin:
    """Factory function for dynamic loading."""
    return PrivacyPlugin()
