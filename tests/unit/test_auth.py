"""Tests for Dilithium5 → JWT authentication module."""

import time

import pytest

from qubitcoin.network.auth import (
    AuthenticateRequest,
    ChallengeResponse,
    _challenge_store,
    _get_jwt_secret,
    authenticate,
    create_challenge,
    optional_verify_token,
    verify_token,
    CHALLENGE_TTL_SECONDS,
)
from qubitcoin.quantum.crypto import DilithiumSigner, SecurityLevel, DILITHIUM_AVAILABLE


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_challenge_store():
    """Clear the challenge store before each test."""
    _challenge_store.clear()
    yield
    _challenge_store.clear()


def _make_keypair():
    """Helper: generate a Dilithium5 keypair and return (pk_bytes, sk_bytes, address)."""
    signer = DilithiumSigner(SecurityLevel.LEVEL5)
    secure_sk, pk = signer.keygen()
    sk = bytes(secure_sk)  # unwrap SecureBytes
    address = DilithiumSigner.derive_address(pk)
    return pk, sk, address


def _sign(sk: bytes, message: bytes) -> bytes:
    """Helper: sign with a Level 5 signer instance."""
    signer = DilithiumSigner(SecurityLevel.LEVEL5)
    return signer.sign(sk, message)


# ── Challenge tests ───────────────────────────────────────────────────────

def test_create_challenge_valid():
    address = "a" * 40
    resp = create_challenge(address)
    assert isinstance(resp, ChallengeResponse)
    assert resp.address == address
    assert len(resp.nonce) == 64  # 32 bytes hex
    assert resp.message.startswith("qbc-auth:")
    assert address in _challenge_store


def test_create_challenge_invalid_address():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_challenge("short")
    assert exc_info.value.status_code == 400


def test_create_challenge_replaces_previous():
    address = "b" * 40
    resp1 = create_challenge(address)
    resp2 = create_challenge(address)
    assert resp1.nonce != resp2.nonce
    # Only latest challenge should be in store
    assert _challenge_store[address][0] == resp2.nonce


# ── Authentication tests ─────────────────────────────────────────────────

@pytest.mark.skipif(not DILITHIUM_AVAILABLE, reason="dilithium-py not installed")
def test_full_auth_flow():
    """Full flow: challenge → sign → authenticate → get JWT."""
    pk, sk, address = _make_keypair()

    challenge = create_challenge(address)
    sig = _sign(sk, challenge.message.encode("utf-8"))

    req = AuthenticateRequest(
        public_key_hex=pk.hex(),
        signature_hex=sig.hex(),
        message=challenge.message,
    )
    resp = authenticate(req)

    assert resp.address == address
    assert len(resp.token) > 0
    assert resp.expires_at > int(time.time())


@pytest.mark.skipif(not DILITHIUM_AVAILABLE, reason="dilithium-py not installed")
def test_auth_wrong_signature():
    """Signing with wrong key should fail."""
    from fastapi import HTTPException

    pk, sk, address = _make_keypair()
    _, wrong_sk, _ = _make_keypair()

    challenge = create_challenge(address)
    sig = _sign(wrong_sk, challenge.message.encode("utf-8"))

    req = AuthenticateRequest(
        public_key_hex=pk.hex(),
        signature_hex=sig.hex(),
        message=challenge.message,
    )
    with pytest.raises(HTTPException) as exc_info:
        authenticate(req)
    assert exc_info.value.status_code == 401


@pytest.mark.skipif(not DILITHIUM_AVAILABLE, reason="dilithium-py not installed")
def test_auth_address_mismatch():
    """Public key doesn't match the challenge address → 401."""
    from fastapi import HTTPException

    pk, sk, _ = _make_keypair()
    address = "c" * 40  # wrong address — won't match pk

    challenge = create_challenge(address)
    sig = _sign(sk, challenge.message.encode("utf-8"))

    req = AuthenticateRequest(
        public_key_hex=pk.hex(),
        signature_hex=sig.hex(),
        message=challenge.message,
    )
    with pytest.raises(HTTPException) as exc_info:
        authenticate(req)
    assert exc_info.value.status_code == 401


@pytest.mark.skipif(not DILITHIUM_AVAILABLE, reason="dilithium-py not installed")
def test_challenge_consumed_on_use():
    """Challenge is one-time-use — second authenticate should fail."""
    from fastapi import HTTPException

    pk, sk, address = _make_keypair()

    challenge = create_challenge(address)
    sig = _sign(sk, challenge.message.encode("utf-8"))

    req = AuthenticateRequest(
        public_key_hex=pk.hex(),
        signature_hex=sig.hex(),
        message=challenge.message,
    )
    authenticate(req)  # first use — should succeed

    with pytest.raises(HTTPException) as exc_info:
        authenticate(req)  # second use — should fail
    assert exc_info.value.status_code == 401


# ── JWT verification tests ───────────────────────────────────────────────

@pytest.mark.skipif(not DILITHIUM_AVAILABLE, reason="dilithium-py not installed")
def test_verify_token_valid():
    pk, sk, address = _make_keypair()

    challenge = create_challenge(address)
    sig = _sign(sk, challenge.message.encode("utf-8"))
    resp = authenticate(AuthenticateRequest(
        public_key_hex=pk.hex(),
        signature_hex=sig.hex(),
        message=challenge.message,
    ))

    payload = verify_token(f"Bearer {resp.token}")
    assert payload.sub == address


def test_verify_token_missing_header():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        verify_token(None)
    assert exc_info.value.status_code == 401


def test_verify_token_invalid_token():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        verify_token("Bearer invalid.jwt.token")
    assert exc_info.value.status_code == 401


def test_optional_verify_token_none():
    result = optional_verify_token(None)
    assert result is None


def test_optional_verify_token_invalid():
    result = optional_verify_token("Bearer bad.token")
    assert result is None


@pytest.mark.skipif(not DILITHIUM_AVAILABLE, reason="dilithium-py not installed")
def test_optional_verify_token_valid():
    pk, sk, address = _make_keypair()
    challenge = create_challenge(address)
    sig = _sign(sk, challenge.message.encode("utf-8"))
    resp = authenticate(AuthenticateRequest(
        public_key_hex=pk.hex(),
        signature_hex=sig.hex(),
        message=challenge.message,
    ))

    payload = optional_verify_token(f"Bearer {resp.token}")
    assert payload is not None
    assert payload.sub == address
