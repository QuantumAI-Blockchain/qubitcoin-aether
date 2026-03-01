"""
AIKGS Bounty Manager — Knowledge gap bounties and seasonal events.

Auto-generates bounties for knowledge gaps detected by the reasoning engine.
Supports seasonal events with time-limited domain boosts.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Bounty:
    """A knowledge gap bounty."""
    bounty_id: int
    domain: str
    description: str
    gap_hash: str
    reward_amount: float
    boost_multiplier: float = 1.0
    status: str = 'open'      # open, claimed, fulfilled, expired, canceled
    claimer_address: Optional[str] = None
    contribution_id: Optional[int] = None
    created_at: float = 0.0
    expires_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            'bounty_id': self.bounty_id,
            'domain': self.domain,
            'description': self.description,
            'gap_hash': self.gap_hash,
            'reward_amount': round(self.reward_amount, 8),
            'boost_multiplier': self.boost_multiplier,
            'status': self.status,
            'claimer_address': self.claimer_address,
            'contribution_id': self.contribution_id,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
        }


@dataclass
class Season:
    """A seasonal knowledge event."""
    season_id: int
    name: str
    domain: str
    boost_multiplier: float
    starts_at: float
    ends_at: float
    active: bool = True

    def to_dict(self) -> dict:
        return {
            'season_id': self.season_id,
            'name': self.name,
            'domain': self.domain,
            'boost_multiplier': self.boost_multiplier,
            'starts_at': self.starts_at,
            'ends_at': self.ends_at,
            'active': self.active,
        }


class BountyManager:
    """Manages knowledge gap bounties and seasonal events."""

    def __init__(self) -> None:
        self._default_reward = float(getattr(Config, 'AIKGS_DEFAULT_BOUNTY_REWARD', 50.0))
        self._default_duration = int(getattr(Config, 'AIKGS_DEFAULT_BOUNTY_DURATION_DAYS', 7))

        self._bounties: Dict[int, Bounty] = {}
        self._bounty_counter: int = 0
        self._gap_hashes: set = set()  # Prevent duplicate bounties

        self._seasons: Dict[int, Season] = {}
        self._season_counter: int = 0
        self._active_domain_seasons: Dict[str, int] = {}  # domain => season_id

    def create_bounty(self, domain: str, description: str, gap_hash: str,
                      reward_amount: Optional[float] = None) -> Bounty:
        """Create a bounty for a knowledge gap.

        Args:
            domain: Knowledge domain.
            description: What knowledge is needed.
            gap_hash: Unique hash of the knowledge gap.
            reward_amount: QBC bounty (defaults to configured default).

        Returns:
            The created Bounty.
        """
        if gap_hash in self._gap_hashes:
            # Return existing bounty
            for b in self._bounties.values():
                if b.gap_hash == gap_hash and b.status == 'open':
                    return b
            self._gap_hashes.discard(gap_hash)  # Allow re-creation if expired

        self._bounty_counter += 1
        reward = reward_amount or self._default_reward
        now = time.time()

        # Check for active season boost
        boost = 1.0
        season_id = self._active_domain_seasons.get(domain)
        if season_id and season_id in self._seasons:
            season = self._seasons[season_id]
            if season.active and now <= season.ends_at:
                boost = season.boost_multiplier

        bounty = Bounty(
            bounty_id=self._bounty_counter,
            domain=domain,
            description=description,
            gap_hash=gap_hash,
            reward_amount=reward,
            boost_multiplier=boost,
            created_at=now,
            expires_at=now + (self._default_duration * 86400),
        )

        self._bounties[bounty.bounty_id] = bounty
        self._gap_hashes.add(gap_hash)

        logger.info(f"Bounty created: id={bounty.bounty_id} domain={domain} reward={reward:.4f} boost={boost}x")
        return bounty

    def claim_bounty(self, bounty_id: int, claimer_address: str) -> bool:
        """Claim an open bounty."""
        bounty = self._bounties.get(bounty_id)
        if not bounty or bounty.status != 'open':
            return False
        if time.time() > bounty.expires_at:
            bounty.status = 'expired'
            return False

        bounty.claimer_address = claimer_address
        bounty.status = 'claimed'
        logger.info(f"Bounty claimed: id={bounty_id} claimer={claimer_address[:8]}...")
        return True

    def fulfill_bounty(self, bounty_id: int, contribution_id: int,
                       contributor_address: str) -> Optional[float]:
        """Fulfill a bounty with a contribution.

        Returns:
            Boosted reward amount, or None if fulfillment failed.
        """
        bounty = self._bounties.get(bounty_id)
        if not bounty:
            return None
        if bounty.status not in ('open', 'claimed'):
            return None
        if bounty.status == 'claimed' and bounty.claimer_address != contributor_address:
            return None

        bounty.contribution_id = contribution_id
        bounty.claimer_address = contributor_address
        bounty.status = 'fulfilled'

        boosted = bounty.reward_amount * bounty.boost_multiplier
        logger.info(f"Bounty fulfilled: id={bounty_id} reward={boosted:.4f} QBC")
        return boosted

    def expire_stale_bounties(self) -> int:
        """Expire bounties past their deadline."""
        now = time.time()
        expired = 0
        for bounty in self._bounties.values():
            if bounty.status in ('open', 'claimed') and now > bounty.expires_at:
                bounty.status = 'expired'
                expired += 1
        return expired

    def start_season(self, name: str, domain: str, boost_multiplier: float,
                     duration_days: int) -> Season:
        """Start a seasonal knowledge event."""
        self._season_counter += 1
        now = time.time()

        season = Season(
            season_id=self._season_counter,
            name=name,
            domain=domain,
            boost_multiplier=boost_multiplier,
            starts_at=now,
            ends_at=now + (duration_days * 86400),
        )

        self._seasons[season.season_id] = season
        self._active_domain_seasons[domain] = season.season_id

        logger.info(f"Season started: {name} domain={domain} boost={boost_multiplier}x duration={duration_days}d")
        return season

    def end_season(self, season_id: int) -> bool:
        """End a season early."""
        season = self._seasons.get(season_id)
        if not season or not season.active:
            return False

        season.active = False
        season.ends_at = time.time()
        if self._active_domain_seasons.get(season.domain) == season_id:
            del self._active_domain_seasons[season.domain]

        logger.info(f"Season ended: {season.name}")
        return True

    def get_open_bounties(self, domain: Optional[str] = None, limit: int = 50) -> List[Bounty]:
        """Get open bounties, optionally filtered by domain."""
        bounties = [
            b for b in self._bounties.values()
            if b.status == 'open' and (not domain or b.domain == domain)
        ]
        bounties.sort(key=lambda b: b.reward_amount, reverse=True)
        return bounties[:limit]

    def get_active_seasons(self) -> List[Season]:
        """Get currently active seasons."""
        now = time.time()
        return [
            s for s in self._seasons.values()
            if s.active and now <= s.ends_at
        ]

    def get_stats(self) -> dict:
        """Get bounty system statistics."""
        status_counts: Dict[str, int] = {}
        total_rewards = 0.0
        for b in self._bounties.values():
            status_counts[b.status] = status_counts.get(b.status, 0) + 1
            total_rewards += b.reward_amount

        return {
            'total_bounties': len(self._bounties),
            'status_distribution': status_counts,
            'total_bounty_rewards': round(total_rewards, 8),
            'active_seasons': len([s for s in self._seasons.values() if s.active]),
            'total_seasons': len(self._seasons),
        }
