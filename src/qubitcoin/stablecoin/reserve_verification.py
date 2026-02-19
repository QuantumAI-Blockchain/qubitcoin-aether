"""
QUSD Reserve Verification & IPFS Snapshots

Public-facing reserve verification for third-party auditing:
  - Real-time backing ratio computation
  - Cryptographic proof of reserves (Merkle root of inflows)
  - Automated daily reserve snapshots to IPFS
  - Quarterly audit report generation

Transparency guarantees:
  - Every inflow has a deterministic ID derived from on-chain data
  - Reserve state is Merkle-committed for tamper detection
  - IPFS snapshots are content-addressed (immutable)
  - Public API requires zero authentication
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Snapshot interval: approximately 1 day at 3.3s/block
BLOCKS_PER_DAY: int = 26_182
# Quarterly report: ~90 days
BLOCKS_PER_QUARTER: int = BLOCKS_PER_DAY * 90


@dataclass
class ReserveSnapshot:
    """Point-in-time snapshot of reserve state."""
    snapshot_id: str
    block_height: int
    timestamp: float
    total_minted_qusd: float
    reserve_value_usd: float
    backing_pct: float
    inflow_count: int
    inflow_merkle_root: str
    chain_year: int
    required_backing_pct: float
    compliant: bool
    chain_supplies: Dict[str, float] = field(default_factory=dict)
    ipfs_cid: str = ""

    def to_dict(self) -> Dict:
        return {
            "snapshot_id": self.snapshot_id,
            "block_height": self.block_height,
            "timestamp": self.timestamp,
            "total_minted_qusd": self.total_minted_qusd,
            "reserve_value_usd": self.reserve_value_usd,
            "backing_pct": self.backing_pct,
            "inflow_count": self.inflow_count,
            "inflow_merkle_root": self.inflow_merkle_root,
            "chain_year": self.chain_year,
            "required_backing_pct": self.required_backing_pct,
            "compliant": self.compliant,
            "chain_supplies": self.chain_supplies,
            "ipfs_cid": self.ipfs_cid,
        }


@dataclass
class AuditReport:
    """Quarterly audit report."""
    report_id: str
    quarter: str  # e.g. "2026-Q1"
    start_block: int
    end_block: int
    start_backing_pct: float
    end_backing_pct: float
    total_inflows_qbc: float
    total_inflows_usd: float
    inflow_count: int
    snapshot_count: int
    violations: int
    milestones_crossed: List[float]
    generated_at: float = field(default_factory=time.time)
    ipfs_cid: str = ""

    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "quarter": self.quarter,
            "start_block": self.start_block,
            "end_block": self.end_block,
            "start_backing_pct": self.start_backing_pct,
            "end_backing_pct": self.end_backing_pct,
            "total_inflows_qbc": self.total_inflows_qbc,
            "total_inflows_usd": self.total_inflows_usd,
            "inflow_count": self.inflow_count,
            "snapshot_count": self.snapshot_count,
            "violations": self.violations,
            "milestones_crossed": self.milestones_crossed,
            "generated_at": self.generated_at,
            "ipfs_cid": self.ipfs_cid,
        }


def compute_merkle_root(hashes: List[str]) -> str:
    """Compute Merkle root from a list of hashes."""
    if not hashes:
        return hashlib.sha256(b"empty").hexdigest()
    if len(hashes) == 1:
        return hashes[0]

    # Pad to even count
    layer = list(hashes)
    if len(layer) % 2 == 1:
        layer.append(layer[-1])

    while len(layer) > 1:
        next_layer = []
        for i in range(0, len(layer), 2):
            left, right = layer[i], layer[i + 1]
            if left > right:
                left, right = right, left
            combined = hashlib.sha256((left + right).encode()).hexdigest()
            next_layer.append(combined)
        layer = next_layer
        if len(layer) > 1 and len(layer) % 2 == 1:
            layer.append(layer[-1])

    return layer[0]


class ReserveVerifier:
    """
    Public reserve verification system.

    Provides:
      - Real-time backing ratio via get_reserve_status()
      - Merkle-committed reserve proof via get_proof_of_reserves()
      - Automated daily snapshots
      - Quarterly audit reports
    """

    def __init__(
        self,
        snapshot_interval_blocks: int = BLOCKS_PER_DAY,
    ) -> None:
        self._snapshots: List[ReserveSnapshot] = []
        self._audit_reports: List[AuditReport] = []
        self._snapshot_interval = snapshot_interval_blocks
        self._last_snapshot_block: int = 0
        self._inflow_hashes: List[str] = []
        logger.info("ReserveVerifier initialised")

    def record_inflow_hash(self, inflow_id: str) -> None:
        """Record an inflow hash for Merkle tree computation."""
        h = hashlib.sha256(inflow_id.encode()).hexdigest()
        self._inflow_hashes.append(h)

    def should_snapshot(self, current_block: int) -> bool:
        """Check if it's time for a new snapshot."""
        return (current_block - self._last_snapshot_block) >= self._snapshot_interval

    def create_snapshot(
        self,
        block_height: int,
        total_minted: float,
        reserve_usd: float,
        chain_year: int,
        required_backing: float,
        chain_supplies: Optional[Dict[str, float]] = None,
    ) -> ReserveSnapshot:
        """
        Create a point-in-time reserve snapshot.

        Args:
            block_height: Current block height.
            total_minted: Total QUSD minted.
            reserve_usd: Total reserve value in USD.
            chain_year: Current chain year from genesis.
            required_backing: Required backing percentage for this year.
            chain_supplies: wQUSD supply per chain.

        Returns:
            The created snapshot.
        """
        backing_pct = (reserve_usd / total_minted * 100.0) if total_minted > 0 else 100.0
        compliant = backing_pct >= required_backing
        merkle_root = compute_merkle_root(list(self._inflow_hashes))

        snapshot_id = hashlib.sha256(
            f"snapshot:{block_height}:{merkle_root}".encode()
        ).hexdigest()[:32]

        snapshot = ReserveSnapshot(
            snapshot_id=snapshot_id,
            block_height=block_height,
            timestamp=time.time(),
            total_minted_qusd=total_minted,
            reserve_value_usd=reserve_usd,
            backing_pct=round(backing_pct, 4),
            inflow_count=len(self._inflow_hashes),
            inflow_merkle_root=merkle_root,
            chain_year=chain_year,
            required_backing_pct=required_backing,
            compliant=compliant,
            chain_supplies=chain_supplies or {},
        )

        self._snapshots.append(snapshot)
        self._last_snapshot_block = block_height

        logger.info(
            f"Reserve snapshot: block {block_height}, "
            f"backing {backing_pct:.2f}% "
            f"({'OK' if compliant else 'VIOLATION'})"
        )
        return snapshot

    def set_snapshot_ipfs_cid(self, snapshot_id: str, cid: str) -> bool:
        """Attach an IPFS CID to a snapshot after pinning."""
        for s in self._snapshots:
            if s.snapshot_id == snapshot_id:
                s.ipfs_cid = cid
                return True
        return False

    def generate_audit_report(
        self,
        quarter: str,
        start_block: int,
        end_block: int,
        total_inflows_qbc: float,
        total_inflows_usd: float,
        inflow_count: int,
        violations: int,
        milestones_crossed: Optional[List[float]] = None,
    ) -> AuditReport:
        """
        Generate a quarterly audit report.

        Args:
            quarter: Quarter identifier (e.g. "2026-Q1").
            start_block: First block of the quarter.
            end_block: Last block of the quarter.
            total_inflows_qbc: Total QBC inflows during the quarter.
            total_inflows_usd: Total USD value of inflows.
            inflow_count: Number of inflow events.
            violations: Number of backing violations during quarter.
            milestones_crossed: Backing milestones crossed in this quarter.

        Returns:
            The generated audit report.
        """
        # Find start/end backing from snapshots
        start_backing = 0.0
        end_backing = 0.0
        snapshot_count = 0

        for s in self._snapshots:
            if s.block_height >= start_block and s.block_height <= end_block:
                snapshot_count += 1
                if s.block_height <= start_block or start_backing == 0.0:
                    start_backing = s.backing_pct
                end_backing = s.backing_pct

        report_id = hashlib.sha256(
            f"audit:{quarter}:{start_block}:{end_block}".encode()
        ).hexdigest()[:32]

        report = AuditReport(
            report_id=report_id,
            quarter=quarter,
            start_block=start_block,
            end_block=end_block,
            start_backing_pct=start_backing,
            end_backing_pct=end_backing,
            total_inflows_qbc=total_inflows_qbc,
            total_inflows_usd=total_inflows_usd,
            inflow_count=inflow_count,
            snapshot_count=snapshot_count,
            violations=violations,
            milestones_crossed=milestones_crossed or [],
        )

        self._audit_reports.append(report)
        logger.info(f"Audit report generated: {quarter}")
        return report

    # ── Public Verification API ────────────────────────────────────────

    def get_reserve_status(
        self,
        total_minted: float,
        reserve_usd: float,
        chain_year: int,
        required_backing: float,
    ) -> Dict:
        """
        Public API: Get current reserve status for third-party verification.

        No authentication required — full transparency.
        """
        backing = (reserve_usd / total_minted * 100.0) if total_minted > 0 else 100.0
        return {
            "total_minted_qusd": total_minted,
            "reserve_value_usd": reserve_usd,
            "backing_pct": round(backing, 4),
            "chain_year": chain_year,
            "required_backing_pct": required_backing,
            "compliant": backing >= required_backing,
            "deficit_pct": round(max(0.0, required_backing - backing), 4),
            "inflow_merkle_root": compute_merkle_root(list(self._inflow_hashes)),
            "total_verified_inflows": len(self._inflow_hashes),
            "snapshot_count": len(self._snapshots),
            "latest_snapshot": (
                self._snapshots[-1].to_dict() if self._snapshots else None
            ),
        }

    def get_proof_of_reserves(self) -> Dict:
        """
        Public API: Get cryptographic proof of reserves.

        Returns Merkle root, snapshot history, and verification instructions.
        """
        return {
            "merkle_root": compute_merkle_root(list(self._inflow_hashes)),
            "inflow_count": len(self._inflow_hashes),
            "snapshot_count": len(self._snapshots),
            "latest_snapshot": (
                self._snapshots[-1].to_dict() if self._snapshots else None
            ),
            "audit_reports": len(self._audit_reports),
            "verification_instructions": (
                "1. Fetch all inflow events from QBC chain. "
                "2. Hash each inflow_id with SHA-256. "
                "3. Build Merkle tree from all hashes. "
                "4. Compare computed root to published merkle_root. "
                "5. Verify reserve balances on-chain match snapshot values."
            ),
        }

    def get_snapshots(self, limit: int = 30) -> List[Dict]:
        """Get recent reserve snapshots."""
        return [s.to_dict() for s in self._snapshots[-limit:]]

    def get_audit_reports(self) -> List[Dict]:
        """Get all quarterly audit reports."""
        return [r.to_dict() for r in self._audit_reports]

    def get_stats(self) -> Dict:
        """Verifier statistics."""
        return {
            "snapshot_count": len(self._snapshots),
            "audit_report_count": len(self._audit_reports),
            "inflow_hash_count": len(self._inflow_hashes),
            "snapshot_interval_blocks": self._snapshot_interval,
            "last_snapshot_block": self._last_snapshot_block,
        }
