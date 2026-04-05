"""
Dilithium5 → JWT authentication for the Aether API.

Flow:
  1. Client requests a challenge:  GET /auth/challenge?address=<qbc_address>
  2. Server returns { nonce, timestamp, message } (valid 5 minutes)
  3. Client signs `message` with their Dilithium5 private key
  4. Client authenticates:  POST /auth/authenticate  { public_key, signature, message }
  5. Server verifies signature, derives address, issues JWT (24h expiry)
  6. Subsequent requests use  Authorization: Bearer <jwt>
"""

import hashlib
import os
import secrets
import time
from typing import Dict, Optional, Tuple

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from ..config import Config
from ..quantum.crypto import DilithiumSigner
from ..utils.logger import get_logger

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
CHALLENGE_TTL_SECONDS = 300  # 5 minutes to sign a challenge
TOKEN_EXPIRY_SECONDS = 86400  # 24 hours


def _get_jwt_secret() -> str:
    """Return the JWT signing secret.  Falls back to a per-process ephemeral
    secret if JWT_SECRET is not set (tokens won't survive restarts)."""
    secret = Config.JWT_SECRET
    if not secret:
        if not hasattr(_get_jwt_secret, "_ephemeral"):
            _get_jwt_secret._ephemeral = secrets.token_hex(32)  # type: ignore[attr-defined]
            logger.warning(
                "JWT_SECRET not set — using ephemeral secret. "
                "Tokens will NOT survive node restarts. "
                "Set JWT_SECRET in .env for production."
            )
        return _get_jwt_secret._ephemeral  # type: ignore[attr-defined]
    return secret


# ── In-memory challenge store ────────────────────────────────────────────
# Maps address → (nonce, timestamp).  Evicted on use or expiry.
_challenge_store: Dict[str, Tuple[str, float]] = {}
_CHALLENGE_STORE_MAX = 10_000  # prevent unbounded growth


def _evict_expired_challenges() -> None:
    """Remove challenges older than TTL (called on every new challenge)."""
    now = time.time()
    expired = [
        addr for addr, (_, ts) in _challenge_store.items()
        if now - ts > CHALLENGE_TTL_SECONDS
    ]
    for addr in expired:
        del _challenge_store[addr]


# ── Request / response models ───────────────────────────────────────────

class ChallengeResponse(BaseModel):
    address: str
    nonce: str
    timestamp: int
    message: str = Field(description="Sign this exact string with your Dilithium5 private key")


class AuthenticateRequest(BaseModel):
    public_key_hex: str = Field(description="Hex-encoded Dilithium5 public key")
    signature_hex: str = Field(description="Hex-encoded signature of the challenge message")
    message: str = Field(description="The exact challenge message that was signed")


class AuthenticateResponse(BaseModel):
    token: str
    address: str
    expires_at: int = Field(description="Unix timestamp when the token expires")


class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: str  # QBC address
    exp: int  # expiry (unix)
    iat: int  # issued at (unix)


# ── Core functions ───────────────────────────────────────────────────────

def create_challenge(address: str) -> ChallengeResponse:
    """Generate a fresh challenge for the given QBC address."""
    address = address.lower().strip()
    if not address or len(address) != 40:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QBC address (expected 40 hex chars)",
        )

    _evict_expired_challenges()

    # Cap store size to prevent memory exhaustion from unauthenticated requests
    if len(_challenge_store) >= _CHALLENGE_STORE_MAX:
        # Drop oldest half
        sorted_entries = sorted(_challenge_store.items(), key=lambda kv: kv[1][1])
        for addr, _ in sorted_entries[: len(sorted_entries) // 2]:
            del _challenge_store[addr]

    nonce = secrets.token_hex(32)
    ts = int(time.time())
    message = f"qbc-auth:{address}:{nonce}:{ts}"

    _challenge_store[address] = (nonce, float(ts))
    logger.debug("Auth challenge issued for %s", address)

    return ChallengeResponse(address=address, nonce=nonce, timestamp=ts, message=message)


def authenticate(req: AuthenticateRequest) -> AuthenticateResponse:
    """Verify a Dilithium5 signature and issue a JWT."""
    # ── Parse inputs ──────────────────────────────────────────────────
    try:
        public_key = bytes.fromhex(req.public_key_hex)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="public_key_hex is not valid hex",
        )

    try:
        signature = bytes.fromhex(req.signature_hex)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="signature_hex is not valid hex",
        )

    # ── Parse challenge message ───────────────────────────────────────
    parts = req.message.split(":")
    if len(parts) != 4 or parts[0] != "qbc-auth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed challenge message",
        )
    claimed_address = parts[1]
    claimed_nonce = parts[2]
    try:
        claimed_ts = int(parts[3])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed challenge timestamp",
        )

    # ── Verify challenge exists and hasn't expired ────────────────────
    stored = _challenge_store.get(claimed_address)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No pending challenge for this address (expired or never issued)",
        )

    stored_nonce, stored_ts = stored
    if stored_nonce != claimed_nonce or int(stored_ts) != claimed_ts:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Challenge nonce/timestamp mismatch",
        )

    if time.time() - stored_ts > CHALLENGE_TTL_SECONDS:
        del _challenge_store[claimed_address]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Challenge expired — request a new one",
        )

    # Consume the challenge (one-time use)
    del _challenge_store[claimed_address]

    # ── Verify Dilithium5 signature ───────────────────────────────────
    message_bytes = req.message.encode("utf-8")
    try:
        valid = DilithiumSigner.verify(public_key, message_bytes, signature)
    except Exception as e:
        logger.warning("Dilithium verify error for %s: %s", claimed_address, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature verification failed",
        )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # ── Derive address from public key and verify it matches ──────────
    derived_address = DilithiumSigner.derive_address(public_key)
    if derived_address != claimed_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Public key does not match claimed address",
        )

    # ── Issue JWT ─────────────────────────────────────────────────────
    now = int(time.time())
    expires_at = now + TOKEN_EXPIRY_SECONDS
    payload = {
        "sub": derived_address,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)
    logger.info("JWT issued for %s (expires %d)", derived_address, expires_at)

    return AuthenticateResponse(token=token, address=derived_address, expires_at=expires_at)


# ── FastAPI dependency for protected routes ──────────────────────────────

def verify_token(authorization: Optional[str] = Header(None, alias="Authorization")) -> TokenPayload:
    """FastAPI dependency — extracts and validates Bearer JWT.

    Usage in a route:
        @app.get("/aether/protected")
        async def protected(caller: TokenPayload = Depends(verify_token)):
            return {"address": caller.sub}
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])
        return TokenPayload(sub=payload["sub"], exp=payload["exp"], iat=payload["iat"])
    except JWTError as e:
        logger.debug("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def optional_verify_token(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[TokenPayload]:
    """FastAPI dependency — returns TokenPayload if a valid Bearer token is
    present, or None if no Authorization header is provided.  Useful for
    endpoints that work for anonymous users but unlock extra features for
    authenticated callers (e.g. higher rate limits, paid tier access)."""
    if not authorization:
        return None
    try:
        return verify_token(authorization)
    except HTTPException:
        return None
