"""
Post-quantum cryptography using CRYSTALS-Dilithium
Implementation using dilithium-py library
"""

import hashlib
from functools import lru_cache
from typing import Tuple

import os

try:
    from dilithium_py.dilithium import Dilithium2 as DilithiumImpl
    DILITHIUM_AVAILABLE = True
except ImportError:
    DILITHIUM_AVAILABLE = False
    _env = os.getenv('QBC_ENV', 'development')
    if _env == 'production':
        raise RuntimeError(
            "FATAL: dilithium-py not installed in production mode. "
            "Post-quantum cryptography is required. Install: pip install dilithium-py"
        )
    print("WARNING: dilithium-py not installed. Using INSECURE fallback (dev only).")
    print("   For production, install: pip install dilithium-py")

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ── Signature verification cache ────────────────────────────────────────
# Caches (pk_hash, msg_hash, sig_hash) → bool so repeated verifications
# of the same (public_key, message, signature) triple skip the expensive
# Dilithium math.  Cache key uses SHA-256 digests to keep memory bounded.
_SIG_CACHE_MAX = 4096


@lru_cache(maxsize=_SIG_CACHE_MAX)
def _cached_verify(pk_hash: bytes, msg_hash: bytes, sig_hash: bytes,
                   pk: bytes, msg: bytes, sig: bytes) -> bool:
    """Internal cached verifier — call via Dilithium2.verify()."""
    if DILITHIUM_AVAILABLE:
        try:
            return DilithiumImpl.verify(pk, msg, sig)
        except Exception as e:
            logger.debug(f"Dilithium2 verification failed: {e}")
            return False
    else:
        import hmac as _hmac
        try:
            if len(pk) != 1312 or len(sig) != 2420:
                return False
            if sig == b'\x00' * 2420:
                return False
            expected_binding = hashlib.sha256(pk[:64] + msg).digest()
            actual_binding = sig[2388:2420]
            if not _hmac.compare_digest(expected_binding, actual_binding):
                return False
            return True
        except Exception:
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
        if DILITHIUM_AVAILABLE:
            # Use real Dilithium2 implementation
            public_key, private_key = DilithiumImpl.keygen()
            logger.debug("Generated Dilithium2 keypair (dilithium-py)")
            return public_key, private_key
        else:
            # Fallback: deterministic but insecure placeholder
            import secrets
            
            # Generate realistic-sized keys for compatibility
            private_key = secrets.token_bytes(2528)
            
            # Derive public key deterministically
            public_key = hashlib.sha3_512(private_key).digest()
            # Pad to Dilithium2 public key size (1312 bytes)
            public_key = (public_key * 21)[:1312]
            
            logger.warning("Using INSECURE fallback Dilithium2 (development only)")
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
        if DILITHIUM_AVAILABLE:
            # Use real Dilithium2 signing
            signature = DilithiumImpl.sign(private_key, message)
            return signature
        else:
            # Fallback: deterministic hash-based signature (DEV ONLY - NOT SECURE)
            # Derive public key material from private key (same as keygen)
            pk_material = hashlib.sha3_512(private_key).digest()  # 64 bytes
            # Signature body from private key + message
            sig_body = hashlib.sha3_512(private_key + message).digest()
            sig_padded = (sig_body * 38)[:2388]
            # Binding tag: ties signature to public_key + message pair
            binding = hashlib.sha256(pk_material[:64] + message).digest()
            signature = sig_padded + binding  # 2388 + 32 = 2420 bytes

            logger.warning("Using INSECURE fallback signature (dev only)")
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
            "implementation": "dilithium-py" if DILITHIUM_AVAILABLE else "fallback (INSECURE)",
            "production_ready": DILITHIUM_AVAILABLE
        }
