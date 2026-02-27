"""Unit tests for QUSDSavingsRate — QUSD DSR-style savings yield."""

import time
import pytest
from decimal import Decimal
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def savings():
    """Return a fresh QUSDSavingsRate instance with default config."""
    from qubitcoin.stablecoin.savings import QUSDSavingsRate
    return QUSDSavingsRate()


@pytest.fixture
def savings_custom():
    """Return a QUSDSavingsRate with explicit parameters for deterministic tests."""
    from qubitcoin.stablecoin.savings import QUSDSavingsRate
    return QUSDSavingsRate(
        annual_rate=0.10,      # 10% APY for easier math
        min_deposit=Decimal('1.0'),
        max_rate=0.20,
    )


# ===========================================================================
# Initialisation
# ===========================================================================

class TestInit:
    """Verify constructor and defaults."""

    def test_default_rate(self, savings):
        """Default rate matches Config.QUSD_SAVINGS_RATE (3.3%)."""
        assert savings.get_current_rate() == pytest.approx(0.033, abs=1e-6)

    def test_custom_rate(self, savings_custom):
        """Custom rate is stored correctly."""
        assert savings_custom.get_current_rate() == pytest.approx(0.10, abs=1e-6)

    def test_initial_deposits_zero(self, savings):
        """Total deposits start at zero."""
        assert savings.get_total_deposits() == Decimal('0')

    def test_stats_initial(self, savings):
        """get_stats returns sane defaults on a fresh instance."""
        stats = savings.get_stats()
        assert stats['total_deposits'] == Decimal('0')
        assert stats['total_interest_paid'] == Decimal('0')
        assert stats['depositor_count'] == 0
        assert stats['last_accrual_block'] == 0
        assert stats['current_rate'] == pytest.approx(0.033, abs=1e-6)
        assert isinstance(stats['blocks_per_year'], int)

    def test_rate_clamped_to_max(self):
        """Rate exceeding max_rate is clamped during init."""
        from qubitcoin.stablecoin.savings import QUSDSavingsRate
        sr = QUSDSavingsRate(annual_rate=0.50, max_rate=0.20)
        assert sr.get_current_rate() == pytest.approx(0.20, abs=1e-6)

    def test_negative_rate_clamped_to_zero(self):
        """Negative rate is clamped to zero during init."""
        from qubitcoin.stablecoin.savings import QUSDSavingsRate
        sr = QUSDSavingsRate(annual_rate=-0.05, max_rate=0.20)
        assert sr.get_current_rate() == pytest.approx(0.0, abs=1e-6)


# ===========================================================================
# Deposits
# ===========================================================================

class TestDeposit:
    """Test the deposit() method."""

    def test_basic_deposit(self, savings):
        """A single deposit increases balance and total_deposits."""
        result = savings.deposit('alice', Decimal('100'))
        assert result['deposited'] == Decimal('100')
        assert savings.get_balance('alice') == Decimal('100')
        assert savings.get_total_deposits() == Decimal('100')

    def test_multiple_deposits_same_user(self, savings):
        """Successive deposits accumulate for the same user."""
        savings.deposit('alice', Decimal('100'))
        savings.deposit('alice', Decimal('50'))
        assert savings.get_balance('alice') == Decimal('150')
        assert savings.get_total_deposits() == Decimal('150')

    def test_multiple_users(self, savings):
        """Independent users tracked separately."""
        savings.deposit('alice', Decimal('100'))
        savings.deposit('bob', Decimal('200'))
        assert savings.get_balance('alice') == Decimal('100')
        assert savings.get_balance('bob') == Decimal('200')
        assert savings.get_total_deposits() == Decimal('300')

    def test_deposit_zero_rejected(self, savings):
        """Zero deposit raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            savings.deposit('alice', Decimal('0'))

    def test_deposit_negative_rejected(self, savings):
        """Negative deposit raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            savings.deposit('alice', Decimal('-10'))

    def test_deposit_below_minimum(self, savings):
        """Deposit below min_deposit raises ValueError."""
        with pytest.raises(ValueError, match="below minimum"):
            savings.deposit('alice', Decimal('0.001'))

    def test_deposit_empty_user_rejected(self, savings):
        """Empty user address raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            savings.deposit('', Decimal('10'))


# ===========================================================================
# Withdrawals
# ===========================================================================

class TestWithdraw:
    """Test the withdraw() method."""

    def test_full_withdrawal(self, savings):
        """Withdrawing full balance empties the account."""
        savings.deposit('alice', Decimal('100'))
        result = savings.withdraw('alice', Decimal('100'))
        assert result['withdrawn'] == Decimal('100')
        assert result['remaining_balance'] == Decimal('0')
        assert savings.get_balance('alice') == Decimal('0')

    def test_partial_withdrawal(self, savings):
        """Partial withdrawal leaves correct remainder."""
        savings.deposit('alice', Decimal('100'))
        savings.withdraw('alice', Decimal('40'))
        assert savings.get_balance('alice') == Decimal('60')

    def test_overdraw_rejected(self, savings):
        """Withdrawing more than balance raises ValueError."""
        savings.deposit('alice', Decimal('100'))
        with pytest.raises(ValueError, match="insufficient"):
            savings.withdraw('alice', Decimal('200'))

    def test_withdraw_zero_rejected(self, savings):
        """Zero withdrawal raises ValueError."""
        savings.deposit('alice', Decimal('100'))
        with pytest.raises(ValueError, match="positive"):
            savings.withdraw('alice', Decimal('0'))

    def test_withdraw_empty_user_rejected(self, savings):
        """Empty user address raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            savings.withdraw('', Decimal('10'))

    def test_withdraw_includes_accrued_interest(self, savings_custom):
        """User can withdraw principal + accrued interest."""
        savings_custom.deposit('alice', Decimal('1000'))
        # Accrue interest for 1 year worth of blocks
        from qubitcoin.stablecoin.savings import BLOCKS_PER_YEAR
        savings_custom.accrue_interest(BLOCKS_PER_YEAR)
        balance = savings_custom.get_balance('alice')
        # 10% of 1000 = 100 interest (approximately, modulo rounding)
        assert balance > Decimal('1099')
        assert balance < Decimal('1101')
        # Withdraw everything
        savings_custom.withdraw('alice', balance)
        assert savings_custom.get_balance('alice') == Decimal('0')


# ===========================================================================
# Interest Accrual
# ===========================================================================

class TestAccrueInterest:
    """Test per-block interest distribution."""

    def test_no_deposits_no_interest(self, savings):
        """No interest when pool is empty."""
        result = savings.accrue_interest(1000)
        assert result == Decimal('0')

    def test_interest_grows_with_blocks(self, savings_custom):
        """Interest accrues proportionally to blocks elapsed."""
        savings_custom.deposit('alice', Decimal('1000'))
        # Accrue for half a year
        from qubitcoin.stablecoin.savings import BLOCKS_PER_YEAR
        half_year = BLOCKS_PER_YEAR // 2
        interest = savings_custom.accrue_interest(half_year)
        # Expected ~50 QUSD (10% of 1000 for half a year)
        assert interest > Decimal('49')
        assert interest < Decimal('51')

    def test_interest_for_full_year(self, savings_custom):
        """Full year accrual matches annual rate."""
        savings_custom.deposit('alice', Decimal('10000'))
        from qubitcoin.stablecoin.savings import BLOCKS_PER_YEAR
        interest = savings_custom.accrue_interest(BLOCKS_PER_YEAR)
        # 10% of 10000 = 1000
        assert interest > Decimal('999')
        assert interest < Decimal('1001')

    def test_proportional_distribution(self, savings_custom):
        """Interest is distributed proportionally to deposits."""
        savings_custom.deposit('alice', Decimal('3000'))
        savings_custom.deposit('bob', Decimal('1000'))
        from qubitcoin.stablecoin.savings import BLOCKS_PER_YEAR
        savings_custom.accrue_interest(BLOCKS_PER_YEAR)

        alice_bal = savings_custom.get_balance('alice')
        bob_bal = savings_custom.get_balance('bob')

        # Alice has 75%, Bob has 25% of pool
        # Alice should have ~3300 (3000 + 300), Bob ~1100 (1000 + 100)
        assert alice_bal > Decimal('3299')
        assert alice_bal < Decimal('3301')
        assert bob_bal > Decimal('1099')
        assert bob_bal < Decimal('1101')

    def test_no_interest_for_past_block(self, savings_custom):
        """Calling accrue_interest with a past block returns 0."""
        savings_custom.deposit('alice', Decimal('1000'))
        savings_custom.accrue_interest(100)
        result = savings_custom.accrue_interest(50)  # earlier block
        assert result == Decimal('0')

    def test_same_block_no_double_accrual(self, savings_custom):
        """Calling accrue_interest twice at the same block returns 0 the second time."""
        savings_custom.deposit('alice', Decimal('1000'))
        savings_custom.accrue_interest(100)
        result = savings_custom.accrue_interest(100)
        assert result == Decimal('0')

    def test_zero_rate_no_interest(self):
        """Zero rate produces no interest."""
        from qubitcoin.stablecoin.savings import QUSDSavingsRate
        sr = QUSDSavingsRate(annual_rate=0.0, max_rate=0.20)
        sr.deposit('alice', Decimal('1000'))
        result = sr.accrue_interest(1_000_000)
        assert result == Decimal('0')

    def test_incremental_accrual(self, savings_custom):
        """Multiple accrual calls sum to approximately the same as one big call."""
        from qubitcoin.stablecoin.savings import QUSDSavingsRate, BLOCKS_PER_YEAR
        # Scenario A: accrue all at once
        sr_a = QUSDSavingsRate(annual_rate=0.10, min_deposit=Decimal('1'), max_rate=0.20)
        sr_a.deposit('alice', Decimal('1000'))
        sr_a.accrue_interest(BLOCKS_PER_YEAR)
        bal_a = sr_a.get_balance('alice')

        # Scenario B: accrue in 4 chunks
        sr_b = QUSDSavingsRate(annual_rate=0.10, min_deposit=Decimal('1'), max_rate=0.20)
        sr_b.deposit('alice', Decimal('1000'))
        quarter = BLOCKS_PER_YEAR // 4
        for i in range(1, 5):
            sr_b.accrue_interest(quarter * i)
        bal_b = sr_b.get_balance('alice')

        # They should be very close (compound vs simple within rounding)
        diff = abs(bal_a - bal_b)
        assert diff < Decimal('5')  # within 5 QUSD tolerance


# ===========================================================================
# Rate Management
# ===========================================================================

class TestSetRate:
    """Test rate changes via set_rate()."""

    def test_set_rate(self, savings):
        """Rate can be changed."""
        result = savings.set_rate(0.05)
        assert result['old_rate'] == pytest.approx(0.033, abs=1e-6)
        assert result['new_rate'] == pytest.approx(0.05, abs=1e-6)
        assert savings.get_current_rate() == pytest.approx(0.05, abs=1e-6)

    def test_set_rate_negative_rejected(self, savings):
        """Negative rate raises ValueError."""
        with pytest.raises(ValueError, match="negative"):
            savings.set_rate(-0.01)

    def test_set_rate_exceeds_max_rejected(self, savings):
        """Rate above max_rate raises ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            savings.set_rate(0.50)

    def test_rate_change_history(self, savings):
        """Rate changes are recorded in history."""
        savings.set_rate(0.05)
        savings.set_rate(0.07)
        stats = savings.get_stats()
        history = stats['rate_change_history']
        assert len(history) == 2
        assert history[0]['new_rate'] == pytest.approx(0.05, abs=1e-6)
        assert history[1]['old_rate'] == pytest.approx(0.05, abs=1e-6)
        assert history[1]['new_rate'] == pytest.approx(0.07, abs=1e-6)

    def test_set_rate_to_zero(self, savings):
        """Rate can be set to zero (pauses interest)."""
        savings.set_rate(0.0)
        assert savings.get_current_rate() == 0.0


# ===========================================================================
# Balance queries
# ===========================================================================

class TestGetBalance:
    """Test balance retrieval."""

    def test_unknown_user_zero(self, savings):
        """Unknown user has zero balance."""
        assert savings.get_balance('nobody') == Decimal('0')

    def test_balance_includes_interest(self, savings_custom):
        """get_balance includes accrued interest."""
        savings_custom.deposit('alice', Decimal('1000'))
        from qubitcoin.stablecoin.savings import BLOCKS_PER_YEAR
        savings_custom.accrue_interest(BLOCKS_PER_YEAR // 10)  # ~1 month
        bal = savings_custom.get_balance('alice')
        assert bal > Decimal('1000')


# ===========================================================================
# Stats
# ===========================================================================

class TestGetStats:
    """Test overall statistics."""

    def test_depositor_count(self, savings):
        """Depositor count tracks unique depositors."""
        savings.deposit('alice', Decimal('10'))
        savings.deposit('bob', Decimal('20'))
        assert savings.get_stats()['depositor_count'] == 2

    def test_total_interest_paid(self, savings_custom):
        """Total interest paid accumulates."""
        savings_custom.deposit('alice', Decimal('1000'))
        from qubitcoin.stablecoin.savings import BLOCKS_PER_YEAR
        savings_custom.accrue_interest(BLOCKS_PER_YEAR)
        stats = savings_custom.get_stats()
        assert stats['total_interest_paid'] > Decimal('99')

    def test_stats_after_full_withdrawal(self, savings):
        """Depositor removed from count after full withdrawal."""
        savings.deposit('alice', Decimal('10'))
        savings.withdraw('alice', Decimal('10'))
        assert savings.get_stats()['depositor_count'] == 0
