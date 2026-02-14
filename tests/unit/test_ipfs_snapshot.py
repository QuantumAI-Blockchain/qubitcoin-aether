"""Tests for IPFS periodic snapshot scheduling (Batch 12.4)."""
import pytest
from unittest.mock import MagicMock, patch


class TestSnapshotScheduling:
    """Test IPFSManager.should_snapshot() and maybe_snapshot()."""

    def _manager(self):
        """Create an IPFSManager without real IPFS connection."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient'):
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager.__new__(IPFSManager)
            mgr.client = None  # no real IPFS
            return mgr

    def test_should_snapshot_at_interval(self):
        mgr = self._manager()
        mgr.SNAPSHOT_INTERVAL = 100
        assert mgr.should_snapshot(100) is True
        assert mgr.should_snapshot(200) is True
        assert mgr.should_snapshot(1000) is True

    def test_should_not_snapshot_between_intervals(self):
        mgr = self._manager()
        mgr.SNAPSHOT_INTERVAL = 100
        assert mgr.should_snapshot(50) is False
        assert mgr.should_snapshot(101) is False
        assert mgr.should_snapshot(199) is False

    def test_should_not_snapshot_at_zero(self):
        mgr = self._manager()
        assert mgr.should_snapshot(0) is False

    def test_should_not_snapshot_negative(self):
        mgr = self._manager()
        assert mgr.should_snapshot(-1) is False

    def test_default_interval_is_1000(self):
        from qubitcoin.storage.ipfs import IPFSManager
        assert IPFSManager.SNAPSHOT_INTERVAL == 1000


class TestMaybeSnapshot:
    """Test maybe_snapshot() convenience method."""

    def _manager(self):
        with patch('qubitcoin.storage.ipfs.ipfshttpclient'):
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager.__new__(IPFSManager)
            mgr.client = None
            return mgr

    def test_maybe_snapshot_returns_none_when_not_due(self):
        mgr = self._manager()
        mgr.SNAPSHOT_INTERVAL = 100
        db = MagicMock()
        assert mgr.maybe_snapshot(db, 50) is None

    def test_maybe_snapshot_calls_create_when_due(self):
        mgr = self._manager()
        mgr.SNAPSHOT_INTERVAL = 100
        mgr.create_snapshot = MagicMock(return_value='QmFakeCid123')
        db = MagicMock()
        result = mgr.maybe_snapshot(db, 100)
        mgr.create_snapshot.assert_called_once_with(db, 100)
        assert result == 'QmFakeCid123'

    def test_maybe_snapshot_not_called_at_101(self):
        mgr = self._manager()
        mgr.SNAPSHOT_INTERVAL = 100
        mgr.create_snapshot = MagicMock()
        db = MagicMock()
        mgr.maybe_snapshot(db, 101)
        mgr.create_snapshot.assert_not_called()


class TestCreateSnapshotNoIPFS:
    """Verify create_snapshot returns None when IPFS is unavailable."""

    def test_create_returns_none_without_client(self):
        with patch('qubitcoin.storage.ipfs.ipfshttpclient'):
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager.__new__(IPFSManager)
            mgr.client = None
            db = MagicMock()
            assert mgr.create_snapshot(db, 500) is None

    def test_retrieve_returns_none_without_client(self):
        with patch('qubitcoin.storage.ipfs.ipfshttpclient'):
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager.__new__(IPFSManager)
            mgr.client = None
            assert mgr.retrieve_snapshot('QmFake') is None
