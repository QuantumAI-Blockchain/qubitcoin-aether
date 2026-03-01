"""
AIKGS Curation Engine — Peer review for Gold/Diamond contributions.

Gold and Diamond tier contributions go through curation:
  - 3 curators assigned per contribution
  - 2/3 consensus required for approval
  - Curators stake reputation; correct curation earns reputation points
  - Incorrect curation (minority vote) loses reputation points
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CurationReview:
    """A single curator's review."""
    curator_address: str
    contribution_id: int
    vote: bool            # True=approve, False=reject
    comment: str = ''
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            'curator_address': self.curator_address,
            'contribution_id': self.contribution_id,
            'vote': self.vote,
            'comment': self.comment,
            'timestamp': self.timestamp,
        }


@dataclass
class CurationRound:
    """A curation round for a contribution."""
    contribution_id: int
    required_votes: int = 3
    reviews: List[CurationReview] = field(default_factory=list)
    status: str = 'pending'  # pending, approved, rejected
    finalized_at: float = 0.0

    @property
    def votes_for(self) -> int:
        return sum(1 for r in self.reviews if r.vote)

    @property
    def votes_against(self) -> int:
        return sum(1 for r in self.reviews if not r.vote)

    @property
    def is_complete(self) -> bool:
        return len(self.reviews) >= self.required_votes

    def to_dict(self) -> dict:
        return {
            'contribution_id': self.contribution_id,
            'required_votes': self.required_votes,
            'votes_for': self.votes_for,
            'votes_against': self.votes_against,
            'reviews': [r.to_dict() for r in self.reviews],
            'status': self.status,
            'finalized_at': self.finalized_at,
        }


class CurationEngine:
    """Peer review engine for high-quality contributions."""

    # Maximum stored rounds to prevent unbounded memory growth
    MAX_ROUNDS = 5000
    # Minimum curator reputation to submit reviews (H4 fix)
    MIN_CURATOR_REPUTATION = 50.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rounds: Dict[int, CurationRound] = {}  # contribution_id => round
        self._curator_reputation: Dict[str, float] = {}  # address => reputation
        self._curator_reviews: Dict[str, List[int]] = {}  # address => [contribution_ids]
        self._required_votes: int = 3
        self._consensus_threshold: float = 2 / 3  # 66.7%
        self._reputation_reward: float = 10.0
        self._reputation_penalty: float = 5.0

    def submit_for_curation(self, contribution_id: int) -> CurationRound:
        """Submit a contribution for peer review."""
        with self._lock:
            if contribution_id in self._rounds:
                return self._rounds[contribution_id]

            round_ = CurationRound(
                contribution_id=contribution_id,
                required_votes=self._required_votes,
            )
            self._rounds[contribution_id] = round_

            # Evict finalized rounds if over limit
            if len(self._rounds) > self.MAX_ROUNDS:
                self._evict_finalized()

            logger.info(f"Contribution {contribution_id} submitted for curation")
            return round_

    def submit_review(self, contribution_id: int, curator_address: str,
                      vote: bool, comment: str = '') -> Optional[CurationRound]:
        """Submit a curation review.

        Args:
            contribution_id: The contribution being reviewed.
            curator_address: The curator's address.
            vote: True=approve, False=reject.
            comment: Optional review comment.

        Returns:
            Updated CurationRound, or None if invalid.

        Raises:
            PermissionError: If curator reputation is below threshold.
        """
        with self._lock:
            round_ = self._rounds.get(contribution_id)
            if not round_ or round_.status != 'pending':
                return None

            # H4 FIX: Permission check — curator must have sufficient reputation
            curator_rep = self._curator_reputation.get(curator_address, 100.0)
            if curator_rep < self.MIN_CURATOR_REPUTATION:
                raise PermissionError(
                    f"Curator reputation {curator_rep:.1f} below minimum {self.MIN_CURATOR_REPUTATION}"
                )

            # Prevent duplicate reviews
            for r in round_.reviews:
                if r.curator_address == curator_address:
                    logger.warning(f"Duplicate curation review: curator={curator_address[:8]}... contribution={contribution_id}")
                    return round_

            review = CurationReview(
                curator_address=curator_address,
                contribution_id=contribution_id,
                vote=vote,
                comment=comment,
                timestamp=time.time(),
            )
            round_.reviews.append(review)

            # Track curator activity
            if curator_address not in self._curator_reviews:
                self._curator_reviews[curator_address] = []
            self._curator_reviews[curator_address].append(contribution_id)

            # Check if round is complete
            if round_.is_complete:
                self._finalize_round(round_)

            return round_

    def _evict_finalized(self) -> None:
        """Remove finalized rounds to bound memory. Must hold self._lock."""
        evictable = [
            cid for cid, r in self._rounds.items()
            if r.status != 'pending'
        ]
        for cid in evictable[:len(self._rounds) - self.MAX_ROUNDS]:
            self._rounds.pop(cid, None)

    def _finalize_round(self, round_: CurationRound) -> None:
        """Finalize a completed curation round."""
        round_.finalized_at = time.time()

        # Determine outcome
        approval_rate = round_.votes_for / len(round_.reviews) if round_.reviews else 0
        round_.status = 'approved' if approval_rate >= self._consensus_threshold else 'rejected'

        # Distribute reputation
        is_approved = round_.status == 'approved'
        for review in round_.reviews:
            was_correct = (review.vote == is_approved)
            if was_correct:
                self._add_reputation(review.curator_address, self._reputation_reward)
            else:
                self._add_reputation(review.curator_address, -self._reputation_penalty)

        logger.info(
            f"Curation finalized: contribution={round_.contribution_id} "
            f"status={round_.status} votes={round_.votes_for}/{len(round_.reviews)}"
        )

    def _add_reputation(self, address: str, amount: float) -> None:
        """Adjust curator reputation."""
        current = self._curator_reputation.get(address, 100.0)
        self._curator_reputation[address] = max(0.0, current + amount)

    def get_curator_reputation(self, address: str) -> float:
        """Get curator reputation score."""
        return self._curator_reputation.get(address, 100.0)

    def get_pending_reviews(self, curator_address: Optional[str] = None) -> List[CurationRound]:
        """Get pending curation rounds, optionally excluding already-reviewed."""
        pending = [r for r in self._rounds.values() if r.status == 'pending']
        if curator_address:
            pending = [
                r for r in pending
                if not any(rev.curator_address == curator_address for rev in r.reviews)
            ]
        return pending

    def get_round(self, contribution_id: int) -> Optional[CurationRound]:
        """Get a curation round by contribution ID."""
        return self._rounds.get(contribution_id)

    def get_curator_stats(self, address: str) -> dict:
        """Get curator performance stats."""
        reviewed = self._curator_reviews.get(address, [])
        correct = 0
        total = 0
        for cid in reviewed:
            round_ = self._rounds.get(cid)
            if round_ and round_.status != 'pending':
                total += 1
                for review in round_.reviews:
                    if review.curator_address == address:
                        was_correct = (review.vote == (round_.status == 'approved'))
                        if was_correct:
                            correct += 1
                        break

        return {
            'address': address,
            'reputation': self.get_curator_reputation(address),
            'total_reviews': len(reviewed),
            'correct_votes': correct,
            'accuracy': round(correct / total, 4) if total > 0 else 0.0,
        }

    def get_stats(self) -> dict:
        """Get curation engine statistics."""
        status_counts: Dict[str, int] = {}
        for r in self._rounds.values():
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

        return {
            'total_rounds': len(self._rounds),
            'status_distribution': status_counts,
            'total_curators': len(self._curator_reputation),
            'avg_reputation': round(
                sum(self._curator_reputation.values()) / len(self._curator_reputation), 2
            ) if self._curator_reputation else 0.0,
        }
