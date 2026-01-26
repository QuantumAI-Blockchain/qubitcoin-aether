"""
Data models for Qubitcoin
Defines core blockchain structures
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from decimal import Decimal
import hashlib
import json


@dataclass
class UTXO:
    """Unspent Transaction Output"""
    txid: str
    vout: int
    amount: Decimal
    address: str
    proof: dict
    block_height: Optional[int] = None
    spent: bool = False
    spent_by: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        d = asdict(self)
        d['amount'] = str(d['amount'])
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UTXO':
        """Create from dictionary"""
        data['amount'] = Decimal(data['amount'])
        return cls(**data)


@dataclass
class Transaction:
    """Transaction with UTXO inputs/outputs"""
    txid: str
    inputs: List[Dict[str, Any]]  # [{'txid': str, 'vout': int, 'signature': str}]
    outputs: List[Dict[str, Any]]  # [{'address': str, 'amount': Decimal}]
    fee: Decimal
    signature: str
    public_key: str
    timestamp: float
    block_height: Optional[int] = None
    status: str = 'pending'
    
    def calculate_txid(self) -> str:
        """Calculate deterministic transaction ID"""
        data = {
            'inputs': self.inputs,
            'outputs': [
                {'address': o['address'], 'amount': str(o['amount'])} 
                for o in self.outputs
            ],
            'fee': str(self.fee),
            'timestamp': self.timestamp
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        d = asdict(self)
        d['fee'] = str(d['fee'])
        d['outputs'] = [
            {'address': o['address'], 'amount': str(o['amount'])} 
            for o in d['outputs']
        ]
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Transaction':
        """Create from dictionary"""
        data['fee'] = Decimal(data['fee'])
        data['outputs'] = [
            {'address': o['address'], 'amount': Decimal(o['amount'])} 
            for o in data['outputs']
        ]
        return cls(**data)


@dataclass
class Block:
    """Block containing quantum proof and transactions"""
    height: int
    prev_hash: str
    proof_data: dict
    transactions: List[Transaction]
    timestamp: float
    difficulty: float
    block_hash: Optional[str] = None
    
    def calculate_hash(self) -> str:
        """Calculate block hash"""
        data = {
            'height': self.height,
            'prev_hash': self.prev_hash,
            'proof': self.proof_data,
            'transactions': [tx.txid for tx in self.transactions],
            'timestamp': self.timestamp,
            'difficulty': self.difficulty
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'height': self.height,
            'prev_hash': self.prev_hash,
            'proof_data': self.proof_data,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'timestamp': self.timestamp,
            'difficulty': self.difficulty,
            'block_hash': self.block_hash or self.calculate_hash()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Block':
        """Create from dictionary"""
        data['transactions'] = [
            Transaction.from_dict(tx) for tx in data['transactions']
        ]
        return cls(**data)


@dataclass
class ProofOfSUSY:
    """Proof-of-SUSY-Alignment data structure"""
    challenge: List[tuple]  # Hamiltonian [(coeff, pauli_str), ...]
    params: List[float]  # VQE optimized parameters
    energy: float  # Ground state energy
    signature: str  # Dilithium signature
    public_key: str  # Miner's public key
    miner_address: str  # Miner's address
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def is_valid(self, difficulty: float) -> bool:
        """Check if proof meets difficulty"""
        return self.energy < difficulty
