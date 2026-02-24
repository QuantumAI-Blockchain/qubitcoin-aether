"""
Bridge Relayer Incentive System

Tracks cross-chain message relay events per relayer address and calculates
QBC rewards based on relay count and message value. Relayers must meet a
minimum stake requirement to be eligible for rewards.

Reward flow:
  1. Relayer delivers a cross-chain message
  2. record_relay() logs the relay event with message value
  3. Rewards are calculated: base reward + value-proportional bonus
  4. get_pending_rewards() returns claimable amounts per relayer
  5. claim_rewards() marks rewards as claimed
"""
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RelayEvent:
    """A single cross-chain message relay by a relayer."""
    relayer: str
    source_chain: str
    dest_chain: str
    message_hash: str
    message_value: Decimal
    reward_qbc: Decimal
    timestamp: float
    claimed: bool = False


class RelayerIncentive:
    """Track bridge relayer activity and compute QBC reward distributions.

    Relayers earn a configurable base reward per relay
    (``Config.BRIDGE_RELAYER_REWARD_QBC``) plus a value-proportional bonus
    calculated as ``message_value * value_bonus_bps / 10000``.

    Relayers must have a registered stake >= ``Config.BRIDGE_RELAYER_MIN_STAKE``
    to be eligible for rewards.  Unregistered or under-staked relayers can
    still relay messages, but their rewards are withheld until they meet
    the stake requirement.
    """

    # Value bonus: basis points of message value added as extra reward
    VALUE_BONUS_BPS: int = 5  # 0.05% of message value

    def __init__(
        self,
        reward_per_relay: Optional[float] = None,
        min_stake: Optional[float] = None,
        value_bonus_bps: Optional[int] = None,
    ) -> None:
        """
        Args:
            reward_per_relay: Base QBC reward per relay.
                Defaults to ``Config.BRIDGE_RELAYER_REWARD_QBC``.
            min_stake: Minimum stake required for reward eligibility.
                Defaults to ``Config.BRIDGE_RELAYER_MIN_STAKE``.
            value_bonus_bps: Basis points of message value added as bonus.
                Defaults to ``VALUE_BONUS_BPS`` (5 bps = 0.05%).
        """
        self.reward_per_relay: Decimal = Decimal(str(
            reward_per_relay
            if reward_per_relay is not None
            else getattr(Config, 'BRIDGE_RELAYER_REWARD_QBC', 0.05)
        ))
        self.min_stake: Decimal = Decimal(str(
            min_stake
            if min_stake is not None
            else getattr(Config, 'BRIDGE_RELAYER_MIN_STAKE', 100.0)
        ))
        self.value_bonus_bps: int = (
            value_bonus_bps if value_bonus_bps is not None else self.VALUE_BONUS_BPS
        )

        # relayer_address -> list of RelayEvent
        self._relays: Dict[str, List[RelayEvent]] = {}
        # message_hash -> relayer (prevent double-counting)
        self._processed_messages: Dict[str, str] = {}
        # relayer_address -> staked QBC amount
        self._stakes: Dict[str, Decimal] = {}
        # Per-chain relay counts
        self._chain_counts: Dict[str, int] = {}

        logger.info(
            f"RelayerIncentive initialized "
            f"(reward_per_relay={self.reward_per_relay} QBC, "
            f"min_stake={self.min_stake} QBC, "
            f"value_bonus_bps={self.value_bonus_bps})"
        )

    # ========================================================================
    # STAKE MANAGEMENT
    # ========================================================================

    def register_stake(self, relayer: str, amount: Decimal) -> bool:
        """Register or update a relayer's stake.

        Args:
            relayer: Relayer address.
            amount: Total staked QBC amount (replaces previous value).

        Returns:
            True if the stake meets the minimum requirement.
        """
        normalized = relayer.lower().strip()
        if amount < Decimal(0):
            logger.warning(f"Invalid stake amount {amount} for {normalized[:16]}...")
            return False

        self._stakes[normalized] = amount
        meets_min = amount >= self.min_stake
        logger.info(
            f"Stake registered: relayer={normalized[:16]}... "
            f"amount={amount} QBC (eligible={meets_min})"
        )
        return meets_min

    def get_stake(self, relayer: str) -> Decimal:
        """Get a relayer's current stake.

        Args:
            relayer: Relayer address.

        Returns:
            Staked amount, or Decimal(0) if not registered.
        """
        return self._stakes.get(relayer.lower().strip(), Decimal(0))

    def is_eligible(self, relayer: str) -> bool:
        """Check if a relayer meets the minimum stake requirement.

        Args:
            relayer: Relayer address.

        Returns:
            True if stake >= min_stake.
        """
        return self.get_stake(relayer) >= self.min_stake

    # ========================================================================
    # RELAY EVENT RECORDING
    # ========================================================================

    def calculate_reward(self, message_value: Decimal) -> Decimal:
        """Calculate the total reward for a single relay.

        Reward = base_reward + (message_value * value_bonus_bps / 10000)

        Args:
            message_value: Value of the relayed message in QBC.

        Returns:
            Total reward in QBC.
        """
        base = self.reward_per_relay
        bonus = (message_value * Decimal(self.value_bonus_bps)) / Decimal(10000)
        return base + bonus

    def record_relay(
        self,
        relayer: str,
        source_chain: str,
        dest_chain: str,
        message_hash: str,
        message_value: Decimal = Decimal(0),
    ) -> Optional[RelayEvent]:
        """Record a cross-chain message relay.

        If the same message_hash has already been recorded, the duplicate
        is silently ignored (prevents double-reward attacks).

        Rewards are calculated but only claimable if the relayer meets the
        minimum stake requirement.

        Args:
            relayer: Relayer address.
            source_chain: Source chain name (e.g. 'ethereum').
            dest_chain: Destination chain name (e.g. 'polygon').
            message_hash: Unique hash of the relayed message.
            message_value: Value of the message in QBC (default 0).

        Returns:
            The RelayEvent if recorded, None if duplicate.
        """
        normalized = relayer.lower().strip()
        src_key = source_chain.lower().strip()
        dst_key = dest_chain.lower().strip()

        # Prevent double-recording the same message
        if message_hash in self._processed_messages:
            logger.debug(
                f"Message {message_hash[:16]}... already relayed by "
                f"{self._processed_messages[message_hash][:16]}..."
            )
            return None

        reward = self.calculate_reward(message_value)

        event = RelayEvent(
            relayer=normalized,
            source_chain=src_key,
            dest_chain=dst_key,
            message_hash=message_hash,
            message_value=message_value,
            reward_qbc=reward,
            timestamp=time.time(),
            claimed=False,
        )

        if normalized not in self._relays:
            self._relays[normalized] = []
        self._relays[normalized].append(event)
        self._processed_messages[message_hash] = normalized

        # Track per-chain counts
        route_key = f"{src_key}->{dst_key}"
        self._chain_counts[route_key] = self._chain_counts.get(route_key, 0) + 1

        logger.info(
            f"Relay recorded: relayer={normalized[:16]}... "
            f"route={src_key}->{dst_key} value={message_value} "
            f"reward={reward} QBC"
        )
        return event

    # ========================================================================
    # REWARD QUERIES
    # ========================================================================

    def get_pending_rewards(self, relayer: str) -> Decimal:
        """Get total unclaimed rewards for a relayer.

        Only returns rewards if the relayer meets the minimum stake.

        Args:
            relayer: Relayer address.

        Returns:
            Total unclaimed QBC rewards (0 if ineligible).
        """
        normalized = relayer.lower().strip()
        if not self.is_eligible(normalized):
            return Decimal(0)

        events = self._relays.get(normalized, [])
        return sum(
            (e.reward_qbc for e in events if not e.claimed),
            Decimal(0),
        )

    def claim_rewards(self, relayer: str) -> Decimal:
        """Mark all pending rewards as claimed and return the total.

        Only processes claims if the relayer meets the minimum stake.

        Args:
            relayer: Relayer address.

        Returns:
            Total QBC claimed (0 if ineligible or no pending rewards).
        """
        normalized = relayer.lower().strip()
        if not self.is_eligible(normalized):
            logger.warning(
                f"Claim rejected: relayer={normalized[:16]}... "
                f"stake={self.get_stake(normalized)} < min={self.min_stake}"
            )
            return Decimal(0)

        events = self._relays.get(normalized, [])
        total_claimed = Decimal(0)
        for event in events:
            if not event.claimed:
                event.claimed = True
                total_claimed += event.reward_qbc

        if total_claimed > 0:
            logger.info(
                f"Rewards claimed: relayer={normalized[:16]}... "
                f"amount={total_claimed} QBC"
            )
        return total_claimed

    def get_relayer_stats(self, relayer: str) -> Dict:
        """Get relay statistics for a specific relayer.

        Args:
            relayer: Relayer address.

        Returns:
            Dict with relay_count, total_rewards, pending_rewards,
            claimed_rewards, stake, eligible, per-route breakdown,
            and recent relays.
        """
        normalized = relayer.lower().strip()
        events = self._relays.get(normalized, [])
        total_rewards = sum((e.reward_qbc for e in events), Decimal(0))
        claimed_rewards = sum(
            (e.reward_qbc for e in events if e.claimed), Decimal(0)
        )
        pending_rewards = total_rewards - claimed_rewards
        total_value = sum((e.message_value for e in events), Decimal(0))

        # Per-route breakdown
        route_breakdown: Dict[str, int] = {}
        for e in events:
            route = f"{e.source_chain}->{e.dest_chain}"
            route_breakdown[route] = route_breakdown.get(route, 0) + 1

        # Recent relays (last 10)
        recent = [
            {
                "source_chain": e.source_chain,
                "dest_chain": e.dest_chain,
                "message_hash": e.message_hash,
                "message_value": str(e.message_value),
                "reward_qbc": str(e.reward_qbc),
                "timestamp": e.timestamp,
                "claimed": e.claimed,
            }
            for e in events[-10:]
        ][::-1]  # Most recent first

        return {
            "relayer": normalized,
            "relay_count": len(events),
            "total_rewards_qbc": str(total_rewards),
            "pending_rewards_qbc": str(pending_rewards),
            "claimed_rewards_qbc": str(claimed_rewards),
            "total_value_relayed": str(total_value),
            "stake": str(self.get_stake(normalized)),
            "eligible": self.is_eligible(normalized),
            "route_breakdown": route_breakdown,
            "recent_relays": recent,
        }

    def get_top_relayers(self, limit: int = 10) -> List[Dict]:
        """Get top relayers ranked by total relay count.

        Args:
            limit: Maximum number of relayers to return.

        Returns:
            List of dicts with relayer, relay_count, total_rewards, eligible.
        """
        ranked = []
        for relayer, events in self._relays.items():
            total_rewards = sum((e.reward_qbc for e in events), Decimal(0))
            ranked.append({
                "relayer": relayer,
                "relay_count": len(events),
                "total_rewards_qbc": str(total_rewards),
                "eligible": self.is_eligible(relayer),
            })
        ranked.sort(key=lambda x: x["relay_count"], reverse=True)
        return ranked[:limit]

    def get_stats(self) -> Dict:
        """Get overall relayer incentive statistics.

        Returns:
            Dict with total relayers, relays, rewards, stakes, and
            per-route counts.
        """
        total_relays = sum(len(v) for v in self._relays.values())
        total_rewards = sum(
            sum((e.reward_qbc for e in events), Decimal(0))
            for events in self._relays.values()
        )
        total_claimed = sum(
            sum((e.reward_qbc for e in events if e.claimed), Decimal(0))
            for events in self._relays.values()
        )
        total_value = sum(
            sum((e.message_value for e in events), Decimal(0))
            for events in self._relays.values()
        )
        eligible_count = sum(
            1 for r in self._relays.keys() if self.is_eligible(r)
        )
        return {
            "total_relayers": len(self._relays),
            "eligible_relayers": eligible_count,
            "total_relays": total_relays,
            "total_rewards_qbc": str(total_rewards),
            "total_claimed_qbc": str(total_claimed),
            "total_pending_qbc": str(total_rewards - total_claimed),
            "total_value_relayed": str(total_value),
            "reward_per_relay": str(self.reward_per_relay),
            "min_stake": str(self.min_stake),
            "value_bonus_bps": self.value_bonus_bps,
            "route_counts": dict(self._chain_counts),
            "processed_messages": len(self._processed_messages),
        }
