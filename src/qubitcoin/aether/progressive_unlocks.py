"""
AIKGS Progressive Unlocks — Reputation-based feature unlocking.

Reputation points unlock features as contributors level up:
  Level 1 (0 RP):     Basic chat + contribute
  Level 2 (100 RP):   Custom theme + profile badge
  Level 3 (500 RP):   Priority queue for LLM responses
  Level 4 (1000 RP):  Curation voting rights
  Level 5 (2500 RP):  Governance voting
  Level 6 (5000 RP):  Create bounties
  Level 7 (10000 RP): Custom LLM adapter config
  Level 8 (25000 RP): Elite badge + early access to features

Reputation earned from:
  - Contributions: quality_score * tier_multiplier * 10
  - Curation: correct votes earn 5 RP
  - Bounty fulfillment: 50 RP
  - Streak milestones: 10-100 RP
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


# Level definitions: (min_rp, level_name, features_unlocked)
LEVELS = [
    (0,     1, 'Novice',      ['basic_chat', 'contribute']),
    (100,   2, 'Learner',     ['custom_theme', 'profile_badge']),
    (500,   3, 'Scholar',     ['priority_queue']),
    (1000,  4, 'Curator',     ['curation_voting']),
    (2500,  5, 'Sage',        ['governance_voting']),
    (5000,  6, 'Master',      ['create_bounties']),
    (10000, 7, 'Archon',      ['custom_llm_config']),
    (25000, 8, 'Enlightened', ['elite_badge', 'early_access']),
]

# Badge milestone triggers
BADGE_TRIGGERS = {
    'first_contribution': lambda stats: stats['total_contributions'] >= 1,
    'streak_3': lambda stats: stats['best_streak'] >= 3,
    'streak_7': lambda stats: stats['best_streak'] >= 7,
    'streak_30': lambda stats: stats['best_streak'] >= 30,
    'streak_100': lambda stats: stats['best_streak'] >= 100,
    'gold_contributor': lambda stats: stats['gold_count'] >= 10,
    'diamond_contributor': lambda stats: stats['diamond_count'] >= 1,
    'bounty_hunter': lambda stats: stats['bounties_fulfilled'] >= 10,
    'early_adopter': lambda stats: stats['contribution_rank'] <= 1000,
    'affiliate_leader': lambda stats: stats['referrals'] >= 50,
}

# Reputation rewards
RP_CONTRIBUTION_BASE = 10.0
RP_CURATION_CORRECT = 5.0
RP_BOUNTY_FULFILLMENT = 50.0
RP_STREAK_MILESTONES = {3: 10, 7: 25, 30: 50, 100: 100}

TIER_RP_MULTIPLIERS = {
    'bronze': 0.5,
    'silver': 1.0,
    'gold': 2.0,
    'diamond': 5.0,
}


@dataclass
class ContributorProfile:
    """Contributor's reputation and progress."""
    address: str
    reputation_points: float = 0.0
    level: int = 1
    level_name: str = 'Novice'
    total_contributions: int = 0
    best_streak: int = 0
    current_streak: int = 0
    gold_count: int = 0
    diamond_count: int = 0
    bounties_fulfilled: int = 0
    referrals: int = 0
    badges: List[str] = field(default_factory=list)
    unlocked_features: List[str] = field(default_factory=list)
    last_contribution_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'reputation_points': round(self.reputation_points, 2),
            'level': self.level,
            'level_name': self.level_name,
            'total_contributions': self.total_contributions,
            'best_streak': self.best_streak,
            'current_streak': self.current_streak,
            'gold_count': self.gold_count,
            'diamond_count': self.diamond_count,
            'bounties_fulfilled': self.bounties_fulfilled,
            'referrals': self.referrals,
            'badges': self.badges,
            'unlocked_features': self.unlocked_features,
            'last_contribution_at': self.last_contribution_at,
        }


class ProgressiveUnlocks:
    """Manages reputation-based feature unlocking."""

    def __init__(self) -> None:
        self._profiles: Dict[str, ContributorProfile] = {}
        self._global_contribution_count: int = 0

    def record_contribution(self, address: str, combined_score: float,
                            tier: str) -> List[str]:
        """Record a contribution and return any new badges earned.

        Args:
            address: Contributor address.
            combined_score: The contribution's combined quality+novelty score.
            tier: The quality tier.

        Returns:
            List of newly earned badge names.
        """
        profile = self._get_or_create(address)
        self._global_contribution_count += 1

        # Update stats
        profile.total_contributions += 1
        profile.last_contribution_at = time.time()

        if tier == 'gold':
            profile.gold_count += 1
        elif tier == 'diamond':
            profile.diamond_count += 1

        # Award reputation points
        tier_mult = TIER_RP_MULTIPLIERS.get(tier, 1.0)
        rp_earned = combined_score * RP_CONTRIBUTION_BASE * tier_mult
        profile.reputation_points += rp_earned

        # Update streak
        today = int(time.time() / 86400)
        last_day = int(profile.last_contribution_at / 86400) if profile.last_contribution_at else 0
        if last_day > 0 and today == last_day + 1:
            profile.current_streak += 1
        elif last_day == 0 or today > last_day + 1:
            profile.current_streak = 1
        # Same day: no change

        if profile.current_streak > profile.best_streak:
            profile.best_streak = profile.current_streak
            # Streak milestone RP
            for milestone, rp in RP_STREAK_MILESTONES.items():
                if profile.best_streak == milestone:
                    profile.reputation_points += rp

        # Update level
        self._update_level(profile)

        # Check for new badges
        new_badges = self._check_badges(profile)

        return new_badges

    def record_curation(self, address: str, correct: bool) -> None:
        """Record a curation vote result."""
        profile = self._get_or_create(address)
        if correct:
            profile.reputation_points += RP_CURATION_CORRECT
        self._update_level(profile)

    def record_bounty_fulfillment(self, address: str) -> None:
        """Record a bounty fulfillment."""
        profile = self._get_or_create(address)
        profile.bounties_fulfilled += 1
        profile.reputation_points += RP_BOUNTY_FULFILLMENT
        self._update_level(profile)

    def record_referral(self, address: str) -> None:
        """Record a new referral."""
        profile = self._get_or_create(address)
        profile.referrals += 1

    def has_feature(self, address: str, feature: str) -> bool:
        """Check if a contributor has unlocked a feature."""
        profile = self._profiles.get(address)
        if not profile:
            return feature in ['basic_chat', 'contribute']
        return feature in profile.unlocked_features

    def get_profile(self, address: str) -> ContributorProfile:
        """Get or create a contributor profile."""
        return self._get_or_create(address)

    def get_leaderboard(self, limit: int = 50) -> List[dict]:
        """Get top contributors by reputation."""
        ranked = sorted(
            self._profiles.values(),
            key=lambda p: p.reputation_points,
            reverse=True,
        )
        return [p.to_dict() for p in ranked[:limit]]

    def _get_or_create(self, address: str) -> ContributorProfile:
        """Get or create a profile."""
        if address not in self._profiles:
            profile = ContributorProfile(address=address)
            profile.unlocked_features = ['basic_chat', 'contribute']
            self._profiles[address] = profile
        return self._profiles[address]

    def _update_level(self, profile: ContributorProfile) -> None:
        """Update contributor level based on reputation."""
        rp = profile.reputation_points
        new_level = 1
        new_name = 'Novice'
        features: List[str] = []

        for min_rp, level, name, level_features in LEVELS:
            if rp >= min_rp:
                new_level = level
                new_name = name
                features.extend(level_features)

        profile.level = new_level
        profile.level_name = new_name
        profile.unlocked_features = features

    def _check_badges(self, profile: ContributorProfile) -> List[str]:
        """Check and award any new badges."""
        stats = {
            'total_contributions': profile.total_contributions,
            'best_streak': profile.best_streak,
            'gold_count': profile.gold_count,
            'diamond_count': profile.diamond_count,
            'bounties_fulfilled': profile.bounties_fulfilled,
            'referrals': profile.referrals,
            'contribution_rank': self._global_contribution_count,
        }

        new_badges: List[str] = []
        for badge_name, check_fn in BADGE_TRIGGERS.items():
            if badge_name not in profile.badges:
                try:
                    if check_fn(stats):
                        profile.badges.append(badge_name)
                        new_badges.append(badge_name)
                        logger.info(f"Badge earned: {badge_name} by {profile.address[:8]}...")
                except Exception:
                    pass

        return new_badges

    def get_stats(self) -> dict:
        """Get progressive unlock statistics."""
        level_distribution: Dict[int, int] = {}
        for p in self._profiles.values():
            level_distribution[p.level] = level_distribution.get(p.level, 0) + 1

        return {
            'total_profiles': len(self._profiles),
            'global_contributions': self._global_contribution_count,
            'level_distribution': level_distribution,
            'total_badges_awarded': sum(len(p.badges) for p in self._profiles.values()),
        }
