"""
QBC Circulation Tracker

Tracks QBC token circulation metrics per block. Ensures the AGI system
never mints new QBC — all QBC comes from mining rewards only.

Metrics tracked:
  - Total QBC in circulation (sum of all coinbase rewards)
  - Current mining era and reward
  - Halving events (phi-halving)
  - Emission schedule progress
  - Fee totals
"""
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CirculationSnapshot:
    """Circulation metrics at a specific block height."""
    block_height: int
    timestamp: float
    total_circulating: Decimal
    current_reward: Decimal
    current_era: int
    percent_emitted: float
    total_fees_collected: Decimal = Decimal('0')
    halving_event: bool = False

    def to_dict(self) -> dict:
        return {
            'block_height': self.block_height,
            'timestamp': self.timestamp,
            'total_circulating': str(self.total_circulating),
            'current_reward': str(self.current_reward),
            'current_era': self.current_era,
            'percent_emitted': round(self.percent_emitted, 6),
            'max_supply': str(Config.MAX_SUPPLY),
            'total_fees_collected': str(self.total_fees_collected),
            'halving_event': self.halving_event,
        }


class CirculationTracker:
    """Track QBC token circulation across the blockchain.

    Key invariant: AGI never mints QBC. All QBC comes from mining rewards.
    This tracker verifies and records circulation metrics per block.
    """

    def __init__(self, max_history: int = 10000) -> None:
        self._history: List[CirculationSnapshot] = []
        self._max_history = max_history
        self._total_fees: Decimal = Decimal('0')
        self._halving_events: List[dict] = []

    @staticmethod
    def compute_era(block_height: int) -> int:
        """Compute the mining era for a given block height.

        Era changes every HALVING_INTERVAL blocks (phi-halving).
        """
        if block_height < 0:
            return 0
        return block_height // Config.HALVING_INTERVAL

    @staticmethod
    def compute_block_reward(block_height: int) -> Decimal:
        """Compute the mining reward for a specific block height.

        Reward = INITIAL_REWARD / PHI^era (golden ratio halving).
        """
        era = CirculationTracker.compute_era(block_height)
        phi = Decimal(str(Config.PHI))
        reward = Config.INITIAL_REWARD / (phi ** era)
        # Never go below 1 satoshi (0.00000001)
        min_reward = Decimal('0.00000001')
        return max(reward, min_reward)

    @staticmethod
    def compute_total_emitted(block_height: int) -> Decimal:
        """Compute total QBC emitted from genesis to a given height.

        Sums rewards across all eras up to block_height.
        """
        if block_height < 0:
            return Decimal('0')

        total = Decimal('0')
        phi = Decimal(str(Config.PHI))
        current_era = CirculationTracker.compute_era(block_height)

        for era in range(current_era + 1):
            era_start = era * Config.HALVING_INTERVAL
            era_end = min(
                (era + 1) * Config.HALVING_INTERVAL - 1, block_height,
            )
            if era_start > block_height:
                break
            blocks_in_era = era_end - era_start + 1
            reward = Config.INITIAL_REWARD / (phi ** era)
            total += reward * blocks_in_era

        # Cap at MAX_SUPPLY
        return min(total, Config.MAX_SUPPLY)

    def record_block(self, block_height: int, block_timestamp: float = 0.0,
                     fees_in_block: Decimal = Decimal('0')) -> CirculationSnapshot:
        """Record circulation metrics for a new block.

        Args:
            block_height: The block height.
            block_timestamp: Unix timestamp of the block.
            fees_in_block: Total fees collected in this block.

        Returns:
            CirculationSnapshot for this block.
        """
        era = self.compute_era(block_height)
        reward = self.compute_block_reward(block_height)
        total = self.compute_total_emitted(block_height)
        self._total_fees += fees_in_block

        # Detect halving event
        prev_era = self.compute_era(block_height - 1) if block_height > 0 else -1
        is_halving = era > prev_era and block_height > 0

        percent = (
            float(total / Config.MAX_SUPPLY * 100)
            if Config.MAX_SUPPLY > 0 else 0.0
        )

        snapshot = CirculationSnapshot(
            block_height=block_height,
            timestamp=block_timestamp or time.time(),
            total_circulating=total,
            current_reward=reward,
            current_era=era,
            percent_emitted=percent,
            total_fees_collected=self._total_fees,
            halving_event=is_halving,
        )

        if is_halving:
            halving_info = {
                'block_height': block_height,
                'old_era': prev_era,
                'new_era': era,
                'old_reward': str(self.compute_block_reward(block_height - 1)),
                'new_reward': str(reward),
                'total_circulating': str(total),
                'timestamp': snapshot.timestamp,
            }
            self._halving_events.append(halving_info)
            logger.info(
                f"PHI-HALVING at block {block_height}: Era {prev_era}->{era}, "
                f"Reward {halving_info['old_reward']}->{reward}"
            )

        self._history.append(snapshot)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return snapshot

    def get_current(self) -> Optional[CirculationSnapshot]:
        """Get the most recent circulation snapshot."""
        return self._history[-1] if self._history else None

    def get_history(self, limit: int = 100) -> List[dict]:
        """Get recent circulation snapshots."""
        return [s.to_dict() for s in self._history[-limit:]]

    def get_halving_events(self) -> List[dict]:
        """Get all recorded halving events."""
        return list(self._halving_events)

    def get_emission_schedule(self, num_eras: int = 10) -> List[dict]:
        """Get the projected emission schedule for upcoming eras."""
        phi = Decimal(str(Config.PHI))
        schedule = []

        for era in range(num_eras):
            reward = Config.INITIAL_REWARD / (phi ** era)
            era_start = era * Config.HALVING_INTERVAL
            era_end = (era + 1) * Config.HALVING_INTERVAL - 1
            blocks = Config.HALVING_INTERVAL
            era_emission = reward * blocks

            schedule.append({
                'era': era,
                'block_start': era_start,
                'block_end': era_end,
                'reward_per_block': str(
                    reward.quantize(Decimal('0.00000001'))
                ),
                'total_era_emission': str(
                    era_emission.quantize(Decimal('0.00000001'))
                ),
                'duration_seconds': blocks * Config.TARGET_BLOCK_TIME,
                'duration_years': round(
                    blocks * Config.TARGET_BLOCK_TIME / (365.25 * 86400), 2,
                ),
            })

        return schedule

    def get_stats(self) -> dict:
        """Get overall circulation statistics."""
        current = self.get_current()
        return {
            'current': current.to_dict() if current else None,
            'halving_events': len(self._halving_events),
            'snapshots_stored': len(self._history),
            'total_fees_collected': str(self._total_fees),
        }
