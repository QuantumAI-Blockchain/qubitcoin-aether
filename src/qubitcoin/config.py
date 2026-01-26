"""
Configuration management for Qubitcoin node
Centralized settings with validation
"""

import os
from decimal import Decimal
from typing import Optional
from dotenv import load_dotenv

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
    # NETWORK SETTINGS
    # ============================================================================
    P2P_PORT: int = int(os.getenv('P2P_PORT', 4001))
    RPC_PORT: int = int(os.getenv('RPC_PORT', 5000))
    RPC_HOST: str = os.getenv('RPC_HOST', '0.0.0.0')
    
    PEER_SEEDS: list = []  # Will be populated from env
    MAX_PEERS: int = 50
    PEER_TIMEOUT: int = 300
    MESSAGE_CACHE_SIZE: int = 10000
    GOSSIP_RATE_LIMIT: int = 100
    
    # ============================================================================
    # DATABASE SETTINGS
    # ============================================================================
    DATABASE_URL: str = os.getenv(
        'DATABASE_URL',
        'postgresql+psycopg2://root@localhost:26257/qbc?sslmode=disable'
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    
    # ============================================================================
    # STORAGE SETTINGS
    # ============================================================================
    IPFS_API: str = os.getenv('IPFS_API', '/ip4/127.0.0.1/tcp/5001/http')
    PINATA_JWT: Optional[str] = os.getenv('PINATA_JWT')
    SNAPSHOT_INTERVAL: int = int(os.getenv('SNAPSHOT_INTERVAL', 100))
    
    # ============================================================================
    # ECONOMIC PARAMETERS
    # ============================================================================
    MAX_SUPPLY: Decimal = Decimal('21000000')
    INITIAL_REWARD: Decimal = Decimal('50')
    HALVING_INTERVAL: int = 210000
    MIN_FEE: Decimal = Decimal('0.01')
    FEE_RATE: Decimal = Decimal('0.001')
    
    # ============================================================================
    # CONSENSUS PARAMETERS
    # ============================================================================
    INITIAL_DIFFICULTY: float = 0.5
    TARGET_BLOCK_TIME: int = 600  # 10 minutes
    DIFFICULTY_ADJUSTMENT_INTERVAL: int = 2016
    CONFIRMATION_DEPTH: int = 6
    MAX_REORG_DEPTH: int = 100
    
    # ============================================================================
    # MINING SETTINGS
    # ============================================================================
    MINING_INTERVAL: int = int(os.getenv('MINING_INTERVAL', 10))
    AUTO_MINE: bool = os.getenv('AUTO_MINE', 'true').lower() == 'true'
    
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
    
    # Prometheus metrics
    METRICS_PORT: int = int(os.getenv('METRICS_PORT', 9090))
    ENABLE_METRICS: bool = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
    
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
        
        # Validate economic parameters
        if cls.MAX_SUPPLY <= 0:
            raise ValueError("MAX_SUPPLY must be positive")
        
        if cls.INITIAL_REWARD <= 0:
            raise ValueError("INITIAL_REWARD must be positive")
        
        if cls.HALVING_INTERVAL <= 0:
            raise ValueError("HALVING_INTERVAL must be positive")
    
    @classmethod
    def display(cls) -> str:
        """Return formatted configuration summary"""
        return f"""
╔══════════════════════════════════════════════════════════════╗
║                  QUBITCOIN NODE CONFIG                       ║
╚══════════════════════════════════════════════════════════════╝

Node Identity:
  Address:              {cls.ADDRESS[:40]}...
  
Quantum Settings:
  Mode:                 {'Local Simulator' if cls.USE_LOCAL_ESTIMATOR else 'IBM Quantum'}
  VQE Max Iterations:   {cls.VQE_MAXITER}
  
Network:
  RPC Port:             {cls.RPC_PORT}
  P2P Port:             {cls.P2P_PORT}
  
Economics:
  Max Supply:           {cls.MAX_SUPPLY} QBC
  Initial Reward:       {cls.INITIAL_REWARD} QBC
  Halving Interval:     {cls.HALVING_INTERVAL} blocks
  
Consensus:
  Initial Difficulty:   {cls.INITIAL_DIFFICULTY}
  Target Block Time:    {cls.TARGET_BLOCK_TIME}s
  
Mining:
  Auto Mine:            {cls.AUTO_MINE}
  Mining Interval:      {cls.MINING_INTERVAL}s
  
Database:
  URL:                  {cls.DATABASE_URL.split('@')[0]}@***
  
Storage:
  IPFS:                 {cls.IPFS_API}
  Snapshot Interval:    {cls.SNAPSHOT_INTERVAL} blocks

╚══════════════════════════════════════════════════════════════╝
"""


# Initialize and validate on import
try:
    Config.validate()
except ValueError as e:
    # Don't fail on import, just warn
    import warnings
    warnings.warn(f"Configuration validation failed: {e}")
