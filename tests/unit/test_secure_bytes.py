"""Unit tests for SecureBytes memory zeroization."""
import pytest

from qubitcoin.quantum.crypto import SecureBytes


class TestSecureBytes:
    """Test SecureBytes zeroization and lifecycle."""

    def test_create_from_bytes(self):
        sb = SecureBytes(b"secret")
        assert len(sb) == 6
        assert not sb.is_zeroed

    def test_bytes_conversion(self):
        data = b"secret data 1234"
        sb = SecureBytes(data)
        assert bytes(sb) == data

    def test_zeroize(self):
        sb = SecureBytes(b"secret data")
        sb.zeroize()
        assert sb.is_zeroed

    def test_double_zeroize_safe(self):
        sb = SecureBytes(b"data")
        sb.zeroize()
        sb.zeroize()  # Should not raise
        assert sb.is_zeroed

    def test_bytes_after_zeroize_raises(self):
        sb = SecureBytes(b"secret")
        sb.zeroize()
        with pytest.raises(ValueError, match="already zeroed"):
            bytes(sb)

    def test_context_manager(self):
        with SecureBytes(b"context data") as sb:
            assert len(sb) == 12
            assert not sb.is_zeroed
        assert sb.is_zeroed

    def test_repr_before_zeroize(self):
        sb = SecureBytes(b"1234")
        assert "4 bytes" in repr(sb)

    def test_repr_after_zeroize(self):
        sb = SecureBytes(b"1234")
        sb.zeroize()
        assert "zeroed" in repr(sb)

    def test_underlying_memory_zeroed(self):
        data = bytearray(b"sensitive key material here")
        sb = SecureBytes(bytes(data))
        sb.zeroize()
        # After zeroization, internal data should be all zeros
        assert all(b == 0 for b in sb._data)

    def test_del_triggers_zeroize(self):
        sb = SecureBytes(b"will be deleted")
        data_ref = sb._data  # Keep reference to internal data
        del sb
        # After del, the data should be zeroed
        assert all(b == 0 for b in data_ref)

    def test_empty_bytes(self):
        sb = SecureBytes(b"")
        assert len(sb) == 0
        sb.zeroize()
        assert sb.is_zeroed
