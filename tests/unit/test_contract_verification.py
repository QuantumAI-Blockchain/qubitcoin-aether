"""Tests for contract source-to-bytecode verification (Batch 15.4)."""
import hashlib
import pytest

from qubitcoin.contracts.verification import ContractVerifier, VerificationRecord


def _verifier() -> ContractVerifier:
    return ContractVerifier()


class TestBytecodeHash:
    """Test bytecode hashing."""

    def test_hash_deterministic(self):
        v = _verifier()
        bc = b'\x60\x00\x80\xfd'
        assert v.compute_bytecode_hash(bc) == v.compute_bytecode_hash(bc)

    def test_different_bytecode_different_hash(self):
        v = _verifier()
        assert v.compute_bytecode_hash(b'\x00') != v.compute_bytecode_hash(b'\x01')

    def test_hash_is_sha256(self):
        v = _verifier()
        bc = b'hello'
        expected = hashlib.sha256(bc).hexdigest()
        assert v.compute_bytecode_hash(bc) == expected


class TestSourceHash:
    """Test source code hashing."""

    def test_hash_deterministic(self):
        v = _verifier()
        src = "contract Foo {}"
        assert v.compute_source_hash(src) == v.compute_source_hash(src)

    def test_whitespace_normalised(self):
        v = _verifier()
        assert v.compute_source_hash("  code  ") == v.compute_source_hash("code")

    def test_different_source_different_hash(self):
        v = _verifier()
        assert v.compute_source_hash("A") != v.compute_source_hash("B")


class TestSubmitVerification:
    """Test verification submission flow."""

    def test_submit_creates_record(self):
        v = _verifier()
        rec = v.submit_verification(
            address='0xabc',
            bytecode=b'\x60\x00',
            source_code='contract Test {}',
            compiler_version='0.8.20',
            submitter='dev',
        )
        assert rec.verified is True
        assert rec.address == '0xabc'
        assert rec.compiler_version == '0.8.20'
        assert rec.verified_at is not None

    def test_submit_sets_hashes(self):
        v = _verifier()
        bc = b'\x60\x00\x80\xfd'
        src = 'contract Foo {}'
        rec = v.submit_verification('0x1', bc, src)
        assert rec.bytecode_hash == hashlib.sha256(bc).hexdigest()
        assert rec.source_hash == hashlib.sha256(src.strip().encode()).hexdigest()

    def test_re_verification_updates(self):
        v = _verifier()
        bc = b'\x60\x00'
        v.submit_verification('0x1', bc, 'v1')
        rec = v.submit_verification('0x1', bc, 'v2', compiler_version='0.8.21')
        assert rec.source_hash == v.compute_source_hash('v2')
        assert rec.compiler_version == '0.8.21'


class TestVerifyMatch:
    """Test bytecode matching against verified record."""

    def test_match_returns_true(self):
        v = _verifier()
        bc = b'\x60\x00\x80'
        v.submit_verification('0x1', bc, 'source')
        assert v.verify_match('0x1', bc) is True

    def test_mismatch_returns_false(self):
        v = _verifier()
        v.submit_verification('0x1', b'\x60\x00', 'source')
        assert v.verify_match('0x1', b'\xff\xff') is False

    def test_unverified_returns_false(self):
        v = _verifier()
        assert v.verify_match('unknown', b'\x00') is False


class TestRecordManagement:
    """Test get / list / revoke operations."""

    def test_get_record(self):
        v = _verifier()
        v.submit_verification('0xabc', b'\x00', 'code')
        rec = v.get_record('0xabc')
        assert rec is not None
        assert rec.address == '0xabc'

    def test_get_missing(self):
        v = _verifier()
        assert v.get_record('nope') is None

    def test_is_verified(self):
        v = _verifier()
        v.submit_verification('0x1', b'\x00', 'code')
        assert v.is_verified('0x1') is True

    def test_is_not_verified(self):
        v = _verifier()
        assert v.is_verified('unknown') is False

    def test_list_verified(self):
        v = _verifier()
        v.submit_verification('0x1', b'\x00', 'code1')
        v.submit_verification('0x2', b'\x01', 'code2')
        assert len(v.list_verified()) == 2

    def test_revoke_verification(self):
        v = _verifier()
        v.submit_verification('0x1', b'\x00', 'code')
        assert v.revoke('0x1') is True
        assert v.is_verified('0x1') is False
        assert v.verify_match('0x1', b'\x00') is False

    def test_revoke_missing(self):
        v = _verifier()
        assert v.revoke('nope') is False

    def test_record_to_dict(self):
        v = _verifier()
        rec = v.submit_verification('0x1', b'\x00', 'code', submitter='dev')
        d = rec.to_dict()
        assert d['address'] == '0x1'
        assert d['verified'] is True
        assert d['submitter'] == 'dev'
