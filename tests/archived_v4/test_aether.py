"""Unit tests for Aether Tree modules (chat, fees, genesis)."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


class TestAetherFeeManager:
    """Test dynamic fee pricing."""

    def test_import(self):
        from qubitcoin.aether.fee_manager import AetherFeeManager
        assert AetherFeeManager is not None

    def test_fixed_qbc_mode(self):
        """In fixed_qbc mode, fee equals config value."""
        from qubitcoin.aether.fee_manager import AetherFeeManager
        with patch('qubitcoin.aether.fee_manager.Config') as MockConfig:
            MockConfig.AETHER_FEE_PRICING_MODE = 'fixed_qbc'
            MockConfig.AETHER_CHAT_FEE_QBC = Decimal('0.01')
            MockConfig.AETHER_QUERY_FEE_MULTIPLIER = 2.0
            MockConfig.AETHER_FEE_MIN_QBC = Decimal('0.001')
            MockConfig.AETHER_FEE_MAX_QBC = Decimal('1.0')

            fm = AetherFeeManager()
            fee = fm.get_chat_fee()
            assert fee == Decimal('0.01')

    def test_deep_query_multiplier(self):
        """Deep queries apply multiplier."""
        from qubitcoin.aether.fee_manager import AetherFeeManager
        with patch('qubitcoin.aether.fee_manager.Config') as MockConfig:
            MockConfig.AETHER_FEE_PRICING_MODE = 'fixed_qbc'
            MockConfig.AETHER_CHAT_FEE_QBC = Decimal('0.01')
            MockConfig.AETHER_QUERY_FEE_MULTIPLIER = 2.0
            MockConfig.AETHER_FEE_MIN_QBC = Decimal('0.001')
            MockConfig.AETHER_FEE_MAX_QBC = Decimal('1.0')

            fm = AetherFeeManager()
            fee = fm.get_chat_fee(is_deep_query=True)
            assert fee == Decimal('0.02')

    def test_fee_clamping_min(self):
        """Fee clamps to minimum."""
        from qubitcoin.aether.fee_manager import AetherFeeManager
        with patch('qubitcoin.aether.fee_manager.Config') as MockConfig:
            MockConfig.AETHER_FEE_PRICING_MODE = 'fixed_qbc'
            MockConfig.AETHER_CHAT_FEE_QBC = Decimal('0.0001')
            MockConfig.AETHER_QUERY_FEE_MULTIPLIER = 1.0
            MockConfig.AETHER_FEE_MIN_QBC = Decimal('0.001')
            MockConfig.AETHER_FEE_MAX_QBC = Decimal('1.0')

            fm = AetherFeeManager()
            fee = fm.get_chat_fee()
            assert fee >= Decimal('0.001')

    def test_fee_clamping_max(self):
        """Fee clamps to maximum."""
        from qubitcoin.aether.fee_manager import AetherFeeManager
        with patch('qubitcoin.aether.fee_manager.Config') as MockConfig:
            MockConfig.AETHER_FEE_PRICING_MODE = 'fixed_qbc'
            MockConfig.AETHER_CHAT_FEE_QBC = Decimal('999')
            MockConfig.AETHER_QUERY_FEE_MULTIPLIER = 1.0
            MockConfig.AETHER_FEE_MIN_QBC = Decimal('0.001')
            MockConfig.AETHER_FEE_MAX_QBC = Decimal('1.0')

            fm = AetherFeeManager()
            fee = fm.get_chat_fee()
            assert fee <= Decimal('1.0')

    def test_fee_info_free_tier(self):
        """Free tier returns zero fee."""
        from qubitcoin.aether.fee_manager import AetherFeeManager
        with patch('qubitcoin.aether.fee_manager.Config') as MockConfig:
            MockConfig.AETHER_FEE_PRICING_MODE = 'fixed_qbc'
            MockConfig.AETHER_CHAT_FEE_QBC = Decimal('0.01')
            MockConfig.AETHER_QUERY_FEE_MULTIPLIER = 1.0
            MockConfig.AETHER_FEE_MIN_QBC = Decimal('0.001')
            MockConfig.AETHER_FEE_MAX_QBC = Decimal('1.0')
            MockConfig.AETHER_FREE_TIER_MESSAGES = 5
            MockConfig.AETHER_CHAT_FEE_USD_TARGET = 0.005
            MockConfig.AETHER_FEE_TREASURY_ADDRESS = ''
            MockConfig.AETHER_FEE_UPDATE_INTERVAL = 100

            fm = AetherFeeManager()
            info = fm.get_fee_info(session_messages_sent=2)
            assert info['is_free'] is True
            assert info['fee_qbc'] == '0'
            assert info['free_remaining'] == 3

    def test_fee_info_paid_tier(self):
        """After free tier, fee is non-zero."""
        from qubitcoin.aether.fee_manager import AetherFeeManager
        with patch('qubitcoin.aether.fee_manager.Config') as MockConfig:
            MockConfig.AETHER_FEE_PRICING_MODE = 'fixed_qbc'
            MockConfig.AETHER_CHAT_FEE_QBC = Decimal('0.01')
            MockConfig.AETHER_QUERY_FEE_MULTIPLIER = 1.0
            MockConfig.AETHER_FEE_MIN_QBC = Decimal('0.001')
            MockConfig.AETHER_FEE_MAX_QBC = Decimal('1.0')
            MockConfig.AETHER_FREE_TIER_MESSAGES = 5
            MockConfig.AETHER_CHAT_FEE_USD_TARGET = 0.005
            MockConfig.AETHER_FEE_TREASURY_ADDRESS = ''
            MockConfig.AETHER_FEE_UPDATE_INTERVAL = 100

            fm = AetherFeeManager()
            info = fm.get_fee_info(session_messages_sent=10)
            assert info['is_free'] is False
            assert Decimal(info['fee_qbc']) > 0


class TestContractFeeCalculator:
    """Test contract deployment fee calculation."""

    def test_import(self):
        from qubitcoin.contracts.fee_calculator import ContractFeeCalculator
        assert ContractFeeCalculator is not None

    def test_fixed_qbc_deploy_fee(self):
        from qubitcoin.contracts.fee_calculator import ContractFeeCalculator
        with patch('qubitcoin.contracts.fee_calculator.Config') as MockConfig:
            MockConfig.CONTRACT_FEE_PRICING_MODE = 'fixed_qbc'
            MockConfig.CONTRACT_DEPLOY_BASE_FEE_QBC = Decimal('1.0')
            MockConfig.CONTRACT_DEPLOY_PER_KB_FEE_QBC = Decimal('0.1')
            MockConfig.CONTRACT_TEMPLATE_DISCOUNT = 0.5
            MockConfig.CONTRACT_DEPLOY_FEE_USD_TARGET = 5.0
            MockConfig.CONTRACT_EXECUTE_BASE_FEE_QBC = Decimal('0.01')

            calc = ContractFeeCalculator()
            # 2KB bytecode
            fee = calc.calculate_deploy_fee(bytecode_size_bytes=2048)
            assert fee == Decimal('1.0') + Decimal('0.1') * 2  # 1.0 + 0.2 = 1.2

    def test_template_discount(self):
        from qubitcoin.contracts.fee_calculator import ContractFeeCalculator
        with patch('qubitcoin.contracts.fee_calculator.Config') as MockConfig:
            MockConfig.CONTRACT_FEE_PRICING_MODE = 'fixed_qbc'
            MockConfig.CONTRACT_DEPLOY_BASE_FEE_QBC = Decimal('1.0')
            MockConfig.CONTRACT_DEPLOY_PER_KB_FEE_QBC = Decimal('0.1')
            MockConfig.CONTRACT_TEMPLATE_DISCOUNT = 0.5
            MockConfig.CONTRACT_DEPLOY_FEE_USD_TARGET = 5.0
            MockConfig.CONTRACT_EXECUTE_BASE_FEE_QBC = Decimal('0.01')

            calc = ContractFeeCalculator()
            full = calc.calculate_deploy_fee(bytecode_size_bytes=1024)
            disc = calc.calculate_deploy_fee(bytecode_size_bytes=1024, is_template=True)
            assert disc < full
            assert disc == full * Decimal('0.5')


class TestQUSDOracle:
    """Test QUSD oracle client."""

    def test_import(self):
        from qubitcoin.utils.qusd_oracle import QUSDOracle
        assert QUSDOracle is not None

    def test_external_price_override(self):
        from qubitcoin.utils.qusd_oracle import QUSDOracle
        oracle = QUSDOracle()
        oracle.set_external_price(Decimal('0.50'))
        price = oracle.get_qbc_usd_price()
        assert price == Decimal('0.50')

    def test_no_price_returns_none(self):
        from qubitcoin.utils.qusd_oracle import QUSDOracle
        oracle = QUSDOracle()
        oracle._cache_ts = 0  # force stale
        oracle._stale_threshold = 0
        price = oracle.get_qbc_usd_price()
        assert price is None

    def test_status_output(self):
        from qubitcoin.utils.qusd_oracle import QUSDOracle
        oracle = QUSDOracle()
        status = oracle.get_status()
        assert 'price' in status
        assert 'stale' in status
        assert 'cache_ttl' in status
