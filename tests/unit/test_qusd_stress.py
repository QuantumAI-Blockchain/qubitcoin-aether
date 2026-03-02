"""QUSD peg stress tests — extreme market conditions.

Simulates price crashes, reserve drains, rapid oscillations, zero liquidity,
max supply, and concurrent operations to verify the StablecoinEngine degrades
gracefully under adversarial scenarios.
"""

import time
from decimal import Decimal
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(
    params: Optional[Dict] = None,
    qvm: Optional[object] = None,
    health_row: Optional[tuple] = None,
):
    """Create a StablecoinEngine with mocked dependencies.

    Args:
        params: ``_load_params`` return value (defaults to empty dict).
        qvm: Optional QVM mock for on-chain queries.
        health_row: Row returned by ``qusd_health`` view query.

    Returns:
        (engine, mock_session) tuple.
    """
    from qubitcoin.stablecoin.engine import StablecoinEngine

    db = MagicMock()
    session = MagicMock()
    db.get_session.return_value.__enter__ = MagicMock(return_value=session)
    db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    db.get_current_height.return_value = 100

    if health_row is not None:
        session.execute.return_value.fetchone.return_value = health_row

    with patch.object(StablecoinEngine, '_load_params', return_value=params or {}):
        with patch.object(StablecoinEngine, '_ensure_qusd_token'):
            eng = StablecoinEngine(
                db_manager=db, quantum_engine=MagicMock(), qvm=qvm,
            )
    return eng, session


# ===========================================================================
# E12: QUSD PEG STRESS TESTS
# ===========================================================================


class TestPriceCrash50Percent:
    """Simulate a 50% QBC price crash and verify system stays intact."""

    def test_reserve_ratio_drops_but_system_reports(self):
        """After a 50% crash the reserve ratio drops but get_system_health
        still returns valid data without raising."""
        # Before crash: reserve=0.95
        eng, session = _make_engine(
            health_row=('1000000', '0.95', '500000', 10, 0),
        )
        health_before = eng.get_system_health()
        assert health_before['reserve_backing'] == Decimal('0.95')

        # After crash: reserve ratio halves because QBC collateral lost value
        session.execute.return_value.fetchone.return_value = (
            '1000000', '0.475', '500000', 10, 5,
        )
        health_after = eng.get_system_health()
        assert health_after['reserve_backing'] == Decimal('0.475')
        assert health_after['at_risk_vaults'] == 5
        # System did not crash — returned valid dict
        assert 'total_qusd' in health_after

    def test_emergency_shutdown_blocks_minting_during_crash(self):
        """During a severe crash with emergency_shutdown=True, minting is
        blocked."""
        eng, _ = _make_engine(params={'emergency_shutdown': True})
        success, msg, vault_id = eng.mint_qusd(
            user_address='crash_user',
            collateral_amount=Decimal('10000'),
            collateral_type='QBC',
            block_height=200,
        )
        assert success is False
        assert 'emergency' in msg.lower()


class TestMassiveReserveWithdrawal:
    """Simulate 90% reserve withdrawal — verify circuit breaker behavior."""

    def test_reserve_drops_to_near_zero(self):
        """System health reports near-zero backing after massive withdrawal."""
        eng, session = _make_engine(
            health_row=('1000000', '0.10', '900000', 2, 8),
        )
        health = eng.get_system_health()
        assert health['reserve_backing'] == Decimal('0.10')
        assert health['at_risk_vaults'] == 8

    def test_mint_blocked_when_debt_ceiling_reached(self):
        """Minting is blocked when the debt ceiling is reached after a
        withdrawal pushes the system to its limit."""
        eng, session = _make_engine(params={})

        # Set up collateral type with a very low debt ceiling
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # UTXO balance check (collateral verification)
                result.scalar.return_value = '999999'
                return result
            if call_count[0] == 2:
                # qusd_health query (from get_system_health in mint_qusd)
                result.fetchone.return_value = (
                    '1000000', '0.95', '500000', 10, 0,
                )
                return result
            if call_count[0] == 3:
                # collateral_types query: ceiling = 100, asset = stablecoin
                result.fetchone.return_value = (
                    1, '1.5', '100', '10', 'stablecoin',
                )
                return result
            if call_count[0] == 4:
                # current debt SUM query — at ceiling
                result.scalar.return_value = '100'
                return result
            return MagicMock()

        session.execute.side_effect = side_effect

        # Mock get_aggregated_price to return None so the stablecoin
        # fallback ($1.00) is used, avoiding extra session.execute calls
        with patch.object(eng, 'get_aggregated_price', return_value=None):
            success, msg, _ = eng.mint_qusd(
                user_address='whale',
                collateral_amount=Decimal('1000'),
                collateral_type='QBC',
                block_height=300,
            )
        assert success is False
        assert 'ceiling' in msg.lower()


class TestRapidPriceOscillation:
    """Simulate rapid price oscillation: 1.0 -> 0.5 -> 1.5 -> 0.3."""

    def test_health_reflects_each_price_point(self):
        """System health updates correctly as the reserve ratio swings."""
        eng, session = _make_engine()
        price_sequence = [
            ('1000000', '1.00', '500000', 10, 0),  # $1.00
            ('1000000', '0.50', '500000', 10, 3),  # crash to $0.50
            ('1000000', '1.50', '500000', 10, 0),  # spike to $1.50
            ('1000000', '0.30', '500000', 10, 8),  # crash to $0.30
        ]
        for row in price_sequence:
            session.execute.return_value.fetchone.return_value = row
            health = eng.get_system_health()
            assert health['reserve_backing'] == Decimal(row[1])

    def test_oscillation_does_not_corrupt_engine_state(self):
        """After rapid oscillations, engine attributes remain intact."""
        eng, session = _make_engine()
        for backing in ['0.50', '1.50', '0.30', '1.20', '0.10', '2.00']:
            session.execute.return_value.fetchone.return_value = (
                '1000000', backing, '500000', 10, 0,
            )
            eng.get_system_health()

        # Engine is still functional
        assert eng.db is not None
        assert isinstance(eng.params, dict)


class TestZeroLiquidity:
    """Simulate all reserves drained — zero liquidity."""

    def test_health_reports_zero_backing(self):
        """When reserves are completely drained, backing is reported as 0."""
        eng, session = _make_engine(
            health_row=('1000000', '0', '1000000', 0, 0),
        )
        health = eng.get_system_health()
        assert health['reserve_backing'] == Decimal('0')

    def test_mint_fails_with_no_price_feed(self):
        """Minting fails when price feed is unavailable (zero liquidity
        likely means oracle failure too)."""
        eng, session = _make_engine(params={})

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # UTXO balance check (collateral verification)
                result.scalar.return_value = '999999'
                return result
            if call_count[0] == 2:
                # qusd_health query (from get_system_health in mint_qusd)
                result.fetchone.return_value = (
                    '1000000', '0.95', '500000', 10, 0,
                )
                return result
            if call_count[0] == 3:
                # collateral_types query
                result.fetchone.return_value = (
                    1, '1.5', '999999999', '10', 'volatile',
                )
                return result
            # aggregated price query returns insufficient data
            result.__iter__ = MagicMock(return_value=iter([('1.0',)]))
            return result

        session.execute.side_effect = side_effect

        # Patch get_aggregated_price to return None (oracle failure)
        with patch.object(eng, 'get_aggregated_price', return_value=None):
            success, msg, _ = eng.mint_qusd(
                user_address='ghost',
                collateral_amount=Decimal('1000'),
                collateral_type='QBC',
                block_height=400,
            )
        assert success is False
        assert 'price' in msg.lower()


class TestPegDeviationTracking:
    """Verify peg history records large deviations."""

    def test_aggregated_price_deviation_marked_invalid(self):
        """Aggregated price with high std deviation is marked invalid."""
        eng, session = _make_engine()
        # Prices with wide spread: std_dev > 0.01
        prices = [('0.50',), ('1.50',), ('0.80',), ('1.20',)]
        session.execute.return_value = prices

        # get_aggregated_price calculates median and checks std_dev < 0.01
        result = eng.get_aggregated_price('QBC/USD')
        # Despite the deviation, the method still returns a median
        assert result is not None
        # The stored record should have valid=False (std_dev > 0.01)
        # Verify the INSERT was called with valid=False
        # session.execute is called with positional args: (text_obj, params_dict)
        calls = session.execute.call_args_list
        # The last execute call is the INSERT INTO aggregated_prices
        insert_call = calls[-1]
        # Positional args: insert_call[0] = (text_obj, params_dict)
        insert_params = insert_call[0][1]
        assert insert_params['valid'] is False

    def test_tight_spread_marked_valid(self):
        """Aggregated price with tight spread is marked valid."""
        eng, session = _make_engine()
        # Very tight prices (< 1% std_dev)
        prices = [('1.0001',), ('1.0002',), ('1.0000',)]
        session.execute.return_value = prices

        result = eng.get_aggregated_price('QBC/USD')
        assert result is not None
        calls = session.execute.call_args_list
        insert_call = calls[-1]
        insert_params = insert_call[0][1]
        assert insert_params['valid'] is True


class TestRecoverySimulation:
    """After a crash, simulate price recovery and verify normal operation."""

    def test_recovery_restores_healthy_state(self):
        """System transitions from critical to healthy as reserve recovers."""
        eng, session = _make_engine()

        # Phase 1: Crash — reserve at 30%
        session.execute.return_value.fetchone.return_value = (
            '1000000', '0.30', '700000', 10, 7,
        )
        health_crash = eng.get_system_health()
        assert health_crash['reserve_backing'] == Decimal('0.30')
        assert health_crash['at_risk_vaults'] == 7

        # Phase 2: Recovery — reserve at 100%
        session.execute.return_value.fetchone.return_value = (
            '1000000', '1.00', '500000', 10, 0,
        )
        health_recovered = eng.get_system_health()
        assert health_recovered['reserve_backing'] == Decimal('1.00')
        assert health_recovered['at_risk_vaults'] == 0

    def test_emergency_shutdown_can_be_lifted(self):
        """After recovery, emergency_shutdown=False allows minting again."""
        # During crash
        eng_shutdown, _ = _make_engine(params={'emergency_shutdown': True})
        success, msg, _ = eng_shutdown.mint_qusd(
            'user', Decimal('100'), 'USDT', 500,
        )
        assert success is False

        # After recovery — new engine state with shutdown lifted
        eng_recovered, _ = _make_engine(params={'emergency_shutdown': False})
        success, msg, _ = eng_recovered.mint_qusd(
            'user', Decimal('100'), 'USDT', 600,
        )
        # It proceeds past emergency check (may fail on collateral lookup,
        # but NOT on emergency shutdown)
        assert 'emergency' not in msg.lower()


class TestConcurrentMintBurn:
    """Simulate multiple operations in quick succession."""

    def test_sequential_mints_all_hit_emergency_check(self):
        """Multiple rapid mint calls during emergency all get blocked."""
        eng, _ = _make_engine(params={'emergency_shutdown': True})
        results = []
        for i in range(10):
            success, msg, _ = eng.mint_qusd(
                f'user_{i}', Decimal('100'), 'USDT', 700 + i,
            )
            results.append((success, msg))

        assert all(not r[0] for r in results)
        assert all('emergency' in r[1].lower() for r in results)

    def test_sequential_mints_without_emergency(self):
        """Multiple rapid mint calls proceed to collateral check."""
        eng, session = _make_engine(params={})
        # All will fail at collateral lookup (mocked DB returns None)
        session.execute.return_value.fetchone.return_value = None
        results = []
        for i in range(5):
            success, msg, _ = eng.mint_qusd(
                f'user_{i}', Decimal('100'), 'QBC', 800 + i,
            )
            results.append(msg)

        # All should have gotten past emergency and failed at collateral
        for msg in results:
            assert 'emergency' not in msg.lower()


class TestMaxSupplyReached:
    """Verify behavior when QUSD approaches maximum supply."""

    def test_debt_ceiling_prevents_over_minting(self):
        """When total debt equals debt ceiling, minting is rejected."""
        eng, session = _make_engine(params={})

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # UTXO balance check (collateral verification)
                result.scalar.return_value = '999999'
                return result
            if call_count[0] == 2:
                # qusd_health query (from get_system_health in mint_qusd)
                result.fetchone.return_value = (
                    '1000000', '0.95', '500000', 10, 0,
                )
                return result
            if call_count[0] == 3:
                # collateral_types query: ceiling = 1_000_000, asset = stablecoin
                result.fetchone.return_value = (
                    1, '1.5', '1000000', '10', 'stablecoin',
                )
                return result
            if call_count[0] == 4:
                # current_debt SUM query — already at ceiling
                result.scalar.return_value = '1000000'
                return result
            return MagicMock()

        session.execute.side_effect = side_effect

        # Mock get_aggregated_price to return None so the stablecoin
        # fallback ($1.00) is used — avoids extra session.execute calls
        with patch.object(eng, 'get_aggregated_price', return_value=None):
            success, msg, _ = eng.mint_qusd(
                'big_minter', Decimal('1000'), 'USDT', 900,
            )
        assert success is False
        assert 'ceiling' in msg.lower()

    def test_small_mint_allowed_under_ceiling(self):
        """A small mint should pass the ceiling check when debt is low."""
        eng, session = _make_engine(params={})

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # UTXO balance check (collateral verification)
                result.scalar.return_value = '999999'
                return result
            if call_count[0] == 2:
                # qusd_health query (from get_system_health in mint_qusd)
                result.fetchone.return_value = (
                    '1000000', '0.95', '500000', 10, 0,
                )
                return result
            if call_count[0] == 3:
                # collateral_types: high ceiling, stablecoin asset
                result.fetchone.return_value = (
                    1, '1.5', '999999999', '10', 'stablecoin',
                )
                return result
            if call_count[0] == 4:
                # current debt SUM is very low
                result.scalar.return_value = '100'
                return result
            if call_count[0] == 5:
                # vault creation returns vault_id
                result.scalar.return_value = 'vault-123'
                return result
            return MagicMock()

        session.execute.side_effect = side_effect

        # Mock the quantum engine for proof generation
        eng.quantum.generate_hamiltonian.return_value = {}
        eng.quantum.optimize_vqe.return_value = (
            MagicMock(tolist=lambda: [0.1, 0.2]), -1.5,
        )

        # Mock get_aggregated_price to return None (stablecoin fallback $1.00)
        with patch.object(eng, 'get_aggregated_price', return_value=None):
            success, msg, vault_id = eng.mint_qusd(
                'small_minter', Decimal('100'), 'USDT', 950,
            )
        # Passes ceiling check — may still fail on subsequent DB ops
        # (since mocking is minimal), but the important thing is it
        # got past the debt ceiling check
        if not success:
            assert 'ceiling' not in msg.lower()


class TestOnChainReserveFallback:
    """Verify on-chain reserve query fallback during stress."""

    def test_qvm_error_falls_back_gracefully(self):
        """If QVM raises during a stress scenario, health still works."""
        mock_qvm = MagicMock()
        mock_qvm.static_call.side_effect = RuntimeError("QVM overloaded")
        eng, session = _make_engine(
            qvm=mock_qvm,
            health_row=('1000000', '0.40', '600000', 5, 3),
        )
        eng._qusd_reserve_addr = 'r' * 40
        eng._qusd_token_addr = 't' * 40

        health = eng.get_system_health()
        assert health['reserve_source'] == 'in_memory'
        assert health['reserve_backing'] == Decimal('0.40')

    def test_zero_supply_on_chain(self):
        """On-chain reserve ratio with zero supply returns Decimal(0)."""
        mock_qvm = MagicMock()
        eng, session = _make_engine(
            qvm=mock_qvm,
            health_row=('0', '0', '0', 0, 0),
        )
        eng._qusd_reserve_addr = 'r' * 40
        eng._qusd_token_addr = 't' * 40

        # Reserve=100, Supply=0
        mock_qvm.static_call.side_effect = [
            (100).to_bytes(32, 'big'),
            (0).to_bytes(32, 'big'),
        ]
        health = eng.get_system_health()
        # On-chain ratio should be 0 (not division error)
        assert health['on_chain_reserve_ratio'] == Decimal('0')


class TestBurnUnderStress:
    """Test burn operations under stress conditions."""

    def test_burn_with_nonexistent_vault(self):
        """Burning against a nonexistent vault returns failure."""
        eng, session = _make_engine()
        session.execute.return_value.fetchone.return_value = None
        success, msg = eng.burn_qusd('user', Decimal('100'), 'vault-999', 100)
        assert success is False
        assert 'not found' in msg.lower()

    def test_burn_by_non_owner(self):
        """Burning by a non-owner is rejected."""
        eng, session = _make_engine()
        session.execute.return_value.fetchone.return_value = (
            'real_owner', '1000', '500', 1,
        )
        success, msg = eng.burn_qusd('impostor', Decimal('100'), 'vault-1', 100)
        assert success is False
        assert 'not vault owner' in msg.lower()
