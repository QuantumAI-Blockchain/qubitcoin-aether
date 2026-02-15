"""
Compliance Proof Storage

Stores and retrieves cryptographic compliance proofs for auditors.
Proofs are generated when the QCOMPLIANCE opcode processes a transaction
and serve as tamper-proof evidence that compliance checks were performed.

Proof types:
  - KYC verification proof (address passed KYC at a given level)
  - AML screening proof (transaction screened for money laundering)
  - Sanctions check proof (address not on any sanctions list)
  - Limit enforcement proof (transaction within daily limits)

Each proof includes a hash chain linking it to the block where the
check was performed, enabling end-to-end audit trails.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ProofType(str, Enum):
    """Types of compliance proofs."""
    KYC_VERIFICATION = 'kyc_verification'
    AML_SCREENING = 'aml_screening'
    SANCTIONS_CHECK = 'sanctions_check'
    LIMIT_ENFORCEMENT = 'limit_enforcement'
    COMPOSITE = 'composite'  # Combined proof covering multiple checks


@dataclass
class ComplianceProof:
    """A single compliance proof for audit purposes.

    Each proof is self-verifiable: the proof_hash is derived from
    the content, creating a tamper-evident record.
    """
    proof_id: str
    proof_type: str
    address: str
    block_height: int
    tx_hash: str = ''
    timestamp: float = 0.0
    proof_data: dict = field(default_factory=dict)
    proof_hash: str = ''
    previous_proof_hash: str = ''  # Chain link to prior proof for this address
    jurisdiction: str = ''
    expiry: float = 0.0  # Unix timestamp when proof expires (0 = never)
    verified_by: str = ''  # Validator/auditor who verified

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.proof_hash:
            self.proof_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Compute a deterministic hash of the proof content."""
        data = {
            'proof_id': self.proof_id,
            'proof_type': self.proof_type,
            'address': self.address,
            'block_height': self.block_height,
            'tx_hash': self.tx_hash,
            'proof_data': self.proof_data,
            'previous_proof_hash': self.previous_proof_hash,
            'jurisdiction': self.jurisdiction,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify the proof has not been tampered with."""
        return self.proof_hash == self.compute_hash()

    def is_expired(self) -> bool:
        """Check if the proof has expired."""
        if self.expiry <= 0:
            return False
        return time.time() > self.expiry

    def to_dict(self) -> dict:
        return {
            'proof_id': self.proof_id,
            'proof_type': self.proof_type,
            'address': self.address,
            'block_height': self.block_height,
            'tx_hash': self.tx_hash,
            'timestamp': self.timestamp,
            'proof_data': self.proof_data,
            'proof_hash': self.proof_hash,
            'previous_proof_hash': self.previous_proof_hash,
            'jurisdiction': self.jurisdiction,
            'expiry': self.expiry,
            'verified_by': self.verified_by,
            'is_valid': self.verify_integrity(),
            'is_expired': self.is_expired(),
        }


class ComplianceProofStore:
    """Store and retrieve compliance proofs.

    Provides:
      - Per-address proof chains (linked list via previous_proof_hash)
      - Lookup by proof ID, address, block height, or type
      - Proof integrity verification
      - Audit trail generation
    """

    def __init__(self, max_proofs: int = 50000) -> None:
        self._proofs: Dict[str, ComplianceProof] = {}
        # address -> latest proof_id (for chaining)
        self._address_latest: Dict[str, str] = {}
        # address -> list of proof_ids (chronological)
        self._address_history: Dict[str, List[str]] = {}
        self._max_proofs = max_proofs
        self._proof_counter: int = 0

    def store_proof(self, proof_type: str, address: str,
                    block_height: int, tx_hash: str = '',
                    proof_data: Optional[dict] = None,
                    jurisdiction: str = '',
                    expiry: float = 0.0,
                    verified_by: str = '') -> ComplianceProof:
        """Create and store a new compliance proof.

        Automatically chains to the previous proof for this address.

        Args:
            proof_type: Type of compliance check performed.
            address: The address that was checked.
            block_height: Block where the check occurred.
            tx_hash: Transaction that triggered the check.
            proof_data: Additional proof payload (check results, scores).
            jurisdiction: Jurisdiction for the compliance check.
            expiry: Unix timestamp when proof expires.
            verified_by: Address of the verifier.

        Returns:
            The stored ComplianceProof.
        """
        self._proof_counter += 1
        proof_id = f"cp_{block_height}_{self._proof_counter}"

        # Get previous proof hash for chain linkage
        prev_hash = ''
        prev_id = self._address_latest.get(address.lower())
        if prev_id and prev_id in self._proofs:
            prev_hash = self._proofs[prev_id].proof_hash

        proof = ComplianceProof(
            proof_id=proof_id,
            proof_type=proof_type,
            address=address.lower(),
            block_height=block_height,
            tx_hash=tx_hash,
            proof_data=proof_data or {},
            previous_proof_hash=prev_hash,
            jurisdiction=jurisdiction,
            expiry=expiry,
            verified_by=verified_by,
        )

        self._proofs[proof_id] = proof
        self._address_latest[address.lower()] = proof_id

        if address.lower() not in self._address_history:
            self._address_history[address.lower()] = []
        self._address_history[address.lower()].append(proof_id)

        # Evict oldest if over capacity
        if len(self._proofs) > self._max_proofs:
            oldest_id = next(iter(self._proofs))
            del self._proofs[oldest_id]

        logger.debug(
            f"Compliance proof stored: {proof_id} ({proof_type}) "
            f"for {address[:10]}... at block {block_height}"
        )
        return proof

    def get_proof(self, proof_id: str) -> Optional[dict]:
        """Get a proof by ID."""
        proof = self._proofs.get(proof_id)
        return proof.to_dict() if proof else None

    def get_address_proofs(self, address: str,
                           proof_type: Optional[str] = None,
                           limit: int = 100) -> List[dict]:
        """Get all proofs for an address, optionally filtered by type.

        Returns proofs in reverse chronological order (newest first).
        """
        addr = address.lower()
        proof_ids = self._address_history.get(addr, [])
        results = []

        for pid in reversed(proof_ids):
            if len(results) >= limit:
                break
            proof = self._proofs.get(pid)
            if not proof:
                continue
            if proof_type and proof.proof_type != proof_type:
                continue
            results.append(proof.to_dict())

        return results

    def get_block_proofs(self, block_height: int) -> List[dict]:
        """Get all proofs generated at a specific block height."""
        return [
            p.to_dict() for p in self._proofs.values()
            if p.block_height == block_height
        ]

    def verify_proof_chain(self, address: str) -> dict:
        """Verify the integrity of an address's entire proof chain.

        Checks that each proof's hash matches its content and that
        the chain links (previous_proof_hash) are consistent.

        Returns:
            Dict with verification results.
        """
        addr = address.lower()
        proof_ids = self._address_history.get(addr, [])
        results = {
            'address': addr,
            'total_proofs': len(proof_ids),
            'valid_proofs': 0,
            'invalid_proofs': 0,
            'chain_intact': True,
            'details': [],
        }

        prev_hash = ''
        for pid in proof_ids:
            proof = self._proofs.get(pid)
            if not proof:
                results['chain_intact'] = False
                results['details'].append({
                    'proof_id': pid, 'status': 'missing',
                })
                continue

            is_valid = proof.verify_integrity()
            chain_ok = proof.previous_proof_hash == prev_hash

            if is_valid and chain_ok:
                results['valid_proofs'] += 1
            else:
                results['invalid_proofs'] += 1
                if not chain_ok:
                    results['chain_intact'] = False

            results['details'].append({
                'proof_id': pid,
                'status': 'valid' if (is_valid and chain_ok) else 'invalid',
                'integrity': is_valid,
                'chain_link': chain_ok,
            })

            prev_hash = proof.proof_hash

        return results

    def get_latest_proof(self, address: str,
                         proof_type: Optional[str] = None) -> Optional[dict]:
        """Get the most recent proof for an address."""
        proofs = self.get_address_proofs(address, proof_type, limit=1)
        return proofs[0] if proofs else None

    def get_stats(self) -> dict:
        """Get proof store statistics."""
        type_counts: Dict[str, int] = {}
        for p in self._proofs.values():
            type_counts[p.proof_type] = type_counts.get(p.proof_type, 0) + 1

        return {
            'total_proofs': len(self._proofs),
            'unique_addresses': len(self._address_history),
            'proof_types': type_counts,
            'max_capacity': self._max_proofs,
        }
