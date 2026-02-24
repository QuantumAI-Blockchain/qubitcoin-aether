"""Unit tests for KeyRotationManager — Dilithium key rotation with grace periods."""
import time
from unittest.mock import patch

import pytest

from qubitcoin.quantum.crypto import (
    Dilithium2,
    KeyRotationManager,
    RetiredKey,
    RotationRecord,
)


@pytest.fixture()
def keypair():
    """Generate a fresh Dilithium2 keypair for tests."""
    return Dilithium2.keygen()


@pytest.fixture()
def manager(keypair):
    """Create a KeyRotationManager with a 7-day grace period."""
    pk, sk = keypair
    return KeyRotationManager(
        current_public_key=pk,
        current_private_key=sk,
        grace_period_days=7,
    )


class TestKeyRotationManagerInit:
    """Tests for initial state."""

    def test_initial_state(self, keypair, manager):
        pk, sk = keypair
        assert manager.current_public_key == pk
        assert manager.current_private_key == sk
        assert manager.current_address == Dilithium2.derive_address(pk)
        assert manager.grace_period_days == 7.0
        assert manager.history == []
        assert manager.active_retired_keys == []

    def test_custom_grace_period(self, keypair):
        pk, sk = keypair
        mgr = KeyRotationManager(pk, sk, grace_period_days=30)
        assert mgr.grace_period_days == 30.0


class TestRotateKeys:
    """Tests for the rotate_keys() method."""

    def test_rotate_returns_new_keys(self, manager):
        old_pk = manager.current_public_key
        new_pk, new_sk, record = manager.rotate_keys()
        assert new_pk != old_pk
        assert isinstance(new_pk, bytes)
        assert isinstance(new_sk, bytes)
        assert len(new_pk) == 1312
        assert len(new_sk) == 2528

    def test_rotate_updates_current_key(self, manager):
        old_pk = manager.current_public_key
        new_pk, new_sk, _ = manager.rotate_keys()
        assert manager.current_public_key == new_pk
        assert manager.current_private_key == new_sk
        assert manager.current_address == Dilithium2.derive_address(new_pk)

    def test_rotate_retires_old_key(self, manager, keypair):
        pk, _ = keypair
        manager.rotate_keys()
        retired = manager.active_retired_keys
        assert len(retired) == 1
        assert retired[0].public_key_hex == pk.hex()

    def test_rotate_records_history(self, manager, keypair):
        pk, _ = keypair
        _, _, record = manager.rotate_keys()
        assert len(manager.history) == 1
        assert isinstance(record, RotationRecord)
        assert record.old_public_key_hex == pk.hex()
        assert record.new_public_key_hex == manager.current_public_key.hex()
        assert record.revoked is False

    def test_multiple_rotations(self, manager):
        keys = [manager.current_public_key]
        for _ in range(3):
            new_pk, _, _ = manager.rotate_keys()
            keys.append(new_pk)
        assert len(manager.history) == 3
        assert len(manager.active_retired_keys) == 3
        # Current key should be the last one generated
        assert manager.current_public_key == keys[-1]

    def test_grace_period_timestamps(self, manager):
        before = time.time()
        _, _, record = manager.rotate_keys()
        after = time.time()
        assert before <= record.rotated_at <= after
        expected_grace = record.rotated_at + (7 * 86400)
        assert abs(record.grace_expires_at - expected_grace) < 1.0


class TestVerify:
    """Tests for signature verification through the rotation manager."""

    def test_verify_with_current_key(self, manager):
        msg = b"test message"
        sig = Dilithium2.sign(manager.current_private_key, msg)
        assert manager.verify(manager.current_public_key, msg, sig)

    def test_verify_with_retired_key_in_grace(self, manager, keypair):
        pk_old, sk_old = keypair
        msg = b"signed before rotation"
        sig = Dilithium2.sign(sk_old, msg)
        # Rotate keys
        manager.rotate_keys()
        # Old key should still work during grace
        assert manager.verify(pk_old, msg, sig)

    def test_verify_with_new_key_after_rotation(self, manager):
        manager.rotate_keys()
        msg = b"signed after rotation"
        sig = Dilithium2.sign(manager.current_private_key, msg)
        assert manager.verify(manager.current_public_key, msg, sig)

    def test_verify_rejects_unknown_key(self, manager):
        unknown_pk, unknown_sk = Dilithium2.keygen()
        msg = b"test"
        sig = Dilithium2.sign(unknown_sk, msg)
        assert not manager.verify(unknown_pk, msg, sig)

    def test_verify_rejects_expired_retired_key(self, manager, keypair):
        pk_old, sk_old = keypair
        msg = b"old message"
        sig = Dilithium2.sign(sk_old, msg)
        manager.rotate_keys()
        # Simulate time passing beyond grace period
        expired_time = time.time() + (8 * 86400)
        with patch('qubitcoin.quantum.crypto.time') as mock_time:
            mock_time.time.return_value = expired_time
            assert not manager.verify(pk_old, msg, sig)

    def test_verify_invalid_signature(self, manager):
        msg = b"test"
        bad_sig = b'\x00' * 2420
        assert not manager.verify(manager.current_public_key, msg, bad_sig)


class TestIsKeyAccepted:
    """Tests for the is_key_accepted() method."""

    def test_current_key_accepted(self, manager):
        assert manager.is_key_accepted(manager.current_public_key)

    def test_retired_key_accepted_in_grace(self, manager, keypair):
        pk_old, _ = keypair
        manager.rotate_keys()
        assert manager.is_key_accepted(pk_old)

    def test_unknown_key_not_accepted(self, manager):
        unknown_pk, _ = Dilithium2.keygen()
        assert not manager.is_key_accepted(unknown_pk)

    def test_expired_key_not_accepted(self, manager, keypair):
        pk_old, _ = keypair
        manager.rotate_keys()
        expired_time = time.time() + (8 * 86400)
        with patch('qubitcoin.quantum.crypto.time') as mock_time:
            mock_time.time.return_value = expired_time
            assert not manager.is_key_accepted(pk_old)


class TestRevokeKey:
    """Tests for immediate key revocation."""

    def test_revoke_retired_key(self, manager, keypair):
        pk_old, _ = keypair
        manager.rotate_keys()
        assert manager.revoke_key(pk_old.hex())
        assert not manager.is_key_accepted(pk_old)
        assert len(manager.active_retired_keys) == 0

    def test_revoke_marks_history(self, manager, keypair):
        pk_old, _ = keypair
        manager.rotate_keys()
        manager.revoke_key(pk_old.hex())
        assert manager.history[0].revoked is True

    def test_revoke_nonexistent_key(self, manager):
        unknown_pk, _ = Dilithium2.keygen()
        assert not manager.revoke_key(unknown_pk.hex())

    def test_revoke_after_already_revoked(self, manager, keypair):
        pk_old, _ = keypair
        manager.rotate_keys()
        assert manager.revoke_key(pk_old.hex())
        # Second revoke should fail (already removed)
        assert not manager.revoke_key(pk_old.hex())


class TestGetStatus:
    """Tests for the get_status() summary."""

    def test_initial_status(self, manager):
        status = manager.get_status()
        assert status['current_address'] == manager.current_address
        assert status['grace_period_days'] == 7.0
        assert status['retired_keys_in_grace'] == 0
        assert status['total_rotations'] == 0
        assert status['retired_keys'] == []
        assert status['history'] == []

    def test_status_after_rotation(self, manager):
        manager.rotate_keys()
        status = manager.get_status()
        assert status['retired_keys_in_grace'] == 1
        assert status['total_rotations'] == 1
        assert len(status['retired_keys']) == 1
        assert len(status['history']) == 1
        rk = status['retired_keys'][0]
        assert 'address' in rk
        assert 'retired_at' in rk
        assert 'grace_expires_at' in rk
        assert rk['seconds_remaining'] > 0

    def test_status_history_entry_fields(self, manager):
        manager.rotate_keys()
        entry = manager.get_status()['history'][0]
        assert 'old_address' in entry
        assert 'new_address' in entry
        assert 'rotated_at' in entry
        assert 'grace_expires_at' in entry
        assert entry['revoked'] is False


class TestGracePeriodExpiry:
    """Tests for automatic purging of expired retired keys."""

    def test_expired_keys_purged_on_access(self, manager, keypair):
        pk_old, _ = keypair
        manager.rotate_keys()
        assert len(manager.active_retired_keys) == 1
        # Simulate time beyond grace
        expired_time = time.time() + (8 * 86400)
        with patch('qubitcoin.quantum.crypto.time') as mock_time:
            mock_time.time.return_value = expired_time
            assert len(manager.active_retired_keys) == 0

    def test_mixed_expired_and_active(self, manager):
        # First rotation
        manager.rotate_keys()
        first_retired = manager.active_retired_keys[0]

        # Second rotation (simulated 1 day later)
        with patch('qubitcoin.quantum.crypto.time') as mock_time:
            mock_time.time.return_value = time.time() + 86400
            manager.rotate_keys()

        # Now simulate 7.5 days from first rotation — first key expired,
        # second still in grace
        check_time = time.time() + (7.5 * 86400)
        with patch('qubitcoin.quantum.crypto.time') as mock_time:
            mock_time.time.return_value = check_time
            active = manager.active_retired_keys
            assert len(active) == 1
            # The remaining one should be the second retired key (not the first)
            assert active[0].public_key_hex != first_retired.public_key_hex


class TestDataclasses:
    """Tests for the RotationRecord and RetiredKey dataclasses."""

    def test_rotation_record_fields(self):
        rec = RotationRecord(
            old_public_key_hex='aabb',
            new_public_key_hex='ccdd',
            new_address='addr123',
            rotated_at=1000.0,
            grace_expires_at=2000.0,
        )
        assert rec.old_public_key_hex == 'aabb'
        assert rec.revoked is False

    def test_retired_key_fields(self):
        rk = RetiredKey(
            public_key_hex='aabb',
            address='addr123',
            retired_at=1000.0,
            grace_expires_at=2000.0,
        )
        assert rk.public_key_hex == 'aabb'
        assert rk.grace_expires_at == 2000.0
