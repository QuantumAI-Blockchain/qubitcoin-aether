"""
Tests for QUSD flash loan support (Item S13).

Verifies:
  - FlashLoan dataclass creation
  - initiate_flash_loan validation and mechanics
  - complete_flash_loan repayment logic
  - Fee calculation (9 bps default)
  - get_flash_loan_stats reporting
  - Edge cases (disabled, max amount, duplicate loans)
"""

import time
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Create a mock DatabaseManager that returns empty results for stablecoin init."""
    db = MagicMock()
    session = MagicMock()

    # Build a mock result object that supports both iteration (for _load_params)
    # and .fetchone() (for _ensure_qusd_token).
    result_mock = MagicMock()
    result_mock.__iter__ = MagicMock(return_value=iter([]))
    result_mock.fetchone.return_value = ('qusd-token-id', True)
    session.execute.return_value = result_mock

    db.get_session.return_value.__enter__ = MagicMock(return_value=session)
    db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    return db


@pytest.fixture
def mock_quantum():
    """Create a mock QuantumEngine."""
    return MagicMock()


@pytest.fixture
def engine(mock_db, mock_quantum):
    """Create a StablecoinEngine with mocked dependencies."""
    # Patch Config to avoid validation errors
    with patch('qubitcoin.stablecoin.engine.Config') as MockConfig:
        MockConfig.QUSD_TOKEN_ADDRESS = ''
        MockConfig.QUSD_RESERVE_ADDRESS = ''
        MockConfig.QUSD_FLASH_LOAN_FEE_BPS = 9
        MockConfig.QUSD_FLASH_LOAN_MAX_AMOUNT = Decimal('1000000')
        MockConfig.QUSD_FLASH_LOAN_ENABLED = True
        MockConfig.QUSD_INSURANCE_FUND_PERCENTAGE = 0.05
        MockConfig.QUSD_INSURANCE_FUND_ADDRESS = ''
        MockConfig.QUSD_INSURANCE_PAYOUT_THRESHOLD = 0.90
        MockConfig.QUSD_REDEMPTION_BASE_FEE_BPS = 10
        MockConfig.QUSD_REDEMPTION_FEE_MULTIPLIER = 5.0

        from qubitcoin.stablecoin.engine import StablecoinEngine
        eng = StablecoinEngine(mock_db, mock_quantum)
    return eng


# ============================================================================
# Tests: FlashLoan dataclass
# ============================================================================

class TestFlashLoanDataclass:
    """Tests for the FlashLoan dataclass."""

    def test_flash_loan_creation(self):
        """FlashLoan should be constructable with required fields."""
        from qubitcoin.stablecoin.engine import FlashLoan
        loan = FlashLoan(
            id='test-id',
            borrower='0xabc',
            amount=Decimal('1000'),
            fee=Decimal('0.9'),
            timestamp=time.time(),
        )
        assert loan.id == 'test-id'
        assert loan.borrower == '0xabc'
        assert loan.amount == Decimal('1000')
        assert loan.fee == Decimal('0.9')
        assert loan.repaid is False
        assert loan.repay_amount == Decimal('0')
        assert loan.repay_timestamp is None

    def test_flash_loan_default_values(self):
        """FlashLoan defaults should be correct."""
        from qubitcoin.stablecoin.engine import FlashLoan
        loan = FlashLoan(
            id='x', borrower='y', amount=Decimal('100'),
            fee=Decimal('1'), timestamp=0.0,
        )
        assert not loan.repaid
        assert loan.repay_amount == Decimal('0')


# ============================================================================
# Tests: initiate_flash_loan
# ============================================================================

class TestInitiateFlashLoan:
    """Tests for initiating flash loans."""

    def test_initiate_basic(self, engine):
        """Should create a flash loan with correct fee calculation."""
        loan = engine.initiate_flash_loan('borrower1', Decimal('10000'))
        # Fee = 10000 * 9 / 10000 = 9.0
        assert loan.amount == Decimal('10000')
        assert loan.fee == Decimal('9')  # 9 bps = 0.09%
        assert loan.borrower == 'borrower1'
        assert not loan.repaid
        assert loan.id is not None

    def test_initiate_fee_calculation_precision(self, engine):
        """Fee should be exactly amount * bps / 10000."""
        loan = engine.initiate_flash_loan('addr1', Decimal('100'))
        expected_fee = (Decimal('100') * Decimal('9')) / Decimal('10000')
        assert loan.fee == expected_fee

    def test_initiate_rejects_zero_amount(self, engine):
        """Should raise ValueError for zero amount."""
        with pytest.raises(ValueError, match="positive"):
            engine.initiate_flash_loan('addr1', Decimal('0'))

    def test_initiate_rejects_negative_amount(self, engine):
        """Should raise ValueError for negative amount."""
        with pytest.raises(ValueError, match="positive"):
            engine.initiate_flash_loan('addr1', Decimal('-100'))

    def test_initiate_rejects_over_max(self, engine):
        """Should raise ValueError when amount exceeds max."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            engine.initiate_flash_loan('addr1', Decimal('2000000'))

    def test_initiate_disabled(self, engine):
        """Should raise ValueError when flash loans are disabled."""
        engine._flash_loan_enabled = False
        with pytest.raises(ValueError, match="disabled"):
            engine.initiate_flash_loan('addr1', Decimal('100'))

    def test_initiate_duplicate_borrower_rejected(self, engine):
        """Should reject a second loan from same borrower while first is active."""
        engine.initiate_flash_loan('addr1', Decimal('100'))
        with pytest.raises(ValueError, match="active flash loan"):
            engine.initiate_flash_loan('addr1', Decimal('200'))


# ============================================================================
# Tests: complete_flash_loan
# ============================================================================

class TestCompleteFlashLoan:
    """Tests for completing flash loans."""

    def test_complete_with_exact_repayment(self, engine):
        """Should succeed when repaying exactly amount + fee."""
        loan = engine.initiate_flash_loan('addr1', Decimal('1000'))
        required = loan.amount + loan.fee
        result = engine.complete_flash_loan(loan.id, required)
        assert result is True

    def test_complete_with_overpayment(self, engine):
        """Should succeed when repaying more than required."""
        loan = engine.initiate_flash_loan('addr1', Decimal('1000'))
        result = engine.complete_flash_loan(loan.id, Decimal('2000'))
        assert result is True

    def test_complete_insufficient_repayment(self, engine):
        """Should return False when repayment is insufficient."""
        loan = engine.initiate_flash_loan('addr1', Decimal('1000'))
        # Pay back only the principal, missing the fee
        result = engine.complete_flash_loan(loan.id, loan.amount)
        assert result is False
        # Loan should still be active
        assert engine.get_active_flash_loan(loan.id) is not None

    def test_complete_unknown_loan_raises(self, engine):
        """Should raise ValueError for unknown loan ID."""
        with pytest.raises(ValueError, match="not found"):
            engine.complete_flash_loan('nonexistent-id', Decimal('100'))

    def test_complete_already_repaid_raises(self, engine):
        """Should raise ValueError if loan already repaid."""
        loan = engine.initiate_flash_loan('addr1', Decimal('100'))
        required = loan.amount + loan.fee
        engine.complete_flash_loan(loan.id, required)
        with pytest.raises(ValueError, match="already repaid"):
            engine.complete_flash_loan(loan.id, required)

    def test_complete_removes_from_active(self, engine):
        """Completed loan should be removed from active loans."""
        loan = engine.initiate_flash_loan('addr1', Decimal('100'))
        required = loan.amount + loan.fee
        engine.complete_flash_loan(loan.id, required)
        assert engine.get_active_flash_loan(loan.id) is None


# ============================================================================
# Tests: get_flash_loan_stats
# ============================================================================

class TestFlashLoanStats:
    """Tests for flash loan statistics."""

    def test_stats_empty(self, engine):
        """Stats should be correct with no loans."""
        stats = engine.get_flash_loan_stats()
        assert stats['enabled'] is True
        assert stats['fee_bps'] == 9
        assert stats['total_loans'] == 0
        assert stats['active_loans'] == 0
        assert stats['completed_loans'] == 0
        assert stats['total_borrowed'] == '0'
        assert stats['total_fees_collected'] == '0'

    def test_stats_after_initiate(self, engine):
        """Stats should reflect an active loan."""
        engine.initiate_flash_loan('addr1', Decimal('500'))
        stats = engine.get_flash_loan_stats()
        assert stats['total_loans'] == 1
        assert stats['active_loans'] == 1
        assert stats['completed_loans'] == 0
        assert stats['total_borrowed'] == '500'

    def test_stats_after_complete(self, engine):
        """Stats should reflect a completed loan and collected fees."""
        loan = engine.initiate_flash_loan('addr1', Decimal('10000'))
        required = loan.amount + loan.fee
        engine.complete_flash_loan(loan.id, required)
        stats = engine.get_flash_loan_stats()
        assert stats['total_loans'] == 1
        assert stats['active_loans'] == 0
        assert stats['completed_loans'] == 1
        assert Decimal(stats['total_fees_collected']) == loan.fee

    def test_stats_max_amount_shown(self, engine):
        """Stats should include the max loan amount."""
        stats = engine.get_flash_loan_stats()
        assert stats['max_amount'] == '1000000'
