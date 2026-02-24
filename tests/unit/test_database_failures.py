"""Unit tests for database failure modes — connection loss, rollback, edge cases."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.exc import OperationalError, IntegrityError


class TestSessionRollback:
    """Test that get_session rolls back on exceptions."""

    def test_rollback_on_exception(self):
        """Session.rollback() called when exception occurs inside get_session."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        dm.SessionLocal = mock_session_factory

        with pytest.raises(ValueError):
            with dm.get_session() as session:
                raise ValueError("test error")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_close_always_called(self):
        """Session.close() is called even on success."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        dm.SessionLocal = MagicMock(return_value=mock_session)

        with dm.get_session() as session:
            pass  # No exception

        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_operational_error_propagates(self):
        """OperationalError (connection lost) propagates up."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.side_effect = OperationalError("conn lost", {}, None)
        dm.SessionLocal = MagicMock(return_value=mock_session)

        with pytest.raises(OperationalError):
            with dm.get_session() as session:
                session.execute("SELECT 1")


class TestGetBlockEdgeCases:
    """Test get_block with missing or invalid data."""

    def test_get_block_nonexistent_returns_none(self):
        """get_block for a height that doesn't exist returns None."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None
        dm.SessionLocal = MagicMock(return_value=mock_session)

        result = dm.get_block(999999)
        assert result is None

    def test_get_block_negative_height(self):
        """get_block for negative height returns None (no block exists)."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None
        dm.SessionLocal = MagicMock(return_value=mock_session)

        result = dm.get_block(-1)
        assert result is None


class TestGetBalanceEdgeCases:
    """Test get_balance edge cases."""

    def test_balance_unknown_address_is_zero(self):
        """Balance for an address with no UTXOs is 0."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar.return_value = 0
        dm.SessionLocal = MagicMock(return_value=mock_session)

        balance = dm.get_balance('nonexistent_address')
        assert balance == Decimal('0')

    def test_balance_null_result_is_zero(self):
        """Balance returns 0 when DB returns None (COALESCE fallback)."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar.return_value = None
        dm.SessionLocal = MagicMock(return_value=mock_session)

        balance = dm.get_balance('addr')
        assert balance == Decimal('0')


class TestGetCurrentHeight:
    """Test get_current_height edge cases."""

    def test_empty_chain_returns_negative_one(self):
        """Empty blockchain returns -1 (COALESCE(MAX(height), -1))."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar.return_value = -1
        dm.SessionLocal = MagicMock(return_value=mock_session)

        height = dm.get_current_height()
        assert height == -1

    def test_height_returns_int(self):
        """get_current_height returns an integer."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar.return_value = 42
        dm.SessionLocal = MagicMock(return_value=mock_session)

        height = dm.get_current_height()
        assert isinstance(height, int)
        assert height == 42


class TestGetUTXOsEdgeCases:
    """Test UTXO retrieval edge cases."""

    def test_no_utxos_returns_empty_list(self):
        """Address with no UTXOs returns empty list."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.return_value.__iter__ = MagicMock(return_value=iter([]))
        dm.SessionLocal = MagicMock(return_value=mock_session)

        utxos = dm.get_utxos('addr_with_no_utxos')
        assert utxos == []


class TestConnectionPoolConfig:
    """Test database engine configuration."""

    def test_pool_pre_ping_enabled(self):
        """Engine uses pool_pre_ping=True for stale connection detection."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        with patch('qubitcoin.database.manager.create_engine') as mock_engine:
            dm._create_engine()
            call_kwargs = mock_engine.call_args[1]
            assert call_kwargs['pool_pre_ping'] is True

    def test_pool_size_from_config(self):
        """Pool size comes from Config.DB_POOL_SIZE."""
        from qubitcoin.database.manager import DatabaseManager
        from qubitcoin.config import Config
        dm = object.__new__(DatabaseManager)
        with patch('qubitcoin.database.manager.create_engine') as mock_engine:
            dm._create_engine()
            call_kwargs = mock_engine.call_args[1]
            assert call_kwargs['pool_size'] == Config.DB_POOL_SIZE
            assert call_kwargs['max_overflow'] == Config.DB_MAX_OVERFLOW
            assert call_kwargs['pool_timeout'] == Config.DB_POOL_TIMEOUT


class TestIntegrityConstraints:
    """Test database integrity error handling."""

    def test_duplicate_block_raises(self):
        """Inserting duplicate block height raises IntegrityError."""
        from qubitcoin.database.manager import DatabaseManager
        dm = object.__new__(DatabaseManager)
        mock_session = MagicMock()
        mock_session.execute.side_effect = IntegrityError(
            "duplicate key", {}, None
        )
        dm.SessionLocal = MagicMock(return_value=mock_session)

        with pytest.raises(IntegrityError):
            with dm.get_session() as session:
                session.execute("INSERT INTO blocks ...")
