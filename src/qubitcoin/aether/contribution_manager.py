"""
AIKGS Contribution Manager — Orchestrates the full contribution lifecycle.

Flow:
  1. User submits knowledge via chat or upload
  2. KnowledgeScorer evaluates quality + novelty + anti-gaming
  3. Knowledge added to KnowledgeGraph as KeterNode
  4. RewardEngine calculates and distributes QBC reward
  5. AffiliateManager processes referral commissions
  6. ContributionLedger records immutably on-chain
  7. Badge NFTs minted for milestone achievements
"""
import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ContributionRecord:
    """Complete record of a processed contribution."""
    contribution_id: int
    contributor_address: str
    content_hash: str
    knowledge_node_id: Optional[int] = None
    quality_score: float = 0.0
    novelty_score: float = 0.0
    combined_score: float = 0.0
    tier: str = 'bronze'
    domain: str = 'general'
    reward_amount: float = 0.0
    affiliate_l1_amount: float = 0.0
    affiliate_l2_amount: float = 0.0
    is_bounty_fulfillment: bool = False
    bounty_id: Optional[int] = None
    badges_earned: List[str] = field(default_factory=list)
    block_height: int = 0
    timestamp: float = 0.0
    status: str = 'accepted'

    def to_dict(self) -> dict:
        return {
            'contribution_id': self.contribution_id,
            'contributor_address': self.contributor_address,
            'content_hash': self.content_hash,
            'knowledge_node_id': self.knowledge_node_id,
            'quality_score': round(self.quality_score, 4),
            'novelty_score': round(self.novelty_score, 4),
            'combined_score': round(self.combined_score, 4),
            'tier': self.tier,
            'domain': self.domain,
            'reward_amount': round(self.reward_amount, 8),
            'affiliate_l1_amount': round(self.affiliate_l1_amount, 8),
            'affiliate_l2_amount': round(self.affiliate_l2_amount, 8),
            'is_bounty_fulfillment': self.is_bounty_fulfillment,
            'bounty_id': self.bounty_id,
            'badges_earned': self.badges_earned,
            'block_height': self.block_height,
            'timestamp': self.timestamp,
            'status': self.status,
        }


class ContributionManager:
    """Orchestrates the full AIKGS contribution lifecycle."""

    # Maximum stored contributions to prevent unbounded memory growth
    MAX_CONTRIBUTIONS = 50000

    def __init__(self,
                 knowledge_graph: object = None,
                 knowledge_scorer: object = None,
                 reward_engine: object = None,
                 affiliate_manager: object = None,
                 bounty_manager: object = None,
                 progressive_unlocks: object = None,
                 curation_engine: object = None,
                 on_chain: object = None,
                 block_height_fn: object = None,
                 queue_reward_fn: object = None) -> None:
        """
        Args:
            knowledge_graph: KnowledgeGraph instance.
            knowledge_scorer: KnowledgeScorer for quality/novelty.
            reward_engine: RewardEngine for QBC distribution.
            affiliate_manager: AffiliateManager for referral commissions.
            bounty_manager: BountyManager for bounty lifecycle.
            progressive_unlocks: ProgressiveUnlocks for reputation.
            on_chain: OnChainAGI for contract interactions.
            block_height_fn: Callable returning current block height.
            queue_reward_fn: Callable(address, amount, reason) to queue UTXO reward outputs.
        """
        self._kg = knowledge_graph
        self._scorer = knowledge_scorer
        self._rewards = reward_engine
        self._affiliates = affiliate_manager
        self._bounties = bounty_manager
        self._unlocks = progressive_unlocks
        self._curation = curation_engine
        self._on_chain = on_chain
        self._block_height_fn = block_height_fn
        self._queue_reward_fn = queue_reward_fn

        self._lock = threading.Lock()
        self._contribution_counter: int = 0
        self._contributions: Dict[int, ContributionRecord] = {}
        self._contributor_history: Dict[str, List[int]] = {}

        # Daily rate limit tracking: address => list of timestamps for today
        self._daily_max = int(getattr(Config, 'AIKGS_MAX_DAILY_SUBMISSIONS', 50))
        self._daily_submissions: Dict[str, List[float]] = {}

    def process_contribution(self, contributor_address: str, content: str,
                             metadata: Optional[dict] = None,
                             bounty_id: Optional[int] = None) -> ContributionRecord:
        """Process a new knowledge contribution through the full pipeline.

        Args:
            contributor_address: QBC address of the contributor.
            content: The knowledge content text.
            metadata: Optional metadata (source, context, tags).
            bounty_id: Optional bounty being fulfilled.

        Returns:
            ContributionRecord with all results.
        """
        start = time.time()
        block_height = self._block_height_fn() if self._block_height_fn else 0

        # C12 FIX: Rate limit + counter increment under a single lock
        # to prevent TOCTOU race where concurrent requests bypass the limit
        with self._lock:
            now = time.time()
            day_start = now - (now % 86400)
            submissions = self._daily_submissions.get(contributor_address, [])
            # Prune old entries (before today)
            submissions = [t for t in submissions if t >= day_start]
            self._daily_submissions[contributor_address] = submissions
            if len(submissions) >= self._daily_max:
                logger.warning(
                    f"Rate limit exceeded: contributor={contributor_address[:8]}... "
                    f"submissions_today={len(submissions)} max={self._daily_max}"
                )
                raise ValueError(
                    f"Daily submission limit reached ({self._daily_max}). Try again tomorrow."
                )
            submissions.append(now)

            self._contribution_counter += 1
            contribution_id = self._contribution_counter

        # 1. Score the contribution
        score = None
        if self._scorer:
            score = self._scorer.score_contribution(content, contributor_address, metadata)
        else:
            # Default scoring if scorer not available
            from .knowledge_scorer import ContributionScore
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            score = ContributionScore(
                quality_score=0.5, novelty_score=0.5, combined_score=0.5,
                tier='silver', is_spam=False, domain='general',
                content_hash=content_hash,
            )

        # 2. Reject spam
        if score.is_spam:
            logger.info(f"Contribution rejected (spam): contributor={contributor_address[:8]}... reason={score.spam_reason}")
            return ContributionRecord(
                contribution_id=contribution_id,
                contributor_address=contributor_address,
                content_hash=score.content_hash,
                quality_score=0.0,
                novelty_score=0.0,
                combined_score=0.0,
                tier='bronze',
                domain=score.domain,
                block_height=block_height,
                timestamp=time.time(),
                status='rejected_spam',
            )

        # 3. Add to knowledge graph
        node_id = None
        if self._kg:
            try:
                node = self._kg.add_node(
                    content={
                        'text': content,
                        'source': f'aikgs:{contributor_address[:8]}',
                        'contributor': contributor_address,
                        **(metadata or {}),
                    },
                    node_type='assertion',
                    confidence=score.quality_score,
                    source_block=block_height,
                )
                node_id = node.node_id
            except Exception as e:
                logger.warning(f"Failed to add contribution to KG: {e}")

        # 4. Calculate and distribute reward
        reward_amount = 0.0
        if self._rewards:
            reward_amount = self._rewards.calculate_reward(
                quality_score=score.quality_score,
                novelty_score=score.novelty_score,
                tier=score.tier,
                contributor_address=contributor_address,
            )

        # 5. Process bounty fulfillment (bonus reward)
        is_bounty = False
        if bounty_id and self._bounties:
            try:
                bounty_reward = self._bounties.fulfill_bounty(
                    bounty_id, contribution_id, contributor_address,
                )
                if bounty_reward:
                    reward_amount += bounty_reward
                    is_bounty = True
            except Exception as e:
                logger.warning(f"Bounty fulfillment failed: {e}")

        # 6. Process affiliate commissions
        l1_amount = 0.0
        l2_amount = 0.0
        if self._affiliates and reward_amount > 0:
            l1_amount, l2_amount = self._affiliates.process_commissions(
                contributor_address, reward_amount, contribution_id,
            )

        # 7. Update reputation / progressive unlocks
        badges_earned: List[str] = []
        if self._unlocks:
            new_badges = self._unlocks.record_contribution(
                contributor_address, score.combined_score, score.tier,
            )
            badges_earned = new_badges

        # 8. Build record
        record = ContributionRecord(
            contribution_id=contribution_id,
            contributor_address=contributor_address,
            content_hash=score.content_hash,
            knowledge_node_id=node_id,
            quality_score=score.quality_score,
            novelty_score=score.novelty_score,
            combined_score=score.combined_score,
            tier=score.tier,
            domain=score.domain,
            reward_amount=reward_amount,
            affiliate_l1_amount=l1_amount,
            affiliate_l2_amount=l2_amount,
            is_bounty_fulfillment=is_bounty,
            bounty_id=bounty_id if is_bounty else None,
            badges_earned=badges_earned,
            block_height=block_height,
            timestamp=time.time(),
            status='accepted',
        )

        # Store (thread-safe)
        with self._lock:
            self._contributions[contribution_id] = record
            if contributor_address not in self._contributor_history:
                self._contributor_history[contributor_address] = []
            self._contributor_history[contributor_address].append(contribution_id)

            # Evict oldest contributions if over limit (C14 memory bounds)
            if len(self._contributions) > self.MAX_CONTRIBUTIONS:
                oldest_ids = sorted(self._contributions.keys())[:len(self._contributions) - self.MAX_CONTRIBUTIONS]
                for old_id in oldest_ids:
                    self._contributions.pop(old_id, None)

        # 9. Queue UTXO reward output for next mined block
        if self._queue_reward_fn and reward_amount > 0:
            self._queue_reward_fn(
                contributor_address, reward_amount,
                f'aikgs_contribution_{contribution_id}',
            )

        # 9b. Queue affiliate commission UTXO outputs
        if self._queue_reward_fn and self._affiliates:
            if l1_amount > 0:
                affiliate = self._affiliates.get_affiliate(contributor_address)
                if affiliate and affiliate.referrer_address:
                    self._queue_reward_fn(
                        affiliate.referrer_address, l1_amount,
                        f'aikgs_l1_commission_{contribution_id}',
                    )
            if l2_amount > 0:
                affiliate = self._affiliates.get_affiliate(contributor_address)
                if affiliate and affiliate.referrer_address:
                    l1_aff = self._affiliates.get_affiliate(affiliate.referrer_address)
                    if l1_aff and l1_aff.referrer_address:
                        self._queue_reward_fn(
                            l1_aff.referrer_address, l2_amount,
                            f'aikgs_l2_commission_{contribution_id}',
                        )

        # 10. Submit gold/diamond contributions for peer curation
        if self._curation and score.tier in ('gold', 'diamond'):
            try:
                self._curation.submit_for_curation(contribution_id)
            except Exception as e:
                logger.warning(f"Curation submission failed: {e}")

        elapsed = (time.time() - start) * 1000
        logger.info(
            f"Contribution processed: id={contribution_id} tier={score.tier} "
            f"quality={score.quality_score:.2f} novelty={score.novelty_score:.2f} "
            f"reward={reward_amount:.4f} QBC ({elapsed:.1f}ms)"
        )

        return record

    def get_contribution(self, contribution_id: int) -> Optional[ContributionRecord]:
        """Get a contribution by ID."""
        return self._contributions.get(contribution_id)

    def get_contributor_history(self, address: str, limit: int = 50) -> List[ContributionRecord]:
        """Get contribution history for an address."""
        ids = self._contributor_history.get(address, [])
        records = [self._contributions[cid] for cid in ids[-limit:] if cid in self._contributions]
        return records

    def get_recent_contributions(self, limit: int = 20) -> List[ContributionRecord]:
        """Get most recent contributions across all contributors."""
        all_ids = sorted(self._contributions.keys(), reverse=True)
        return [self._contributions[cid] for cid in all_ids[:limit]]

    def get_leaderboard(self, limit: int = 50) -> List[dict]:
        """Get top contributors by total reward earned."""
        totals: Dict[str, dict] = {}
        for record in self._contributions.values():
            addr = record.contributor_address
            if addr not in totals:
                totals[addr] = {
                    'address': addr,
                    'total_reward': 0.0,
                    'contribution_count': 0,
                    'avg_quality': 0.0,
                    'best_tier': 'bronze',
                }
            totals[addr]['total_reward'] += record.reward_amount
            totals[addr]['contribution_count'] += 1
            totals[addr]['avg_quality'] += record.quality_score
            tier_rank = {'diamond': 4, 'gold': 3, 'silver': 2, 'bronze': 1}
            if tier_rank.get(record.tier, 0) > tier_rank.get(totals[addr]['best_tier'], 0):
                totals[addr]['best_tier'] = record.tier

        for entry in totals.values():
            if entry['contribution_count'] > 0:
                entry['avg_quality'] = round(entry['avg_quality'] / entry['contribution_count'], 4)
            entry['total_reward'] = round(entry['total_reward'], 8)

        ranked = sorted(totals.values(), key=lambda x: x['total_reward'], reverse=True)
        return ranked[:limit]

    def get_stats(self) -> dict:
        """Get contribution manager statistics."""
        tier_counts: Dict[str, int] = {'bronze': 0, 'silver': 0, 'gold': 0, 'diamond': 0}
        total_rewards = 0.0
        for r in self._contributions.values():
            tier_counts[r.tier] = tier_counts.get(r.tier, 0) + 1
            total_rewards += r.reward_amount

        return {
            'total_contributions': self._contribution_counter,
            'unique_contributors': len(self._contributor_history),
            'total_rewards_distributed': round(total_rewards, 8),
            'tier_distribution': tier_counts,
            'bounty_fulfillments': sum(1 for r in self._contributions.values() if r.is_bounty_fulfillment),
        }
