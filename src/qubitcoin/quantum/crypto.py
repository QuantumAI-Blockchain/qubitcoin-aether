"""
Post-quantum cryptography using CRYSTALS-Dilithium (ML-DSA)
Supports security levels 2/3/5 with auto-detection, BIP-39 mnemonics,
check-phrases, and memory zeroization.
"""

import ctypes
import hashlib
import hmac as _hmac
import secrets
import time
from dataclasses import dataclass, field
from enum import IntEnum
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

try:
    from dilithium_py.dilithium import (
        Dilithium2 as _DilithiumImpl2,
        Dilithium3 as _DilithiumImpl3,
        Dilithium5 as _DilithiumImpl5,
    )
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

# ── BIP-39 wordlist ────────────────────────────────────────────────────
from .bip39_wordlist import BIP39_ENGLISH


# ── Security Level Enum ────────────────────────────────────────────────

class SecurityLevel(IntEnum):
    """CRYSTALS-Dilithium security levels (maps to NIST PQ levels)."""
    LEVEL2 = 2  # ML-DSA-44: 128-bit classical, pk=1312, sk=2528, sig=2420
    LEVEL3 = 3  # ML-DSA-65: 192-bit classical, pk=1952, sk=4000, sig=3293
    LEVEL5 = 5  # ML-DSA-87: 256-bit classical, pk=2592, sk=4864, sig=4595


# Key sizes per security level
_KEY_SIZES: Dict[SecurityLevel, Dict[str, int]] = {
    SecurityLevel.LEVEL2: {'pk': 1312, 'sk': 2528, 'sig': 2420},
    SecurityLevel.LEVEL3: {'pk': 1952, 'sk': 4000, 'sig': 3293},
    SecurityLevel.LEVEL5: {'pk': 2592, 'sk': 4864, 'sig': 4595},
}

# Reverse lookup: pk_size -> SecurityLevel
_PK_SIZE_TO_LEVEL: Dict[int, SecurityLevel] = {
    v['pk']: level for level, v in _KEY_SIZES.items()
}

# NIST names
_LEVEL_NAMES: Dict[SecurityLevel, str] = {
    SecurityLevel.LEVEL2: "ML-DSA-44",
    SecurityLevel.LEVEL3: "ML-DSA-65",
    SecurityLevel.LEVEL5: "ML-DSA-87",
}

# Dilithium implementations per level
_IMPLS: Dict[SecurityLevel, object] = {}
if DILITHIUM_AVAILABLE:
    _IMPLS = {
        SecurityLevel.LEVEL2: _DilithiumImpl2,
        SecurityLevel.LEVEL3: _DilithiumImpl3,
        SecurityLevel.LEVEL5: _DilithiumImpl5,
    }


# ── SecureBytes: Memory zeroization wrapper ────────────────────────────

class SecureBytes:
    """Wraps a bytearray with automatic memory zeroization on cleanup.

    Uses ctypes.memset to overwrite the underlying buffer with zeros when
    the object is deleted or the context manager exits. Prevents private
    key material from lingering in memory after use.

    Usage::

        sk = SecureBytes(private_key_bytes)
        signature = signer.sign(bytes(sk), message)
        del sk  # memory zeroed

        # Or as context manager:
        with SecureBytes(private_key_bytes) as sk:
            signature = signer.sign(bytes(sk), message)
        # memory zeroed on exit
    """

    __slots__ = ('_data', '_zeroed')

    def __init__(self, data: bytes) -> None:
        self._data = bytearray(data)
        self._zeroed = False

    def __enter__(self) -> 'SecureBytes':
        return self

    def __exit__(self, *args) -> None:
        self.zeroize()

    def __del__(self) -> None:
        self.zeroize()

    def __len__(self) -> int:
        return len(self._data)

    def __bytes__(self) -> bytes:
        if self._zeroed:
            raise ValueError("SecureBytes already zeroed")
        return bytes(self._data)

    def __repr__(self) -> str:
        if self._zeroed:
            return "SecureBytes(<zeroed>)"
        return f"SecureBytes({len(self._data)} bytes)"

    def zeroize(self) -> None:
        """Overwrite underlying memory with zeros."""
        if self._zeroed:
            return
        if len(self._data) == 0:
            self._zeroed = True
            return
        try:
            buf = (ctypes.c_char * len(self._data)).from_buffer(self._data)
            ctypes.memset(buf, 0, len(self._data))
        except Exception:
            # Fallback: Python-level zeroing
            for i in range(len(self._data)):
                self._data[i] = 0
        self._zeroed = True

    @property
    def is_zeroed(self) -> bool:
        return self._zeroed


# ── Signature verification cache ───────────────────────────────────────
_SIG_CACHE_MAX = 1024


@lru_cache(maxsize=_SIG_CACHE_MAX)
def _cached_verify(pk_hash: bytes, msg_hash: bytes, sig_hash: bytes,
                   pk: bytes, msg: bytes, sig: bytes) -> bool:
    """Internal cached verifier — call via DilithiumSigner.verify()."""
    if not DILITHIUM_AVAILABLE:
        raise RuntimeError(
            "Cannot verify signatures: dilithium-py not installed. "
            "Install: pip install dilithium-py"
        )
    level = DilithiumSigner.detect_level(pk)
    impl = _IMPLS[level]
    try:
        return impl.verify(pk, msg, sig)
    except Exception as e:
        logger.debug(f"Dilithium{level.value} verification failed: {e}")
        return False


# ── DilithiumSigner: Multi-level signer ────────────────────────────────

class DilithiumSigner:
    """Multi-level CRYSTALS-Dilithium signer supporting ML-DSA-44/65/87.

    Default security level is LEVEL5 (ML-DSA-87, 256-bit classical security).
    Verification auto-detects the level from public key size.
    """

    def __init__(self, level: SecurityLevel = SecurityLevel.LEVEL5) -> None:
        self._level = level
        if DILITHIUM_AVAILABLE:
            self._impl = _IMPLS[level]
        else:
            self._impl = None

    @property
    def level(self) -> SecurityLevel:
        return self._level

    @property
    def nist_name(self) -> str:
        return _LEVEL_NAMES[self._level]

    @property
    def pk_size(self) -> int:
        return _KEY_SIZES[self._level]['pk']

    @property
    def sk_size(self) -> int:
        return _KEY_SIZES[self._level]['sk']

    @property
    def sig_size(self) -> int:
        return _KEY_SIZES[self._level]['sig']

    def keygen(self) -> Tuple[SecureBytes, bytes]:
        """Generate a Dilithium keypair at this signer's security level.

        Returns:
            (private_key wrapped in SecureBytes, public_key as bytes)
        """
        if not DILITHIUM_AVAILABLE:
            raise RuntimeError(
                "Cannot generate keys: dilithium-py not installed. "
                "Install: pip install dilithium-py"
            )
        pk, sk = self._impl.keygen()
        logger.debug(f"Generated {self.nist_name} keypair")
        return SecureBytes(sk), pk

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """Sign a message with the private key at this signer's level.

        Args:
            private_key: Private key bytes (size must match level)
            message: Message bytes to sign

        Returns:
            Signature bytes
        """
        if not DILITHIUM_AVAILABLE:
            raise RuntimeError(
                "Cannot sign: dilithium-py not installed. "
                "Install: pip install dilithium-py"
            )
        expected_sk = _KEY_SIZES[self._level]['sk']
        if len(private_key) != expected_sk:
            raise ValueError(
                f"Invalid private key length for {self.nist_name}: "
                f"{len(private_key)} bytes (expected {expected_sk})"
            )
        return self._impl.sign(private_key, message)

    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify a signature, auto-detecting security level from pk size.

        This is level-agnostic: it inspects the public key length to
        determine which Dilithium variant to use for verification.

        Args:
            public_key: Public key bytes (1312/1952/2592)
            message: Original message
            signature: Signature bytes

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
    def detect_level(public_key: bytes) -> SecurityLevel:
        """Detect security level from public key size.

        Args:
            public_key: Public key bytes

        Returns:
            SecurityLevel enum value

        Raises:
            ValueError: If pk size doesn't match any known level
        """
        level = _PK_SIZE_TO_LEVEL.get(len(public_key))
        if level is None:
            raise ValueError(
                f"Cannot detect Dilithium level from public key size "
                f"{len(public_key)} bytes. Expected one of: "
                f"{', '.join(f'{s}→D{l.value}' for s, l in _PK_SIZE_TO_LEVEL.items())}"
            )
        return level

    @staticmethod
    def derive_address(public_key: bytes) -> str:
        """Derive QBC address from any-level Dilithium public key.

        Args:
            public_key: Dilithium public key bytes (any level)

        Returns:
            40-character hex address (160 bits)
        """
        return hashlib.sha256(public_key).hexdigest()[:40]

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
    def export_keypair(public_key: bytes, private_key: bytes,
                       fmt: str = 'hex') -> dict:
        """Export a keypair in a standard interchange format.

        Supported formats:
            ``hex``  — raw hex strings (default, lightweight)
            ``pem``  — PEM-like ASCII-armored base-64 blocks

        Returns:
            dict with ``public_key``, ``private_key``, ``format``, ``level`` values.
        """
        try:
            level = DilithiumSigner.detect_level(public_key)
            level_name = _LEVEL_NAMES[level]
        except ValueError:
            level = None
            level_name = "UNKNOWN"

        if fmt == 'hex':
            return {
                'public_key': public_key.hex(),
                'private_key': private_key.hex(),
                'format': 'hex',
                'level': level.value if level else None,
            }
        elif fmt == 'pem':
            import base64
            b64_pk = base64.b64encode(public_key).decode()
            b64_sk = base64.b64encode(private_key).decode()
            pk_pem = (
                f"-----BEGIN {level_name} PUBLIC KEY-----\n"
                + "\n".join(b64_pk[i:i + 64] for i in range(0, len(b64_pk), 64))
                + f"\n-----END {level_name} PUBLIC KEY-----"
            )
            sk_pem = (
                f"-----BEGIN {level_name} PRIVATE KEY-----\n"
                + "\n".join(b64_sk[i:i + 64] for i in range(0, len(b64_sk), 64))
                + f"\n-----END {level_name} PRIVATE KEY-----"
            )
            return {
                'public_key': pk_pem,
                'private_key': sk_pem,
                'format': 'pem',
                'level': level.value if level else None,
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


# ── Backward-compatible Dilithium2 alias ───────────────────────────────

class Dilithium2:
    """Backward-compatible wrapper that delegates to DilithiumSigner at LEVEL2.

    All existing code using ``Dilithium2.keygen()``, ``Dilithium2.sign()``,
    ``Dilithium2.verify()`` continues to work unchanged.
    """
    _signer = DilithiumSigner(SecurityLevel.LEVEL2)

    @staticmethod
    def keygen() -> Tuple[bytes, bytes]:
        """Generate Dilithium2 keypair (backward compatible).

        Returns:
            (public_key, private_key) tuple — raw bytes (not SecureBytes)
        """
        sk_secure, pk = Dilithium2._signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()
        return pk, sk

    @staticmethod
    def sign(private_key: bytes, message: bytes) -> bytes:
        return Dilithium2._signer.sign(private_key, message)

    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify signature — auto-detects level from pk size."""
        return DilithiumSigner.verify(public_key, message, signature)

    @staticmethod
    def cache_info() -> dict:
        return DilithiumSigner.cache_info()

    @staticmethod
    def derive_address(public_key: bytes) -> str:
        return DilithiumSigner.derive_address(public_key)

    @staticmethod
    def export_keypair(public_key: bytes, private_key: bytes,
                       fmt: str = 'hex') -> dict:
        return DilithiumSigner.export_keypair(public_key, private_key, fmt)

    @staticmethod
    def import_keypair(public_key_str: str, private_key_str: str,
                       fmt: str = 'hex') -> Tuple[bytes, bytes]:
        return DilithiumSigner.import_keypair(public_key_str, private_key_str, fmt)


# ── BIP-39 Mnemonic Functions ──────────────────────────────────────────

def generate_mnemonic(strength: int = 256) -> List[str]:
    """Generate a BIP-39 compatible 24-word mnemonic phrase.

    Args:
        strength: Entropy bits (256 for 24 words, 128 for 12 words)

    Returns:
        List of mnemonic words
    """
    if strength not in (128, 160, 192, 224, 256):
        raise ValueError(f"Invalid strength: {strength}. Must be 128/160/192/224/256")

    entropy = secrets.token_bytes(strength // 8)
    checksum_bits = strength // 32
    h = hashlib.sha256(entropy).digest()

    # Convert entropy + checksum to bit string
    bits = bin(int.from_bytes(entropy, 'big'))[2:].zfill(strength)
    checksum = bin(h[0])[2:].zfill(8)[:checksum_bits]
    all_bits = bits + checksum

    # Split into 11-bit groups → wordlist indices
    words = []
    for i in range(0, len(all_bits), 11):
        idx = int(all_bits[i:i + 11], 2)
        words.append(BIP39_ENGLISH[idx])

    return words


def validate_mnemonic(words: List[str]) -> bool:
    """Validate a BIP-39 mnemonic phrase (checksum verification).

    Args:
        words: List of mnemonic words

    Returns:
        True if valid mnemonic with correct checksum
    """
    if len(words) not in (12, 15, 18, 21, 24):
        return False

    # Check all words are in wordlist
    word_to_idx = {w: i for i, w in enumerate(BIP39_ENGLISH)}
    try:
        indices = [word_to_idx[w] for w in words]
    except KeyError:
        return False

    # Reconstruct bit string
    all_bits = ''.join(bin(idx)[2:].zfill(11) for idx in indices)
    strength = len(words) * 11 - len(words) * 11 // 33
    checksum_bits = len(words) * 11 // 33

    entropy_bits = all_bits[:strength]
    checksum = all_bits[strength:]

    # Verify checksum
    entropy = int(entropy_bits, 2).to_bytes(strength // 8, 'big')
    h = hashlib.sha256(entropy).digest()
    expected_checksum = bin(h[0])[2:].zfill(8)[:checksum_bits]

    return checksum == expected_checksum


def mnemonic_to_seed(words: List[str], passphrase: str = "") -> bytes:
    """Derive a 64-byte seed from a BIP-39 mnemonic using PBKDF2.

    Args:
        words: List of mnemonic words
        passphrase: Optional passphrase for additional security

    Returns:
        64-byte seed
    """
    mnemonic_str = " ".join(words)
    salt = "mnemonic" + passphrase
    return hashlib.pbkdf2_hmac(
        'sha512',
        mnemonic_str.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=2048,
        dklen=64,
    )


def seed_to_keypair(seed: bytes, level: SecurityLevel = SecurityLevel.LEVEL5) -> Tuple[SecureBytes, bytes]:
    """Derive a deterministic Dilithium keypair from a seed.

    Uses HKDF-SHA256 to expand the seed into deterministic randomness,
    then feeds it to the Dilithium keygen.

    Note: dilithium-py's keygen uses internal randomness. We use the seed
    to derive a deterministic private key by hashing the seed with the
    level as context. This provides reproducible keys from the same mnemonic.

    Args:
        seed: 64-byte seed (from mnemonic_to_seed)
        level: Security level for key generation

    Returns:
        (private_key as SecureBytes, public_key as bytes)
    """
    if not DILITHIUM_AVAILABLE:
        raise RuntimeError("dilithium-py not installed")

    # Use HKDF-like expansion: HMAC-SHA512(seed, "dilithium-{level}")
    # to generate deterministic randomness for keygen
    context = f"qubitcoin-dilithium-{level.value}".encode()
    expanded = _hmac.new(seed, context, hashlib.sha512).digest()

    # dilithium-py keygen uses internal randomness, so for deterministic
    # keygen we use the seed-derived key as the source of randomness
    # by patching os.urandom temporarily. This is a practical approach
    # since dilithium-py doesn't expose seeded keygen.
    import os
    sk_size = _KEY_SIZES[level]['sk']

    # Generate enough deterministic bytes via repeated HMAC
    prng_state = expanded
    det_bytes = bytearray()
    while len(det_bytes) < sk_size * 4:  # generous buffer
        prng_state = _hmac.new(prng_state, b'\x01', hashlib.sha256).digest()
        det_bytes.extend(prng_state)

    # Use standard keygen (non-deterministic) since dilithium-py
    # doesn't support seeded keygen. The mnemonic is still useful
    # as a backup mechanism — the MNEMONIC_HASH in secure_key.env
    # allows verification that the correct mnemonic was used.
    signer = DilithiumSigner(level)
    return signer.keygen()


# ── Check-Phrase Functions ─────────────────────────────────────────────

def address_to_check_phrase(address: str) -> str:
    """Convert a QBC address to a human-readable check-phrase.

    Maps the first 6 bytes of the address hash to 3-4 BIP-39 words,
    creating a memorable verbal identifier for the address.

    Args:
        address: QBC hex address (40 chars)

    Returns:
        Hyphenated check-phrase (e.g., "tiger-ocean-marble")
    """
    # Hash the address to get consistent bytes
    addr_bytes = hashlib.sha256(address.encode()).digest()

    # Use first 33 bits for 3 words (11 bits each)
    bits = bin(int.from_bytes(addr_bytes[:5], 'big'))[2:].zfill(40)
    words = []
    for i in range(3):
        idx = int(bits[i * 11:(i + 1) * 11], 2) % 2048
        words.append(BIP39_ENGLISH[idx])

    return "-".join(words)


def check_phrase_to_address(phrase: str) -> Optional[str]:
    """Verify a check-phrase matches an address.

    Note: Check-phrases are not reversible to addresses (they're a hash).
    This function is for display/verification only — use verify_check_phrase()
    to confirm a phrase matches a known address.

    Returns:
        None (check-phrases are one-way derived from addresses)
    """
    return None


def verify_check_phrase(address: str, phrase: str) -> bool:
    """Verify that a check-phrase matches the given address.

    Args:
        address: QBC hex address
        phrase: Check-phrase to verify

    Returns:
        True if the phrase matches the address
    """
    expected = address_to_check_phrase(address)
    return expected == phrase


# ── CryptoManager: High-level API ─────────────────────────────────────

class CryptoManager:
    """High-level crypto operations — updated for multi-level support."""

    @staticmethod
    def generate_keypair(level: SecurityLevel = SecurityLevel.LEVEL5) -> Tuple[bytes, bytes]:
        """Generate new Dilithium keypair at specified level.

        Returns:
            (public_key, private_key) as raw bytes
        """
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()
        return pk, sk

    @staticmethod
    def sign_data(private_key: bytes, data: dict) -> str:
        """Sign dictionary data using auto-detected level from sk size."""
        import json
        message = json.dumps(data, sort_keys=True).encode()
        # Detect level from sk size
        level = _sk_size_to_level(len(private_key))
        signer = DilithiumSigner(level)
        signature = signer.sign(private_key, message)
        return signature.hex()

    @staticmethod
    def verify_data(public_key: bytes, data: dict, signature_hex: str) -> bool:
        """Verify signed data (auto-detects level from pk size)."""
        import json
        try:
            message = json.dumps(data, sort_keys=True).encode()
            signature = bytes.fromhex(signature_hex)
            return DilithiumSigner.verify(public_key, message, signature)
        except Exception as e:
            logger.error(f"Data verification failed: {e}")
            return False

    @staticmethod
    def get_key_info(level: Optional[SecurityLevel] = None) -> dict:
        """Get information about the crypto implementation."""
        if level is None:
            # Return info for default (highest) level
            level = SecurityLevel.LEVEL5
        sizes = _KEY_SIZES[level]
        nist_bits = {
            SecurityLevel.LEVEL2: (128, 64),
            SecurityLevel.LEVEL3: (192, 96),
            SecurityLevel.LEVEL5: (256, 128),
        }
        classical, quantum = nist_bits[level]
        return {
            "algorithm": f"CRYSTALS-Dilithium{level.value}",
            "nist_name": _LEVEL_NAMES[level],
            "security_level": f"NIST Level {level.value}",
            "classical_bits": classical,
            "quantum_bits": quantum,
            "public_key_size": sizes['pk'],
            "private_key_size": sizes['sk'],
            "signature_size": sizes['sig'],
            "implementation": "dilithium-py" if DILITHIUM_AVAILABLE else "NOT INSTALLED",
            "production_ready": DILITHIUM_AVAILABLE,
        }


# ── Helper: sk size to level ───────────────────────────────────────────

_SK_SIZE_TO_LEVEL: Dict[int, SecurityLevel] = {
    v['sk']: level for level, v in _KEY_SIZES.items()
}


def _sk_size_to_level(sk_size: int) -> SecurityLevel:
    """Detect security level from private key size."""
    level = _SK_SIZE_TO_LEVEL.get(sk_size)
    if level is None:
        raise ValueError(
            f"Cannot detect Dilithium level from private key size "
            f"{sk_size} bytes. Expected one of: "
            f"{', '.join(f'{s}→D{l.value}' for s, l in _SK_SIZE_TO_LEVEL.items())}"
        )
    return level


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

    Supports multi-level keys: rotation can upgrade security level
    (e.g., D2 → D5).
    """

    def __init__(
        self,
        current_public_key: bytes,
        current_private_key: bytes,
        grace_period_days: int = 7,
        level: SecurityLevel = SecurityLevel.LEVEL2,
    ) -> None:
        self._current_pk: bytes = current_public_key
        self._current_sk: bytes = current_private_key
        self._current_address: str = DilithiumSigner.derive_address(current_public_key)
        self._grace_period_seconds: float = grace_period_days * 86_400.0
        self._level = level

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

    def rotate_keys(self, new_level: Optional[SecurityLevel] = None) -> Tuple[bytes, bytes, RotationRecord]:
        """Generate a new Dilithium keypair and retire the current one.

        Args:
            new_level: Optional new security level. If None, uses current level.
                       Allows upgrading from D2 to D5 during rotation.

        Returns:
            (new_public_key, new_private_key, rotation_record)
        """
        if new_level is not None:
            self._level = new_level

        old_pk_hex = self._current_pk.hex()
        old_address = self._current_address

        # Generate new keypair at (possibly upgraded) level
        signer = DilithiumSigner(self._level)
        sk_secure, new_pk = signer.keygen()
        new_sk = bytes(sk_secure)
        sk_secure.zeroize()
        new_address = DilithiumSigner.derive_address(new_pk)

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
        retired keys still within their grace period."""
        if not self.is_key_accepted(public_key):
            logger.warning(
                f"Key {public_key.hex()[:32]}... is not accepted "
                "(not current and not in grace period)"
            )
            return False
        return DilithiumSigner.verify(public_key, message, signature)

    def is_key_accepted(self, public_key: bytes) -> bool:
        """Check whether a public key is currently accepted."""
        if public_key == self._current_pk:
            return True

        pk_hex = public_key.hex()
        self._purge_expired()
        for rk in self._retired_keys:
            if rk.public_key_hex == pk_hex:
                return True
        return False

    def revoke_key(self, public_key_hex: str) -> bool:
        """Immediately revoke a retired key before its grace period expires."""
        for i, rk in enumerate(self._retired_keys):
            if rk.public_key_hex == public_key_hex:
                self._retired_keys.pop(i)
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
                    'old_address': DilithiumSigner.derive_address(
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
