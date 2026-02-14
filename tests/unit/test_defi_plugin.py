"""Tests for DeFi Plugin (Batch 18.2)."""
import pytest

from qubitcoin.qvm.defi_plugin import (
    DeFiPlugin,
    LendingPool,
    DEX,
    StakingPool,
    LiquidityPool,
    create_plugin,
    _pair_id,
)
from qubitcoin.qvm.plugins import PluginManager, HookType


class TestDeFiLifecycle:
    def test_name_and_version(self):
        p = DeFiPlugin()
        assert p.name() == 'defi'
        assert p.version() == '0.1.0'

    def test_start_stop(self):
        p = DeFiPlugin()
        p.on_load()
        p.on_start()
        assert p._started is True
        p.on_stop()
        assert p._started is False

    def test_create_plugin_factory(self):
        p = create_plugin()
        assert isinstance(p, DeFiPlugin)

    def test_stats(self):
        p = DeFiPlugin()
        s = p.get_stats()
        assert 'lending' in s
        assert 'staking' in s


class TestLendingPool:
    def test_deposit(self):
        pool = LendingPool()
        pos = pool.deposit('alice', 100.0)
        assert pos.collateral == 100.0

    def test_borrow_within_ratio(self):
        pool = LendingPool(min_collateral_ratio=1.5)
        pool.deposit('alice', 150.0)
        assert pool.borrow('alice', 100.0) is True
        assert pool.get_position('alice').borrowed == 100.0

    def test_borrow_exceeds_ratio(self):
        pool = LendingPool(min_collateral_ratio=1.5)
        pool.deposit('alice', 100.0)
        assert pool.borrow('alice', 100.0) is False

    def test_repay(self):
        pool = LendingPool()
        pool.deposit('alice', 200.0)
        pool.borrow('alice', 50.0)
        assert pool.repay('alice', 30.0) is True
        assert pool.get_position('alice').borrowed == 20.0

    def test_repay_more_than_borrowed(self):
        pool = LendingPool()
        pool.deposit('alice', 200.0)
        pool.borrow('alice', 50.0)
        pool.repay('alice', 100.0)
        assert pool.get_position('alice').borrowed == 0.0

    def test_withdraw(self):
        pool = LendingPool()
        pool.deposit('alice', 100.0)
        assert pool.withdraw('alice', 50.0) is True
        assert pool.get_position('alice').collateral == 50.0

    def test_withdraw_blocked_by_borrow(self):
        pool = LendingPool(min_collateral_ratio=1.5)
        pool.deposit('alice', 150.0)
        pool.borrow('alice', 100.0)
        assert pool.withdraw('alice', 50.0) is False

    def test_liquidation_check(self):
        pool = LendingPool(liquidation_threshold=1.2)
        pool.deposit('alice', 100.0)
        pool.borrow('alice', 60.0)
        # 100/60 = 1.67 > 1.2, no liquidation
        assert pool.check_liquidation('alice') is False

    def test_liquidation_triggered(self):
        pool = LendingPool(min_collateral_ratio=1.0, liquidation_threshold=1.5)
        pool.deposit('alice', 120.0)
        pool.borrow('alice', 100.0)
        # 120/100 = 1.2 < 1.5
        assert pool.check_liquidation('alice') is True

    def test_deposit_negative_raises(self):
        pool = LendingPool()
        with pytest.raises(ValueError):
            pool.deposit('alice', -10.0)

    def test_position_to_dict(self):
        pool = LendingPool()
        pos = pool.deposit('alice', 100.0)
        d = pos.to_dict()
        assert d['address'] == 'alice'
        assert d['collateral'] == 100.0

    def test_pool_stats(self):
        pool = LendingPool()
        pool.deposit('alice', 100.0)
        pool.borrow('alice', 50.0)
        stats = pool.get_stats()
        assert stats['total_deposited'] == 100.0
        assert stats['total_borrowed'] == 50.0


class TestDEX:
    def test_create_pool(self):
        dex = DEX()
        pool = dex.create_pool('QBC', 'QUSD')
        assert pool.token_a == 'QBC'

    def test_duplicate_pool_raises(self):
        dex = DEX()
        dex.create_pool('QBC', 'QUSD')
        with pytest.raises(ValueError):
            dex.create_pool('QBC', 'QUSD')

    def test_add_liquidity(self):
        dex = DEX()
        dex.create_pool('QBC', 'QUSD')
        lp = dex.add_liquidity('QBC', 'QUSD', 100.0, 200.0, 'alice')
        assert lp > 0
        pool = dex.get_pool('QBC', 'QUSD')
        assert pool.reserve_a == 100.0
        assert pool.reserve_b == 200.0

    def test_swap(self):
        dex = DEX()
        dex.create_pool('QBC', 'QUSD')
        dex.add_liquidity('QBC', 'QUSD', 1000.0, 2000.0, 'lp')
        out = dex.swap('QBC', 'QUSD', 10.0)
        assert out > 0
        assert out < 20.0  # Price impact

    def test_swap_fee_deducted(self):
        dex = DEX()
        dex.create_pool('QBC', 'QUSD', fee_rate=0.01)
        dex.add_liquidity('QBC', 'QUSD', 1000.0, 1000.0, 'lp')
        out_with_fee = dex.swap('QBC', 'QUSD', 10.0)

        dex2 = DEX()
        dex2.create_pool('QBC', 'QUSD', fee_rate=0.0)
        dex2.add_liquidity('QBC', 'QUSD', 1000.0, 1000.0, 'lp')
        out_no_fee = dex2.swap('QBC', 'QUSD', 10.0)

        assert out_with_fee < out_no_fee

    def test_get_quote(self):
        dex = DEX()
        dex.create_pool('QBC', 'QUSD')
        dex.add_liquidity('QBC', 'QUSD', 1000.0, 2000.0, 'lp')
        quote = dex.get_quote('QBC', 'QUSD', 10.0)
        assert quote > 0

    def test_list_pools(self):
        dex = DEX()
        dex.create_pool('QBC', 'QUSD')
        dex.create_pool('QBC', 'ETH')
        pools = dex.list_pools()
        assert len(pools) == 2

    def test_pool_to_dict(self):
        dex = DEX()
        dex.create_pool('QBC', 'QUSD')
        dex.add_liquidity('QBC', 'QUSD', 100.0, 200.0, 'lp')
        pool = dex.get_pool('QBC', 'QUSD')
        d = pool.to_dict()
        assert d['price_a_in_b'] == 2.0


class TestStakingPool:
    def test_stake(self):
        pool = StakingPool()
        pos = pool.stake('alice', 100.0)
        assert pos.amount == 100.0

    def test_unstake(self):
        pool = StakingPool()
        pool.stake('alice', 100.0)
        assert pool.unstake('alice', 50.0) is True
        assert pool.get_position('alice').amount == 50.0

    def test_unstake_all_removes_position(self):
        pool = StakingPool()
        pool.stake('alice', 100.0)
        pool.unstake('alice', 100.0)
        assert pool.get_position('alice') is None

    def test_unstake_too_much(self):
        pool = StakingPool()
        pool.stake('alice', 100.0)
        assert pool.unstake('alice', 200.0) is False

    def test_stake_negative_raises(self):
        pool = StakingPool()
        with pytest.raises(ValueError):
            pool.stake('alice', -10.0)

    def test_pending_rewards(self):
        pool = StakingPool(annual_rate=1.0)  # 100% APR for easy testing
        pool.stake('alice', 100.0)
        # Rewards depend on time elapsed, should be >= 0
        rewards = pool.get_pending_rewards('alice')
        assert rewards >= 0

    def test_claim_rewards(self):
        pool = StakingPool(annual_rate=0.1)
        pool.stake('alice', 100.0)
        # Claim should return accumulated (may be tiny due to fast test)
        rewards = pool.claim_rewards('alice')
        assert rewards >= 0

    def test_stats(self):
        pool = StakingPool()
        pool.stake('alice', 100.0)
        stats = pool.get_stats()
        assert stats['total_staked'] == 100.0
        assert stats['positions'] == 1


class TestPairId:
    def test_canonical_order(self):
        assert _pair_id('QBC', 'QUSD') == _pair_id('QUSD', 'QBC')

    def test_different_pairs(self):
        assert _pair_id('QBC', 'QUSD') != _pair_id('QBC', 'ETH')


class TestPluginManagerIntegration:
    def test_register_and_start(self):
        mgr = PluginManager()
        plugin = DeFiPlugin()
        mgr.register(plugin)
        assert mgr.load('defi') is True
        assert mgr.start('defi') is True
