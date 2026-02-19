"""
QVM Transaction Batcher — Rollup-Style Batch Execution

Aggregates multiple QVM transactions into a single batch that is
executed atomically and committed as one state transition. This reduces
per-transaction overhead and enables higher throughput.

Batch protocol:
1. COLLECT: Accumulate transactions into a pending batch
2. VALIDATE: Check all transactions meet gas/compliance requirements
3. EXECUTE: Run all transactions in sequence via QVM
4. COMMIT: Compute batch state root and commit to chain
5. PROVE: Generate batch proof (Merkle root of tx receipts)

Benefits:
- Amortized gas: batch overhead shared across N transactions
- Atomic execution: all-or-nothing semantics per batch
- Compressed storage: batch proof replaces N individual proofs
- Higher throughput: reduced per-tx chain interaction
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)

MAX_BATCH_SIZE = 100            # Max transactions per batch
MAX_BATCH_GAS = 15_000_000     # Gas limit per batch (half of block)
BATCH_TIMEOUT_BLOCKS = 10       # Auto-submit after N blocks


class BatchState(str, Enum):
    COLLECTING = "collecting"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMMITTED = "committed"
    FAILED = "failed"


@dataclass
class BatchTransaction:
    """A transaction queued for batch execution."""
    tx_id: str
    sender: str
    to: str
    value: float
    data: bytes = b""
    gas_limit: int = 21000
    gas_price: float = 0.000000001  # 1 Gwei
    nonce: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def gas_cost(self) -> float:
        return self.gas_limit * self.gas_price

    def to_dict(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "sender": self.sender,
            "to": self.to,
            "value": self.value,
            "gas_limit": self.gas_limit,
            "nonce": self.nonce,
        }


@dataclass
class BatchReceipt:
    """Receipt for a committed batch."""
    batch_id: str
    tx_count: int
    total_gas_used: int
    batch_root: str              # Merkle root of all tx receipts
    state_root_before: str
    state_root_after: str
    block_height: int
    success: bool
    tx_results: List[dict] = field(default_factory=list)
    duration_s: float = 0.0
    committed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "tx_count": self.tx_count,
            "total_gas_used": self.total_gas_used,
            "batch_root": self.batch_root,
            "state_root_before": self.state_root_before,
            "state_root_after": self.state_root_after,
            "block_height": self.block_height,
            "success": self.success,
            "duration_s": round(self.duration_s, 3),
        }


class TransactionBatcher:
    """
    Rollup-style transaction batcher for QVM.

    Collects transactions, validates them, executes as a batch,
    and produces a batch receipt with Merkle proof.
    """

    def __init__(self, max_batch_size: int = MAX_BATCH_SIZE,
                 max_batch_gas: int = MAX_BATCH_GAS) -> None:
        self._max_size = max_batch_size
        self._max_gas = max_batch_gas
        self._pending: List[BatchTransaction] = []
        self._batch_id_counter: int = 0
        self._receipts: List[BatchReceipt] = []
        self._total_batches: int = 0
        self._total_tx_batched: int = 0
        self._current_gas: int = 0
        self._start_block: Optional[int] = None
        logger.info(
            f"Transaction Batcher initialized "
            f"(max_size={max_batch_size}, max_gas={max_batch_gas})"
        )

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def pending_gas(self) -> int:
        return self._current_gas

    def add_transaction(self, tx: BatchTransaction) -> dict:
        """
        Add a transaction to the current batch.

        Returns error if batch is full or gas limit would be exceeded.
        """
        if len(self._pending) >= self._max_size:
            return {"success": False, "error": "Batch full"}

        if self._current_gas + tx.gas_limit > self._max_gas:
            return {"success": False, "error": "Batch gas limit exceeded"}

        self._pending.append(tx)
        self._current_gas += tx.gas_limit

        if self._start_block is None:
            self._start_block = 0  # Will be set on commit

        return {
            "success": True,
            "batch_position": len(self._pending) - 1,
            "pending_count": len(self._pending),
            "remaining_gas": self._max_gas - self._current_gas,
        }

    def should_submit(self, block_height: int) -> bool:
        """Check if batch should be auto-submitted (full or timeout)."""
        if len(self._pending) >= self._max_size:
            return True
        if self._current_gas >= self._max_gas:
            return True
        if (self._start_block is not None and
                block_height - self._start_block >= BATCH_TIMEOUT_BLOCKS and
                len(self._pending) > 0):
            return True
        return False

    def execute_batch(self, block_height: int,
                      state_root_before: str = "") -> BatchReceipt:
        """
        Execute all pending transactions as a single batch.

        In production, this would call QVM.execute() for each tx.
        Here we simulate execution and produce a batch receipt.

        Args:
            block_height: Current block height.
            state_root_before: State root before batch execution.

        Returns:
            BatchReceipt with results.
        """
        start = time.monotonic()
        self._batch_id_counter += 1
        batch_id = hashlib.sha3_256(
            f"batch:{self._batch_id_counter}:{block_height}:{time.time()}".encode()
        ).hexdigest()[:16]

        tx_results = []
        total_gas = 0

        for i, tx in enumerate(self._pending):
            # Simulate execution (in production: self.qvm.execute(tx))
            result = {
                "tx_id": tx.tx_id,
                "index": i,
                "gas_used": tx.gas_limit,
                "success": True,
            }
            tx_results.append(result)
            total_gas += tx.gas_limit

        # Compute batch Merkle root from tx results
        batch_root = self._compute_batch_root(tx_results)

        # Compute new state root (simulated)
        state_root_after = hashlib.sha3_256(
            f"{state_root_before}:{batch_root}".encode()
        ).hexdigest()

        duration = time.monotonic() - start
        receipt = BatchReceipt(
            batch_id=batch_id,
            tx_count=len(self._pending),
            total_gas_used=total_gas,
            batch_root=batch_root,
            state_root_before=state_root_before,
            state_root_after=state_root_after,
            block_height=block_height,
            success=True,
            tx_results=tx_results,
            duration_s=duration,
        )

        self._receipts.append(receipt)
        self._total_batches += 1
        self._total_tx_batched += len(self._pending)

        # Clear pending
        self._pending.clear()
        self._current_gas = 0
        self._start_block = None

        logger.info(
            f"Batch {batch_id} committed: {receipt.tx_count} txs, "
            f"gas={total_gas}, root={batch_root[:16]}..."
        )
        return receipt

    def _compute_batch_root(self, tx_results: List[dict]) -> str:
        """Compute Merkle root of transaction results."""
        if not tx_results:
            return "0" * 64

        # Leaf hashes
        leaves = [
            hashlib.sha3_256(
                f"{r['tx_id']}:{r['gas_used']}:{r['success']}".encode()
            ).hexdigest()
            for r in tx_results
        ]

        # Build Merkle tree bottom-up
        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])  # Duplicate last if odd
            next_level = []
            for i in range(0, len(leaves), 2):
                combined = leaves[i] + leaves[i + 1]
                next_level.append(
                    hashlib.sha3_256(combined.encode()).hexdigest()
                )
            leaves = next_level

        return leaves[0]

    def get_pending(self) -> List[dict]:
        return [tx.to_dict() for tx in self._pending]

    def get_receipt(self, batch_id: str) -> Optional[dict]:
        for r in self._receipts:
            if r.batch_id == batch_id:
                return r.to_dict()
        return None

    def get_stats(self) -> dict:
        return {
            "pending_count": len(self._pending),
            "pending_gas": self._current_gas,
            "max_batch_size": self._max_size,
            "max_batch_gas": self._max_gas,
            "total_batches": self._total_batches,
            "total_tx_batched": self._total_tx_batched,
            "avg_batch_size": round(
                self._total_tx_batched / max(self._total_batches, 1), 1
            ),
            "receipts_stored": len(self._receipts),
        }
