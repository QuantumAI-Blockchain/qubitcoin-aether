"""Tests for Dilithium key import/export in standard formats (multi-level)."""
import pytest

from qubitcoin.quantum.crypto import Dilithium2, DilithiumSigner, SecurityLevel


class TestHexExport:
    """Test hex-format key export."""

    def test_export_hex_returns_dict(self):
        pk, sk = Dilithium2.keygen()
        result = Dilithium2.export_keypair(pk, sk, fmt='hex')
        assert isinstance(result, dict)
        assert result['format'] == 'hex'

    def test_export_hex_has_correct_lengths(self):
        pk, sk = Dilithium2.keygen()
        result = Dilithium2.export_keypair(pk, sk, fmt='hex')
        assert len(result['public_key']) == 1312 * 2  # hex doubles byte count
        assert len(result['private_key']) == 2528 * 2

    def test_hex_round_trip(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='hex')
        pk2, sk2 = Dilithium2.import_keypair(
            exported['public_key'], exported['private_key'], fmt='hex'
        )
        assert pk2 == pk
        assert sk2 == sk

    def test_hex_round_trip_sign_verify(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='hex')
        pk2, sk2 = Dilithium2.import_keypair(
            exported['public_key'], exported['private_key'], fmt='hex'
        )
        msg = b"round trip test"
        sig = Dilithium2.sign(sk2, msg)
        assert Dilithium2.verify(pk2, msg, sig) is True


class TestPemExport:
    """Test PEM-format key export."""

    def test_export_pem_returns_dict(self):
        pk, sk = Dilithium2.keygen()
        result = Dilithium2.export_keypair(pk, sk, fmt='pem')
        assert result['format'] == 'pem'

    def test_pem_has_headers(self):
        pk, sk = Dilithium2.keygen()
        result = Dilithium2.export_keypair(pk, sk, fmt='pem')
        # PEM headers now use NIST name (ML-DSA-44 for Dilithium2/LEVEL2)
        assert '-----BEGIN ML-DSA-44 PUBLIC KEY-----' in result['public_key']
        assert '-----END ML-DSA-44 PUBLIC KEY-----' in result['public_key']
        assert '-----BEGIN ML-DSA-44 PRIVATE KEY-----' in result['private_key']
        assert '-----END ML-DSA-44 PRIVATE KEY-----' in result['private_key']

    def test_pem_round_trip(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='pem')
        pk2, sk2 = Dilithium2.import_keypair(
            exported['public_key'], exported['private_key'], fmt='pem'
        )
        assert pk2 == pk
        assert sk2 == sk

    def test_pem_round_trip_sign_verify(self):
        pk, sk = Dilithium2.keygen()
        exported = Dilithium2.export_keypair(pk, sk, fmt='pem')
        pk2, sk2 = Dilithium2.import_keypair(
            exported['public_key'], exported['private_key'], fmt='pem'
        )
        msg = b"PEM round trip"
        sig = Dilithium2.sign(sk2, msg)
        assert Dilithium2.verify(pk2, msg, sig) is True


class TestExportErrors:
    """Test error handling for invalid formats."""

    def test_unsupported_export_format(self):
        pk, sk = Dilithium2.keygen()
        with pytest.raises(ValueError, match="Unsupported export format"):
            Dilithium2.export_keypair(pk, sk, fmt='der')

    def test_unsupported_import_format(self):
        with pytest.raises(ValueError, match="Unsupported import format"):
            Dilithium2.import_keypair('aa', 'bb', fmt='xml')

    def test_default_format_is_hex(self):
        pk, sk = Dilithium2.keygen()
        result = Dilithium2.export_keypair(pk, sk)
        assert result['format'] == 'hex'


class TestMultiLevelExportImport:
    """Test export/import at all security levels."""

    @pytest.mark.parametrize("level", [SecurityLevel.LEVEL2, SecurityLevel.LEVEL3, SecurityLevel.LEVEL5])
    def test_hex_round_trip_all_levels(self, level):
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()
        exported = DilithiumSigner.export_keypair(pk, sk, fmt='hex')
        pk2, sk2 = DilithiumSigner.import_keypair(
            exported['public_key'], exported['private_key'], fmt='hex'
        )
        assert pk2 == pk
        assert sk2 == sk

    @pytest.mark.parametrize("level", [SecurityLevel.LEVEL2, SecurityLevel.LEVEL3, SecurityLevel.LEVEL5])
    def test_pem_round_trip_all_levels(self, level):
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()
        exported = DilithiumSigner.export_keypair(pk, sk, fmt='pem')
        pk2, sk2 = DilithiumSigner.import_keypair(
            exported['public_key'], exported['private_key'], fmt='pem'
        )
        assert pk2 == pk
        assert sk2 == sk

    @pytest.mark.parametrize("level,nist_name", [
        (SecurityLevel.LEVEL2, "ML-DSA-44"),
        (SecurityLevel.LEVEL3, "ML-DSA-65"),
        (SecurityLevel.LEVEL5, "ML-DSA-87"),
    ])
    def test_pem_headers_per_level(self, level, nist_name):
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()
        exported = DilithiumSigner.export_keypair(pk, sk, fmt='pem')
        assert f'-----BEGIN {nist_name} PUBLIC KEY-----' in exported['public_key']
        assert f'-----BEGIN {nist_name} PRIVATE KEY-----' in exported['private_key']

    @pytest.mark.parametrize("level", [SecurityLevel.LEVEL2, SecurityLevel.LEVEL3, SecurityLevel.LEVEL5])
    def test_sign_verify_after_import(self, level):
        signer = DilithiumSigner(level)
        sk_secure, pk = signer.keygen()
        sk = bytes(sk_secure)
        sk_secure.zeroize()
        exported = DilithiumSigner.export_keypair(pk, sk, fmt='hex')
        pk2, sk2 = DilithiumSigner.import_keypair(
            exported['public_key'], exported['private_key'], fmt='hex'
        )
        sig = signer.sign(sk2, b"import test")
        assert DilithiumSigner.verify(pk2, b"import test", sig) is True
