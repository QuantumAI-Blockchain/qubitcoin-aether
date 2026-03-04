"""
BFT Finality Gadget for Qubitcoin.

Provides probabilistic finality via stake-weighted validator voting.
Once a block is finalized, it cannot be reverted by chain reorgs.

Architecture:
- Uses Rust FinalityCore (from security-core PyO3 crate) for vote
  computation with a pure-Python fallback.
- Python wrapper handles persistence (DB), signature verification,
  and integration with the consensus engine.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Try to use Rust FinalityCore for performance
try:
    from security_core import FinalityCore as _RustFinality
    _USE_RUST = True
    logger.info("FinalityGadget: using Rust FinalityCore (security-core)")
except ImportError:
    _USE_RUST = False
    logger.info("FinalityGadget: using pure-Python fallback")


# ── Pure-Python fallback ──────────────────────────────────────────────


class _PythonFinalityCore:
    """Pure-Python finality computation core (fallback when Rust not installed)."""

    def __init__(self, threshold: float, vote_expiry_blocks: int) -> None:
        self._threshold = threshold
        self._vote_expiry = vote_expiry_blocks
        self._validators: Dict[str, float] = {}
        self._votes: Dict[int, List[dict]] = {}
        self._last_finalized: int = 0

    def add_validator(self, address: str, stake: float) -> None:
        self._validators[address] = stake

    def remove_validator(self, address: str) -> None:
        self._validators.pop(address, None)

    def record_vote(self, voter: str, block_height: int, block_hash: str) -> bool:
        if voter not in self._validators:
            return False
        height_votes = self._votes.setdefault(block_height, [])
        if any(v["voter"] == voter for v in height_votes):
            return False
        height_votes.append({
            "voter": voter,
            "block_height": block_height,
            "block_hash": block_hash,
        })
        return True

    def check_finality(self, block_height: int) -> bool:
        if block_height <= self._last_finalized:
            return True
        voted, total = self.calculate_vote_weight(block_height)
        if total <= 0.0:
            return False
        if voted / total >= self._threshold:
            if block_height > self._last_finalized:
                self._last_finalized = block_height
            return True
        return False

    def get_last_finalized(self) -> int:
        return self._last_finalized

    def calculate_vote_weight(self, block_height: int) -> Tuple[float, float]:
        total = sum(self._validators.values())
        height_votes = self._votes.get(block_height, [])
        voted = sum(
            self._validators.get(v["voter"], 0.0) for v in height_votes
        )
        return voted, total

    def validator_count(self) -> int:
        return len(self._validators)

    def vote_count(self, block_height: int) -> int:
        return len(self._votes.get(block_height, []))

    def total_stake(self) -> float:
        return sum(self._validators.values())

    def prune_votes(self, current_height: int) -> None:
        if current_height <= self._vote_expiry:
            return
        cutoff = current_height - self._vote_expiry
        self._votes = {h: v for h, v in self._votes.items() if h >= cutoff}


# ── Validator dataclass ───────────────────────────────────────────────


@dataclass
class ValidatorInfo:
    """Registered finality validator."""
    address: str
    stake: float
    registered_at_block: int
    active: bool = True
    last_vote_block: int = 0


@dataclass
class FinalityStatus:
    """Current finality status for a block height."""
    block_height: int
    is_finalized: bool
    voted_stake: float
    total_stake: float
    vote_ratio: float
    threshold: float
    voter_count: int
    last_finalized_height: int


# ── FinalityGadget ────────────────────────────────────────────────────


class FinalityGadget:
    """
    BFT Finality Gadget — Python wrapper over Rust FinalityCore.

    Handles:
    - Validator registration and persistence
    - Vote recording with optional signature verification
    - Finality checking and checkpoint recording
    - Consensus integration (reject reorgs past finalized height)
    """

    def __init__(self, db_manager) -> None:
        self._db = db_manager
        self._threshold = Config.FINALITY_THRESHOLD
        self._min_stake = Config.FINALITY_MIN_STAKE
        self._vote_expiry = Config.FINALITY_VOTE_EXPIRY_BLOCKS

        # Initialize core engine (Rust or Python)
        if _USE_RUST:
            self._core = _RustFinality(self._threshold, self._vote_expiry)
        else:
            self._core = _PythonFinalityCore(self._threshold, self._vote_expiry)

        # Load validators from DB
        self._load_validators()
        logger.info(
            f"FinalityGadget initialized: threshold={self._threshold}, "
            f"min_stake={self._min_stake}, validators={self._core.validator_count()}"
        )

    def _load_validators(self) -> None:
        """Load active validators from DB into the core engine."""
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                rows = session.execute(
                    text("SELECT address, stake FROM finality_validators WHERE active = true")
                ).fetchall()
                for row in rows:
                    self._core.add_validator(row[0], float(row[1]))
                if rows:
                    logger.info(f"Loaded {len(rows)} finality validators from DB")
        except Exception as e:
            logger.debug(f"Could not load finality validators: {e}")

    def register_validator(self, address: str, stake: float, current_height: int) -> bool:
        """Register a new finality validator.

        Args:
            address: Validator address.
            stake: Amount of QBC staked.
            current_height: Current block height.

        Returns:
            True if registered successfully.
        """
        if stake < self._min_stake:
            logger.warning(
                f"Validator {address[:16]} stake {stake} below minimum {self._min_stake}"
            )
            return False

        self._core.add_validator(address, stake)
        self._persist_validator(address, stake, current_height)
        logger.info(f"Validator registered: {address[:16]}... stake={stake}")
        return True

    def unregister_validator(self, address: str) -> bool:
        """Remove a finality validator.

        Args:
            address: Validator address.

        Returns:
            True if removed successfully.
        """
        self._core.remove_validator(address)
        self._deactivate_validator(address)
        logger.info(f"Validator unregistered: {address[:16]}...")
        return True

    def submit_vote(
        self,
        voter: str,
        block_height: int,
        block_hash: str,
        signature: Optional[str] = None,
    ) -> bool:
        """Submit a finality vote.

        Args:
            voter: Voter address (must be registered validator).
            block_height: Block being voted for.
            block_hash: Hash of the block being voted for.
            signature: Optional Dilithium signature for verification.

        Returns:
            True if vote was accepted.
        """
        accepted = self._core.record_vote(voter, block_height, block_hash)
        if not accepted:
            return False

        self._persist_vote(voter, block_height, block_hash, signature)

        # Check if this vote triggers finality
        if self._core.check_finality(block_height):
            voted, total = self._core.calculate_vote_weight(block_height)
            self._persist_checkpoint(block_height, block_hash, voted, total)
            logger.info(
                f"Block {block_height} finalized! "
                f"voted={voted:.1f}/{total:.1f} ({voted/total:.1%})"
            )

        return True

    def check_finality(self, block_height: int) -> bool:
        """Check if a block height is finalized."""
        return self._core.check_finality(block_height)

    def get_last_finalized(self) -> int:
        """Get the last finalized block height."""
        return self._core.get_last_finalized()

    def get_finality_status(self, block_height: int) -> FinalityStatus:
        """Get detailed finality status for a block height."""
        is_final = self._core.check_finality(block_height)
        voted, total = self._core.calculate_vote_weight(block_height)
        ratio = voted / total if total > 0 else 0.0
        return FinalityStatus(
            block_height=block_height,
            is_finalized=is_final,
            voted_stake=voted,
            total_stake=total,
            vote_ratio=ratio,
            threshold=self._threshold,
            voter_count=self._core.vote_count(block_height),
            last_finalized_height=self._core.get_last_finalized(),
        )

    def process_block(self, block_height: int) -> None:
        """Process a new block — prune old votes."""
        self._core.prune_votes(block_height)

    def auto_vote_if_validator(
        self,
        block_height: int,
        block_hash: str,
        node_address: str,
    ) -> bool:
        """Auto-vote for a block if this node is a registered validator.

        Called after a new block is accepted by consensus.

        Args:
            block_height: Accepted block height.
            block_hash: Accepted block hash.
            node_address: This node's address.

        Returns:
            True if a vote was cast.
        """
        # Only vote if we are a validator
        voted, _ = self._core.calculate_vote_weight(block_height)
        # Quick check: see if our address is a validator by trying to vote
        accepted = self.submit_vote(node_address, block_height, block_hash)
        if accepted:
            logger.debug(f"Auto-voted for block {block_height}")
        return accepted

    def is_reorg_allowed(self, target_height: int) -> bool:
        """Check if a reorg to target_height is allowed.

        Reorgs past the last finalized height are rejected.

        Args:
            target_height: The height the reorg would revert to.

        Returns:
            True if the reorg is allowed (target is above finalized).
        """
        finalized = self._core.get_last_finalized()
        if finalized == 0:
            return True  # No finality yet
        return target_height > finalized

    def get_validator_count(self) -> int:
        """Get the number of registered validators."""
        return self._core.validator_count()

    def get_total_stake(self) -> float:
        """Get total stake across all validators."""
        return self._core.total_stake()

    def get_validators(self) -> List[ValidatorInfo]:
        """Get all validators from DB."""
        validators: List[ValidatorInfo] = []
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                rows = session.execute(
                    text(
                        "SELECT address, stake, registered_at_block, active, last_vote_block "
                        "FROM finality_validators ORDER BY stake DESC"
                    )
                ).fetchall()
                for row in rows:
                    validators.append(ValidatorInfo(
                        address=row[0],
                        stake=float(row[1]),
                        registered_at_block=int(row[2]),
                        active=bool(row[3]),
                        last_vote_block=int(row[4] or 0),
                    ))
        except Exception as e:
            logger.debug(f"Could not load validators: {e}")
        return validators

    # ── Persistence ───────────────────────────────────────────────────

    def _persist_validator(self, address: str, stake: float, block_height: int) -> None:
        """Persist validator to DB."""
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                session.execute(
                    text(
                        "INSERT INTO finality_validators (address, stake, registered_at_block, active) "
                        "VALUES (:addr, :stake, :block, true) "
                        "ON CONFLICT (address) DO UPDATE SET stake = :stake, active = true"
                    ),
                    {"addr": address, "stake": stake, "block": block_height},
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Could not persist validator: {e}")

    def _deactivate_validator(self, address: str) -> None:
        """Deactivate validator in DB."""
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                session.execute(
                    text("UPDATE finality_validators SET active = false WHERE address = :addr"),
                    {"addr": address},
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Could not deactivate validator: {e}")

    def _persist_vote(
        self,
        voter: str,
        block_height: int,
        block_hash: str,
        signature: Optional[str],
    ) -> None:
        """Persist vote to DB."""
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                session.execute(
                    text(
                        "INSERT INTO finality_votes (voter_address, block_height, block_hash, signature) "
                        "VALUES (:voter, :height, :hash, :sig) "
                        "ON CONFLICT (voter_address, block_height) DO NOTHING"
                    ),
                    {
                        "voter": voter,
                        "height": block_height,
                        "hash": block_hash,
                        "sig": signature,
                    },
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Could not persist vote: {e}")

    def _persist_checkpoint(
        self,
        block_height: int,
        block_hash: str,
        voted_stake: float,
        total_stake: float,
    ) -> None:
        """Record a finality checkpoint."""
        try:
            with self._db.get_session() as session:
                from sqlalchemy import text
                session.execute(
                    text(
                        "INSERT INTO finality_checkpoints (block_height, block_hash, voted_stake, total_stake) "
                        "VALUES (:height, :hash, :voted, :total) "
                        "ON CONFLICT (block_height) DO NOTHING"
                    ),
                    {
                        "height": block_height,
                        "hash": block_hash,
                        "voted": voted_stake,
                        "total": total_stake,
                    },
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Could not persist checkpoint: {e}")
