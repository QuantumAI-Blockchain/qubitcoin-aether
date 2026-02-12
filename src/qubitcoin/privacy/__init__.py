"""
Privacy module for Qubitcoin — Susy Swaps
Implements opt-in confidential transactions using Pedersen commitments,
Bulletproofs range proofs, and stealth addresses.
"""
from .commitments import PedersenCommitment
from .range_proofs import RangeProofGenerator, RangeProofVerifier
from .stealth import StealthAddressManager
from .susy_swap import SusySwapBuilder

__all__ = [
    'PedersenCommitment',
    'RangeProofGenerator',
    'RangeProofVerifier',
    'StealthAddressManager',
    'SusySwapBuilder',
]
