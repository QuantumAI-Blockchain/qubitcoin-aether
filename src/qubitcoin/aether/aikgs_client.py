"""
Python gRPC client for the Rust AIKGS sidecar.

Bridges the Python node with the Rust AIKGS gRPC sidecar.
All AIKGS business logic runs in the sidecar; this client
translates between Python dicts and protobuf messages.

Includes circuit breaker pattern to prevent cascading failures
when the sidecar is slow or unresponsive.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Import gRPC and generated protobuf stubs
try:
    import grpc
    import grpc.aio

    from .aikgs_pb import aikgs_pb2
    from .aikgs_pb import aikgs_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AIKGS gRPC not available: {e}")
    grpc = None  # type: ignore[assignment]
    aikgs_pb2 = None  # type: ignore[assignment]
    aikgs_pb2_grpc = None  # type: ignore[assignment]
    GRPC_AVAILABLE = False


class _AuthMetadataInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    """gRPC client interceptor that attaches x-auth-token metadata to every call."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def intercept_unary_unary(
        self,
        continuation: Any,
        client_call_details: Any,
        request: Any,
    ) -> Any:
        if self._token:
            # Build new metadata with auth token
            metadata = list(client_call_details.metadata or [])
            metadata.append(("x-auth-token", self._token))
            # Create updated call details with new metadata
            new_details = grpc.aio.ClientCallDetails(
                client_call_details.method,
                client_call_details.timeout,
                metadata,
                client_call_details.credentials,
                client_call_details.wait_for_ready,
            )
            return await continuation(new_details, request)
        return await continuation(client_call_details, request)


class AikgsClient:
    """
    Async gRPC client for the AIKGS Rust gRPC sidecar.

    Wraps all 35 AikgsService RPCs with Python-friendly interfaces
    that return plain dicts. The node uses this client to communicate
    with the Rust sidecar which handles all AIKGS business logic.

    All gRPC calls include the x-auth-token metadata header for
    authentication (AIKGS-C1).
    """

    # Circuit breaker constants
    CB_FAILURE_THRESHOLD: int = 3      # Open after N consecutive failures
    CB_COOLDOWN_SECONDS: float = 60.0  # Stay open for this long before half-open probe
    CB_SLOW_THRESHOLD: float = 10.0    # Calls taking >10s count as slow failures

    def __init__(self, grpc_addr: str = "127.0.0.1:50052", auth_token: str = "") -> None:
        self.grpc_addr = grpc_addr
        self.auth_token = auth_token
        self._grpc_timeout: int = Config.AIKGS_GRPC_TIMEOUT
        self.channel: Any = None
        self.stub: Any = None
        self._connected = False

        # Circuit breaker state
        self._cb_failures: int = 0
        self._cb_open_since: float = 0.0
        self._cb_total_trips: int = 0

    async def connect(self) -> bool:
        """Connect to the AIKGS Rust gRPC sidecar."""
        if not GRPC_AVAILABLE:
            logger.error("grpcio / protobuf stubs not available — cannot connect to AIKGS sidecar")
            return False
        try:
            # Build channel with auth interceptor (AIKGS-C1)
            interceptors: list = []
            if self.auth_token:
                interceptors.append(_AuthMetadataInterceptor(self.auth_token))
            else:
                # Expected in dev mode — the sidecar can run without auth
                # for local development. In production, set AIKGS_AUTH_TOKEN.
                logger.warning(
                    "AIKGS_AUTH_TOKEN not set — expected in dev mode; "
                    "set AIKGS_AUTH_TOKEN in .env for production"
                )
            self.channel = grpc.aio.insecure_channel(
                self.grpc_addr, interceptors=interceptors
            )
            self.stub = aikgs_pb2_grpc.AikgsServiceStub(self.channel)
            # Quick health probe — try GetRewardStats
            await self.stub.GetRewardStats(
                aikgs_pb2.Empty(), timeout=self._grpc_timeout
            )
            self._connected = True
            logger.info(f"AIKGS sidecar connected at {self.grpc_addr}")
            return True
        except Exception as e:
            logger.warning(f"AIKGS sidecar not reachable at {self.grpc_addr}: {e}")
            self._connected = False
            return False

    async def close(self) -> None:
        """Close the gRPC channel to the Rust sidecar."""
        if self.channel:
            await self.channel.close()
            self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    # ================================================================
    # Circuit Breaker
    # ================================================================

    def _cb_is_open(self) -> bool:
        """Check if circuit breaker is open (blocking calls)."""
        if self._cb_failures < self.CB_FAILURE_THRESHOLD:
            return False
        elapsed = time.monotonic() - self._cb_open_since
        if elapsed >= self.CB_COOLDOWN_SECONDS:
            # Half-open: allow one probe
            return False
        return True

    def _cb_record_success(self) -> None:
        """Reset circuit breaker on success."""
        if self._cb_failures > 0:
            logger.info(
                f"AIKGS circuit breaker closed after {self._cb_failures} failures"
            )
        self._cb_failures = 0

    def _cb_record_failure(self, method: str, elapsed: float, error: str) -> None:
        """Record a failure. Open circuit if threshold reached."""
        self._cb_failures += 1
        if self._cb_failures >= self.CB_FAILURE_THRESHOLD:
            self._cb_open_since = time.monotonic()
            self._cb_total_trips += 1
            logger.warning(
                f"AIKGS circuit breaker OPEN (trip #{self._cb_total_trips}) "
                f"after {self._cb_failures} failures — "
                f"last: {method} ({elapsed:.1f}s): {error}. "
                f"Cooling down {self.CB_COOLDOWN_SECONDS}s"
            )

    async def _guarded_call(self, method_name: str, coro: Any) -> Any:
        """Execute a gRPC call with circuit breaker + timing."""
        if self._cb_is_open():
            raise RuntimeError(
                f"AIKGS circuit breaker open — skipping {method_name} "
                f"(cooldown {self.CB_COOLDOWN_SECONDS - (time.monotonic() - self._cb_open_since):.0f}s remaining)"
            )
        t0 = time.monotonic()
        try:
            result = await coro
            elapsed = time.monotonic() - t0
            if elapsed > self.CB_SLOW_THRESHOLD:
                self._cb_record_failure(method_name, elapsed, f"slow ({elapsed:.1f}s)")
                logger.warning(f"AIKGS {method_name} slow: {elapsed:.1f}s")
            else:
                self._cb_record_success()
            return result
        except Exception as e:
            elapsed = time.monotonic() - t0
            self._cb_record_failure(method_name, elapsed, str(e))
            raise

    # ================================================================
    # Contributions
    # ================================================================

    async def process_contribution(
        self,
        contributor_address: str,
        content: str,
        metadata: Optional[Dict[str, str]] = None,
        bounty_id: int = 0,
    ) -> Dict[str, Any]:
        """Submit a knowledge contribution to the Rust gRPC sidecar.

        Returns contribution record dict with scoring and reward info.
        """
        req = aikgs_pb2.ContributeRequest(
            contributor_address=contributor_address,
            content=content,
            metadata=metadata or {},
            bounty_id=bounty_id,
        )
        resp = await self._guarded_call("ProcessContribution", self.stub.ProcessContribution(req))
        result = _contribution_to_dict(resp)
        # Validate expected fields in response
        if 'contribution_id' not in result or 'quality_score' not in result:
            logger.warning(
                "ProcessContribution response missing expected fields "
                "(contribution_id, quality_score)"
            )
        return result

    async def get_contribution(self, contribution_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific contribution by ID from the Rust gRPC sidecar."""
        try:
            resp = await self._guarded_call("GetContribution", self.stub.GetContribution(
                aikgs_pb2.GetContributionRequest(contribution_id=contribution_id)
            ))
            return _contribution_to_dict(resp)
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise

    async def get_contributor_history(self, address: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get contribution history for an address from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetContributorHistory", self.stub.GetContributorHistory(
            aikgs_pb2.ContributorHistoryRequest(address=address, limit=limit)
        ))
        return [_contribution_to_dict(c) for c in resp.contributions]

    async def get_leaderboard(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get contribution leaderboard from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetContributionLeaderboard", self.stub.GetContributionLeaderboard(
            aikgs_pb2.LeaderboardRequest(limit=limit)
        ))
        return [
            {
                "address": e.address,
                "total_reward": e.total_reward,
                "contribution_count": e.contribution_count,
                "avg_quality": e.avg_quality,
                "best_tier": e.best_tier,
            }
            for e in resp.entries
        ]

    async def get_contribution_stats(self) -> Dict[str, Any]:
        """Get aggregate contribution statistics from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetContributionStats", self.stub.GetContributionStats(aikgs_pb2.Empty()))
        return {
            "total_contributions": resp.total_contributions,
            "unique_contributors": resp.unique_contributors,
            "total_rewards_distributed": resp.total_rewards_distributed,
            "tier_distribution": dict(resp.tier_distribution),
            "bounty_fulfillments": resp.bounty_fulfillments,
        }

    # ================================================================
    # Rewards
    # ================================================================

    async def get_reward_stats(self) -> Dict[str, Any]:
        """Get reward pool statistics from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetRewardStats", self.stub.GetRewardStats(aikgs_pb2.Empty()))
        result = {
            "pool_balance": resp.pool_balance,
            "total_distributed": resp.total_distributed,
            "distribution_count": resp.distribution_count,
            "total_contributions": resp.total_contributions,
            "base_reward": resp.base_reward,
            "max_reward": resp.max_reward,
            "early_threshold": resp.early_threshold,
            "contributors_with_streaks": resp.contributors_with_streaks,
        }
        # Validate expected fields in response
        if not hasattr(resp, 'pool_balance') or not hasattr(resp, 'total_distributed'):
            logger.warning(
                "GetRewardStats response missing expected fields "
                "(pool_balance, total_distributed)"
            )
        return result

    async def get_contributor_streak(self, address: str) -> Dict[str, Any]:
        """Get streak info for an address from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetContributorStreak", self.stub.GetContributorStreak(
            aikgs_pb2.StreakRequest(address=address)
        ))
        return {
            "streak_days": resp.streak_days,
            "multiplier": resp.multiplier,
            "next_milestone": resp.next_milestone,
        }

    # ================================================================
    # Affiliates
    # ================================================================

    async def register_affiliate(
        self, address: str, referral_code: str = "", referrer_address: str = ""
    ) -> Dict[str, Any]:
        """Register an affiliate via the Rust gRPC sidecar."""
        resp = await self._guarded_call("RegisterAffiliate", self.stub.RegisterAffiliate(
            aikgs_pb2.RegisterAffiliateRequest(
                address=address,
                referral_code=referral_code,
                referrer_address=referrer_address,
            )
        ))
        return _affiliate_to_dict(resp)

    async def get_affiliate(self, address: str) -> Optional[Dict[str, Any]]:
        """Get affiliate info from the Rust gRPC sidecar."""
        try:
            resp = await self._guarded_call("GetAffiliate", self.stub.GetAffiliate(
                aikgs_pb2.GetAffiliateRequest(address=address)
            ))
            return _affiliate_to_dict(resp)
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise

    async def get_affiliate_link(self, address: str) -> Optional[Dict[str, Any]]:
        """Get affiliate referral link from the Rust gRPC sidecar."""
        try:
            resp = await self._guarded_call("GetAffiliateLink", self.stub.GetAffiliateLink(
                aikgs_pb2.AffiliateLinkRequest(address=address)
            ))
            return {
                "referral_link": resp.referral_link,
                "referral_code": resp.referral_code,
            }
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise

    async def get_affiliate_stats(self) -> Dict[str, Any]:
        """Get aggregate affiliate statistics from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetAffiliateStats", self.stub.GetAffiliateStats(aikgs_pb2.Empty()))
        return {
            "total_affiliates": resp.total_affiliates,
            "total_l1_commissions": resp.total_l1_commissions,
            "total_l2_commissions": resp.total_l2_commissions,
        }

    # ================================================================
    # Bounties
    # ================================================================

    async def create_bounty(
        self, domain: str, description: str, reward_amount: float,
        gap_hash: str = "", duration_secs: int = 0, boost_multiplier: float = 1.0,
    ) -> Dict[str, Any]:
        """Create a new bounty via the Rust gRPC sidecar."""
        resp = await self._guarded_call("CreateBounty", self.stub.CreateBounty(
            aikgs_pb2.CreateBountyRequest(
                domain=domain, description=description, gap_hash=gap_hash,
                reward_amount=reward_amount, duration_secs=duration_secs,
                boost_multiplier=boost_multiplier,
            )
        ))
        return _bounty_to_dict(resp)

    async def list_bounties(
        self, status: str = "open", domain: str = "", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List bounties from the Rust gRPC sidecar."""
        resp = await self._guarded_call("ListBounties", self.stub.ListBounties(
            aikgs_pb2.ListBountiesRequest(domain=domain, status=status, limit=limit)
        ))
        return [_bounty_to_dict(b) for b in resp.bounties]

    async def claim_bounty(self, bounty_id: int, claimer_address: str) -> Dict[str, Any]:
        """Claim a bounty via the Rust gRPC sidecar."""
        resp = await self._guarded_call("ClaimBounty", self.stub.ClaimBounty(
            aikgs_pb2.ClaimBountyRequest(bounty_id=bounty_id, claimer_address=claimer_address)
        ))
        return _bounty_to_dict(resp)

    async def fulfill_bounty(
        self, bounty_id: int, contribution_id: int, contributor_address: str
    ) -> Dict[str, Any]:
        """Fulfill a bounty with a contribution via the Rust gRPC sidecar."""
        resp = await self._guarded_call("FulfillBounty", self.stub.FulfillBounty(
            aikgs_pb2.FulfillBountyRequest(
                bounty_id=bounty_id, contribution_id=contribution_id,
                contributor_address=contributor_address,
            )
        ))
        return {"reward_amount": resp.reward_amount}

    async def get_bounty_stats(self) -> Dict[str, Any]:
        """Get aggregate bounty statistics from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetBountyStats", self.stub.GetBountyStats(aikgs_pb2.Empty()))
        return {
            "total_bounties": resp.total_bounties,
            "open_bounties": resp.open_bounties,
            "fulfilled_bounties": resp.fulfilled_bounties,
            "total_reward_pool": resp.total_reward_pool,
        }

    # ================================================================
    # Profiles / Progressive Unlocks
    # ================================================================

    async def get_profile(self, address: str) -> Optional[Dict[str, Any]]:
        """Get contributor profile from the Rust gRPC sidecar."""
        try:
            resp = await self._guarded_call("GetProfile", self.stub.GetProfile(
                aikgs_pb2.ProfileRequest(address=address)
            ))
            return _profile_to_dict(resp)
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise

    async def has_feature(self, address: str, feature: str) -> bool:
        """Check if a contributor has unlocked a feature via the Rust gRPC sidecar."""
        resp = await self._guarded_call("HasFeature", self.stub.HasFeature(
            aikgs_pb2.HasFeatureRequest(address=address, feature=feature)
        ))
        return resp.has_feature

    async def get_unlocks_leaderboard(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get unlocks leaderboard from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetUnlocksLeaderboard", self.stub.GetUnlocksLeaderboard(
            aikgs_pb2.UnlocksLeaderboardRequest(limit=limit)
        ))
        return [_profile_to_dict(p) for p in resp.profiles]

    async def get_unlocks_stats(self) -> Dict[str, Any]:
        """Get unlock statistics from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetUnlocksStats", self.stub.GetUnlocksStats(aikgs_pb2.Empty()))
        return {
            "total_profiles": resp.total_profiles,
            "global_contributions": resp.global_contributions,
            "level_distribution": dict(resp.level_distribution),
            "total_badges_awarded": resp.total_badges_awarded,
        }

    # ================================================================
    # Curation
    # ================================================================

    async def submit_for_curation(self, contribution_id: int) -> Dict[str, Any]:
        """Submit a contribution for curation via the Rust gRPC sidecar."""
        resp = await self._guarded_call("SubmitForCuration", self.stub.SubmitForCuration(
            aikgs_pb2.SubmitForCurationRequest(contribution_id=contribution_id)
        ))
        return _curation_round_to_dict(resp)

    async def submit_review(
        self, contribution_id: int, curator_address: str, vote: bool, comment: str = ""
    ) -> Dict[str, Any]:
        """Submit a curation review/vote via the Rust gRPC sidecar."""
        resp = await self._guarded_call("SubmitReview", self.stub.SubmitReview(
            aikgs_pb2.SubmitReviewRequest(
                contribution_id=contribution_id, curator_address=curator_address,
                vote=vote, comment=comment,
            )
        ))
        return _curation_round_to_dict(resp)

    async def get_pending_reviews(self, curator_address: str = "") -> List[Dict[str, Any]]:
        """Get pending curation rounds from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetPendingReviews", self.stub.GetPendingReviews(
            aikgs_pb2.PendingReviewsRequest(curator_address=curator_address)
        ))
        return [_curation_round_to_dict(r) for r in resp.rounds]

    async def get_curation_round(self, contribution_id: int) -> Optional[Dict[str, Any]]:
        """Get a curation round for a contribution from the Rust gRPC sidecar."""
        try:
            resp = await self._guarded_call("GetCurationRound", self.stub.GetCurationRound(
                aikgs_pb2.GetCurationRoundRequest(contribution_id=contribution_id)
            ))
            return _curation_round_to_dict(resp)
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise

    async def get_curator_stats(self, address: str) -> Dict[str, Any]:
        """Get stats for a curator from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetCuratorStats", self.stub.GetCuratorStats(
            aikgs_pb2.CuratorStatsRequest(address=address)
        ))
        return {
            "address": resp.address,
            "reputation": resp.reputation,
            "total_reviews": resp.total_reviews,
            "correct_votes": resp.correct_votes,
            "accuracy": resp.accuracy,
        }

    async def get_curation_stats(self) -> Dict[str, Any]:
        """Get aggregate curation statistics from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetCurationStats", self.stub.GetCurationStats(aikgs_pb2.Empty()))
        return {
            "total_rounds": resp.total_rounds,
            "status_distribution": dict(resp.status_distribution),
            "total_curators": resp.total_curators,
            "avg_reputation": resp.avg_reputation,
        }

    # ================================================================
    # API Key Vault
    # ================================================================

    async def store_api_key(
        self, owner_address: str, provider: str, api_key: str,
        model: str = "", is_shared: bool = False,
        shared_reward_bps: int = 0, label: str = "",
    ) -> Dict[str, Any]:
        """Store an API key in the vault via the Rust gRPC sidecar."""
        resp = await self._guarded_call("StoreApiKey", self.stub.StoreApiKey(
            aikgs_pb2.StoreKeyRequest(
                provider=provider, api_key=api_key, owner_address=owner_address,
                model=model, is_shared=is_shared,
                shared_reward_bps=shared_reward_bps, label=label,
            )
        ))
        return _key_info_to_dict(resp.key_info) if resp.key_info else {}

    async def get_api_key(self, key_id: str, owner_address: str = "") -> Optional[Dict[str, Any]]:
        """Get and decrypt an API key via the Rust gRPC sidecar."""
        try:
            metadata = []
            if owner_address:
                metadata.append(("x-owner-address", owner_address))
            resp = await self._guarded_call("GetApiKey", self.stub.GetApiKey(
                aikgs_pb2.GetKeyRequest(key_id=key_id),
                metadata=metadata if metadata else None,
            ))
            return {
                "key_id": resp.key_id,
                "provider": resp.provider,
                "api_key": resp.api_key,
            }
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise

    async def list_api_keys(self, owner_address: str) -> List[Dict[str, Any]]:
        """List API keys for an owner via the Rust gRPC sidecar."""
        resp = await self._guarded_call("ListApiKeys", self.stub.ListApiKeys(
            aikgs_pb2.ListKeysRequest(owner_address=owner_address)
        ))
        return [_key_info_to_dict(k) for k in resp.keys]

    async def revoke_api_key(self, key_id: str, owner_address: str) -> bool:
        """Revoke an API key via the Rust gRPC sidecar."""
        resp = await self._guarded_call("RevokeApiKey", self.stub.RevokeApiKey(
            aikgs_pb2.RevokeKeyRequest(key_id=key_id, owner_address=owner_address)
        ))
        return resp.ok

    async def get_shared_key_pool(self, provider: str = "") -> List[Dict[str, Any]]:
        """Get shared API key pool from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetSharedKeyPool", self.stub.GetSharedKeyPool(
            aikgs_pb2.SharedPoolRequest(provider=provider)
        ))
        return [_key_info_to_dict(k) for k in resp.keys]

    # ================================================================
    # Aggregate Stats
    # ================================================================

    async def get_full_stats(self) -> Dict[str, Any]:
        """Get full AIKGS statistics (all subsystems) from the Rust gRPC sidecar."""
        resp = await self._guarded_call("GetFullStats", self.stub.GetFullStats(aikgs_pb2.Empty()))
        result: Dict[str, Any] = {}
        if resp.contributions:
            result["contributions"] = {
                "total_contributions": resp.contributions.total_contributions,
                "unique_contributors": resp.contributions.unique_contributors,
                "total_rewards_distributed": resp.contributions.total_rewards_distributed,
                "tier_distribution": dict(resp.contributions.tier_distribution),
            }
        if resp.rewards:
            result["rewards"] = {
                "pool_balance": resp.rewards.pool_balance,
                "total_distributed": resp.rewards.total_distributed,
            }
        if resp.affiliates:
            result["affiliates"] = {
                "total_affiliates": resp.affiliates.total_affiliates,
                "total_l1_commissions": resp.affiliates.total_l1_commissions,
                "total_l2_commissions": resp.affiliates.total_l2_commissions,
            }
        if resp.bounties:
            result["bounties"] = {
                "total_bounties": resp.bounties.total_bounties,
                "open_bounties": resp.bounties.open_bounties,
                "fulfilled_bounties": resp.bounties.fulfilled_bounties,
            }
        if resp.unlocks:
            result["unlocks"] = {
                "total_profiles": resp.unlocks.total_profiles,
                "level_distribution": dict(resp.unlocks.level_distribution),
            }
        if resp.curation:
            result["curation"] = {
                "total_rounds": resp.curation.total_rounds,
                "status_distribution": dict(resp.curation.status_distribution),
            }
        return result


# ════════════════════════════════════════════════════════════════════════
# Protobuf → dict converters
# ════════════════════════════════════════════════════════════════════════


def _contribution_to_dict(c: Any) -> Dict[str, Any]:
    return {
        "contribution_id": c.contribution_id,
        "contributor_address": c.contributor_address,
        "content_hash": c.content_hash,
        "knowledge_node_id": c.knowledge_node_id,
        "quality_score": c.quality_score,
        "novelty_score": c.novelty_score,
        "combined_score": c.combined_score,
        "tier": c.tier,
        "domain": c.domain,
        "reward_amount": c.reward_amount,
        "affiliate_l1_amount": c.affiliate_l1_amount,
        "affiliate_l2_amount": c.affiliate_l2_amount,
        "is_bounty_fulfillment": c.is_bounty_fulfillment,
        "bounty_id": c.bounty_id,
        "badges_earned": list(c.badges_earned),
        "block_height": c.block_height,
        "timestamp": c.timestamp,
        "status": c.status,
    }


def _affiliate_to_dict(a: Any) -> Dict[str, Any]:
    return {
        "address": a.address,
        "referrer_address": a.referrer_address,
        "referral_code": a.referral_code,
        "l1_referrals": a.l1_referrals,
        "l2_referrals": a.l2_referrals,
        "total_l1_commission": a.total_l1_commission,
        "total_l2_commission": a.total_l2_commission,
        "is_active": a.is_active,
    }


def _bounty_to_dict(b: Any) -> Dict[str, Any]:
    return {
        "bounty_id": b.bounty_id,
        "domain": b.domain,
        "description": b.description,
        "gap_hash": b.gap_hash,
        "reward_amount": b.reward_amount,
        "boost_multiplier": b.boost_multiplier,
        "status": b.status,
        "claimer_address": b.claimer_address,
        "contribution_id": b.contribution_id,
        "created_at": b.created_at,
        "expires_at": b.expires_at,
    }


def _profile_to_dict(p: Any) -> Dict[str, Any]:
    return {
        "address": p.address,
        "reputation_points": p.reputation_points,
        "level": p.level,
        "level_name": p.level_name,
        "total_contributions": p.total_contributions,
        "best_streak": p.best_streak,
        "current_streak": p.current_streak,
        "gold_count": p.gold_count,
        "diamond_count": p.diamond_count,
        "bounties_fulfilled": p.bounties_fulfilled,
        "referrals": p.referrals,
        "badges": list(p.badges),
        "unlocked_features": list(p.unlocked_features),
        "last_contribution_at": p.last_contribution_at,
    }


def _curation_round_to_dict(r: Any) -> Dict[str, Any]:
    return {
        "contribution_id": r.contribution_id,
        "required_votes": r.required_votes,
        "votes_for": r.votes_for,
        "votes_against": r.votes_against,
        "reviews": [
            {
                "curator_address": rev.curator_address,
                "contribution_id": rev.contribution_id,
                "vote": rev.vote,
                "comment": rev.comment,
                "timestamp": rev.timestamp,
            }
            for rev in r.reviews
        ],
        "status": r.status,
        "finalized_at": r.finalized_at,
    }


def _key_info_to_dict(k: Any) -> Dict[str, Any]:
    return {
        "key_id": k.key_id,
        "provider": k.provider,
        "model": k.model,
        "owner_address": k.owner_address,
        "is_shared": k.is_shared,
        "shared_reward_bps": k.shared_reward_bps,
        "label": k.label,
        "use_count": k.use_count,
        "is_active": k.is_active,
    }
