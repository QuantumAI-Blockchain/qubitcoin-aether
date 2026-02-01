"""
Smart Contract Templates
Pre-defined contract configurations
"""

# QUSD Stablecoin Contract
QUSD_CONTRACT = {
    'symbol': 'QUSD',
    'name': 'Qubitcoin USD Stablecoin',
    'decimals': 8,
    'stablecoin_type': 'multi-collateral',
    'peg': 'USD',
    'collateral_types': ['USDT', 'USDC', 'DAI', 'QBC', 'ETH'],
    'functions': [
        'mint',           # Mint QUSD against collateral
        'burn',           # Burn QUSD to unlock collateral
        'transfer',       # Transfer QUSD
        'balanceOf',      # Check balance
        'updateOracle',   # Update price feed
        'getHealth',      # Get system health
        'checkLiquidations'  # Check for liquidatable vaults
    ],
    'parameters': {
        'peg_tolerance': 0.005,
        'min_mint': 10.0,
        'oracle_sources': ['Chainlink', 'Band', 'Native']
    }
}

