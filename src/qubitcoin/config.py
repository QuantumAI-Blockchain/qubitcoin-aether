"""
Configuration management for Qubitcoin node
Supersymmetric Economics Model
"""

import os
from decimal import Decimal
from typing import Optional
from dotenv import load_dotenv
import math

load_dotenv()


class Config:
    """Global configuration for Qubitcoin node"""

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
    IBM_TOKEN: Optional[str] = os.getenv('IBM_TOKEN')
    IBM_INSTANCE: Optional[str] = os.getenv('IBM_INSTANCE')

    VQE_REPS: int = 1
    VQE_MAXITER: int = int(os.getenv('VQE_MAXITER', 50))
    VQE_TOLERANCE: float = 1e-6
    ENERGY_VALIDATION_TOLERANCE: float = 1e-3

    # ============================================================================
    # NETWORK SETTINGS (Legacy Python P2P - kept for compatibility)
    # ============================================================================
    P2P_PORT: int = int(os.getenv('P2P_PORT', 4001))
    RPC_PORT: int = int(os.getenv('RPC_PORT', 5000))
    RPC_HOST: str = os.getenv('RPC_HOST', '0.0.0.0')

    PEER_SEEDS: list = []
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
    BOOTSTRAP_PEERS: str = os.getenv('BOOTSTRAP_PEERS', '')

    # ============================================================================
    # DATABASE SETTINGS
    # ============================================================================
    DATABASE_URL: str = os.getenv(
        'DATABASE_URL',
        'postgresql://root@localhost:8080/qbc?sslmode=verify-full&sslrootcert=/home/ash/qubitcoin/data/certs/ca.crt&sslcert=/home/ash/qubitcoin/data/certs/client.root.crt&sslkey=/home/ash/qubitcoin/data/certs/client.root.key'
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ============================================================================
    # STORAGE SETTINGS
    # ============================================================================
    IPFS_API: str = os.getenv('IPFS_API', '/ip4/127.0.0.1/tcp/5002/http')
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

    # Fee structure (micro-fees for high frequency)
    MIN_FEE: Decimal = Decimal('0.0001')
    FEE_RATE: Decimal = Decimal('0.0001')

    # ============================================================================
    # CONSENSUS PARAMETERS
    # ============================================================================
    INITIAL_DIFFICULTY: float = 0.5
    DIFFICULTY_ADJUSTMENT_INTERVAL: int = 1000  # Adjust every 1000 blocks (~55 min)
    CONFIRMATION_DEPTH: int = 180  # Wait 180 blocks (~10 min) for finality
    MAX_REORG_DEPTH: int = 100

    # ============================================================================
    # MINING SETTINGS (Production - Hardcoded)
    # ============================================================================
    MINING_INTERVAL: int = 1  # Attempt every 1 second (VQE + wait)
    AUTO_MINE: bool = True  # Always enabled in production

    # ============================================================================
    # BRIDGE SETTINGS
    # ============================================================================
    INFURA_URL: Optional[str] = os.getenv('INFURA_URL')
    ETH_PRIVATE_KEY: Optional[str] = os.getenv('ETH_PRIVATE_KEY')
    BRIDGE_CONTRACT_ADDRESS: Optional[str] = os.getenv('BRIDGE_CONTRACT_ADDRESS')

    # ============================================================================
    # LOGGING & MONITORING
    # ============================================================================
    DEBUG: bool = os.getenv('DEBUG', 'false').lower() == 'true'
    LOG_LEVEL: str = 'DEBUG' if DEBUG else 'INFO'
    LOG_FILE: str = 'logs/qbc_node.log'
    LOG_MAX_BYTES: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5

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
    def validate(cls) -> None:
        """Validate critical configuration"""
        required = ['ADDRESS', 'PRIVATE_KEY_HEX', 'PUBLIC_KEY_HEX']
        missing = [k for k in required if not getattr(cls, k)]

        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}\n"
                f"Run: python scripts/generate_keys.py"
            )

        if cls.MAX_SUPPLY <= 0:
            raise ValueError("MAX_SUPPLY must be positive")

        if cls.INITIAL_REWARD <= 0:
            raise ValueError("INITIAL_REWARD must be positive")

        if cls.HALVING_INTERVAL <= 0:
            raise ValueError("HALVING_INTERVAL must be positive")

    @classmethod
    def display(cls) -> str:
        """Return formatted configuration summary"""
        rust_p2p_status = "Enabled" if cls.ENABLE_RUST_P2P else "Disabled (using Python P2P)"
        
        return f"""
╔══════════════════════════════════════════════════════════════╗
║           QUBITCOIN NODE - SUSY ECONOMICS v1.0               ║
╚══════════════════════════════════════════════════════════════╝

Node Identity:
  Address:              {cls.ADDRESS[:40]}...

Supersymmetric Economics:
  Max Supply:           {cls.MAX_SUPPLY:,} QBC (3.3 billion)
  Block Time:           {cls.TARGET_BLOCK_TIME} seconds
  Initial Reward:       {cls.INITIAL_REWARD} QBC/block
  Halving Interval:     {cls.HALVING_INTERVAL:,} blocks (φ years)
  Emission Period:      {cls.EMISSION_PERIOD} years
  Golden Ratio (φ):     {cls.PHI}

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
  Adjustment Interval:  {cls.DIFFICULTY_ADJUSTMENT_INTERVAL} blocks

Mining:
  Auto Mine:            {cls.AUTO_MINE}
  Mining Interval:      {cls.MINING_INTERVAL}s (hardcoded)

Database:
  URL:                  {cls.DATABASE_URL.split('@')[1].split('?')[0]}

Storage:
  IPFS:                 {cls.IPFS_API}
  Snapshot Interval:    {cls.SNAPSHOT_INTERVAL} blocks

Expected Emission:
  Year 1.618 (φ):       ~236M QBC (7.2%)
  Year 10:              ~1.65B QBC (50%)
  Year 20:              ~2.97B QBC (90%)
  Year 33:              ~3.27B QBC (99%)

╚══════════════════════════════════════════════════════════════╝
"""


# Initialize and validate on import
try:
    Config.validate()
except ValueError as e:
    import warnings
    warnings.warn(f"Configuration validation failed: {e}")
