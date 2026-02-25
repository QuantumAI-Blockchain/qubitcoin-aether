"""
Bridge Liquidity Pool — LP Rewards for Bridge Depth

Tracks liquidity provider (LP) positions across bridge chains and
distributes proportional QBC rewards to incentivize deep liquidity.

Reward mechanism:
  1. Provider deposits QBC into a chain-specific liquidity pool
  2. Rewards accrue based on share of pool and time staked
  3. On withdrawal, proportional rewards are included
  4. Periodic distribution processes pending rewards

Configuration:
  - BRIDGE_LP_REWARD_RATE_BPS: Annual reward rate in basis points (default 500 = 5% APY)
  - BRIDGE_LP_MIN_DEPOSIT: Minimum deposit amount (default 10.0 QBC)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Seconds in a year (365.25 days)
SECONDS_PER_YEAR: float = 365.25 * 24 * 3600


@dataclass
class LPPosition:
    """A single liquidity provider position in a chain pool."""
    provider: str
    chain: str
    amount: float
    deposit_timestamp: float
    last_reward_timestamp: float
    accumulated_rewards: float = 0.0


@dataclass
class RewardDistribution:
    """Record of a reward distribution event."""
    provider: str
    chain: str
    reward_amount: float
    pool_share: float
    timestamp: float


class BridgeLiquidityPool:
    """Manages LP positions and reward distribution for bridge liquidity.

    Providers deposit QBC into chain-specific pools. Rewards accrue
    proportionally based on:
      - Provider's share of the total pool for that chain
      - Time elapsed since last reward calculation
      - Annual reward rate (BRIDGE_LP_REWARD_RATE_BPS)

    Usage:
        pool = BridgeLiquidityPool()
        pool.add_liquidity("qbc1abc...", "ethereum", 100.0)
        rewards = pool.calculate_rewards("qbc1abc...")
        pool.distribute_rewards()
        pool.remove_liquidity("qbc1abc...", "ethereum", 50.0)
    """

    def __init__(
        self,
        reward_rate_bps: Optional[int] = None,
        min_deposit: Optional[float] = None,
    ) -> None:
        """
        Args:
            reward_rate_bps: Annual reward rate in basis points.
                Defaults to Config.BRIDGE_LP_REWARD_RATE_BPS (500 = 5%).
            min_deposit: Minimum deposit amount in QBC.
                Defaults to Config.BRIDGE_LP_MIN_DEPOSIT (10.0).
        """
        self.reward_rate_bps: int = (
            reward_rate_bps
            if reward_rate_bps is not None
            else int(getattr(Config, 'BRIDGE_LP_REWARD_RATE_BPS', 500))
        )
        self.min_deposit: float = (
            min_deposit
            if min_deposit is not None
            else float(getattr(Config, 'BRIDGE_LP_MIN_DEPOSIT', 10.0))
        )

        # (provider, chain) -> LPPosition
        self._positions: Dict[Tuple[str, str], LPPosition] = {}

        # chain -> total liquidity in that chain's pool
        self._pool_totals: Dict[str, float] = {}

        # History of reward distributions
        self._distributions: List[RewardDistribution] = []

        # Total rewards distributed ever
        self._total_rewards_distributed: float = 0.0

        logger.info(
            "BridgeLiquidityPool initialized "
            f"(reward_rate={self.reward_rate_bps} bps, "
            f"min_deposit={self.min_deposit} QBC)"
        )

    def add_liquidity(self, provider: str, chain: str, amount: float) -> LPPosition:
        """Add liquidity to a chain-specific pool.

        If the provider already has a position in this chain, the amount
        is added to the existing position and pending rewards are first
        calculated and accumulated.

        Args:
            provider: Provider address.
            chain: Target chain name (e.g. 'ethereum', 'polygon').
            amount: QBC amount to deposit.

        Returns:
            The updated LPPosition.

        Raises:
            ValueError: If amount is below minimum deposit or non-positive.
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        normalized_provider = provider.lower().strip()
        normalized_chain = chain.lower().strip()
        key = (normalized_provider, normalized_chain)

        existing = self._positions.get(key)
        now = time.time()

        if existing is not None:
            # Settle pending rewards before updating position
            self._accrue_rewards_for_position(existing, now)

            existing.amount += amount
            existing.last_reward_timestamp = now

            self._pool_totals[normalized_chain] = (
                self._pool_totals.get(normalized_chain, 0.0) + amount
            )

            logger.info(
                f"LP added to existing position: provider={normalized_provider[:16]}... "
                f"chain={normalized_chain} +{amount} QBC "
                f"(total={existing.amount})"
            )
            return existing

        # New position — enforce minimum deposit
        if amount < self.min_deposit:
            raise ValueError(
                f"Deposit {amount} QBC is below minimum of "
                f"{self.min_deposit} QBC"
            )

        position = LPPosition(
            provider=normalized_provider,
            chain=normalized_chain,
            amount=amount,
            deposit_timestamp=now,
            last_reward_timestamp=now,
        )
        self._positions[key] = position
        self._pool_totals[normalized_chain] = (
            self._pool_totals.get(normalized_chain, 0.0) + amount
        )

        logger.info(
            f"LP new position: provider={normalized_provider[:16]}... "
            f"chain={normalized_chain} {amount} QBC"
        )
        return position

    def remove_liquidity(
        self, provider: str, chain: str, amount: float
    ) -> Tuple[float, float]:
        """Remove liquidity from a chain pool and collect proportional rewards.

        Before removing, pending rewards are accrued. The provider receives
        their withdrawn amount plus accumulated rewards.

        Args:
            provider: Provider address.
            chain: Target chain name.
            amount: QBC amount to withdraw.

        Returns:
            Tuple of (withdrawn_amount, rewards_collected).

        Raises:
            ValueError: If no position exists, amount exceeds position,
                or amount is non-positive.
        """
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        normalized_provider = provider.lower().strip()
        normalized_chain = chain.lower().strip()
        key = (normalized_provider, normalized_chain)

        position = self._positions.get(key)
        if position is None:
            raise ValueError(
                f"No LP position found for {normalized_provider} "
                f"on {normalized_chain}"
            )

        if amount > position.amount:
            raise ValueError(
                f"Withdrawal amount {amount} exceeds position "
                f"balance {position.amount}"
            )

        now = time.time()

        # Accrue pending rewards before withdrawal
        self._accrue_rewards_for_position(position, now)

        # Calculate proportional rewards to collect
        # If withdrawing everything, take all accumulated rewards
        if amount >= position.amount:
            rewards = position.accumulated_rewards
            position.accumulated_rewards = 0.0
            position.amount = 0.0
            # Remove empty position
            del self._positions[key]
        else:
            # Proportional reward withdrawal
            proportion = amount / position.amount
            rewards = position.accumulated_rewards * proportion
            position.accumulated_rewards -= rewards
            position.amount -= amount
            position.last_reward_timestamp = now

        # Update pool total
        self._pool_totals[normalized_chain] = max(
            0.0, self._pool_totals.get(normalized_chain, 0.0) - amount
        )

        logger.info(
            f"LP withdrawal: provider={normalized_provider[:16]}... "
            f"chain={normalized_chain} -{amount} QBC, "
            f"rewards={rewards:.6f} QBC"
        )

        return (amount, rewards)

    def calculate_rewards(self, provider: str) -> Dict[str, float]:
        """Calculate pending + accumulated rewards for a provider across all chains.

        This does NOT modify state — it is a read-only calculation.

        Args:
            provider: Provider address.

        Returns:
            Dict mapping chain name to total reward amount (accumulated +
            pending since last accrual).
        """
        normalized = provider.lower().strip()
        now = time.time()
        rewards: Dict[str, float] = {}

        for (p, chain), position in self._positions.items():
            if p != normalized:
                continue

            # Calculate pending (unaccrued) rewards
            pending = self._calculate_pending_rewards(position, now)
            total = position.accumulated_rewards + pending
            if total > 0:
                rewards[chain] = round(total, 8)

        return rewards

    def distribute_rewards(self) -> int:
        """Process pending rewards for all LP positions.

        Iterates through all positions, calculates time-weighted rewards,
        and adds them to accumulated_rewards. Records distribution events.

        Returns:
            Number of positions that received rewards.
        """
        now = time.time()
        distributed_count = 0

        for key, position in self._positions.items():
            pending = self._calculate_pending_rewards(position, now)
            if pending > 0:
                position.accumulated_rewards += pending
                position.last_reward_timestamp = now

                pool_total = self._pool_totals.get(position.chain, 0.0)
                share = position.amount / pool_total if pool_total > 0 else 0.0

                dist = RewardDistribution(
                    provider=position.provider,
                    chain=position.chain,
                    reward_amount=pending,
                    pool_share=share,
                    timestamp=now,
                )
                self._distributions.append(dist)
                self._total_rewards_distributed += pending
                distributed_count += 1

        # Cap distribution history
        if len(self._distributions) > 10000:
            self._distributions = self._distributions[-10000:]

        if distributed_count > 0:
            logger.info(
                f"LP rewards distributed to {distributed_count} positions"
            )

        return distributed_count

    def get_pool_stats(self) -> Dict:
        """Get overall liquidity pool statistics.

        Returns:
            Dict with total liquidity, provider count, pool breakdown
            by chain, reward rate, and APY.
        """
        total_liquidity = sum(self._pool_totals.values())
        unique_providers = set(p for (p, _) in self._positions.keys())

        # Per-chain breakdown
        chain_stats: Dict[str, Dict] = {}
        for chain, total in self._pool_totals.items():
            providers_in_chain = [
                pos for (_, c), pos in self._positions.items()
                if c == chain
            ]
            chain_stats[chain] = {
                'total_liquidity': round(total, 8),
                'provider_count': len(providers_in_chain),
            }

        apy_percent = self.reward_rate_bps / 100.0  # bps to percent

        return {
            'total_liquidity': round(total_liquidity, 8),
            'total_providers': len(unique_providers),
            'total_positions': len(self._positions),
            'reward_rate_bps': self.reward_rate_bps,
            'apy_percent': apy_percent,
            'min_deposit': self.min_deposit,
            'total_rewards_distributed': round(self._total_rewards_distributed, 8),
            'distribution_events': len(self._distributions),
            'chains': chain_stats,
            'recent_distributions': [
                {
                    'provider': d.provider,
                    'chain': d.chain,
                    'reward_amount': round(d.reward_amount, 8),
                    'pool_share': round(d.pool_share, 4),
                    'timestamp': d.timestamp,
                }
                for d in self._distributions[-10:]
            ],
        }

    def get_provider_positions(self, provider: str) -> List[Dict]:
        """Get all LP positions for a given provider.

        Args:
            provider: Provider address.

        Returns:
            List of position dicts with chain, amount, rewards, etc.
        """
        normalized = provider.lower().strip()
        now = time.time()
        positions = []

        for (p, chain), position in self._positions.items():
            if p != normalized:
                continue
            pending = self._calculate_pending_rewards(position, now)
            pool_total = self._pool_totals.get(chain, 0.0)
            share = position.amount / pool_total if pool_total > 0 else 0.0
            positions.append({
                'chain': chain,
                'amount': round(position.amount, 8),
                'accumulated_rewards': round(position.accumulated_rewards, 8),
                'pending_rewards': round(pending, 8),
                'total_rewards': round(position.accumulated_rewards + pending, 8),
                'pool_share': round(share, 6),
                'deposit_timestamp': position.deposit_timestamp,
                'last_reward_timestamp': position.last_reward_timestamp,
            })

        return positions

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _calculate_pending_rewards(
        self, position: LPPosition, now: float
    ) -> float:
        """Calculate pending (unaccrued) rewards for a position.

        Reward formula:
            reward = amount * (rate_bps / 10000) * (elapsed / seconds_per_year)

        Args:
            position: The LP position.
            now: Current timestamp.

        Returns:
            Pending reward amount in QBC.
        """
        elapsed = now - position.last_reward_timestamp
        if elapsed <= 0 or position.amount <= 0:
            return 0.0

        annual_rate = self.reward_rate_bps / 10000.0
        reward = position.amount * annual_rate * (elapsed / SECONDS_PER_YEAR)
        return reward

    def _accrue_rewards_for_position(
        self, position: LPPosition, now: float
    ) -> float:
        """Accrue pending rewards into the position's accumulated_rewards.

        Args:
            position: The LP position to update.
            now: Current timestamp.

        Returns:
            Amount of newly accrued rewards.
        """
        pending = self._calculate_pending_rewards(position, now)
        if pending > 0:
            position.accumulated_rewards += pending
            position.last_reward_timestamp = now
        return pending
