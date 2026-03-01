"""
AIKGS Affiliate Manager — 2-Level referral commission system.

Commission structure:
  - L1 (direct referrer): 10% of contributor's reward (from pool, NOT from contributor)
  - L2 (referrer's referrer): 5% of contributor's reward (from pool)

Features:
  - Referral code generation and tracking
  - Telegram deep-link integration
  - Commission history and leaderboard
  - Anti-abuse: self-referral prevention, minimum activity requirements
"""
import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AffiliateRecord:
    """Affiliate registration and stats."""
    address: str
    referrer_address: Optional[str] = None
    referral_code: str = ''
    registered_at: float = 0.0
    l1_referrals: int = 0        # Direct referrals
    l2_referrals: int = 0        # Indirect referrals
    total_l1_commission: float = 0.0
    total_l2_commission: float = 0.0
    total_referral_rewards: float = 0.0  # Total rewards from all referrals
    is_active: bool = True

    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'referrer_address': self.referrer_address,
            'referral_code': self.referral_code,
            'registered_at': self.registered_at,
            'l1_referrals': self.l1_referrals,
            'l2_referrals': self.l2_referrals,
            'total_l1_commission': round(self.total_l1_commission, 8),
            'total_l2_commission': round(self.total_l2_commission, 8),
            'total_referral_rewards': round(self.total_referral_rewards, 8),
            'is_active': self.is_active,
        }


@dataclass
class CommissionEvent:
    """Record of a commission payment."""
    affiliate_address: str
    contributor_address: str
    amount: float
    level: int  # 1 or 2
    contribution_id: int
    timestamp: float

    def to_dict(self) -> dict:
        return {
            'affiliate_address': self.affiliate_address,
            'contributor_address': self.contributor_address,
            'amount': round(self.amount, 8),
            'level': self.level,
            'contribution_id': self.contribution_id,
            'timestamp': self.timestamp,
        }


class AffiliateManager:
    """Manages 2-level referral system for AIKGS."""

    # Maximum stored commission events to prevent unbounded memory growth
    MAX_COMMISSION_HISTORY = 10000

    def __init__(self, reward_engine: object = None) -> None:
        self._l1_commission_rate = float(getattr(Config, 'AIKGS_L1_COMMISSION_RATE', 0.10))
        self._l2_commission_rate = float(getattr(Config, 'AIKGS_L2_COMMISSION_RATE', 0.05))
        self._reward_engine = reward_engine  # For pool deductions

        self._lock = threading.Lock()
        self._affiliates: Dict[str, AffiliateRecord] = {}
        self._referral_codes: Dict[str, str] = {}  # code => address
        self._commission_history: List[CommissionEvent] = []
        self._total_commissions: float = 0.0

    def register(self, address: str, referrer_code: Optional[str] = None) -> AffiliateRecord:
        """Register a new affiliate.

        Args:
            address: The user's QBC address.
            referrer_code: Optional referral code of who referred them.

        Returns:
            AffiliateRecord for the new affiliate.
        """
        with self._lock:
            return self._register_inner(address, referrer_code)

    def _register_inner(self, address: str, referrer_code: Optional[str] = None) -> AffiliateRecord:
        """Inner registration logic — must be called under self._lock."""
        if address in self._affiliates:
            return self._affiliates[address]

        # Resolve referrer
        referrer_address = None
        if referrer_code:
            referrer_address = self._referral_codes.get(referrer_code)
            if referrer_address == address:
                referrer_address = None  # Anti-abuse: no self-referral
            # Anti-abuse: detect circular referral chains (A→B→A)
            if referrer_address:
                visited = {address}
                current = referrer_address
                while current:
                    if current in visited:
                        logger.warning(f"Circular referral detected: {address[:8]}... → {referrer_address[:8]}...")
                        referrer_address = None
                        break
                    visited.add(current)
                    parent = self._affiliates.get(current)
                    current = parent.referrer_address if parent else None

        # Generate unique referral code
        code = self._generate_code(address)

        record = AffiliateRecord(
            address=address,
            referrer_address=referrer_address,
            referral_code=code,
            registered_at=time.time(),
        )
        self._affiliates[address] = record
        self._referral_codes[code] = address

        # Update referrer counts
        if referrer_address and referrer_address in self._affiliates:
            self._affiliates[referrer_address].l1_referrals += 1

            # L2: referrer's referrer
            l2_address = self._affiliates[referrer_address].referrer_address
            if l2_address and l2_address in self._affiliates:
                self._affiliates[l2_address].l2_referrals += 1

        logger.info(f"Affiliate registered: {address[:8]}... referrer={referrer_address or 'none'}")
        return record

    def process_commissions(self, contributor_address: str, reward_amount: float,
                            contribution_id: int) -> Tuple[float, float]:
        """Calculate and record affiliate commissions.

        Commissions are DEDUCTED FROM THE REWARD POOL via RewardEngine,
        not created from thin air. If the pool lacks funds, commissions
        are reduced proportionally.

        Args:
            contributor_address: The contributor who earned the reward.
            reward_amount: The reward amount the contributor earned.
            contribution_id: The contribution identifier.

        Returns:
            Tuple of (l1_commission, l2_commission).
        """
        with self._lock:
            affiliate = self._affiliates.get(contributor_address)
            if not affiliate or not affiliate.referrer_address:
                return (0.0, 0.0)

            l1_amount = 0.0
            l2_amount = 0.0

            # L1 commission to direct referrer
            l1_referrer = affiliate.referrer_address
            if l1_referrer and l1_referrer in self._affiliates:
                l1_amount = reward_amount * self._l1_commission_rate

                # Deduct from reward pool — commissions MUST be pool-funded
                if self._reward_engine:
                    with self._reward_engine._lock:
                        l1_amount = min(l1_amount, self._reward_engine._pool_balance)
                        self._reward_engine._pool_balance -= l1_amount
                        self._reward_engine._total_distributed += l1_amount

                self._affiliates[l1_referrer].total_l1_commission += l1_amount
                self._affiliates[l1_referrer].total_referral_rewards += l1_amount

                self._commission_history.append(CommissionEvent(
                    affiliate_address=l1_referrer,
                    contributor_address=contributor_address,
                    amount=l1_amount,
                    level=1,
                    contribution_id=contribution_id,
                    timestamp=time.time(),
                ))

                # L2 commission to referrer's referrer
                l2_referrer = self._affiliates[l1_referrer].referrer_address
                if l2_referrer and l2_referrer in self._affiliates:
                    l2_amount = reward_amount * self._l2_commission_rate

                    # Deduct from reward pool
                    if self._reward_engine:
                        with self._reward_engine._lock:
                            l2_amount = min(l2_amount, self._reward_engine._pool_balance)
                            self._reward_engine._pool_balance -= l2_amount
                            self._reward_engine._total_distributed += l2_amount

                    self._affiliates[l2_referrer].total_l2_commission += l2_amount
                    self._affiliates[l2_referrer].total_referral_rewards += l2_amount

                    self._commission_history.append(CommissionEvent(
                        affiliate_address=l2_referrer,
                        contributor_address=contributor_address,
                        amount=l2_amount,
                        level=2,
                        contribution_id=contribution_id,
                        timestamp=time.time(),
                    ))

            self._total_commissions += l1_amount + l2_amount

            # Evict old commission history to prevent unbounded memory growth
            if len(self._commission_history) > self.MAX_COMMISSION_HISTORY:
                self._commission_history = self._commission_history[-self.MAX_COMMISSION_HISTORY:]

            return (round(l1_amount, 8), round(l2_amount, 8))

    def get_affiliate(self, address: str) -> Optional[AffiliateRecord]:
        """Get affiliate info."""
        return self._affiliates.get(address)

    def get_referral_chain(self, address: str) -> dict:
        """Get the referral chain for an address."""
        affiliate = self._affiliates.get(address)
        if not affiliate:
            return {'address': address, 'l1': None, 'l2': None}

        l1 = affiliate.referrer_address
        l2 = None
        if l1 and l1 in self._affiliates:
            l2 = self._affiliates[l1].referrer_address

        return {'address': address, 'l1': l1, 'l2': l2}

    def get_referrals(self, address: str) -> List[str]:
        """Get list of direct referrals (L1) for an address."""
        return [
            a.address for a in self._affiliates.values()
            if a.referrer_address == address
        ]

    def resolve_code(self, code: str) -> Optional[str]:
        """Resolve a referral code to an address."""
        return self._referral_codes.get(code)

    def get_commission_history(self, address: str, limit: int = 50) -> List[dict]:
        """Get commission history for an affiliate."""
        events = [
            e.to_dict() for e in self._commission_history
            if e.affiliate_address == address
        ]
        return events[-limit:]

    def get_leaderboard(self, limit: int = 50) -> List[dict]:
        """Get top affiliates by total commission earned."""
        ranked = sorted(
            self._affiliates.values(),
            key=lambda a: a.total_l1_commission + a.total_l2_commission,
            reverse=True,
        )
        return [a.to_dict() for a in ranked[:limit]]

    def _generate_code(self, address: str) -> str:
        """Generate a unique referral code from an address with collision check."""
        for _ in range(10):
            h = hashlib.sha256(f"{address}:{time.time()}:{os.urandom(4).hex()}".encode()).hexdigest()
            code = f"QBC-{h[:8].upper()}"
            if code not in self._referral_codes:
                return code
        # Extremely unlikely fallback — use longer hash
        h = hashlib.sha256(f"{address}:{time.time()}:{os.urandom(16).hex()}".encode()).hexdigest()
        return f"QBC-{h[:12].upper()}"

    def get_stats(self) -> dict:
        """Get affiliate system statistics."""
        return {
            'total_affiliates': len(self._affiliates),
            'total_commissions': round(self._total_commissions, 8),
            'commission_events': len(self._commission_history),
            'l1_commission_rate': self._l1_commission_rate,
            'l2_commission_rate': self._l2_commission_rate,
            'total_referral_codes': len(self._referral_codes),
        }
