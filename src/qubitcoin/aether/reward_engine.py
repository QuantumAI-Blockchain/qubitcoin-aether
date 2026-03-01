"""
AIKGS Reward Engine — Calculates QBC rewards for knowledge contributions.

Reward formula:
  base_reward * quality * novelty_bonus * tier_multiplier * streak_multiplier
  * staking_boost * early_contributor_bonus

All parameters are configurable via Config (.env).
"""
import time
from dataclasses import dataclass
from typing import Dict, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


# Tier multipliers
TIER_MULTIPLIERS = {
    'bronze': 0.5,
    'silver': 1.0,
    'gold': 2.0,
    'diamond': 5.0,
}

# Streak multipliers (days => multiplier)
STREAK_MULTIPLIERS = [
    (100, 2.0),
    (30, 1.5),
    (7, 1.3),
    (3, 1.1),
    (0, 1.0),
]

# Staking boost thresholds (staked QBC => multiplier)
STAKING_BOOSTS = [
    (10000, 1.5),
    (1000, 1.3),
    (100, 1.1),
    (0, 1.0),
]


@dataclass
class RewardCalculation:
    """Breakdown of a reward calculation."""
    base_reward: float
    quality_factor: float
    novelty_factor: float
    tier_multiplier: float
    streak_multiplier: float
    staking_boost: float
    early_bonus: float
    final_reward: float

    def to_dict(self) -> dict:
        return {
            'base_reward': round(self.base_reward, 8),
            'quality_factor': round(self.quality_factor, 4),
            'novelty_factor': round(self.novelty_factor, 4),
            'tier_multiplier': round(self.tier_multiplier, 4),
            'streak_multiplier': round(self.streak_multiplier, 4),
            'staking_boost': round(self.staking_boost, 4),
            'early_bonus': round(self.early_bonus, 4),
            'final_reward': round(self.final_reward, 8),
        }


class RewardEngine:
    """Calculates and tracks QBC rewards for contributions."""

    def __init__(self) -> None:
        # Configurable base reward
        self._base_reward = float(getattr(Config, 'AIKGS_BASE_REWARD_QBC', 10.0))
        self._max_reward = float(getattr(Config, 'AIKGS_MAX_REWARD_QBC', 500.0))

        # Pool tracking
        self._pool_balance: float = float(getattr(Config, 'AIKGS_INITIAL_POOL_QBC', 1000000.0))
        self._total_distributed: float = 0.0
        self._distribution_count: int = 0

        # Per-contributor streaks
        self._streaks: Dict[str, int] = {}           # address => streak days
        self._last_contribution_day: Dict[str, int] = {}  # address => day number

        # Early contributor tracking
        self._total_contributions: int = 0
        self._early_threshold = int(getattr(Config, 'AIKGS_EARLY_THRESHOLD', 10000))
        self._early_max_bonus = float(getattr(Config, 'AIKGS_EARLY_MAX_BONUS', 5.0))

    def calculate_reward(self, quality_score: float, novelty_score: float,
                         tier: str, contributor_address: str,
                         staked_amount: float = 0.0) -> float:
        """Calculate reward for a contribution.

        Returns:
            Reward amount in QBC.
        """
        calc = self.calculate_reward_breakdown(
            quality_score, novelty_score, tier,
            contributor_address, staked_amount,
        )
        return calc.final_reward

    def calculate_reward_breakdown(self, quality_score: float, novelty_score: float,
                                   tier: str, contributor_address: str,
                                   staked_amount: float = 0.0) -> RewardCalculation:
        """Calculate reward with full breakdown."""
        # 1. Base reward
        base = self._base_reward

        # 2. Quality factor (0-1)
        quality_factor = max(0.0, min(1.0, quality_score))

        # 3. Novelty bonus: +50% max for fully novel content
        novelty_factor = 1.0 + (max(0.0, min(1.0, novelty_score)) * 0.5)

        # 4. Tier multiplier
        tier_mult = TIER_MULTIPLIERS.get(tier, 1.0)

        # 5. Streak multiplier
        streak_mult = self._get_streak_multiplier(contributor_address)

        # 6. Staking boost
        staking_boost = 1.0
        for threshold, mult in STAKING_BOOSTS:
            if staked_amount >= threshold:
                staking_boost = mult
                break

        # 7. Early contributor bonus (decays linearly)
        early_bonus = 1.0
        if self._total_contributions < self._early_threshold:
            decay = (self._early_threshold - self._total_contributions) / self._early_threshold
            early_bonus = 1.0 + (self._early_max_bonus - 1.0) * decay

        # Final calculation
        reward = (base * quality_factor * novelty_factor * tier_mult
                  * streak_mult * staking_boost * early_bonus)

        # Clamp to max
        reward = min(reward, self._max_reward)

        # Check pool balance
        if reward > self._pool_balance:
            reward = self._pool_balance
            if reward <= 0:
                logger.warning("Reward pool depleted!")

        # Update tracking
        self._pool_balance -= reward
        self._total_distributed += reward
        self._distribution_count += 1
        self._total_contributions += 1

        # Update streak
        self._update_streak(contributor_address)

        return RewardCalculation(
            base_reward=base,
            quality_factor=quality_factor,
            novelty_factor=novelty_factor,
            tier_multiplier=tier_mult,
            streak_multiplier=streak_mult,
            staking_boost=staking_boost,
            early_bonus=early_bonus,
            final_reward=round(reward, 8),
        )

    def _get_streak_multiplier(self, address: str) -> float:
        """Get the streak multiplier for an address."""
        streak = self._streaks.get(address, 0)
        for days, mult in STREAK_MULTIPLIERS:
            if streak >= days:
                return mult
        return 1.0

    def _update_streak(self, address: str) -> None:
        """Update the contribution streak for an address."""
        today = int(time.time() / 86400)
        last_day = self._last_contribution_day.get(address, 0)

        if last_day == 0 or today > last_day + 1:
            self._streaks[address] = 1
        elif today == last_day + 1:
            self._streaks[address] = self._streaks.get(address, 0) + 1
        # Same day: no streak change

        self._last_contribution_day[address] = today

    def fund_pool(self, amount: float) -> None:
        """Add QBC to the reward pool."""
        self._pool_balance += amount
        logger.info(f"Reward pool funded: +{amount:.4f} QBC (balance={self._pool_balance:.4f})")

    def get_contributor_streak(self, address: str) -> dict:
        """Get streak info for a contributor."""
        streak = self._streaks.get(address, 0)
        mult = self._get_streak_multiplier(address)
        return {
            'streak_days': streak,
            'multiplier': mult,
            'next_milestone': self._next_streak_milestone(streak),
        }

    @staticmethod
    def _next_streak_milestone(current: int) -> Optional[int]:
        """Get the next streak milestone."""
        milestones = [3, 7, 30, 100]
        for m in milestones:
            if current < m:
                return m
        return None

    def get_stats(self) -> dict:
        """Get reward engine statistics."""
        return {
            'pool_balance': round(self._pool_balance, 8),
            'total_distributed': round(self._total_distributed, 8),
            'distribution_count': self._distribution_count,
            'total_contributions': self._total_contributions,
            'base_reward': self._base_reward,
            'max_reward': self._max_reward,
            'early_threshold': self._early_threshold,
            'contributors_with_streaks': len(self._streaks),
        }
