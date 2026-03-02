"""Tests for Dilithium2 signature verification caching (Batch 12.1)."""
import pytest

from qubitcoin.quantum.crypto import Dilithium2, _cached_verify


class TestCacheWorks:
    """Verify the LRU cache speeds up repeated verifications."""

    def setup_method(self):
        # Clear cache before each test
        _cached_verify.cache_clear()

    def test_verify_still_works(self):
        """Basic sign + verify round-trip must still pass."""
        pk, sk = Dilithium2.keygen()
        msg = b"test message"
        sig = Dilithium2.sign(sk, msg)
        assert Dilithium2.verify(pk, msg, sig) is True

    def test_cache_hit_on_second_call(self):
        """Second verify of same (pk, msg, sig) should be a cache hit."""
        pk, sk = Dilithium2.keygen()
        msg = b"cached verification"
        sig = Dilithium2.sign(sk, msg)

        _cached_verify.cache_clear()
        assert Dilithium2.verify(pk, msg, sig) is True  # miss
        info_after_first = Dilithium2.cache_info()
        assert info_after_first['misses'] >= 1

        assert Dilithium2.verify(pk, msg, sig) is True  # hit
        info_after_second = Dilithium2.cache_info()
        assert info_after_second['hits'] >= 1

    def test_different_messages_different_results(self):
        """Different messages produce independent cache entries."""
        pk, sk = Dilithium2.keygen()
        msg1 = b"message one"
        msg2 = b"message two"
        sig1 = Dilithium2.sign(sk, msg1)
        sig2 = Dilithium2.sign(sk, msg2)

        assert Dilithium2.verify(pk, msg1, sig1) is True
        assert Dilithium2.verify(pk, msg2, sig2) is True
        # Cross-verify must fail
        assert Dilithium2.verify(pk, msg1, sig2) is False
        assert Dilithium2.verify(pk, msg2, sig1) is False

    def test_invalid_signature_cached_as_false(self):
        """Invalid signatures get cached as False (no re-computation)."""
        pk, sk = Dilithium2.keygen()
        msg = b"test"
        bad_sig = b'\x00' * 2420

        _cached_verify.cache_clear()
        assert Dilithium2.verify(pk, msg, bad_sig) is False
        assert Dilithium2.verify(pk, msg, bad_sig) is False
        info = Dilithium2.cache_info()
        assert info['hits'] >= 1

    def test_cache_info_returns_dict(self):
        """cache_info() should return a dict with standard LRU fields."""
        info = Dilithium2.cache_info()
        assert 'hits' in info
        assert 'misses' in info
        assert 'maxsize' in info
        assert 'currsize' in info
        assert info['maxsize'] == 1024


class TestCacheDoesNotBreakEdgeCases:
    """Ensure caching doesn't mask edge-case failures."""

    def setup_method(self):
        _cached_verify.cache_clear()

    def test_wrong_pk_size_rejected(self):
        assert Dilithium2.verify(b'\x00' * 100, b"msg", b'\x00' * 2420) is False

    def test_wrong_sig_size_rejected(self):
        pk, _ = Dilithium2.keygen()
        assert Dilithium2.verify(pk, b"msg", b'\x00' * 100) is False

    def test_empty_message(self):
        pk, sk = Dilithium2.keygen()
        msg = b""
        sig = Dilithium2.sign(sk, msg)
        assert Dilithium2.verify(pk, msg, sig) is True

    def test_large_message(self):
        pk, sk = Dilithium2.keygen()
        msg = b"A" * 100_000
        sig = Dilithium2.sign(sk, msg)
        assert Dilithium2.verify(pk, msg, sig) is True
