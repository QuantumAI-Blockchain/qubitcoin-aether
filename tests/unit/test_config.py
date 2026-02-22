"""Unit tests for configuration module."""
import pytest
from decimal import Decimal


def test_config_imports():
    """Config class imports without error."""
    from qubitcoin.config import Config
    assert Config is not None


def test_config_economics_constants():
    """Core economic constants are correct."""
    from qubitcoin.config import Config
    assert Config.MAX_SUPPLY == Decimal('3300000000')
    assert Config.TARGET_BLOCK_TIME == 3.3
    assert Config.EMISSION_PERIOD == 33
    assert Config.INITIAL_REWARD == Decimal('15.27')
    assert Config.HALVING_INTERVAL == 15_474_020


def test_config_phi():
    """Golden ratio constant is correct."""
    from qubitcoin.config import Config
    assert abs(Config.PHI - 1.618033988749895) < 1e-12
    assert abs(Config.PHI_INVERSE - 0.618033988749895) < 1e-12
    assert abs(Config.PHI * Config.PHI_INVERSE - 1.0) < 1e-12


def test_config_consensus_params():
    """Consensus parameters match CLAUDE.md spec."""
    from qubitcoin.config import Config
    assert Config.DIFFICULTY_WINDOW == 144
    assert Config.DIFFICULTY_ADJUSTMENT_INTERVAL == 1
    assert Config.MAX_DIFFICULTY_CHANGE == 0.10
    assert Config.COINBASE_MATURITY == 100
    assert Config.MAX_FUTURE_BLOCK_TIME == 7200


def test_config_chain_ids():
    """Chain ID defaults to mainnet."""
    from qubitcoin.config import Config
    assert Config.CHAIN_ID == 3301


def test_config_aether_fee_params():
    """Aether Tree fee parameters are loaded."""
    from qubitcoin.config import Config
    assert Config.AETHER_CHAT_FEE_QBC == Decimal('0.01')
    assert Config.AETHER_CHAT_FEE_USD_TARGET == 0.005
    assert Config.AETHER_FEE_PRICING_MODE in ('qusd_peg', 'fixed_qbc', 'direct_usd')
    assert Config.AETHER_FEE_MIN_QBC < Config.AETHER_FEE_MAX_QBC
    assert Config.AETHER_FREE_TIER_MESSAGES == 100


def test_config_contract_fee_params():
    """Contract fee parameters are loaded."""
    from qubitcoin.config import Config
    assert Config.CONTRACT_DEPLOY_BASE_FEE_QBC == Decimal('1.0')
    assert Config.CONTRACT_DEPLOY_PER_KB_FEE_QBC == Decimal('0.1')
    assert 0 <= Config.CONTRACT_TEMPLATE_DISCOUNT <= 1


def test_config_display():
    """Display method returns formatted string."""
    from qubitcoin.config import Config
    output = Config.display()
    assert 'QUBITCOIN NODE' in output
    assert '3,300,000,000' in output
    assert '3.3 seconds' in output
