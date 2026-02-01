"""
Post-quantum cryptography using CRYSTALS-Dilithium
Implementation using dilithium-py library
"""

import hashlib
from typing import Tuple

try:
    # Correct import for dilithium-py package
    from dilithium_py.dilithium import Dilithium2 as DilithiumImpl
    DILITHIUM_AVAILABLE = True
except ImportError:
    DILITHIUM_AVAILABLE = False
    print("⚠️  WARNING: dilithium-py not installed. Using fallback implementation.")
    print("   For production, install: pip install dilithium-py")

from ..utils.logger import get_logger

logger = get_logger(__name__)


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
            # Fallback: hash-based signature (INSECURE)
            combined = private_key + message
            sig_hash = hashlib.sha3_512(combined).digest()
            signature = (sig_hash * 38)[:2420]
            
            logger.warning("Using INSECURE fallback signature")
            return signature

    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """
        Verify Dilithium2 signature
        
        Args:
            public_key: 1312-byte Dilithium2 public key
            message: Original message
            signature: 2420-byte signature to verify
            
        Returns:
            True if signature is valid
        """
        if DILITHIUM_AVAILABLE:
            # Use real Dilithium2 verification
            try:
                return DilithiumImpl.verify(public_key, message, signature)
            except Exception as e:
                logger.debug(f"Dilithium2 verification failed: {e}")
                return False
        else:
            # Fallback: basic length check only (INSECURE)
            try:
                if len(public_key) != 1312:
                    return False
                if len(signature) != 2420:
                    return False
                return signature != b'\x00' * 2420
            except Exception as e:
                logger.error(f"Signature verification failed: {e}")
                return False

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
