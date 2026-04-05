"""
Per-wallet token-bucket rate limiter for the Aether API.

Uses Redis when available, falls back to in-memory counters.
Tier limits mirror the AetherAPISubscription.sol contract tiers.
"""

import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, status

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ── Tier definitions (mirrors AetherAPISubscription.sol) ─────────────────

class Tier(IntEnum):
    FREE = 0
    DEVELOPER = 1
    PROFESSIONAL = 2
    INSTITUTIONAL = 3


@dataclass(frozen=True)
class TierLimits:
    chat_per_day: int
    query_per_day: int
    ingest_per_day: int


TIER_LIMITS: Dict[Tier, TierLimits] = {
    Tier.FREE:          TierLimits(chat_per_day=5,     query_per_day=10,    ingest_per_day=0),
    Tier.DEVELOPER:     TierLimits(chat_per_day=1_000, query_per_day=500,   ingest_per_day=50),
    Tier.PROFESSIONAL:  TierLimits(chat_per_day=10_000, query_per_day=5_000, ingest_per_day=500),
    Tier.INSTITUTIONAL: TierLimits(chat_per_day=0,     query_per_day=0,     ingest_per_day=0),  # 0 = unlimited
}

# Anonymous callers (no JWT) get the Free tier limits
ANONYMOUS_TIER = Tier.FREE


# ── Redis-backed rate limiter ────────────────────────────────────────────

_redis_client = None
_redis_init_attempted = False


def _get_redis():
    """Lazy-init Redis client.  Returns None if Redis is unavailable."""
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client
    _redis_init_attempted = True
    try:
        import redis
        _redis_client = redis.Redis(
            host=Config.REDIS_HOST if hasattr(Config, 'REDIS_HOST') else 'localhost',
            port=int(getattr(Config, 'REDIS_PORT', 6379)),
            db=int(getattr(Config, 'REDIS_DB', 0)),
            password=getattr(Config, 'REDIS_PASSWORD', None) or None,
            socket_connect_timeout=2,
            decode_responses=True,
        )
        _redis_client.ping()
        logger.info("Rate limiter: Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning("Rate limiter: Redis unavailable (%s), using in-memory fallback", e)
        _redis_client = None
        return None


# ── In-memory fallback ───────────────────────────────────────────────────
# key → (count, window_start_ts)
_mem_store: Dict[str, Tuple[int, float]] = {}
_MEM_STORE_MAX = 50_000
_DAY_SECONDS = 86400


def _mem_check_and_increment(key: str, limit: int) -> Tuple[bool, int]:
    """Check rate limit in memory.  Returns (allowed, current_count)."""
    now = time.time()
    entry = _mem_store.get(key)
    if entry is None or now - entry[1] >= _DAY_SECONDS:
        _mem_store[key] = (1, now)
        # Evict old entries periodically
        if len(_mem_store) > _MEM_STORE_MAX:
            cutoff = now - _DAY_SECONDS
            expired = [k for k, (_, ts) in _mem_store.items() if ts < cutoff]
            for k in expired:
                del _mem_store[k]
        return True, 1
    count, window_start = entry
    if limit > 0 and count >= limit:
        return False, count
    _mem_store[key] = (count + 1, window_start)
    return True, count + 1


def _redis_check_and_increment(r, key: str, limit: int) -> Tuple[bool, int]:
    """Check rate limit in Redis using a daily sliding window."""
    count = r.incr(key)
    if count == 1:
        r.expire(key, _DAY_SECONDS)
    if limit > 0 and count > limit:
        return False, int(count)
    return True, int(count)


# ── Public API ───────────────────────────────────────────────────────────

def check_rate_limit(
    wallet_address: Optional[str],
    action: str,
    tier: Tier = ANONYMOUS_TIER,
) -> None:
    """Check whether the caller is within their daily rate limit.

    Args:
        wallet_address: Authenticated wallet address (None for anonymous).
        action: One of "chat", "query", "ingest".
        tier: The caller's subscription tier.

    Raises:
        HTTPException 429 if the rate limit is exceeded.
    """
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[Tier.FREE])

    if action == "chat":
        limit = limits.chat_per_day
    elif action == "query":
        limit = limits.query_per_day
    elif action == "ingest":
        limit = limits.ingest_per_day
    else:
        limit = limits.query_per_day  # default to query limits

    # Unlimited tier (0 means unlimited for Institutional)
    if tier == Tier.INSTITUTIONAL:
        return

    # Zero limit means no access for this action at this tier
    if limit == 0:
        tier_name = tier.name.lower()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"{action} is not available on the {tier_name} tier. Upgrade your subscription.",
            headers={"Retry-After": "3600"},
        )

    # Build the rate limit key
    identity = wallet_address or "anon"
    today = time.strftime("%Y%m%d", time.gmtime())
    key = f"aether_rl:{identity}:{action}:{today}"

    r = _get_redis()
    if r is not None:
        try:
            allowed, count = _redis_check_and_increment(r, key, limit)
        except Exception:
            # Redis error — fall through to memory
            allowed, count = _mem_check_and_increment(key, limit)
    else:
        allowed, count = _mem_check_and_increment(key, limit)

    if not allowed:
        tier_name = tier.name.lower()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily {action} limit reached ({limit}/{tier_name} tier). "
                f"Upgrade your subscription for higher limits."
            ),
            headers={"Retry-After": "3600"},
        )


def get_tier_for_wallet(wallet_address: Optional[str]) -> Tier:
    """Look up the subscription tier for a wallet.

    Currently returns FREE for all wallets.  Once AetherAPISubscription.sol
    is deployed and the contract reader is wired, this will query on-chain
    tier status.
    """
    # TODO: query AetherAPISubscription.sol via QVM or contract reader
    # For now, all authenticated users get Developer tier as early-access bonus
    if wallet_address:
        return Tier.DEVELOPER
    return Tier.FREE
