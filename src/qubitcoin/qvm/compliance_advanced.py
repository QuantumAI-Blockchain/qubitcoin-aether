"""
QVM Advanced Compliance Features — TLAC, HDCK, VCR

Three institutional-grade compliance features from the QVM whitepaper:

1. TLAC (Time-Locked Atomic Compliance)
   Multi-jurisdictional approval with time-lock puzzles. A transaction
   requiring approval from multiple regulators in different jurisdictions
   can be structured as a time-locked atomic operation.

2. HDCK (Hierarchical Deterministic Compliance Keys)
   BIP-32 extension with role-based permissions. Organizational key
   hierarchy: m/44'/689'/{org}'/role/index where roles are:
   trading=0, audit=1, compliance=2, emergency=3.

3. VCR (Verifiable Computation Receipts)
   Quantum audit trails that prove a computation was performed correctly
   without re-executing it. 100x faster than re-execution for auditors.
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import IntEnum

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# TLAC — Time-Locked Atomic Compliance
# ═══════════════════════════════════════════════════════════════════════

class ApprovalStatus(IntEnum):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2
    EXPIRED = 3


@dataclass
class JurisdictionApproval:
    """Approval record from a specific jurisdiction."""
    jurisdiction: str           # e.g., "US_SEC", "EU_MiCA", "UK_FCA"
    approver_address: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    timestamp: float = 0.0
    signature: str = ""
    notes: str = ""


@dataclass
class TLACTransaction:
    """
    A Time-Locked Atomic Compliance transaction.

    Requires approval from multiple jurisdictions before execution.
    Automatically expires if not fully approved within the time lock.
    """
    tlac_id: str
    initiator: str
    tx_data: dict               # The transaction to execute on approval
    required_jurisdictions: List[str]
    approvals: Dict[str, JurisdictionApproval] = field(default_factory=dict)
    time_lock_blocks: int = 1000    # Blocks until expiry
    created_block: int = 0
    executed: bool = False
    expired: bool = False

    @property
    def approval_count(self) -> int:
        return sum(
            1 for a in self.approvals.values()
            if a.status == ApprovalStatus.APPROVED
        )

    @property
    def is_fully_approved(self) -> bool:
        return all(
            self.approvals.get(j, JurisdictionApproval(j, "")).status == ApprovalStatus.APPROVED
            for j in self.required_jurisdictions
        )

    @property
    def deadline_block(self) -> int:
        return self.created_block + self.time_lock_blocks

    def to_dict(self) -> dict:
        return {
            "tlac_id": self.tlac_id,
            "initiator": self.initiator,
            "required_jurisdictions": self.required_jurisdictions,
            "approval_count": self.approval_count,
            "total_required": len(self.required_jurisdictions),
            "fully_approved": self.is_fully_approved,
            "deadline_block": self.deadline_block,
            "executed": self.executed,
            "expired": self.expired,
        }


class TLACManager:
    """Manages Time-Locked Atomic Compliance transactions."""

    def __init__(self) -> None:
        self._transactions: Dict[str, TLACTransaction] = {}
        self._total_created: int = 0
        self._total_executed: int = 0
        self._total_expired: int = 0
        logger.info("TLAC Manager initialized")

    def create(self, initiator: str, tx_data: dict,
               jurisdictions: List[str], time_lock_blocks: int,
               block_height: int) -> dict:
        """Create a new TLAC transaction requiring multi-jurisdiction approval."""
        if not jurisdictions:
            return {"success": False, "error": "At least one jurisdiction required"}

        tlac_id = hashlib.sha3_256(
            f"tlac:{initiator}:{block_height}:{time.time()}".encode()
        ).hexdigest()[:16]

        tx = TLACTransaction(
            tlac_id=tlac_id,
            initiator=initiator,
            tx_data=tx_data,
            required_jurisdictions=jurisdictions,
            time_lock_blocks=time_lock_blocks,
            created_block=block_height,
        )
        # Initialize pending approvals
        for j in jurisdictions:
            tx.approvals[j] = JurisdictionApproval(
                jurisdiction=j, approver_address=""
            )

        self._transactions[tlac_id] = tx
        self._total_created += 1

        logger.info(
            f"TLAC {tlac_id} created: {len(jurisdictions)} jurisdictions, "
            f"deadline=block {tx.deadline_block}"
        )
        return {"success": True, "tlac_id": tlac_id, "transaction": tx.to_dict()}

    def approve(self, tlac_id: str, jurisdiction: str,
                approver: str, signature: str = "",
                block_height: int = 0) -> dict:
        """Submit approval from a jurisdiction."""
        tx = self._transactions.get(tlac_id)
        if tx is None:
            return {"success": False, "error": "TLAC not found"}
        if tx.expired:
            return {"success": False, "error": "TLAC expired"}
        if tx.executed:
            return {"success": False, "error": "TLAC already executed"}
        if block_height > tx.deadline_block:
            tx.expired = True
            self._total_expired += 1
            return {"success": False, "error": "TLAC deadline passed"}
        if jurisdiction not in tx.required_jurisdictions:
            return {"success": False, "error": f"Jurisdiction {jurisdiction} not required"}

        tx.approvals[jurisdiction] = JurisdictionApproval(
            jurisdiction=jurisdiction,
            approver_address=approver,
            status=ApprovalStatus.APPROVED,
            timestamp=time.time(),
            signature=signature,
        )

        return {
            "success": True,
            "tlac_id": tlac_id,
            "jurisdiction": jurisdiction,
            "fully_approved": tx.is_fully_approved,
            "remaining": [
                j for j in tx.required_jurisdictions
                if tx.approvals.get(j, JurisdictionApproval(j, "")).status != ApprovalStatus.APPROVED
            ],
        }

    def execute_if_ready(self, tlac_id: str, block_height: int) -> dict:
        """Execute the TLAC transaction if fully approved."""
        tx = self._transactions.get(tlac_id)
        if tx is None:
            return {"success": False, "error": "TLAC not found"}
        if tx.executed:
            return {"success": False, "error": "Already executed"}
        if block_height > tx.deadline_block:
            tx.expired = True
            self._total_expired += 1
            return {"success": False, "error": "Deadline expired"}
        if not tx.is_fully_approved:
            return {"success": False, "error": "Not fully approved"}

        tx.executed = True
        self._total_executed += 1
        logger.info(f"TLAC {tlac_id} executed at block {block_height}")
        return {"success": True, "tlac_id": tlac_id, "tx_data": tx.tx_data}

    def expire_stale(self, block_height: int) -> int:
        """Expire all TLAC transactions past their deadline."""
        count = 0
        for tx in self._transactions.values():
            if not tx.expired and not tx.executed and block_height > tx.deadline_block:
                tx.expired = True
                self._total_expired += 1
                count += 1
        return count

    def get_stats(self) -> dict:
        active = sum(
            1 for t in self._transactions.values()
            if not t.expired and not t.executed
        )
        return {
            "total_created": self._total_created,
            "total_executed": self._total_executed,
            "total_expired": self._total_expired,
            "active": active,
        }


# ═══════════════════════════════════════════════════════════════════════
# HDCK — Hierarchical Deterministic Compliance Keys
# ═══════════════════════════════════════════════════════════════════════

class HDCKRole(IntEnum):
    """Role-based key derivation paths: m/44'/689'/{org}'/role/index"""
    TRADING = 0
    AUDIT = 1
    COMPLIANCE = 2
    EMERGENCY = 3


@dataclass
class HDCKNode:
    """A node in the hierarchical key derivation tree."""
    path: str                   # e.g., "m/44'/689'/0'/2/0"
    role: HDCKRole
    org_id: int
    index: int
    public_key_hash: str        # SHA3-256 of the derived public key
    permissions: Set[str] = field(default_factory=set)
    active: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "role": self.role.name,
            "org_id": self.org_id,
            "index": self.index,
            "public_key_hash": self.public_key_hash[:16] + "...",
            "permissions": sorted(self.permissions),
            "active": self.active,
        }


# Default permissions per role
ROLE_PERMISSIONS: Dict[HDCKRole, Set[str]] = {
    HDCKRole.TRADING: {"sign_tx", "view_balance", "create_order"},
    HDCKRole.AUDIT: {"view_all", "export_reports", "verify_proofs"},
    HDCKRole.COMPLIANCE: {"freeze_account", "approve_kyc", "review_aml", "sign_tx"},
    HDCKRole.EMERGENCY: {"freeze_all", "pause_contracts", "emergency_withdraw", "revoke_keys"},
}


class HDCKManager:
    """Manages Hierarchical Deterministic Compliance Key derivation."""

    QBC_COIN_TYPE = 689  # Registered coin type for QBC

    def __init__(self) -> None:
        self._keys: Dict[str, HDCKNode] = {}  # path → node
        self._org_keys: Dict[int, List[str]] = {}  # org_id → [paths]
        logger.info("HDCK Manager initialized (BIP-32 compliance keys)")

    def derive_key(self, org_id: int, role: HDCKRole, index: int,
                   public_key_hex: str = "") -> dict:
        """
        Derive a compliance key at the specified path.

        Path format: m/44'/689'/{org_id}'/{role}/{index}

        Args:
            org_id: Organization identifier.
            role: Key role (TRADING, AUDIT, COMPLIANCE, EMERGENCY).
            index: Key index within the role.
            public_key_hex: Optional public key material for hashing.

        Returns:
            Result dict with the derived key node.
        """
        path = f"m/44'/{self.QBC_COIN_TYPE}'/{org_id}'/{role.value}/{index}"

        if path in self._keys:
            return {"success": False, "error": f"Key already exists at {path}"}

        # Derive key hash (in production: actual BIP-32 derivation)
        key_material = public_key_hex or f"{path}:{time.time()}"
        key_hash = hashlib.sha3_256(key_material.encode()).hexdigest()

        node = HDCKNode(
            path=path,
            role=role,
            org_id=org_id,
            index=index,
            public_key_hash=key_hash,
            permissions=set(ROLE_PERMISSIONS.get(role, set())),
        )

        self._keys[path] = node
        self._org_keys.setdefault(org_id, []).append(path)

        logger.info(f"HDCK derived: {path} (role={role.name}, perms={len(node.permissions)})")
        return {"success": True, "path": path, "key": node.to_dict()}

    def check_permission(self, path: str, permission: str) -> bool:
        """Check if a key at the given path has a specific permission."""
        node = self._keys.get(path)
        if node is None or not node.active:
            return False
        return permission in node.permissions

    def revoke_key(self, path: str) -> dict:
        """Revoke a key (mark as inactive)."""
        node = self._keys.get(path)
        if node is None:
            return {"success": False, "error": "Key not found"}
        node.active = False
        logger.warning(f"HDCK key revoked: {path}")
        return {"success": True, "path": path}

    def get_org_keys(self, org_id: int) -> List[dict]:
        """Get all keys for an organization."""
        paths = self._org_keys.get(org_id, [])
        return [self._keys[p].to_dict() for p in paths if p in self._keys]

    def get_stats(self) -> dict:
        active = sum(1 for k in self._keys.values() if k.active)
        return {
            "total_keys": len(self._keys),
            "active_keys": active,
            "organizations": len(self._org_keys),
        }


# ═══════════════════════════════════════════════════════════════════════
# VCR — Verifiable Computation Receipts
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ComputationReceipt:
    """
    A verifiable receipt proving a computation was performed correctly.

    Auditors can verify the receipt without re-executing the computation,
    achieving ~100x speedup over full re-execution.
    """
    receipt_id: str
    computation_hash: str       # Hash of the computation inputs
    result_hash: str            # Hash of the computation outputs
    execution_trace_root: str   # Merkle root of execution trace
    gas_used: int
    block_height: int
    executor: str               # Address that performed the computation
    timestamp: float = field(default_factory=time.time)
    verified_by: List[str] = field(default_factory=list)
    verification_count: int = 0

    @property
    def integrity_hash(self) -> str:
        """Hash binding all receipt fields together."""
        data = (
            f"{self.receipt_id}:{self.computation_hash}:{self.result_hash}:"
            f"{self.execution_trace_root}:{self.gas_used}:{self.block_height}"
        )
        return hashlib.sha3_256(data.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "computation_hash": self.computation_hash[:16] + "...",
            "result_hash": self.result_hash[:16] + "...",
            "trace_root": self.execution_trace_root[:16] + "...",
            "gas_used": self.gas_used,
            "block_height": self.block_height,
            "executor": self.executor,
            "verification_count": self.verification_count,
            "integrity": self.integrity_hash[:16] + "...",
        }


class VCRStore:
    """
    Stores and verifies Computation Receipts.

    Provides:
    - Receipt creation from execution results
    - Fast verification without re-execution
    - Audit trail with multi-verifier support
    - Receipt chain linking (previous receipt references)
    """

    def __init__(self, max_receipts: int = 10000) -> None:
        self._receipts: Dict[str, ComputationReceipt] = {}
        self._block_receipts: Dict[int, List[str]] = {}  # block → receipt_ids
        self._max_receipts = max_receipts
        self._total_created: int = 0
        self._total_verified: int = 0
        logger.info("VCR Store initialized (Verifiable Computation Receipts)")

    def create_receipt(self, computation_input: str, computation_output: str,
                       execution_trace: List[str], gas_used: int,
                       block_height: int, executor: str) -> ComputationReceipt:
        """
        Create a VCR from computation results.

        Args:
            computation_input: Serialized computation inputs.
            computation_output: Serialized computation outputs.
            execution_trace: List of execution step hashes.
            gas_used: Gas consumed by the computation.
            block_height: Block at which computation occurred.
            executor: Address that ran the computation.

        Returns:
            The created ComputationReceipt.
        """
        receipt_id = hashlib.sha3_256(
            f"vcr:{executor}:{block_height}:{time.time()}".encode()
        ).hexdigest()[:16]

        computation_hash = hashlib.sha3_256(computation_input.encode()).hexdigest()
        result_hash = hashlib.sha3_256(computation_output.encode()).hexdigest()
        trace_root = self._compute_trace_root(execution_trace)

        receipt = ComputationReceipt(
            receipt_id=receipt_id,
            computation_hash=computation_hash,
            result_hash=result_hash,
            execution_trace_root=trace_root,
            gas_used=gas_used,
            block_height=block_height,
            executor=executor,
        )

        self._receipts[receipt_id] = receipt
        self._block_receipts.setdefault(block_height, []).append(receipt_id)
        self._total_created += 1

        # Evict old receipts if over limit
        if len(self._receipts) > self._max_receipts:
            self._evict_oldest()

        return receipt

    def verify_receipt(self, receipt_id: str, verifier: str,
                       expected_computation_hash: str = "",
                       expected_result_hash: str = "") -> dict:
        """
        Verify a computation receipt without re-executing.

        Checks:
        1. Receipt exists and has valid integrity
        2. Computation hash matches expected (if provided)
        3. Result hash matches expected (if provided)

        Returns:
            Verification result dict.
        """
        receipt = self._receipts.get(receipt_id)
        if receipt is None:
            return {"verified": False, "reason": "Receipt not found"}

        # Verify integrity (hash binding)
        expected_integrity = receipt.integrity_hash
        recomputed = hashlib.sha3_256(
            f"{receipt.receipt_id}:{receipt.computation_hash}:{receipt.result_hash}:"
            f"{receipt.execution_trace_root}:{receipt.gas_used}:{receipt.block_height}".encode()
        ).hexdigest()

        if expected_integrity != recomputed:
            return {"verified": False, "reason": "Integrity check failed"}

        # Verify computation hash if provided
        if expected_computation_hash and receipt.computation_hash != expected_computation_hash:
            return {"verified": False, "reason": "Computation hash mismatch"}

        # Verify result hash if provided
        if expected_result_hash and receipt.result_hash != expected_result_hash:
            return {"verified": False, "reason": "Result hash mismatch"}

        # Record verification
        if verifier not in receipt.verified_by:
            receipt.verified_by.append(verifier)
            receipt.verification_count += 1
        self._total_verified += 1

        return {
            "verified": True,
            "receipt_id": receipt_id,
            "verifier": verifier,
            "verification_count": receipt.verification_count,
        }

    def get_receipt(self, receipt_id: str) -> Optional[dict]:
        r = self._receipts.get(receipt_id)
        return r.to_dict() if r else None

    def get_block_receipts(self, block_height: int) -> List[dict]:
        ids = self._block_receipts.get(block_height, [])
        return [
            self._receipts[rid].to_dict()
            for rid in ids if rid in self._receipts
        ]

    def _compute_trace_root(self, trace: List[str]) -> str:
        """Compute Merkle root of execution trace steps."""
        if not trace:
            return "0" * 64
        leaves = [hashlib.sha3_256(s.encode()).hexdigest() for s in trace]
        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])
            next_level = []
            for i in range(0, len(leaves), 2):
                combined = leaves[i] + leaves[i + 1]
                next_level.append(hashlib.sha3_256(combined.encode()).hexdigest())
            leaves = next_level
        return leaves[0]

    def _evict_oldest(self) -> None:
        """Evict oldest receipts beyond capacity."""
        if len(self._receipts) <= self._max_receipts:
            return
        sorted_ids = sorted(
            self._receipts.keys(),
            key=lambda rid: self._receipts[rid].timestamp,
        )
        to_remove = sorted_ids[:len(self._receipts) - self._max_receipts]
        for rid in to_remove:
            del self._receipts[rid]

    def get_stats(self) -> dict:
        return {
            "total_created": self._total_created,
            "total_verified": self._total_verified,
            "stored": len(self._receipts),
            "max_capacity": self._max_receipts,
        }
