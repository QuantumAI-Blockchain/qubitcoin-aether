"""
Post-quantum cryptography using CRYSTALS-Dilithium
Implementation using dilithium-py library
"""

import hashlib
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import os

try:
    from dilithium_py.dilithium import Dilithium2 as DilithiumImpl
    DILITHIUM_AVAILABLE = True
except ImportError:
    DILITHIUM_AVAILABLE = False

from ..utils.logger import get_logger

logger = get_logger(__name__)

if not DILITHIUM_AVAILABLE:
    logger.error(
        "dilithium-py not installed. Post-quantum cryptography is REQUIRED. "
        "Install: pip install dilithium-py"
    )


# ── Signature verification cache ────────────────────────────────────────
# Caches (pk_hash, msg_hash, sig_hash) → bool so repeated verifications
# of the same (public_key, message, signature) triple skip the expensive
# Dilithium math.  Cache key uses SHA-256 digests to keep memory bounded.
_SIG_CACHE_MAX = 4096


@lru_cache(maxsize=_SIG_CACHE_MAX)
def _cached_verify(pk_hash: bytes, msg_hash: bytes, sig_hash: bytes,
                   pk: bytes, msg: bytes, sig: bytes) -> bool:
    """Internal cached verifier — call via Dilithium2.verify()."""
    if not DILITHIUM_AVAILABLE:
        raise RuntimeError(
            "Cannot verify signatures: dilithium-py not installed. "
            "Install: pip install dilithium-py"
        )
    try:
        return DilithiumImpl.verify(pk, msg, sig)
    except Exception as e:
        logger.debug(f"Dilithium2 verification failed: {e}")
        return False


class Dilithium2:
    """
    CRYSTALS-Dilithium2 signature scheme (NIST Level 2)

    Security: 128-bit classical, 64-bit quantum resistance
    Public key: 1312 bytes
    Signature: 2420 bytes
    Based on Module-LWE hardness assumption
    """

    @staticmethod
    def keygen() -> Tuple[bytes, bytes]:
        """
        Generate Dilithium2 keypair
        
        Returns:
            (public_key, private_key) tuple
            - public_key: 1312 bytes
            - private_key: 2528 bytes
        """
        if not DILITHIUM_AVAILABLE:
            raise RuntimeError(
                "Cannot generate keys: dilithium-py not installed. "
                "Install: pip install dilithium-py"
            )
        public_key, private_key = DilithiumImpl.keygen()
        logger.debug("Generated Dilithium2 keypair (dilithium-py)")
        return public_key, private_key

    @staticmethod
    def sign(private_key: bytes, message: bytes) -> bytes:
        """
        Sign message with Dilithium2 private key
        
        Args:
            private_key: 2528-byte Dilithium2 private key
            message: Message to sign
            
        Returns:
            2420-byte signature
        """
        if not DILITHIUM_AVAILABLE:
            raise RuntimeError(
                "Cannot sign: dilithium-py not installed. "
                "Install: pip install dilithium-py"
            )
        signature = DilithiumImpl.sign(private_key, message)
        return signature

    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """
        Verify Dilithium2 signature (with LRU caching for performance).

        Repeated verifications of the same (pk, msg, sig) triple are served
        from a bounded cache (up to ``_SIG_CACHE_MAX`` entries) so the
        expensive lattice math runs at most once per unique triple.

        Args:
            public_key: 1312-byte Dilithium2 public key
            message: Original message
            signature: 2420-byte signature to verify

        Returns:
            True if signature is valid
        """
        try:
            pk_hash = hashlib.sha256(public_key).digest()
            msg_hash = hashlib.sha256(message).digest()
            sig_hash = hashlib.sha256(signature).digest()
            return _cached_verify(pk_hash, msg_hash, sig_hash,
                                  public_key, message, signature)
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    @staticmethod
    def cache_info() -> dict:
        """Return cache statistics for signature verification."""
        info = _cached_verify.cache_info()
        return {
            'hits': info.hits,
            'misses': info.misses,
            'maxsize': info.maxsize,
            'currsize': info.currsize,
        }

    @staticmethod
    def derive_address(public_key: bytes) -> str:
        """
        Derive QBC address from Dilithium2 public key
        
        Args:
            public_key: 1312-byte Dilithium2 public key
            
        Returns:
            40-character hex address (160 bits)
        """
        return hashlib.sha256(public_key).hexdigest()[:40]


    @staticmethod
    def export_keypair(public_key: bytes, private_key: bytes,
                       fmt: str = 'hex') -> dict:
        """Export a keypair in a standard interchange format.

        Supported formats:
            ``hex``  — raw hex strings (default, lightweight)
            ``pem``  — PEM-like ASCII-armored base-64 blocks

        Returns:
            dict with ``public_key`` and ``private_key`` string values.
        """
        if fmt == 'hex':
            return {
                'public_key': public_key.hex(),
                'private_key': private_key.hex(),
                'format': 'hex',
            }
        elif fmt == 'pem':
            import base64
            b64_pk = base64.b64encode(public_key).decode()
            b64_sk = base64.b64encode(private_key).decode()
            pk_pem = (
                "-----BEGIN DILITHIUM2 PUBLIC KEY-----\n"
                + "\n".join(b64_pk[i:i + 64] for i in range(0, len(b64_pk), 64))
                + "\n-----END DILITHIUM2 PUBLIC KEY-----"
            )
            sk_pem = (
                "-----BEGIN DILITHIUM2 PRIVATE KEY-----\n"
                + "\n".join(b64_sk[i:i + 64] for i in range(0, len(b64_sk), 64))
                + "\n-----END DILITHIUM2 PRIVATE KEY-----"
            )
            return {
                'public_key': pk_pem,
                'private_key': sk_pem,
                'format': 'pem',
            }
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

    @staticmethod
    def import_keypair(public_key_str: str, private_key_str: str,
                       fmt: str = 'hex') -> Tuple[bytes, bytes]:
        """Import a keypair from a standard interchange format.

        Returns:
            (public_key_bytes, private_key_bytes)
        """
        if fmt == 'hex':
            return bytes.fromhex(public_key_str), bytes.fromhex(private_key_str)
        elif fmt == 'pem':
            import base64
            pk_lines = [
                ln for ln in public_key_str.splitlines()
                if not ln.startswith('-----')
            ]
            sk_lines = [
                ln for ln in private_key_str.splitlines()
                if not ln.startswith('-----')
            ]
            pk = base64.b64decode(''.join(pk_lines))
            sk = base64.b64decode(''.join(sk_lines))
            return pk, sk
        else:
            raise ValueError(f"Unsupported import format: {fmt}")


class CryptoManager:
    """High-level crypto operations"""

    @staticmethod
    def generate_keypair() -> Tuple[bytes, bytes]:
        """Generate new Dilithium2 keypair"""
        return Dilithium2.keygen()

    @staticmethod
    def sign_data(private_key: bytes, data: dict) -> str:
        """Sign dictionary data"""
        import json
        message = json.dumps(data, sort_keys=True).encode()
        signature = Dilithium2.sign(private_key, message)
        return signature.hex()

    @staticmethod
    def verify_data(public_key: bytes, data: dict, signature_hex: str) -> bool:
        """Verify signed data"""
        import json
        try:
            message = json.dumps(data, sort_keys=True).encode()
            signature = bytes.fromhex(signature_hex)
            return Dilithium2.verify(public_key, message, signature)
        except Exception as e:
            logger.error(f"Data verification failed: {e}")
            return False

    @staticmethod
    def get_key_info() -> dict:
        """Get information about the crypto implementation"""
        return {
            "algorithm": "CRYSTALS-Dilithium2",
            "security_level": "NIST Level 2",
            "classical_bits": 128,
            "quantum_bits": 64,
            "public_key_size": 1312,
            "private_key_size": 2528,
            "signature_size": 2420,
            "implementation": "dilithium-py" if DILITHIUM_AVAILABLE else "NOT INSTALLED",
            "production_ready": DILITHIUM_AVAILABLE
        }


# ── Key Rotation ─────────────────────────────────────────────────────────


@dataclass
class RotationRecord:
    """Immutable record of a single key rotation event."""

    old_public_key_hex: str
    new_public_key_hex: str
    new_address: str
    rotated_at: float  # Unix timestamp
    grace_expires_at: float  # Unix timestamp when old key becomes invalid
    revoked: bool = False


@dataclass
class RetiredKey:
    """A public key that has been rotated out but is still within its grace period."""

    public_key_hex: str
    address: str
    retired_at: float
    grace_expires_at: float


class KeyRotationManager:
    """Manage Dilithium key rotation with configurable grace periods.

    During a grace period both the current key and the retired key are
    accepted for signature verification.  After the grace period the old
    key is revoked and only the current key is valid.

    Usage::

        mgr = KeyRotationManager(
            current_public_key=pk,
            current_private_key=sk,
            grace_period_days=7,
        )
        # Later, rotate:
        new_pk, new_sk, record = mgr.rotate_keys()
        # Verify with either old or new key during grace:
        assert mgr.verify(old_pk, message, signature)
        assert mgr.verify(new_pk, message, signature)
    """

    def __init__(
        self,
        current_public_key: bytes,
        current_private_key: bytes,
        grace_period_days: int = 7,
    ) -> None:
        self._current_pk: bytes = current_public_key
        self._current_sk: bytes = current_private_key
        self._current_address: str = Dilithium2.derive_address(current_public_key)
        self._grace_period_seconds: float = grace_period_days * 86_400.0

        # Retired keys still within their grace window
        self._retired_keys: List[RetiredKey] = []

        # Full rotation history (append-only)
        self._history: List[RotationRecord] = []

    # ── Properties ────────────────────────────────────────────────────

    @property
    def current_public_key(self) -> bytes:
        return self._current_pk

    @property
    def current_private_key(self) -> bytes:
        return self._current_sk

    @property
    def current_address(self) -> str:
        return self._current_address

    @property
    def grace_period_days(self) -> float:
        return self._grace_period_seconds / 86_400.0

    @property
    def history(self) -> List[RotationRecord]:
        """Return a copy of the full rotation history."""
        return list(self._history)

    @property
    def active_retired_keys(self) -> List[RetiredKey]:
        """Return retired keys that are still within their grace period."""
        self._purge_expired()
        return list(self._retired_keys)

    # ── Core operations ───────────────────────────────────────────────

    def rotate_keys(self) -> Tuple[bytes, bytes, RotationRecord]:
        """Generate a new Dilithium keypair and retire the current one.

        The old public key remains valid for ``grace_period_days`` after
        rotation.

        Returns:
            (new_public_key, new_private_key, rotation_record)
        """
        old_pk_hex = self._current_pk.hex()
        old_address = self._current_address

        # Generate new keypair
        new_pk, new_sk = Dilithium2.keygen()
        new_address = Dilithium2.derive_address(new_pk)

        now = time.time()
        grace_expires = now + self._grace_period_seconds

        # Retire current key
        self._retired_keys.append(RetiredKey(
            public_key_hex=old_pk_hex,
            address=old_address,
            retired_at=now,
            grace_expires_at=grace_expires,
        ))

        # Record in history
        record = RotationRecord(
            old_public_key_hex=old_pk_hex,
            new_public_key_hex=new_pk.hex(),
            new_address=new_address,
            rotated_at=now,
            grace_expires_at=grace_expires,
        )
        self._history.append(record)

        # Swap to new key
        self._current_pk = new_pk
        self._current_sk = new_sk
        self._current_address = new_address

        logger.info(
            f"Key rotated: {old_address[:16]}... -> {new_address[:16]}..., "
            f"grace until {grace_expires:.0f}"
        )
        return new_pk, new_sk, record

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify a signature, accepting both the current key and any
        retired keys still within their grace period.

        Args:
            public_key: The public key that allegedly signed ``message``.
            message: The original message bytes.
            signature: The signature to verify.

        Returns:
            ``True`` if the signature is valid AND the public key is either
            the current key or a non-expired retired key.
        """
        if not self.is_key_accepted(public_key):
            logger.warning(
                f"Key {public_key.hex()[:32]}... is not accepted "
                "(not current and not in grace period)"
            )
            return False
        return Dilithium2.verify(public_key, message, signature)

    def is_key_accepted(self, public_key: bytes) -> bool:
        """Check whether a public key is currently accepted.

        A key is accepted if it is the current active key, or if it is a
        retired key whose grace period has not yet expired.
        """
        # Current key is always accepted
        if public_key == self._current_pk:
            return True

        pk_hex = public_key.hex()
        self._purge_expired()
        for rk in self._retired_keys:
            if rk.public_key_hex == pk_hex:
                return True
        return False

    def revoke_key(self, public_key_hex: str) -> bool:
        """Immediately revoke a retired key before its grace period expires.

        Args:
            public_key_hex: Hex-encoded public key to revoke.

        Returns:
            ``True`` if the key was found and revoked.
        """
        for i, rk in enumerate(self._retired_keys):
            if rk.public_key_hex == public_key_hex:
                self._retired_keys.pop(i)
                # Mark in history
                for rec in self._history:
                    if rec.old_public_key_hex == public_key_hex and not rec.revoked:
                        rec.revoked = True
                        break
                logger.info(f"Key {public_key_hex[:32]}... revoked early")
                return True
        logger.warning(f"Key {public_key_hex[:32]}... not found in retired keys")
        return False

    def get_status(self) -> dict:
        """Return a JSON-serialisable status summary."""
        self._purge_expired()
        return {
            'current_address': self._current_address,
            'current_public_key_hex': self._current_pk.hex(),
            'grace_period_days': self.grace_period_days,
            'retired_keys_in_grace': len(self._retired_keys),
            'total_rotations': len(self._history),
            'retired_keys': [
                {
                    'address': rk.address,
                    'public_key_hex_short': rk.public_key_hex[:32] + '...',
                    'retired_at': rk.retired_at,
                    'grace_expires_at': rk.grace_expires_at,
                    'seconds_remaining': max(0, rk.grace_expires_at - time.time()),
                }
                for rk in self._retired_keys
            ],
            'history': [
                {
                    'old_address': Dilithium2.derive_address(
                        bytes.fromhex(rec.old_public_key_hex)
                    ),
                    'new_address': rec.new_address,
                    'rotated_at': rec.rotated_at,
                    'grace_expires_at': rec.grace_expires_at,
                    'revoked': rec.revoked,
                }
                for rec in self._history
            ],
        }

    # ── Internal helpers ──────────────────────────────────────────────

    def _purge_expired(self) -> None:
        """Remove retired keys whose grace period has expired."""
        now = time.time()
        expired = [rk for rk in self._retired_keys if rk.grace_expires_at <= now]
        if expired:
            for rk in expired:
                logger.info(
                    f"Grace period expired for key {rk.public_key_hex[:32]}... "
                    f"(address {rk.address[:16]}...)"
                )
            self._retired_keys = [
                rk for rk in self._retired_keys if rk.grace_expires_at > now
            ]
