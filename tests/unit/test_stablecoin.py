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


# ============================================================================
# S03: get_system_health on-chain wiring tests
# ============================================================================


class TestSystemHealthOnChainWiring:
    """Test get_system_health integration with on-chain reserve ratio."""

    def _make_engine(self, qvm=None):
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(StablecoinEngine, '_load_params', return_value={}):
            with patch.object(StablecoinEngine, '_ensure_qusd_token'):
                eng = StablecoinEngine(
                    db_manager=db, quantum_engine=MagicMock(), qvm=qvm
                )
        return eng, session

    def test_health_falls_back_to_in_memory_without_qvm(self):
        """Without QVM, get_system_health uses in-memory data."""
        eng, session = self._make_engine(qvm=None)
        # qusd_health view returns a row
        session.execute.return_value.fetchone.return_value = (
            '1000000', '0.85', '500000', 10, 2
        )
        health = eng.get_system_health()
        assert health['reserve_source'] == 'in_memory'
        assert health['reserve_backing'] == Decimal('0.85')
        assert 'on_chain_reserve_ratio' not in health

    def test_health_uses_on_chain_when_available(self):
        """With QVM + deployed contracts, on-chain ratio overrides in-memory."""
        mock_qvm = MagicMock()
        eng, session = self._make_engine(qvm=mock_qvm)

        # Set contract addresses
        eng._qusd_reserve_addr = 'r' * 40
        eng._qusd_token_addr = 't' * 40

        # qusd_health view
        session.execute.return_value.fetchone.return_value = (
            '1000000', '0.50', '500000', 10, 2
        )

        # Mock QVM static_call: reserve=900000, supply=1000000 → ratio=0.9
        reserve_bytes = (900000).to_bytes(32, 'big')
        supply_bytes = (1000000).to_bytes(32, 'big')
        mock_qvm.static_call.side_effect = [reserve_bytes, supply_bytes]

        health = eng.get_system_health()
        assert health['reserve_source'] == 'on_chain'
        assert health['on_chain_reserve_ratio'] == Decimal('900000') / Decimal('1000000')
        assert health['reserve_backing'] == health['on_chain_reserve_ratio']

    def test_health_falls_back_on_qvm_error(self):
        """When QVM static_call raises, falls back to in-memory gracefully."""
        mock_qvm = MagicMock()
        eng, session = self._make_engine(qvm=mock_qvm)
        eng._qusd_reserve_addr = 'r' * 40
        eng._qusd_token_addr = 't' * 40

        session.execute.return_value.fetchone.return_value = (
            '1000000', '0.75', '500000', 10, 2
        )
        mock_qvm.static_call.side_effect = RuntimeError("QVM offline")

        health = eng.get_system_health()
        assert health['reserve_source'] == 'in_memory'
        assert health['reserve_backing'] == Decimal('0.75')

    def test_health_returns_defaults_when_no_db_view(self):
        """When qusd_health view returns None, returns zero defaults."""
        eng, session = self._make_engine(qvm=None)
        session.execute.return_value.fetchone.return_value = None
        health = eng.get_system_health()
        assert health['total_qusd'] == Decimal(0)
        assert health['reserve_backing'] == Decimal(0)
        assert health['reserve_source'] == 'in_memory'


class TestSyncFromChain:
    """Test sync_from_chain method."""

    def _make_engine(self, qvm=None):
        from qubitcoin.stablecoin.engine import StablecoinEngine
        db = MagicMock()
        session = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(StablecoinEngine, '_load_params', return_value={}):
            with patch.object(StablecoinEngine, '_ensure_qusd_token'):
                eng = StablecoinEngine(
                    db_manager=db, quantum_engine=MagicMock(), qvm=qvm
                )
        return eng

    def test_sync_without_qvm_returns_false(self):
        """sync_from_chain returns False when no QVM is available."""
        eng = self._make_engine(qvm=None)
        assert eng.sync_from_chain() is False

    def test_sync_with_qvm_success(self):
        """sync_from_chain succeeds with valid QVM responses."""
        mock_qvm = MagicMock()
        eng = self._make_engine(qvm=mock_qvm)
        eng._qusd_reserve_addr = 'r' * 40
        eng._qusd_token_addr = 't' * 40

        supply_bytes = (2000000).to_bytes(32, 'big')
        reserve_bytes = (1800000).to_bytes(32, 'big')
        mock_qvm.static_call.side_effect = [supply_bytes, reserve_bytes]

        assert eng.sync_from_chain() is True

    def test_sync_handles_empty_response(self):
        """sync_from_chain returns False when contracts return empty data."""
        mock_qvm = MagicMock()
        eng = self._make_engine(qvm=mock_qvm)
        eng._qusd_reserve_addr = 'r' * 40
        eng._qusd_token_addr = 't' * 40

        mock_qvm.static_call.return_value = None  # Empty response

        assert eng.sync_from_chain() is False
