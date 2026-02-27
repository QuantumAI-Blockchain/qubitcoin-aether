"""
Bridge LP Rewards — Liquidity Provider Reward System

Extends the base BridgeLiquidityPool with:
  - Per-block reward updates (called from node's block processing loop)
  - Claim interface that tracks cooldown blocks between claims
  - Provider and pool statistics reporting
  - Integration with Config for all economic parameters

Configuration (all in .env):
  BRIDGE_LP_REWARD_RATE           : QBC per block distributed to the LP pool
  BRIDGE_LP_REWARD_RATE_BPS       : Annual reward rate in basis points (500 = 5% APY)
  BRIDGE_LP_MIN_LIQUIDITY         : Minimum QBC to open an LP position
  BRIDGE_LP_REWARD_COOLDOWN_BLOCKS: Minimum blocks between reward claims
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger
from .liquidity_pool import (
    BridgeLiquidityPool,
    LPPosition,
    RewardDistribution,
    SECONDS_PER_YEAR,
)

logger = get_logger(__name__)


@dataclass
class ClaimRecord:
    """Record of a reward claim event."""
    provider: str
    amount: float
    block_height: int
    timestamp: float


class BridgeLPRewards:
    """Manages LP rewards for bridge liquidity providers.

    Wraps BridgeLiquidityPool with additional features:
      - Per-block reward distribution via update_rewards()
      - Claim cooldown enforcement (BRIDGE_LP_REWARD_COOLDOWN_BLOCKS)
      - Detailed provider and pool-level statistics

    Usage:
        rewards = BridgeLPRewards(config=Config)
        rewards.add_liquidity("qbc1abc...", "ethereum", 100.0)
        rewards.update_rewards(block_height=42)
        pending = rewards.calculate_rewards("qbc1abc...")
        claimed = rewards.claim_rewards("qbc1abc...")
    """

    def __init__(self, config: type = Config) -> None:
        """Initialize the LP rewards system.

        Args:
            config: Configuration class (defaults to Config). Must have
                BRIDGE_LP_REWARD_RATE, BRIDGE_LP_REWARD_RATE_BPS,
                BRIDGE_LP_MIN_LIQUIDITY, and BRIDGE_LP_REWARD_COOLDOWN_BLOCKS.
        """
        self.reward_rate_per_block: float = float(
            getattr(config, 'BRIDGE_LP_REWARD_RATE', 0.5)
        )
        self.cooldown_blocks: int = int(
            getattr(config, 'BRIDGE_LP_REWARD_COOLDOWN_BLOCKS', 100)
        )
        min_liquidity: float = float(
            getattr(config, 'BRIDGE_LP_MIN_LIQUIDITY', 10.0)
        )
        reward_rate_bps: int = int(
            getattr(config, 'BRIDGE_LP_REWARD_RATE_BPS', 500)
        )

        # Underlying pool engine
        self._pool = BridgeLiquidityPool(
            reward_rate_bps=reward_rate_bps,
            min_deposit=min_liquidity,
        )

        # Track last claim block per provider
        self._last_claim_block: Dict[str, int] = {}

        # Total QBC distributed from per-block rewards
        self._block_rewards_distributed: float = 0.0

        # Claim history
        self._claims: List[ClaimRecord] = []

        # Last block that called update_rewards
        self._last_update_block: int = 0

        # Total liquidity (delegate to pool but also expose)
        self.total_liquidity: float = 0.0

        logger.info(
            "BridgeLPRewards initialized "
            f"(per_block={self.reward_rate_per_block} QBC, "
            f"cooldown={self.cooldown_blocks} blocks, "
            f"min_liquidity={min_liquidity} QBC, "
            f"apy={reward_rate_bps / 100.0}%)"
        )

    # ========================================================================
    # LIQUIDITY MANAGEMENT
    # ========================================================================

    def add_liquidity(
        self, provider: str, chain: str, amount: float
    ) -> LPPosition:
        """Add liquidity to a chain-specific pool.

        Args:
            provider: Provider address.
            chain: Target chain name (e.g. 'ethereum', 'polygon').
            amount: QBC amount to deposit.

        Returns:
            The created or updated LPPosition.

        Raises:
            ValueError: If amount is non-positive or below minimum.
        """
        position = self._pool.add_liquidity(provider, chain, amount)
        self.total_liquidity = sum(self._pool._pool_totals.values())
        return position

    def remove_liquidity(
        self, provider: str, chain: str, amount: float
    ) -> float:
        """Remove liquidity from a chain pool.

        Accrues pending rewards before withdrawal. Returns the withdrawn
        amount. Proportional accumulated rewards remain on the position
        or are collected automatically on full withdrawal.

        Args:
            provider: Provider address.
            chain: Target chain name.
            amount: QBC amount to withdraw.

        Returns:
            The withdrawn QBC amount (principal only). Use claim_rewards
            to collect accumulated rewards separately, or remove the full
            position to auto-collect.

        Raises:
            ValueError: If no position, amount exceeds balance, or <= 0.
        """
        withdrawn, rewards = self._pool.remove_liquidity(provider, chain, amount)
        self.total_liquidity = sum(self._pool._pool_totals.values())
        return withdrawn

    # ========================================================================
    # REWARD CALCULATION AND CLAIMING
    # ========================================================================

    def calculate_rewards(self, provider: str) -> float:
        """Calculate total pending rewards for a provider across all chains.

        This is a read-only operation.

        Args:
            provider: Provider address.

        Returns:
            Total pending reward amount in QBC.
        """
        by_chain = self._pool.calculate_rewards(provider)
        return sum(by_chain.values())

    def claim_rewards(self, provider: str, block_height: int = 0) -> float:
        """Claim accumulated rewards for a provider.

        Distributes all pending rewards to the provider's positions, then
        collects accumulated_rewards from every position. Enforces cooldown
        period between claims.

        Args:
            provider: Provider address.
            block_height: Current block height (for cooldown enforcement).
                If 0, cooldown is not enforced.

        Returns:
            Total QBC claimed.

        Raises:
            ValueError: If provider has no positions or is in cooldown.
        """
        normalized = provider.lower().strip()

        # Enforce cooldown
        if block_height > 0 and self.cooldown_blocks > 0:
            last = self._last_claim_block.get(normalized, 0)
            if last > 0 and (block_height - last) < self.cooldown_blocks:
                remaining = self.cooldown_blocks - (block_height - last)
                raise ValueError(
                    f"Claim cooldown active: {remaining} blocks remaining"
                )

        # Distribute pending rewards first
        self._pool.distribute_rewards()

        # Collect accumulated rewards from all positions
        total_claimed: float = 0.0
        keys_to_check = [
            (p, c) for (p, c) in self._pool._positions
            if p == normalized
        ]

        if not keys_to_check:
            raise ValueError(f"No LP positions found for {normalized}")

        for key in keys_to_check:
            position = self._pool._positions.get(key)
            if position and position.accumulated_rewards > 0:
                total_claimed += position.accumulated_rewards
                position.accumulated_rewards = 0.0

        if block_height > 0:
            self._last_claim_block[normalized] = block_height

        if total_claimed > 0:
            self._claims.append(ClaimRecord(
                provider=normalized,
                amount=total_claimed,
                block_height=block_height,
                timestamp=time.time(),
            ))
            logger.info(
                f"LP rewards claimed: provider={normalized[:16]}... "
                f"amount={total_claimed:.8f} QBC at block {block_height}"
            )

        return total_claimed

    # ========================================================================
    # PER-BLOCK UPDATES
    # ========================================================================

    def update_rewards(self, block_height: int) -> None:
        """Called per block to distribute time-weighted rewards.

        Triggers the underlying pool's distribute_rewards() which accrues
        pending rewards based on elapsed time and position sizes. Also
        tracks per-block reward metrics.

        Args:
            block_height: Current block height.
        """
        if block_height <= self._last_update_block:
            return  # Already processed this block

        count = self._pool.distribute_rewards()
        self._last_update_block = block_height

        if count > 0:
            logger.debug(
                f"LP rewards updated at block {block_height}: "
                f"{count} positions processed"
            )

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_provider_stats(self, provider: str) -> dict:
        """Get detailed statistics for a specific provider.

        Args:
            provider: Provider address.

        Returns:
            Dict with positions, total staked, pending rewards,
            claim history, and cooldown status.
        """
        normalized = provider.lower().strip()
        positions = self._pool.get_provider_positions(normalized)

        total_staked = sum(p['amount'] for p in positions)
        total_pending = sum(
            p['accumulated_rewards'] + p['pending_rewards']
            for p in positions
        )
        total_claimed = sum(
            c.amount for c in self._claims if c.provider == normalized
        )

        last_claim_block = self._last_claim_block.get(normalized, 0)
        claim_history = [
            {
                'amount': c.amount,
                'block_height': c.block_height,
                'timestamp': c.timestamp,
            }
            for c in self._claims[-20:]
            if c.provider == normalized
        ]

        return {
            'provider': normalized,
            'positions': positions,
            'total_staked': round(total_staked, 8),
            'total_pending_rewards': round(total_pending, 8),
            'total_claimed': round(total_claimed, 8),
            'last_claim_block': last_claim_block,
            'cooldown_blocks': self.cooldown_blocks,
            'claim_history': claim_history,
        }

    def get_pool_stats(self, chain: Optional[str] = None) -> dict:
        """Get pool-level statistics.

        Args:
            chain: If provided, return stats for only that chain.
                If None, return aggregated stats for all chains.

        Returns:
            Dict with liquidity, providers, reward metrics, and
            per-chain breakdown.
        """
        base_stats = self._pool.get_pool_stats()

        # Add BridgeLPRewards-specific fields
        base_stats['reward_rate_per_block'] = self.reward_rate_per_block
        base_stats['cooldown_blocks'] = self.cooldown_blocks
        base_stats['last_update_block'] = self._last_update_block
        base_stats['total_claims'] = len(self._claims)
        base_stats['block_rewards_distributed'] = round(
            self._block_rewards_distributed, 8
        )

        recent_claims = [
            {
                'provider': c.provider,
                'amount': round(c.amount, 8),
                'block_height': c.block_height,
                'timestamp': c.timestamp,
            }
            for c in self._claims[-10:]
        ]
        base_stats['recent_claims'] = recent_claims

        if chain is not None:
            chain_key = chain.lower().strip()
            chain_info = base_stats.get('chains', {}).get(chain_key, {})
            return {
                'chain': chain_key,
                **chain_info,
                'reward_rate_bps': base_stats['reward_rate_bps'],
                'apy_percent': base_stats['apy_percent'],
            }

        return base_stats
