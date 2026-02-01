"""
Multi-Chain Bridge Module
Cross-chain bridges for QBC ↔ ETH/SOL/etc.
"""

from .base import BaseBridge, ChainType, BridgeStatus
from .ethereum import EVMBridge
from .solana import SolanaBridge
from .manager import BridgeManager

__all__ = [
    'BaseBridge',
    'ChainType',
    'BridgeStatus',
    'EVMBridge',
    'SolanaBridge',
    'BridgeManager'
]
