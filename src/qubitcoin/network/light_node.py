"""
Light Node — SPV Verification and Fast Sync Protocol

Provides Simplified Payment Verification (SPV) for resource-constrained
devices (mobile, embedded). Light nodes store only block headers and
verify transactions via Merkle proofs without downloading full blocks.

Node type comparison (from CLAUDE.md):
  Full Node:    500GB+, 16GB RAM, full validation
  Light Node:   1GB,    2GB RAM,  SPV verification, <5min sync
  Mining Node:  Full + quantum hardware
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Sync constants
HEADERS_PER_BATCH = 500          # Headers fetched per sync request
MAX_HEADER_STORE = 1_000_000     # Max headers in memory (~80MB for QBC headers)
CHECKPOINT_INTERVAL = 10_000     # Store checkpoint every N blocks
SPV_CONFIRMATION_DEPTH = 6       # Standard confirmation depth


@dataclass
class BlockHeader:
    """Compact block header for SPV storage (~200 bytes vs full block)."""
    height: int
    block_hash: str
    prev_hash: str
    merkle_root: str
    timestamp: float
    difficulty: float
    state_root: str = ""

    def compute_hash(self) -> str:
        """Compute SHA3-256 hash of the header."""
        data = (
            f"{self.height}:{self.prev_hash}:{self.merkle_root}:"
            f"{self.timestamp}:{self.difficulty}"
        )
        return hashlib.sha3_256(data.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "height": self.height,
            "block_hash": self.block_hash,
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "difficulty": self.difficulty,
            "state_root": self.state_root,
        }


@dataclass
class MerkleProof:
    """Merkle inclusion proof for SPV transaction verification."""
    tx_hash: str
    block_height: int
    proof_hashes: List[str]     # Sibling hashes from leaf to root
    proof_indices: List[int]    # 0 = left, 1 = right at each level
    merkle_root: str            # Expected root (from block header)

    def to_dict(self) -> dict:
        return {
            "tx_hash": self.tx_hash,
            "block_height": self.block_height,
            "proof_hashes": self.proof_hashes,
            "proof_indices": self.proof_indices,
            "merkle_root": self.merkle_root,
        }


@dataclass
class SyncCheckpoint:
    """Hardcoded checkpoint for fast sync validation."""
    height: int
    block_hash: str
    timestamp: float


class SPVVerifier:
    """
    Simplified Payment Verification engine.

    Verifies that a transaction is included in a block by checking its
    Merkle proof against the block header's merkle_root. Does NOT validate
    the transaction itself — only its inclusion in the chain.

    Security model:
    - Assumes the longest chain with valid PoW is honest (SPV assumption)
    - Requires SPV_CONFIRMATION_DEPTH (6) confirmations for confidence
    - Vulnerable to 51% attacks (same as Bitcoin SPV)
    """

    def __init__(self) -> None:
        self._verifications: int = 0
        self._failures: int = 0
        logger.info("SPV Verifier initialized")

    def verify_merkle_proof(self, proof: MerkleProof) -> bool:
        """
        Verify a Merkle inclusion proof.

        Recomputes the Merkle root from the transaction hash and proof path,
        then checks against the expected root from the block header.

        Args:
            proof: MerkleProof containing tx_hash, sibling hashes, and root.

        Returns:
            True if the proof is valid (tx is in the block).
        """
        if not proof.proof_hashes:
            # Single-tx block: tx_hash should equal merkle_root
            result = proof.tx_hash == proof.merkle_root
            self._record(result)
            return result

        if len(proof.proof_hashes) != len(proof.proof_indices):
            self._record(False)
            return False

        current = proof.tx_hash
        for sibling, index in zip(proof.proof_hashes, proof.proof_indices):
            if index == 0:
                # Current is on the left, sibling is on the right
                combined = current + sibling
            else:
                # Current is on the right, sibling is on the left
                combined = sibling + current
            current = hashlib.sha3_256(combined.encode()).hexdigest()

        result = current == proof.merkle_root
        self._record(result)
        return result

    def verify_tx_in_chain(self, proof: MerkleProof,
                           headers: Dict[int, BlockHeader],
                           chain_tip: int) -> dict:
        """
        Full SPV verification: Merkle proof + confirmation depth.

        Args:
            proof: Merkle inclusion proof.
            headers: Block header store.
            chain_tip: Current chain tip height.

        Returns:
            Verification result dict.
        """
        # Check block header exists
        header = headers.get(proof.block_height)
        if header is None:
            return {
                "verified": False,
                "reason": f"Block header {proof.block_height} not found",
                "confirmations": 0,
            }

        # Verify Merkle root matches header
        if proof.merkle_root != header.merkle_root:
            return {
                "verified": False,
                "reason": "Merkle root mismatch with block header",
                "confirmations": 0,
            }

        # Verify Merkle proof
        if not self.verify_merkle_proof(proof):
            return {
                "verified": False,
                "reason": "Invalid Merkle proof",
                "confirmations": 0,
            }

        # Check confirmation depth
        confirmations = chain_tip - proof.block_height
        confirmed = confirmations >= SPV_CONFIRMATION_DEPTH

        return {
            "verified": True,
            "confirmed": confirmed,
            "confirmations": confirmations,
            "required_confirmations": SPV_CONFIRMATION_DEPTH,
            "block_hash": header.block_hash,
            "block_height": proof.block_height,
        }

    def _record(self, success: bool) -> None:
        self._verifications += 1
        if not success:
            self._failures += 1

    def get_stats(self) -> dict:
        return {
            "total_verifications": self._verifications,
            "failures": self._failures,
            "success_rate": round(
                (self._verifications - self._failures) /
                max(self._verifications, 1), 4
            ),
        }


class LightNodeSync:
    """
    Fast header sync protocol for light nodes.

    Sync protocol:
    1. Fetch checkpoints from trusted source (hardcoded + peers)
    2. Download headers in batches of HEADERS_PER_BATCH
    3. Validate header chain (prev_hash linkage + difficulty)
    4. Verify against checkpoints at CHECKPOINT_INTERVAL
    5. Store headers in memory (compact ~200 bytes each)

    Target: <5 minutes for full sync from genesis to tip.
    At 3.3s blocks, 1 year ≈ 9.5M blocks ≈ 1.9GB headers.
    With batched download, sync rate = ~50K headers/sec → ~3 min for 1 year.
    """

    def __init__(self) -> None:
        self._headers: Dict[int, BlockHeader] = {}
        self._tip_height: int = -1
        self._checkpoints: List[SyncCheckpoint] = []
        self._sync_start_time: Optional[float] = None
        self._sync_complete: bool = False
        self._headers_synced: int = 0
        self._validation_errors: int = 0
        logger.info("Light Node Sync initialized")

    @property
    def tip_height(self) -> int:
        return self._tip_height

    @property
    def is_synced(self) -> bool:
        return self._sync_complete

    @property
    def header_count(self) -> int:
        return len(self._headers)

    def add_checkpoint(self, height: int, block_hash: str,
                       timestamp: float = 0.0) -> None:
        """Add a trusted checkpoint for sync validation."""
        self._checkpoints.append(SyncCheckpoint(
            height=height, block_hash=block_hash, timestamp=timestamp
        ))
        self._checkpoints.sort(key=lambda c: c.height)
        logger.debug(f"Checkpoint added: height={height}")

    def process_header_batch(self, headers: List[BlockHeader]) -> dict:
        """
        Process a batch of headers from a peer.

        Validates chain linkage, difficulty, and checkpoint alignment.

        Args:
            headers: Batch of BlockHeader objects (must be in order).

        Returns:
            Dict with accepted count, rejected count, errors.
        """
        if not headers:
            return {"accepted": 0, "rejected": 0, "errors": []}

        if self._sync_start_time is None:
            self._sync_start_time = time.monotonic()

        accepted = 0
        rejected = 0
        errors: List[str] = []

        for header in headers:
            # Validate chain linkage
            if header.height > 0:
                prev = self._headers.get(header.height - 1)
                if prev and prev.block_hash != header.prev_hash:
                    errors.append(
                        f"Height {header.height}: prev_hash mismatch "
                        f"(expected {prev.block_hash[:16]}...)"
                    )
                    rejected += 1
                    self._validation_errors += 1
                    continue

            # Validate against checkpoints
            checkpoint = self._get_checkpoint(header.height)
            if checkpoint and checkpoint.block_hash != header.block_hash:
                errors.append(
                    f"Height {header.height}: checkpoint mismatch "
                    f"(expected {checkpoint.block_hash[:16]}...)"
                )
                rejected += 1
                self._validation_errors += 1
                continue

            # Validate difficulty is positive
            if header.difficulty <= 0:
                errors.append(f"Height {header.height}: invalid difficulty {header.difficulty}")
                rejected += 1
                self._validation_errors += 1
                continue

            # Accept header
            self._headers[header.height] = header
            if header.height > self._tip_height:
                self._tip_height = header.height
            accepted += 1
            self._headers_synced += 1

        # Evict old headers if over limit
        if len(self._headers) > MAX_HEADER_STORE:
            self._evict_old_headers()

        return {"accepted": accepted, "rejected": rejected, "errors": errors}

    def mark_sync_complete(self) -> None:
        """Mark sync as complete (all headers downloaded)."""
        self._sync_complete = True
        duration = time.monotonic() - (self._sync_start_time or time.monotonic())
        logger.info(
            f"Light node sync complete: {self._headers_synced} headers "
            f"in {duration:.1f}s (tip={self._tip_height})"
        )

    def get_header(self, height: int) -> Optional[BlockHeader]:
        """Get a stored block header by height."""
        return self._headers.get(height)

    def get_headers_range(self, start: int, end: int) -> List[BlockHeader]:
        """Get a range of headers [start, end)."""
        return [
            self._headers[h]
            for h in range(start, end)
            if h in self._headers
        ]

    def get_header_store(self) -> Dict[int, BlockHeader]:
        """Get the full header store (for SPV verification)."""
        return self._headers

    def _get_checkpoint(self, height: int) -> Optional[SyncCheckpoint]:
        """Find checkpoint at exact height."""
        for cp in self._checkpoints:
            if cp.height == height:
                return cp
        return None

    def _evict_old_headers(self) -> None:
        """Evict oldest headers beyond MAX_HEADER_STORE, keeping checkpoints."""
        if len(self._headers) <= MAX_HEADER_STORE:
            return
        # Keep headers from tip - MAX_HEADER_STORE onward
        min_keep = max(0, self._tip_height - MAX_HEADER_STORE)
        checkpoint_heights = {cp.height for cp in self._checkpoints}
        to_remove = [
            h for h in self._headers
            if h < min_keep and h not in checkpoint_heights
        ]
        for h in to_remove:
            del self._headers[h]

    def get_status(self) -> dict:
        """Get sync status for API/dashboard."""
        elapsed = 0.0
        if self._sync_start_time:
            elapsed = time.monotonic() - self._sync_start_time
        return {
            "synced": self._sync_complete,
            "tip_height": self._tip_height,
            "headers_stored": len(self._headers),
            "headers_synced": self._headers_synced,
            "checkpoints": len(self._checkpoints),
            "validation_errors": self._validation_errors,
            "sync_duration_s": round(elapsed, 2),
            "headers_per_sec": round(
                self._headers_synced / max(elapsed, 0.001), 1
            ) if elapsed > 0 else 0,
        }


class LightNode:
    """
    Complete light node combining SPV verification with header sync.

    Usage:
        node = LightNode()
        # Add checkpoints from trusted source
        node.sync.add_checkpoint(0, genesis_hash)
        node.sync.add_checkpoint(10000, checkpoint_hash)
        # Process headers from peers
        node.sync.process_header_batch(headers)
        node.sync.mark_sync_complete()
        # Verify transactions
        result = node.verify_transaction(proof)
    """

    def __init__(self) -> None:
        self.spv = SPVVerifier()
        self.sync = LightNodeSync()
        logger.info(
            f"Light Node initialized (SPV mode, "
            f"confirmation_depth={SPV_CONFIRMATION_DEPTH})"
        )

    def verify_transaction(self, proof: MerkleProof) -> dict:
        """Verify a transaction via SPV against stored headers."""
        return self.spv.verify_tx_in_chain(
            proof,
            self.sync.get_header_store(),
            self.sync.tip_height,
        )

    def get_status(self) -> dict:
        """Get combined light node status."""
        return {
            "type": "light",
            "sync": self.sync.get_status(),
            "spv": self.spv.get_stats(),
            "chain_id": Config.CHAIN_ID,
        }
