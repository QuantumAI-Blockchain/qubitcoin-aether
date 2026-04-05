"""Tests for per-wallet token-bucket rate limiter."""

import pytest
from fastapi import HTTPException

from qubitcoin.network.rate_limiter import (
    Tier,
    TierLimits,
    TIER_LIMITS,
    check_rate_limit,
    get_tier_for_wallet,
    _mem_store,
)


@pytest.fixture(autouse=True)
def _clear_mem_store():
    """Clear in-memory rate limit store before each test."""
    _mem_store.clear()
    yield
    _mem_store.clear()


# ── Tier definitions ──────────────────────────────────────────────────────

def test_tier_limits_defined():
    assert Tier.FREE in TIER_LIMITS
    assert Tier.DEVELOPER in TIER_LIMITS
    assert Tier.PROFESSIONAL in TIER_LIMITS
    assert Tier.INSTITUTIONAL in TIER_LIMITS


def test_free_tier_limits():
    limits = TIER_LIMITS[Tier.FREE]
    assert limits.chat_per_day >= 5  # env-configurable, defaults to 5
    assert limits.query_per_day >= 10
    assert limits.ingest_per_day == 0


def test_developer_tier_limits():
    limits = TIER_LIMITS[Tier.DEVELOPER]
    assert limits.chat_per_day == 1_000
    assert limits.query_per_day == 500


# ── Rate limit checks ────────────────────────────────────────────────────

def test_free_tier_allows_within_limit():
    """Free tier allows up to configured chat limit."""
    limit = TIER_LIMITS[Tier.FREE].chat_per_day
    for _ in range(limit):
        check_rate_limit(None, "chat", Tier.FREE)


def test_free_tier_blocks_over_limit():
    """Free tier blocks after exceeding configured chat limit."""
    limit = TIER_LIMITS[Tier.FREE].chat_per_day
    for _ in range(limit):
        check_rate_limit(None, "chat", Tier.FREE)
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(None, "chat", Tier.FREE)
    assert exc_info.value.status_code == 429


def test_free_tier_blocks_ingest():
    """Free tier cannot ingest (0 per day)."""
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(None, "ingest", Tier.FREE)
    assert exc_info.value.status_code == 429


def test_developer_tier_allows_more():
    """Developer tier allows 1000 chat messages."""
    wallet = "d" * 40
    for _ in range(100):  # just check 100 — no need to loop 1000
        check_rate_limit(wallet, "chat", Tier.DEVELOPER)


def test_institutional_unlimited():
    """Institutional tier is unlimited."""
    wallet = "e" * 40
    for _ in range(100):
        check_rate_limit(wallet, "chat", Tier.INSTITUTIONAL)
        check_rate_limit(wallet, "query", Tier.INSTITUTIONAL)
        check_rate_limit(wallet, "ingest", Tier.INSTITUTIONAL)


def test_different_wallets_independent():
    """Rate limits are per-wallet."""
    wallet_a = "a" * 40
    wallet_b = "b" * 40
    limit = TIER_LIMITS[Tier.FREE].chat_per_day
    for _ in range(limit):
        check_rate_limit(wallet_a, "chat", Tier.FREE)
    # wallet_a exhausted
    with pytest.raises(HTTPException):
        check_rate_limit(wallet_a, "chat", Tier.FREE)
    # wallet_b still has quota
    check_rate_limit(wallet_b, "chat", Tier.FREE)


def test_different_actions_independent():
    """Chat and query limits are independent."""
    limit = TIER_LIMITS[Tier.FREE].chat_per_day
    for _ in range(limit):
        check_rate_limit(None, "chat", Tier.FREE)
    # Chat exhausted, but query still works
    check_rate_limit(None, "query", Tier.FREE)


# ── Tier lookup ───────────────────────────────────────────────────────────

def test_get_tier_anonymous():
    assert get_tier_for_wallet(None) == Tier.FREE


def test_get_tier_authenticated():
    assert get_tier_for_wallet("f" * 40) == Tier.DEVELOPER
