"""Unit tests for stablecoin engine — initialization, oracle, aggregation."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
import numpy as np


class TestStablecoinInit:
    """Test stablecoin engine initialization."""

    @patch('qubitcoin.stablecoin.engine.StablecoinEngine._ensure_qusd_token')
    @patch('qubitcoin.stablecoin.engine.StablecoinEngine._load_params')
    def test_init_loads_params(self, mock_load, mock_ensure):
        """Engine loads parameters on init."""
        mock_load.return_value = {'min_collateral_ratio': Decimal('1.5')}
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        qe = MagicMock()
        eng = StablecoinEngine(db_manager=db, quantum_engine=qe)
        mock_load.assert_called_once()
        assert eng.params['min_collateral_ratio'] == Decimal('1.5')

    @patch('qubitcoin.stablecoin.engine.StablecoinEngine._ensure_qusd_token')
    @patch('qubitcoin.stablecoin.engine.StablecoinEngine._load_params')
    def test_init_ensures_qusd_token(self, mock_load, mock_ensure):
        """Engine ensures QUSD token exists on init."""
        mock_load.return_value = {}
        from qubitcoin.stablecoin.engine import StablecoinEngine
        eng = StablecoinEngine(db_manager=MagicMock(), quantum_engine=MagicMock())
        mock_ensure.assert_called_once()


class TestParamLoading:
    """Test parameter loading from database."""

    def test_load_decimal_param(self):
        """Decimal params are parsed correctly."""
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()
        session.execute.return_value = [
            ('min_ratio', '1.5', 'decimal'),
        ]
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(StablecoinEngine, '_ensure_qusd_token'):
            eng = StablecoinEngine(db_manager=db, quantum_engine=MagicMock())

        assert eng.params['min_ratio'] == Decimal('1.5')

    def test_load_integer_param(self):
        """Integer params are parsed correctly."""
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()
        session.execute.return_value = [
            ('max_oracles', '5', 'integer'),
        ]
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(StablecoinEngine, '_ensure_qusd_token'):
            eng = StablecoinEngine(db_manager=db, quantum_engine=MagicMock())

        assert eng.params['max_oracles'] == 5

    def test_load_boolean_param(self):
        """Boolean params are parsed correctly."""
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()
        session.execute.return_value = [
            ('active', 'true', 'boolean'),
            ('paused', 'false', 'boolean'),
        ]
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(StablecoinEngine, '_ensure_qusd_token'):
            eng = StablecoinEngine(db_manager=db, quantum_engine=MagicMock())

        assert eng.params['active'] is True
        assert eng.params['paused'] is False


class TestQUSDTokenEnsure:
    """Test QUSD token existence check."""

    def test_existing_active_token(self):
        """Existing active QUSD token is accepted."""
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()

        # _load_params returns empty
        load_result = MagicMock()
        load_result.__iter__ = MagicMock(return_value=iter([]))
        # _ensure_qusd_token finds active token
        ensure_result = MagicMock()
        ensure_result.fetchone.return_value = ('token-1', True)

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                return load_result
            return ensure_result

        session.execute.side_effect = side_effect
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        eng = StablecoinEngine(db_manager=db, quantum_engine=MagicMock())
        # Should not raise
        assert eng is not None

    def test_inactive_token_activated(self):
        """Inactive QUSD token gets activated."""
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()

        load_result = MagicMock()
        load_result.__iter__ = MagicMock(return_value=iter([]))
        ensure_result = MagicMock()
        ensure_result.fetchone.return_value = ('token-1', False)  # inactive

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                return load_result
            return ensure_result

        session.execute.side_effect = side_effect
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        eng = StablecoinEngine(db_manager=db, quantum_engine=MagicMock())
        # Should have called commit to activate
        assert session.commit.called


class TestPriceUpdate:
    """Test oracle price feed updates."""

    def _make_engine(self):
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        session._engine = db  # store for test access

        with patch.object(StablecoinEngine, '_load_params', return_value={}):
            with patch.object(StablecoinEngine, '_ensure_qusd_token'):
                eng = StablecoinEngine(db_manager=db, quantum_engine=MagicMock())
        return eng, session

    def test_update_price_unknown_source(self):
        """Updating price with unknown oracle source returns False."""
        eng, session = self._make_engine()
        # Source not found
        session.execute.return_value.fetchone.return_value = None
        result = eng.update_price(
            asset_pair='USDT/USD',
            price=Decimal('1.0001'),
            source='unknown_oracle',
            block_height=100,
        )
        assert result is False

    def test_update_price_valid_source(self):
        """Updating price with valid oracle source succeeds."""
        eng, session = self._make_engine()
        # Source found
        session.execute.return_value.fetchone.return_value = (1,)
        result = eng.update_price(
            asset_pair='USDT/USD',
            price=Decimal('1.0001'),
            source='chainlink',
            block_height=100,
        )
        assert result is True
        assert session.commit.called


class TestPriceAggregation:
    """Test oracle price aggregation (median calculation)."""

    def _make_engine(self):
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        db.get_current_height.return_value = 100

        with patch.object(StablecoinEngine, '_load_params', return_value={}):
            with patch.object(StablecoinEngine, '_ensure_qusd_token'):
                eng = StablecoinEngine(db_manager=db, quantum_engine=MagicMock())
        return eng, session

    def test_insufficient_data(self):
        """Returns None with fewer than 2 price points."""
        eng, session = self._make_engine()
        session.execute.return_value = [('1.0001',)]  # only 1 price
        result = eng.get_aggregated_price('USDT/USD')
        assert result is None

    def test_median_odd_count(self):
        """Median of odd-count prices is middle value."""
        eng, session = self._make_engine()
        prices = [('0.9998',), ('1.0000',), ('1.0002',)]
        session.execute.return_value = prices
        result = eng.get_aggregated_price('USDT/USD')
        assert result == Decimal('1.0000')

    def test_median_even_count(self):
        """Median of even-count prices is average of middle two."""
        eng, session = self._make_engine()
        prices = [('0.999',), ('1.000',), ('1.001',), ('1.002',)]
        session.execute.return_value = prices
        result = eng.get_aggregated_price('USDT/USD')
        expected = (Decimal('1.000') + Decimal('1.001')) / 2
        assert result == expected


class TestEmergencyShutdownCircuitBreaker:
    """Test QUSD emergency shutdown halts minting."""

    def _make_engine_with_params(self, params: dict):
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(StablecoinEngine, '_load_params', return_value=params):
            with patch.object(StablecoinEngine, '_ensure_qusd_token'):
                eng = StablecoinEngine(db_manager=db, quantum_engine=MagicMock())
        return eng

    def test_emergency_shutdown_blocks_minting(self):
        """When emergency_shutdown=True, mint_qusd returns failure."""
        eng = self._make_engine_with_params({'emergency_shutdown': True})
        success, msg, vault_id = eng.mint_qusd(
            user_address='test_addr',
            collateral_amount=Decimal('1000'),
            collateral_type='USDT',
            block_height=100,
        )
        assert success is False
        assert 'emergency' in msg.lower()
        assert vault_id is None

    def test_no_emergency_allows_mint_attempt(self):
        """Without emergency_shutdown, mint proceeds past the check."""
        eng = self._make_engine_with_params({'emergency_shutdown': False})
        # This will fail at DB query (collateral_types), but NOT at emergency check
        success, msg, vault_id = eng.mint_qusd(
            user_address='test_addr',
            collateral_amount=Decimal('1000'),
            collateral_type='USDT',
            block_height=100,
        )
        # Should fail at a later stage (DB mock), not at emergency check
        assert 'emergency' not in msg.lower()

    def test_missing_emergency_param_allows_mint(self):
        """When emergency_shutdown param is absent, minting is not blocked."""
        eng = self._make_engine_with_params({})  # no emergency_shutdown key
        success, msg, vault_id = eng.mint_qusd(
            user_address='test_addr',
            collateral_amount=Decimal('1000'),
            collateral_type='USDT',
            block_height=100,
        )
        assert 'emergency' not in msg.lower()
