"""Unit tests for contract engine — deployment, execution, validation, fees."""
import pytest
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch


class TestContractEngineInit:
    """Test contract engine initialization."""

    def _make_engine(self, **overrides):
        from qubitcoin.contracts.engine import ContractEngine
        db = MagicMock()
        qe = MagicMock()
        kwargs = dict(db_manager=db, quantum_engine=qe)
        kwargs.update(overrides)
        return ContractEngine(**kwargs)

    def test_init_registers_validators(self):
        """Engine registers all contract type validators."""
        eng = self._make_engine()
        assert 'token' in eng.validators
        assert 'nft' in eng.validators
        assert 'escrow' in eng.validators
        assert 'governance' in eng.validators
        assert 'quantum_gate' in eng.validators

    def test_init_registers_executors(self):
        """Engine registers all contract type executors."""
        eng = self._make_engine()
        assert 'token' in eng.executors
        assert 'nft' in eng.executors
        assert 'escrow' in eng.executors
        assert 'governance' in eng.executors

    def test_optional_fee_collector(self):
        """Engine works without fee_collector."""
        eng = self._make_engine()
        assert eng.fee_collector is None

    def test_optional_fee_calculator(self):
        """Engine works without fee_calculator."""
        eng = self._make_engine()
        assert eng.fee_calculator is None


class TestContractDeployment:
    """Test contract deployment flow."""

    def _make_engine(self):
        from qubitcoin.contracts.engine import ContractEngine
        db = MagicMock()
        db.get_balance.return_value = Decimal('1000')
        db.get_current_height.return_value = 10

        # Mock session context manager
        session = MagicMock()
        result = MagicMock()
        result.scalar.return_value = 'contract-123'
        session.execute.return_value = result
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        qe = MagicMock()
        return ContractEngine(db_manager=db, quantum_engine=qe)

    @patch('qubitcoin.contracts.engine.Config')
    @patch('qubitcoin.contracts.engine.Dilithium2')
    def test_deploy_unsupported_type(self, mock_dil, mock_config):
        """Deploying unsupported contract type fails."""
        mock_config.SUPPORTED_CONTRACT_TYPES = ['token', 'nft']
        eng = self._make_engine()
        ok, msg, cid = eng.deploy_contract(
            deployer_address='qbc1test',
            contract_type='unknown_type',
            contract_code={},
            signature='aa' * 64,
            public_key='bb' * 32,
        )
        assert ok is False
        assert 'Unsupported' in msg
        assert cid is None

    @patch('qubitcoin.contracts.engine.Config')
    @patch('qubitcoin.contracts.engine.Dilithium2')
    def test_deploy_invalid_signature(self, mock_dil, mock_config):
        """Deploying with invalid signature fails."""
        mock_config.SUPPORTED_CONTRACT_TYPES = ['token']
        mock_dil.verify.return_value = False
        eng = self._make_engine()
        ok, msg, cid = eng.deploy_contract(
            deployer_address='qbc1test',
            contract_type='token',
            contract_code={'name': 'TestToken'},
            signature='aa' * 64,
            public_key='bb' * 32,
        )
        assert ok is False
        assert 'signature' in msg.lower()

    @patch('qubitcoin.contracts.engine.Config')
    @patch('qubitcoin.contracts.engine.Dilithium2')
    def test_deploy_insufficient_balance(self, mock_dil, mock_config):
        """Deploying with insufficient balance fails."""
        mock_config.SUPPORTED_CONTRACT_TYPES = ['token']
        mock_config.GAS_CONTRACT_DEPLOY_BASE = Decimal('10000')
        mock_config.GAS_CONTRACT_DEPLOY_PER_KB = Decimal('1')
        mock_config.MAX_CONTRACT_SIZE = 1_000_000
        mock_dil.verify.return_value = True
        eng = self._make_engine()
        eng.db.get_balance.return_value = Decimal('0.001')  # too low
        ok, msg, cid = eng.deploy_contract(
            deployer_address='qbc1test',
            contract_type='token',
            contract_code={
                'name': 'TestToken',
                'symbol': 'TST',
                'total_supply': '1000',
                'decimals': 18,
            },
            signature='aa' * 64,
            public_key='bb' * 32,
        )
        assert ok is False
        assert 'Insufficient' in msg

    @patch('qubitcoin.contracts.engine.Config')
    @patch('qubitcoin.contracts.engine.Dilithium2')
    def test_deploy_oversized_contract(self, mock_dil, mock_config):
        """Deploying oversized contract fails."""
        mock_config.SUPPORTED_CONTRACT_TYPES = ['token']
        mock_config.GAS_CONTRACT_DEPLOY_BASE = Decimal('1')
        mock_config.GAS_CONTRACT_DEPLOY_PER_KB = Decimal('0')
        mock_config.MAX_CONTRACT_SIZE = 10  # very small
        mock_dil.verify.return_value = True
        eng = self._make_engine()
        eng.db.get_balance.return_value = Decimal('1000')
        ok, msg, cid = eng.deploy_contract(
            deployer_address='qbc1test',
            contract_type='token',
            contract_code={
                'name': 'A' * 100,
                'symbol': 'TST',
                'total_supply': '1000',
                'decimals': 18,
            },
            signature='aa' * 64,
            public_key='bb' * 32,
        )
        assert ok is False
        assert 'large' in msg.lower() or 'size' in msg.lower() or 'exceed' in msg.lower()


class TestTokenValidation:
    """Test token contract validation."""

    def _make_engine(self):
        from qubitcoin.contracts.engine import ContractEngine
        return ContractEngine(
            db_manager=MagicMock(),
            quantum_engine=MagicMock(),
        )

    def test_validate_token_requires_name(self):
        """Token contract must have a name field."""
        eng = self._make_engine()
        validator = eng.validators['token']
        valid, error = validator({'symbol': 'TST', 'total_supply': '1000', 'decimals': 18})
        # Should fail because 'name' is missing
        assert valid is False or 'name' in str(error).lower() or error is not None

    def test_validate_token_valid(self):
        """Valid token contract passes validation."""
        eng = self._make_engine()
        validator = eng.validators['token']
        valid, error = validator({
            'name': 'TestToken',
            'symbol': 'TST',
            'total_supply': '1000',
            'decimals': 18,
        })
        # A complete token should pass
        assert valid is True


class TestContractExecution:
    """Test contract method execution."""

    def _make_engine(self):
        from qubitcoin.contracts.engine import ContractEngine
        db = MagicMock()
        session = MagicMock()
        db.get_session.return_value.__enter__ = MagicMock(return_value=session)
        db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        return ContractEngine(db_manager=db, quantum_engine=MagicMock())

    @patch('qubitcoin.contracts.engine.Config')
    @patch('qubitcoin.contracts.engine.Dilithium2')
    def test_execute_nonexistent_contract(self, mock_dil, mock_config):
        """Executing non-existent contract fails gracefully."""
        eng = self._make_engine()
        # Session returns no contract
        sess = eng.db.get_session.return_value.__enter__.return_value
        sess.execute.return_value.fetchone.return_value = None

        ok, msg, result = eng.execute_contract(
            contract_id='nonexistent',
            executor_address='qbc1test',
            method='transfer',
            params={},
            signature='aa' * 64,
            public_key='bb' * 32,
        )
        assert ok is False
