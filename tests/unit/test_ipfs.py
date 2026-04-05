"""Unit tests for IPFS storage manager — snapshot, retrieval, pinning."""
import json
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestIPFSInit:
    """Test IPFS manager initialization."""

    @patch('qubitcoin.storage.ipfs.ipfshttpclient')
    def test_connects_on_init(self, mock_ipfs):
        """IPFSManager connects to IPFS daemon on init."""
        mock_client = MagicMock()
        mock_client.version.return_value = {'Version': '0.20.0'}
        mock_ipfs.connect.return_value = mock_client
        from qubitcoin.storage.ipfs import IPFSManager
        mgr = IPFSManager()
        assert mgr.client is not None
        mock_ipfs.connect.assert_called_once()

    @patch('qubitcoin.storage.ipfs.ipfshttpclient')
    def test_graceful_failure(self, mock_ipfs):
        """IPFSManager degrades gracefully when IPFS is unavailable."""
        mock_ipfs.connect.side_effect = Exception("Connection refused")
        from qubitcoin.storage.ipfs import IPFSManager
        mgr = IPFSManager()
        assert mgr.client is None

    @patch('qubitcoin.storage.ipfs.ipfshttpclient')
    def test_gateway_url(self, mock_ipfs):
        """gateway_url returns correct port."""
        mock_ipfs.connect.side_effect = Exception("offline")
        from qubitcoin.storage.ipfs import IPFSManager
        mgr = IPFSManager()
        assert 'http://127.0.0.1' in mgr.gateway_url


class TestSnapshotCreation:
    """Test snapshot creation and upload."""

    def _make_manager(self):
        """Create an IPFSManager with a mocked client."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_client = MagicMock()
            mock_client.version.return_value = {'Version': '0.20.0'}
            mock_client.add_json.return_value = 'QmTestCID123'
            mock_ipfs.connect.return_value = mock_client
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        return mgr

    def _make_db(self, blocks=None, utxos=None, txs=None):
        """Create a mock db_manager with configurable query results."""
        db = MagicMock()
        session = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        blocks = blocks or []
        utxos = utxos or []
        txs = txs or []

        call_count = [0]
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.fetchall.return_value = blocks
                return result
            elif call_count[0] == 2:
                result.fetchall.return_value = utxos
                return result
            elif call_count[0] == 3:
                result.fetchall.return_value = txs
                return result
            return result

        session.execute.side_effect = execute_side_effect

        mock_block = MagicMock()
        mock_block.block_hash = 'abc123'
        db.get_block.return_value = mock_block
        return db, session

    def test_snapshot_returns_cid(self):
        """Successful snapshot returns IPFS CID."""
        mgr = self._make_manager()
        db, _ = self._make_db()
        cid = mgr.create_snapshot(db, height=10)
        assert cid == 'QmTestCID123'

    def test_snapshot_no_client_returns_none(self):
        """Snapshot returns None when IPFS client is unavailable."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_ipfs.connect.side_effect = Exception("offline")
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        assert mgr.create_snapshot(MagicMock(), height=10) is None

    def test_snapshot_stores_record(self):
        """Snapshot stores CID record in database."""
        mgr = self._make_manager()
        db, session = self._make_db()
        mgr.create_snapshot(db, height=10)
        # _store_snapshot_record should have been called (session.execute called for INSERT)
        assert session.execute.called

    def test_snapshot_upload_failure_returns_none(self):
        """If IPFS upload fails, returns None."""
        mgr = self._make_manager()
        mgr.client.add_json.side_effect = Exception("upload failed")
        db, _ = self._make_db()
        cid = mgr.create_snapshot(db, height=10)
        assert cid is None


class TestSnapshotRetrieval:
    """Test snapshot retrieval from IPFS."""

    def test_retrieve_success(self):
        """Successful retrieval returns snapshot dict."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_client = MagicMock()
            mock_client.version.return_value = {'Version': '0.20.0'}
            mock_ipfs.connect.return_value = mock_client
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        # retrieve_snapshot uses httpx.post directly (inline import),
        # so we patch it at the httpx module level
        mock_response = MagicMock()
        mock_response.json.return_value = {'height': 100, 'blocks': []}
        mock_response.content = b'{"height": 100, "blocks": []}'
        mock_response.raise_for_status.return_value = None
        with patch('httpx.post', return_value=mock_response):
            snapshot = mgr.retrieve_snapshot('QmTestCID')
        assert snapshot is not None
        assert snapshot['height'] == 100

    def test_retrieve_no_client(self):
        """Retrieve returns None when IPFS unavailable."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_ipfs.connect.side_effect = Exception("offline")
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        assert mgr.retrieve_snapshot('QmTest') is None

    def test_retrieve_failure(self):
        """Retrieve returns None on IPFS error."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_client = MagicMock()
            mock_client.version.return_value = {'Version': '0.20.0'}
            mock_client.get_json.side_effect = Exception("not found")
            mock_ipfs.connect.return_value = mock_client
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        assert mgr.retrieve_snapshot('QmBadCID') is None


class TestPeriodicSnapshot:
    """Test periodic snapshot scheduling."""

    def test_should_snapshot_at_interval(self):
        """should_snapshot returns True at SNAPSHOT_INTERVAL multiples."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_ipfs.connect.side_effect = Exception("offline")
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        assert mgr.should_snapshot(1000) is True
        assert mgr.should_snapshot(2000) is True

    def test_should_not_snapshot_between_intervals(self):
        """should_snapshot returns False between intervals."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_ipfs.connect.side_effect = Exception("offline")
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        assert mgr.should_snapshot(500) is False
        assert mgr.should_snapshot(1001) is False

    def test_should_not_snapshot_at_zero(self):
        """should_snapshot returns False at height 0."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_ipfs.connect.side_effect = Exception("offline")
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        assert mgr.should_snapshot(0) is False

    def test_maybe_snapshot_skips_when_not_due(self):
        """maybe_snapshot returns None when interval not met."""
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_ipfs.connect.side_effect = Exception("offline")
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        assert mgr.maybe_snapshot(MagicMock(), 501) is None


class TestPinataPinning:
    """Test Pinata remote pinning."""

    @patch('qubitcoin.storage.ipfs.Config')
    def test_pin_to_pinata_success(self, mock_config):
        """Pinata pinning calls correct API."""
        mock_config.PINATA_JWT = 'test-jwt'
        mock_config.IPFS_API = '/ip4/127.0.0.1/tcp/5001/http'
        mock_config.IPFS_GATEWAY_PORT = 8081
        with patch('qubitcoin.storage.ipfs.ipfshttpclient') as mock_ipfs:
            mock_client = MagicMock()
            mock_client.version.return_value = {'Version': '0.20.0'}
            mock_ipfs.connect.return_value = mock_client
            from qubitcoin.storage.ipfs import IPFSManager
            mgr = IPFSManager()
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mgr._pin_to_pinata('QmTestCID')
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert 'pinata.cloud' in call_args[0][0]
            assert call_args[1]['json']['hashToPin'] == 'QmTestCID'
