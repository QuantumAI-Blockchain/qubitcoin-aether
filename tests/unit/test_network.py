"""Unit tests for network layer — admin API, JSON-RPC basics."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


class TestAdminAPI:
    """Test admin API models and auth logic."""

    def test_import(self):
        from qubitcoin.network.admin_api import router, AetherFeeUpdate
        assert router is not None
        assert AetherFeeUpdate is not None

    def test_verify_admin_no_key(self):
        """No API key configured = reject."""
        from qubitcoin.network.admin_api import _verify_admin
        with patch('qubitcoin.network.admin_api.Config') as MockConfig:
            MockConfig.ADMIN_API_KEY = ''
            assert _verify_admin('any-key') is False

    def test_verify_admin_wrong_key(self):
        """Wrong API key = reject."""
        from qubitcoin.network.admin_api import _verify_admin
        with patch('qubitcoin.network.admin_api.Config') as MockConfig:
            MockConfig.ADMIN_API_KEY = 'secret123'
            assert _verify_admin('wrong-key') is False

    def test_verify_admin_correct_key(self):
        """Correct API key = accept."""
        from qubitcoin.network.admin_api import _verify_admin
        with patch('qubitcoin.network.admin_api.Config') as MockConfig:
            MockConfig.ADMIN_API_KEY = 'secret123'
            assert _verify_admin('secret123') is True

    def test_audit_log(self):
        """Audit log records entries."""
        from qubitcoin.network.admin_api import _audit, _audit_log
        initial_len = len(_audit_log)
        _audit('test_action', {'param': 'value'})
        assert len(_audit_log) == initial_len + 1
        assert _audit_log[-1]['action'] == 'test_action'
        assert _audit_log[-1]['params'] == {'param': 'value'}

    def test_aether_fee_update_model(self):
        """AetherFeeUpdate Pydantic model validates."""
        from qubitcoin.network.admin_api import AetherFeeUpdate
        update = AetherFeeUpdate(chat_fee_qbc='0.02', pricing_mode='fixed_qbc')
        assert update.chat_fee_qbc == '0.02'
        assert update.pricing_mode == 'fixed_qbc'
        assert update.min_qbc is None

    def test_contract_fee_update_model(self):
        """ContractFeeUpdate Pydantic model validates."""
        from qubitcoin.network.admin_api import ContractFeeUpdate
        update = ContractFeeUpdate(base_fee_qbc='2.0', template_discount=0.3)
        assert update.base_fee_qbc == '2.0'
        assert update.template_discount == 0.3

    def test_treasury_update_model(self):
        """TreasuryUpdate Pydantic model validates."""
        from qubitcoin.network.admin_api import TreasuryUpdate
        update = TreasuryUpdate(aether_treasury='qbc1abc')
        assert update.aether_treasury == 'qbc1abc'
        assert update.contract_treasury is None


class TestJSONRPC:
    """Test JSON-RPC module imports."""

    def test_import(self):
        from qubitcoin.network.jsonrpc import router
        assert router is not None
