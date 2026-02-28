"""
Smart Contract Templates — Pre-defined contract configurations.

Each template provides a validated configuration dict that can be deployed
via ContractEngine.deploy_contract().  Templates receive a deployment fee
discount (CONTRACT_TEMPLATE_DISCOUNT in config.py).
"""

# ---------------------------------------------------------------------------
# QUSD Stablecoin
# ---------------------------------------------------------------------------

QUSD_CONTRACT = {
    'symbol': 'QUSD',
    'name': 'Qubitcoin USD Stablecoin',
    'decimals': 8,
    'stablecoin_type': 'multi-collateral',
    'peg': 'USD',
    'collateral_types': ['USDT', 'USDC', 'DAI', 'QBC', 'ETH'],
    'functions': [
        'mint',
        'burn',
        'transfer',
        'balanceOf',
        'updateOracle',
        'getHealth',
        'checkLiquidations',
    ],
    'parameters': {
        'peg_tolerance': 0.005,
        'min_mint': 10.0,
        'oracle_sources': ['Chainlink', 'Band', 'Native'],
    },
}

# ---------------------------------------------------------------------------
# QBC-20 Fungible Token
# ---------------------------------------------------------------------------

TOKEN_CONTRACT = {
    'symbol': '',          # Set by deployer
    'name': '',            # Set by deployer
    'decimals': 8,
    'total_supply': 0,     # Set by deployer
    'functions': [
        'transfer',
        'balanceOf',
        'approve',
        'transferFrom',
        'allowance',
        'totalSupply',
        'name',
        'symbol',
        'decimals',
    ],
    'parameters': {
        'mintable': False,
        'burnable': False,
        'pausable': False,
        'max_supply': 0,   # 0 = no cap beyond total_supply
    },
}

# ---------------------------------------------------------------------------
# QBC-721 Non-Fungible Token
# ---------------------------------------------------------------------------

NFT_CONTRACT = {
    'symbol': '',
    'name': '',
    'decimals': 0,
    'base_uri': '',        # Metadata URI prefix (IPFS or HTTPS)
    'max_supply': 10000,   # Maximum mintable NFTs (0 = unlimited)
    'functions': [
        'mint',
        'burn',
        'transfer',
        'transferFrom',
        'approve',
        'setApprovalForAll',
        'balanceOf',
        'ownerOf',
        'tokenURI',
        'totalSupply',
    ],
    'parameters': {
        'auto_increment_ids': True,
        'royalty_bps': 0,        # Creator royalty in basis points
        'royalty_receiver': '',   # Royalty recipient address
        'enumerable': True,
    },
}

# ---------------------------------------------------------------------------
# Escrow (Multi-Signature)
# ---------------------------------------------------------------------------

ESCROW_CONTRACT = {
    'name': '',
    'symbol': 'ESCROW',
    'decimals': 8,
    'functions': [
        'deposit',
        'release',
        'refund',
        'dispute',
        'resolveDispute',
        'getBalance',
        'getStatus',
    ],
    'parameters': {
        'arbiter': '',                # Dispute resolution address
        'buyer': '',                  # Buyer address
        'seller': '',                 # Seller address
        'timeout_blocks': 86400,      # Auto-release after N blocks (~3.3 days)
        'require_arbiter_for_release': False,
        'fee_bps': 50,               # 0.5% escrow fee
    },
}

# ---------------------------------------------------------------------------
# Governance (DAO)
# ---------------------------------------------------------------------------

GOVERNANCE_CONTRACT = {
    'name': '',
    'symbol': 'GOV',
    'decimals': 8,
    'functions': [
        'propose',
        'vote',
        'execute',
        'cancel',
        'getProposal',
        'getVotingPower',
        'delegate',
        'undelegate',
    ],
    'parameters': {
        'voting_token': '',           # QBC-20 token address for voting power
        'voting_period_blocks': 43636,  # ~1.67 days at 3.3s blocks
        'quorum_bps': 400,            # 4% of total supply must vote
        'proposal_threshold': 1000,   # Min tokens to create proposal
        'execution_delay_blocks': 8727,  # ~8 hour timelock
        'vote_types': ['for', 'against', 'abstain'],
    },
}

# ---------------------------------------------------------------------------
# Token Sale (Launchpad)
# ---------------------------------------------------------------------------

LAUNCHPAD_CONTRACT = {
    'name': '',
    'symbol': 'LAUNCH',
    'decimals': 8,
    'functions': [
        'contribute',
        'claimTokens',
        'refund',
        'finalize',
        'getProgress',
        'getContribution',
    ],
    'parameters': {
        'raise_target': 0,           # Soft cap in QBC
        'hard_cap': 0,               # Hard cap (0 = no hard cap)
        'token_price': 0,            # Price per token in QBC
        'duration_hours': 72,
        'min_contribution': 1,       # Min QBC per contribution
        'max_contribution': 0,       # 0 = no per-user cap
        'vesting_blocks': 0,         # 0 = immediate claim
        'whitelist_enabled': False,
    },
}

# ---------------------------------------------------------------------------
# Template Registry — for lookup by contract type
# ---------------------------------------------------------------------------

TEMPLATES = {
    'stablecoin': QUSD_CONTRACT,
    'token': TOKEN_CONTRACT,
    'nft': NFT_CONTRACT,
    'escrow': ESCROW_CONTRACT,
    'governance': GOVERNANCE_CONTRACT,
    'launchpad': LAUNCHPAD_CONTRACT,
}


def get_template(contract_type: str) -> dict:
    """Return a copy of the template for the given contract type.

    Returns None if no template exists for the type.
    """
    template = TEMPLATES.get(contract_type)
    if template is None:
        return None
    # Return a deep-ish copy so callers can mutate without affecting the template
    import copy
    return copy.deepcopy(template)
