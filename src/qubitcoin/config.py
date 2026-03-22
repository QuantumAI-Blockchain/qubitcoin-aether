"""
Configuration management for Qubitcoin node
Supersymmetric Economics Model
"""

import os
from decimal import Decimal
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load secure_key.env FIRST (private key material), then .env (node config).
# secure_key.env values take precedence for key fields; .env provides all other config.
_project_root = Path(__file__).resolve().parent.parent.parent
_secure_key_path = _project_root / 'secure_key.env'
if _secure_key_path.exists():
    load_dotenv(_secure_key_path, override=True)
load_dotenv(override=False)  # .env values do NOT override secure_key.env


class Config:
    """Global configuration for Qubitcoin node"""

    # ============================================================================
    # VERSION
    # ============================================================================
    NODE_VERSION: str = os.getenv('NODE_VERSION', '2.0.0')

    # ============================================================================
    # NODE IDENTITY
    # ============================================================================
    ADDRESS: str = os.getenv('ADDRESS', '')
    PRIVATE_KEY_HEX: str = os.getenv('PRIVATE_KEY_HEX', '')
    PUBLIC_KEY_HEX: str = os.getenv('PUBLIC_KEY_HEX', '')
    PRIVATE_KEY_ED25519: Optional[str] = os.getenv('PRIVATE_KEY_ED25519')

    # ============================================================================
    # QUANTUM SETTINGS
    # ============================================================================
    USE_LOCAL_ESTIMATOR: bool = os.getenv('USE_LOCAL_ESTIMATOR', 'true').lower() == 'true'
    USE_SIMULATOR: bool = os.getenv('USE_SIMULATOR', 'false').lower() == 'true'
    USE_GPU_AER: bool = os.getenv('USE_GPU_AER', 'false').lower() == 'true'
    IBM_TOKEN: Optional[str] = os.getenv('IBM_TOKEN')
    IBM_INSTANCE: Optional[str] = os.getenv('IBM_INSTANCE')

    VQE_REPS: int = int(os.getenv('VQE_REPS', 2))
    VQE_MAXITER: int = int(os.getenv('VQE_MAXITER', 200))
    VQE_TOLERANCE: float = 1e-6
    ENERGY_VALIDATION_TOLERANCE: float = 1e-3

    # ============================================================================
    # NETWORK SETTINGS (Legacy Python P2P - kept for compatibility)
    # ============================================================================
    P2P_PORT: int = int(os.getenv('P2P_PORT', 4001))
    RPC_PORT: int = int(os.getenv('RPC_PORT', 5000))
    RPC_HOST: str = os.getenv('RPC_HOST', '127.0.0.1')
    
    PEER_SEEDS: list = [s.strip() for s in os.getenv('PEER_SEEDS', '').split(',') if s.strip()]
    MAX_PEERS: int = 50
    PEER_TIMEOUT: int = 300
    MESSAGE_CACHE_SIZE: int = 10000
    GOSSIP_RATE_LIMIT: int = 100

    # ============================================================================
    # RUST P2P SETTINGS (NEW - libp2p 0.56)
    # ============================================================================
    ENABLE_RUST_P2P: bool = os.getenv('ENABLE_RUST_P2P', 'true').lower() == 'true'
    RUST_P2P_PORT: int = int(os.getenv('RUST_P2P_PORT', 4001))
    RUST_P2P_GRPC: int = int(os.getenv('RUST_P2P_GRPC', 50051))
    RUST_P2P_GRPC_HOST: str = os.getenv('RUST_P2P_GRPC_HOST', '')  # empty = spawn subprocess
    RUST_P2P_BINARY: str = os.getenv('RUST_P2P_BINARY', 'rust-p2p/target/release/qubitcoin-p2p')
    RUST_P2P_STARTUP_TIMEOUT: int = int(os.getenv('RUST_P2P_STARTUP_TIMEOUT', '10'))
    BOOTSTRAP_PEERS: str = os.getenv('BOOTSTRAP_PEERS', '')

    # ============================================================================
    # DATABASE SETTINGS
    # ============================================================================
    DATABASE_URL: str = os.getenv(
        'DATABASE_URL',
        'postgresql://root@localhost:26257/qbc?sslmode=disable'
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ============================================================================
    # STORAGE SETTINGS
    # ============================================================================
    IPFS_API: str = os.getenv('IPFS_API', '/ip4/127.0.0.1/tcp/5002/http')
    # IPFS gateway port — default 8081 to avoid conflict with CockroachDB admin UI (8080)
    IPFS_GATEWAY_PORT: int = int(os.getenv('IPFS_GATEWAY_PORT', 8081))
    PINATA_JWT: Optional[str] = os.getenv('PINATA_JWT')
    SNAPSHOT_INTERVAL: int = int(os.getenv('SNAPSHOT_INTERVAL', 100))

    # ============================================================================
    # SUPERSYMMETRIC ECONOMIC PARAMETERS (SUSY Economics)
    # ============================================================================

    # Core constants
    MAX_SUPPLY: Decimal = Decimal('3300000000')  # 3.3 billion QBC
    TARGET_BLOCK_TIME: float = 3.3  # seconds (supersymmetric constant)
    EMISSION_PERIOD: int = 33  # years (3.3 × 10)

    # Golden Ratio (φ) - Nature's perfect proportion
    PHI: float = 1.618033988749895  # (1 + √5) / 2
    PHI_INVERSE: float = 0.618033988749895  # 1/φ

    # Block calculations
    BLOCKS_PER_YEAR: int = 9_563_636  # 365.25 days × 86,400 sec ÷ 3.3 sec
    TOTAL_EMISSION_BLOCKS: int = 315_600_000  # 33 years of blocks

    # Reward schedule (Golden ratio decay)
    INITIAL_REWARD: Decimal = Decimal('15.27')  # QBC per block (Era 0)
    HALVING_INTERVAL: int = 15_474_020  # φ years in blocks (~1.618 years)

    # Tail emission — small fixed reward that continues after phi-halving
    # reward drops below this threshold.  Ensures 100% of MAX_SUPPLY is
    # eventually mineable (phi-halving alone converges to only ~651M QBC).
    # Tail emission continues until total_supply reaches MAX_SUPPLY.
    TAIL_EMISSION_REWARD: Decimal = Decimal(os.getenv('TAIL_EMISSION_REWARD', '0.1'))

    # Genesis premine — ~1% of max supply allocated at block 0
    GENESIS_PREMINE: Decimal = Decimal(os.getenv('GENESIS_PREMINE', '33000000'))

    # ── Canonical Genesis Block ──────────────────────────────────────
    # Every node MUST use the same genesis block. Mining block 0 via VQE
    # is forbidden — genesis is a fixed constant, not a mined block.
    # This prevents independent chains from forming when nodes start fresh.
    # The chain was bootstrapped with block_hash = all-zeros for genesis.
    # Block 1's prev_hash references this. Both the stored hash (all-zeros)
    # and the calculated content hash are valid identifiers for genesis.
    CANONICAL_GENESIS_HASH: str = '0000000000000000000000000000000000000000000000000000000000000000'
    CANONICAL_GENESIS_CONTENT_HASH: str = 'dde8da5cc5417e5f615d8b68061a40bfd3a23b57191d59fb5f9362d03b3ea040'
    CANONICAL_GENESIS_TIMESTAMP: float = 1707350400.0  # 2024-02-08T00:00:00Z
    CANONICAL_GENESIS_COINBASE_TXID: str = '4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b'

    # If True, this node is allowed to create the genesis block (first node only).
    # All subsequent nodes MUST sync genesis from the network.
    ALLOW_GENESIS_MINE: bool = os.getenv('ALLOW_GENESIS_MINE', 'false').lower() == 'true'

    # Default sync peer — new nodes MUST sync from an existing node before mining.
    SYNC_PEER_URL: str = os.getenv('SYNC_PEER_URL', '')

    # Fee structure (micro-fees for high frequency)
    MIN_FEE: Decimal = Decimal('0.0001')
    FEE_RATE: Decimal = Decimal('0.0001')

    # Fee burning — percentage of L1 transaction fees permanently destroyed
    # to create deflationary pressure (EIP-1559 inspired).
    # 0.0 = no burn (all fees to miner), 1.0 = burn everything.
    FEE_BURN_PERCENTAGE: float = float(os.getenv('FEE_BURN_PERCENTAGE', '0.5'))

    # ============================================================================
    # CONSENSUS PARAMETERS
    # ============================================================================
    INITIAL_DIFFICULTY: float = float(os.getenv('INITIAL_DIFFICULTY', 1.0))
    DIFFICULTY_WINDOW: int = 144  # 144-block lookback window for difficulty calc
    DIFFICULTY_ADJUSTMENT_INTERVAL: int = 1  # Adjust EVERY block (per-block adjustment)
    MAX_DIFFICULTY_CHANGE: float = 0.10  # Max +/-10% per adjustment
    DIFFICULTY_FLOOR: float = float(os.getenv('DIFFICULTY_FLOOR', 0.5))
    DIFFICULTY_CEILING: float = float(os.getenv('DIFFICULTY_CEILING', 1000.0))
    # VQE ground-state energies are typically in [-5, +5].  Once difficulty
    # exceeds this threshold it is trivially easy (energy < difficulty always
    # true) and further increases can't speed up mining — compute time is the
    # bottleneck.  The adjustment algorithm holds steady above this value.
    DIFFICULTY_MEANINGFUL_MAX: float = float(os.getenv('DIFFICULTY_MEANINGFUL_MAX', 10.0))
    # Margin above exact ground state energy that difficulty must exceed.
    # Ensures VQE can feasibly find a solution (VQE finds local minima,
    # not always the exact ground state).
    ENERGY_MARGIN: float = float(os.getenv('ENERGY_MARGIN', 0.5))
    # PHI_FORK_HEIGHT removed — v3 is the only formula (DB reset + new genesis)
    # One-time difficulty reset height to recover from ceiling runaway
    DIFFICULTY_CEILING_FIX_HEIGHT: int = int(os.getenv('DIFFICULTY_CEILING_FIX_HEIGHT', 2750))
    COINBASE_MATURITY: int = 100  # Coinbase outputs unspendable for 100 blocks
    MAX_FUTURE_BLOCK_TIME: int = 120  # Max seconds a block timestamp can be in the future (2 minutes)
    CONFIRMATION_DEPTH: int = 180  # Wait 180 blocks (~10 min) for finality
    MAX_REORG_DEPTH: int = 100

    # ============================================================================
    # MINING SETTINGS (Production - Hardcoded)
    # ============================================================================
    MINING_INTERVAL: int = 1  # Attempt every 1 second (VQE + wait)
    AUTO_MINE: bool = os.getenv('AUTO_MINE', 'true').lower() == 'true'

    # ============================================================================
    # SMART CONTRACT SETTINGS
    # ============================================================================
    SUPPORTED_CONTRACT_TYPES: list = [
        'token', 'nft', 'launchpad', 'escrow', 'governance',
        'quantum_gate', 'stablecoin', 'vault', 'oracle'
    ]
    GAS_CONTRACT_DEPLOY_BASE: Decimal = Decimal('0.1')
    GAS_CONTRACT_DEPLOY_PER_KB: Decimal = Decimal('0.01')
    GAS_CONTRACT_EXECUTE_BASE: Decimal = Decimal('0.01')
    MAX_CONTRACT_SIZE: int = 256_000  # 256KB max contract code

    # QVM Settings
    CHAIN_ID: int = int(os.getenv('CHAIN_ID', 3303))  # QBC chain ID
    BLOCK_GAS_LIMIT: int = int(os.getenv('BLOCK_GAS_LIMIT', 30_000_000))
    DEFAULT_GAS_PRICE: Decimal = Decimal('0.000000001')  # 1 Gwei equivalent in QBC

    # EIP-1559 Base Fee Parameters
    EIP1559_INITIAL_BASE_FEE: int = int(os.getenv('EIP1559_INITIAL_BASE_FEE', 1_000_000_000))  # 1 gwei
    EIP1559_ELASTICITY_MULTIPLIER: int = int(os.getenv('EIP1559_ELASTICITY_MULTIPLIER', 2))
    EIP1559_BASE_FEE_CHANGE_DENOMINATOR: int = int(os.getenv('EIP1559_BASE_FEE_CHANGE_DENOMINATOR', 8))

    # EIP-2930 Access List Gas Costs
    EIP2930_ACCESS_LIST_ADDRESS_COST: int = int(os.getenv('EIP2930_ACCESS_LIST_ADDRESS_COST', 2400))
    EIP2930_ACCESS_LIST_STORAGE_KEY_COST: int = int(os.getenv('EIP2930_ACCESS_LIST_STORAGE_KEY_COST', 1900))

    # ============================================================================
    # BRIDGE SETTINGS
    # ============================================================================
    INFURA_URL: Optional[str] = os.getenv('INFURA_URL')
    # ETH_PRIVATE_KEY loaded from secure_key.env only (never from .env)
    ETH_PRIVATE_KEY: Optional[str] = os.getenv('ETH_PRIVATE_KEY_SECURE')
    BRIDGE_CONTRACT_ADDRESS: Optional[str] = os.getenv('BRIDGE_CONTRACT_ADDRESS')
    QUSD_TREASURY_ADDRESS: str = os.getenv('QUSD_TREASURY_ADDRESS', '')
    BRIDGE_TREASURY_ADDRESS: str = os.getenv('BRIDGE_TREASURY_ADDRESS', '')

    # ============================================================================
    # AETHER TREE FEE ECONOMICS
    # ============================================================================
    AETHER_CHAT_FEE_QBC: Decimal = Decimal(os.getenv('AETHER_CHAT_FEE_QBC', '0.01'))
    AETHER_CHAT_FEE_USD_TARGET: float = float(os.getenv('AETHER_CHAT_FEE_USD_TARGET', '0.005'))
    AETHER_FEE_PRICING_MODE: str = os.getenv('AETHER_FEE_PRICING_MODE', 'qusd_peg')
    AETHER_FEE_MIN_QBC: Decimal = Decimal(os.getenv('AETHER_FEE_MIN_QBC', '0.001'))
    AETHER_FEE_MAX_QBC: Decimal = Decimal(os.getenv('AETHER_FEE_MAX_QBC', '1.0'))
    AETHER_FEE_UPDATE_INTERVAL: int = int(os.getenv('AETHER_FEE_UPDATE_INTERVAL', '100'))
    AETHER_FEE_TREASURY_ADDRESS: str = os.getenv('AETHER_FEE_TREASURY_ADDRESS', '')
    AETHER_QUERY_FEE_MULTIPLIER: float = float(os.getenv('AETHER_QUERY_FEE_MULTIPLIER', '2.0'))
    AETHER_FREE_TIER_MESSAGES: int = int(os.getenv('AETHER_FREE_TIER_MESSAGES', '100'))

    # ============================================================================
    # CONTRACT DEPLOYMENT FEE ECONOMICS
    # ============================================================================
    CONTRACT_DEPLOY_BASE_FEE_QBC: Decimal = Decimal(os.getenv('CONTRACT_DEPLOY_BASE_FEE_QBC', '1.0'))
    CONTRACT_DEPLOY_PER_KB_FEE_QBC: Decimal = Decimal(os.getenv('CONTRACT_DEPLOY_PER_KB_FEE_QBC', '0.1'))
    CONTRACT_DEPLOY_FEE_USD_TARGET: float = float(os.getenv('CONTRACT_DEPLOY_FEE_USD_TARGET', '5.0'))
    CONTRACT_FEE_PRICING_MODE: str = os.getenv('CONTRACT_FEE_PRICING_MODE', 'qusd_peg')
    CONTRACT_FEE_TREASURY_ADDRESS: str = os.getenv('CONTRACT_FEE_TREASURY_ADDRESS', '')
    CONTRACT_EXECUTE_BASE_FEE_QBC: Decimal = Decimal(os.getenv('CONTRACT_EXECUTE_BASE_FEE_QBC', '0.01'))
    CONTRACT_TEMPLATE_DISCOUNT: float = float(os.getenv('CONTRACT_TEMPLATE_DISCOUNT', '0.5'))

    # ============================================================================
    # QUSD CDP (Collateralized Debt Positions)
    # ============================================================================
    CDP_BASE_INTEREST_RATE: float = float(os.getenv('CDP_BASE_INTEREST_RATE', '0.02'))
    CDP_INTEREST_SLOPE: float = float(os.getenv('CDP_INTEREST_SLOPE', '0.1'))
    CDP_MIN_COLLATERAL_RATIO: float = float(os.getenv('CDP_MIN_COLLATERAL_RATIO', '1.5'))
    CDP_LIQUIDATION_RATIO: float = float(os.getenv('CDP_LIQUIDATION_RATIO', '1.2'))
    CDP_LIQUIDATION_PENALTY: float = float(os.getenv('CDP_LIQUIDATION_PENALTY', '0.13'))
    CDP_MAX_DEBT_CEILING: Decimal = Decimal(os.getenv('CDP_MAX_DEBT_CEILING', '1000000'))

    # ============================================================================
    # QUSD RESERVE ATTESTATION (Chainlink-style Proof of Reserve)
    # ============================================================================
    RESERVE_ATTESTATION_INTERVAL: int = int(os.getenv('RESERVE_ATTESTATION_INTERVAL', '1000'))
    RESERVE_MIN_RATIO: float = float(os.getenv('RESERVE_MIN_RATIO', '1.0'))

    # ============================================================================
    # QUSD INSURANCE FUND
    # ============================================================================
    QUSD_INSURANCE_FUND_PERCENTAGE: float = float(os.getenv('QUSD_INSURANCE_FUND_PERCENTAGE', '0.05'))
    QUSD_INSURANCE_FUND_ADDRESS: str = os.getenv('QUSD_INSURANCE_FUND_ADDRESS', '')
    QUSD_INSURANCE_PAYOUT_THRESHOLD: float = float(os.getenv('QUSD_INSURANCE_PAYOUT_THRESHOLD', '0.90'))

    # ============================================================================
    # QUSD REDEMPTION FEE (dynamic, increases when reserve ratio < 100%)
    # ============================================================================
    QUSD_REDEMPTION_BASE_FEE_BPS: int = int(os.getenv('QUSD_REDEMPTION_BASE_FEE_BPS', '10'))  # 10 bps = 0.1%
    QUSD_REDEMPTION_FEE_MULTIPLIER: float = float(os.getenv('QUSD_REDEMPTION_FEE_MULTIPLIER', '5.0'))

    # ============================================================================
    # QUSD FLASH LOANS
    # ============================================================================
    QUSD_FLASH_LOAN_FEE_BPS: int = int(os.getenv('QUSD_FLASH_LOAN_FEE_BPS', '9'))  # 9 bps = 0.09% (Aave-style)
    QUSD_FLASH_LOAN_MAX_AMOUNT: Decimal = Decimal(os.getenv('QUSD_FLASH_LOAN_MAX_AMOUNT', '1000000'))  # 1M QUSD max
    QUSD_FLASH_LOAN_ENABLED: bool = os.getenv('QUSD_FLASH_LOAN_ENABLED', 'true').lower() == 'true'

    # ============================================================================
    # QUSD SAVINGS RATE (DSR-style yield on deposited QUSD)
    # ============================================================================
    QUSD_SAVINGS_RATE: float = float(os.getenv('QUSD_SAVINGS_RATE', '0.033'))  # 3.3% APY
    QUSD_SAVINGS_MIN_DEPOSIT: Decimal = Decimal(os.getenv('QUSD_SAVINGS_MIN_DEPOSIT', '1.0'))
    QUSD_SAVINGS_MAX_RATE: float = float(os.getenv('QUSD_SAVINGS_MAX_RATE', '0.20'))  # 20% cap

    # ============================================================================
    # BRIDGE LP REWARDS
    # ============================================================================
    BRIDGE_LP_REWARD_RATE: Decimal = Decimal(os.getenv('BRIDGE_LP_REWARD_RATE', '0.5'))  # QBC per block to LP pool
    BRIDGE_LP_REWARD_RATE_BPS: int = int(os.getenv('BRIDGE_LP_REWARD_RATE_BPS', '500'))  # 500 bps = 5% APY
    BRIDGE_LP_MIN_DEPOSIT: Decimal = Decimal(os.getenv('BRIDGE_LP_MIN_DEPOSIT', '10.0'))
    BRIDGE_LP_MIN_LIQUIDITY: Decimal = Decimal(os.getenv('BRIDGE_LP_MIN_LIQUIDITY', '10.0'))  # Alias for MIN_DEPOSIT
    BRIDGE_LP_REWARD_COOLDOWN_BLOCKS: int = int(os.getenv('BRIDGE_LP_REWARD_COOLDOWN_BLOCKS', '100'))

    # ============================================================================
    # BRIDGE FEES (editable)
    # ============================================================================
    BRIDGE_FEE_BPS: int = int(os.getenv('BRIDGE_FEE_BPS', '30'))  # Basis points (30 = 0.3%)
    BRIDGE_VALIDATOR_REWARD_QBC: float = float(os.getenv('BRIDGE_VALIDATOR_REWARD_QBC', '0.01'))
    BRIDGE_RELAYER_REWARD_QBC: float = float(os.getenv('BRIDGE_RELAYER_REWARD_QBC', '0.05'))
    BRIDGE_RELAYER_MIN_STAKE: float = float(os.getenv('BRIDGE_RELAYER_MIN_STAKE', '100.0'))

    # ============================================================================
    # QUSD KEEPER SETTINGS
    # ============================================================================
    KEEPER_ENABLED: bool = os.getenv('KEEPER_ENABLED', 'true').lower() == 'true'
    KEEPER_DEFAULT_MODE: str = os.getenv('KEEPER_DEFAULT_MODE', 'scan')  # off|scan|periodic|continuous|aggressive
    KEEPER_CHECK_INTERVAL: int = int(os.getenv('KEEPER_CHECK_INTERVAL', '10'))  # blocks
    KEEPER_MAX_TRADE_SIZE: float = float(os.getenv('KEEPER_MAX_TRADE_SIZE', '1000000'))
    KEEPER_FLOOR_PRICE: float = float(os.getenv('KEEPER_FLOOR_PRICE', '0.99'))
    KEEPER_CEILING_PRICE: float = float(os.getenv('KEEPER_CEILING_PRICE', '1.01'))
    KEEPER_COOLDOWN_BLOCKS: int = int(os.getenv('KEEPER_COOLDOWN_BLOCKS', '10'))
    KEEPER_ROLE: str = os.getenv('KEEPER_ROLE', 'primary')  # primary|observer — observer nodes only scan, never execute
    QUSD_STABILIZER_ADDRESS: str = os.getenv('QUSD_STABILIZER_ADDRESS', '')

    # ============================================================================
    # ON-CHAIN AGI CONTRACT ADDRESSES (set after deployment)
    # Auto-populated from contract_registry.json if env vars are empty.
    # ============================================================================
    CONSCIOUSNESS_DASHBOARD_ADDRESS: str = os.getenv('CONSCIOUSNESS_DASHBOARD_ADDRESS', '')
    PROOF_OF_THOUGHT_ADDRESS: str = os.getenv('PROOF_OF_THOUGHT_ADDRESS', '')
    CONSTITUTIONAL_AI_ADDRESS: str = os.getenv('CONSTITUTIONAL_AI_ADDRESS', '')
    TREASURY_DAO_ADDRESS: str = os.getenv('TREASURY_DAO_ADDRESS', '')
    UPGRADE_GOVERNOR_ADDRESS: str = os.getenv('UPGRADE_GOVERNOR_ADDRESS', '')
    VALIDATOR_REGISTRY_ADDRESS: str = os.getenv('VALIDATOR_REGISTRY_ADDRESS', '')
    EMERGENCY_SHUTDOWN_ADDRESS: str = os.getenv('EMERGENCY_SHUTDOWN_ADDRESS', '')
    # Kernel address used as msg.sender for on-chain AGI calls
    AETHER_KERNEL_ADDRESS: str = os.getenv('AETHER_KERNEL_ADDRESS', '')

    # ============================================================================
    # HIGGS COGNITIVE FIELD PARAMETERS
    # ============================================================================
    HIGGS_FIELD_ADDRESS: str = os.getenv('HIGGS_FIELD_ADDRESS', '')
    HIGGS_MU: float = float(os.getenv('HIGGS_MU', '88.45'))
    HIGGS_LAMBDA: float = float(os.getenv('HIGGS_LAMBDA', '0.129'))
    HIGGS_TAN_BETA: float = float(os.getenv('HIGGS_TAN_BETA', '1.618033988749895'))
    HIGGS_EXCITATION_THRESHOLD: float = float(os.getenv('HIGGS_EXCITATION_THRESHOLD', '0.10'))
    HIGGS_DT: float = float(os.getenv('HIGGS_DT', '0.01'))
    HIGGS_ENABLE_MASS_REBALANCING: bool = os.getenv('HIGGS_ENABLE_MASS_REBALANCING', 'true').lower() == 'true'
    HIGGS_FIELD_UPDATE_INTERVAL: int = int(os.getenv('HIGGS_FIELD_UPDATE_INTERVAL', '1'))

    # ============================================================================
    # INVESTOR PUBLIC SALE
    # ============================================================================
    INVESTOR_REVENUE_SPLIT: float = float(os.getenv('INVESTOR_REVENUE_SPLIT', '0.10'))
    INVESTOR_REVENUE_ADDRESS: str = os.getenv('INVESTOR_REVENUE_ADDRESS', '')
    INVESTOR_SEED_ROUND_CONTRACT: str = os.getenv('INVESTOR_SEED_ROUND_CONTRACT', '')
    INVESTOR_VESTING_CONTRACT: str = os.getenv('INVESTOR_VESTING_CONTRACT', '')
    INVESTOR_REVENUE_CONTRACT: str = os.getenv('INVESTOR_REVENUE_CONTRACT', '')
    INVESTOR_TREASURY_WALLET: str = os.getenv('INVESTOR_TREASURY_WALLET', '')
    ETH_RPC_URL: str = os.getenv('ETH_RPC_URL', 'https://eth.llamarpc.com')
    ETHERSCAN_API_KEY: str = os.getenv('ETHERSCAN_API_KEY', '')
    SEED_ROUND_ETH_ADDRESS: str = os.getenv('SEED_ROUND_ETH_ADDRESS', '')
    SEED_ROUND_TOKEN_PRICE: str = os.getenv('SEED_ROUND_TOKEN_PRICE', '1.0')
    SEED_ROUND_HARD_CAP: str = os.getenv('SEED_ROUND_HARD_CAP', '10000000')
    CHAINLINK_ETH_USD_FEED: str = os.getenv('CHAINLINK_ETH_USD_FEED', '0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419')

    # ============================================================================
    # QUSD CONTRACT ADDRESSES (set after deployment)
    # ============================================================================
    QUSD_TOKEN_ADDRESS: str = os.getenv('QUSD_TOKEN_ADDRESS', '')
    QUSD_RESERVE_ADDRESS: str = os.getenv('QUSD_RESERVE_ADDRESS', '')
    # How often to write Phi to chain (every N blocks)
    ONCHAIN_PHI_INTERVAL: int = int(os.getenv('ONCHAIN_PHI_INTERVAL', '10'))

    # ============================================================================
    # LLM / EXTERNAL AI CONFIGURATION
    # ============================================================================
    LLM_ENABLED: bool = os.getenv('LLM_ENABLED', 'false').lower() == 'true'
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-4')
    OPENAI_MAX_TOKENS: int = int(os.getenv('OPENAI_MAX_TOKENS', '1024'))
    OPENAI_TEMPERATURE: float = float(os.getenv('OPENAI_TEMPERATURE', '0.7'))
    CLAUDE_API_KEY: str = os.getenv('CLAUDE_API_KEY', '')
    CLAUDE_MODEL: str = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')
    LOCAL_LLM_URL: str = os.getenv('LOCAL_LLM_URL', '')
    OLLAMA_BASE_URL: str = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL: str = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')
    LLM_PRIMARY_ADAPTER: str = os.getenv('LLM_PRIMARY_ADAPTER', 'openai')
    LLM_SEEDER_ENABLED: bool = os.getenv('LLM_SEEDER_ENABLED', 'false').lower() == 'true'
    LLM_SEEDER_INTERVAL_BLOCKS: int = int(os.getenv('LLM_SEEDER_INTERVAL_BLOCKS', '50'))
    LLM_SEEDER_RATE_LIMIT_PER_HOUR: int = int(os.getenv('LLM_SEEDER_RATE_LIMIT_PER_HOUR', '10'))
    LLM_SEEDER_MAX_TOKENS: int = int(os.getenv('LLM_SEEDER_MAX_TOKENS', '2048'))
    LLM_SEEDER_COOLDOWN_SECONDS: int = int(os.getenv('LLM_SEEDER_COOLDOWN_SECONDS', '15'))

    # ============================================================================
    # DB MAINTENANCE / PRUNING
    # ============================================================================
    PHI_DOWNSAMPLE_RETAIN_DAYS: int = int(os.getenv('PHI_DOWNSAMPLE_RETAIN_DAYS', '7'))
    PHI_DOWNSAMPLE_INTERVAL: int = int(os.getenv('PHI_DOWNSAMPLE_INTERVAL', '1000'))
    PRUNE_CONFIDENCE_THRESHOLD: float = float(os.getenv('PRUNE_CONFIDENCE_THRESHOLD', '0.1'))
    PRUNE_INTERVAL_BLOCKS: int = int(os.getenv('PRUNE_INTERVAL_BLOCKS', '500'))
    REASONING_ARCHIVE_RETAIN_BLOCKS: int = int(os.getenv('REASONING_ARCHIVE_RETAIN_BLOCKS', '50000'))

    # ============================================================================
    # KNOWLEDGE GRAPH INTELLIGENCE
    # ============================================================================
    CONFIDENCE_DECAY_HALFLIFE: int = int(os.getenv('CONFIDENCE_DECAY_HALFLIFE', '100000'))
    CONFIDENCE_DECAY_FLOOR: float = float(os.getenv('CONFIDENCE_DECAY_FLOOR', '0.3'))

    # ============================================================================
    # SEPHIROT STAKING
    # ============================================================================
    SEPHIROT_STAKER_SHARE_RATIO: float = float(os.getenv('SEPHIROT_STAKER_SHARE_RATIO', '0.6'))
    SEPHIROT_REWARD_INTERVAL: int = int(os.getenv('SEPHIROT_REWARD_INTERVAL', '100'))
    SEPHIROT_MIN_STAKE: float = float(os.getenv('SEPHIROT_MIN_STAKE', '100.0'))
    SEPHIROT_UNSTAKING_DELAY_BLOCKS: int = int(os.getenv('SEPHIROT_UNSTAKING_DELAY_BLOCKS', '183272'))
    SEPHIROT_MAX_STAKE_PER_NODE: float = float(os.getenv('SEPHIROT_MAX_STAKE_PER_NODE', '1000000.0'))
    SEPHIROT_MAX_STAKE_PER_ADDRESS: float = float(os.getenv('SEPHIROT_MAX_STAKE_PER_ADDRESS', '100000.0'))
    SEPHIROT_NODE_MAX_SHARE: float = float(os.getenv('SEPHIROT_NODE_MAX_SHARE', '0.20'))
    SEPHIROT_STAKE_ENERGY_FACTOR: float = float(os.getenv('SEPHIROT_STAKE_ENERGY_FACTOR', '0.5'))
    POT_VALIDATOR_MAX_VOTE_WEIGHT: float = float(os.getenv('POT_VALIDATOR_MAX_VOTE_WEIGHT', '0.33'))

    # ============================================================================
    # AETHER TREE BLOCK INTERVALS (all configurable via .env)
    # ============================================================================
    AETHER_CONFIDENCE_PROPAGATION_INTERVAL: int = int(os.getenv('AETHER_CONFIDENCE_PROPAGATION_INTERVAL', '10'))
    AETHER_POT_PROCESS_INTERVAL: int = int(os.getenv('AETHER_POT_PROCESS_INTERVAL', '5'))
    AETHER_SEPHIROT_ROUTE_INTERVAL: int = int(os.getenv('AETHER_SEPHIROT_ROUTE_INTERVAL', '5'))
    AETHER_CONTRADICTION_RESOLVE_INTERVAL: int = int(os.getenv('AETHER_CONTRADICTION_RESOLVE_INTERVAL', '1000'))
    AETHER_KETER_GOALS_INTERVAL: int = int(os.getenv('AETHER_KETER_GOALS_INTERVAL', '500'))
    AETHER_KG_BOOST_INTERVAL: int = int(os.getenv('AETHER_KG_BOOST_INTERVAL', '1000'))
    AETHER_SELF_REFLECT_INTERVAL: int = int(os.getenv('AETHER_SELF_REFLECT_INTERVAL', '50'))
    AETHER_DREAM_ANALOGIES_INTERVAL: int = int(os.getenv('AETHER_DREAM_ANALOGIES_INTERVAL', '50'))
    AETHER_CAUSAL_DISCOVERY_INTERVAL: int = int(os.getenv('AETHER_CAUSAL_DISCOVERY_INTERVAL', '50'))
    AETHER_DEBATE_INTERVAL: int = int(os.getenv('AETHER_DEBATE_INTERVAL', '25'))
    AETHER_CONCEPT_FORMATION_INTERVAL: int = int(os.getenv('AETHER_CONCEPT_FORMATION_INTERVAL', '50'))
    AETHER_MEMORY_CONSOLIDATE_INTERVAL: int = int(os.getenv('AETHER_MEMORY_CONSOLIDATE_INTERVAL', '50'))
    AETHER_EPISODIC_REPLAY_INTERVAL: int = int(os.getenv('AETHER_EPISODIC_REPLAY_INTERVAL', '50'))
    AETHER_CURIOSITY_INTERVAL: int = int(os.getenv('AETHER_CURIOSITY_INTERVAL', '50'))
    AETHER_KNOWLEDGE_DIGEST_INTERVAL: int = int(os.getenv('AETHER_KNOWLEDGE_DIGEST_INTERVAL', '100'))
    AETHER_SELF_IMPROVEMENT_INTERVAL: int = int(os.getenv('AETHER_SELF_IMPROVEMENT_INTERVAL', '100'))
    AETHER_EXTERNAL_KNOWLEDGE_INTERVAL: int = int(os.getenv('AETHER_EXTERNAL_KNOWLEDGE_INTERVAL', '1000'))
    AETHER_CONSCIOUSNESS_ARCHIVE_INTERVAL: int = int(os.getenv('AETHER_CONSCIOUSNESS_ARCHIVE_INTERVAL', '5000'))
    AETHER_REASONING_ARCHIVE_INTERVAL: int = int(os.getenv('AETHER_REASONING_ARCHIVE_INTERVAL', '10000'))
    AETHER_SEPHIROT_PERSIST_INTERVAL: int = int(os.getenv('AETHER_SEPHIROT_PERSIST_INTERVAL', '100'))

    # ============================================================================
    # KNOWLEDGE GRAPH SETTINGS
    # ============================================================================
    KNOWLEDGE_GRAPH_MAX_NODES: int = int(os.getenv('KNOWLEDGE_GRAPH_MAX_NODES', '500000'))
    KNOWLEDGE_GRAPH_AUTO_PRUNE_THRESHOLD: float = float(os.getenv('KNOWLEDGE_GRAPH_AUTO_PRUNE_THRESHOLD', '0.08'))
    KNOWLEDGE_GRAPH_DUPLICATE_SIMILARITY: float = float(os.getenv('KNOWLEDGE_GRAPH_DUPLICATE_SIMILARITY', '0.92'))

    # ============================================================================
    # WORKING MEMORY SETTINGS
    # ============================================================================
    WORKING_MEMORY_DECAY_FACTOR: float = float(os.getenv('WORKING_MEMORY_DECAY_FACTOR', '0.95'))
    WORKING_MEMORY_MIN_CAPACITY: int = int(os.getenv('WORKING_MEMORY_MIN_CAPACITY', '20'))
    WORKING_MEMORY_MAX_CAPACITY: int = int(os.getenv('WORKING_MEMORY_MAX_CAPACITY', '200'))

    # ============================================================================
    # AETHER CHAT SETTINGS
    # ============================================================================
    AETHER_CHAT_RATE_LIMIT: int = int(os.getenv('AETHER_CHAT_RATE_LIMIT', '30'))
    AETHER_CHAT_CONTEXT_WINDOW: int = int(os.getenv('AETHER_CHAT_CONTEXT_WINDOW', '10'))
    AETHER_SESSION_TTL_SECONDS: int = int(os.getenv('AETHER_SESSION_TTL_SECONDS', '7200'))

    # ============================================================================
    # REASONING SETTINGS
    # ============================================================================
    REASONING_CONFIDENCE_FLOOR: float = float(os.getenv('REASONING_CONFIDENCE_FLOOR', '0.1'))
    REASONING_CROSS_DOMAIN_INTERVAL: int = int(os.getenv('REASONING_CROSS_DOMAIN_INTERVAL', '500'))

    # ============================================================================
    # PROOF-OF-THOUGHT ENFORCEMENT HEIGHTS
    # ============================================================================
    MANDATORY_POT_HEIGHT: int = int(os.getenv('MANDATORY_POT_HEIGHT', '1000'))
    MANDATORY_PHI_ENFORCEMENT_HEIGHT: int = int(os.getenv('MANDATORY_PHI_ENFORCEMENT_HEIGHT', '5000'))
    PHI_THRESHOLD: float = float(os.getenv('PHI_THRESHOLD', '3.0'))

    # Phi calculator spectral bisection sampling limits
    PHI_MAX_SAMPLE_NODES: int = int(os.getenv('PHI_MAX_SAMPLE_NODES', '2000'))
    PHI_SAMPLE_SEED: int = int(os.getenv('PHI_SAMPLE_SEED', '42'))

    # ============================================================================
    # SELF-IMPROVEMENT ENGINE (Recursive reasoning optimization)
    # ============================================================================
    SELF_IMPROVEMENT_INTERVAL: int = int(os.getenv('SELF_IMPROVEMENT_INTERVAL', '100'))
    SELF_IMPROVEMENT_MIN_WEIGHT: float = float(os.getenv('SELF_IMPROVEMENT_MIN_WEIGHT', '0.05'))
    SELF_IMPROVEMENT_MAX_WEIGHT: float = float(os.getenv('SELF_IMPROVEMENT_MAX_WEIGHT', '0.5'))

    # ============================================================================
    # RPC API LIMITS
    # ============================================================================
    RPC_GRAPH_MAX_NODES: int = int(os.getenv('RPC_GRAPH_MAX_NODES', '5000'))
    RPC_SEARCH_MAX_RESULTS: int = int(os.getenv('RPC_SEARCH_MAX_RESULTS', '200'))
    RPC_JSONLD_MAX_NODES: int = int(os.getenv('RPC_JSONLD_MAX_NODES', '10000'))
    RPC_PHI_HISTORY_MAX: int = int(os.getenv('RPC_PHI_HISTORY_MAX', '1000'))
    RPC_BLOCK_RANGE_MAX: int = int(os.getenv('RPC_BLOCK_RANGE_MAX', '1000'))

    # ============================================================================
    # MEV PROTECTION (Commit-Reveal Transaction Ordering)
    # ============================================================================
    MEV_COMMIT_REVEAL_ENABLED: bool = os.getenv('MEV_COMMIT_REVEAL_ENABLED', 'true').lower() == 'true'
    MEV_REVEAL_WINDOW_BLOCKS: int = int(os.getenv('MEV_REVEAL_WINDOW_BLOCKS', '10'))

    # ============================================================================
    # ADMIN API
    # ============================================================================
    ADMIN_API_KEY: str = os.getenv('ADMIN_API_KEY', '')

    # ============================================================================
    # KEY ROTATION SETTINGS
    # ============================================================================
    KEY_ROTATION_GRACE_PERIOD_DAYS: int = int(os.getenv('KEY_ROTATION_GRACE_PERIOD_DAYS', '7'))

    # ============================================================================
    # AIKGS (Aether Incentivized Knowledge Growth System)
    # ============================================================================
    AIKGS_ENABLED: bool = os.getenv('AIKGS_ENABLED', 'true').lower() == 'true'
    AIKGS_BASE_REWARD_QBC: float = float(os.getenv('AIKGS_BASE_REWARD_QBC', '0.05'))
    AIKGS_MAX_REWARD_QBC: float = float(os.getenv('AIKGS_MAX_REWARD_QBC', '0.5'))
    AIKGS_INITIAL_POOL_QBC: float = float(os.getenv('AIKGS_INITIAL_POOL_QBC', '1000000.0'))
    AIKGS_EARLY_THRESHOLD: int = int(os.getenv('AIKGS_EARLY_THRESHOLD', '10000'))
    AIKGS_EARLY_MAX_BONUS: float = float(os.getenv('AIKGS_EARLY_MAX_BONUS', '2.0'))
    AIKGS_QUALITY_WEIGHT: float = float(os.getenv('AIKGS_QUALITY_WEIGHT', '0.6'))
    AIKGS_NOVELTY_WEIGHT: float = float(os.getenv('AIKGS_NOVELTY_WEIGHT', '0.4'))
    AIKGS_L1_COMMISSION_RATE: float = float(os.getenv('AIKGS_L1_COMMISSION_RATE', '0.10'))
    AIKGS_L2_COMMISSION_RATE: float = float(os.getenv('AIKGS_L2_COMMISSION_RATE', '0.05'))
    AIKGS_MAX_DAILY_SUBMISSIONS: int = int(os.getenv('AIKGS_MAX_DAILY_SUBMISSIONS', '50'))
    AIKGS_AETHER_FEE_PERCENT: float = float(os.getenv('AIKGS_AETHER_FEE_PERCENT', '0.10'))
    AIKGS_EXCHANGE_FEE_PERCENT: float = float(os.getenv('AIKGS_EXCHANGE_FEE_PERCENT', '0.05'))
    AIKGS_DEFAULT_BOUNTY_REWARD: float = float(os.getenv('AIKGS_DEFAULT_BOUNTY_REWARD', '0.25'))
    AIKGS_DEFAULT_BOUNTY_DURATION_DAYS: int = int(os.getenv('AIKGS_DEFAULT_BOUNTY_DURATION_DAYS', '30'))
    AIKGS_CURATION_REQUIRED_VOTES: int = int(os.getenv('AIKGS_CURATION_REQUIRED_VOTES', '3'))

    # AIKGS Rust Sidecar
    AIKGS_USE_RUST_SIDECAR: bool = os.getenv('AIKGS_USE_RUST_SIDECAR', 'true').lower() == 'true'
    AIKGS_GRPC_PORT: int = int(os.getenv('AIKGS_GRPC_PORT', '50052'))
    AIKGS_GRPC_ADDR: str = os.getenv('AIKGS_GRPC_ADDR', '127.0.0.1')
    AIKGS_AUTH_TOKEN: str = os.getenv('AIKGS_AUTH_TOKEN', '')
    AIKGS_TREASURY_ADDRESS: str = os.getenv('AIKGS_TREASURY_ADDRESS', '')
    AIKGS_GRPC_TIMEOUT: int = int(os.getenv('AIKGS_GRPC_TIMEOUT', '5'))

    # AIKGS Contract Addresses (set after deployment)
    AIKGS_REWARD_POOL_ADDRESS: str = os.getenv('AIKGS_REWARD_POOL_ADDRESS', '')
    AIKGS_AFFILIATE_REGISTRY_ADDRESS: str = os.getenv('AIKGS_AFFILIATE_REGISTRY_ADDRESS', '')
    AIKGS_CONTRIBUTION_LEDGER_ADDRESS: str = os.getenv('AIKGS_CONTRIBUTION_LEDGER_ADDRESS', '')
    AIKGS_BOUNTY_CONTRACT_ADDRESS: str = os.getenv('AIKGS_BOUNTY_CONTRACT_ADDRESS', '')
    AIKGS_NFT_CONTRACT_ADDRESS: str = os.getenv('AIKGS_NFT_CONTRACT_ADDRESS', '')

    # API Key Vault
    API_KEY_VAULT_SECRET: str = os.getenv('API_KEY_VAULT_SECRET', '')

    # Additional LLM Adapters
    GROK_API_KEY: str = os.getenv('GROK_API_KEY', '')
    GROK_MODEL: str = os.getenv('GROK_MODEL', 'grok-2')
    GEMINI_API_KEY: str = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL: str = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    MISTRAL_API_KEY: str = os.getenv('MISTRAL_API_KEY', '')
    MISTRAL_MODEL: str = os.getenv('MISTRAL_MODEL', 'mistral-large-latest')

    # ============================================================================
    # TELEGRAM BOT
    # ============================================================================
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_BOT_USERNAME: str = os.getenv('TELEGRAM_BOT_USERNAME', '')
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
    TELEGRAM_MINI_APP_URL: str = os.getenv('TELEGRAM_MINI_APP_URL', '')
    TELEGRAM_WEBHOOK_URL: str = os.getenv('TELEGRAM_WEBHOOK_URL', '')

    # ============================================================================
    # GEVURAH SAFETY (Aether Tree veto / emergency shutdown authentication)
    # ============================================================================
    # Shared secret for HMAC-based veto and shutdown authentication.
    # Generate with: openssl rand -hex 32
    # If not set, a random ephemeral secret is generated at startup
    # (tokens will not persist across restarts).
    GEVURAH_SECRET: str = os.getenv('GEVURAH_SECRET', '')

    # ============================================================================
    # SUBSTRATE HYBRID MODE
    # ============================================================================
    SUBSTRATE_MODE: bool = os.getenv('SUBSTRATE_MODE', 'false').lower() == 'true'
    SUBSTRATE_WS_URL: str = os.getenv('SUBSTRATE_WS_URL', 'ws://localhost:9944')
    SUBSTRATE_HTTP_URL: str = os.getenv('SUBSTRATE_HTTP_URL', 'http://localhost:9944')
    SUBSTRATE_SUDO_SEED: str = os.getenv('SUBSTRATE_SUDO_SEED', '//Alice')

    # ============================================================================
    # DILITHIUM SECURITY LEVEL (ML-DSA)
    # ============================================================================
    # 2 = ML-DSA-44 (128-bit), 3 = ML-DSA-65 (192-bit), 5 = ML-DSA-87 (256-bit)
    DILITHIUM_LEVEL: int = int(os.getenv('DILITHIUM_SECURITY_LEVEL', '5'))

    @classmethod
    def get_security_level(cls) -> 'SecurityLevel':
        """Return the configured SecurityLevel enum value."""
        from .quantum.crypto import SecurityLevel
        return SecurityLevel(cls.DILITHIUM_LEVEL)

    @classmethod
    def _load_contract_registry(cls) -> None:
        """Auto-populate empty contract addresses from contract_registry.json.

        Maps registry contract names to Config class attributes.  Only
        overwrites attributes that are currently empty strings, so env-var
        overrides always take priority.
        """
        import json
        registry_path = _project_root / 'contract_registry.json'
        if not registry_path.exists():
            return

        try:
            with open(registry_path) as f:
                registry = json.load(f)
        except Exception:
            return

        # Mapping: registry key -> Config attribute name
        _REGISTRY_MAP = {
            'ConsciousnessDashboard': 'CONSCIOUSNESS_DASHBOARD_ADDRESS',
            'ProofOfThought': 'PROOF_OF_THOUGHT_ADDRESS',
            'ConstitutionalAI': 'CONSTITUTIONAL_AI_ADDRESS',
            'TreasuryDAO': 'TREASURY_DAO_ADDRESS',
            'UpgradeGovernor': 'UPGRADE_GOVERNOR_ADDRESS',
            'ValidatorRegistry': 'VALIDATOR_REGISTRY_ADDRESS',
            'EmergencyShutdown': 'EMERGENCY_SHUTDOWN_ADDRESS',
            'AetherKernel': 'AETHER_KERNEL_ADDRESS',
            'HiggsField': 'HIGGS_FIELD_ADDRESS',
            'SUSYEngine': 'SUSY_ENGINE_ADDRESS',
            'NodeRegistry': 'NODE_REGISTRY_ADDRESS',
        }

        loaded = 0
        for reg_name, attr_name in _REGISTRY_MAP.items():
            current = getattr(cls, attr_name, '')
            if current:
                continue  # env var already set — don't override
            entry = registry.get(reg_name)
            if not entry:
                continue
            # Entries have 'proxy' (upgradeable) or 'address' (direct)
            addr = entry.get('proxy') or entry.get('address', '')
            if addr:
                setattr(cls, attr_name, addr)
                loaded += 1

        if loaded > 0:
            # Use print because logger may not be initialized yet
            print(f"[Config] Loaded {loaded} contract addresses from contract_registry.json")

    # ============================================================================
    # TRANSACTION REVERSIBILITY
    # ============================================================================
    REVERSAL_DEFAULT_WINDOW: int = int(os.getenv('REVERSAL_DEFAULT_WINDOW', '0'))  # blocks (0 = irreversible)
    REVERSAL_MAX_WINDOW: int = int(os.getenv('REVERSAL_MAX_WINDOW', '26182'))  # ~24h at 3.3s/block
    REVERSAL_GUARDIAN_THRESHOLD: int = int(os.getenv('REVERSAL_GUARDIAN_THRESHOLD', '2'))

    # ============================================================================
    # INHERITANCE PROTOCOL
    # ============================================================================
    INHERITANCE_ENABLED: bool = os.getenv('INHERITANCE_ENABLED', 'true').lower() == 'true'
    INHERITANCE_DEFAULT_INACTIVITY: int = int(os.getenv('INHERITANCE_DEFAULT_INACTIVITY', '2618200'))  # ~100 days
    INHERITANCE_MIN_INACTIVITY: int = int(os.getenv('INHERITANCE_MIN_INACTIVITY', '26182'))  # ~24h
    INHERITANCE_MAX_INACTIVITY: int = int(os.getenv('INHERITANCE_MAX_INACTIVITY', '95636360'))  # ~10 years
    INHERITANCE_GRACE_PERIOD: int = int(os.getenv('INHERITANCE_GRACE_PERIOD', '78546'))  # ~3 days

    # ============================================================================
    # HIGH-SECURITY ACCOUNTS
    # ============================================================================
    SECURITY_POLICY_ENABLED: bool = os.getenv('SECURITY_POLICY_ENABLED', 'true').lower() == 'true'
    SECURITY_DAILY_LIMIT_WINDOW: int = int(os.getenv('SECURITY_DAILY_LIMIT_WINDOW', '26182'))  # ~24h in blocks
    SECURITY_MAX_WHITELIST_SIZE: int = int(os.getenv('SECURITY_MAX_WHITELIST_SIZE', '100'))
    SECURITY_MAX_TIME_LOCK: int = int(os.getenv('SECURITY_MAX_TIME_LOCK', '26182'))  # ~24h

    # ============================================================================
    # STRATUM MINING SERVER
    # ============================================================================
    STRATUM_ENABLED: bool = os.getenv('STRATUM_ENABLED', 'false').lower() == 'true'
    STRATUM_PORT: int = int(os.getenv('STRATUM_PORT', '3333'))
    STRATUM_HOST: str = os.getenv('STRATUM_HOST', '0.0.0.0')
    STRATUM_MAX_WORKERS: int = int(os.getenv('STRATUM_MAX_WORKERS', '100'))
    STRATUM_GRPC_PORT: int = int(os.getenv('STRATUM_GRPC_PORT', '50053'))

    # ============================================================================
    # DENIABLE RPCs (Privacy)
    # ============================================================================
    DENIABLE_RPC_ENABLED: bool = os.getenv('DENIABLE_RPC_ENABLED', 'true').lower() == 'true'
    DENIABLE_RPC_MAX_BATCH: int = int(os.getenv('DENIABLE_RPC_MAX_BATCH', '100'))
    DENIABLE_RPC_BLOOM_MAX_SIZE: int = int(os.getenv('DENIABLE_RPC_BLOOM_MAX_SIZE', '65536'))

    # ============================================================================
    # BFT FINALITY GADGET
    # ============================================================================
    FINALITY_ENABLED: bool = os.getenv('FINALITY_ENABLED', 'true').lower() == 'true'
    FINALITY_MIN_STAKE: float = float(os.getenv('FINALITY_MIN_STAKE', '100.0'))
    FINALITY_THRESHOLD: float = float(os.getenv('FINALITY_THRESHOLD', '0.667'))
    FINALITY_VOTE_EXPIRY_BLOCKS: int = int(os.getenv('FINALITY_VOTE_EXPIRY_BLOCKS', '1000'))

    # ============================================================================
    # LOGGING & MONITORING
    # ============================================================================
    DEBUG: bool = os.getenv('DEBUG', 'false').lower() == 'true'
    LOG_LEVEL: str = 'DEBUG' if DEBUG else 'INFO'
    LOG_FILE: str = os.getenv('LOG_FILE', 'logs/qbc_node.log')
    LOG_MAX_BYTES: int = int(os.getenv('LOG_MAX_BYTES', '10485760'))  # 10MB
    LOG_BACKUP_COUNT: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))

    METRICS_PORT: int = int(os.getenv('METRICS_PORT', 9090))
    ENABLE_METRICS: bool = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'

    @classmethod
    def get_bootstrap_peers(cls) -> list:
        """
        Parse bootstrap peers from environment variable
        
        Returns:
            List of bootstrap peer multiaddrs
        """
        if not cls.BOOTSTRAP_PEERS:
            return []
        return [p.strip() for p in cls.BOOTSTRAP_PEERS.split(',') if p.strip()]

    @classmethod
    def verify_emission_schedule(cls) -> bool:
        """Verify that phi-halving emission schedule is valid.

        Checks:
        1. Phi-halving rewards are monotonically decreasing.
        2. The phi-halving series converges (to ~618M QBC from mining).
        3. TAIL_EMISSION_REWARD is positive and less than INITIAL_REWARD.
        4. Total phi-halving emission (before tail kicks in) is under MAX_SUPPLY.

        The tail emission is a fixed reward per block that bridges the gap
        between the convergent phi-halving sum (~651M QBC) and MAX_SUPPLY
        (3.3B QBC).  The consensus engine enforces the cap by clamping
        rewards when total_supply reaches MAX_SUPPLY.
        """
        PHI = Decimal(str(cls.PHI))
        prev_reward = cls.INITIAL_REWARD + 1
        total = cls.GENESIS_PREMINE
        for era in range(100):
            reward = cls.INITIAL_REWARD / (PHI ** era)
            if reward < Decimal('0.00000001'):
                break
            if reward >= prev_reward:
                return False  # Rewards must strictly decrease
            prev_reward = reward
            total += reward * cls.HALVING_INTERVAL
        # Phi-halving total must be under MAX_SUPPLY (tail emission fills the rest)
        if total > cls.MAX_SUPPLY:
            return False
        # Tail emission must be valid
        if cls.TAIL_EMISSION_REWARD <= 0:
            return False
        if cls.TAIL_EMISSION_REWARD >= cls.INITIAL_REWARD:
            return False
        return True

    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration.

        Raises ValueError for any configuration that would cause the node
        to malfunction at runtime.  This prevents the node from starting
        in an unsafe or misconfigured state.
        """
        required = ['ADDRESS', 'PRIVATE_KEY_HEX', 'PUBLIC_KEY_HEX']
        missing = [k for k in required if not getattr(cls, k)]

        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}\n"
                f"Run: python scripts/generate_keys.py"
            )

        # ── Economics validation ──────────────────────────────────────
        if cls.MAX_SUPPLY <= 0:
            raise ValueError("MAX_SUPPLY must be positive")

        if cls.INITIAL_REWARD <= 0:
            raise ValueError("INITIAL_REWARD must be positive")

        if cls.HALVING_INTERVAL <= 0:
            raise ValueError("HALVING_INTERVAL must be positive")

        if cls.GENESIS_PREMINE < 0:
            raise ValueError("GENESIS_PREMINE must be non-negative")

        if cls.GENESIS_PREMINE >= cls.MAX_SUPPLY:
            raise ValueError("GENESIS_PREMINE must be less than MAX_SUPPLY")

        if cls.AETHER_FEE_MIN_QBC >= cls.AETHER_FEE_MAX_QBC:
            raise ValueError("AETHER_FEE_MIN_QBC must be less than AETHER_FEE_MAX_QBC")

        if not cls.verify_emission_schedule():
            raise ValueError("Emission schedule is not monotonically decreasing or exceeds MAX_SUPPLY")

        if cls.COINBASE_MATURITY < 1:
            raise ValueError("COINBASE_MATURITY must be at least 1")

        # ── Network / DB validation (critical for runtime) ───────────
        if cls.CHAIN_ID <= 0:
            raise ValueError(f"CHAIN_ID must be positive, got {cls.CHAIN_ID}")

        if not cls.DATABASE_URL or '://' not in cls.DATABASE_URL:
            raise ValueError(
                f"DATABASE_URL must be a valid connection string, "
                f"got: '{cls.DATABASE_URL[:40] if cls.DATABASE_URL else ''}'"
            )

        if cls.RPC_PORT < 1 or cls.RPC_PORT > 65535:
            raise ValueError(f"RPC_PORT must be 1-65535, got {cls.RPC_PORT}")

        # ── Consensus validation ─────────────────────────────────────
        if cls.INITIAL_DIFFICULTY <= 0:
            raise ValueError(f"INITIAL_DIFFICULTY must be positive, got {cls.INITIAL_DIFFICULTY}")

        if cls.DIFFICULTY_FLOOR <= 0:
            raise ValueError(f"DIFFICULTY_FLOOR must be positive, got {cls.DIFFICULTY_FLOOR}")

        if cls.DIFFICULTY_CEILING <= cls.DIFFICULTY_FLOOR:
            raise ValueError(
                f"DIFFICULTY_CEILING ({cls.DIFFICULTY_CEILING}) must be greater "
                f"than DIFFICULTY_FLOOR ({cls.DIFFICULTY_FLOOR})"
            )

        if cls.MAX_REORG_DEPTH < 1:
            raise ValueError(f"MAX_REORG_DEPTH must be at least 1, got {cls.MAX_REORG_DEPTH}")

        if cls.TARGET_BLOCK_TIME <= 0:
            raise ValueError(f"TARGET_BLOCK_TIME must be positive, got {cls.TARGET_BLOCK_TIME}")

        # ── Fee validation ───────────────────────────────────────────
        if cls.FEE_BURN_PERCENTAGE < 0.0 or cls.FEE_BURN_PERCENTAGE > 1.0:
            raise ValueError(
                f"FEE_BURN_PERCENTAGE must be between 0.0 and 1.0, "
                f"got {cls.FEE_BURN_PERCENTAGE}"
            )

        if cls.BLOCK_GAS_LIMIT < 21000:
            raise ValueError(f"BLOCK_GAS_LIMIT must be at least 21000, got {cls.BLOCK_GAS_LIMIT}")

    @classmethod
    def _compute_supply_at_height(cls, target_height: int) -> Decimal:
        """Compute total QBC emitted from genesis through target_height.

        Uses era-level arithmetic (not block-by-block) for efficiency.
        Accounts for phi-halving and tail emission.
        """
        if target_height < 0:
            return Decimal('0')

        PHI = Decimal(str(cls.PHI))
        total = cls.GENESIS_PREMINE
        h = 0

        while h <= target_height:
            era = h // cls.HALVING_INTERVAL
            era_end_block = (era + 1) * cls.HALVING_INTERVAL - 1
            segment_end = min(era_end_block, target_height)
            blocks_in_segment = segment_end - h + 1

            phi_reward = cls.INITIAL_REWARD / (PHI ** era)
            reward = phi_reward if phi_reward >= cls.TAIL_EMISSION_REWARD else cls.TAIL_EMISSION_REWARD

            remaining = cls.MAX_SUPPLY - total
            max_blocks = int(remaining / reward) if reward > 0 else 0
            if blocks_in_segment > max_blocks:
                total += reward * max_blocks
                break
            total += reward * blocks_in_segment
            h = segment_end + 1

        return min(total, cls.MAX_SUPPLY)

    @classmethod
    def _compute_emission_projection(cls) -> dict:
        """Compute accurate emission projection milestones.

        Uses the actual phi-halving + tail emission formula to project
        total supply at various time milestones.
        """
        blocks_per_year = int(365.25 * 86400 / cls.TARGET_BLOCK_TIME)
        milestones = {}
        for target_yr in [1.618, 10, 20, 33, 50, 100]:
            target_height = int(target_yr * blocks_per_year)
            supply = cls._compute_supply_at_height(target_height)
            pct = float(supply / cls.MAX_SUPPLY * 100)
            milestones[target_yr] = (float(supply), pct)
        return milestones

    @classmethod
    def display(cls) -> str:
        """Return formatted configuration summary"""
        rust_p2p_status = "Enabled" if cls.ENABLE_RUST_P2P else "Disabled (using Python P2P)"

        # Compute accurate emission projections
        try:
            proj = cls._compute_emission_projection()
            yr1_6 = proj.get(1.618, (0, 0))
            yr10 = proj.get(10, (0, 0))
            yr20 = proj.get(20, (0, 0))
            yr33 = proj.get(33, (0, 0))
            emission_lines = (
                f"  Year 1.618 (phi):     ~{yr1_6[0] / 1e6:.0f}M QBC ({yr1_6[1]:.1f}%)\n"
                f"  Year 10:              ~{yr10[0] / 1e6:.0f}M QBC ({yr10[1]:.1f}%)\n"
                f"  Year 20:              ~{yr20[0] / 1e6:.0f}M QBC ({yr20[1]:.1f}%)\n"
                f"  Year 33:              ~{yr33[0] / 1e6:.0f}M QBC ({yr33[1]:.1f}%)"
            )
        except Exception:
            emission_lines = "  (projection unavailable)"

        return f"""
╔══════════════════════════════════════════════════════════════╗
║           QUBITCOIN NODE - SUSY ECONOMICS v1.0               ║
╚══════════════════════════════════════════════════════════════╝

Node Identity:
  Address:              {cls.ADDRESS[:40] + '...' if cls.ADDRESS else '(not set)'}

Supersymmetric Economics:
  Max Supply:           {cls.MAX_SUPPLY:,} QBC (3.3 billion)
  Block Time:           {cls.TARGET_BLOCK_TIME} seconds
  Initial Reward:       {cls.INITIAL_REWARD} QBC/block
  Tail Emission:        {cls.TAIL_EMISSION_REWARD} QBC/block (after phi-halving drops below)
  Genesis Premine:      {cls.GENESIS_PREMINE:,} QBC (~{float(cls.GENESIS_PREMINE / cls.MAX_SUPPLY * 100):.2f}%)
  Halving Interval:     {cls.HALVING_INTERVAL:,} blocks (phi years)
  Emission Period:      {cls.EMISSION_PERIOD} years (phi-halving), then tail emission
  Golden Ratio (phi):   {cls.PHI}

Quantum Settings:
  Mode:                 {'Local Simulator' if cls.USE_LOCAL_ESTIMATOR else 'IBM Quantum'}
  VQE Max Iterations:   {cls.VQE_MAXITER}

Network:
  RPC Port:             {cls.RPC_PORT}
  Rust P2P:             {rust_p2p_status}
  Rust P2P Port:        {cls.RUST_P2P_PORT if cls.ENABLE_RUST_P2P else 'N/A'}
  Rust P2P gRPC:        {cls.RUST_P2P_GRPC if cls.ENABLE_RUST_P2P else 'N/A'}

Consensus:
  Initial Difficulty:   {cls.INITIAL_DIFFICULTY}
  Target Block Time:    {cls.TARGET_BLOCK_TIME}s
  Difficulty Window:    {cls.DIFFICULTY_WINDOW} blocks (per-block adjustment)
  Max Difficulty Change: +/-{cls.MAX_DIFFICULTY_CHANGE * 100:.0f}%
  Coinbase Maturity:    {cls.COINBASE_MATURITY} blocks

Mining:
  Auto Mine:            {cls.AUTO_MINE}
  Mining Interval:      {cls.MINING_INTERVAL}s (hardcoded)

Database:
  URL:                  {cls.DATABASE_URL.split('@')[1].split('?')[0] if '@' in cls.DATABASE_URL else cls.DATABASE_URL.split('?')[0]}

Storage:
  IPFS API:             {cls.IPFS_API}
  IPFS Gateway Port:    {cls.IPFS_GATEWAY_PORT} (CockroachDB admin on 8080)
  Snapshot Interval:    {cls.SNAPSHOT_INTERVAL} blocks

Expected Emission (phi-halving + tail emission):
{emission_lines}

╚══════════════════════════════════════════════════════════════╝
"""


# Auto-populate contract addresses from contract_registry.json at import time.
# Must run before validate() so addresses are available for any checks.
Config._load_contract_registry()

# Initialize and validate on import.
# Critical validation failures (invalid economics, bad DB URL, bad consensus
# params) raise immediately to prevent the node from starting in an unsafe
# state.  Only the "missing keys" case is tolerated as a warning, because
# tests and key-generation scripts import this module before keys exist.
try:
    Config.validate()
except ValueError as e:
    # ADDRESS/PRIVATE_KEY_HEX/PUBLIC_KEY_HEX may legitimately be empty
    # during test imports or key generation scripts.  Allow those through
    # with a warning.  All other validation failures are FATAL — the node
    # must not start with invalid economics, DB config, or consensus params.
    err_str = str(e)
    if 'Missing required configuration' in err_str:
        import warnings
        warnings.warn(
            f"Configuration incomplete (node will fail at startup): {e}"
        )
    else:
        raise
