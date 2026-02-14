"""
Bridge Proof Storage & QVCSP (Quantum-Verified Cross-Chain State Proofs)

Implements the proof storage layer for cross-chain bridge verification:
  - BridgeProof: cryptographic proof of a cross-chain state transition
  - ProofStore: indexed storage of proofs with replay protection
  - QVCSP verifier: quantum-entanglement-based proof verification

Proof lifecycle:
  1. Source chain event detected (deposit/withdrawal)
  2. Bridge relayer creates BridgeProof with Merkle inclusion proof
  3. Proof submitted to QBC via QBRIDGE_VERIFY opcode or direct API
  4. ProofStore validates uniqueness (no replay), stores immutably
  5. Bridge contract reads verified proofs to release funds

Patent feature: QVCSP — Quantum-Verified Cross-Chain State Proofs (Section 7.5)
"""

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ProofStatus(Enum):
    """Lifecycle state of a bridge proof."""
    PENDING = "pending"
    VERIFIED = "verified"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ProofType(Enum):
    """Type of cross-chain proof."""
    DEPOSIT = "deposit"          # QBC → wQBC on target chain
    WITHDRAWAL = "withdrawal"    # wQBC burn → QBC unlock
    STATE_SYNC = "state_sync"    # Arbitrary state synchronisation


@dataclass
class BridgeProof:
    """
    A cryptographic proof of a cross-chain state transition.

    Contains the source chain event data, Merkle inclusion proof,
    and optional quantum entanglement ID for QVCSP verification.
    """
    proof_id: str
    source_chain_id: int
    dest_chain_id: int
    proof_type: ProofType
    source_tx_hash: str
    source_block_height: int
    sender: str
    receiver: str
    amount: float
    merkle_proof: List[str]
    state_root: str
    entanglement_id: Optional[int] = None
    status: ProofStatus = ProofStatus.PENDING
    created_at: float = field(default_factory=time.time)
    verified_at: Optional[float] = None
    executed_at: Optional[float] = None
    qbc_block_height: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "proof_id": self.proof_id,
            "source_chain_id": self.source_chain_id,
            "dest_chain_id": self.dest_chain_id,
            "proof_type": self.proof_type.value,
            "source_tx_hash": self.source_tx_hash,
            "source_block_height": self.source_block_height,
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "merkle_proof": self.merkle_proof,
            "state_root": self.state_root,
            "entanglement_id": self.entanglement_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "verified_at": self.verified_at,
            "executed_at": self.executed_at,
            "qbc_block_height": self.qbc_block_height,
        }


def compute_proof_id(
    source_chain_id: int,
    source_tx_hash: str,
    sender: str,
    receiver: str,
    amount: float,
) -> str:
    """
    Derive a deterministic proof ID from its key fields.

    This prevents duplicate proofs for the same source event.
    """
    preimage = (
        f"{source_chain_id}:{source_tx_hash}:{sender}:{receiver}:{amount}"
    )
    return hashlib.sha256(preimage.encode()).hexdigest()


def compute_entanglement_id(
    source_chain_id: int,
    dest_chain_id: int,
    state_root: str,
    block_number: int,
) -> int:
    """
    Compute QBRIDGE_ENTANGLE entanglement ID (mirrors QVM opcode logic).

    Must match the deterministic formula used in vm.py opcode 0xF8
    so that on-chain and off-chain verification produce the same ID.
    """
    seed = (
        str(source_chain_id).encode()
        + str(dest_chain_id).encode()
        + state_root.encode()
        + str(block_number).encode()
    )
    return int.from_bytes(hashlib.sha256(seed).digest(), "big")


def verify_merkle_proof(
    leaf_hash: str,
    proof: List[str],
    root: str,
) -> bool:
    """
    Verify a Merkle inclusion proof.

    Args:
        leaf_hash: Hash of the leaf (source event data).
        proof: List of sibling hashes from leaf to root.
        root: Expected Merkle root.

    Returns:
        True if the proof is valid.
    """
    current = leaf_hash
    for sibling in proof:
        # Canonical ordering: smaller hash first
        if current < sibling:
            combined = current + sibling
        else:
            combined = sibling + current
        current = hashlib.sha256(combined.encode()).hexdigest()
    return current == root


class ProofStore:
    """
    Indexed storage for bridge proofs with replay protection.

    Provides:
      - Submit & verify proofs
      - Replay protection (no duplicate proof_ids)
      - Status lifecycle management
      - Query by chain, status, sender, receiver
    """

    def __init__(self, proof_expiry_seconds: float = 86400.0) -> None:
        """
        Args:
            proof_expiry_seconds: Time after which unverified proofs expire.
        """
        self._proofs: Dict[str, BridgeProof] = {}
        self._by_source_tx: Dict[str, str] = {}  # source_tx_hash → proof_id
        self._proof_expiry = proof_expiry_seconds
        logger.info("ProofStore initialised")

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit_proof(
        self,
        source_chain_id: int,
        dest_chain_id: int,
        proof_type: ProofType,
        source_tx_hash: str,
        source_block_height: int,
        sender: str,
        receiver: str,
        amount: float,
        merkle_proof: List[str],
        state_root: str,
        qbc_block_height: int = 0,
    ) -> Optional[BridgeProof]:
        """
        Submit a new bridge proof for verification.

        Returns None if a proof for this source tx already exists (replay).
        """
        proof_id = compute_proof_id(
            source_chain_id, source_tx_hash, sender, receiver, amount
        )

        # Replay protection
        if proof_id in self._proofs:
            logger.warning(f"Replay rejected: proof {proof_id[:16]}…")
            return None

        if source_tx_hash in self._by_source_tx:
            logger.warning(
                f"Duplicate source tx: {source_tx_hash[:16]}…"
            )
            return None

        # Compute entanglement ID (mirrors QBRIDGE_ENTANGLE opcode)
        ent_id = compute_entanglement_id(
            source_chain_id, dest_chain_id, state_root, qbc_block_height
        )

        proof = BridgeProof(
            proof_id=proof_id,
            source_chain_id=source_chain_id,
            dest_chain_id=dest_chain_id,
            proof_type=proof_type,
            source_tx_hash=source_tx_hash,
            source_block_height=source_block_height,
            sender=sender,
            receiver=receiver,
            amount=amount,
            merkle_proof=merkle_proof,
            state_root=state_root,
            entanglement_id=ent_id,
            status=ProofStatus.PENDING,
            qbc_block_height=qbc_block_height,
        )

        self._proofs[proof_id] = proof
        self._by_source_tx[source_tx_hash] = proof_id

        logger.info(
            f"Proof submitted: {proof_id[:16]}… "
            f"(chain {source_chain_id}→{dest_chain_id}, {amount} QBC)"
        )
        return proof

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    def verify_proof(self, proof_id: str) -> bool:
        """
        Verify a pending proof using its Merkle inclusion proof.

        A proof is valid if:
          1. It exists and is in PENDING status
          2. Its Merkle proof verifies against the state root
          3. It has not expired

        Returns:
            True if the proof is now VERIFIED.
        """
        proof = self._proofs.get(proof_id)
        if proof is None:
            return False

        if proof.status != ProofStatus.PENDING:
            return False

        # Expiry check
        if time.time() - proof.created_at > self._proof_expiry:
            proof.status = ProofStatus.EXPIRED
            logger.info(f"Proof expired: {proof_id[:16]}…")
            return False

        # Compute leaf hash from proof data
        leaf_data = (
            f"{proof.source_chain_id}:{proof.source_tx_hash}:"
            f"{proof.sender}:{proof.receiver}:{proof.amount}"
        )
        leaf_hash = hashlib.sha256(leaf_data.encode()).hexdigest()

        if not verify_merkle_proof(leaf_hash, proof.merkle_proof, proof.state_root):
            proof.status = ProofStatus.REJECTED
            logger.warning(f"Proof rejected (invalid Merkle): {proof_id[:16]}…")
            return False

        proof.status = ProofStatus.VERIFIED
        proof.verified_at = time.time()
        logger.info(f"Proof verified: {proof_id[:16]}…")
        return True

    # ------------------------------------------------------------------
    # Execute (mark as consumed by bridge)
    # ------------------------------------------------------------------

    def mark_executed(self, proof_id: str) -> bool:
        """Mark a verified proof as executed (funds released)."""
        proof = self._proofs.get(proof_id)
        if proof is None or proof.status != ProofStatus.VERIFIED:
            return False
        proof.status = ProofStatus.EXECUTED
        proof.executed_at = time.time()
        logger.info(f"Proof executed: {proof_id[:16]}…")
        return True

    # ------------------------------------------------------------------
    # QVCSP verification (quantum-entanglement path)
    # ------------------------------------------------------------------

    def verify_qvcsp(
        self,
        proof_id: str,
        entanglement_id: int,
        source_chain_id: int,
    ) -> bool:
        """
        Quantum-verified cross-chain state proof (QVCSP).

        Verifies the proof using quantum entanglement correlation:
        the stored entanglement_id must match the one computed by the
        QBRIDGE_ENTANGLE opcode for the same parameters.

        Args:
            proof_id: ID of the proof to verify.
            entanglement_id: Entanglement ID from QBRIDGE_ENTANGLE opcode.
            source_chain_id: Source chain reported by caller.

        Returns:
            True if QVCSP verification passes.
        """
        proof = self._proofs.get(proof_id)
        if proof is None:
            return False

        if proof.status not in (ProofStatus.PENDING, ProofStatus.VERIFIED):
            return False

        # Chain must match
        if proof.source_chain_id != source_chain_id:
            logger.warning(
                f"QVCSP chain mismatch: expected {proof.source_chain_id}, "
                f"got {source_chain_id}"
            )
            return False

        # Entanglement correlation check
        if proof.entanglement_id != entanglement_id:
            logger.warning(
                f"QVCSP entanglement mismatch for {proof_id[:16]}…"
            )
            return False

        if proof.status == ProofStatus.PENDING:
            proof.status = ProofStatus.VERIFIED
            proof.verified_at = time.time()

        logger.info(f"QVCSP verified: {proof_id[:16]}…")
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_proof(self, proof_id: str) -> Optional[BridgeProof]:
        """Get a proof by ID."""
        return self._proofs.get(proof_id)

    def get_proof_by_source_tx(self, source_tx_hash: str) -> Optional[BridgeProof]:
        """Look up a proof by its source chain transaction hash."""
        pid = self._by_source_tx.get(source_tx_hash)
        if pid is None:
            return None
        return self._proofs.get(pid)

    def list_proofs(
        self,
        status: Optional[ProofStatus] = None,
        source_chain_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """List proofs with optional filters."""
        results: List[Dict] = []
        for p in self._proofs.values():
            if status is not None and p.status != status:
                continue
            if source_chain_id is not None and p.source_chain_id != source_chain_id:
                continue
            results.append(p.to_dict())
            if len(results) >= limit:
                break
        return results

    def get_stats(self) -> Dict:
        """Proof store statistics."""
        by_status: Dict[str, int] = {}
        by_chain: Dict[int, int] = {}
        total_amount = 0.0

        for p in self._proofs.values():
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
            by_chain[p.source_chain_id] = by_chain.get(p.source_chain_id, 0) + 1
            total_amount += p.amount

        return {
            "total_proofs": len(self._proofs),
            "by_status": by_status,
            "by_source_chain": by_chain,
            "total_amount": total_amount,
        }

    def expire_stale(self) -> int:
        """Expire all pending proofs past the expiry window. Returns count."""
        now = time.time()
        count = 0
        for p in self._proofs.values():
            if (
                p.status == ProofStatus.PENDING
                and now - p.created_at > self._proof_expiry
            ):
                p.status = ProofStatus.EXPIRED
                count += 1
        if count:
            logger.info(f"Expired {count} stale proofs")
        return count
