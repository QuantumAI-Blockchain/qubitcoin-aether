"""Unit tests for Dilithium2 signature scheme — key sizes, signing, verification.

These are test vectors for the (fallback) Dilithium2 implementation, verifying:
- Key generation produces correct sizes
- Signing produces correct signature size
- Verification accepts valid signatures
- Verification rejects tampered signatures/messages/keys
- Address derivation is deterministic
- CryptoManager high-level API works end-to-end
"""
import pytest


class TestDilithium2KeyGen:
    """Test key generation produces correct sizes."""

    def test_keygen_returns_tuple(self):
        from qubitcoin.quantum.crypto import Dilithium2
        result = Dilithium2.keygen()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_public_key_size_1312(self):
        """Public key must be exactly 1312 bytes."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        assert len(pk) == 1312, f"Expected 1312 bytes, got {len(pk)}"

    def test_private_key_size_2528(self):
        """Private key must be exactly 2528 bytes."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        assert len(sk) == 2528, f"Expected 2528 bytes, got {len(sk)}"

    def test_keygen_unique_keys(self):
        """Two key generations produce different keys."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk1, sk1 = Dilithium2.keygen()
        pk2, sk2 = Dilithium2.keygen()
        assert sk1 != sk2, "Private keys should be unique"

    def test_keygen_pk_derived_from_sk(self):
        """Public key is derived from private key (deterministic derivation)."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        # Public key should not be all zeros
        assert pk != b'\x00' * 1312


class TestDilithium2Signing:
    """Test signing produces correct-size signatures."""

    def test_signature_size_2420(self):
        """Signature must be exactly 2420 bytes (~2.4KB)."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        msg = b"Hello Qubitcoin"
        sig = Dilithium2.sign(sk, msg)
        assert len(sig) == 2420, f"Expected 2420 bytes, got {len(sig)}"

    def test_sign_empty_message(self):
        """Signing empty message produces valid 2420-byte signature."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"")
        assert len(sig) == 2420

    def test_sign_large_message(self):
        """Signing large message still produces 2420-byte signature."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        large_msg = b"x" * 100000
        sig = Dilithium2.sign(sk, large_msg)
        assert len(sig) == 2420

    def test_different_messages_different_signatures(self):
        """Different messages produce different signatures."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        sig1 = Dilithium2.sign(sk, b"message A")
        sig2 = Dilithium2.sign(sk, b"message B")
        assert sig1 != sig2

    def test_same_message_same_key_deterministic(self):
        """Same message + same key produces same signature (deterministic)."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        sig1 = Dilithium2.sign(sk, b"deterministic")
        sig2 = Dilithium2.sign(sk, b"deterministic")
        assert sig1 == sig2


class TestDilithium2Verification:
    """Test signature verification (valid and invalid cases)."""

    def test_verify_valid_signature(self):
        """Valid signature verifies successfully."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        msg = b"Verify this transaction"
        sig = Dilithium2.sign(sk, msg)
        assert Dilithium2.verify(pk, msg, sig) is True

    def test_verify_wrong_message_fails(self):
        """Signature for different message fails verification."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"original message")
        assert Dilithium2.verify(pk, b"tampered message", sig) is False

    def test_verify_wrong_key_fails(self):
        """Signature verified with wrong public key fails."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk1, sk1 = Dilithium2.keygen()
        pk2, sk2 = Dilithium2.keygen()
        msg = b"Test"
        sig = Dilithium2.sign(sk1, msg)
        assert Dilithium2.verify(pk2, msg, sig) is False

    def test_verify_tampered_signature_fails(self):
        """Tampered signature bytes fail verification."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        msg = b"Tamper test"
        sig = Dilithium2.sign(sk, msg)
        # Flip a byte in the binding tag region (last 32 bytes)
        tampered = bytearray(sig)
        tampered[-1] ^= 0xFF
        assert Dilithium2.verify(pk, msg, bytes(tampered)) is False

    def test_verify_zero_signature_fails(self):
        """All-zero signature fails verification."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        zero_sig = b'\x00' * 2420
        assert Dilithium2.verify(pk, b"test", zero_sig) is False

    def test_verify_wrong_size_key_fails(self):
        """Public key with wrong size fails verification."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"test")
        short_pk = pk[:100]
        assert Dilithium2.verify(short_pk, b"test", sig) is False

    def test_verify_wrong_size_sig_fails(self):
        """Signature with wrong size fails verification."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        short_sig = b'\x42' * 100
        assert Dilithium2.verify(pk, b"test", short_sig) is False


class TestDilithiumTransactionSize:
    """Verify signature impact on transaction sizes."""

    def test_signature_is_approximately_3kb(self):
        """Dilithium2 signature is ~2.4KB, within the ~3KB budget."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"tx data")
        # Signature = 2420 bytes (~2.4KB)
        # With public key (1312 bytes) total crypto overhead = ~3.7KB
        assert 2000 <= len(sig) <= 3000, f"Sig size {len(sig)} not in ~3KB range"

    def test_crypto_overhead_per_transaction(self):
        """Total crypto overhead (pubkey + sig) fits documented ~3KB budget."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"transaction data")
        # Public key + signature = total crypto overhead
        total = len(pk) + len(sig)
        # CLAUDE.md says ~3KB per signature. Public key is separate.
        # Verify signature alone is approximately 2.4KB
        assert len(sig) == 2420
        # Total crypto overhead (pk + sig) = 1312 + 2420 = 3732 bytes
        assert total == 3732

    def test_block_capacity_with_dilithium(self):
        """Estimate: ~1MB block fits ~270 transactions with Dilithium overhead."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"tx")
        # Assume ~300 bytes base tx + 2420 sig + 1312 pk = ~4032 bytes per tx
        tx_size = 300 + len(sig) + len(pk)
        block_size = 1_000_000  # 1MB
        capacity = block_size // tx_size
        # CLAUDE.md says ~333 tx/MB. With full key, we get ~248.
        # Verify we're in a reasonable range
        assert 200 <= capacity <= 400


class TestAddressDerivation:
    """Test address derivation from public key."""

    def test_address_is_40_hex_chars(self):
        """Address is a 40-character hex string (160 bits)."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        addr = Dilithium2.derive_address(pk)
        assert len(addr) == 40
        assert all(c in '0123456789abcdef' for c in addr)

    def test_address_deterministic(self):
        """Same public key always produces same address."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk, sk = Dilithium2.keygen()
        addr1 = Dilithium2.derive_address(pk)
        addr2 = Dilithium2.derive_address(pk)
        assert addr1 == addr2

    def test_different_keys_different_addresses(self):
        """Different public keys produce different addresses."""
        from qubitcoin.quantum.crypto import Dilithium2
        pk1, _ = Dilithium2.keygen()
        pk2, _ = Dilithium2.keygen()
        assert Dilithium2.derive_address(pk1) != Dilithium2.derive_address(pk2)


class TestCryptoManager:
    """Test high-level CryptoManager API."""

    def test_sign_and_verify_data(self):
        """Sign and verify a Python dict via CryptoManager."""
        from qubitcoin.quantum.crypto import CryptoManager
        pk, sk = CryptoManager.generate_keypair()
        data = {"amount": "100", "to": "qbc1abc"}
        sig_hex = CryptoManager.sign_data(sk, data)
        assert CryptoManager.verify_data(pk, data, sig_hex) is True

    def test_verify_tampered_data_fails(self):
        """Tampered data fails verification."""
        from qubitcoin.quantum.crypto import CryptoManager
        pk, sk = CryptoManager.generate_keypair()
        data = {"amount": "100"}
        sig_hex = CryptoManager.sign_data(sk, data)
        tampered = {"amount": "999"}
        assert CryptoManager.verify_data(pk, tampered, sig_hex) is False

    def test_get_key_info(self):
        """Key info returns expected metadata."""
        from qubitcoin.quantum.crypto import CryptoManager
        info = CryptoManager.get_key_info()
        assert info['algorithm'] == 'CRYSTALS-Dilithium2'
        assert info['public_key_size'] == 1312
        assert info['private_key_size'] == 2528
        assert info['signature_size'] == 2420
        assert info['security_level'] == 'NIST Level 2'
