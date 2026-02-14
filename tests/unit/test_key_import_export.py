"""Tests for Dilithium2 key import/export in standard formats (Batch 13.1)."""
import pytest

from qubitcoin.quantum.crypto import Dilithium2


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
        assert '-----BEGIN DILITHIUM2 PUBLIC KEY-----' in result['public_key']
        assert '-----END DILITHIUM2 PUBLIC KEY-----' in result['public_key']
        assert '-----BEGIN DILITHIUM2 PRIVATE KEY-----' in result['private_key']
        assert '-----END DILITHIUM2 PRIVATE KEY-----' in result['private_key']

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
