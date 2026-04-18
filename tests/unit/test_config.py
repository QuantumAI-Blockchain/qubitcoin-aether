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
    assert Config.MAX_FUTURE_BLOCK_TIME == 10  # Hardened from 7200s → 120s → 10s


def test_config_chain_ids():
    """Chain ID defaults to mainnet."""
    from qubitcoin.config import Config
    assert Config.CHAIN_ID == 3303


def test_config_aether_fee_params():
    """Aether Tree fee parameters are loaded."""
    from qubitcoin.config import Config
    assert Config.AETHER_CHAT_FEE_QBC == Decimal('0.01')
    assert Config.AETHER_CHAT_FEE_USD_TARGET == 0.005
    assert Config.AETHER_FEE_PRICING_MODE in ('qusd_peg', 'fixed_qbc', 'direct_usd')
    assert Config.AETHER_FEE_MIN_QBC < Config.AETHER_FEE_MAX_QBC
    assert Config.AETHER_FREE_TIER_MESSAGES > 0  # Default 100, env may override


def test_config_contract_fee_params():
    """Contract fee parameters are loaded."""
    from qubitcoin.config import Config
    assert Config.CONTRACT_DEPLOY_BASE_FEE_QBC == Decimal('1.0')
    assert Config.CONTRACT_DEPLOY_PER_KB_FEE_QBC == Decimal('0.1')
    assert 0 <= Config.CONTRACT_TEMPLATE_DISCOUNT <= 1


def test_config_genesis_premine():
    """Genesis premine constant is valid."""
    from qubitcoin.config import Config
    assert Config.GENESIS_PREMINE == Decimal('33000000')
    assert Config.GENESIS_PREMINE >= 0
    assert Config.GENESIS_PREMINE < Config.MAX_SUPPLY


def test_config_tail_emission_reward():
    """Tail emission reward constant is valid."""
    from qubitcoin.config import Config
    assert Config.TAIL_EMISSION_REWARD == Decimal('0.1')
    assert Config.TAIL_EMISSION_REWARD > 0
    assert Config.TAIL_EMISSION_REWARD < Config.INITIAL_REWARD


def test_config_display():
    """Display method returns formatted string."""
    from qubitcoin.config import Config
    output = Config.display()
    assert 'QUBITCOIN NODE' in output
    assert '3,300,000,000' in output
    assert '3.3 seconds' in output
    assert 'Genesis Premine' in output
    assert 'Tail Emission' in output


def test_config_display_no_fabricated_projections():
    """Display method shows accurate emission projections, not fabricated ones."""
    from qubitcoin.config import Config
    output = Config.display()
    # Old fabricated values should NOT appear
    assert 'Year 33:              ~3.27B' not in output
    # Should contain "phi-halving + tail emission" label
    assert 'phi-halving + tail emission' in output


def test_config_compute_supply_at_height_zero():
    """Supply at height 0 equals INITIAL_REWARD + GENESIS_PREMINE."""
    from qubitcoin.config import Config
    supply = Config._compute_supply_at_height(0)
    assert supply == Config.INITIAL_REWARD + Config.GENESIS_PREMINE


def test_config_compute_supply_at_height_negative():
    """Supply at negative height is zero."""
    from qubitcoin.config import Config
    supply = Config._compute_supply_at_height(-1)
    assert supply == Decimal('0')


def test_config_compute_supply_never_exceeds_max():
    """Supply at any height never exceeds MAX_SUPPLY."""
    from qubitcoin.config import Config
    # Very large height (well into tail emission territory)
    supply = Config._compute_supply_at_height(999_999_999_999)
    assert supply <= Config.MAX_SUPPLY


def test_config_emission_projection_realistic():
    """Emission projection at year 33 should be well under 100% with phi-halving alone.

    The phi-halving series converges to ~651M QBC. With tail emission of 0.1 QBC/block,
    year 33 supply should be meaningfully higher than the phi-halving convergence but
    well under MAX_SUPPLY.
    """
    from qubitcoin.config import Config
    proj = Config._compute_emission_projection()
    yr33_supply, yr33_pct = proj[33]
    # Must be more than the phi-halving convergence (~651M)
    assert yr33_supply > 651_000_000
    # Must be less than MAX_SUPPLY
    assert yr33_pct < 100.0
