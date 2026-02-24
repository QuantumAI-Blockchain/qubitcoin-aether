"""
Bridge Validator Reward Tracker

Tracks bridge validators who verify cross-chain proofs and calculates
proportional QBC rewards. Validators earn configurable rewards per
successful proof verification.

Reward flow:
  1. Validator verifies a cross-chain proof
  2. record_verification() logs the verification
  3. calculate_rewards() computes proportional QBC allocation
  4. Rewards are distributed during block finalization
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VerificationRecord:
    """A single proof verification by a validator."""
    validator: str
    bridge_name: str
    proof_hash: str
    timestamp: float
    reward_qbc: float


class ValidatorRewardTracker:
    """Track bridge validator verifications and compute reward distributions.

    Each successful verification earns the validator a configurable QBC
    reward (``Config.BRIDGE_VALIDATOR_REWARD_QBC``). Rewards accumulate
    and can be queried per-validator or in aggregate.
    """

    def __init__(self, reward_per_verification: Optional[float] = None) -> None:
        """
        Args:
            reward_per_verification: QBC reward per verification.
                Defaults to ``Config.BRIDGE_VALIDATOR_REWARD_QBC`` (0.01).
        """
        self.reward_per_verification: float = (
            reward_per_verification
            if reward_per_verification is not None
            else getattr(Config, 'BRIDGE_VALIDATOR_REWARD_QBC', 0.01)
        )
        # validator_address -> list of VerificationRecord
        self._verifications: Dict[str, List[VerificationRecord]] = {}
        # proof_hash -> validator (prevent double-counting same proof)
        self._processed_proofs: Dict[str, str] = {}
        # Per-bridge verification counts
        self._bridge_counts: Dict[str, int] = {}
        logger.info(
            f"ValidatorRewardTracker initialized "
            f"(reward_per_verification={self.reward_per_verification} QBC)"
        )

    def record_verification(self, validator: str, bridge_name: str,
                            proof_hash: str) -> None:
        """Record a successful proof verification by a validator.

        If the same proof_hash has already been recorded, the duplicate
        is silently ignored (prevents double-reward attacks).

        Args:
            validator: Validator address (hex string).
            bridge_name: Name of the bridge chain (e.g. 'ethereum').
            proof_hash: Unique hash of the bridge proof.
        """
        normalized = validator.lower().strip()
        bridge_key = bridge_name.lower().strip()

        # Prevent double-recording the same proof
        if proof_hash in self._processed_proofs:
            logger.debug(
                f"Proof {proof_hash[:16]}... already processed by "
                f"{self._processed_proofs[proof_hash][:16]}..."
            )
            return

        record = VerificationRecord(
            validator=normalized,
            bridge_name=bridge_key,
            proof_hash=proof_hash,
            timestamp=time.time(),
            reward_qbc=self.reward_per_verification,
        )

        if normalized not in self._verifications:
            self._verifications[normalized] = []
        self._verifications[normalized].append(record)
        self._processed_proofs[proof_hash] = normalized
        self._bridge_counts[bridge_key] = self._bridge_counts.get(bridge_key, 0) + 1

        logger.info(
            f"Verification recorded: validator={normalized[:16]}... "
            f"bridge={bridge_key} proof={proof_hash[:16]}..."
        )

    def calculate_rewards(self, bridge_name: Optional[str] = None) -> Dict[str, float]:
        """Calculate accumulated QBC rewards per validator.

        Args:
            bridge_name: If provided, only count verifications for this bridge.
                         If None, count all bridges.

        Returns:
            Dict mapping validator address to total QBC reward.
        """
        rewards: Dict[str, float] = {}
        for validator, records in self._verifications.items():
            filtered = records
            if bridge_name:
                bridge_key = bridge_name.lower().strip()
                filtered = [r for r in records if r.bridge_name == bridge_key]
            total = sum(r.reward_qbc for r in filtered)
            if total > 0:
                rewards[validator] = total
        return rewards

    def get_validator_stats(self, validator: str) -> Dict:
        """Get verification statistics for a specific validator.

        Args:
            validator: Validator address.

        Returns:
            Dict with verification_count, total_rewards, per-bridge
            breakdown, and recent verifications.
        """
        normalized = validator.lower().strip()
        records = self._verifications.get(normalized, [])
        total_rewards = sum(r.reward_qbc for r in records)

        # Per-bridge breakdown
        bridge_breakdown: Dict[str, int] = {}
        for r in records:
            bridge_breakdown[r.bridge_name] = bridge_breakdown.get(r.bridge_name, 0) + 1

        # Recent verifications (last 10)
        recent = [
            {
                "bridge_name": r.bridge_name,
                "proof_hash": r.proof_hash,
                "timestamp": r.timestamp,
                "reward_qbc": r.reward_qbc,
            }
            for r in records[-10:]
        ][::-1]  # Most recent first

        return {
            "validator": normalized,
            "verification_count": len(records),
            "total_rewards_qbc": total_rewards,
            "bridge_breakdown": bridge_breakdown,
            "recent_verifications": recent,
        }

    def get_top_validators(self, limit: int = 10) -> List[Dict]:
        """Get top validators ranked by total verifications.

        Args:
            limit: Maximum number of validators to return.

        Returns:
            List of dicts with validator, verification_count, total_rewards.
        """
        ranked = []
        for validator, records in self._verifications.items():
            ranked.append({
                "validator": validator,
                "verification_count": len(records),
                "total_rewards_qbc": sum(r.reward_qbc for r in records),
            })
        ranked.sort(key=lambda x: x["verification_count"], reverse=True)
        return ranked[:limit]

    def get_stats(self) -> Dict:
        """Get overall reward tracker statistics.

        Returns:
            Dict with total validators, verifications, rewards, and
            per-bridge counts.
        """
        total_verifications = sum(len(v) for v in self._verifications.values())
        total_rewards = sum(
            sum(r.reward_qbc for r in records)
            for records in self._verifications.values()
        )
        return {
            "total_validators": len(self._verifications),
            "total_verifications": total_verifications,
            "total_rewards_qbc": total_rewards,
            "reward_per_verification": self.reward_per_verification,
            "bridge_counts": dict(self._bridge_counts),
            "processed_proofs": len(self._processed_proofs),
        }
