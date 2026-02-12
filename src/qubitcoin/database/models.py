"""
Data models for Qubitcoin
Defines core blockchain structures with QVM and Aether Tree support
"""
from dataclasses import dataclass, asdict, field
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
        d = asdict(self)
        d['amount'] = str(d['amount'])
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'UTXO':
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        filtered['amount'] = Decimal(filtered['amount'])
        return cls(**filtered)


@dataclass
class Transaction:
    """Transaction with UTXO inputs/outputs and QVM contract support"""
    txid: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    fee: Decimal
    signature: str
    public_key: str
    timestamp: float
    block_height: Optional[int] = None
    status: str = 'pending'
    # QVM fields
    tx_type: str = 'transfer'  # 'transfer', 'contract_deploy', 'contract_call'
    to_address: Optional[str] = None  # Contract address for calls, None for deploy
    data: Optional[str] = None  # Hex-encoded calldata or bytecode
    gas_limit: int = 0
    gas_price: Decimal = Decimal(0)
    nonce: int = 0

    def calculate_txid(self) -> str:
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
        d = asdict(self)
        d['fee'] = str(d['fee'])
        d['gas_price'] = str(d['gas_price'])
        d['outputs'] = [
            {'address': o['address'], 'amount': str(o['amount'])}
            for o in d['outputs']
        ]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'Transaction':
        data = dict(data)  # Don't mutate the original
        data['fee'] = Decimal(data.get('fee', '0'))
        data['gas_price'] = Decimal(data.get('gas_price', '0'))
        data['outputs'] = [
            {'address': o['address'], 'amount': Decimal(o['amount'])}
            for o in data.get('outputs', [])
        ]
        data.setdefault('tx_type', 'transfer')
        data.setdefault('to_address', None)
        data.setdefault('data', None)
        data.setdefault('gas_limit', 0)
        data.setdefault('nonce', 0)
        # Filter to known fields to prevent TypeError on unexpected keys
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class TransactionReceipt:
    """Receipt generated after executing a transaction (EVM-compatible)"""
    txid: str
    block_height: int
    block_hash: str
    tx_index: int
    from_address: str
    to_address: Optional[str]
    contract_address: Optional[str]
    gas_used: int
    gas_limit: int
    status: int  # 1 = success, 0 = revert
    logs: List[Dict[str, Any]] = field(default_factory=list)
    return_data: str = ''
    revert_reason: str = ''
    state_root: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Account:
    """EVM-compatible account for QVM contract state"""
    address: str
    nonce: int = 0
    balance: Decimal = Decimal(0)
    code_hash: str = ''
    storage_root: str = ''

    def is_contract(self) -> bool:
        return bool(self.code_hash)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['balance'] = str(d['balance'])
        return d


@dataclass
class Block:
    """Block containing quantum proof, transactions, and state root"""
    height: int
    prev_hash: str
    proof_data: dict
    transactions: List[Transaction]
    timestamp: float
    difficulty: float
    block_hash: Optional[str] = None
    state_root: str = ''
    receipts_root: str = ''
    thought_proof: Optional[dict] = None

    def calculate_hash(self) -> str:
        data = {
            'height': self.height,
            'prev_hash': self.prev_hash,
            'proof': self.proof_data,
            'transactions': [tx.txid for tx in self.transactions],
            'timestamp': self.timestamp,
            'difficulty': self.difficulty,
            'state_root': self.state_root,
            'receipts_root': self.receipts_root
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def to_dict(self) -> dict:
        return {
            'height': self.height,
            'prev_hash': self.prev_hash,
            'proof_data': self.proof_data,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'timestamp': self.timestamp,
            'difficulty': self.difficulty,
            'block_hash': self.block_hash or self.calculate_hash(),
            'state_root': self.state_root,
            'receipts_root': self.receipts_root,
            'thought_proof': self.thought_proof
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Block':
        data = dict(data)  # Don't mutate the original
        data['transactions'] = [
            Transaction.from_dict(tx) for tx in data.get('transactions', [])
        ]
        data.setdefault('state_root', '')
        data.setdefault('receipts_root', '')
        data.setdefault('thought_proof', None)
        # Filter to known fields to prevent TypeError on unexpected keys
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class ProofOfSUSY:
    """Proof-of-SUSY-Alignment data structure"""
    challenge: List[tuple]
    params: List[float]
    energy: float
    signature: str
    public_key: str
    miner_address: str

    def to_dict(self) -> dict:
        return asdict(self)

    def is_valid(self, difficulty: float) -> bool:
        return self.energy < difficulty


@dataclass
class ProofOfThought:
    """Aether Tree Proof-of-Thought data structure"""
    thought_hash: str
    reasoning_steps: List[Dict[str, Any]]
    phi_value: float
    knowledge_root: str
    validator_address: str
    signature: str
    timestamp: float

    def to_dict(self) -> dict:
        return asdict(self)

    def calculate_hash(self) -> str:
        data = {
            'reasoning_steps': self.reasoning_steps,
            'phi_value': self.phi_value,
            'knowledge_root': self.knowledge_root,
            'timestamp': self.timestamp
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
