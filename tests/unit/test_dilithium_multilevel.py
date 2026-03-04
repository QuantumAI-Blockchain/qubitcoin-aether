"""Unit tests for multi-level Dilithium support (ML-DSA-44/65/87).

Tests all three security levels: keygen, sign, verify, cross-level rejection,
auto-detection from pk size, and backward compatibility.
"""
import pytest

from qubitcoin.quantum.crypto import (
    SecurityLevel,
    DilithiumSigner,
    Dilithium2,
    _KEY_SIZES,
    _PK_SIZE_TO_LEVEL,
    _LEVEL_NAMES,
)


class TestSecurityLevel:
    """Test SecurityLevel enum."""

    def test_level_values(self):
        assert SecurityLevel.LEVEL2 == 2
        assert SecurityLevel.LEVEL3 == 3
        assert SecurityLevel.LEVEL5 == 5

    def test_level_names(self):
        assert _LEVEL_NAMES[SecurityLevel.LEVEL2] == "ML-DSA-44"
        assert _LEVEL_NAMES[SecurityLevel.LEVEL3] == "ML-DSA-65"
        assert _LEVEL_NAMES[SecurityLevel.LEVEL5] == "ML-DSA-87"


class TestDilithiumSignerMultiLevel:
    """Test DilithiumSigner at all security levels."""

    @pytest.mark.parametrize("level", [SecurityLevel.LEVEL2, SecurityLevel.LEVEL3, SecurityLevel.LEVEL5])
    def test_keygen_correct_sizes(self, level):
        """Keygen produces correct pk/sk sizes for each level."""
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()

        sizes = _KEY_SIZES[level]
        assert len(pk) == sizes['pk'], f"pk size {len(pk)} != {sizes['pk']} for {level.name}"
        assert len(sk) == sizes['sk'], f"sk size {len(sk)} != {sizes['sk']} for {level.name}"

    @pytest.mark.parametrize("level", [SecurityLevel.LEVEL2, SecurityLevel.LEVEL3, SecurityLevel.LEVEL5])
    def test_sign_correct_size(self, level):
        """Sign produces correct signature size for each level."""
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()

        sig = signer.sign(sk, b"test message")
        sizes = _KEY_SIZES[level]
        assert len(sig) == sizes['sig'], f"sig size {len(sig)} != {sizes['sig']} for {level.name}"

    @pytest.mark.parametrize("level", [SecurityLevel.LEVEL2, SecurityLevel.LEVEL3, SecurityLevel.LEVEL5])
    def test_sign_verify_roundtrip(self, level):
        """Sign and verify at each level."""
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()

        msg = b"verify this at " + level.name.encode()
        sig = signer.sign(sk, msg)
        assert DilithiumSigner.verify(pk, msg, sig) is True

    @pytest.mark.parametrize("level", [SecurityLevel.LEVEL2, SecurityLevel.LEVEL3, SecurityLevel.LEVEL5])
    def test_verify_rejects_tampered(self, level):
        """Tampered signatures are rejected."""
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()

        sig = signer.sign(sk, b"original")
        tampered = bytearray(sig)
        tampered[-1] ^= 0xFF
        assert DilithiumSigner.verify(pk, b"original", bytes(tampered)) is False

    def test_cross_level_rejection_d2_d5(self):
        """D2 signature should NOT verify with D5 key."""
        s2 = DilithiumSigner(SecurityLevel.LEVEL2)
        s5 = DilithiumSigner(SecurityLevel.LEVEL5)

        sk2_s, pk2 = s2.keygen()
        sk5_s, pk5 = s5.keygen()
        sk2 = bytes(sk2_s)
        sk2_s.zeroize()
        sk5_s.zeroize()

        sig2 = s2.sign(sk2, b"cross level test")
        assert DilithiumSigner.verify(pk5, b"cross level test", sig2) is False

    def test_cross_level_rejection_d3_d2(self):
        """D3 signature should NOT verify with D2 key."""
        s2 = DilithiumSigner(SecurityLevel.LEVEL2)
        s3 = DilithiumSigner(SecurityLevel.LEVEL3)

        sk2_s, pk2 = s2.keygen()
        sk3_s, pk3 = s3.keygen()
        sk3 = bytes(sk3_s)
        sk2_s.zeroize()
        sk3_s.zeroize()

        sig3 = s3.sign(sk3, b"cross level")
        assert DilithiumSigner.verify(pk2, b"cross level", sig3) is False

    def test_wrong_sk_length_raises(self):
        """Signing with wrong-length sk raises ValueError."""
        signer = DilithiumSigner(SecurityLevel.LEVEL5)
        bad_sk = b'\x00' * 100
        with pytest.raises(ValueError, match="Invalid private key length"):
            signer.sign(bad_sk, b"test")


class TestDetectLevel:
    """Test auto-detection of security level from pk size."""

    def test_detect_d2(self):
        signer = DilithiumSigner(SecurityLevel.LEVEL2)
        _, pk = signer.keygen()
        assert DilithiumSigner.detect_level(pk) == SecurityLevel.LEVEL2

    def test_detect_d3(self):
        signer = DilithiumSigner(SecurityLevel.LEVEL3)
        _, pk = signer.keygen()
        assert DilithiumSigner.detect_level(pk) == SecurityLevel.LEVEL3

    def test_detect_d5(self):
        signer = DilithiumSigner(SecurityLevel.LEVEL5)
        _, pk = signer.keygen()
        assert DilithiumSigner.detect_level(pk) == SecurityLevel.LEVEL5

    def test_detect_invalid_size_raises(self):
        with pytest.raises(ValueError, match="Cannot detect Dilithium level"):
            DilithiumSigner.detect_level(b'\x00' * 999)

    def test_pk_size_to_level_mapping(self):
        assert _PK_SIZE_TO_LEVEL[1312] == SecurityLevel.LEVEL2
        assert _PK_SIZE_TO_LEVEL[1952] == SecurityLevel.LEVEL3
        assert _PK_SIZE_TO_LEVEL[2592] == SecurityLevel.LEVEL5


class TestAutoDetectVerify:
    """Test that verify() auto-detects level from pk size."""

    def test_verify_d2_no_config_needed(self):
        """D2 verify works without explicit level configuration."""
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"auto-detect")
        assert DilithiumSigner.verify(pk, b"auto-detect", sig) is True

    def test_verify_d5_no_config_needed(self):
        """D5 verify works without explicit level configuration."""
        signer = DilithiumSigner(SecurityLevel.LEVEL5)
        sk_s, pk = signer.keygen()
        sig = signer.sign(bytes(sk_s), b"auto-detect-5")
        sk_s.zeroize()
        # Use the static verify (not signer instance method)
        assert DilithiumSigner.verify(pk, b"auto-detect-5", sig) is True


class TestBackwardCompatibility:
    """Test that Dilithium2 alias still works for all operations."""

    def test_dilithium2_keygen(self):
        pk, sk = Dilithium2.keygen()
        assert len(pk) == 1312
        assert len(sk) == 2528

    def test_dilithium2_sign(self):
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"compat test")
        assert len(sig) == 2420

    def test_dilithium2_verify(self):
        pk, sk = Dilithium2.keygen()
        sig = Dilithium2.sign(sk, b"compat verify")
        assert Dilithium2.verify(pk, b"compat verify", sig) is True

    def test_dilithium2_derive_address(self):
        pk, sk = Dilithium2.keygen()
        addr = Dilithium2.derive_address(pk)
        assert len(addr) == 40
        assert all(c in '0123456789abcdef' for c in addr)

    def test_dilithium2_export_import(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='hex')
        pk2, sk2 = Dilithium2.import_keypair(
            exported['public_key'], exported['private_key'], fmt='hex'
        )
        assert pk == pk2
        assert sk == sk2


class TestDilithiumSignerProperties:
    """Test DilithiumSigner property accessors."""

    def test_level5_properties(self):
        signer = DilithiumSigner(SecurityLevel.LEVEL5)
        assert signer.level == SecurityLevel.LEVEL5
        assert signer.nist_name == "ML-DSA-87"
        assert signer.pk_size == 2592
        assert signer.sk_size == 4864
        assert signer.sig_size == 4595

    def test_level2_properties(self):
        signer = DilithiumSigner(SecurityLevel.LEVEL2)
        assert signer.level == SecurityLevel.LEVEL2
        assert signer.nist_name == "ML-DSA-44"
        assert signer.pk_size == 1312
        assert signer.sk_size == 2528
        assert signer.sig_size == 2420
