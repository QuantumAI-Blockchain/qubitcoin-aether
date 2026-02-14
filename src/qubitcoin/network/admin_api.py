"""
Admin API — Hot-reload economic configuration

Authenticated endpoints for managing fee parameters, treasury addresses,
and oracle settings without restarting the node.

All changes are logged for audit trail. Auth via API key or Dilithium signature.
Rate limited: max 30 requests/minute per IP for admin endpoints.
"""
import collections
import time
import hashlib
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Audit log (in-memory; production should persist to DB)
_audit_log: list = []

# Admin-specific rate limiting (stricter than global)
_admin_rate_limit: dict = {
    'requests': collections.defaultdict(list),  # ip -> [timestamps]
    'max_per_minute': 30,
}


# ========================================================================
# AUTH + RATE LIMITING
# ========================================================================

def _check_admin_rate_limit(request: Request) -> None:
    """Enforce stricter rate limiting on admin endpoints (30 req/min)."""
    client_ip = request.client.host if request.client else 'unknown'
    now = time.time()
    window = 60.0

    timestamps = _admin_rate_limit['requests'][client_ip]
    _admin_rate_limit['requests'][client_ip] = [
        t for t in timestamps if now - t < window
    ]

    if len(_admin_rate_limit['requests'][client_ip]) >= _admin_rate_limit['max_per_minute']:
        logger.warning(f"Admin rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Admin rate limit exceeded (30/min). Try again later.",
        )

    _admin_rate_limit['requests'][client_ip].append(now)


def _verify_admin(api_key: Optional[str] = None) -> bool:
    """Verify admin auth via API key.

    Production: replace with Dilithium signature verification.
    """
    admin_key = Config.ADMIN_API_KEY if hasattr(Config, "ADMIN_API_KEY") else None
    if not admin_key:
        # No key configured — reject all admin calls
        return False
    return api_key == admin_key


def _require_admin(x_api_key: Optional[str] = Header(None)) -> None:
    if not _verify_admin(x_api_key):
        raise HTTPException(status_code=403, detail="Admin authentication required")


def _audit(action: str, params: dict) -> None:
    entry = {
        "action": action,
        "params": params,
        "timestamp": time.time(),
    }
    _audit_log.append(entry)
    # Keep last 1000 entries
    if len(_audit_log) > 1000:
        _audit_log.pop(0)
    logger.info(f"Admin action: {action} — {params}")


# ========================================================================
# MODELS
# ========================================================================

class AetherFeeUpdate(BaseModel):
    chat_fee_qbc: Optional[str] = None
    chat_fee_usd_target: Optional[float] = None
    pricing_mode: Optional[str] = None
    min_qbc: Optional[str] = None
    max_qbc: Optional[str] = None
    update_interval: Optional[int] = None
    query_multiplier: Optional[float] = None
    free_tier_messages: Optional[int] = None
    treasury_address: Optional[str] = None


class ContractFeeUpdate(BaseModel):
    base_fee_qbc: Optional[str] = None
    per_kb_fee_qbc: Optional[str] = None
    usd_target: Optional[float] = None
    pricing_mode: Optional[str] = None
    execute_base_fee: Optional[str] = None
    template_discount: Optional[float] = None
    treasury_address: Optional[str] = None


class TreasuryUpdate(BaseModel):
    aether_treasury: Optional[str] = None
    contract_treasury: Optional[str] = None


# ========================================================================
# ENDPOINTS
# ========================================================================

@router.get("/economics")
async def get_economics(x_api_key: Optional[str] = Header(None)):
    """Get current economic configuration (no auth required for read)."""
    return {
        "aether_fees": {
            "chat_fee_qbc": str(Config.AETHER_CHAT_FEE_QBC),
            "chat_fee_usd_target": Config.AETHER_CHAT_FEE_USD_TARGET,
            "pricing_mode": Config.AETHER_FEE_PRICING_MODE,
            "min_qbc": str(Config.AETHER_FEE_MIN_QBC),
            "max_qbc": str(Config.AETHER_FEE_MAX_QBC),
            "update_interval": Config.AETHER_FEE_UPDATE_INTERVAL,
            "query_multiplier": Config.AETHER_QUERY_FEE_MULTIPLIER,
            "free_tier_messages": Config.AETHER_FREE_TIER_MESSAGES,
            "treasury_address": Config.AETHER_FEE_TREASURY_ADDRESS,
        },
        "contract_fees": {
            "base_fee_qbc": str(Config.CONTRACT_DEPLOY_BASE_FEE_QBC),
            "per_kb_fee_qbc": str(Config.CONTRACT_DEPLOY_PER_KB_FEE_QBC),
            "usd_target": Config.CONTRACT_DEPLOY_FEE_USD_TARGET,
            "pricing_mode": Config.CONTRACT_FEE_PRICING_MODE,
            "execute_base_fee": str(Config.CONTRACT_EXECUTE_BASE_FEE_QBC),
            "template_discount": Config.CONTRACT_TEMPLATE_DISCOUNT,
            "treasury_address": Config.CONTRACT_FEE_TREASURY_ADDRESS,
        },
        "chain": {
            "chain_id": Config.CHAIN_ID,
            "block_gas_limit": Config.BLOCK_GAS_LIMIT,
            "max_supply": str(Config.MAX_SUPPLY),
            "phi": Config.PHI,
        },
    }


@router.put("/aether/fees")
async def update_aether_fees(
    request: Request,
    body: AetherFeeUpdate,
    x_api_key: Optional[str] = Header(None),
):
    """Update Aether Tree fee parameters (hot reload)."""
    _check_admin_rate_limit(request)
    _require_admin(x_api_key)
    changes = {}

    if body.chat_fee_qbc is not None:
        Config.AETHER_CHAT_FEE_QBC = Decimal(body.chat_fee_qbc)
        changes["chat_fee_qbc"] = body.chat_fee_qbc

    if body.chat_fee_usd_target is not None:
        Config.AETHER_CHAT_FEE_USD_TARGET = body.chat_fee_usd_target
        changes["chat_fee_usd_target"] = body.chat_fee_usd_target

    if body.pricing_mode is not None:
        if body.pricing_mode not in ("qusd_peg", "fixed_qbc", "direct_usd"):
            raise HTTPException(400, "Invalid pricing_mode")
        Config.AETHER_FEE_PRICING_MODE = body.pricing_mode
        changes["pricing_mode"] = body.pricing_mode

    if body.min_qbc is not None:
        Config.AETHER_FEE_MIN_QBC = Decimal(body.min_qbc)
        changes["min_qbc"] = body.min_qbc

    if body.max_qbc is not None:
        Config.AETHER_FEE_MAX_QBC = Decimal(body.max_qbc)
        changes["max_qbc"] = body.max_qbc

    if body.update_interval is not None:
        Config.AETHER_FEE_UPDATE_INTERVAL = body.update_interval
        changes["update_interval"] = body.update_interval

    if body.query_multiplier is not None:
        Config.AETHER_QUERY_FEE_MULTIPLIER = body.query_multiplier
        changes["query_multiplier"] = body.query_multiplier

    if body.free_tier_messages is not None:
        Config.AETHER_FREE_TIER_MESSAGES = body.free_tier_messages
        changes["free_tier_messages"] = body.free_tier_messages

    if body.treasury_address is not None:
        Config.AETHER_FEE_TREASURY_ADDRESS = body.treasury_address
        changes["treasury_address"] = body.treasury_address

    if not changes:
        raise HTTPException(400, "No parameters provided")

    # Validate min < max
    if Config.AETHER_FEE_MIN_QBC >= Config.AETHER_FEE_MAX_QBC:
        raise HTTPException(400, "min_qbc must be less than max_qbc")

    _audit("update_aether_fees", changes)
    return {"updated": changes}


@router.put("/contract/fees")
async def update_contract_fees(
    request: Request,
    body: ContractFeeUpdate,
    x_api_key: Optional[str] = Header(None),
):
    """Update contract deployment fee parameters (hot reload)."""
    _check_admin_rate_limit(request)
    _require_admin(x_api_key)
    changes = {}

    if body.base_fee_qbc is not None:
        Config.CONTRACT_DEPLOY_BASE_FEE_QBC = Decimal(body.base_fee_qbc)
        changes["base_fee_qbc"] = body.base_fee_qbc

    if body.per_kb_fee_qbc is not None:
        Config.CONTRACT_DEPLOY_PER_KB_FEE_QBC = Decimal(body.per_kb_fee_qbc)
        changes["per_kb_fee_qbc"] = body.per_kb_fee_qbc

    if body.usd_target is not None:
        Config.CONTRACT_DEPLOY_FEE_USD_TARGET = body.usd_target
        changes["usd_target"] = body.usd_target

    if body.pricing_mode is not None:
        if body.pricing_mode not in ("qusd_peg", "fixed_qbc", "direct_usd"):
            raise HTTPException(400, "Invalid pricing_mode")
        Config.CONTRACT_FEE_PRICING_MODE = body.pricing_mode
        changes["pricing_mode"] = body.pricing_mode

    if body.execute_base_fee is not None:
        Config.CONTRACT_EXECUTE_BASE_FEE_QBC = Decimal(body.execute_base_fee)
        changes["execute_base_fee"] = body.execute_base_fee

    if body.template_discount is not None:
        if not 0 <= body.template_discount <= 1:
            raise HTTPException(400, "template_discount must be 0-1")
        Config.CONTRACT_TEMPLATE_DISCOUNT = body.template_discount
        changes["template_discount"] = body.template_discount

    if body.treasury_address is not None:
        Config.CONTRACT_FEE_TREASURY_ADDRESS = body.treasury_address
        changes["treasury_address"] = body.treasury_address

    if not changes:
        raise HTTPException(400, "No parameters provided")

    _audit("update_contract_fees", changes)
    return {"updated": changes}


@router.put("/treasury")
async def update_treasury(
    request: Request,
    body: TreasuryUpdate,
    x_api_key: Optional[str] = Header(None),
):
    """Update treasury addresses."""
    _check_admin_rate_limit(request)
    _require_admin(x_api_key)
    changes = {}

    if body.aether_treasury is not None:
        Config.AETHER_FEE_TREASURY_ADDRESS = body.aether_treasury
        changes["aether_treasury"] = body.aether_treasury

    if body.contract_treasury is not None:
        Config.CONTRACT_FEE_TREASURY_ADDRESS = body.contract_treasury
        changes["contract_treasury"] = body.contract_treasury

    if not changes:
        raise HTTPException(400, "No parameters provided")

    _audit("update_treasury", changes)
    return {"updated": changes}


@router.get("/economics/history")
async def get_economics_history(
    request: Request,
    limit: int = 50,
    x_api_key: Optional[str] = Header(None),
):
    """Get audit log of economic parameter changes."""
    _check_admin_rate_limit(request)
    _require_admin(x_api_key)
    return {"history": _audit_log[-limit:]}
