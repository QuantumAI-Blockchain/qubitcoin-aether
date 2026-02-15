"""
SUSY Hamiltonian solution verification tracker.

Tracks how many independent verifications each solved Hamiltonian has
received, enabling confidence scoring for the scientific database.

Every mined block contributes a solved SUSY Hamiltonian. Other nodes
can verify the solution by re-running VQE and confirming energy < threshold.
This module tracks those verification counts.
"""
import time
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SolutionVerification:
    """A single verification event for a Hamiltonian solution."""
    verifier_address: str
    block_height: int
    verified_energy: float
    matches_original: bool
    timestamp: float = field(default_factory=time.time)
    verification_id: str = ''

    def __post_init__(self) -> None:
        if not self.verification_id:
            raw = f"{self.verifier_address}:{self.block_height}:{self.timestamp}"
            self.verification_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            'verification_id': self.verification_id,
            'verifier_address': self.verifier_address,
            'block_height': self.block_height,
            'verified_energy': self.verified_energy,
            'matches_original': self.matches_original,
            'timestamp': self.timestamp,
        }


@dataclass
class SolutionRecord:
    """Aggregate record for a solved Hamiltonian with verification history."""
    solution_id: int
    block_height: int
    miner_address: str
    original_energy: float
    verifications: List[SolutionVerification] = field(default_factory=list)

    @property
    def verification_count(self) -> int:
        return len(self.verifications)

    @property
    def confirmed_count(self) -> int:
        return sum(1 for v in self.verifications if v.matches_original)

    @property
    def confidence(self) -> float:
        """Confidence score: ratio of confirmations to total verifications."""
        if self.verification_count == 0:
            return 0.0
        return self.confirmed_count / self.verification_count

    def to_dict(self) -> dict:
        return {
            'solution_id': self.solution_id,
            'block_height': self.block_height,
            'miner_address': self.miner_address,
            'original_energy': self.original_energy,
            'verification_count': self.verification_count,
            'confirmed_count': self.confirmed_count,
            'confidence': round(self.confidence, 4),
            'verifications': [v.to_dict() for v in self.verifications],
        }


class SolutionVerificationTracker:
    """Tracks verification counts for solved SUSY Hamiltonians.

    Each mined block's Hamiltonian solution can be independently verified
    by other nodes. This tracker aggregates those verifications and provides
    confidence scoring for the scientific database.

    Usage:
        tracker = SolutionVerificationTracker()
        tracker.register_solution(id=1, block_height=100, ...)
        tracker.record_verification(solution_id=1, verifier='qbc1...', ...)
        record = tracker.get_solution(1)
        print(record.confidence)
    """

    def __init__(self, max_solutions: int = 10000):
        self._solutions: Dict[int, SolutionRecord] = {}
        self._by_block: Dict[int, int] = {}  # block_height -> solution_id
        self._by_miner: Dict[str, List[int]] = {}  # miner -> [solution_ids]
        self._max_solutions = max_solutions
        self._lock = threading.Lock()
        logger.info("Solution verification tracker initialized")

    def register_solution(
        self,
        solution_id: int,
        block_height: int,
        miner_address: str,
        original_energy: float,
    ) -> SolutionRecord:
        """Register a newly mined Hamiltonian solution for tracking."""
        with self._lock:
            if solution_id in self._solutions:
                return self._solutions[solution_id]

            # Evict oldest if at capacity
            if len(self._solutions) >= self._max_solutions:
                oldest_id = min(self._solutions.keys())
                old = self._solutions.pop(oldest_id)
                self._by_block.pop(old.block_height, None)
                miner_list = self._by_miner.get(old.miner_address, [])
                if oldest_id in miner_list:
                    miner_list.remove(oldest_id)

            record = SolutionRecord(
                solution_id=solution_id,
                block_height=block_height,
                miner_address=miner_address,
                original_energy=original_energy,
            )
            self._solutions[solution_id] = record
            self._by_block[block_height] = solution_id
            self._by_miner.setdefault(miner_address, []).append(solution_id)
            return record

    def record_verification(
        self,
        solution_id: int,
        verifier_address: str,
        verified_energy: float,
        energy_tolerance: float = 0.01,
    ) -> Optional[SolutionVerification]:
        """Record a verification attempt for a solution.

        Args:
            solution_id: The solution being verified.
            verifier_address: Address of the verifying node.
            verified_energy: Energy found by the verifier's VQE run.
            energy_tolerance: Max absolute difference to count as matching.

        Returns:
            The verification record, or None if solution_id not found.
        """
        with self._lock:
            record = self._solutions.get(solution_id)
            if record is None:
                return None

            # Check for duplicate verifier
            for v in record.verifications:
                if v.verifier_address == verifier_address:
                    logger.debug(f"Duplicate verification by {verifier_address} for solution {solution_id}")
                    return v

            matches = abs(verified_energy - record.original_energy) <= energy_tolerance
            verification = SolutionVerification(
                verifier_address=verifier_address,
                block_height=record.block_height,
                verified_energy=verified_energy,
                matches_original=matches,
            )
            record.verifications.append(verification)
            logger.debug(
                f"Solution {solution_id}: verification #{record.verification_count} "
                f"by {verifier_address} (match={matches})"
            )
            return verification

    def get_solution(self, solution_id: int) -> Optional[SolutionRecord]:
        """Get a solution record by ID."""
        with self._lock:
            return self._solutions.get(solution_id)

    def get_by_block(self, block_height: int) -> Optional[SolutionRecord]:
        """Get solution record by block height."""
        with self._lock:
            sid = self._by_block.get(block_height)
            if sid is None:
                return None
            return self._solutions.get(sid)

    def get_by_miner(self, miner_address: str) -> List[SolutionRecord]:
        """Get all solutions by a given miner."""
        with self._lock:
            ids = self._by_miner.get(miner_address, [])
            return [self._solutions[sid] for sid in ids if sid in self._solutions]

    def get_top_verified(self, limit: int = 10) -> List[SolutionRecord]:
        """Get solutions with the most verifications."""
        with self._lock:
            sorted_records = sorted(
                self._solutions.values(),
                key=lambda r: r.verification_count,
                reverse=True,
            )
            return sorted_records[:limit]

    def get_unverified(self, limit: int = 20) -> List[SolutionRecord]:
        """Get solutions that have zero verifications."""
        with self._lock:
            unverified = [
                r for r in self._solutions.values()
                if r.verification_count == 0
            ]
            # Sort by block height descending (newest first)
            unverified.sort(key=lambda r: r.block_height, reverse=True)
            return unverified[:limit]

    def get_stats(self) -> dict:
        """Aggregate statistics."""
        with self._lock:
            total = len(self._solutions)
            verified = sum(1 for r in self._solutions.values() if r.verification_count > 0)
            total_verifications = sum(r.verification_count for r in self._solutions.values())
            total_confirmed = sum(r.confirmed_count for r in self._solutions.values())
            avg_confidence = 0.0
            if verified > 0:
                avg_confidence = sum(
                    r.confidence for r in self._solutions.values() if r.verification_count > 0
                ) / verified
            unique_miners = len(self._by_miner)
            return {
                'total_solutions': total,
                'verified_solutions': verified,
                'unverified_solutions': total - verified,
                'total_verifications': total_verifications,
                'total_confirmed': total_confirmed,
                'avg_confidence': round(avg_confidence, 4),
                'unique_miners': unique_miners,
            }
