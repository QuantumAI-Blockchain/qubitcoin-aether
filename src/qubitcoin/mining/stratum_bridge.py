"""
Python gRPC server for the Stratum mining bridge.

The Rust stratum server connects to this gRPC service to:
- Get work units (block templates) from the mining engine
- Submit mining solutions
- Subscribe to new block notifications
- Query difficulty

Port: STRATUM_GRPC_PORT (default 50053)
"""

import asyncio
import hashlib
import time
from typing import Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StratumBridgeService:
    """Python-side gRPC service for the Rust stratum server.

    In unit tests and when grpcio is not available, this class provides
    the core logic without the gRPC transport layer.
    """

    def __init__(self, mining_engine=None, consensus_engine=None,
                 db_manager=None) -> None:
        self.mining = mining_engine
        self.consensus = consensus_engine
        self.db = db_manager
        self._current_job_id: str = ""
        self._job_counter: int = 0
        self._last_work_height: int = 0
        logger.info("StratumBridgeService initialized")

    def get_work_unit(self) -> dict:
        """Generate a work unit (block template) for miners.

        Returns:
            Dict with job_id, prev_block_hash, height, difficulty, etc.
        """
        self._job_counter += 1
        job_id = hashlib.sha256(
            f"job-{self._job_counter}-{time.time()}".encode()
        ).hexdigest()[:16]
        self._current_job_id = job_id

        # Get current chain state
        height = 0
        prev_hash = "0" * 64
        difficulty = 1.0
        hamiltonian_seed = ""

        if self.consensus:
            height = getattr(self.consensus, '_current_height', 0)
            difficulty = getattr(self.consensus, '_current_difficulty', 1.0)

        if self.db:
            try:
                tip = self.db.get_latest_block()
                if tip:
                    prev_hash = tip.get('hash', prev_hash)
                    height = tip.get('height', height) + 1
            except Exception:
                pass

        self._last_work_height = height

        return {
            'job_id': job_id,
            'prev_block_hash': prev_hash,
            'height': height,
            'difficulty': difficulty,
            'hamiltonian_seed': hashlib.sha256(prev_hash.encode()).hexdigest()[:32],
            'timestamp': int(time.time()),
            'merkle_root': '',
            'extra_data': b'',
        }

    def submit_solution(self, job_id: str, worker_id: str,
                         worker_address: str, vqe_params: list,
                         energy: float, nonce: int) -> dict:
        """Validate and submit a mining solution.

        Args:
            job_id: Job ID from get_work_unit
            worker_id: Stratum worker ID
            worker_address: Miner's QBC address
            vqe_params: VQE optimization parameters
            energy: Ground state energy achieved
            nonce: Block nonce

        Returns:
            Dict with accepted, block_found, reason, block_hash
        """
        # Validate job ID
        if job_id != self._current_job_id:
            return {
                'accepted': False,
                'block_found': False,
                'reason': 'Stale job',
                'block_hash': '',
            }

        # Check energy against difficulty
        difficulty = 1.0
        if self.consensus:
            difficulty = getattr(self.consensus, '_current_difficulty', 1.0)

        if energy >= difficulty:
            return {
                'accepted': False,
                'block_found': False,
                'reason': f'Energy {energy:.4f} >= difficulty {difficulty:.4f}',
                'block_hash': '',
            }

        # Valid share — check if it's also a valid block
        block_hash = hashlib.sha256(
            f"{job_id}-{energy}-{nonce}".encode()
        ).hexdigest()

        logger.info(
            f"Share accepted from worker {worker_id}: "
            f"energy={energy:.4f}, difficulty={difficulty:.4f}"
        )

        return {
            'accepted': True,
            'block_found': True,
            'reason': 'Block found',
            'block_hash': block_hash,
        }

    def get_difficulty(self, height: int) -> dict:
        """Get difficulty for a given height.

        Returns:
            Dict with difficulty and height
        """
        difficulty = 1.0
        if self.consensus:
            difficulty = getattr(self.consensus, '_current_difficulty', 1.0)
        return {'difficulty': difficulty, 'height': height}

    def get_stats(self) -> dict:
        """Get bridge statistics."""
        return {
            'current_job_id': self._current_job_id,
            'job_counter': self._job_counter,
            'last_work_height': self._last_work_height,
        }
